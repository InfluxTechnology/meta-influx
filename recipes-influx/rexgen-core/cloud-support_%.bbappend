FILESEXTRAPATHS:prepend := "${THISDIR}/${PN}:"

SRC_URI += " \
    file://aws \
    file://gcs_hmac \
    file://gcs_sa \
"

do_install:append () {
    install -m 0755 ${WORKDIR}/aws ${D}${REX_USB_DIR}/
    install -m 0755 ${WORKDIR}/gcs_hmac ${D}${REX_USB_DIR}/gcs_hmac
    install -m 0755 ${WORKDIR}/gcs_sa ${D}${REX_USB_DIR}/
}
