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
    firstLogin DATETIME,
    lastSeen DATETIME,
    totalTime BIGINT UNSIGNED,
    nLogins INT UNSIGNED,
    nMessages INT UNSIGNED,
    nSuicides INT UNSIGNED,
    chunks INT UNSIGNED
  );"""

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


  cursor.execute(playersTableCreation)
  cursor.execute(metaTableCreation)
  cursor.execute(mobsTableCreation)
  cursor.execute(accountCleanupTableCreation)
  setupOutback(connection)



def setupOutback(connection):
  outbackTableCreation = """CREATE OR REPLACE TABLE outback (
    id INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    name TINYTEXT NOT NULL UNIQUE,
    count INT UNSIGNED
  );"""
  cursor = connection.cursor()
  cursor.execute(outbackTableCreation)
  connection.commit()
