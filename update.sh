#!/bin/bash
cd /root/enyekala-analyzer

# Redirect stdout and stderr to file.
exec 2>&1 >> log

date
source env/bin/activate
./download.py && ./analyze.py && mariadb-dump enyekala > /srv/enyekala/download/enyekala.db-dump
echo "---"
