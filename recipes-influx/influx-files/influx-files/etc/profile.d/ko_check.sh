#!/bin/sh

# patch to check for kernel objects
if ls /opt/influx/ko/* 1> /dev/null 2>&1; then
    if [ ! -d /lib/modules/$(uname -r)/extra ]; then 
        mkdir /lib/modules/$(uname -r)/extra/
    fi
#    for i in  /opt/influx/ko/*; do mv -- "$i" "${i%}.ko"; done
#    mv /opt/influx/ko/*.ko /lib/modules/$(uname -r)/extra/
#    depmod -a
fi
