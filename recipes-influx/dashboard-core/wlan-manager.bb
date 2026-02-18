FILESEXTRAPATHS:prepend := "${THISDIR}/netservices:"

SUMMARY = "Manage wifi AP/STA modes"

DESCRIPTION = " Create a virtual wlan1 interface \
    It provides AP mode for initial wifi configuration \
    Available also a dashboard \
    wlan0 is used for STA mode\
"

SRC_URI += "\
        file://dashboard/app.py \
        file://dashboard/__init__.py \
        file://dashboard/templates/ap_settings.html \
        file://dashboard/templates/device_info.html \
        file://dashboard/templates/index.html \
        file://dashboard/templates/manage_networks.html \
        file://dashboard/templates/rexgend_settings.html \
        file://dashboard/templates/settings.html \
        file://dashboard/templates/settings_ap_password.html \
        file://dashboard/templates/settings_device_info.html \
        file://dashboard/templates/settings_rexgend_config.html \
        file://services/__init__.py \
        file://services/ap_clients_config.json \
        file://services/ap_manager.py \
        file://services/client_manager.py \
        file://services/network_scan_config.json \
        file://services/shared_state.py \
        file://services/wifi_manager.py \
        file://scripts/led_blink.sh \
        file://systemd/led-blink.service \
        file://systemd/wifi-dashboard.service \
        file://systemd/wifi-manager.service \
"
#        file://docs/architecture.drawio 

LICENSE = "CLOSED"

S = "${WORKDIR}"

INFLUX_DIR="/opt/influx/"
INFLUX_DIRS = "\
    ${INFLUX_DIR} \
    ${INFLUX_DIR}/netservices/ \
    ${INFLUX_DIR}/netservices/dashboard/ \
    ${INFLUX_DIR}/netservices/dashboard/templates/ \
    ${INFLUX_DIR}/netservices/scripts/ \
    ${INFLUX_DIR}/netservices/services/ \
    /etc/systemd/system/ \
    /usr/lib/systemd/system/ \
    /usr/lib/systemd/system/multi-user.target.wants/ \
"
#    ${INFLUX_DIR}/netservices/docs/ 

INFLUX_FILES = "\
    ${S}/docs/ \
    ${S}/dashboard/ \
    ${S}/dashboard/templates/ \
    ${S}/scripts/ \
    ${S}/services/ \
"

do_install:prepend() {
    for d in ${INFLUX_DIRS}; do
        if [ ! -d ${D}${d} ]; then
            install -m 0755 -d ${D}${d}
        fi
    done
}

do_install () {    
    install -m 0755 ${S}/dashboard/*.py ${D}${INFLUX_DIR}/netservices/dashboard/
    install -m 0755 ${S}/dashboard/templates/*.html ${D}${INFLUX_DIR}/netservices/dashboard/templates/
    install -m 0755 ${S}/scripts/*.sh ${D}${INFLUX_DIR}/netservices/scripts/
    install -m 0755 ${S}/services/*.py ${D}${INFLUX_DIR}/netservices/services/
    install -m 0755 ${S}/services/*.json ${D}${INFLUX_DIR}/netservices/services/
    install -m 0644 ${S}/systemd/*.service ${D}/etc/systemd/system/

    ln -sf /etc/systemd/system/led-blink.service ${D}/usr/lib/systemd/system/multi-user.target.wants/led-blink.service
    ln -sf /etc/systemd/system/wifi-dashboard.service ${D}/usr/lib/systemd/system/multi-user.target.wants/wifi-dashboard.service
    ln -sf /etc/systemd/system/wifi-manager.service ${D}/usr/lib/systemd/system/multi-user.target.wants/wifi-manager.service
}

#    install -m 0755 ${S}/docs/architecture.drawio ${D}${INFLUX_DIR}/netservices/docs/

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
