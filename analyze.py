#!/usr/bin/env python3
import os
import re
import time
import mariadb
import datetime
import database
import configmanager
from helpers import *

from mobmessages import kill_ang

# Date format switch happened on 2017-07-05
dateRegexNew = r"^\[(\d{4})/(\d{2})/(\d{2}), (\d{2}):(\d{2}):(\d{2}) UTC\][ ]*"
serverMsgPrefix = "^# Server: "
regexNameWithMark = (
  "<(!)?(.*?)"         # Then, capture the user name; optional ! in case of shouting: "<!boxface"
  r"( \["              # Open a new group in case the player is marked, with coordinates show in brackets: " ["
  "(.*?: ?)?"          # If this is the case, the realm comes next: "Caverns: "
                       # But realms were missing at the beginning of the servers life, so this is also an optional group!
                       # Also, there are three cases were the space after the colon is missing -_- (as of 2022-11-19)
  r"-?\d*,-?\d*,-?\d*" # The coordinates follow, minus sign is optional: "1059,-5791,-8929"
  r"\])?"              # Close the group for the player marking and make it optional: "]"
  "!?>"                # And the closing chevron with optional shouting finally ending this: "!>")
)



def analyzeMapgen(data: dict, l: str, timestamp: datetime.datetime):
  players = data["players"]
  chunkGenerations = data["chunkGenerations"]
  date = timestamp.date()

  try:
    if l[0] != "#":
      # ToDo: Are there any mapgen messages before the current datetime format was introduced?
      return False
  except IndexError:
      pass

  regexBlame = serverMsgPrefix + r"Mapgen scrambling\. Blame <(.*?)> for lag. Chunks: (\d*)\.$"
  res = re.search(regexBlame, l)
  if res:
    g = res.groups()
    name = g[0]
    chunks = int(g[1])
    ensurePlayer(players, name, timestamp)
    players[name]["nChunks"] += chunks

    updateLastSeen(players[name], timestamp)
    if not chunkGenerations.get(date):
      chunkGenerations[date] = 0
    chunkGenerations[date] += chunks
    return True

  regexAnon = serverMsgPrefix + r"Mapgen working, expect lag\. \(Chunks: (\d*)\.\)$"
  res = re.search(regexAnon, l)
  if res:
    chunks = int(res.groups()[0])
    if not chunkGenerations.get(date):
      chunkGenerations[date] = 0
    chunkGenerations[date] += chunks
    return True

  return False


def analyzeLogins(data: dict, l: str, timestamp: datetime.datetime):
  # Issues
  # - Other logout messages (kicking etc.)
  # - Player has not logged out yet (staying logged in past midnight UTC, especially on first login)
  # - Name changes while logged in

  players = data["players"]

  joinString = r"^\*{3} <(.*?)> joined the game\.$"
  # The quit string regex does not have a $ at the end, because an
  # additional comment in parenthesis may follow.
  quitString = r"^\*{3} <(.*?)> left the game\."

  try:
    if l[0] != "*":
      return False
  except IndexError:
      return False
  res = re.search(joinString, l)
  if res:
    name = res.groups()[0]
    startSession(data, name, timestamp)
    return True

  res = re.search(quitString, l)
  if res:
    name = res.groups()[0]
    endSession(data, name, timestamp)
    return True

  return False


def analyzeChatMessages(data: dict, l: str, timestamp: datetime.datetime):
  # Get all lines that start with a username surrounded by chevrons (< and >),
  # i.e. all user messages in public chat.
  # Example with all optional groups present:
  # <!boxface [Caverns: 1059,-5791,-8929]!> HELP
  # Example without realm:
  # <J2 [-232,-4,1]> hello?
  players = data["players"]

  res = re.search("^" + regexNameWithMark, l)
  if not res:
    return False
  name = res.groups()[1]
  ensurePlayer(players, name, timestamp)
  updateLastSeen(players[name], timestamp)
  players[name]["nMsg"] += 1
  if res.groups()[0] == "!":
    players[name]["nShouts"] += 1
  return True


def analyzePlanes(data: dict, l: str, timestamp: datetime.datetime):
  # Server: <Nakilashiva> has plane shifted to Overworld.
  # Server: <dunks> has plane shifted to Outback. Noob!
  players = data["players"]
  regex = serverMsgPrefix + r"<(.*?)> has plane shifted to (.*?)\.$"

  res = re.search(regex, l)
  if not res:
    return False
  name, plane = res.groups()
  ensurePlayer(players, name, timestamp)
  if not plane in players[name]["planes"]:
    players[name]["planes"].append(plane)
  return True


def analyzeSuicides(data: dict, l: str, timestamp: datetime.datetime):
  players = data["players"]
  regex = serverMsgPrefix + "<(.*?)> ended (her|him)self.$"
  res = re.search(regex, l)
  if not res:
    return False
  name = res.groups()[0]
  ensurePlayer(players, name, timestamp)
  players[name]["nSuicides"] += 1
  return True


re_ang = "|".join(kill_ang)
mobRegex = serverMsgPrefix + f"(<.*?>|An explorer) was .*? by an? ({re_ang})? ?(.*?)\\.$"
def analyzeDeathByMob(data: dict, l: str, timestamp: datetime.datetime):
  # "# Server: " .. victim .. " was " .. adv .. adj .. " by " .. an .. " " .. ang .. mname .. "."
  res = re.search(mobRegex, l)
  if not res:
    return False
  mob = res.groups()[-1]
  if not data["deathbymob"].get(mob):
    data["deathbymob"][mob] = 1
  else:
    data["deathbymob"][mob] += 1
  return True


def analyzeCleanups(data: dict, l: str, timestamp: datetime.datetime):
  # [2025/11/16, 07:00:04 UTC]    # Server: Accounts have been hoovered. 1660 chars kept. Go save a stork.
  regex = serverMsgPrefix + r"Accounts have been hoovered\. (\d*) chars kept\."
  res = re.search(regex, l)
  if not res:
    return False
  data["cleanups"].append({
    "timestamp": timestamp,
    "n": res.groups()[0]
  })
  return True


def analyzeRenames(data: dict, l: str, timestamp: datetime.datetime):
  # [2022/08/29, 14:55:44 UTC]    # Server: Player <DragonsVolcanoDance> is reidentified as <GordanRamsey>!
  # [2019/03/31, 19:58:46 UTC]    # Server: Player <wannabe> renamed to <MustTest>!
  regex = serverMsgPrefix + r"Player <([^<>]*)> (renamed to|is reidentified as) <([^<>]*)>"
  res = re.search(regex, l)
  if not res:
    return False
  from_name = res.groups()[0]
  to_name = res.groups()[2]

  endSession(data, from_name, timestamp)
  startSession(data, to_name, timestamp)
  return True


def analyzeKicks(data: dict, l: str, timestamp: datetime.datetime):
  # [2023/03/17, 00:39:01 UTC]    # Server: <Cucina> was kicked for being AFK too long.
  # [2023/03/17, 00:49:42 UTC]    # Server: <Jr> was kicked off the server.
  regex = serverMsgPrefix + r"<(.*?)> was kicked"
  if not (res := re.search(regex, l)):
    return False
  name = res.groups()[0]
  if not data["players"].get(name):
    print(f"WEIRD: {name} was kicked without ever logging in")
    return True
  data["players"][name]["nKicks"] += 1
  return True


def analyzeDuctTapes(data: dict, l: str, timestamp: datetime.datetime):
  # [2025/11/22, 18:11:31 UTC]    # Server: Player <Q>'s chat has been duct-taped!
  regex = serverMsgPrefix + r"Player <(.*?)>'s chat has been duct-taped"
  if not (res := re.search(regex, l)):
    return False
  name = res.groups()[0]
  data["players"][name]["nDuctTapes"] += 1
  return True


def analyzeMes(data: dict, l: str, timestamp: datetime.datetime):
  # * <DragonsVolcanoDance> gives hamburger
  # * <Alex [-386,-6,412]> coughs
  regex = r"^\* " + regexNameWithMark
  if not (res := re.search(regex, l)):
    return False
  name = res.groups()[1]
  ensurePlayer(data["players"], name, timestamp)
  data["players"][name]["nMes"] += 1
  data["players"][name]["nMsg"] += 1
  return True


def analyzeMarks(data: dict, l: str, timestamp: datetime.datetime):
  # Server: Player <linux> has been marked!
  regex = serverMsgPrefix + r"Player <(.*?)> has been marked!"
  if not (res := re.search(regex, l)):
    return False
  name = res.groups()[0]
  data["players"][name]["nMarks"] += 1
  return True


def parseShutdowns(data: dict, l: str, timestamp: datetime.datetime):
  # Server: Startup complete.
  # Server: Exited without signal. If this is a normal failure the server will restart in a few seconds.
  regex_shutdown = serverMsgPrefix + "(Startup complete|Normal shutdown|Exited without signal)"

  if not (res := re.search(regex_shutdown, l)):
    return False

  # Terminate all player sessions.
  for name in data["activeSessions"]:
    p = data["players"][name]
    if p["sessions"][-1]["end"] != None:
      continue
    p["sessions"][-1]["end"] = timestamp
  data["activeSessions"] = []
  return True


def printLine(data: dict, l: str, timestamp: datetime.datetime):
  print(l.rstrip("\n"))
  return False


def sumTotalTime(players: dict):
  for name,p in players.items():
    totalTime = datetime.timedelta()
    for s in p["sessions"]:
      if s["start"] == None or s["end"] == None:
        continue
      p["totalTime"] += s["end"] - s["start"]


def checkSessions(players: dict):
  n_issues = 0
  for name,p in players.items():
    for i,s in enumerate(p["sessions"]):
      valid = True
      if s["start"] == None:
        #print(f"Session {i} of player '{name}' does not have a start.")
        n_issues += 1
        valid = False
      if s["end"] == None:
        #print(f"Session {i} of player '{name}' does not have an end.")
        n_issues += 1
        valid = False
      if s["start"] == None and s["end"] == None:
        print("---------------- BOTH START AND END EMPTY ----------------")
      if not valid:
        continue
      dt = s["end"] - s["start"]
      if dt.total_seconds() > 3600*24:
        print(f"Session {i} of player '{name}' is longer than one day. ({dt})")
        n_issues += 1
  print(f"{n_issues=}")

def printPlayer(d, name):
  players = d["players"]
  if not name in players:
    print(f"User <{name}> is not known.")
    return

  print(f"User: {name}")
  print(f"Last seen: {players[name]['lastSeen']}")
  print(f"First seen: {players[name]['firstSeen']}")
  print(f"Time played: {players[name]['totalTime']}")
  print(f"Chunks generated: {players[name]['chunks']}")
  print(f"Chat messages sent: {players[name]['messages']}")
  print(f"Suicides: {players[name]['suicides']}")
  if "planes" in players[name]:
    realms = ', '.join(players[name]['planes'])
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
  data = {
    "players": {},
    "deathbymob": {},
    "cleanups": [],
    "chunkGenerations": {},
    "print": False,
    "activeSessions": [],
  }

  import time
  start = time.time()

  # For every line in the chatlog, the analyzers are called one after
  # another until one returns True, signaling that its regex matched
  # and no further parsing is necessary. The most frequent matches
  # should therefore be at the beginning of the list. (-> performance)
  analyzers = [analyzeChatMessages, analyzeLogins, analyzeMapgen, analyzePlanes, analyzeDeathByMob, analyzeKicks, analyzeMes, analyzeDuctTapes, analyzeMarks, analyzeRenames, analyzeSuicides, analyzeCleanups, parseShutdowns]
  matches = [0] * len(analyzers)
  for fileName in files:
    with open(fileName) as f:
      for l in f:
        if not (res := re.search(dateRegexNew, l)):
          continue
        timestamp = datetimeFromRegex(res.groups())
        l = l[30:] # This fails at [2017/07/05, 22:17:40 UTC]
        for i,analyzer in enumerate(analyzers):
          if analyzer(data, l, timestamp):
            matches[i] += 1
            break

  sumTotalTime(data["players"])
  end = time.time()
  print("Dauer: ", end - start)
  print(matches)

  checkSessions(data["players"])

  cursor = connection.cursor()
  query = "INSERT INTO players VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);"
  for name,player in data["players"].items():
    try:
        cursor.execute(query, (
          name,
          player["firstSeen"],
          player["lastSeen"],
          player["totalTime"].total_seconds(),
          player["nLogins"],
          player["nMsg"],
          player["nSuicides"],
          player["nChunks"],
          player["nDuctTapes"],
          player["nKicks"],
          player["nMarks"],
          player["nShouts"],
          player["nMes"],
          ", ".join(player["planes"])
        ))
    except mariadb.IntegrityError as e:
        pass

  query = "INSERT INTO meta VALUES (DEFAULT, UTC_TIME());"
  cursor.execute(query, ())

  query = "INSERT INTO accountCleanups VALUES (DEFAULT, ?, ?);"
  for c in data["cleanups"]:
    cursor.execute(query, (c["timestamp"], c["n"]))

  query = "INSERT INTO chunkGenerations VALUES (DEFAULT, ?, ?);"
  for timestamp,count in data["chunkGenerations"].items():
    cursor.execute(query, (timestamp, count))

  query = "INSERT INTO mobs VALUES (DEFAULT, ?, ?);"
  for name,count in data["deathbymob"].items():
    cursor.execute(query, (name, count))

  connection.commit()
