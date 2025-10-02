SUMMARY = "Tools to Google cloud support"

DESCRIPTION = "Google cloud support via Service Account credential json - download, upload, resume upload."
SECTION = "console/tools"

require rexgen-base.inc

SRC_URI:append = "git://github.com/InfluxTechnology/rexgen-linux-stream.git;protocol=https;branch=pro"

SRCREV = "fa1b857f698486acf6b65aecb6569904462133a4"

S1="${S}/src_aws"
S2="${S}/src_gcs_hmac"
S3="${S}/src_gcs_sa"

CC:append = " -fcommon -w "

do_compile () {
	${CC} -o aws ${S1}/main_aws.c ${S1}/s3_client.c ${S1}/s3_sigv4.c ${S1}/sha256.c ${LDFLAGS}
	${CC} -o gcs_hmac ${S2}/gcs_hmac.c ${S2}/gcs_client.c ${S2}/gcs_sigv2.c ${S2}/sha1.c ${LDFLAGS}
	${CC} -o gcs_sa ${S3}/*.c ${LDFLAGS}
}

do_install () {
	install -m 0755 ${S}/aws ${D}${REX_USB_DIR}/aws
	install -m 0755 ${S}/gcs_hmac ${D}${REX_USB_DIR}/gcs_hmac
	install -m 0755 ${S}/gcs_sa ${D}${REX_USB_DIR}/gcs_sa

	ln -sf ${REX_USB_DIR}aws ${D}/usr/sbin/aws
}

INHIBIT_PACKAGE_STRIP = "1"
INHIBIT_PACKAGE_DEBUG_SPLIT = "1"

PACKAGES = "${PN}"
FILES:${PN} = "/"
