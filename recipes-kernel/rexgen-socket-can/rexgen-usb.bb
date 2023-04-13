SUMMARY = "Influx Technology LTD - ReXgen SocketCAN Driver for linux"
DESCRIPTION = "The SocketCAN driver allows you to use ReXgen device as CAN interfaces within your own socketCAN based applications."

LICENSE = "MIT"
LIC_FILES_CHKSUM="file://LICENSE;md5=b234ee4d69f5fce4486a80fdaf4a4263"

SRC_URI = "git://github.com/InfluxTechnology/rexgen-socketcan.git;protocol=https;branch=main \
	file://LICENSE \
	file://Fix-Makefile-build-recipe.patch \
"
SRCREV = "bb8075d1d3e7adb4943f041bd9ef58f6bac5b991"
S = "${WORKDIR}/git"

S = "${WORKDIR}"

inherit module

RPROVIDES:${PN} += "kernel-module-rexgen_usb"

