SUMMARY = "Influx Technology LTD - ReXgen SocketCAN Driver for linux"
DESCRIPTION = "The SocketCAN driver allows you to use ReXgen device as CAN interfaces within your own socketCAN based applications."

LICENSE = "MIT"
LIC_FILES_CHKSUM="file://LICENSE;md5=b234ee4d69f5fce4486a80fdaf4a4263"

SRC_URI = "git://github.com/InfluxTechnology/rexgen-socketcan.git;protocol=https;branch=main \
	file://LICENSE \
	file://Fix-Makefile-build-recipe.patch \
"
SRCREV = "871890899d6df0ac3df0e1e5c03e726dd5458dd8"

S = "${WORKDIR}"

inherit module

RPROVIDES:${PN} += "kernel-module-rexgen_usb"

