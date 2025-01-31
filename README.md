Yocto BSP layer for Influx Technology ARM platforms
==================================================

This meta-layer including AP. WiFi access point which make wifi connection configuration. 

# Project Summary

This project enables an embedded Linux device to act as a configurable Wi-Fi access point (AP). The solution uses Flask to create a captive portal for configuring and managing Wi-Fi connections. It includes two key components:

    ap_flask.py (Flask app for the captive portal)
    wifi_monitor.sh (script to manage Wi-Fi connections and AP mode)

The project is optimized for systems where commands like pkill, pgrep, and certain system tools might be unavailable. The workflow ensures that the AP mode is automatically enabled when no valid network connection exists and stops AP mode once the device successfully connects to a saved Wi-Fi network.

# Logic Description
1. ap_flask.py

    Purpose:
    Provides a captive portal for configuring Wi-Fi settings.
    Core Functionality:
        Starts AP mode on device boot when invoked.
        Hosts a captive portal accessible on http://192.168.51.1.
        Detects Android (/generate_204) and iOS (/hotspot-detect.html) devices for captive portal auto-prompting.
        Provides a form where users can input Wi-Fi credentials.
        Writes the Wi-Fi credentials to /etc/wpa_supplicant.conf.
        Logs all operations to /var/log/wifi_monitor.log.
        If a connection attempt fails, AP mode restarts.

Key Endpoints:

    /generate_204: For Android captive portal detection.
    /hotspot-detect.html: For iOS captive portal detection.
    /configure_wifi: Handles Wi-Fi configuration.
    /: Renders a webpage to scan and display available networks.

2. wifi_monitor.sh

    Purpose:
    Continuously monitors the device’s Wi-Fi connection status and manages the transition between normal Wi-Fi mode and AP mode.
    Core Logic:
        The script runs in an infinite loop.
        It checks if wlan0 is connected to a network.
        If not connected, it attempts up to 3 times to reconnect to a saved Wi-Fi network.
        If all connection attempts fail, it starts the AP Flask mode.
        If AP Flask mode is active and a previously saved network becomes available, it stops the AP mode and reconnects.
        Logs connection attempts and AP mode activity to /var/log/wifi_monitor.log.


# Embedded Device Wi-Fi Configuration with Captive Portal

This project provides a solution for managing Wi-Fi connections on embedded Linux devices by using a captive portal for network configuration.

## **Features**
- Captive portal for easy Wi-Fi configuration.
- Automatically switches between Access Point (AP) mode and client mode.
- Supports Android and iOS captive portal detection.
- Logs all activity to `/var/log/wifi_monitor.log`.

---

## **Installation**

### **Dependencies**
- Python 3
- Flask (`pip3 install flask`)
- System services: `hostapd`, `dnsmasq`, `wpa_supplicant`
- Linux commands: `iw`, `systemctl`

### **Files**
- `ap_flask.py`: Flask application to handle AP and captive portal.
- `wifi_monitor.sh`: Monitors Wi-Fi connection and manages AP mode.

---

## **Setup**

1. **Configure Services**
   - Ensure `hostapd`, `dnsmasq`, and `wpa_supplicant` are installed and enabled on your device.

2. **DNSMasq Configuration**
   Add the following to `/etc/dnsmasq.conf`:
   ```conf
   interface=wlan0
   dhcp-range=192.168.51.2,192.168.51.20,255.255.255.0,24h
   address=/#/192.168.51.1

    Hostapd Configuration The ap_flask.py script will generate a dynamic /etc/hostapd.conf.

    Systemd Service Setup (Optional) Create a service file /etc/systemd/system/wifi_monitor.service:



Enable and start the service:

    systemctl enable wifi_monitor
    systemctl start wifi_monitor

## Usage

    Boot Behavior
        On device boot, wifi_monitor.sh runs and checks for a valid Wi-Fi connection.
        If no connection is detected, the device enters AP mode.
        The captive portal page is hosted at http://192.168.51.1.

    Accessing the Portal
        Connect to the Wi-Fi network named Influx-Rexgen-Smart.
        Open any browser; captive portal redirection should trigger automatically on most devices.
        Enter your Wi-Fi credentials on the portal page.

    Logs
        Check /var/log/wifi_monitor.log for detailed logs of Wi-Fi and AP mode activity.

## Troubleshooting

    Captive Portal Not Triggering
        Ensure /generate_204 and /hotspot-detect.html endpoints are accessible.
        Confirm DNS redirection is correctly configured in /etc/dnsmasq.conf.

    AP Mode Not Starting
        Check that hostapd and dnsmasq services are properly configured and running.
        Review the log file for errors: /var/log/wifi_monitor.log.

    Python Errors
        Ensure Flask is installed: pip3 install flask.
