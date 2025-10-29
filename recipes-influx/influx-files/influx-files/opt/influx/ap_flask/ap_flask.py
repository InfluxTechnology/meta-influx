#!/usr/bin/env python3

import os
import time
import logging
import subprocess
import re
import threading
from flask import Flask, render_template, request, redirect, jsonify, make_response, url_for
import sys

# Initialize Flask app
app = Flask(__name__)
#app.debug = True

# Log file path
LOG_FILE = "/var/log/wifi_monitor.log"

# Configure logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

last_heartbeat = 0
networks = []
heartbeat_lock = threading.Lock()
ap_mode_lock = threading.Lock()
scan_network_lock = threading.Lock()


def log_message(message):
    logging.info(message)

# Function to retrieve and clean the serial number from a file
def get_serial_number():
    serial_file = "/home/root/rexusb/var/serial"
    try:
        if os.path.exists(serial_file):
            with open(serial_file, "r") as f:
                serial_number = f.read().strip()  # Read and remove any whitespace/newlines
                serial_number = "".join(filter(str.isprintable, serial_number))  # Remove non-printable characters
                return serial_number
        else:
            log_message(f"Serial number file not found: {serial_file}")
            return "UNKNOWN_SN"
    except Exception as e:
        log_message(f"Error retrieving serial number: {e}")
        return "UNKNOWN_SN"

# Generate AP SSID dynamically
SERIAL_NUMBER = get_serial_number()
AP_SSID = f"INF-{SERIAL_NUMBER}"

# Log the generated SSID
log_message(f"Generated AP SSID: {AP_SSID}")

AP_PASSWORD = "12345678"
AP_IP = "192.168.51.1"

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
    with ap_mode_lock:
        with open('/sys/class/leds/JA35/brightness', 'w') as f:
            f.write('0')
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

def is_wifi_connected():
    try:
        # Run iwconfig command to get WiFi status
        result = subprocess.check_output(["iwconfig"], stderr=subprocess.STDOUT).decode("utf-8")
        # Check if the output contains an SSID (indicating a connection)
        return "ESSID" in result and "Access Point" in result and "Not-Associated" not in result
    except subprocess.CalledProcessError:
        return False

# Check for known networks and attempt connection
def check_and_connect_known_networks():
    # Read known networks from wpa_supplicant.conf
    try:
        if is_user_connected_to_ap():
            log_message("User connected to AP")
            return False
        if is_wifi_connected():
            log_message("WiFi is connected")
            return True        
        with open('/etc/wpa_supplicant.conf', 'r') as f:
            config = f.read()
        # Extract SSIDs using regex
        known_ssids = re.findall(r'ssid="([^"]+)"', config)
        if not known_ssids:
            log_message("No known networks found in wpa_supplicant.conf")
            return False
    except Exception as e:
        log_message(f"Error reading wpa_supplicant.conf: {e}")
        return False

    # Scan for available networks
    log_message("Scan for wifi 1")
    available_networks = scan_wifi_networks()
    # Check if any known SSID is in range    
    for ssid in known_ssids:
        if ssid in available_networks:
            log_message(f"Known network in range: {ssid}")
            # Stop AP mode services
            os.system("systemctl stop hostapd")
            os.system("systemctl stop dnsmasq")
            os.system(f"ip addr flush dev wlan0")
            # Attempt to connect
            os.system("systemctl restart wpa_supplicant@wlan0.service")
            time.sleep(10)
            connection_status = os.popen("iw wlan0 link | grep 'Connected to'").read()
            if "Connected to" in connection_status:
                with open('/sys/class/leds/JA35/brightness', 'w') as f:
                    f.write('1')
                log_message(f"Successfully connected to known network: {ssid}")
                return True
            else:
                log_message(f"Failed to connect to known network: {ssid}")#   Attempt: {attempt_counter}")
                # Restart AP mode if connection fails                    
    return False

@app.route('/heartbeat', methods=['POST'])
def heartbeat():
    global last_heartbeat
    with heartbeat_lock:
        last_heartbeat = time.monotonic()
    log_message("Heartbeat received")
    return jsonify({"status": "ok"})


#Check if a user is connected to AP
def is_user_connected_to_ap():
    global last_heartbeat
    with heartbeat_lock:
        if last_heartbeat == 0:
            last_heartbeat = time.monotonic()
        now = time.monotonic()
        time_diff = now - last_heartbeat
        log_message(f"is_user_connected_to_ap: now={now}, last_heartbeat={last_heartbeat}, diff={time_diff}")
    if time_diff <= 30:
        log_message("Heartbeat is fresh. Client is connected.")
        return True
    else:
        log_message("No recent heartbeat. No client connected.")
        return False


# Background thread to periodically check for known networks
def periodic_network_check(interval=30):
    while True: 
        log_message("periodic_network_check STARTED")
        if is_user_connected_to_ap():
            log_message("AP is in use. Skip network check")
            time.sleep(10)
            continue
        log_message("Checking for known networks...")
        if check_and_connect_known_networks():
            log_message("Connected to a known network")
        else:
            start_ap_mode()            
            #attempt_counter = 1            
            #while check_and_connect_known_networks() == False:                
               # time.sleep(5)
                #log_message(f"Attempt to connect {attempt_counter}")
                #if attempt_counter == 3:                 
                    #start_ap_mode()
                    #break
                #attempt_counter += 1   
            #os._exit(0)  # Exit the entire script
        time.sleep(interval)

@app.route('/chat', methods=['GET', 'POST'])
def chat_redirect():
    log_message("/chat endpoint accessed.")
    if request.method == 'POST':
        return "Chat endpoint reached. POST method handled.", 200
    return redirect('/')

@app.route('/generate_204')
def android_redirect():
    return redirect('/')

@app.route('/hotspot-detect.html')
def ios_redirect():
    return redirect('/')

#@app.route('/', defaults={'path': ''})
#@app.route('/<path:path>')
#def catch_all(path):
#    #networks = scan_wifi_networks()
#    global networks
#    return render_template("index.html", networks=networks)


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    global networks

    if request.cookies.get("first_visit_done"):
        log_message("Page refresh detected – rescanning networks.")
        scan_wifi_networks()
    else:
        log_message("First page load – using existing networks list.")

    # Session cookie: no expiration = deleted on browser close
    response = make_response(render_template("index.html", networks=networks))
    response.set_cookie("first_visit_done", "1")  # session cookie
    return response

@app.route('/configure_wifi', methods=['POST'])
def configure_wifi():
    ssid = request.form['ssid']
    password = request.form['password']
    success = configure_wpa_supplicant(ssid, password)
    if success:
        log_message(f"Connected to Wi-Fi network: {ssid}")
        with open('/sys/class/leds/JA35/brightness', 'w') as f:
            f.write('1')
        time.sleep(5)  # Wait for IP to be assigned

        device_ip = get_ip_address()
        if device_ip and device_ip != "No IP assigned":
            return redirect(f"http://{device_ip}:5051/dashboard")

        return f"<html><body><h1>Configuration Successful</h1><p>Connected to {ssid}, but no IP found.</p></body></html>"
        
        os._exit(0)  # Optional: Exit after redirect
    else:
        start_ap_mode()
        log_message(f"Failed to connect to Wi-Fi network: {ssid}. Restarting AP mode.")
        return f"<html><body><h1>Configuration Failed</h1><p>Could not connect to {ssid}. Check credentials.</p></body></html>"


# Scan for available Wi-Fi networks
def scan_wifi_networks():
    with scan_network_lock:
        scan_output = ""
        while not scan_output.strip():
            scan_output = os.popen("iw wlan0 scan 2>/dev/null | grep SSID").read()
            print("No SSIDs found. Retrying...")
        global networks
        networks = []
        for line in scan_output.splitlines():
            if "SSID" in line:
                try:
                    networks.append(line.split(":")[1].strip())
                except IndexError:
                    continue
    log_message(f"Scanned Wi-Fi networks: {networks}")
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
    time.sleep(15)
    connection_status = os.popen("iw wlan0 link | grep 'Connected to'").read()    
    connected = "Connected to" in connection_status
    if connected: 
        with open('/sys/class/leds/JA35/brightness', 'w') as f:
            f.write('1')
    else:
        with open('/sys/class/leds/JA35/brightness', 'w') as f:
            f.write('0')
    log_message(f"Attempted to connect to {ssid}. Success: {connected}")
    return connected

# Retrieve the IP address of wlan0
def get_ip_address():
    ip_output = os.popen("ip addr show wlan0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1").read().strip()
    log_message(f"Current IP address: {ip_output}")
    return ip_output if ip_output else "No IP assigned"

if __name__ == "__main__":
    while True: 
        # Check for known networks first
        if check_and_connect_known_networks():
            log_message("Connected to a known network")
        # Start periodic network check in background thread
        network_check_thread = threading.Thread(target=periodic_network_check, args=(30,), daemon=True)
        network_check_thread.start()
        # Start AP mode
        #if check_and_connect_known_networks() == False:
           # start_ap_mode()
        app.run(host='0.0.0.0', port=80)