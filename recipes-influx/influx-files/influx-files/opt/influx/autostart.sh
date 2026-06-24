#!/bin/sh

# Mender image update need this
# remove/add this crontab jobs
/usr/bin/crontab -u root -l |  grep -v "* /opt/influx/release_check.sh" |  /usr/bin/crontab -
#
# extract preserved files
if test -f /data/mender/preserved-files.tgz; then
    tar -xzf /data/mender/preserved-files.tgz -C /
    mv /data/mender/preserved-files.tgz /data/mender/preserved-files_old.tgz
fi
#
# Avoiding the sleep during OTA update
INF_UPG=$(/usr/bin/fw_printenv influx_upgrade | cut -d = -f 2)
if [ "$INF_UPG" == "1" ]; then
        /opt/influx/mender_update_finish.sh
fi

# Power up the Quectel chip
/opt/influx/cellular_module_start.sh

# start LTE connection by wvdial
#/opt/influx/lte_start_wvdial.sh
#/opt/influx/start_ppp0.sh

systemctl stop serial-getty@ttymxc1.service
systemctl disable serial-getty@ttymxc1.service

/opt/influx/local_settings.sh
