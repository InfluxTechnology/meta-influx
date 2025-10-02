#!/bin/sh

/usr/bin/crontab -u root -l |  /bin/grep -v "* /opt/influx/reboot.sh" |  /usr/bin/crontab -
echo "Rebboting ..."
/sbin/reboot -f
