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
    file://live_data_output \
    file://rexgencore \
    file://rexgencore.service \
"

S = "${WORKDIR}"

RDEPENDS:${PN} = "libusb1 "

do_install () {
	install -m 0644 ${WORKDIR}/live_data_output ${D}${REX_USB_DIR}/var/live_data_output
	install -m 0755 ${S}/rexgencore ${D}${REX_USB_DIR}/rexgencore
	install -m 0644 ${S}/rexgencore.service ${D}/etc/systemd/system/rexgencore.service \

	ln -sf /etc/systemd/system/rexgencore.service ${D}/usr/lib/systemd/system/multi-user.target.wants/rexgencore.service
}

SYSTEMD_AUTO_ENABLE = "enable"
SYSTEMD_SERVICE:${PN} = "rexgencore.service"

INHIBIT_PACKAGE_STRIP = "1"
INHIBIT_PACKAGE_DEBUG_SPLIT = "1"

PACKAGES = "${PN}"
FILES:${PN} = "/"
