#!/bin/sh

mv /data/mender /opt/influx/

# Locate mmc device with a boot0 partition and extract device path
dev=`ls /dev/mmcblk*boot*`
dev=($dev)
dev=${dev[0]}
devpath=${dev%boot*}

# Extract partition's numbers
PART_NUM_3=$(parted $devpath -ms unit s p | tail -n 2 | head -n 1 | cut -f 1 -d:)
PART_NUM_4=$(parted $devpath -ms unit s p | tail -n 1 | cut -f 1 -d:)

# Extract partition's start/end sectors
PART_START_3=$(parted $devpath -ms unit s p | grep "^${PART_NUM_3}" | cut -f 2 -d:)
PART_END_4=$(parted $devpath -ms unit s p | grep "^${PART_NUM_4}" | cut -f 3 -d:)

# remove last character
PART_START_3=${PART_START_3%?}
PART_END_4=${PART_END_4%?}

echo $PART_NUM_4 $PART_START_3 $PART_END_4

# Run fdisk in scripted mode
fdisk "$devpath" <<EOF
d
$PART_NUM_3
d
$PART_NUM_4
n
p
$PART_NUM_4
$PART_START_3
$PART_END_4
w
EOF

# Reload partition table
partprobe "$devpath" || true

# Remove the service. Should only be run once
systemctl --no-reload disable resizefs.service

mv /opt/influx/mender /data

reboot
