FILESEXTRAPATHS:prepend := "${THISDIR}/netservices-lite:"

SUMMARY = "Manage wifi AP/STA modes"

DESCRIPTION = " Create a virtual wlan1 interface \
    It provides AP mode for initial wifi configuration \
    Available also a dashboard \
    wlan0 is used for STA mode\
"

require conf/include/inf-common.inc

LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${INF_INC_DIR}/LICENSE-MIT;md5=d4b228eee080114fd16f597b56fc395c"

SRC_URI += "\
        file://dashboard/app.py \
        file://dashboard/__init__.py \
	file://dashboard/templates_main/_footer.html \
        file://dashboard/templates_main/_topnav.html \
        file://dashboard/templates_main/manage_networks.html \
        file://dashboard/templates_main/wifi_network_info.html \
        file://dashboard/templates_main/wifi_settings.html \
	file://scripts/led_blink.sh \
        file://services/__init__.py \
        file://services/ap_clients_config.json \
        file://services/ap_manager.py \
        file://services/client_manager.py \
        file://services/constants_network.py \
        file://services/constants_paths.py \
        file://services/constants_runtime.py \
        file://services/netservices_config.py \
        file://services/network_scan_config.json \
        file://services/shared_state.py \
        file://services/wifi_manager.py \
	file://systemd/led-blink.service \
        file://systemd/wifi-dashboard.service \
        file://systemd/wifi-manager.service \
"
#SRC_URI -= "\
#	file://scripts/pack.sh 
#"

S = "${WORKDIR}"

do_install () {    
    install -m 0755 ${S}/dashboard/*.py ${D}${INFLUX_DIR}${NET_SERV_VER}/dashboard/
    install -m 0755 ${S}/dashboard/templates_main/*.html ${D}${INFLUX_DIR}${NET_SERV_VER}/dashboard/templates_main/
    install -m 0755 ${S}/scripts/*.sh ${D}${INFLUX_DIR}${NET_SERV_VER}/scripts/
    install -m 0755 ${S}/services/*.py ${D}${INFLUX_DIR}${NET_SERV_VER}/services/
    install -m 0755 ${S}/services/*.json ${D}${INFLUX_DIR}${NET_SERV_VER}/services/
    install -m 0644 ${S}/systemd/*.service ${D}/etc/systemd/system/

    ln -sf /etc/systemd/system/led-blink.service ${D}/usr/lib/systemd/system/multi-user.target.wants/led-blink.service
    ln -sf /etc/systemd/system/wifi-dashboard.service ${D}/usr/lib/systemd/system/multi-user.target.wants/wifi-dashboard.service
    ln -sf /etc/systemd/system/wifi-manager.service ${D}/usr/lib/systemd/system/multi-user.target.wants/wifi-manager.service
}

SYSTEMD_AUTO_ENABLE = "enable"
SYSTEMD_SERVICE:${PN} = "\
    led-blink.service \
    wifi-dashboard.service \
    wifi-manager.service \
"

INHIBIT_PACKAGE_STRIP = "1"
INHIBIT_PACKAGE_DEBUG_SPLIT = "1"

PACKAGES = "${PN}"
FILES:${PN} = "/"
