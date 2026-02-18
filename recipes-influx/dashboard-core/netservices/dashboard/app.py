#!/usr/bin/env python3
"""
WiFi Dashboard Service - Lightweight version
"""

import os
import sys
import logging
import time

# Minimal imports for lower memory
from flask import Flask, render_template, request, redirect, jsonify, make_response

# Add services to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))
from shared_state import wifi_state

# ========== Configuration ==========

LOG_FILE = "/var/log/wifi_dashboard.log"
DASHBOARD_PORT = 80
CONNECT_LOCK_TIMEOUT_SECONDS = 90

# Setup logging - minimal
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(message)s"
)
log = logging.getLogger(__name__)
TRACE_VERBOSE = os.environ.get("REXGEN_TRACE_VERBOSE", "1") == "1"

# Flask app - minimal config
app = Flask(__name__, template_folder='templates')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['TEMPLATES_AUTO_RELOAD'] = True


def _trace(msg: str):
    if TRACE_VERBOSE:
        log.info(f"[TRACE][DASH] {msg}")


def busy_connect_response():
    target = wifi_state.get("connect_target")
    if target:
        return jsonify({"error": f"Connection to '{target}' is in progress. Please wait."}), 409
    return jsonify({"error": "A connection attempt is in progress. Please wait."}), 409


# ========== Validation ==========

def validate_wifi_input(ssid: str, password: str) -> tuple:
    """
    Validate WiFi credentials. Returns (is_valid, error_message)
    Empty password = open network (allowed)
    WPA password must be 8-63 characters
    """
    if not ssid:
        return False, "SSID is required"
    if len(ssid) > 32:
        return False, "SSID too long (max 32 characters)"
    # Empty password = open network (allowed)
    if password and len(password) < 8:
        return False, f"Password too short ({len(password)} chars, WPA requires min 8)"
    if password and len(password) > 63:
        return False, f"Password too long ({len(password)} chars, max 63)"
    return True, None


# ========== API Endpoints ==========

@app.route('/heartbeat', methods=['POST'])
def heartbeat():
    _trace(f"POST /heartbeat from={request.remote_addr}")
    wifi_state.heartbeat()
    return '{"status":"ok"}', 200, {'Content-Type': 'application/json'}


@app.route('/api/status')
def api_status():
    _trace(f"GET /api/status from={request.remote_addr}")
    wifi_state.heartbeat()
    state = wifi_state.get_all()
    if state.get("connect_in_progress", False):
        started = state.get("connect_started_at", 0)
        if started and (time.time() - started) > CONNECT_LOCK_TIMEOUT_SECONDS:
            wifi_state.update({
                "connect_in_progress": False,
                "connect_target": None,
                "connect_error": "Connection attempt timed out (watchdog). Please retry.",
                "connect_finished_at": time.time()
            })
            state = wifi_state.get_all()
            _trace("api_status watchdog cleared stale connect lock")
    _trace(
        f"api_status payload connected_ssid={state.get('connected_ssid')} "
        f"connect_in_progress={state.get('connect_in_progress', False)} "
        f"ap_clients={len(state.get('ap_clients', []))}"
    )
    return jsonify({
        "networks": state.get("networks", []),
        "known": state.get("known_networks", []),
        "connected_ssid": state.get("connected_ssid"),
        "ap_mode": state.get("ap_mode", False),
        "client_ip": state.get("client_ip"),
        "client_mac": state.get("client_mac"),
        "serial_number": state.get("serial_number"),
        "connect_error": state.get("connect_error"),
        "connect_in_progress": state.get("connect_in_progress", False),
        "connect_target": state.get("connect_target"),
        "connect_trace_id": state.get("connect_trace_id"),
        "connect_started_at": state.get("connect_started_at"),
        "connect_finished_at": state.get("connect_finished_at"),
        "last_scan": state.get("last_scan", 0),
        "ap_clients": state.get("ap_clients", []),
        "ap_blocked": state.get("ap_blocked", {}),
        "requester_ip": request.remote_addr
    })


@app.route('/api/networks')
def api_networks():
    return jsonify({
        "networks": wifi_state.get("networks", []),
        "known": wifi_state.get("known_networks", [])
    })


@app.route('/api/saved-networks', methods=['GET'])
def api_saved_networks():
    return jsonify({
        "saved_networks": wifi_state.get("known_networks", []),
        "connected_ssid": wifi_state.get("connected_ssid"),
        "saved_network_error": wifi_state.get("saved_network_error"),
        "saved_network_last_action": wifi_state.get("saved_network_last_action")
    })


@app.route('/api/saved-networks', methods=['POST'])
def api_saved_networks_add():
    if wifi_state.get("connect_in_progress", False):
        return busy_connect_response()

    data = request.get_json() or {}
    ssid = (data.get('ssid') or '').strip()
    password = data.get('password') or ''

    valid, error = validate_wifi_input(ssid, password)
    if not valid:
        return jsonify({"error": error}), 400

    wifi_state.request_saved_network_add(ssid, password)
    return jsonify({"status": "requested"}), 202


@app.route('/api/saved-networks/delete', methods=['POST'])
def api_saved_networks_delete():
    if wifi_state.get("connect_in_progress", False):
        return busy_connect_response()

    data = request.get_json() or {}
    ssid = (data.get('ssid') or '').strip()
    if not ssid:
        return jsonify({"error": "SSID is required"}), 400

    wifi_state.request_saved_network_delete(ssid)
    return jsonify({"status": "requested"}), 202


@app.route('/api/scan', methods=['POST'])
def api_scan():
    _trace(f"POST /api/scan from={request.remote_addr}")
    wifi_state.heartbeat()
    if wifi_state.get("connect_in_progress", False):
        return busy_connect_response()
    wifi_state.request_scan()
    return '{"status":"requested"}', 200, {'Content-Type': 'application/json'}


import re
_MAC_RE = re.compile(r'^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$')


@app.route('/api/ap-clients')
def api_ap_clients():
    _trace(f"GET /api/ap-clients from={request.remote_addr}")
    wifi_state.heartbeat()
    before = wifi_state.get("ap_clients_updated_at", 0)
    _trace(f"api_ap_clients before_updated_at={before}")
    wifi_state.request_ap_clients_refresh()
    # Give wifi-manager a short window to process the refresh request.
    for _ in range(15):
        after = wifi_state.get("ap_clients_updated_at", 0)
        if after and after > before:
            break
        time.sleep(0.1)
    clients = wifi_state.get("ap_clients", [])
    blocked = wifi_state.get("ap_blocked", {})
    _trace(
        f"api_ap_clients after_updated_at={wifi_state.get('ap_clients_updated_at', 0)} "
        f"clients={len(clients)} blocked={len(blocked)}"
    )
    return jsonify({
        "clients": clients,
        "blocked": blocked
    })


@app.route('/api/ap-clients/block', methods=['POST'])
def api_ap_block():
    _trace(f"POST /api/ap-clients/block from={request.remote_addr}")
    if wifi_state.get("connect_in_progress", False):
        return busy_connect_response()

    data = request.get_json() or {}
    mac = (data.get('mac') or '').strip().lower()
    if not mac or not _MAC_RE.match(mac):
        return jsonify({"error": "Valid MAC address required"}), 400
    _trace(f"api_ap_block mac={mac}")
    wifi_state.request_block_client(mac)
    wifi_state.request_ap_clients_refresh()
    return jsonify({"status": "requested"}), 202


@app.route('/api/ap-clients/unblock', methods=['POST'])
def api_ap_unblock():
    _trace(f"POST /api/ap-clients/unblock from={request.remote_addr}")
    if wifi_state.get("connect_in_progress", False):
        return busy_connect_response()

    data = request.get_json() or {}
    mac = (data.get('mac') or '').strip().lower()
    if not mac or not _MAC_RE.match(mac):
        return jsonify({"error": "Valid MAC address required"}), 400
    _trace(f"api_ap_unblock mac={mac}")
    wifi_state.request_unblock_client(mac)
    wifi_state.request_ap_clients_refresh()
    return jsonify({"status": "requested"}), 202


@app.route('/api/connect', methods=['POST'])
def api_connect():
    """Non-blocking connect request with validation"""
    data = request.get_json() or {}
    ssid = data.get('ssid') or request.form.get('ssid', '')
    password = data.get('password') or request.form.get('password', '')
    use_saved = data.get('use_saved', False)
    _trace(
        f"POST /api/connect from={request.remote_addr} ssid='{ssid}' "
        f"use_saved={use_saved} password_len={len(password or '')}"
    )

    # Validate input (skip password validation if using saved)
    if not use_saved:
        valid, error = validate_wifi_input(ssid, password)
        if not valid:
            return jsonify({"error": error}), 400
    else:
        # Still validate SSID
        if not ssid:
            return jsonify({"error": "SSID is required"}), 400

    # Reject parallel connection attempts from multiple clients/devices.
    # One attempt at a time keeps wlan0/wlan1 behavior predictable.
    # Auto-expire stale locks after 60s (e.g. service restart mid-connect).
    if wifi_state.get("connect_in_progress", False):
        started = wifi_state.get("connect_started_at", 0)
        if started and (time.time() - started) > 60:
            wifi_state.update({"connect_in_progress": False, "connect_target": None})
            _trace("api_connect cleared stale lock >60s before accepting new request")
        else:
            target = wifi_state.get("connect_target")
            _trace(f"api_connect rejected due active lock target='{target}'")
            if target:
                return jsonify({"error": f"Already connecting to '{target}'. Please wait."}), 409
            return jsonify({"error": "Another connection attempt is already in progress. Please wait."}), 409

    # Lock immediately at API acceptance time to prevent rapid double-click races
    # before wifi-manager picks up the request.
    wifi_state.update({
        "connect_in_progress": True,
        "connect_target": ssid,
        "connect_started_at": time.time(),
        "connect_error": None
    })
    wifi_state.request_connect(ssid, password, use_saved)
    _trace(f"api_connect accepted ssid='{ssid}'")
    return '{"status":"connecting"}', 200, {'Content-Type': 'application/json'}


# ========== Web Pages ==========

@app.route('/')
def index():
    networks = wifi_state.get("networks", [])
    return render_template("index.html", networks=networks)


@app.route('/saved-networks')
def saved_networks_page():
    return render_template("manage_networks.html")


@app.route('/configure_wifi', methods=['POST'])
def configure_wifi():
    ssid = request.form.get('ssid', '').strip()
    password = request.form.get('password', '')

    # Validate input
    valid, error = validate_wifi_input(ssid, password)
    if not valid:
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Error</title>
    <style>
        body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
        .error {{ color: #dc3545; font-size: 18px; margin: 20px 0; }}
    </style>
</head>
<body>
    <h1>Invalid Input</h1>
    <p class="error">{error}</p>
    <p><a href="/">Go back</a></p>
</body>
</html>""", 400

    # Non-blocking - just send request
    wifi_state.request_connect(ssid, password)

    # Return immediately with status page
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Connecting...</title>
    <style>
        body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
        .spinner {{ border: 4px solid #f3f3f3; border-top: 4px solid #667eea;
                   border-radius: 50%; width: 40px; height: 40px;
                   animation: spin 1s linear infinite; margin: 20px auto; }}
        @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
    </style>
</head>
<body>
    <h1>Connecting to {ssid}...</h1>
    <div class="spinner"></div>
    <p id="status">Please wait...</p>
    <script>
        let checks = 0;
        const maxChecks = 20;

        function checkStatus() {{
            fetch('/api/status')
                .then(r => r.json())
                .then(data => {{
                    // Check connected FIRST (success takes priority over stale errors)
                    if (data.connected_ssid === '{ssid}') {{
                        document.getElementById('status').innerHTML =
                            '<b style="color:#28a745">Connected!</b><br>IP: ' + (data.client_ip || 'acquiring...');
                        document.querySelector('.spinner').style.display = 'none';
                        // Stay on port 80 in AP mode; no redirect to 5080
                    }} else if (data.connect_error) {{
                        document.getElementById('status').innerHTML =
                            '<span style="color:#dc3545"><b>Error:</b> ' + data.connect_error + '</span><br><a href="/">Try again</a>';
                        document.querySelector('.spinner').style.display = 'none';
                    }} else if (++checks >= maxChecks) {{
                        document.getElementById('status').innerHTML =
                            '<span style="color:#dc3545">Connection timeout.</span> <a href="/">Try again</a>';
                        document.querySelector('.spinner').style.display = 'none';
                    }} else {{
                        setTimeout(checkStatus, 1000);
                    }}
                }})
                .catch(() => setTimeout(checkStatus, 1000));
        }}
        setTimeout(checkStatus, 2000);
    </script>
</body>
</html>"""


# ========== Captive Portal Detection ==========

# Android connectivity check
@app.route('/generate_204')
@app.route('/gen_204')
def android_captive():
    # Return 302 redirect to trigger "Sign in to network" popup
    return redirect('http://192.168.51.1/', code=302)

# iOS/Apple connectivity check
@app.route('/hotspot-detect.html')
@app.route('/library/test/success.html')
def ios_captive():
    # iOS expects "Success" text - returning anything else triggers captive portal
    return redirect('http://192.168.51.1/', code=302)

# Windows connectivity check
@app.route('/ncsi.txt')
@app.route('/connecttest.txt')
def windows_captive():
    return redirect('http://192.168.51.1/', code=302)

# General captive portal
@app.route('/chat', methods=['GET', 'POST'])
def captive_redirect():
    return redirect('http://192.168.51.1/', code=302)


@app.route('/<path:path>')
def catch_all(path):
    return redirect('http://192.168.51.1/', code=302)


@app.errorhandler(404)
def not_found(e):
    return redirect('http://192.168.51.1/', code=302)


# ========== Main ==========

if __name__ == "__main__":
    # Use threaded server to prevent one slow request from blocking the whole dashboard.
    app.run(host='0.0.0.0', port=DASHBOARD_PORT, threaded=True, debug=False)
