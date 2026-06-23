FILESEXTRAPATHS:prepend := "${THISDIR}/netservices:"

SUMMARY = "Manage wifi AP/STA modes"

DESCRIPTION = " Create a virtual wlan1 interface \
    It provides AP mode for initial wifi configuration \
    Available also a dashboard \
    wlan0 is used for STA mode\
"
require conf/include/inf-common_${PV}.inc

LICENSE = "CLOSED"

SRC_URI += "\
	file://VERSION \
        file://bin/netservices-dashboard \
        file://bin/netservices-manager \
	file://lib/dashboard/_assets_data.so \
        file://lib/dashboard/_template_loader.so \
        file://lib/dashboard/app.so \
        file://lib/modules/rexgen_live/constants.so \
        file://lib/modules/rexgen_live/router.so \
        file://lib/modules/rexgen_topology/constants.so \
        file://lib/modules/rexgen_topology/router.so \
        file://lib/services/ap_manager.so \
        file://lib/services/client_manager.so \
        file://lib/services/constants_network.so \
        file://lib/services/constants_paths.so \
        file://lib/services/constants_runtime.so \
        file://lib/services/netservices_config.so \
        file://lib/services/shared_state.so \
        file://lib/services/wifi_manager.so \
        file://licensing/closed-source/EULA.txt \
        file://licensing/closed-source/SOURCE_OFFER.txt \
        file://licensing/closed-source/package-manifest-template.csv \
        file://licensing/closed-source/OSS_NOTICES.txt \
        file://licensing/closed-source/THIRD_PARTY_LICENSES.txt \
        file://licensing/open-source/LICENSE-Apache-2.0.txt \
        file://licensing/open-source/LICENSE-BSD-3-Clause.txt \
        file://licensing/open-source/LICENSE-GPL-3.0.txt \
        file://licensing/open-source/LICENSE-MIT.txt \
        file://licensing/open-source/NOTICE-template.txt \
        file://scripts/led_blink.sh \
        file://ssl/ca.crt \
        file://ssl/ca.key \
        file://systemd/led-blink.service \
        file://systemd/wifi-dashboard.service \
        file://systemd/wifi-manager.service \
"

S = "${WORKDIR}"

do_install () {    
    install -m 0644 ${S}/VERSION ${D}${INFLUX_DIR}${NET_SERV_VER}
    install -m 0755 ${S}/bin/* ${D}${INFLUX_DIR}${NET_SERV_VER}/bin/
    install -m 0755 ${S}/lib/dashboard/*.so ${D}${INFLUX_DIR}${NET_SERV_VER}/lib/dashboard/
    install -m 0755 ${S}/lib/modules/rexgen_live/*.so ${D}${INFLUX_DIR}${NET_SERV_VER}/lib/modules/rexgen_live/
    install -m 0755 ${S}/lib/modules/rexgen_topology/*.so ${D}${INFLUX_DIR}${NET_SERV_VER}/lib/modules/rexgen_topology/
    install -m 0755 ${S}/lib/services/*.so ${D}${INFLUX_DIR}${NET_SERV_VER}/lib/services/
    install -m 0644 ${S}/licensing/closed-source/*.txt ${D}${INFLUX_DIR}${NET_SERV_VER}/licensing/closed-source/
    install -m 0644 ${S}/licensing/open-source/*.txt ${D}${INFLUX_DIR}${NET_SERV_VER}/licensing/open-source/
    install -m 0755 ${S}/scripts/*.sh ${D}${INFLUX_DIR}${NET_SERV_VER}/scripts/
    install -m 0644 ${S}/ssl/ca.* ${D}${INFLUX_DIR}${NET_SERV_VER}/ssl
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
