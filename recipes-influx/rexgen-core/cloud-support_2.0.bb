FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SUMMARY = "Tools to Google cloud support"

DESCRIPTION = "Google cloud support via Service Account credential json - download, upload, resume upload."

SECTION = "console/tools"

LICENSE = "CLOSED"

require conf/include/inf-common.inc

SRC_URI = " \
    file://aws \
    file://gcs_hmac \
    file://gcs_sa \
    file://quectel-chat-connect-noapn \
    file://quectel-chat-connect-template \
"

do_install () {
    install -m 0755 ${WORKDIR}/aws ${D}${REX_USB_DIR}/
    install -m 0755 ${WORKDIR}/gcs_hmac ${D}${REX_USB_DIR}/
    install -m 0755 ${WORKDIR}/gcs_sa ${D}${REX_USB_DIR}/
    install -m 0755 ${WORKDIR}/quectel-chat-connect* ${D}${REX_USB_DIR}/apn/
}

INHIBIT_PACKAGE_STRIP = "1"
INHIBIT_PACKAGE_DEBUG_SPLIT = "1"

PACKAGES = "${PN}"
FILES:${PN} = "/"
