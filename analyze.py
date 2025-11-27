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
serverMsgPrefix = "# Server: "
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



def analyzeMapgen(l: str, data: dict):
  players = data["players"]
  chunkGenerations = data["chunkGenerations"]

  try:
    if l[30] != "#":
      # ToDo: Are there any mapgen messages before the current datetime format was introduced?
      return False
  except IndexError:
      pass

  regexBlame = dateRegexNew + r"# Server: Mapgen scrambling\. Blame <(.*?)> for lag. Chunks: (\d*)\.$"
  res = re.search(regexBlame, l)
  if res:
    g = res.groups()
    timestamp = datetimeFromRegex(g)
    name = g[6]
    chunks = int(g[7])
    ensurePlayer(players, name, timestamp)
    players[name]["nChunks"] += chunks

    date = timestamp.date()
    updateLastSeen(players[name], timestamp)
    if not chunkGenerations.get(date):
      # This is needed for the chatlog of 2024-07-18, because at there is a chunk generation of
      # 2024-07-19 at the end.
      chunkGenerations[date] = 0
    chunkGenerations[date] += chunks
    return True

  regexAnon = dateRegexNew + r"# Server: Mapgen working, expect lag\. \(Chunks: (\d*)\.\)$"
  res = re.search(regexAnon, l)
  if res:
    chunks = int(res.groups()[6])
    date = dateFromRegex(res.groups())
    if not chunkGenerations.get(date):
      chunkGenerations[date] = 0
    chunkGenerations[date] += chunks
    return True

  return False


def analyzeLogins(l: str, data: dict):
  # Issues
  # - Other logout messages (kicking etc.)
  # - Player has not logged out yet (staying logged in past midnight UTC, especially on first login)
  # - Name changes while logged in

  players = data["players"]

  joinString = dateRegexNew + r"\*{3} <(.*?)> joined the game.$"
  # The quit string regex does not have a $ at the end, because an
  # additional comment in parenthesis may follow.
  quitString = dateRegexNew + r"\*{3} <(.*?)> left the game."

  try:
    if l[30] != "*":
      return False
  except IndexError:
      return False
  res = re.search(joinString, l)
  if res:
    dateGroups = res.groups()[:-1]
    name = res.groups()[-1]
    startDate = datetimeFromRegex(res.groups())
    ensurePlayer(players, name, startDate)
    players[name]["start"] = startDate
    players[name]["sessions"].append({"start": startDate, "end": None})
    players[name]["nLogins"] += 1
    updateLastSeen(players[name], startDate)
    return True

  res = re.search(quitString, l)
  if res:
    dateGroups = res.groups()[:-1]
    name = res.groups()[-1]
    endDate = datetimeFromRegex(res.groups())
    if not players.get(name) or len(players[name]["sessions"]) == 0:
      # ToDo
      return True
    if players[name]["sessions"][-1]["end"] == None:
      players[name]["sessions"][-1]["end"] = endDate
    else:
      print(f"Session of {name} on {endDate} never started")
    updateLastSeen(players[name], endDate)
    return True

  return False


def analyzeChatMessages(l: str, data: dict):
  # Get all lines that start with a username surrounded by chevrons (< and >),
  # i.e. all user messages in public chat.
  # Example with all optional groups present:
  # <!boxface [Caverns: 1059,-5791,-8929]!> HELP
  # Example without realm:
  # <J2 [-232,-4,1]> hello?
  regex = dateRegexNew + regexNameWithMark
  players = data["players"]

  res = re.search(regex, l)
  if not res:
    return False
  name = res.groups()[7]
  timestamp = datetimeFromRegex(res.groups())
  ensurePlayer(players, name, timestamp)
  updateLastSeen(players[name], timestamp)
  players[name]["nMsg"] += 1
  if res.groups()[6] == "!":
    players[name]["nShouts"] += 1
  return True


def analyzePlanes(l: str, data: dict):
  # Server: <Nakilashiva> has plane shifted to Overworld.
  # Server: <dunks> has plane shifted to Outback. Noob!
  players = data["players"]
  regex = dateRegexNew + serverMsgPrefix + r"<(.*?)> has plane shifted to (.*?)\.$"

  res = re.search(regex, l)
  if not res:
    return False
  timestamp = datetimeFromRegex(res.groups())
  name = res.groups()[6]
  plane = res.groups()[7]
  ensurePlayer(players, name, timestamp)
  if not plane in players[name]["planes"]:
    players[name]["planes"].append(plane)
  return True


def analyzeSuicides(l: str, data: dict):
  players = data["players"]
  regex = dateRegexNew + serverMsgPrefix + "<(.*?)> ended (her|him)self.$"
  res = re.search(regex, l)
  if not res:
    return False
  timestamp = datetimeFromRegex(res.groups())
  name = res.groups()[6]
  ensurePlayer(players, name, timestamp)
  players[name]["nSuicides"] += 1
  return True


def analyzeDeathByMob(l: str, data: dict):
  # "# Server: " .. victim .. " was " .. adv .. adj .. " by " .. an .. " " .. ang .. mname .. "."
  re_ang = "|".join(kill_ang)
  regex = dateRegexNew + serverMsgPrefix + f"(<.*?>|An explorer) was .*? by an? ({re_ang})? ?(.*?)\\.$"
  res = re.search(regex, l)
  if not res:
    return False
  mob = res.groups()[8]
  if not data["deathbymob"].get(mob):
    data["deathbymob"][mob] = 1
  else:
    data["deathbymob"][mob] += 1
  return True


def analyzeCleanups(l: str, data: dict):
  # [2025/11/16, 07:00:04 UTC]    # Server: Accounts have been hoovered. 1660 chars kept. Go save a stork.
  regex = dateRegexNew + serverMsgPrefix + r"Accounts have been hoovered\. (\d*) chars kept\."
  res = re.search(regex, l)
  if not res:
    return False
  data["cleanups"].append({
    "timestamp": datetimeFromRegex(res.groups()),
    "n": res.groups()[6]
  })
  return True


def analyzeRenames(l: str, data: dict):
  # [2022/08/29, 14:55:44 UTC]    # Server: Player <DragonsVolcanoDance> is reidentified as <GordanRamsey>!
  # [2019/03/31, 19:58:46 UTC]    # Server: Player <wannabe> renamed to <MustTest>!
  players = data["players"]
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
  if players[from_name]["sessions"][-1]["end"] == None:
    players[from_name]["sessions"][-1]["end"] = endDate
  else:
    print(f"Session of {from_name} never started")
  if not players[from_name].get("totalTime"):
    players[from_name]["totalTime"] = datetime.timedelta()
  players[from_name]["totalTime"] += dt

  # Begin session for new player name.
  ensurePlayer(players, to_name, timestamp)
  players[name]["start"] = startDate
  players[name]["sessions"].append({"start": startDate, "end": None})
  players[name]["nLogins"] += 1
  updateLastSeen(players[name], startDate)


def analyzeKicks(l: str, data: dict):
  # [2023/03/17, 00:39:01 UTC]    # Server: <Cucina> was kicked for being AFK too long.
  # [2023/03/17, 00:49:42 UTC]    # Server: <Jr> was kicked off the server.
  regex = dateRegexNew + serverMsgPrefix + r"<(.*?)> was kicked"
  if not (res := re.search(regex, l)):
    return False
  name = res.groups()[6]
  if not data["players"].get(name):
    print(f"WEIRD: {name} was kicked without ever logging in")
    return True
  data["players"][name]["nKicks"] += 1
  return True


def analyzeDuctTapes(l: str, data: dict):
  # [2025/11/22, 18:11:31 UTC]    # Server: Player <Q>'s chat has been duct-taped!
  regex = dateRegexNew + serverMsgPrefix + r"Player <(.*?)>'s chat has been duct-taped"
  if not (res := re.search(regex, l)):
    return False
  name = res.groups()[6]
  data["players"][name]["nDuctTapes"] += 1
  return True


def analyzeMes(l: str, data: dict):
  # * <DragonsVolcanoDance> gives hamburger
  # * <Alex [-386,-6,412]> coughs
  regex = dateRegexNew + r"\* " + regexNameWithMark
  if not (res := re.search(regex, l)):
    return False
  name = res.groups()[7]
  timestamp = datetimeFromRegex(res.groups())
  ensurePlayer(data["players"], name, timestamp)
  data["players"][name]["nMes"] += 1
  data["players"][name]["nMsg"] += 1
  return True


def analyzeMarks(l: str, data: dict):
  # Server: Player <linux> has been marked!
  regex = dateRegexNew + serverMsgPrefix + r"Player <(.*?)> has been marked!"
  if not (res := re.search(regex, l)):
    return False
  name = res.groups()[6]
  data["players"][name]["nMarks"] += 1
  return True


def parseShutdowns(l: str, data: dict):
  # Server: Normal shutdown. Everybody off!
  # TODO: Terminate all player sessions.
  return False


def printLine(l: str, data: dict):
  print(l.rstrip("\n"))
  return False


def sumTotalTime(player: dict):
  pass
  #try:
  #    dt = endDate - players[name]["start"]
  #except KeyError as e:
  #  #print("Warning: KeyError on {}".format(l))
  #  #print(e)
  #  print(f"KeyError: {l.rstrip("\n")}")
  #  return True
  #players[name]["totalTime"] += dt
  #if dt > datetime.timedelta(days=1):
  #  print(f"Session of {name} longer than one day ({dt})")



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
  }

  import time
  start = time.time()

  # For every line in the chatlog, the analyzers are called one after
  # another until one returns True, signaling that its regex matched
  # and no further parsing is necessary. The most frequent matches
  # should therefore be at the beginning of the list. (-> performance)
  analyzers = [analyzeChatMessages, analyzeLogins, analyzeMapgen, analyzePlanes, analyzeDeathByMob, analyzeKicks, analyzeMes, analyzeDuctTapes, analyzeMarks, analyzeSuicides, analyzeCleanups, parseShutdowns]
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
  print(matches)

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
