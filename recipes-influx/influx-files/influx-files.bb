SUMMARY = "Miscellaneous files for the base system"
DESCRIPTION = "The influx-files package adds some files referenced in documentation."
SECTION = "base"
LICENSE = "MIT"
LIC_FILES_CHKSUM="file://LICENSE;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://LICENSE \
	file://other/VERSION \
	file://other/firststart.sh \
	file://other/ko_check.sh \
	file://other/autostart.sh \
	file://other/autostart.service \
	file://other/check_firmware_version.sh \
	file://wireless/wpa_supplicant@wlan0.service \
	file://wireless/20-wireless-wlan0.network \
	file://wireless/hostapd@wlan1.service \
	file://wireless/wlan_check.sh \
        file://wireless/wakeup_BT.sh \
	file://wireless/BCM4345C0_003.001.025.0175.0000_Murata_1MW_SXM_TEST_ONLY.hcd \
	file://rexusb/rexgen_data.service \
	file://rexusb/etc/escape.minicom \
	file://rexusb/etc/gnssdata_start.sh \
	file://rexusb/etc/minirc.dfl \
	file://rexusb/etc/gnssinit.py \
	file://rexusb/usb/uhubctl \
	file://rexusb/usb/rexgen_usb.conf \
	file://rexusb/usb/rexgen_usb \
	file://rexusb/usb/driver_reconnect.sh \
	file://rexusb/usb/pipes_reconnect.sh \
	file://ppp/ppp_generic \
	file://ppp/ppp_generic.conf \
	file://ppp/slhc \
	file://ppp/slhc.conf \
	file://ppp/ppp_deflate \
	file://ppp/ppp_deflate.conf \
	file://ppp/ppp_async \
	file://ppp/ppp_async.conf \
	file://ppp/bsd_comp \
	file://ppp/bsd_comp.conf \
	file://ppp/crc-ccitt \
	file://ppp/crc-ccitt.conf \
	file://lte/SARA-R510M8S-00B-01_FW02.06_A00.01_IP.upd \
	file://lte/SARA-R510M8S-01B-00_FW03.03_A00.01_PT.dof \
	file://lte/options \
	file://lte/1nce.provider \
	file://lte/pap-secrets \
	file://lte/1nce-new.chat \
	file://lte/wvdial.conf \
	file://lte/ublox-up-down-pin.sh \
	file://lte/lte_start_ppp.sh \
	file://lte/lte_start_wvdial.sh \
"

S = "${WORKDIR}"

do_install () {
	install -m 0755 -d ${D}${sysconfdir}/systemd/network
	install -m 0755 -d ${D}${systemd_system_unitdir}
	install -m 0755 -d ${D}/opt

	# Influx Technology
	# to find kernel release, type 'uname -r' on device and fill here  
#	EXTRA_DIR="/lib/modules/5.15.32+g1bee87d20/extra/"
#	MODULE_DIR="/lib/modules/5.15.32+g1bee87d20/"

	HOME_DIR="/home/root/"
	REX_USB_DIR="/home/root/rexusb/"
	INFLUX_DIR="/opt/influx/"

	install -m 0755 -d ${D}${REX_USB_DIR}
	install -m 0755 -d ${D}${INFLUX_DIR}/etc/
	install -m 0755 -d ${D}${INFLUX_DIR}/ko/
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

	# Influx Technology
	install -m 0644 ${WORKDIR}/rexusb/rexgen_data.service ${D}/etc/systemd/system/rexgen_data.service	
	install -m 0644 ${WORKDIR}/rexusb/etc/escape.minicom ${D}${INFLUX_DIR}/escape.minicom
	install -m 0755 ${WORKDIR}/rexusb/etc/gnssdata_start.sh ${D}${INFLUX_DIR}/gnssdata_start.sh
	install -m 0644 ${WORKDIR}/rexusb/etc/minirc.dfl ${D}/etc/minirc.dfl
	install -m 0755 ${WORKDIR}/rexusb/etc/gnssinit.py ${D}${INFLUX_DIR}/gnssinit.py	

	# rexgen_usb driver
	install -m 0644 ${WORKDIR}/rexusb/usb/uhubctl ${D}/usr/local/bin/uhubctl
	install -m 0755 ${WORKDIR}/rexusb/usb/driver_reconnect.sh ${D}${INFLUX_DIR}/driver_reconnect.sh
	install -m 0755 ${WORKDIR}/rexusb/usb/pipes_reconnect.sh ${D}${INFLUX_DIR}/pipes_reconnect.sh

	# crypto support

	# wireless
	install -m 0644 ${WORKDIR}/other/VERSION ${D}${INFLUX_DIR}/VERSION
	install -m 0644 ${WORKDIR}/wireless/wpa_supplicant@wlan0.service ${D}${systemd_system_unitdir}
	install -m 0644 ${WORKDIR}/wireless/20-wireless-wlan0.network ${D}${sysconfdir}/systemd/network/
	install -m 0644 ${WORKDIR}/wireless/hostapd@wlan1.service ${D}${systemd_system_unitdir}
	install -m 0755 ${WORKDIR}/wireless/wlan_check.sh ${D}/etc/profile.d/wlan_check.sh
	install -m 0755 ${WORKDIR}/wireless/wakeup_BT.sh ${D}${INFLUX_DIR}/wakeup_BT.sh
	install -m 0755 ${WORKDIR}/wireless/BCM4345C0_003.001.025.0175.0000_Murata_1MW_SXM_TEST_ONLY.hcd ${D}/etc/firmware/BCM4345C0_003.001.025.0175.0000_Murata_1MW_SXM_TEST_ONLY.hcd

	# LTE
	install -m 0644 ${WORKDIR}/lte/SARA-R510M8S-00B-01_FW02.06_A00.01_IP.upd ${D}${INFLUX_DIR}/SARA-R510M8S-00B-01_FW02.06_A00.01_IP.upd
	install -m 0644 ${WORKDIR}/lte/SARA-R510M8S-01B-00_FW03.03_A00.01_PT.dof ${D}${INFLUX_DIR}/SARA-R510M8S-01B-00_FW03.03_A00.01_PT.dof
	install -m 0644 ${WORKDIR}/lte/options ${D}${INFLUX_DIR}/options 		
	install -m 0644 ${WORKDIR}/lte/1nce.provider ${D}/etc/ppp/peers/1nce.provider
	install -m 0644 ${WORKDIR}/lte/pap-secrets ${D}${INFLUX_DIR}/pap-secrets	
	install -m 0644 ${WORKDIR}/lte/1nce-new.chat ${D}/etc/chatscripts/1nce-new.chat
	install -m 0644 ${WORKDIR}/lte/wvdial.conf  ${D}/etc/wvdial.conf
	install -m 0755 ${WORKDIR}/lte/ublox-up-down-pin.sh ${D}${INFLUX_DIR}/ublox-up-down-pin.sh
	install -m 0755 ${WORKDIR}/lte/lte_start_ppp.sh ${D}${INFLUX_DIR}/lte_start_ppp.sh
	install -m 0755 ${WORKDIR}/lte/lte_start_wvdial.sh ${D}${INFLUX_DIR}/lte_start_wvdial.sh

	# mender

	# other
	install -m 0755 ${WORKDIR}/other/firststart.sh ${D}/etc/profile.d/firststart.sh
	install -m 0755 ${WORKDIR}/other/ko_check.sh ${D}/etc/profile.d/ko_check.sh
	install -m 0755 ${WORKDIR}/other/autostart.sh ${D}${INFLUX_DIR}/autostart.sh
	install -m 0644 ${WORKDIR}/other/autostart.service ${D}/etc/systemd/system/autostart.service
	install -m 0755 ${WORKDIR}/other/check_firmware_version.sh ${D}${INFLUX_DIR}/check_firmware_version.sh    

	# cmake

	# kernel objects
	install -m 0644 ${WORKDIR}/ppp/ppp_generic ${D}${INFLUX_DIR}/ko/ppp_generic
	install -m 0644 ${WORKDIR}/ppp/slhc ${D}${INFLUX_DIR}/ko/slhc
	install -m 0644 ${WORKDIR}/ppp/ppp_deflate ${D}${INFLUX_DIR}/ko/ppp_deflate
	install -m 0644 ${WORKDIR}/ppp/ppp_async ${D}${INFLUX_DIR}/ko/ppp_async
	install -m 0644 ${WORKDIR}/ppp/bsd_comp ${D}${INFLUX_DIR}/ko/bsd_comp
	install -m 0644 ${WORKDIR}/ppp/crc-ccitt ${D}${INFLUX_DIR}/ko/crc-ccitt
	install -m 0644 ${WORKDIR}/rexusb/usb/rexgen_usb ${D}${INFLUX_DIR}/ko/rexgen_usb

	# modules load 
	install -m 0644 ${WORKDIR}/ppp/ppp_generic.conf ${D}/etc/modules-load.d/ppp_generic.conf
	install -m 0644 ${WORKDIR}/ppp/slhc.conf ${D}/etc/modules-load.d/slhc.conf
	install -m 0644 ${WORKDIR}/ppp/ppp_deflate.conf ${D}/etc/modules-load.d/ppp_deflate.conf
	install -m 0644 ${WORKDIR}/ppp/ppp_async.conf ${D}/etc/modules-load.d/ppp_async.conf
	install -m 0644 ${WORKDIR}/ppp/bsd_comp.conf ${D}/etc/modules-load.d/bsd_comp.conf
	install -m 0644 ${WORKDIR}/ppp/crc-ccitt.conf ${D}/etc/modules-load.d/crc-ccitt.conf
}

PACKAGES = "${PN}"
FILES:${PN} = "/"
