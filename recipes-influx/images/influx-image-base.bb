SUMMARY = "A console-only image that fully supports the target device \
hardware."

IMAGE_FEATURES += "splash ssh-server-openssh"

LICENSE = "MIT"

IMAGE_FEATURES += " \
    ${@bb.utils.contains('DISTRO_FEATURES', 'wayland', 'weston','', d)} \
"

IMAGE_INSTALL = "\
   ${CORE_IMAGE_BASE_INSTALL} \
   i2c-tools-misc \
   i2c-tools \
   pciutils \
   can-utils \
   iproute2 \
   ethtool \
   evtest \
   alsa-utils \
   wget \
   nano \
   gdbserver \
   openssh-sftp-server \
   sqlite3 \
   v4l-utils \
   bluez5 \
   bluez5-noinst-tools \
   bluez5-obex \
   openobex \
   obexftp \
   glibc-gconv-utf-16 \
   glibc-utils \
   iperf3 \
   tslib \
   tslib-tests \
   tslib-calibrate \
   tslib-dev \
   mtdev \
   mmc-utils \
   memtester \
   screen \
   u-boot-fw-utils \
   u-boot-script-inf \
   libgpiod \
   libgpiod-tools \
   firmwared \
   python3-pip \
   python3 \
   python3-dev\
   auditd \
   hostapd \
   murata-binaries \
   cyw-supplicant \
   cyw-hostapd \
   hostap-conf \
   hostap-utils \
   kernel-module-nxp-wlan \
   linux-firmware \
   backporttool-linux \
    uhubctl \
    influx-files \
    rexgen-stream \
    rexgen-usb \
"

#IMAGE_INSTALL:append:imx8mn-influx-rex-smart = "\
#   inf-resizefs \
#"

inherit core-image

# User/Group modifications"
# - Adding user 'tester' without password"
# - Setting password for user 'root' to 'pass'"
# - For more options see extrausers.bbclass"
inherit extrausers

# Password is set to 'pass'. Encrypted using mkpasswd with seed 'qwerty123456'.
# NOTE: Special characters such as '$' must be escaped
#
# mkpasswd -m sha-512 pass -s "qwerty123456"

PASSWD = '\$6\$qwerty123456\$FbXWy3i5PyuYYvNR.X1c4BbJ8zTcVEv7i9Di9erLRDTiIBiswLSnGo7iXBrhZPBNUh/TyLJ.RVbDiUFxWgmbX.'
EXTRA_USERS_PARAMS = " \
  useradd -p '' tester; \
  usermod -s /bin/sh tester; \
  usermod -p '${PASSWD}' root; \
"
