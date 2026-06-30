FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SUMMARY = "Provide communication with RexGen device"

DESCRIPTION = " \
    Store some RexGen parameters in /home/root/rexusb/var/ \
    Support socket can over virtual can. (file live_data_output must contain 'socketcan') \
    Support multi partition. \
    Upload data to cloud. \
"

require conf/include/inf-common.inc

LICENSE = "CLOSED"

SRC_URI = " \
    file://rexgend \
    file://rexgend.conf \
    file://example.so \
    file://seedkey \
    file://rexgend.service \
    file://end_influx_upgrade.service \
"

S = "${WORKDIR}"

RDEPENDS:${PN} = "libusb1 "

do_install () {
#	mkdir -p ${D}/data/rexgen/seedkey/
#	install -m 0644 ${S}/example.so ${D}/data/rexgen/seedkey/example.so
#	install -m 0755 ${S}/seedkey ${D}/data/rexgen/seedkey/seedkey

	install -m 0755 ${S}/rexgend ${D}${REX_USB_DIR}/rexgend
	install -m 0644 ${S}/rexgend.conf ${D}${REX_USB_DIR}/rexgend.conf
	install -m 0644 ${S}/rexgend.service ${D}/etc/systemd/system/rexgend.service 
	install -m 0644 ${S}/end_influx_upgrade.service ${D}/etc/systemd/system/end_influx_upgrade.service

	ln -sf /home/root/rexusb/rexgend ${D}/usr/sbin/rexgend
}

INHIBIT_PACKAGE_STRIP = "1"
INHIBIT_PACKAGE_DEBUG_SPLIT = "1"

PACKAGES = "${PN}"
FILES:${PN} = "/"

pkg_postinst_ontarget:${PN}() {
	mv /home/root/rexusb/rexgend.conf /data/rexgen/config/rexgend.conf
}
