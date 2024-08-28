#!/usr/bin/env python3
import os
import re
import time
import mariadb
import datetime
import configmanager


dateRegexNew = r"^\[(\d{4})/(\d{2})/(\d{2}), (\d{2}):(\d{2}):(\d{2}) UTC\][ ]*"
serverMsgPrefix = "# Server: "



def connectDatabase(config):
  try:
    dbConf = config["db"]
    connection = mariadb.connect(
        user = dbConf["user"],
        password = dbConf["password"],
        host = dbConf["host"],
        port = dbConf["port"],
        database = dbConf["database"],
        autocommit = False
    )
  except mariadb.Error as e:
    print(f"Error connecting to MariaDB Platform: {e}")
    exit()

  return connection




def setupDatabase(connection):
  cursor = connection.cursor()

  # Will create table. If it exists, drop it first.
  playersTableCreation = """CREATE OR REPLACE TABLE players (
    id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    name TINYTEXT NOT NULL UNIQUE,
    firstLogin DATETIME,
    lastSeen DATETIME,
    totalTime BIGINT UNSIGNED,
    nLogins INT,
    nMessages INT,
    chunks INT
  );"""

  metaTableCreation = """CREATE OR REPLACE TABLE meta (
    id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    analyzeDate DATETIME
  );"""

  cursor.execute(playersTableCreation)
  cursor.execute(metaTableCreation)
  connection.commit()


def updateLastSeen(p: dict, time):
  try:
    if p["lastSeen"] < time:
      p["lastSeen"] = time
  except KeyError:
      p["lastSeen"] = time


def datetimeFromRegex(groups):
  r = [int(i) for i in groups[:6]]
  return datetime.datetime(r[0], r[1], r[2], r[3], r[4], r[5])


def dateFromRegex(groups):
  r = [int(i) for i in groups[:3]]
  return datetime.date(r[0], r[1], r[2])



def analyzeMapgen(files, d: dict):
  startTime = time.perf_counter()
  print("Blaming chunks...", end="", flush=True)

  chunkGenerations = {}
  regexAnon = dateRegexNew + r"# Server: Mapgen working, expect lag. (Chunks: (\d*).)$"
  regexBlame = dateRegexNew + r"# Server: Mapgen scrambling. Blame <(.*?)> for lag. Chunks: (\d*).$"
  for fileName in files:
    dateString = fileName.split("/")[-1]
    year = int(dateString[0:4])
    month = int(dateString[5:7])
    day = int(dateString[8:10])
    date = datetime.date(year, month, day)
    chunkGenerations[date] = 0

    with open(fileName) as f:
      for l in f:
        try:
          if l[30] != "#":
            # ToDo: Are there any mapgen messages before the current datetime format was introduced?
            continue
        except IndexError:
            pass
        res = re.search(regexBlame, l)
        if res:
          g = res.groups()
          name = g[6]
          chunks = int(g[7])
          if not d.get(name):
            d[name] = {}
          if not d[name].get("chunks"):
            d[name]["chunks"] = 0
          d[name]["chunks"] += chunks

          print(f"----{date}")
          date = dateFromRegex(g)
          print(date)
          if not chunkGenerations.get(date):
            # This is needed for the chatlog of 2024-07-18, because at there is a chunk generation of
            # 2024-07-19 at the end.
            chunkGenerations[date] = 0
          chunkGenerations[date] += chunks
          continue

        res = re.search(regexAnon, l)
        if res:
          g = res.groups()
          chunks = int(g[6])
          d[name]["chunks"] += int(chunks)
          date = dateFromRegex(res.groups())
          chunkGenerations[date] += chunks

  endTime = time.perf_counter()
  print(f" {endTime-startTime:.2f} s", flush=True)
  return d, chunkGenerations



def analyzeLogins(files, d: dict):
  # Issues
  # - Other logout messages (kicking etc.)
  # - Player has not logged out yet (staying logged in past midnight UTC, especially on first login)
  # - Name changes while logged in
  startTime = time.perf_counter()
  print("Stalking logins...", end="", flush=True)

  joinString = dateRegexNew + r"\*{3} <(.*?)> joined the game.$"
  # The quit string regex does not have a $ at the end, because an
  # additional comment in parenthesis may follow.
  quitString = dateRegexNew + r"\*{3} <(.*?)> left the game."
  for fileName in files:
    with open(fileName) as f:
      for l in f:
        try:
          if l[30] != "*":
            continue
        except IndexError:
            pass
        res = re.search(joinString, l)
        if res:
          dateGroups = res.groups()[:-1]
          name = res.groups()[-1]
          r = [int(i) for i in dateGroups]
          startDate = datetime.datetime(r[0], r[1], r[2], r[3], r[4], r[5]) # ToDo: Add timezone info
          if not d.get(name):
            d[name] = {}
          if not d[name].get("nLogin"):
            d[name]["nLogin"] = 0
            d[name]["firstLogin"] = startDate
          d[name]["start"] = startDate
          d[name]["nLogin"] += 1
          updateLastSeen(d[name], startDate)
          continue

        res = re.search(quitString, l)
        if res:
          dateGroups = res.groups()[:-1]
          name = res.groups()[-1]
          r = [int(i) for i in dateGroups]
          endDate = datetime.datetime(r[0], r[1], r[2], r[3], r[4], r[5]) # ToDo: Add timezone info
          try:
            dt = endDate - d[name]["start"]
          except KeyError:
            #print("Warning: KeyError on {}".format(l))
            continue
          if not d[name].get("totalTime"):
            d[name]["totalTime"] = datetime.timedelta()
          d[name]["totalTime"] += dt
          updateLastSeen(d[name], endDate)
          if dt > datetime.timedelta(days=1):
            pass#print(dt, name)

  endTime = time.perf_counter()
  print(f" {endTime-startTime:.2f} s", flush=True)
  return d



def analyzeChatMessages(files, d: dict):
  startTime = time.perf_counter()
  print("Reading messages...", end="", flush=True)

  # Get all lines that start with a username surrounded by chevrons (< and >),
  # i.e. all user messages in public chat.
  # Example with all optional groups present:
  # <!boxface [Caverns: 1059,-5791,-8929]!> HELP
  # Example without realm:
  # <J2 [-232,-4,1]> hello?
  regex = (dateRegexNew +      # First, the timestamp
          "<!?(.*?)"           # Then, capture the user name; optional ! in case of shouting: "<!boxface"
          r"( \["              # Open a new group in case the player is marked, with coordinates show in brackets: " ["
          "(.*?: ?)?"          # If this is the case, the realm comes next: "Caverns: "
                               # But realms were missing at the beginning of the servers life, so this is also an optional group!
                               # Also, there are three cases were the space after the colon is missing -_- (as of 2022-11-19)
          r"-?\d*,-?\d*,-?\d*" # The coordinates follow, minus sign is optional: "1059,-5791,-8929"
          r"\])?"              # Close the group for the player marking and make it optional: "]"
          "!?>"                # And the closing chevron with optional shouting finally ending this: "!>"
          )

  for fileName in files:
    with open(fileName) as f:
      for l in f:
        res = re.search(regex, l)
        if not res:
          continue
        name = res.groups()[6]
        if "[" in name:
          print(l)
        if not d.get(name):
          d[name] = {}
        if not d[name].get("nMsg"):
          d[name]["nMsg"] = 0
        d[name]["nMsg"] += 1

        r = [int(i) for i in res.groups()[:6]]
        date = datetime.datetime(r[0], r[1], r[2], r[3], r[4], r[5]) # ToDo: Add timezone info
        updateLastSeen(d[name], date)

  endTime = time.perf_counter()
  print(f" {endTime-startTime:.2f} s", flush=True)
  return d



def analyzePlanes(files, d: dict):
  startTime = time.perf_counter()
  print("Investigating planes of existence...", end="", flush=True)

  regex = dateRegexNew + serverMsgPrefix + "<(.*?)> has plane shifted to (.*?).$"
  for fileName in files:
    with open(fileName) as f:
      for l in f:
        res = re.search(regex, l)
        if not res:
          continue
        name = res.groups()[6]
        plane = res.groups()[7]
        if not d.get(name):
          d[name] = {}
        if not d[name].get("planes"):
          d[name]["planes"] = []
        if not plane in d[name]["planes"]:
          d[name]["planes"].append(plane)

  endTime = time.perf_counter()
  print(f" {endTime-startTime:.2f} s", flush=True)
  return d



def printPlayer(d, name):
  if not name in d:
    print(f"User <{name}> is not known.")
    return

  print(f"User: {name}")
  print(f"Last seen: {d[name]['lastSeen']}")
  print(f"First login: {d[name]['firstLogin']}")
  print(f"Time played: {d[name]['totalTime']}")
  print(f"Chunks generated: {d[name]['chunks']}")
  print(f"Chat messages sent: {d[name]['nMsg']}")
  if "planes" in d[name]:
    realms = ', '.join(d[name]['planes'])
    print(f"Visited {realms}")



if __name__ == "__main__":
  config = configmanager.readConfig()
  connection = connectDatabase(config)
  setupDatabase(connection)

  files = sorted(os.listdir(config["chatlogDir"]))
  files = [config["chatlogDir"] + f for f in files]
  d = {}
  d, chunkTimeline = analyzeMapgen(files, d)
  d = analyzeLogins(files, d)
  d = analyzeChatMessages(files, d)
  d = analyzePlanes(files, d)


  cursor = connection.cursor()
  query = "INSERT INTO players VALUES (NULL, ?, ?, ?, ?, ?, ?, ?);"
  for name in d:
    try:
        if d[name].get("nLogin"):
          nLogin = d[name]["nLogin"]
        else:
          nLogin = 0

        if d[name].get("firstLogin"):
          firstLogin = d[name]["firstLogin"]
        else:
          firstLogin = None

        if d[name].get("lastSeen"):
          lastSeen = d[name]["lastSeen"]
        else:
          lastSeen = None

        if d[name].get("totalTime"):
          totalTime = d[name]["totalTime"].total_seconds()
        else:
          totalTime = None

        if d[name].get("nMsg"):
          nMsg = d[name]["nMsg"]
        else:
          nMsg = 0

        if d[name].get("chunks"):
          chunks = d[name]["chunks"]
        else:
          chunks = 0

        cursor.execute(query, (name, firstLogin, lastSeen, totalTime, nLogin, nMsg, chunks))
    except mariadb.IntegrityError as e:
        pass

  query = "INSERT INTO meta VALUES (NULL, UTC_TIME());"
  cursor.execute(query, ())

  connection.commit()
