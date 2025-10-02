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
REX_USB_DIRS = "${REX_USB_DIR} ${REX_USB_DIR}/config/ ${REX_USB_DIR}/etc \
	${REX_USB_DIR}/examples/ ${REX_USB_DIR}/firmware/"

do_install:prepend() {
    if [ ! -d ${D}/usr/sbin/ ]; then
	mkdir -p ${D}/usr/sbin/
    fi

    for d in ${REX_USB_DIRS}; do
	if [ ! -d ${D}${d} ]; then
	    install -m 0755 -d ${D}${d}
	fi
    done
}