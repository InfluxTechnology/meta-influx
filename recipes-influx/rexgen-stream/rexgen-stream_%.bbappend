FILESEXTRAPATHS:prepend := "${THISDIR}/${PN}:"

SRC_URI += " \
    file://aws \
    file://gcs_sa \
    file://rexgen \
    file://rexgen_stream \
    file://live_data_output \
"

do_install:append () {
    install -m 0644 ${WORKDIR}/live_data_output ${D}${REX_USB_DIR}/var/live_data_output
    install -m 0755 ${WORKDIR}/aws ${D}${REX_USB_DIR}/
    install -m 0755 ${WORKDIR}/gcs_sa ${D}${REX_USB_DIR}/
    install -m 0755 ${WORKDIR}/rexgen ${D}${REX_USB_DIR}/
}
