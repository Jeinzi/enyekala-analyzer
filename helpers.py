import copy
import datetime


def updateLastSeen(p: dict, time: datetime.datetime):
  try:
    if p["lastSeen"] < time:
      p["lastSeen"] = time
  except KeyError:
    p["lastSeen"] = time
  except TypeError:
    p["lastSeen"] = time


def datetimeFromRegex(groups: list):
  r = [int(i) for i in groups[:6]]
  return datetime.datetime(*r)


def dateFromRegex(groups: list):
  r = [int(i) for i in groups[:3]]
  return datetime.date(*r)


def startSession(data: dict, name: str, timestamp: datetime.datetime):
  ensurePlayer(data["players"], name, timestamp)
  data["players"][name]["sessions"].append({"start": timestamp, "end": None})
  data["players"][name]["nLogins"] += 1
  updateLastSeen(data["players"][name], timestamp)
  data["activeSessions"].append(name)


def endSession(data: dict, name: str, timestamp: datetime.datetime):
  # ToDo?
  if not data["players"].get(name):
    return
  if len(data["players"][name]["sessions"]) == 0:
    return
  if data["players"][name]["sessions"][-1]["end"] != None:
    #print(f"Session of {name} on {endDate} never started")
    return

  data["players"][name]["sessions"][-1]["end"] = timestamp
  updateLastSeen(data["players"][name], timestamp)
  data["activeSessions"].remove(name)


userTemplate = {
  "nChunks": 0,
  "firstSeen": None,
  "nLogins": 0,
  "nSuicides": 0,
  "sessions": [],
  "nMsg": 0,
  "totalTime": datetime.timedelta(),
  "planes": [],
  "lastSeen": None,
  "nDuctTapes": 0,
  "nKicks": 0,
  "nMarks": 0,
  "nMes": 0,
  "nShouts": 0,

  #"deaths": 0,
  #"portalSickness": 0,
  #"voids": 0,
  #"swearing": 0,
  #"deathsByMob": {},
}


def ensurePlayer(players: dict, name: str, timestamp: datetime.datetime):
  if not players.get(name):
    players[name] = copy.deepcopy(userTemplate)
    players[name]["firstSeen"] = timestamp
    return True
  return False
