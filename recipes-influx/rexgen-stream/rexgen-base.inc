# Copyright (C) 2025 Influx Technology

DESCRIPTION = "Create RexGen needed folders"

LICENSE = "MIT"
LIC_FILES_CHKSUM="file://LICENSE;md5=b234ee4d69f5fce4486a80fdaf4a4263"

SRC_URI = " \
    file://LICENSE \
"

S = "${WORKDIR}/git"

# these folders will be created
REX_USB_DIR = "/home/root/rexusb/"
INFLUX_DIRS = "${REX_USB_DIR} ${REX_USB_DIR}/config/ ${REX_USB_DIR}/etc/ \
	${REX_USB_DIR}/examples/ ${REX_USB_DIR}/firmware/  ${REX_USB_DIR}/log/ \
	/usr/sbin/ /etc/systemd/network/ /etc/systemd/system/ \
        /usr/lib/systemd/system/ /usr/lib/systemd/system/multi-user.target.wants/ "

do_install:prepend() {
    for d in ${INFLUX_DIRS}; do
	if [ ! -d ${D}${d} ]; then
	    install -m 0755 -d ${D}${d}
	fi
    done
}