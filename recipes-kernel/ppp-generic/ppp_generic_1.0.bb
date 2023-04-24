SUMMARY = "Build ppp module"
LICENSE = "GPLv2"
LIC_FILES_CHKSUM = "file://COPYING;md5=12f884d2ae1ff87c09e5b7ccc2c4ca7e"

inherit module

SRC_URI = "file://Makefile \
           file://COPYING \
"

S = "${WORKDIR}"

FILES_${PN} += "${libdir}/*"
FILES_${PN}-dev = "${libdir}/* ${includedir}"

PPP_SRC = "${STAGING_KERNEL_DIR}/drivers/net/ppp/"
SLIP_SRC = "${STAGING_KERNEL_DIR}/drivers/net/slip/"
CRC_SRC = "${STAGING_KERNEL_DIR}/lib/"

do_fetch () {
	cp ${PPP_SRC}/*.h ${S}
	cp ${PPP_SRC}/*.c ${S}
	cp ${SLIP_SRC}/*.h ${S}
	cp ${SLIP_SRC}/*.c ${S}
	cp ${CRC_SRC}/crc-ccitt.c ${S}
}

RPROVIDES_${PN} += "kernel-module-ppp_generic"
RPROVIDES_${PN} += "kernel-module-ppp_async"
RPROVIDES_${PN} += "kernel-module-ppp_deflate"
RPROVIDES_${PN} += "kernel-module-bsd_comp"
RPROVIDES_${PN} += "kernel-module-crc-ccitt"
RPROVIDES_${PN} += "kernel-module-slhc"

MODULES_LOAD = "bsd_comp  crc-ccitt  ppp_async  ppp_deflate  ppp_generic  slhc"

do_install:append () {
	install -m 0755 -d ${D}/etc/modules-load.d/

	for c in $(echo ${MODULES_LOAD}); do
		echo ${c} > ${S}/${c}.conf
		install -m 0644 ${S}/${c}.conf ${D}/etc/modules-load.d/${c}.conf 
	done
}

#INHIBIT_PACKAGE_STRIP = "1"
#INHIBIT_PACKAGE_DEBUG_SPLIT = "1"

#PACKAGES = "${PN}"
#FILES:${PN} = "/"

