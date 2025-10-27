FILESEXTRAPATHS:prepend := "${THISDIR}/${PN}:"

SRC_URI += " \
    file://rexgen \
    file://rexgen_stream \
    file://aws \
"

do_install:append () {
    install -m 755 ${WORKDIR}/rexgen* ${D}${REX_USB_DIR}/
    install -m 755 ${WORKDIR}/aws ${D}${REX_USB_DIR}/
}
