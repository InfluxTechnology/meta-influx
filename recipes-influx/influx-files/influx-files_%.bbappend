FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

do_install:append () {
    echo ${INFLUX_RELEASE} > ${D}/etc/hostname
    sed -i 's/\./\_/g' ${D}/etc/hostname
}

