SUMMARY = "Miscellaneous files for the base system"
DESCRIPTION = "The influx-files package adds some files referenced in documentation and includes the WiFi management project, along with the socket application."
SECTION = "base"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://LICENSE;md5=0835ade698e0bcf8506ecda2f7b4f302"

#	file://etc/hostname 
SRC_URI = "file://LICENSE \
        file://etc/minirc.dfl \
        file://etc/wvdial.conf \
        file://etc/chatscripts/1nce-new.chat \
        file://etc/firmware/BCM4345C0_003.001.025.0175.0000_Murata_1MW_SXM_TEST_ONLY.hcd \
	file://etc/mender/scripts/ArtifactInstall_Enter_00 \
	file://etc/mender/scripts/ArtifactReboot_Leave_00 \
	file://etc/mender/scripts/Download_Leave_00 \
	file://etc/mender/scripts/Download_Enter_00 \
        file://etc/ppp/peers/1nce.provider \
        file://etc/ppp/peers/quectel-chat-connect \
        file://etc/ppp/peers/quectel-chat-disconnect \
        file://etc/ppp/peers/quectel-ppp \
        file://etc/profile.d/enable_services.sh \
        file://etc/profile.d/login.sh \
        file://etc/profile.d/wlan_check.sh \
        file://etc/profile.d/wpa_supplicant_check.sh \
        file://etc/systemd/network/20-wireless-wlan0.network \
        file://etc/systemd/system/autostart.service \
        file://usr/lib/systemd/system/wpa_supplicant@wlan0.service \
        file://usr/lib/systemd/system/hostapd@wlan1.service \
        file://opt/influx/escape.minicom \
        file://opt/influx/gnssdata_start.sh \
        file://opt/influx/gnssinit_quectel.py \
        file://opt/influx/gnssinit_ublox.py \
        file://opt/influx/driver_reconnect.sh \
        file://opt/influx/pipes_reconnect.sh \
        file://opt/influx/Release-notes \
        file://opt/influx/autostart.sh \
        file://opt/influx/check_firmware_version.sh \
        file://opt/influx/wakeup_BT.sh \
        file://opt/influx/options \
        file://opt/influx/cellular_module_start.sh \
        file://opt/influx/lte_start_ppp.sh \
        file://opt/influx/lte_start_wvdial.sh \
        file://opt/influx/pap-secrets \
        file://opt/influx/wpa_supplicant.conf.cust \
        file://opt/influx/start_ppp0.sh \
	file://opt/influx/ap_flask/ap_flask.py \
        file://opt/influx/ap_flask/wifi_monitor.sh \
        file://opt/influx/ap_flask/templates/index.html \
        file://etc/systemd/system/wifi_monitor.service \
        file://etc/systemd/system/wifi_monitor.timer \
        file://opt/influx/setup_wifi_module.sh \
        file://opt/influx/socket/socket \
        file://etc/systemd/system/socket.service \
        file://etc/systemd/system/lte-ppp.service \
        file://opt/influx/net_failover.sh \
        file://etc/systemd/system/net-failover.service \
        file://etc/systemd/system/net-failover.timer \
        file://opt/influx/ap_flask/net_led.sh \
        file://etc/systemd/system/net_led.service \
        file://opt/influx/release_check.sh \
        file://etc/systemd/system/rex_sys_log.service \
        file://etc/systemd/system/release_check.service \
        file://opt/influx/rc.local \
        file://opt/influx/release_check.sh \
	file://opt/influx/preserved-files \
        file://home/root/rexusb/gcs_hmac \
        file://home/root/rexusb/gcs_sa \
        file://home/root/rexusb/aws \
        file://home/root/rexusb/log/rex_sys_log.conf \
        file://home/root/rexusb/log/rex_sys_log.sh \
"

S = "${WORKDIR}"

# Add runtime dependencies
RDEPENDS:${PN} = "libusb1 python3 python3-flask python3-pip bash dnsmasq"

REX_USB_DIR="/home/root/rexusb/"
INFLUX_DIR="/opt/influx/"

# Directories to create in the image
INFLUX_DIRS = "\
    /etc/profile.d/ \
    /etc/systemd/system/ \
    /etc/firmware/ \
    /etc/ppp/ \
    /etc/ppp/peers/ \
    /etc/chatscripts/ \
    /etc/systemd/network/ \
    /usr/lib/systemd/system/ \
    ${REX_USB_DIR} \
    ${REX_USB_DIR}/log/ \
    ${INFLUX_DIR} \
    ${INFLUX_DIR}/ap_flask/ \
    ${INFLUX_DIR}/ap_flask/templates/ \
    ${INFLUX_DIR}/socket/ \
    /etc/mender/scripts/ \
"

# Files to install with 755 permissions
INFLUX_FILES_755 = "\
    ${S}/etc/mender/scripts/ArtifactInstall_Enter_00 \
    ${S}/etc/mender/scripts/ArtifactReboot_Leave_00 \
    ${S}/etc/mender/scripts/Download_Enter_00 \
    ${S}/etc/mender/scripts/Download_Leave_00 \
    ${S}/opt/influx/escape.minicom \
    ${S}/opt/influx/gnssdata_start.sh \
    ${S}/opt/influx/gnssinit_quectel.py \
    ${S}/opt/influx/gnssinit_ublox.py \
    ${S}/opt/influx/driver_reconnect.sh \
    ${S}/opt/influx/pipes_reconnect.sh \
    ${S}/opt/influx/autostart.sh \
    ${S}/opt/influx/check_firmware_version.sh \
    ${S}/opt/influx/wakeup_BT.sh \
    ${S}/opt/influx/cellular_module_start.sh \
    ${S}/opt/influx/lte_start_ppp.sh \
    ${S}/opt/influx/lte_start_wvdial.sh \
    ${S}/opt/influx/start_ppp0.sh \
    ${S}/opt/influx/ap_flask/ap_flask.py \
    ${S}/opt/influx/ap_flask/wifi_monitor.sh \
    ${S}/opt/influx/socket/socket \
    ${S}/opt/influx/setup_wifi_module.sh \
    ${S}/opt/influx/ap_flask/net_led.sh \
    ${S}/opt/influx/release_check.sh \
    ${S}/opt/influx/net_failover.sh \
    ${S}/opt/influx/rc.local \
    ${S}/home/root/rexusb/log/rex_sys_log.sh \
    ${S}/home/root/rexusb/gcs_hmac \
    ${S}/home/root/rexusb/gcs_sa \
    ${S}/home/root/rexusb/aws \
    ${S}/opt/influx/preserved-files \
"

# Files to install with 644 permissions
INFLUX_FILES_644 = "\
    ${S}/etc/hostname \
    ${S}/etc/minirc.dfl \
    ${S}/etc/wvdial.conf \
    ${S}/etc/profile.d/enable_services.sh \
    ${S}/etc/profile.d/login.sh \
    ${S}/etc/profile.d/wlan_check.sh \
    ${S}/etc/profile.d/wpa_supplicant_check.sh \
    ${S}/etc/systemd/network/20-wireless-wlan0.network \
    ${S}/etc/systemd/system/autostart.service \
    ${S}/usr/lib/systemd/system/wpa_supplicant@wlan0.service \
    ${S}/usr/lib/systemd/system/hostapd@wlan1.service \
    ${S}/opt/influx/Release-notes \
    ${S}/opt/influx/options \
    ${S}/opt/influx/pap-secrets \
    ${S}/opt/influx/wpa_supplicant.conf.cust \
    ${S}/opt/influx/ap_flask/templates/index.html \
    ${S}/home/root/rexusb/log/rex_sys_log.conf \
    ${S}/etc/systemd/system/wifi_monitor.service \
    ${S}/etc/systemd/system/wifi_monitor.timer \
    ${S}/etc/systemd/system/socket.service \
    ${S}/etc/systemd/system/lte-ppp.service \
    ${S}/etc/systemd/system/net_led.service \
    ${S}/etc/systemd/system/net-failover.service \
    ${S}/etc/systemd/system/net-failover.timer \
    ${S}/etc/systemd/system/rex_sys_log.service \
    ${S}/etc/ppp/peers/1nce.provider \
    ${S}/etc/ppp/peers/quectel-chat-connect \
    ${S}/etc/ppp/peers/quectel-chat-disconnect \
    ${S}/etc/ppp/peers/quectel-ppp \
"

do_install() {
    # Create necessary directories
    for d in ${INFLUX_DIRS}; do
        install -m 0755 -d ${D}${d}
    done

    # Ensure the systemd multi-user.target.wants directory exists
    install -d ${D}/usr/lib/systemd/system/multi-user.target.wants

    # Install files with 755 permissions
    for f in ${INFLUX_FILES_755}; do
        if [ -f ${f} ]; then
            install -m 0755 ${f} ${D}${f#${S}}
        else
            echo "Warning: Skipping missing file ${f}"
        fi
    done

    # Install files with 644 permissions
    for f in ${INFLUX_FILES_644}; do
        if [ -f ${f} ]; then
            install -m 0644 ${f} ${D}${f#${S}}
        else
            echo "Warning: Skipping missing file ${f}"
        fi
    done

    # Enable services manually
    ln -sf /etc/systemd/system/wifi_monitor.service ${D}/usr/lib/systemd/system/multi-user.target.wants/wifi_monitor.service
    ln -sf /etc/systemd/system/wifi_monitor.timer ${D}/usr/lib/systemd/system/multi-user.target.wants/wifi_monitor.timer
    ln -sf /etc/systemd/system/socket.service ${D}/usr/lib/systemd/system/multi-user.target.wants/socket.service
    ln -sf /etc/systemd/system/lte-ppp.service ${D}/usr/lib/systemd/system/multi-user.target.wants/lte-ppp.service
    ln -sf /etc/systemd/system/net_led.service ${D}/usr/lib/systemd/system/multi-user.target.wants/net_led.service
    ln -sf /etc/systemd/system/net-failover.service ${D}/usr/lib/systemd/system/multi-user.target.wants/net-failover.service
    ln -sf /etc/systemd/system/net-failover.timer ${D}/usr/lib/systemd/system/multi-user.target.wants/net-failover.timer
    ln -sf /etc/systemd/system/rex_sys_log.service ${D}/usr/lib/systemd/system/multi-user.target.wants/rex_sys_log.service
}

# Enable systemd services
SYSTEMD_AUTO_ENABLE = "enable"
SYSTEMD_SERVICE:${PN} = "wifi_monitor.service wifi_monitor.timer socket.service lte-ppp.service net_led.service rex_sys_log.service"

INHIBIT_PACKAGE_STRIP = "1"
INHIBIT_PACKAGE_DEBUG_SPLIT = "1"

PACKAGES = "${PN}"
FILES:${PN} = "/"

# Post-install script to setup Wi-Fi module
pkg_postinst:${PN}() {
    if [ -z "$D" ]; then
        echo "Running postinstall for Wi-Fi module setup..."
        
        exec >> /var/log/post_wifi.log 2>&1
        set -x

        # Unlock boot partition
        if [ -e /sys/block/mmcblk2boot0/force_ro ]; then
            echo "0" > /sys/block/mmcblk2boot0/force_ro
        fi

        # Call switch script
        /usr/sbin/switch_module.sh 1MW

        # Set correct DTB
        /sbin/fw_setenv fdt_file imx8mm-influx-rex-smart_v2-1mw.dtb

        sync

        echo "Wi-Fi module postinstall setup complete."
        # Do not reboot here!
        # echo "WIFI_SETUP_DONE" > /tmp/.wifi_setup_done
    else
        echo "Postinstall will run on first boot"
    fi
}
