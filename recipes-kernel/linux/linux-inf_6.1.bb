# Copyright (C) 2017-2023 Influx Technology
# Released under the MIT license (see COPYING.MIT for the terms)
#
# SPDX-License-Identifier: MIT
#

SUMMARY = "Linux Kernel provided by Influx Technology but based on NXP's kernel"
DESCRIPTION = "Linux Kernel for Influx Technology i.MX based COM boards. \
The kernel is based on the kernel provided by NXP."

require recipes-kernel/linux/linux-imx.inc

LICENSE = "GPL-2.0-only"
LIC_FILES_CHKSUM = "file://COPYING;md5=6bc538ed5bd9a7fc9398086aedcd7e46"

DEPENDS += "lzop-native bc-native"

SRCBRANCH = "influx_6.1.y"
LOCALVERSION = "-lts-next"
KERNEL_SRC ?= "git://github.com/InfluxTechnology/linux-imx.git;protocol=https;branch=${SRCBRANCH}"
KBRANCH = "${SRCBRANCH}"
SRC_URI = "${KERNEL_SRC}"

SRCREV = "08a1a77ba3b2ddc038087267210a2cf55951d7bb"

# PV is defined in the base in linux-imx.inc file and uses the LINUX_VERSION definition
# required by kernel-yocto.bbclass.
#
# LINUX_VERSION define should match to the kernel version referenced by SRC_URI and
# should be updated once patchlevel is merged.
LINUX_VERSION = "6.1.y"

KERNEL_CONFIG_COMMAND = "oe_runmake_call -C ${S} CC="${KERNEL_CC}" O=${B} olddefconfig"

DEFAULT_PREFERENCE = "1"

DO_CONFIG_INF_IMX_COPY = "no"
DO_CONFIG_INF_IMX_COPY:mx6-nxp-bsp = "yes"
DO_CONFIG_INF_IMX_COPY:mx7-nxp-bsp = "yes"
DO_CONFIG_INF_IMX_COPY:mx8-nxp-bsp = "no"
DO_CONFIG_INF_IMX_COPY:mx9-nxp-bsp = "no"

# Add setting for LF Mainline build
IMX_KERNEL_CONFIG_AARCH32 = "influx_imx8mm_defconfig"
IMX_KERNEL_CONFIG_AARCH64 = "influx_imx8mm_defconfig"
KBUILD_DEFCONFIG ?= ""
KBUILD_DEFCONFIG:mx6-nxp-bsp = "${IMX_KERNEL_CONFIG_AARCH32}"
KBUILD_DEFCONFIG:mx7-nxp-bsp = "${IMX_KERNEL_CONFIG_AARCH32}"
KBUILD_DEFCONFIG:mx8-nxp-bsp = "${IMX_KERNEL_CONFIG_AARCH64}"
KBUILD_DEFCONFIG:mx9-nxp-bsp = "${IMX_KERNEL_CONFIG_AARCH64}"


## Use a verbatim copy of the defconfig from the linux-imx repo.
## IMPORTANT: This task effectively disables kernel config fragments
## since the config fragments applied in do_kernel_configme are replaced.
#addtask copy_defconfig after do_kernel_configme before do_kernel_localversion
#do_copy_defconfig () {
#    install -d ${B}
#
#    if [ ${DO_CONFIG_INF_IMX_COPY} = "yes" ]; then
#        # copy latest ea_imx_defconfig to use
#        mkdir -p ${B}
#        cp ${S}/arch/arm/configs/${IMX_KERNEL_CONFIG_AARCH32} ${B}/.config
#    else
#        # copy latest defconfig to use for mx8
#        mkdir -p ${B}
#        cp ${S}/arch/arm64/configs/${IMX_KERNEL_CONFIG_AARCH64} ${B}/.config
#    fi
#}
#
#DELTA_KERNEL_DEFCONFIG ?= ""
##DELTA_KERNEL_DEFCONFIG:mx8-nxp-bsp = "imx.config"
#
#do_merge_delta_config[dirs] = "${B}"
#do_merge_delta_config[depends] += " \
#    flex-native:do_populate_sysroot \
#    bison-native:do_populate_sysroot \
#"
#do_merge_delta_config() {
#    for deltacfg in ${DELTA_KERNEL_DEFCONFIG}; do
#        if [ -f ${S}/arch/${ARCH}/configs/${deltacfg} ]; then
#            ${KERNEL_CONFIG_COMMAND}
#            oe_runmake_call -C ${S} CC="${KERNEL_CC}" O=${B} ${deltacfg}
#        elif [ -f "${WORKDIR}/${deltacfg}" ]; then
#            ${S}/scripts/kconfig/merge_config.sh -m .config ${WORKDIR}/${deltacfg}
#        elif [ -f "${deltacfg}" ]; then
#            ${S}/scripts/kconfig/merge_config.sh -m .config ${deltacfg}
#        fi
#    done
#    cp .config ${WORKDIR}/defconfig
#}
#addtask merge_delta_config before do_kernel_localversion after do_copy_defconfig

do_kernel_configcheck[noexec] = "1"

KERNEL_VERSION_SANITY_SKIP="1"
COMPATIBLE_MACHINE = "(imx-nxp-bsp)"
