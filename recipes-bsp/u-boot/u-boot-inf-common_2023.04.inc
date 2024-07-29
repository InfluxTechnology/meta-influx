# Copyright (C) 2023 Influx Technology

DESCRIPTION = "U-Boot for Influx Technology i.MX based boards."

DEPENDS += "flex-native bison-native"

LICENSE = "GPL-2.0-or-later"
LIC_FILES_CHKSUM = "file://Licenses/gpl-2.0.txt;md5=b234ee4d69f5fce4486a80fdaf4a4263"

SRCBRANCH = "inf_v2023.04"
SRC_URI = "git://github.com/InfluxTechnology/uboot-imx.git;protocol=https;branch=${SRCBRANCH}"
SRCREV = "0319391f0bea51d0679f75693ad0016f882f89e2"

S = "${WORKDIR}/git"

inherit fsl-u-boot-localversion

LOCALVERSION ?= "-${SRCBRANCH}"

PACKAGE_ARCH = "${MACHINE_ARCH}"

