
DESCRIPTION = "U-Boot for Influx Technology LTD Redge, RedgeAIR boards."

DEPENDS += "flex-native bison-native"

LICENSE = "GPL-2.0-or-later"
LIC_FILES_CHKSUM = "file://Licenses/gpl-2.0.txt;md5=b234ee4d69f5fce4486a80fdaf4a4263"

SRCBRANCH = "ea_v2022.04"
SRC_URI = "git://github.com/InfluxTechnology/uboot-imx.git;protocol=https;branch=${SRCBRANCH} \
           "
SRCREV = "ce43911c3841a4e52329769265a0b80f6a5ea06a"


S = "${WORKDIR}/git"

inherit fsl-u-boot-localversion

LOCALVERSION ?= "-${SRCBRANCH}"

PACKAGE_ARCH = "${MACHINE_ARCH}"

