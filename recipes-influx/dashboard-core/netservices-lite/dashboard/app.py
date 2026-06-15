#!/usr/bin/env python3
"""
WiFi Dashboard Service - Lite version (no auth)

Only exposes the Wi-Fi tab: scan, saved networks, connect.
No login. No device-info, AP, rexgend, system, mender, vpn, terminal, modules.
"""

import ipaddress
import logging
import os
import socket
import sys
import time
from pathlib import Path

from flask import (Blueprint, Flask, jsonify, redirect, render_template,
                   request)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))
from shared_state import wifi_state  # noqa: E402
from netservices_config import NetservicesConfig  # noqa: E402


# ========== Configuration ==========

LOG_FILE = "/var/log/wifi_dashboard.log"
DASHBOARD_PORT = 80
CONNECT_LOCK_TIMEOUT_SECONDS = 90
DASHBOARD_VERSION = "1.0"

logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

dashboard = Blueprint("dashboard", __name__, template_folder='templates_main')

_PERSIST_CFG = NetservicesConfig()


# ========== Globals injected into templates ==========

@dashboard.app_context_processor
def _inject_globals():
    return {"version": DASHBOARD_VERSION, "active_tab": "wifi",
            "theme": _PERSIST_CFG.read_theme()}


# ========== Helpers ==========

def _is_ap_client_request(remote_addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(remote_addr or "")
        return ip in ipaddress.ip_network("192.168.51.0/24")
    except Exception:
        return False


def busy_connect_response():
    target = wifi_state.get("connect_target")
    if target:
        return jsonify({"error": f"Connection to '{target}' is in progress. Please wait."}), 409
    return jsonify({"error": "A connection attempt is in progress. Please wait."}), 409


def validate_wifi_input(ssid: str, password: str):
    if not ssid:
        return False, "SSID is required"
    if len(ssid) > 32:
        return False, "SSID too long (max 32 characters)"
    if password and len(password) < 8:
        return False, f"Password too short ({len(password)} chars, WPA requires min 8)"
    if password and len(password) > 63:
        return False, f"Password too long ({len(password)} chars, max 63)"
    return True, None


# ========== API endpoints ==========

@dashboard.route('/heartbeat', methods=['POST'])
def heartbeat():
    wifi_state.heartbeat()
    return '{"status":"ok"}', 200, {'Content-Type': 'application/json'}


@dashboard.route('/api/status')
def api_status():
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
        "requester_ip": request.remote_addr,
    })


@dashboard.route('/api/networks')
def api_networks():
    return jsonify({
        "networks": wifi_state.get("networks", []),
        "known": wifi_state.get("known_networks", []),
    })


@dashboard.route('/api/saved-networks', methods=['GET'])
def api_saved_networks():
    return jsonify({
        "saved_networks": wifi_state.get("known_networks", []),
        "connected_ssid": wifi_state.get("connected_ssid"),
        "saved_network_error": wifi_state.get("saved_network_error"),
        "saved_network_last_action": wifi_state.get("saved_network_last_action"),
    })


@dashboard.route('/api/saved-networks', methods=['POST'])
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


@dashboard.route('/api/saved-networks/delete', methods=['POST'])
def api_saved_networks_delete():
    if wifi_state.get("connect_in_progress", False):
        return busy_connect_response()
    data = request.get_json() or {}
    ssid = (data.get('ssid') or '').strip()
    if not ssid:
        return jsonify({"error": "SSID is required"}), 400
    wifi_state.request_saved_network_delete(ssid)
    return jsonify({"status": "requested"}), 202


@dashboard.route('/api/scan', methods=['POST'])
def api_scan():
    wifi_state.heartbeat()
    if wifi_state.get("connect_in_progress", False):
        return busy_connect_response()
    wifi_state.request_scan()
    return '{"status":"requested"}', 200, {'Content-Type': 'application/json'}


@dashboard.route('/api/connect', methods=['POST'])
def api_connect():
    if not _is_ap_client_request(request.remote_addr):
        return jsonify({"error": "SSID connect is allowed only when accessed via AP."}), 403

    data = request.get_json() or {}
    ssid = data.get('ssid') or request.form.get('ssid', '')
    password = data.get('password') or request.form.get('password', '')
    use_saved = data.get('use_saved', False)

    if not use_saved:
        valid, error = validate_wifi_input(ssid, password)
        if not valid:
            return jsonify({"error": error}), 400
    elif not ssid:
        return jsonify({"error": "SSID is required"}), 400

    if wifi_state.get("connect_in_progress", False):
        started = wifi_state.get("connect_started_at", 0)
        if started and (time.time() - started) > 60:
            wifi_state.update({"connect_in_progress": False, "connect_target": None})
        else:
            target = wifi_state.get("connect_target")
            if target:
                return jsonify({"error": f"Already connecting to '{target}'. Please wait."}), 409
            return jsonify({"error": "Another connection attempt is already in progress. Please wait."}), 409

    wifi_state.update({
        "connect_in_progress": True,
        "connect_target": ssid,
        "connect_started_at": time.time(),
        "connect_error": None,
    })
    wifi_state.request_connect(ssid, password, use_saved)
    return '{"status":"connecting"}', 200, {'Content-Type': 'application/json'}


# ========== Web pages ==========

@dashboard.route('/')
def home():
    return redirect('/wifi-settings', code=302)


@dashboard.route('/wifi-settings')
def index():
    networks = wifi_state.get("networks", [])
    return render_template(
        "wifi_settings.html",
        networks=networks,
        show_back=(not _is_ap_client_request(request.remote_addr)),
        connect_allowed=_is_ap_client_request(request.remote_addr),
    )


@dashboard.route('/saved-networks')
def saved_networks_page():
    return render_template("manage_networks.html")


@dashboard.route('/wifi-network-info')
def wifi_network_info_page():
    return render_template("wifi_network_info.html")


@dashboard.route('/configure_wifi', methods=['POST'])
def configure_wifi():
    if not _is_ap_client_request(request.remote_addr):
        return "SSID connect is allowed only when accessed via AP.", 403
    ssid = request.form.get('ssid', '').strip()
    password = request.form.get('password', '')
    valid, error = validate_wifi_input(ssid, password)
    if not valid:
        return f"<h1>Invalid Input</h1><p>{error}</p><p><a href='/'>Back</a></p>", 400
    wifi_state.request_connect(ssid, password)
    return f"<h1>Connecting to {ssid}...</h1><p>Check status at <a href='/wifi-settings'>Wi-Fi Settings</a>.</p>"


# ========== Captive portal ==========

def _captive_portal_url():
    try:
        req_host = (request.host or "").strip().split(":", 1)[0].strip().lower()
    except RuntimeError:
        req_host = ""
    if req_host:
        try:
            ip = ipaddress.ip_address(req_host)
            if isinstance(ip, ipaddress.IPv4Address) and (ip.is_private or ip.is_loopback):
                return f"http://{req_host}/"
        except Exception:
            try:
                host = socket.gethostname().strip().lower()
                names = {"localhost"}
                if host:
                    names.add(host)
                    if "." not in host:
                        names.add(f"{host}.local")
                if req_host in names:
                    return f"http://{req_host}/"
            except Exception:
                pass
    return "http://192.168.51.1/"


@dashboard.route('/generate_204')
@dashboard.route('/gen_204')
@dashboard.route('/hotspot-detect.html')
@dashboard.route('/library/test/success.html')
@dashboard.route('/ncsi.txt')
@dashboard.route('/connecttest.txt')
@dashboard.route('/chat', methods=['GET', 'POST'])
def captive_redirect():
    return redirect(_captive_portal_url(), code=302)


@dashboard.route('/favicon.ico')
def favicon():
    return ('', 204)


@dashboard.route('/<path:path>')
def catch_all(path):
    return redirect('/', code=302)


@dashboard.app_errorhandler(404)
def not_found(e):
    return redirect('/', code=302)


# ========== App factory ==========

def create_app() -> Flask:
    flask_app = Flask(__name__, template_folder='templates_main')
    flask_app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    flask_app.config['TEMPLATES_AUTO_RELOAD'] = True
    flask_app.register_blueprint(dashboard)
    return flask_app


app = create_app()


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=DASHBOARD_PORT, threaded=True, debug=False)
