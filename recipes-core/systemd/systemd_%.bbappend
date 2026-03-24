FILESEXTRAPATHS:prepend := "${THISDIR}/files:"


SNWO_PATCH= "systemd-networkd-wait-online.patch"
SNWO_FILE= "systemd-networkd-wait-online.service"
BA_DIR := "${THISDIR}"
TS_PATCH="timesyncd.patch"

do_install:append() {
    patch -Np1 ${D}/usr/lib/systemd/system/${SNWO_FILE} < ${BA_DIR}/${SNWO_PATCH}
    patch -Np1 ${D}/etc/systemd/timesyncd.conf < ${BA_DIR}/${TS_PATCH}
}