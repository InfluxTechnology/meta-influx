SUMMARY = "Provide communication with RexGen device"

DESCRIPTION = " \
    Store some RexGen parameters in /home/root/rexusb/var/ \
    Support socket can over virtual can. (file live_data_output must contain 'socketcan') \
    Support multi partition. \
    Upload data to cloud. \
"

require rexgen-base.inc

LICENSE = "CLOSED"

SRC_URI = " \
    file://rexgend \
    file://rexgend.conf \
    file://rexgend.service \
    file://end_influx_upgrade.service \
"

S = "${WORKDIR}"

RDEPENDS:${PN} = "libusb1 "

do_install () {
	install -m 0755 ${S}/rexgend ${D}${REX_USB_DIR}/rexgend
	install -m 0644 ${S}/rexgend.conf ${D}${REX_USB_DIR}/rexgend.conf
	install -m 0644 ${S}/rexgend.service ${D}/etc/systemd/system/rexgend.service 
	install -m 0644 ${S}/end_influx_upgrade.service ${D}/etc/systemd/system/end_influx_upgrade.service

#	ln -sf /etc/systemd/system/rexgend.service ${D}/usr/lib/systemd/system/multi-user.target.wants/rexgend.service
}

#SYSTEMD_AUTO_ENABLE = "enable"
#SYSTEMD_SERVICE:${PN} = "rexgend.service"

INHIBIT_PACKAGE_STRIP = "1"
INHIBIT_PACKAGE_DEBUG_SPLIT = "1"

PACKAGES = "${PN}"
FILES:${PN} = "/"
