SUMMARY = "RexGen system logging service"

DESCRIPTION = " \
    Logs the min, max and average cpu, temperature and memory. \
    It also logs GNSS position and download speed. \
    Logs are written in /home/root/rexusb/log and uploaded to Google cloud at the end of the day. \
    Measurement times can be configured through rex_sys_log.conf \
"

require rexgen-base.inc

LICENSE = "CLOSED"

SRC_URI = " \
    file://rex_sys_log.conf \
    file://rex_sys_log.service \
    file://rex_sys_log.sh \
"

S = "${WORKDIR}"

do_install () {
	install -m 0644 ${S}/rex_sys_log.conf ${D}${REX_USB_DIR}/log/rex_sys_log.conf
	install -m 0755 ${S}/rex_sys_log.sh ${D}${REX_USB_DIR}/log/rex_sys_log.sh
	install -m 0644 ${S}/rex_sys_log.service ${D}/etc/systemd/system/rex_sys_log.service \

	ln -sf /etc/systemd/system/rex_sys_log.service ${D}/usr/lib/systemd/system/multi-user.target.wants/rex_sys_log.service
}

SYSTEMD_AUTO_ENABLE = "enable"
SYSTEMD_SERVICE:${PN} = "rex_sys_log.service"

INHIBIT_PACKAGE_STRIP = "1"
INHIBIT_PACKAGE_DEBUG_SPLIT = "1"

PACKAGES = "${PN}"
FILES:${PN} = "/"
