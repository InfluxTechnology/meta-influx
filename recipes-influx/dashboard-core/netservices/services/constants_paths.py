#!/usr/bin/env python3
"""Shared filesystem paths for netservices modules."""

REXGEN_DATA_DIR = "/data/rexgen"
REXGEN_CONFIG_DIR = f"{REXGEN_DATA_DIR}/config"
REXGEN_TMP_DIR = f"{REXGEN_DATA_DIR}/tmp"

WIFI_STATE_FILE = f"{REXGEN_TMP_DIR}/wifi_state.json"
NETSERVICES_CONFIG_FILE = f"{REXGEN_CONFIG_DIR}/netservices.conf"
REXGEND_CONFIG_FILE = f"{REXGEN_CONFIG_DIR}/rexgend.conf"

SERIAL_FILE = "/home/root/rexusb/var/serial"
LED_PATH = "/sys/class/leds/JA35/brightness"
MENDER_ARTIFACT_INFO_FILE = "/etc/mender/artifact_info"

HOSTAPD_CONF = "/etc/hostapd.conf"
DNSMASQ_CONF = "/etc/dnsmasq.d/rexgen-ap.conf"
HOSTAPD_CTRL_DIR = "/var/run/hostapd"
AP_BLOCKED_FILE = f"{REXGEN_TMP_DIR}/ap_blocked.json"
DHCP_LEASES_FILE = "/var/lib/misc/dnsmasq.leases"

WPA_CONFIG = "/etc/wpa_supplicant.conf"
WPA_SOCKET_DIR = "/var/run/wpa_supplicant"
RESOLV_CONF = "/etc/resolv.conf"
