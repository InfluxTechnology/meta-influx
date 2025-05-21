# Copyright (C) 2025 Influx Technology

DESCRIPTION = "U-Boot for Influx Technology i.MX based boards."

DEPENDS += "flex-native bison-native"

LICENSE = "GPL-2.0-or-later"
LIC_FILES_CHKSUM = "file://Licenses/gpl-2.0.txt;md5=b234ee4d69f5fce4486a80fdaf4a4263"

SRCBRANCH = "inf_v2024.04"
SRC_URI = "git://github.com/InfluxTechnology/uboot-imx.git;protocol=https;branch=${SRCBRANCH}"
SRCREV = "dcc2d06e2c82da592ce550de6e17869c78d82954"

S = "${WORKDIR}/git"

inherit fsl-u-boot-localversion

LOCALVERSION ?= "-${SRCBRANCH}"

PACKAGE_ARCH = "${MACHINE_ARCH}"

