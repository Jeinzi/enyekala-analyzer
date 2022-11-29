#!/usr/bin/env python3
import os
import re
import math
import configmanager



def calcDistance(p0, p1):
  d = (p0[0]-p1[0], p0[1]-p1[1], p0[2]-p1[2])
  return math.sqrt(d[0]**2 + d[1]**2 + d[2]**2)



if __name__ == "__main__":
  # Search for unclaimed boneboxes within a sphere.
  chatlogDir = configmanager.readConfig()["chatlogDir"]
  center = (896, 4 , 7455)
  radius = 500

  for fileName in os.listdir(chatlogDir):
    try:
      with open(chatlogDir + fileName) as f:
        for l in f:
          ll = l.lower()
          if        not "blackbox" in ll \
                and not "bonebox" in ll \
                and not "ritual box detected" in ll \
                and not "death beacon" in ll:
            continue
          if "outback" in ll:
            continue
          if "id and location unknown" in ll:
            continue
          if not re.search("^\[\d{4}/\d{2}/\d{2}, \d{2}:\d{2}:\d{2} UTC\][ ]*# Server:", l):
            continue

          res = re.search("\(.*?: (-?\d*?),(-?\d*?),(-?\d*?)\)", l)
          if not res:
            continue
          pos = tuple(int(x) for x in res.groups())

          distance = calcDistance(pos, center)
          if distance > radius:
            continue


          claimed = False
          for fileName2 in os.listdir(chatlogDir):
            break
            try:
              with open(chatlogDir + fileName2) as f2:
                for l2 in f2:
                  if "claimed" not in l2:
                    continue
                  if f"{pos[0]},{pos[1]},{pos[2]}" not in l2:
                    continue
                  claimed = True
            except Exception as e:
              raise e
          if claimed:
            continue

          print(f"{distance}: {l}", end="")
    except Exception as e:
      raise e
