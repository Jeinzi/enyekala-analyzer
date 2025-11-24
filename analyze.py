#!/usr/bin/env python3
import os
import re
import time
import mariadb
import datetime
import database
import configmanager

from mobmessages import kill_ang


dateRegexNew = r"^\[(\d{4})/(\d{2})/(\d{2}), (\d{2}):(\d{2}):(\d{2}) UTC\][ ]*"
serverMsgPrefix = "# Server: "



def updateLastSeen(p: dict, time):
  try:
    if p["lastSeen"] < time:
      p["lastSeen"] = time
  except KeyError:
      p["lastSeen"] = time


def datetimeFromRegex(groups):
  r = [int(i) for i in groups[:6]]
  return datetime.datetime(*r)


def dateFromRegex(groups):
  r = [int(i) for i in groups[:3]]
  return datetime.date(*r)



def analyzeMapgen(l: str, data: dict):
  if not data.get("chunkGenerations"):
    data["chunkGenerations"] = {}
  d = data["players"]
  chunkGenerations = data["chunkGenerations"]
  matched = False

  regexAnon = dateRegexNew + r"# Server: Mapgen working, expect lag. (Chunks: (\d*).)$"
  regexBlame = dateRegexNew + r"# Server: Mapgen scrambling. Blame <(.*?)> for lag. Chunks: (\d*).$"

  try:
    if l[30] != "#":
      # ToDo: Are there any mapgen messages before the current datetime format was introduced?
      return False
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

    #print(f"----{date}")
    date = dateFromRegex(g)
    #print(date)
    if not chunkGenerations.get(date):
      # This is needed for the chatlog of 2024-07-18, because at there is a chunk generation of
      # 2024-07-19 at the end.
      chunkGenerations[date] = 0
    chunkGenerations[date] += chunks
    return True

  res = re.search(regexAnon, l)
  if res:
    g = res.groups()
    chunks = int(g[6])
    d[name]["chunks"] += int(chunks)
    date = dateFromRegex(res.groups())
    chunkGenerations[date] += chunks
    return True

  return matched


def analyzeLogins(l: str, data: dict):
  # Issues
  # - Other logout messages (kicking etc.)
  # - Player has not logged out yet (staying logged in past midnight UTC, especially on first login)
  # - Name changes while logged in

  d = data["players"]

  joinString = dateRegexNew + r"\*{3} <(.*?)> joined the game.$"
  # The quit string regex does not have a $ at the end, because an
  # additional comment in parenthesis may follow.
  quitString = dateRegexNew + r"\*{3} <(.*?)> left the game."
  matched = False

  try:
    if l[30] != "*":
      return False
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
    if not d[name].get("sessions"):
      d[name]["sessions"] = []
    if not d[name].get("nLogin"):
      d[name]["nLogin"] = 0
      d[name]["firstLogin"] = startDate
    d[name]["start"] = startDate
    d[name]["sessions"].append({"start": startDate, "end": None})
    d[name]["nLogin"] += 1
    updateLastSeen(d[name], startDate)
    return True

  res = re.search(quitString, l)
  if res:
    dateGroups = res.groups()[:-1]
    name = res.groups()[-1]
    r = [int(i) for i in dateGroups]
    endDate = datetime.datetime(r[0], r[1], r[2], r[3], r[4], r[5]) # ToDo: Add timezone info
    try:
      dt = endDate - d[name]["start"]
    except KeyError as e:
      #print("Warning: KeyError on {}".format(l))
      #print(e)
      print(f"KeyError: {l.rstrip("\n")}")
      return True
    if d[name]["sessions"][-1]["end"] == None:
      d[name]["sessions"][-1]["end"] = endDate
    else:
      print(f"Session of {name} never started")
    if not d[name].get("totalTime"):
      d[name]["totalTime"] = datetime.timedelta()
    d[name]["totalTime"] += dt
    updateLastSeen(d[name], endDate)
    if dt > datetime.timedelta(days=1):
      print(f"Session of {name} longer than one day ({dt})")
    return True

  return matched



def analyzeChatMessages(l: str, data: dict):
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
  d = data["players"]

  res = re.search(regex, l)
  if not res:
    return False
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
  return True



def analyzePlanes(l: str, data: dict):
  d = data["players"]
  regex = dateRegexNew + serverMsgPrefix + "<(.*?)> has plane shifted to (.*?).$"

  res = re.search(regex, l)
  if not res:
    return False
  name = res.groups()[6]
  plane = res.groups()[7]
  if not d.get(name):
    d[name] = {}
  if not d[name].get("planes"):
    d[name]["planes"] = []
  if not plane in d[name]["planes"]:
    d[name]["planes"].append(plane)

  return True


def analyzeSuicide(l: str, data: dict):
  d = data["players"]
  regex = dateRegexNew + serverMsgPrefix + "<(.*?)> ended (her|him)self.$"
  res = re.search(regex, l)
  if not res:
    return False
  name = res.groups()[6]
  if not d[name].get("suicides"):
    d[name]["suicides"] = 1
  else:
    d[name]["suicides"] += 1
  return True


def analyzeDeathByMob(l: str, data: dict):
  # "# Server: " .. victim .. " was " .. adv .. adj .. " by " .. an .. " " .. ang .. mname .. "."
  re_ang = "|".join(kill_ang)
  regex = dateRegexNew + serverMsgPrefix + f"(<.*?>|An explorer) was .*? by an? ({re_ang})? ?(.*?)\\.$"
  res = re.search(regex, l)
  if not res:
    return False
  mob = res.groups()[8]
  if not data.get("deathbymob"):
    data["deathbymob"] = {}
  if not data["deathbymob"].get(mob):
    data["deathbymob"][mob] = 1
  else:
    data["deathbymob"][mob] += 1
  return True


def analyzeCleanups(l: str, data: dict):
  # [2025/11/16, 07:00:04 UTC]    # Server: Accounts have been hoovered. 1660 chars kept. Go save a stork.
  regex = dateRegexNew + serverMsgPrefix + r"Accounts have been hoovered. (\d*) chars kept."
  res = re.search(regex, l)
  if not res:
    return False
  if not data.get("cleanups"):
    data["cleanups"] = []
  data["cleanups"].append({
    "timestamp": datetimeFromRegex(res.groups()),
    "n": res.groups()[6]
  })
  return True


def analyzeRenames(l: str, data: dict):
  # [2022/08/29, 14:55:44 UTC]    # Server: Player <DragonsVolcanoDance> is reidentified as <GordanRamsey>!
  # [2019/03/31, 19:58:46 UTC]    # Server: Player <wannabe> renamed to <MustTest>!
  regex = dateRegexNew + serverMsgPrefix + r"Player <([^<>]*)> (renamed to|is reidentified as) <([^<>]*)>"
  res = re.search(regex, l)
  if not res:
    return False
  from_name = res.groups()[6]
  to_name = res.groups()[8]
  #print(f"{from_name} -> {to_name}")

  # End session for old player name.
  timestamp = datetimeFromRegex(res.groups())
  try:
    dt = timestamp - d[name]["start"]
  except KeyError as e:
    #print("Warning: KeyError on {}".format(l))
    #print(e)
    print(f"NEW KeyError: {l.rstrip("\n")}")
    return True
  if d[from_name]["sessions"][-1]["end"] == None:
    d[from_name]["sessions"][-1]["end"] = endDate
  else:
    print(f"Session of {from_name} never started")
  if not d[from_name].get("totalTime"):
    d[from_name]["totalTime"] = datetime.timedelta()
  d[from_name]["totalTime"] += dt

  # Begin session for new player name.
  # TODO d[to_name] = 





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
  print(f"Suicides: {d[name]['suicides']}")
  if "planes" in d[name]:
    realms = ', '.join(d[name]['planes'])
    print(f"Visited {realms}")


def plot_session_probability(player: str, t_step: int):
  T = list(range(0, 24*3600, t_step))
  P = [0]*len(T)
  import math
  for s in data["players"][player]["sessions"]:
    t = s["start"]
    seconds = t.minute*60+t.second
    t -= datetime.timedelta(seconds=seconds)
    t += datetime.timedelta(seconds=t_step*math.ceil(seconds/t_step))
    dt = datetime.timedelta(seconds=t_step)
    if s["end"] == None:
      continue
    while t >= s["start"] and t <= s["end"]:
      seconds = t.hour*3600 + t.minute*60 + t.second
      P[round(seconds/t_step)] += 1
      t += dt
  print(P)
  import matplotlib.pyplot as plt
  fig,ax = plt.subplots()
  T2 = []
  for t in T:
    hour = int(t/3600)
    t -= 3600*hour
    minute = int(t/60)
    t -= 60*minute
    T2.append(datetime.time(hour=hour, minute=minute, second=t))
  ax.set_xlabel("Time (UTC)")
  ax.set_ylabel("Days player was online at that time")
  ax.plot([t/3600 for t in T], P)
  plt.show()




if __name__ == "__main__":
  config = configmanager.readConfig()
  connection = database.connect(config)
  database.setup(connection)

  files = sorted(os.listdir(config["chatlogDir"]))
  files = [config["chatlogDir"] + f for f in files]
  data = {"players": {}, "print": False}

  import time
  start = time.time()

  analyzers = [analyzeChatMessages, analyzeLogins, analyzeMapgen, analyzePlanes, analyzeDeathByMob, analyzeSuicide, analyzeCleanups]
  matches = [0] * len(analyzers)
  for fileName in files:
    with open(fileName) as f:
      for l in f:
        for i,analyzer in enumerate(analyzers):
          res = analyzer(l, data)
          if res:
            matches[i] += 1
            break

  end = time.time()
  print("Dauer: ", end - start)
  #print(matches)
  #print(data["players"]["jeinzi"])

  t_step = 5*60


  cursor = connection.cursor()
  query = "INSERT INTO players VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?);"
  for name in data["players"]:
    try:
        if data["players"][name].get("nLogin"):
          nLogin = data["players"][name]["nLogin"]
        else:
          nLogin = 0

        if data["players"][name].get("firstLogin"):
          firstLogin = data["players"][name]["firstLogin"]
        else:
          firstLogin = None

        if data["players"][name].get("lastSeen"):
          lastSeen = data["players"][name]["lastSeen"]
        else:
          lastSeen = None

        if data["players"][name].get("totalTime"):
          totalTime = data["players"][name]["totalTime"].total_seconds()
        else:
          totalTime = None

        if data["players"][name].get("nMsg"):
          nMsg = data["players"][name]["nMsg"]
        else:
          nMsg = 0

        if data["players"][name].get("chunks"):
          chunks = data["players"][name]["chunks"]
        else:
          chunks = 0

        if data["players"][name].get("suicides"):
          nSuicides = data["players"][name]["suicides"]
        else:
          nSuicides = 0

        cursor.execute(query, (name, firstLogin, lastSeen, totalTime, nLogin, nMsg, nSuicides, chunks))
    except mariadb.IntegrityError as e:
        pass

  query = "INSERT INTO meta VALUES (DEFAULT, UTC_TIME());"
  cursor.execute(query, ())

  query = "INSERT INTO accountCleanups VALUES (DEFAULT, ?, ?);"
  for c in data["cleanups"]:
    cursor.execute(query, (c["timestamp"], c["n"]))

  query = "INSERT INTO mobs VALUES (DEFAULT, ?, ?);"
  for name,count in data["deathbymob"].items():
    cursor.execute(query, (name, count))
  # timestamp DATETIME NOT NULL, accountsKept INT UNSIGNED
  # name, nDeaths

  connection.commit()
