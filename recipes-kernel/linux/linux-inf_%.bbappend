FILESEXTRAPATHS:prepend := "${THISDIR}/${PN}:"

MAINTAINER = "Influx Technology <ggeorgiev@influxtechnology.com>"

SRC_URI:append = "\
    file://0001-influx_imx8mm_defconfig.patch \
"

IMAGE_INSTALL:append = " \
    kernel-module-usbnet \
    kernel-module-cdc-wdm \
    kernel-module-qmi-wwan \
    kernel-module-cdc-mbim \
    kernel-module-cdc-ncm \
    kernel-module-cdc-ether \
"

KERNEL_MODULE_AUTOLOAD:append = " usbnet cdc_wdm qmi_wwan cdc_mbim cdc_ncm cdc_ether "
