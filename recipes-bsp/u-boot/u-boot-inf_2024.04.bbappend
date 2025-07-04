FILESEXTRAPATHS:prepend := "${THISDIR}/${PN}:"

№SRC_URI += " file://autoboot_Not_stop.patch "
№SRC_URI += " file://mx8mm-influx-rex-smart.patch "

# Automatic start mrproper before build
№do_compile[nostamp] = "1"

№do_compile:prepend() {
№    bbnote "Running mrproper to clean U-Boot tree..."
№    oe_runmake mrproper || true
№}
