# Copyright (C) 2025 Influx Technology

DESCRIPTION = "Create RexGen needed folders"

# these folders will be created
REX_USB_DIR = "/home/root/rexusb/"
INFLUX_DIR = "/opt/influx/"
INF_DIRS = " \
    ${INFLUX_DIR} \
    ${REX_USB_DIR}/log/ ${REX_USB_DIR}/var/ ${REX_USB_DIR}/apn/ \
    /etc/chatscripts/ /etc/firmware/ /etc/ppp/peers/ \
    /etc/systemd/network/ /etc/systemd/system/ \
    /usr/sbin/ /usr/lib/systemd/system/multi-user.target.wants/ \
"

INF_INC_DIR = '${@os.path.normpath("${COREBASE}/../meta-influx/conf/include/")}'

do_install:prepend() {
    for d in ${INF_DIRS}; do
    if [ ! -d ${D}${d} ]; then
        install -m 0755 -d ${D}${d}
    fi
    done
}