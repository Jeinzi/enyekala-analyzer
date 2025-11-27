import mariadb


def connect(config):
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


def setup(connection):
  cursor = connection.cursor()

  # Will create table. If it exists, drop it first.
  playersTableCreation = """CREATE OR REPLACE TABLE players (
    id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    name TINYTEXT NOT NULL UNIQUE,
    firstSeen DATETIME,
    lastSeen DATETIME,
    totalTime BIGINT UNSIGNED,
    nLogins INT UNSIGNED,
    nMessages INT UNSIGNED,
    nSuicides INT UNSIGNED,
    chunks INT UNSIGNED,
    nDuctTapes INT UNSIGNED,
    nKicks INT UNSIGNED,
    nMarks INT UNSIGNED,
    nShouts INT UNSIGNED,
    nMes INT UNSIGNED,
    planes MEDIUMTEXT
  )
  CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_de_pb_0900_as_cs';"""

  mobsTableCreation = """CREATE OR REPLACE TABLE mobs (
    id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    name TINYTEXT NOT NULL UNIQUE,
    nDeaths INT UNSIGNED
  );"""

  accountCleanupTableCreation = """CREATE OR REPLACE TABLE accountCleanups (
    id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    timestamp DATETIME NOT NULL,
    accountsKept INT UNSIGNED
  );"""

  metaTableCreation = """CREATE OR REPLACE TABLE meta (
    id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    analyzeDate DATETIME
  );"""

  chunkTableCreation = """CREATE OR REPLACE TABLE chunkGenerations (
    id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    timestamp DATE NOT NULL,
    count INT UNSIGNED
  );"""


  cursor.execute(playersTableCreation)
  cursor.execute(metaTableCreation)
  cursor.execute(mobsTableCreation)
  cursor.execute(chunkTableCreation)
  cursor.execute(accountCleanupTableCreation)



def setupOutback(connection):
  outbackTableCreation = """CREATE OR REPLACE TABLE outback (
    id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    name TINYTEXT NOT NULL UNIQUE,
    count INT UNSIGNED
  );"""
  cursor = connection.cursor()
  cursor.execute(outbackTableCreation)
  connection.commit()
