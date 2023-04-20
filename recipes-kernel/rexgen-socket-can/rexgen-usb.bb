SUMMARY = "Influx Technology LTD - ReXgen SocketCAN Driver for linux"
DESCRIPTION = "The SocketCAN driver allows you to use ReXgen device as CAN interfaces within your own socketCAN based applications."

LICENSE = "MIT"
LIC_FILES_CHKSUM="file://LICENSE;md5=b234ee4d69f5fce4486a80fdaf4a4263"

SRC_URI = "git://github.com/InfluxTechnology/rexgen-socketcan.git;protocol=https;branch=main \
	file://LICENSE \
	file://Makefile.patch \
"
SRCREV = "80127e0976539b9d7a0a4a82855eb534b01db3e7"

S = "${WORKDIR}/git"

inherit module

RPROVIDES:${PN} += "kernel-module-rexgen_usb"

