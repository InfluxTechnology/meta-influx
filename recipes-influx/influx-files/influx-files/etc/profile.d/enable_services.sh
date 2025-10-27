#!/bin/sh

# create link to rexgen tool
if [ ! -f /usr/sbin/rexgen ]; then
    ln -s /home/root/rexusb/rexgen /usr/sbin/rexgen
fi

# create link to aws tool
#if test -f /opt/influx/socket/aws; then
#    mv /opt/influx/socket/aws /home/root/rexusb/
#fi
if [ ! -f /usr/sbin/aws ]; then
    ln -s /home/root/rexusb/aws /usr/sbin/aws
fi

# rc.local 
if test -f /opt/influx/rc.local; then
    chmod +x /opt/influx/rc.local
    mv /opt/influx/rc.local /etc/
fi

# Google cloud support
#if test -f /opt/influx/socket/gcs*; then
#    mv /opt/influx/socket/gcs* /home/root/rexusb/
#fi

# enable autostart service
as_enabled=$(systemctl is-enabled autostart.service)
if [ "$as_enabled" != "enabled" ];
then
   systemctl enable autostart.service
   systemctl start autostart.service
   /bin/sed -i "s/####//" /opt/influx/autostart.sh
fi

