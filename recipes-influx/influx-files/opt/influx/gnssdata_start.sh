#!/bin/sh

/usr/bin/crontab -u root -l |  /bin/grep -v "* /opt/influx/gnssdata_start.sh" |  /usr/bin/crontab -
/opt/influx/gnssinit.py

