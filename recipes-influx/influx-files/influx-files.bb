SUMMARY = "Miscellaneous files for the base system"
DESCRIPTION = "The influx-files package adds some files referenced in documentation."
SECTION = "base"
LICENSE = "MIT"
LIC_FILES_CHKSUM="file://LICENSE;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://LICENSE \
	file://etc/minirc.dfl \
	file://etc/wvdial.conf \
	file://etc/chatscripts/1nce-new.chat \
	file://etc/firmware/BCM4345C0_003.001.025.0175.0000_Murata_1MW_SXM_TEST_ONLY.hcd \
	file://etc/ppp/peers/1nce.provider \
	file://etc/profile.d/enable_services.sh \
	file://etc/profile.d/login.sh \
	file://etc/profile.d/wlan_check.sh \
	file://etc/systemd/network/20-wireless-wlan0.network \
	file://etc/systemd/system/rexgen_data.service \
	file://etc/systemd/system/autostart.service \
	file://home/root/rexusb/rexgen \
	file://lib/systemd/system/wpa_supplicant@wlan0.service \
	file://lib/systemd/system/hostapd@wlan1.service \
	file://opt/influx/escape.minicom \
	file://opt/influx/gnssdata_start.sh \
	file://opt/influx/gnssinit.py \
	file://opt/influx/driver_reconnect.sh \
	file://opt/influx/pipes_reconnect.sh \
	file://opt/influx/VERSION \
	file://opt/influx/autostart.sh \
	file://opt/influx/check_firmware_version.sh \
        file://opt/influx/wakeup_BT.sh \
	file://opt/influx/SARA-R510M8S-00B-01_FW02.06_A00.01_IP.upd \
	file://opt/influx/SARA-R510M8S-01B-00_FW03.03_A00.01_PT.dof \
	file://opt/influx/options \
	file://opt/influx/ublox-up-down-pin.sh \
	file://opt/influx/lte_start_ppp.sh \
	file://opt/influx/lte_start_wvdial.sh \
	file://opt/influx/pap-secrets \
"

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
	${S}/home/root/rexusb/ \
	${S}/opt/influx/ \
"

# these files will be installed with 644 permisions
INFLUX_FILES_644 = "\
	minirc.dfl \
	wvdial.conf \
	rexgen_data.service \
	autostart.service \
	20-wireless-wlan0.network \
	hostapd@wlan1.service \
	wpa_supplicant@wlan0.service \
	escape.minicom \ 
	VERSION \
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