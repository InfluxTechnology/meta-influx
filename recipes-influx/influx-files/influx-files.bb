SUMMARY = "Miscellaneous files for the base system"
DESCRIPTION = "The influx-files package adds some files referenced in documentation."
SECTION = "base"
LICENSE = "MIT"
LIC_FILES_CHKSUM="file://LICENSE;md5=0835ade698e0bcf8506ecda2f7b4f302"

S = "${WORKDIR}"

RDEPENDS:influx-files = "libusb1"

REX_USB_DIR="/home/root/rexusb/"
INFLUX_DIR="/opt/influx/"

# these folders will be created in the image
INFLUX_DIRS = "\
	/etc/profile.d/ \
	/etc/systemd/system/ \
	/etc/firmware/ \
	/etc/ppp/ \
	/etc/ppp/peers/ \
	/etc/chatscripts/ \
	/etc/systemd/network/ \
	/lib/systemd/system/ \
	${REX_USB_DIR} \
	${INFLUX_DIR} \
"

# must uncomment for mender support
#INFLUX_DIRS += "\
#	/etc/mender/
#	/etc/mender/scripts/
#	/usr/share/mender/
#	/usr/share/mender/modules/v3/
#"

# content of these folders will be installed with 755 permisions
INFLUX_FILES_755 = "\
	${S}/etc/ \
	${S}/lib/systemd/system \
	${S}/opt/influx/ \
"

# these files will be installed with 644 permisions
INFLUX_FILES_644 = "\
	minirc.dfl \
	wvdial.conf \
	wpa_supplicant.conf.cust \
	rexgen_data.service \
	autostart.service \
	20-wireless-wlan0.network \
	hostapd@wlan1.service \
	wpa_supplicant@wlan0.service \
	escape.minicom \ 
	Release-notes \
	SARA-R510M8S-00B-01_FW02.06_A00.01_IP.upd \
	SARA-R510M8S-01B-00_FW03.03_A00.01_PT.dof \
	options \
	pap-secrets \
	1nce-new.chat \
	1nce.provider \
"

do_install () {
	for d in ${INFLUX_DIRS}; do
		fold="${d#${S}}"
		install -m 0755 -d ${D}${fold}
	done

	for d in $(find ${INFLUX_FILES_755}); do
		# skip folders
		if [ -d ${d} ]; then
			continue
		fi

		t="${d#${S}}"
		for c in $(echo ${t} | tr "/" "\n"); do
			file=${c}
		done

		fold="${t%${file}}"

		install -m 0755 ${S}${fold}${file} ${D}${fold}${file}

		for e in ${INFLUX_FILES_644}; do
			if [ "${e}" != "${file}" ]; then 
				continue
			else
				chmod 644 ${D}${fold}${file}
			fi
		done
	done
}

INHIBIT_PACKAGE_STRIP = "1"
INHIBIT_PACKAGE_DEBUG_SPLIT = "1"

PACKAGES = "${PN}"
FILES:${PN} = "/"
