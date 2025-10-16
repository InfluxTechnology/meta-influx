FILESEXTRAPATHS:prepend := "${THISDIR}/${PN}:"

SRC_URI += " \
    file://rexgen \
    file://rexgen_stream \
"

do_install:append () {
    install -m 0755 ${WORKDIR}/rexgen ${D}${REX_USB_DIR}/
    install -m 0755 ${WORKDIR}/rexgen_stream ${D}${REX_USB_DIR}/
}
