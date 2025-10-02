#!/bin/sh

export EDITOR=/usr/bin/nano	# crontab uses this editor
# execute at first time
/etc/profile.d/enable_services.sh

# Mender image update need this 
# remove/add this crontab jobs
/usr/bin/crontab -u root -l |  grep -v "* /opt/influx/release_check.sh" |  /usr/bin/crontab -
#
# extract preserved files
if test -f /data/mender/preserved-files.tgz; then
    tar -xzf /data/mender/preserved-files.tgz -C /
    mv /data/mender/preserved-files.tgz /data/mender/preserved-files_old.tgz 
fi

# Power up the Quectel chip
/opt/influx/cellular_module_start.sh

# start LTE connection by wvdial
#/opt/influx/lte_start_wvdial.sh
#/opt/influx/start_ppp0.sh

echo 0 > /sys/block/mmcblk2boot0/force_ro
