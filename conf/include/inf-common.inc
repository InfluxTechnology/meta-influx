# Copyright (C) 2025 Influx Technology

DESCRIPTION = "Create RexGen needed folders"

# these folders will be created
REX_USB_DIR = "/home/root/rexusb/"
INFLUX_DIR = "/opt/influx/"
NET_SERV_VER = "netservices-lite"
INF_DIRS = " \
    ${REX_USB_DIR} \
    ${REX_USB_DIR}/log/ ${REX_USB_DIR}/var/ ${REX_USB_DIR}/apn/ \
    ${INFLUX_DIR} \
    ${INFLUX_DIR}${NET_SERV_VER}/ \
    ${INFLUX_DIR}${NET_SERV_VER}/bin/ \
    ${INFLUX_DIR}${NET_SERV_VER}/lib/ \
    ${INFLUX_DIR}${NET_SERV_VER}/lib/dashboard/ \
    ${INFLUX_DIR}${NET_SERV_VER}/lib/services/ \
    ${INFLUX_DIR}${NET_SERV_VER}/licensing/ \
    ${INFLUX_DIR}${NET_SERV_VER}/licensing/closed-source/ \
    ${INFLUX_DIR}${NET_SERV_VER}/licensing/open-source/ \
    ${INFLUX_DIR}${NET_SERV_VER}/scripts/ \
    ${INFLUX_DIR}${NET_SERV_VER}/services/ \
    ${INFLUX_DIR}${NET_SERV_VER}/systemd \
    /etc/chatscripts/ /etc/firmware/ /etc/ppp/ /etc/ppp/peers/ \
    /etc/systemd/network/ /etc/systemd/system/ \
    /usr/sbin/ /usr/lib/systemd/system/ /usr/lib/systemd/system/multi-user.target.wants/ \
"
INF_INC_DIR = '${@os.path.normpath("${COREBASE}/../meta-influx/conf/include/")}'

do_install:prepend() {
    for d in ${INF_DIRS}; do
    if [ ! -d ${D}${d} ]; then
        install -m 0755 -d ${D}${d}
    fi
    done
}