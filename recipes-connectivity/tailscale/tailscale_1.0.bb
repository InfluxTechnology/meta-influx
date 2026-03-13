SUMMARY = "Tailscale"
DESCRIPTION = "Tailscale is a secure VPN based on WireGuard."

LICENSE = "CLOSED"

SRC_URI = " \
    file://tailscale \
    file://tailscaled \
    file://tailscaled.defaults \
    file://tailscaled.service \
"

S = "${WORKDIR}"

INFLUX_DIRS = "\
    /usr/sbin/ \
    /etc/default/ \
    /etc/systemd/system/ \
    /etc/systemd/system/multi-user.target.wants \
"

do_install:prepend() {
    for d in ${INFLUX_DIRS}; do
        if [ ! -d ${D}${d} ]; then
            install -m 0755 -d ${D}${d}
        fi
    done
}

do_install() {
    install -m 0755 ${S}/tailscale ${D}/usr/sbin/
    install -m 0755 ${S}/tailscaled ${D}/usr/sbin/
    install -m 0644 ${S}/tailscaled.defaults ${D}/etc/default/tailscaled
    install -m 0644 ${S}/tailscaled.service ${D}/etc/systemd/system/

#    ln -sf /etc/systemd/system/tailscaled.service ${D}/etc/systemd/system/multi-user.target.wants/tailscaled.service
}

#SYSTEMD_AUTO_ENABLE = "enable"
#SYSTEMD_SERVICE:${PN} = "tailscaled.service"

INHIBIT_PACKAGE_STRIP = "1"
INHIBIT_PACKAGE_DEBUG_SPLIT = "1"

PACKAGES = "${PN}"
FILES:${PN} = "/"
