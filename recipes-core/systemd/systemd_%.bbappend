FILESEXTRAPATHS:prepend := "${THISDIR}/files:"


BA_PATCH= "systemd-networkd-wait-online.patch"
BA_FILE= "systemd-networkd-wait-online.service"
BA_DIR := "${THISDIR}"

do_install:append() {
    patch -Np1 ${D}/usr/lib/systemd/system/${BA_FILE} < ${BA_DIR}/${BA_PATCH}
}