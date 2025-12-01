#!/usr/bin/env python3
import os
import datetime
from lxml import etree
import urllib.parse
import urllib.request
import urllib.error
import configmanager



def saveChatlog(date, saveDir):
  postDict = {
    "date": date.isoformat(),
    "submit": "Show Log From Date"
  }
  data = urllib.parse.urlencode(postDict).encode()
  req =  urllib.request.Request("https://arklegacy-server.net/chat.html", data=data)
  with urllib.request.urlopen(req) as resp:
    tree = etree.parse(resp, etree.HTMLParser())
    chatlog = tree.xpath("/html/body/main/section[1]/form/pre")[0]
    saveFilePath = saveDir + date.isoformat()
    with open(saveFilePath, "w") as f:
      f.write(chatlog.text)
      print(f"Downloading {date}")



if __name__ == "__main__":
  # Create save directory.
  saveDir = configmanager.readConfig()["chatlogDir"]
  if not os.path.exists(saveDir):
    os.mkdir(saveDir)

  if not os.path.isdir(saveDir):
    print("Save directory can't be created because a file named identically already exists!")
    exit()

  # Iterate through dates, starting with the first day of the chat archive.
  date = datetime.date.fromisoformat("2017-07-03")
  error_counter = 0
  while date != datetime.date.today():
    fileName = saveDir + date.isoformat()
    if os.path.exists(saveDir + date.isoformat()):
      date += datetime.timedelta(days=1)
      continue

    try:
      saveChatlog(date, saveDir)
    except:
      error_counter += 1
      if error_counter >= 3:
        print("More than 3 errors, aborting.")
        exit()
      else:
        print(f"Error on {date}, retrying...")
    else:
      date += datetime.timedelta(days=1)
      error_counter = 0
