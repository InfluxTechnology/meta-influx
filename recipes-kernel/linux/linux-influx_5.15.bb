# Copyright (C) 2022 Influx Technology LTD
# Released under the MIT license (see COPYING.MIT for the terms)

SUMMARY = "Linux Kernel provided by Influx Technology is based on NXP's kernel"
DESCRIPTION = "Linux Kernel for Influx Technology Redge RedgeAIR boards. \
The kernel is based on the kernel provided by NXP."

require recipes-kernel/linux/linux-imx.inc

SRC_URI = "git://github.com/InfluxTechnology/linux-imx.git;protocol=https;branch=${SRCBRANCH}"
SRCREV = "0690fc0f7ea1e81fc2bee67c995e814854aa1d9e"

LIC_FILES_CHKSUM = "file://COPYING;md5=6bc538ed5bd9a7fc9398086aedcd7e46"

LOCALVERSION = ""
SRCBRANCH = "ea_5.15.y"
DEPENDS += "lzop-native bc-native"

SRC_URI += "file://0001-uapi-Add-ion.h-to-userspace.patch"

LINUX_VERSION = "5.15.32"

DEFAULT_PREFERENCE = "1"

DO_CONFIG_EA_IMX_COPY = "no"
DO_CONFIG_EA_IMX_COPY:mx6-nxp-bsp = "yes"
DO_CONFIG_EA_IMX_COPY:mx7-nxp-bsp = "yes"
DO_CONFIG_EA_IMX_COPY:mx8-nxp-bsp = "no"

# Add setting for LF Mainline build
IMX_KERNEL_CONFIG_AARCH32 = "ea_imx_defconfig"
IMX_KERNEL_CONFIG_AARCH64 = "ea_imx8_defconfig"
KBUILD_DEFCONFIG ?= ""
KBUILD_DEFCONFIG:mx6-nxp-bsp = "${IMX_KERNEL_CONFIG_AARCH32}"
KBUILD_DEFCONFIG:mx7-nxp-bsp = "${IMX_KERNEL_CONFIG_AARCH32}"
KBUILD_DEFCONFIG:mx8-nxp-bsp = "${IMX_KERNEL_CONFIG_AARCH64}"

addtask copy_defconfig after do_unpack before do_preconfigure
do_copy_defconfig () {
    install -d ${B}

    if [ ${DO_CONFIG_EA_IMX_COPY} = "yes" ]; then
        # copy latest ea_imx_defconfig to use
        mkdir -p ${B}
        cp ${S}/arch/arm/configs/${IMX_KERNEL_CONFIG_AARCH32} ${B}/.config
        cp ${S}/arch/arm/configs/${IMX_KERNEL_CONFIG_AARCH32} ${B}/../defconfig
    else
        # copy latest defconfig to use for mx8
        mkdir -p ${B}
        cp ${S}/arch/arm64/configs/${IMX_KERNEL_CONFIG_AARCH64} ${B}/.config
        cp ${S}/arch/arm64/configs/${IMX_KERNEL_CONFIG_AARCH64} ${B}/../defconfig
    fi
}

COMPATIBLE_MACHINE = "(imx-nxp-bsp)"

EXTRA_OEMAKE:append:mx6-nxp-bsp = " ARCH=arm"
EXTRA_OEMAKE:append:mx7-nxp-bsp = " ARCH=arm"
EXTRA_OEMAKE:append:mx8-nxp-bsp = " ARCH=arm64"
