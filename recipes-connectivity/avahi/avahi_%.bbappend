FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

SRC_URI += " \
    file://avahi-daemon.conf \
    file://http.service \
    file://rexgenpro.service \
"

do_install:append () {
    install -m 0644 ${WORKDIR}/avahi-daemon.conf ${D}/etc/avahi/
    install -m 0644 ${WORKDIR}/*.service ${D}/etc/avahi/services/

    sed -i "s/\*\*\*\*/${INFLUX_VERSION}/g" ${D}/etc/avahi/services/rexgenpro.service
}
