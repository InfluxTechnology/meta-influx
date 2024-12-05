#!/bin/sh

# create link to rexgen tool
if [ ! -f /usr/sbin/rexgen ]; then
    ln -s /home/root/rexusb/rexgen /usr/sbin/rexgen
fi

# create link to aws tool
if [ ! -f /usr/sbin/aws ]; then
    ln -s /home/root/rexusb/aws /usr/sbin/aws
fi

# enable autostart service
as_enabled=$(systemctl is-enabled autostart.service)
if [ "$as_enabled" != "enabled" ];
then
   systemctl enable autostart.service
   systemctl start autostart.service
   /bin/sed -i "s/####//" /opt/influx/autostart.sh
fi

