FILESEXTRAPATHS:prepend := "${THISDIR}/${PN}:"

SRC_URI += " \
    file://rexgen \
    file://rexgen_stream \
"

do_install:append () {
    install -m 755 ${WORKDIR}/rexgen* ${D}${REX_USB_DIR}/
}
