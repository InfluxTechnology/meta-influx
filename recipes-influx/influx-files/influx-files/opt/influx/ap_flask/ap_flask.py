#!/usr/bin/env python3

import os
import time
import logging
from flask import Flask, render_template, request, redirect

# Initialize Flask app
app = Flask(__name__)
app.debug = True

# Access Point Configuration
AP_SSID = "Influx-Rexgen-Smart"
AP_PASSWORD = "12345678"
AP_IP = "192.168.51.1"
LOG_FILE = "/var/log/wifi_monitor.log"

# Configure logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

def log_message(message):
    logging.info(message)

# Configure hostapd for AP mode
def configure_hostapd():
    hostapd_config = f"""
interface=wlan0
driver=nl80211
ssid={AP_SSID}
hw_mode=g
channel=6
auth_algs=1
wpa=2
wpa_passphrase={AP_PASSWORD}
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
"""
    with open("/etc/hostapd.conf", "w") as f:
        f.write(hostapd_config)
    os.system("systemctl unmask hostapd")
    os.system("systemctl enable hostapd")
    log_message("Hostapd configured and enabled.")

# Configure dnsmasq for DHCP and DNS
def configure_dnsmasq():
    dnsmasq_config = f"""
interface=wlan0
dhcp-range=192.168.51.2,192.168.51.20,255.255.255.0,24h
address=/#/{AP_IP}
"""
    with open("/etc/dnsmasq.conf", "w") as f:
        f.write(dnsmasq_config)
    os.system("systemctl restart dnsmasq")
    log_message("Dnsmasq configured and restarted.")

# Start AP mode
def start_ap_mode():
    os.system("systemctl stop wpa_supplicant@wlan0.service")
    os.system("systemctl stop dnsmasq")
    os.system("systemctl stop hostapd")
    configure_hostapd()
    configure_dnsmasq()
    os.system(f"ip addr flush dev wlan0")
    os.system(f"ip addr add {AP_IP}/24 dev wlan0")
    os.system("ip link set wlan0 up")
    os.system("systemctl restart hostapd")
    time.sleep(5)
    os.system("systemctl restart dnsmasq")
    log_message("AP mode started.")

@app.route('/chat', methods=['GET', 'POST'])
def chat_redirect():
    # Handle chat-specific requests and redirect to configuration
    log_message("/chat endpoint accessed.")
    if request.method == 'POST':
        return "Chat endpoint reached. POST method handled.", 200
    return redirect('/')

@app.route('/generate_204')
def android_redirect():
    # Captive portal detection for Android
    return redirect('/')

@app.route('/hotspot-detect.html')
def ios_redirect():
    # Captive portal detection for iOS
    return redirect('/')

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    # Redirect all HTTP requests to the main page
    networks = scan_wifi_networks()
    return render_template("index.html", networks=networks)

@app.route('/configure_wifi', methods=['POST'])
def configure_wifi():
    # Configure Wi-Fi credentials and attempt to connect
    ssid = request.form['ssid']
    password = request.form['password']
    success = configure_wpa_supplicant(ssid, password)
    if success:
        os.system("systemctl restart wpa_supplicant@wlan0.service")
        log_message(f"Connected to Wi-Fi network: {ssid}")
        return f"<html><body><h1>Configuration Successful</h1><p>Connected to {ssid}</p></body></html>"
    else:
        start_ap_mode()
        log_message(f"Failed to connect to Wi-Fi network: {ssid}. Restarting AP mode.")
        return f"<html><body><h1>Configuration Failed</h1><p>Could not connect to {ssid}. Check credentials.</p></body></html>"

# Scan for available Wi-Fi networks
def scan_wifi_networks():
    scan_output = os.popen("iw wlan0 scan 2>/dev/null | grep SSID").read()
    networks = []
    for line in scan_output.splitlines():
        if "SSID" in line:
            try:
                networks.append(line.split(":")[1].strip())
            except IndexError:
                continue
    log_message("Scanned Wi-Fi networks.")
    return networks

# Configure wpa_supplicant and attempt connection
def configure_wpa_supplicant(ssid, password):
    wpa_config = f"""
network={{
    ssid="{ssid}"
    psk="{password}"
}}
"""
    with open('/etc/wpa_supplicant.conf', 'w') as f:
        f.write(wpa_config)
    os.system("systemctl restart wpa_supplicant@wlan0.service")
    time.sleep(10)
    connection_status = os.popen("iw wlan0 link | grep 'Connected to'").read()
    connected = "Connected to" in connection_status
    log_message(f"Attempted to connect to {ssid}. Success: {connected}")
    return connected

# Retrieve the IP address of wlan0
def get_ip_address():
    ip_output = os.popen("ip addr show wlan0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1").read().strip()
    log_message(f"Current IP address: {ip_output}")
    return ip_output if ip_output else "No IP assigned"

if __name__ == "__main__":
    start_ap_mode()
    app.run(host='0.0.0.0', port=80)
