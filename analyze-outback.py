#!/usr/bin/env python3
import math
from mtschem import mtschem
import database
import configmanager

def count_blocks(schematic):
  occurances = [0 for name in schematic.nodes]

  for x, xd in enumerate(schematic.data["node"]):
    for y, yd in enumerate(xd):
      for z, zd in enumerate(yd):
        occurances[zd] += 1
  stats = {name: n for name,n in zip(schematic.nodes, occurances)}
  return stats


def get_positions(schematic, ids: list):
  positions = {schematic.nodes[id]: [] for id in ids}
  for x, xd in enumerate(schematic.data["node"]):
    for y, yd in enumerate(xd):
      for z, zd in enumerate(yd):
        if zd in ids:
          name = schematic.nodes[zd]
          positions[name].append((x, y, z))
  return positions


def game_to_mts(x, y, z):
  return (x+100, y+100, z+100)

def mts_to_game(x, y, z):
  return (x-100, y-100, z-100)

def get_block_positions(schematic, name):
  positions = get_positions(schematic, [schematic.nodes.index(name)])[name]
  return [mts_to_game(*pos) for pos in positions]


def dist(p0, p1):
  dx = p0[0] - p1[0]
  dy = p0[1] - p1[1]
  dz = p0[2] - p1[2]
  return math.sqrt(dx**2+dy**2+dz**2)

def find(pos, radius):
  print("Gold: ")
  for block_pos in gold_positions:
    if dist(pos, block_pos) < radius:
      print(block_pos)
  print("\nDiamond: ")
  for block_pos in dia_positions:
    if dist(pos, block_pos) < radius:
      print(block_pos)
  print("\nMese: ")
  for block_pos in mese_positions:
    if dist(pos, block_pos) < radius:
      print(block_pos)


def score(pos):
  #positions = {
  #  gold_positions: 1,
  #  dia_positions: 0,
  #  mese_positions: 0
  #}
  score = 0
  #for collection,weight in positions.items():
  for block_pos in dirt_positions:
    if block_pos[0] == pos[0] and block_pos[1] == pos[1] and block_pos[2] == pos[2]:
      continue
    if dist(block_pos, pos) < 5:
      score += 1
  return score



if __name__ == "__main__":
  config = configmanager.readConfig()
  connection = database.connect(config)
  database.setupOutback(connection)

  schematic = mtschem.Schem("musttest_game/mods/rc/outback_map.mts")
  stats = count_blocks(schematic)
  query = "INSERT INTO outback VALUES (DEFAULT, ?, ?);"
  cursor = connection.cursor()
  for name,count in stats.items():
    cursor.execute(query, (name, count));
  connection.commit()

  #rare_blocks = [schematic.nodes.index(name) for name,amount in stats.items() if amount <= 2]
  #positions = get_positions(schematic, rare_blocks)
  #gold_positions = get_block_positions(schematic, "rackstone:rackstone_with_gold")
  #dia_positions = get_block_positions(schematic, "rackstone:rackstone_with_diamond")
  #mese_positions = get_block_positions(schematic, "rackstone:rackstone_with_mese")
  #iron_positions = get_block_positions(schematic, "rackstone:rackstone_with_iron")
  #dirt_positions = get_block_positions(schematic, "default:dirt")
  #print(gold_positions)
  scores = {}
  # for pos in dirt_positions:
  #   scores[pos] = score(pos)
  # i = 0
  # for s in sorted(scores, key=scores.get, reverse=True):
  #   if dist((-66, 48, -82), s) < 10:
  #     continue
  #   if abs(s[1] < 10):
  #     continue
  #   print(s, scores[s])
  #   i += 1
  #   if i >= 100:
  #     break
