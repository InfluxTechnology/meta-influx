SUMMARY = "Build ppp module"
LICENSE = "GPLv2"
LIC_FILES_CHKSUM = "file://COPYING;md5=12f884d2ae1ff87c09e5b7ccc2c4ca7e"

inherit module

SRC_URI = "file://Makefile \
           file://ppp_generic.c \
           file://ppp_async.c \
           file://ppp_deflate.c \
           file://bsd_comp.c \
           file://slhc.c \
           file://crc-ccitt.c \
           file://COPYING \
          "

S = "${WORKDIR}"

# The inherit of module.bbclass will automatically name module packages with
# "kernel-module-" prefix as required by the oe-core build environment.

RPROVIDES_${PN} += "kernel-module-ppp_generic"
RPROVIDES_${PN} += "kernel-module-ppp_async"
RPROVIDES_${PN} += "kernel-module-ppp_deflate"
RPROVIDES_${PN} += "kernel-module-bsd_comp"
RPROVIDES_${PN} += "kernel-module-crc-ccitt"
RPROVIDES_${PN} += "kernel-module-slhc"

FILES_${PN} += "${libdir}/*"
FILES_${PN}-dev = "${libdir}/* ${includedir}"

