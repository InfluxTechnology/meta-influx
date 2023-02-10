SUMMARY = "Miscellaneous files for the base system"
DESCRIPTION = "The influx-files package adds some files referenced in documentation."
SECTION = "base"
LICENSE = "MIT"
LIC_FILES_CHKSUM="file://LICENSE;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://LICENSE \
	file://other/firststart.sh \
	file://wireless/wpa_supplicant@wlan0.service \
	file://wireless/20-wireless-wlan0.network \
	file://wireless/hostapd@wlan1.service \
"

S = "${WORKDIR}"

INFLUX_FILES_644 ?= ""
INFLUX_FILES_755 ?= ""
INFLUX_FILES_DIRS ?= ""

do_install () {
	install -m 0755 -d ${D}${sysconfdir}/systemd/network
	install -m 0755 -d ${D}${systemd_system_unitdir}
	install -m 0755 -d ${D}/opt

	# Influx Technology
	# to find kernel release, type 'uname -r' on device and fill here  
	EXTRA_DIR="/lib/modules/5.15.32+g663184199df6/extra/"
	MODULE_DIR="/lib/modules/5.15.32+g663184199df6/"

	HOME_DIR="/home/root/"
	REX_USB_DIR="/home/root/rexusb/"
	REX_FRM_DIR="/home/root/rexusb/firmware"
	REX_CFG_DIR="/home/root/rexusb/config"
	INFLUX_DIR="/opt/influx/"

	install -m 0755 -d ${D}${EXTRA_DIR}
	install -m 0755 -d ${D}${REX_USB_DIR}
	install -m 0755 -d ${D}${REX_USB_DIR}/demo/
	install -m 0755 -d ${D}${REX_FRM_DIR}
	install -m 0755 -d ${D}${REX_CFG_DIR}
	install -m 0755 -d ${D}${INFLUX_DIR}
	install -m 0755 -d ${D}${INFLUX_DIR}/etc/
	install -m 0755 -d ${D}${INFLUX_DIR}/cmake/
	install -m 0755 -d ${D}/etc/modules-load.d/
	install -m 0755 -d ${D}/home/root/
	install -m 0755 -d ${D}/etc/profile.d/
	install -m 0755 -d ${D}/etc/ppp/
	install -m 0755 -d ${D}/etc/ppp/peers/
	install -m 0755 -d ${D}/etc/chatscripts/
	install -m 0755 -d ${D}/etc/systemd/system/
	install -m 0755 -d ${D}/etc/firmware/
	install -m 0755 -d ${D}/etc/firmware/murata-master/
#	install -m 0755 -d ${D}/etc/mender/
	install -m 0755 -d ${D}/etc/network/
#	install -m 0755 -d ${D}/etc/mender/scripts/
#	install -m 0755 -d ${D}/usr/share/mender/
#	install -m 0755 -d ${D}/usr/share/mender/modules/v3/
	install -m 0755 -d ${D}/usr/local/bin/


	for d in ${INFLUX_FILES_DIRS}; do
		install -m 0755 -d ${D}${d}
	done

	# Influx Technology
	
	# RexGen support

	# rexgen_usb driver

	# gnssdata support

	# ppp support

	# crypto support

	# wireless
	install -m 0644 ${WORKDIR}/wireless/wpa_supplicant@wlan0.service ${D}${systemd_system_unitdir}
	install -m 0644 ${WORKDIR}/wireless/20-wireless-wlan0.network ${D}${sysconfdir}/systemd/network/
	install -m 0644 ${WORKDIR}/wireless/hostapd@wlan1.service ${D}${systemd_system_unitdir}

	# LTE

	# mender

	# other
	install -m 0755 ${WORKDIR}/other/firststart.sh ${D}/etc/profile.d/firststart.sh
    
	# cmake

	# load kernel modules at start

	for d in ${INFLUX_FILES_644}; do
		f_in=$(echo "${d}" | cut -d":" -f1)
		f_out=$(echo "$d" | cut -d":" -f2)
		if [ "${f_in#/}" = "${f_in}" ]] ;
		then
			install -m 0644 ${TOPDIR}/${f_in} ${D}${f_out}
		else
			install -m 0644 ${f_in} ${D}${f_out}
		fi
	done
	
	for d in ${INFLUX_FILES_755}; do
		f_in=$(echo "${d}" | cut -d":" -f1)
		f_out=$(echo "$d" | cut -d":" -f2)
		if [ "${f_in#/}" = "${f_in}" ]] ;
		then
			install -m 0755 ${TOPDIR}/${f_in} ${D}${f_out}
		else
			install -m 0755 ${f_in} ${D}${f_out}
		fi
	done
}

PACKAGES = "${PN}"
FILES:${PN} = "/"
