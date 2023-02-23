
DESCRIPTION = "U-Boot for Influx Technology LTD Redge, RedgeAIR boards."

DEPENDS += "flex-native bison-native"

LICENSE = "GPL-2.0-or-later"
LIC_FILES_CHKSUM = "file://Licenses/gpl-2.0.txt;md5=b234ee4d69f5fce4486a80fdaf4a4263"

SRCBRANCH = "ea_v2022.04"
SRC_URI = "git://github.com/InfluxTechnology/uboot-imx.git;protocol=https;branch=${SRCBRANCH} \
           "
SRCREV = "7c19afc9bfef7cbf9ce8ae0c0c8cd4194c243db2"


S = "${WORKDIR}/git"

inherit fsl-u-boot-localversion

LOCALVERSION ?= "-${SRCBRANCH}"

PACKAGE_ARCH = "${MACHINE_ARCH}"

