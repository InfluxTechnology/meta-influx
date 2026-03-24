SUMMARY = "Miscellaneous files for the base system"
DESCRIPTION = "The influx-files package adds some files referenced in documentation and includes the WiFi management project, along with the socket application."
SECTION = "base"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://LICENSE;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI += "file://LICENSE \
	file://etc/minirc.dfl \
	file://etc/wvdial.conf \
	file://etc/chatscripts/1nce-new.chat \
	file://etc/firmware/BCM4345C0_003.001.025.0175.0000_Murata_1MW_SXM_TEST_ONLY.hcd \
	file://etc/ppp/peers/1nce.provider \
	file://etc/ppp/peers/quectel-chat-connect \
	file://etc/ppp/peers/quectel-chat-disconnect \
	file://etc/ppp/peers/quectel-ppp \
	file://etc/systemd/network/20-wireless-wlan0.network \
	file://etc/systemd/system/rexgen_sn_to_hostname.service \
	file://etc/systemd/system/autostart.service \
	file://etc/systemd/system/lte-ppp.service \
	file://etc/systemd/system/net-failover.service \
	file://etc/systemd/system/net-failover.timer \
	file://etc/systemd/system/release_check.service \
	file://opt/influx/Release-notes \
	file://opt/influx/autostart.sh \
	file://opt/influx/blt_start.sh \
	file://opt/influx/escape.minicom \
	file://opt/influx/cellular_module_start.sh \
	file://opt/influx/check_taiscale_status.sh \
	file://opt/influx/gnssdata_start.sh \
	file://opt/influx/gnssinit_quectel.py \
	file://opt/influx/gnssinit_ublox.py \
	file://opt/influx/gnss_led_blink.sh \
	file://opt/influx/driver_reconnect.sh \
	file://opt/influx/local_settings.sh \
	file://opt/influx/lte_start_ppp.sh \
	file://opt/influx/lte_start_wvdial.sh \
	file://opt/influx/mender_update_finish.sh \
	file://opt/influx/mender_update_start.sh \
	file://opt/influx/net_failover.sh \
	file://opt/influx/options \
	file://opt/influx/pap-secrets \
	file://opt/influx/pipes_reconnect.sh \
	file://opt/influx/reboot.sh \
	file://opt/influx/start_ppp0.sh \
	file://opt/influx/rexgen_sn_to_hostname.sh \
	file://usr/lib/systemd/system/wpa_supplicant@wlan0.service \
"

S = "${WORKDIR}"

# Add runtime dependencies
RDEPENDS:${PN} = "libusb1 python3 python3-flask python3-pip bash dnsmasq"

REX_USB_DIR="/home/root/rexusb/"
INFLUX_DIR="/opt/influx/"

# Directories to create in the image
INFLUX_DIRS = "\
    ${INFLUX_DIR} \
    ${REX_USB_DIR} \
    /etc/chatscripts/ \
    /etc/firmware/ \
    /etc/mender/scripts/ \
    /etc/ppp/ \
    /etc/ppp/peers/ \
    /etc/profile.d/ \
    /etc/systemd/network/ \
    /etc/systemd/system/ \
    /usr/lib/systemd/system/ \
    /usr/lib/systemd/system/multi-user.target.wants \
"

# Files to install with 755 permissions
INFLUX_FILES_755 = "\
    ${S}/etc/ \
    ${S}/opt/influx/ \
    ${S}/usr/lib/systemd/system/ \
"

# Files to install with 644 permissions
INFLUX_FILES_644 = "\
    Release-notes \
    1nce.provider \
    20-wireless-wlan0.network \
    autostart.service \
    lte-ppp.service \
    minirc.dfl \
    net-failover.service \
    net-failover.timer \
    options \
    pap-secrets \
    peers/quectel-ppp \
    templates/index.html \
    quectel-chat-connect \
    quectel-chat-disconnect \
    wpa_supplicant@wlan0.service \
    wvdial.conf \
"

do_install () {
    # Create necessary directories
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
	
	# default file permisions is 755
	if echo ${SRC_URI} | grep -q ${file}; then
	    install -m 0755 ${S}${fold}${file} ${D}${fold}${file}
	fi

	# check file in 644 permision list
	if echo ${INFLUX_FILES_644} | grep -q ${file}; then
	    chmod 644 ${D}${fold}${file}
	fi
    done

    # Enable services manually
    ln -sf /etc/systemd/system/autostart.service ${D}/usr/lib/systemd/system/multi-user.target.wants/autostart.service
    ln -sf /etc/systemd/system/net-failover.service ${D}/usr/lib/systemd/system/multi-user.target.wants/net-failover.service
    ln -sf /etc/systemd/system/net-failover.timer ${D}/usr/lib/systemd/system/multi-user.target.wants/net-failover.timer
    ln -sf /etc/systemd/system/lte-ppp.service ${D}/usr/lib/systemd/system/multi-user.target.wants/lte-ppp.service
    ln -sf /etc/systemd/system/rexgen_sn_to_hostname.service ${D}/usr/lib/systemd/system/multi-user.target.wants/rexgen_sn_to_hostname.service
}

do_install:append () {
    echo ${INFLUX_RELEASE} > ${D}/etc/hostname
    sed -i 's/\./\_/g' ${D}/etc/hostname

    echo ${INFLUX_RELEASE} > ${D}${INFLUX_DIR}/release
}

# Enable systemd services 
SYSTEMD_AUTO_ENABLE = "enable"
SYSTEMD_SERVICE:${PN} = " \
    autostart.service \
    lte-ppp.service \
    rexgen_sn_to_hostname.service \
"

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
        /sbin/fw_setenv fdt_file boot/imx8mm-influx-rex-smart_v2-1mw.dtb

        sync

        echo "Wi-Fi module postinstall setup complete."
    else
        echo "Postinstall will run on first boot"
    fi
}
