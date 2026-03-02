#!/usr/bin/env python3
"""
WiFi Dashboard Service - Lightweight version
"""

import os
import sys
import logging
import time
import subprocess
import signal
import configparser
import ipaddress
import json
import re
import shutil
import threading
import secrets
import hmac
import socket
import crypt
import pty
import select
import struct
import fcntl
import termios
import uuid
import base64
import collections
from datetime import timedelta
from pathlib import Path

# Minimal imports for lower memory
from flask import Flask, render_template, request, redirect, jsonify, make_response, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.serving import make_server

# Add services to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))
from shared_state import wifi_state
from netservices_config import NetservicesConfig

# ========== Configuration ==========

LOG_FILE = "/var/log/wifi_dashboard.log"
DASHBOARD_PORT = 443
DASHBOARD_HTTP_PORT = 80
SSL_CERT_DIR = Path("/data/rexgen/config/ssl")
SSL_CERT_FILE = SSL_CERT_DIR / "dashboard.crt"
SSL_KEY_FILE = SSL_CERT_DIR / "dashboard.key"
SSL_CA_FILE = SSL_CERT_DIR / "ca.crt"
SSL_CA_KEY_FILE = SSL_CERT_DIR / "ca.key"
SERIAL_FILE = "/home/root/rexusb/var/serial"
CONNECT_LOCK_TIMEOUT_SECONDS = 90
REXGEND_CONFIG_FILE = "/data/rexgen/config/rexgend.conf"
REXGEND_SERVICE = "rexgend.service"
WIFI_DASHBOARD_SERVICE = "wifi-dashboard.service"
MENDER_CONFIG_FILE = "/etc/mender/mender.conf"
MENDER_SERVICES = ["mender-authd.service", "mender-updated.service"]
CONTROL_CENTER_DEFAULT_USER = "admin"
CONTROL_CENTER_DEFAULT_PASS = "admin"
DASHBOARD_VERSION = "1.1.1"
LOGIN_ATTEMPT_WINDOW_SECONDS = 600
LOGIN_LOCK_SECONDS = 900
LOGIN_MAX_FAILURES = 5
SERVICE_STATUS_CACHE_SECONDS = 30
_SERVICE_STATUS_CACHE = {"ts": 0.0, "items": []}
_FW_UPGRADE_CACHE = {"value": False}
_SETTINGS_CACHE = {"ts": 0.0, "data": None}
_SETTINGS_CACHE_TTL = 10.0
_UNIT_NAME_RE = re.compile(r"^[A-Za-z0-9@_.:-]+$")
REXGEND_DEFAULTS = {
    "use_socketcan": 0,
    "use_space_limit": 1,
    "max_space_percent": 90,
    "log_errors": 0,
    "use_ntp": 1,
    "ntp_update_period": 300,
}

# Setup logging - minimal
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(message)s"
)
log = logging.getLogger(__name__)
TRACE_VERBOSE = os.environ.get("REXGEN_TRACE_VERBOSE", "0") == "1"

# Flask app - minimal config
app = Flask(__name__, template_folder='templates')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

@app.context_processor
def _inject_globals():
    path = request.path
    if path in ("/device-info", "/cpu-detail", "/memory-detail", "/disk-detail",
                "/process-info", "/service-info", "/services"):
        active_tab = "device"
    elif path in ("/wifi-settings", "/wifi-network-info", "/manage-networks"):
        active_tab = "wifi"
    elif path in ("/ap-settings", "/ap-client-info"):
        active_tab = "ap"
    elif path == "/rexgend-settings":
        active_tab = "rexgend"
    elif path == "/system-settings":
        active_tab = "system"
    else:
        active_tab = ""
    return {"version": DASHBOARD_VERSION, "active_tab": active_tab,
            "theme": _PERSIST_CFG.read_theme(),
            "experimental": _PERSIST_CFG.read_experimental()}


_LOGIN_FAIL_STATE = {}
_PERSIST_CFG = NetservicesConfig()


def _make_password_hash(password: str) -> str:
    try:
        return generate_password_hash(password, method="scrypt")
    except Exception:
        return generate_password_hash(password, method="pbkdf2:sha256:600000")


def _load_or_init_auth_config() -> dict:
    data = _PERSIST_CFG.read_auth()
    username = (data.get("username") or "").strip()
    password_hash = (data.get("password_hash") or "").strip()
    if username and password_hash:
        return {"username": username, "password_hash": password_hash}
    init_data = {
        "username": CONTROL_CENTER_DEFAULT_USER,
        "password_hash": _make_password_hash(CONTROL_CENTER_DEFAULT_PASS),
    }
    _PERSIST_CFG.write_auth(init_data)
    return init_data


def _save_auth_config(username: str, password_hash: str):
    _PERSIST_CFG.write_auth({
        "username": (username or "").strip(),
        "password_hash": (password_hash or "").strip(),
    })


def _load_or_init_settings() -> dict:
    data = _PERSIST_CFG.read_dashboard()
    if "https_enabled" not in data:
        data["https_enabled"] = False
    if "https_hostname" not in data:
        data["https_hostname"] = ""
    return data


def _save_settings(data: dict):
    _PERSIST_CFG.write_dashboard(data)


def _load_or_init_system_settings() -> dict:
    data = _PERSIST_CFG.read_system()
    if "ssh_enabled" not in data:
        data["ssh_enabled"] = True
        _PERSIST_CFG.write_system({"ssh_enabled": True})
    return data


def _save_system_settings(data: dict):
    _PERSIST_CFG.write_system(data)


def _normalize_https_hostname(value: str) -> str:
    return (value or "").strip().lower().replace("_", "-")


def _is_fw_upgrade_in_progress() -> bool:
    """Return True if influx_upgrade u-boot env flag is set to 1.
    Value is updated by a background thread — never blocks a request."""
    return _FW_UPGRADE_CACHE["value"]


def _fw_upgrade_poll_loop():
    """Background daemon: polls fw_printenv every 10 s, never blocks requests."""
    while True:
        try:
            out = subprocess.run(
                ["fw_printenv", "influx_upgrade"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
            _FW_UPGRADE_CACHE["value"] = (out == "influx_upgrade=1")
        except Exception:
            _FW_UPGRADE_CACHE["value"] = False
        time.sleep(10)


threading.Thread(target=_fw_upgrade_poll_loop, daemon=True, name="fw-upgrade-poll").start()


def _cached_settings() -> dict:
    """Read dashboard settings with a short in-memory cache to avoid flash I/O per request."""
    now = time.time()
    if _SETTINGS_CACHE["data"] is not None and now - _SETTINGS_CACHE["ts"] < _SETTINGS_CACHE_TTL:
        return _SETTINGS_CACHE["data"]
    data = _load_or_init_settings()
    _SETTINGS_CACHE["ts"] = now
    _SETTINGS_CACHE["data"] = data
    return data


def _invalidate_settings_cache():
    """Call after saving settings so the next request picks up fresh values."""
    _SETTINGS_CACHE["data"] = None


def _default_https_hostname() -> str:
    try:
        host = _normalize_https_hostname(Path(SERIAL_FILE).read_text())
    except Exception:
        host = ""
    if not host:
        return ""
    if "." in host:
        return host
    return f"{host}.local"


def _configured_https_hostname(settings: dict | None = None) -> str:
    cfg = settings if settings is not None else _load_or_init_settings()
    v = _normalize_https_hostname(cfg.get("https_hostname") or "")
    if v:
        if "." not in v:
            return f"{v}.local"
        return v
    return _default_https_hostname()


def _apply_mdns_hostname_from_setting(hostname_value: str):
    """Apply dashboard hostname to system hostname so Avahi advertises it via mDNS."""
    raw = _normalize_https_hostname(hostname_value)
    if not raw:
        return
    short = raw.split(".", 1)[0].strip()
    if not short:
        return
    if len(short) > 63:
        raise RuntimeError("mDNS hostname label too long")
    if (not re.fullmatch(r"[a-z0-9-]+", short)) or short.startswith("-") or short.endswith("-"):
        raise RuntimeError("mDNS hostname contains invalid characters")

    current = ""
    try:
        current = (subprocess.run(["hostname"], check=True, timeout=5, capture_output=True, text=True).stdout or "").strip().lower()
    except Exception:
        pass
    if current == short:
        return

    try:
        subprocess.run(["hostnamectl", "set-hostname", short], check=True, timeout=10, capture_output=True, text=True)
    except Exception:
        subprocess.run(["sh", "-c", f"echo '{short}' > /etc/hostname"], check=True, timeout=10, capture_output=True, text=True)
        subprocess.run(["hostname", short], check=True, timeout=10, capture_output=True, text=True)
    subprocess.run(["systemctl", "restart", "avahi-daemon"], check=True, timeout=15, capture_output=True, text=True)


def _apply_mdns_hostname_from_effective(effective_host: str):
    """Apply effective hostname (.local or custom) to system hostname/mDNS short label."""
    raw = _normalize_https_hostname(effective_host)
    if not raw:
        return
    _apply_mdns_hostname_from_setting(raw)


def _load_or_init_secret_key() -> str:
    sess = _PERSIST_CFG.read_session()
    key = (sess.get("secret_key") or "").strip()
    if key:
        return key
    key = secrets.token_hex(32)
    _PERSIST_CFG.write_session({"secret_key": key})
    return key


def _initialize_auth_runtime():
    app.secret_key = _load_or_init_secret_key()
    _load_or_init_auth_config()


def _is_safe_next_path(path: str) -> bool:
    if not path:
        return False
    if not path.startswith("/"):
        return False
    if path.startswith("//"):
        return False
    if path.startswith("/login"):
        return False
    return True


def _is_public_path(path: str) -> bool:
    if not path:
        return False
    public_prefixes = ("/static/",)
    public_exact = {
        "/login",
        "/logout",
        "/favicon.ico",
        "/heartbeat",
        "/generate_204",
        "/gen_204",
        "/hotspot-detect.html",
        "/library/test/success.html",
        "/ncsi.txt",
        "/connecttest.txt",
        "/chat",
        "/host-switch",
        "/updating",
        "/api/update-status",
        "/install-certificate",
        "/download-ca-cert",
    }
    if path in public_exact:
        return True
    return any(path.startswith(pfx) for pfx in public_prefixes)


def _is_captive_path(path: str) -> bool:
    p = path or "/"
    return p in {
        "/generate_204",
        "/gen_204",
        "/hotspot-detect.html",
        "/library/test/success.html",
        "/ncsi.txt",
        "/connecttest.txt",
        "/chat",
    }


def _is_authenticated() -> bool:
    return bool(session.get("cc_auth") is True)


def _client_key() -> str:
    return request.remote_addr or "unknown"


def _get_login_lock_seconds_left(client: str) -> int:
    now = int(time.time())
    rec = _LOGIN_FAIL_STATE.get(client)
    if not rec:
        return 0
    locked_until = int(rec.get("locked_until", 0))
    if locked_until <= now:
        if rec.get("first_ts", 0) and (now - int(rec.get("first_ts", 0)) > LOGIN_ATTEMPT_WINDOW_SECONDS):
            _LOGIN_FAIL_STATE.pop(client, None)
        return 0
    return max(0, locked_until - now)


def _register_login_failure(client: str):
    now = int(time.time())
    rec = _LOGIN_FAIL_STATE.get(client)
    if not rec or (now - int(rec.get("first_ts", 0)) > LOGIN_ATTEMPT_WINDOW_SECONDS):
        rec = {"count": 0, "first_ts": now, "locked_until": 0}
    rec["count"] = int(rec.get("count", 0)) + 1
    if rec["count"] >= LOGIN_MAX_FAILURES:
        rec["locked_until"] = now + LOGIN_LOCK_SECONDS
        rec["count"] = 0
        rec["first_ts"] = now
    _LOGIN_FAIL_STATE[client] = rec


def _clear_login_failures(client: str):
    _LOGIN_FAIL_STATE.pop(client, None)


_initialize_auth_runtime()


def _trace(msg: str):
    if TRACE_VERBOSE:
        log.info(f"[TRACE][DASH] {msg}")


@app.before_request
def _auth_guard():
    path = request.path or "/"
    settings = _cached_settings()
    https_enabled = bool(settings.get("https_enabled", False))
    host = (request.host or "").split(":", 1)[0].strip().lower()
    canonical_host = _configured_https_hostname(settings).strip().lower()

    # In HTTPS mode, keep a canonical host for LAN/normal browsing.
    # AP onboarding host (192.168.51.1) is intentionally exempt.
    if https_enabled and canonical_host and host and (host != "192.168.51.1") and (host != canonical_host) and (not _is_captive_path(path)) and (path != "/host-switch"):
        base = f"https://{canonical_host}"
        suffix = request.full_path if request.query_string else request.path
        if suffix.endswith("?"):
            suffix = suffix[:-1]
        if not suffix.startswith("/"):
            suffix = "/" + suffix
        return redirect(base + suffix, code=302)

    # Keep AP onboarding on plain HTTP, but upgrade other HTTP traffic to HTTPS hostname.
    if https_enabled and (not request.is_secure):
        if host and (host != "192.168.51.1") and (not _is_captive_path(path)):
            base = _dashboard_url().rstrip("/")
            suffix = request.full_path if request.query_string else request.path
            if suffix.endswith("?"):
                suffix = suffix[:-1]
            if not suffix.startswith("/"):
                suffix = "/" + suffix
            return redirect(base + suffix, code=302)

    # Block all access during firmware upgrade, except the update page and its poll endpoint.
    _UPDATE_EXEMPT = {"/updating", "/api/update-status"}
    if path not in _UPDATE_EXEMPT and not _is_captive_path(path) and not path.startswith("/static/"):
        if _is_fw_upgrade_in_progress():
            if path.startswith("/api/"):
                return jsonify({"error": "Device is updating firmware, please wait."}), 503
            return redirect("/updating", code=302)

    if _is_public_path(path):
        return None
    if _is_authenticated():
        session.permanent = True
        return None

    if path.startswith("/api/"):
        return jsonify({"error": "Authentication required"}), 401

    next_path = request.full_path if request.query_string else request.path
    if next_path.endswith("?"):
        next_path = next_path[:-1]
    if not _is_safe_next_path(next_path):
        next_path = "/"
    return redirect(url_for("login_page", next=next_path), code=302)


def _is_ap_client_request(remote_addr: str) -> bool:
    """True when request originates from AP subnet clients."""
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


def validate_ap_password(password: str) -> tuple:
    """Validate AP password (WPA2 PSK constraints)."""
    if not password:
        return False, "AP password is required"
    if len(password) < 8:
        return False, "AP password too short (min 8 characters)"
    if len(password) > 63:
        return False, "AP password too long (max 63 characters)"
    return True, None


def _read_text(path: str) -> str:
    try:
        return Path(path).read_text().strip()
    except Exception:
        return ""


def _read_os_release_pretty_name() -> str:
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    return ""


def _read_mac_address(iface: str) -> str:
    return _read_text(f"/sys/class/net/{iface}/address")


def _read_ipv4_address(iface: str) -> str:
    try:
        out = subprocess.run(
            ["ip", "-4", "-o", "addr", "show", "dev", iface],
            capture_output=True, text=True, timeout=3
        ).stdout or ""
        # Example: "2: eth0    inet 192.168.11.185/24 brd ... "
        for line in out.splitlines():
            m = re.search(r"\binet\s+([0-9.]+)/", line)
            if m:
                return m.group(1)
    except Exception:
        pass
    return ""


def _format_iface_ip_mac(iface: str) -> str:
    ip = _read_ipv4_address(iface) or "--"
    mac = _read_mac_address(iface) or "--"
    return f"{ip}, {mac}"


def _read_network_interfaces() -> str:
    try:
        ifaces = sorted([name for name in os.listdir("/sys/class/net") if name != "lo"])
        return ",".join(ifaces)
    except Exception:
        return ""


def _read_cpu_model() -> str:
    def _clean(v: str) -> str:
        s = (v or "").strip()
        if not s:
            return ""
        if s.lower() in {"0", "unknown", "n/a", "na", "none"}:
            return ""
        return s

    def _extract_soc(v: str) -> str:
        s = _clean(v)
        if not s:
            return ""
        m = re.search(r"(i\.?mx[0-9a-z]+)", s, re.IGNORECASE)
        if m:
            soc = m.group(1).replace(".", "").upper()
            if soc.startswith("IMX"):
                return "i.MX" + soc[3:]
        return ""

    model_name = ""
    hardware_name = ""
    processor_name = ""
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip().lower()
            v = _clean(value)
            if not v:
                continue
            if key == "model name" and not model_name:
                model_name = v
            elif key == "hardware" and not hardware_name:
                hardware_name = v
            elif key == "processor" and not processor_name and not v.isdigit():
                processor_name = v
    except Exception:
        pass
    if model_name or hardware_name or processor_name:
        value = _clean(model_name or hardware_name or processor_name)
        return _extract_soc(value) or value
    try:
        raw = Path("/proc/device-tree/model").read_bytes()
        value = _clean(raw.decode("utf-8", errors="replace").replace("\x00", ""))
        return _extract_soc(value) or value
    except Exception:
        return ""


def _read_rexgend_release_date(base: str) -> str:
    candidates = [
        "rexgend_release_date",
        "rexgend_release",
        "release_date",
        "build_date",
    ]
    for name in candidates:
        value = _read_text(f"{base}/{name}")
        if value:
            return value
    return ""


def _read_mender_details() -> dict:
    out = {
        "mender_client_version": "",
        "mender_bootloader_integration": "",
    }
    version_text = ""
    for cmd in (["mender-update", "--version"], ["mender", "--version"]):
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            if res.returncode == 0:
                version_text = ((res.stdout or "") + "\n" + (res.stderr or "")).strip()
                if version_text:
                    break
        except Exception:
            continue

    if version_text:
        for line in version_text.splitlines():
            m_ver = re.search(r"\b(?:mender-update|mender)\s+([0-9A-Za-z._-]+)", line, re.IGNORECASE)
            if m_ver and not out["mender_client_version"]:
                out["mender_client_version"] = m_ver.group(1)
        if not out["mender_client_version"]:
            first = version_text.splitlines()[0].strip()
            if first and re.match(r"^[0-9A-Za-z._-]+$", first):
                out["mender_client_version"] = first

    try:
        inv = subprocess.run(
            ["/usr/share/mender/inventory/mender-inventory-bootloader-integration"],
            capture_output=True, text=True, timeout=3
        )
        if inv.returncode == 0:
            for line in (inv.stdout or "").splitlines():
                if line.startswith("mender_bootloader_integration="):
                    out["mender_bootloader_integration"] = line.split("=", 1)[1].strip()
                    break
    except Exception:
        pass

    return out


def _restart_mender_services() -> tuple:
    """Restart Mender services in order and verify they are active."""
    restarted = []
    for svc in MENDER_SERVICES:
        subprocess.run(["systemctl", "restart", svc], check=True, timeout=20)
        is_active = subprocess.run(
            ["systemctl", "is-active", svc],
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
        if is_active != "active":
            raise RuntimeError(f"{svc} is not active after restart")
        restarted.append(svc)
    return tuple(restarted)


def get_device_info() -> dict:
    """Read device metadata from rexgend var files and Linux system info."""
    base = "/home/root/rexusb/var"
    image_version = ""
    try:
        res = subprocess.run(
            ["mender-update", "show-artifact"],
            capture_output=True, text=True, timeout=3
        )
        if res.returncode == 0:
            image_version = (res.stdout or "").strip()
    except Exception:
        image_version = ""

    os_release_text = _read_text("/etc/os-release")
    if (not image_version) and os_release_text:
        for line in os_release_text.splitlines():
            if line.startswith("VERSION_ID="):
                image_version = line.split("=", 1)[1].strip().strip('"')
                break
    if not image_version:
        image_version = "2.04"

    mender = _read_mender_details()
    return {
        "rexgend_version": _read_text(f"{base}/rexgend_version"),
        "rexgend_release_date": _read_rexgend_release_date(base),
        "serial_number": _read_text(f"{base}/serial"),
        "cpu_type": _read_text(f"{base}/cputype"),
        "firmware_version": _read_text(f"{base}/firmware"),
        "configuration_name": _read_text(f"{base}/configuration_name"),
        "configuration_uid": _read_text(f"{base}/configuration_uuid"),
        "linux_version": os.uname().release if hasattr(os, "uname") else "",
        "image_version": image_version,
        "os": _read_os_release_pretty_name(),
        "hostname": os.uname().nodename if hasattr(os, "uname") else "",
        "architecture": os.uname().machine if hasattr(os, "uname") else "",
        "cpu_cores": str(os.cpu_count() or ""),
        "cpu_model": _read_cpu_model(),
        "mac_eth0": _read_mac_address("eth0"),
        "mac_wlan0": _read_mac_address("wlan0"),
        "mac_wlan1": _read_mac_address("wlan1"),
        "iface_eth0": _format_iface_ip_mac("eth0"),
        "iface_wlan0": _format_iface_ip_mac("wlan0"),
        "iface_wlan1": _format_iface_ip_mac("wlan1"),
        "network_interfaces": _read_network_interfaces(),
        "mender_client_version": mender.get("mender_client_version", ""),
        "mender_bootloader_integration": mender.get("mender_bootloader_integration", ""),
    }


def _read_meminfo() -> dict:
    vals = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            parts = v.strip().split()
            if not parts:
                continue
            vals[k.strip()] = int(parts[0])  # kB
    except Exception:
        return {}
    return vals


def _cpu_stat_sample() -> dict:
    """Sample /proc/stat for overall + per-core CPU times.

    Returns dict:
      cpuN keys -> (total, idle, irq, softirq, user, system, iowait)
      "ctxt"    -> int  (total context switches)
      "intr"    -> int  (total interrupts)
    /proc/stat fields: user nice system idle iowait irq softirq [steal]
    """
    result = {}
    for line in _read_text("/proc/stat").splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0].startswith("cpu") and len(parts) >= 5:
            nums = [int(x) for x in parts[1:8] if x.isdigit()]
            if len(nums) < 4:
                continue
            idle = nums[3] + (nums[4] if len(nums) > 4 else 0)
            total = sum(nums)
            irq = nums[5] if len(nums) > 5 else 0
            softirq = nums[6] if len(nums) > 6 else 0
            user = nums[0] + nums[1]  # user + nice
            system = nums[2]
            iowait = nums[4] if len(nums) > 4 else 0
            result[parts[0]] = (total, idle, irq, softirq, user, system, iowait)
        elif parts[0] == "ctxt" and len(parts) >= 2:
            result["ctxt"] = int(parts[1])
        elif parts[0] == "intr" and len(parts) >= 2:
            result["intr"] = int(parts[1])
    return result


class _SystemSampler:
    """Background sampler for CPU and process data.

    Samples /proc/stat and /proc/[pid] every 2 seconds in a daemon thread.
    All API endpoints read from the latest snapshot — no blocking sleeps,
    no redundant /proc walks, no subprocess calls.
    """

    def __init__(self, interval=2.0):
        self._lock = threading.Lock()
        self._interval = interval
        self._stat_a: dict = {}
        self._stat_b: dict = {}
        # Per-process: pid -> (ticks, name, state, rss_pages, vsize_bytes)
        self._procs_a: dict = {}
        self._procs_b: dict = {}
        self._extra = {"cores": os.cpu_count() or 0, "tasks": 0, "threads": 0, "running": 0}
        self._ready = False
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        self._stat_b = _cpu_stat_sample()
        self._procs_b, extra = self._walk_procs()
        self._extra = extra
        time.sleep(self._interval)
        while True:
            stat = _cpu_stat_sample()
            procs, extra = self._walk_procs()
            with self._lock:
                self._stat_a = self._stat_b
                self._stat_b = stat
                self._procs_a = self._procs_b
                self._procs_b = procs
                self._extra = extra
                self._ready = True
            time.sleep(self._interval)

    def _walk_procs(self):
        """Single walk of /proc/[pid] — CPU ticks, names, RSS, vsize, task/thread counts."""
        procs = {}
        tasks = 0
        threads = 0
        running = 0
        try:
            for d in os.listdir("/proc"):
                if not d.isdigit():
                    continue
                base = f"/proc/{d}"
                try:
                    cmdline = Path(base + "/cmdline").read_bytes()
                    if not cmdline:
                        continue
                except Exception:
                    continue
                tasks += 1
                try:
                    raw = Path(base + "/stat").read_text()
                except Exception:
                    continue
                paren_end = raw.rfind(")")
                if paren_end < 0:
                    continue
                comm = raw[raw.index("(") + 1:paren_end]
                rest = raw[paren_end + 2:].split()
                if len(rest) < 22:
                    continue
                state = rest[0]
                if state == "R":
                    running += 1
                utime = int(rest[11])
                stime = int(rest[12])
                num_threads = int(rest[17])
                vsize = int(rest[20])
                rss = int(rest[21])
                threads += num_threads
                name = _proc_display_name(cmdline, comm)
                procs[d] = (utime + stime, name, state, rss, vsize)
        except Exception:
            pass
        extra = {
            "cores": os.cpu_count() or 0,
            "tasks": tasks,
            "threads": max(0, threads - tasks),
            "running": running,
        }
        return procs, extra

    def get_cpu_snapshot(self):
        """Returns (stat_a, stat_b, procs_a, procs_b, extra, interval, ready)."""
        with self._lock:
            return (dict(self._stat_a), dict(self._stat_b),
                    dict(self._procs_a), dict(self._procs_b),
                    dict(self._extra), self._interval, self._ready)

    def get_extra(self):
        with self._lock:
            return dict(self._extra)


_sampler = _SystemSampler(interval=2.0)


def _sampler_cpu_pct() -> float:
    """CPU usage % from the background sampler (no sleep)."""
    stat_a, stat_b, _, _, _, _, ready = _sampler.get_cpu_snapshot()
    if not ready or "cpu" not in stat_a or "cpu" not in stat_b:
        return -1.0
    dt = stat_b["cpu"][0] - stat_a["cpu"][0]
    didle = stat_b["cpu"][1] - stat_a["cpu"][1]
    if dt <= 0:
        return -1.0
    return max(0.0, min(100.0, 100.0 * (dt - didle) / dt))



def _format_bytes(n: int) -> str:
    if n < 0:
        return "--"
    units = ["B", "KB", "MB", "GB", "TB"]
    val = float(n)
    idx = 0
    while val >= 1024.0 and idx < len(units) - 1:
        val /= 1024.0
        idx += 1
    if idx <= 1:
        return f"{int(val)} {units[idx]}"
    return f"{val:.1f} {units[idx]}"


def get_device_status() -> dict:
    mem = _read_meminfo()
    mem_total_kb = int(mem.get("MemTotal", 0))
    mem_avail_kb = int(mem.get("MemAvailable", mem.get("MemFree", 0)))
    mem_used_kb = max(0, mem_total_kb - mem_avail_kb)
    mem_pct = (100.0 * mem_used_kb / mem_total_kb) if mem_total_kb > 0 else -1.0

    disk_total = disk_used = disk_free = -1
    disk_pct = -1.0
    try:
        du = shutil.disk_usage("/")
        disk_total = int(du.total)
        disk_used = int(du.used)
        disk_free = int(du.free)
        disk_pct = (100.0 * disk_used / disk_total) if disk_total > 0 else -1.0
    except Exception:
        pass

    uptime_seconds = -1
    try:
        up = _read_text("/proc/uptime").split()
        if up:
            uptime_seconds = int(float(up[0]))
    except Exception:
        pass

    cpu_temp_c = None
    for zone in ("/sys/class/thermal/thermal_zone0/temp", "/sys/class/thermal/thermal_zone1/temp"):
        raw = _read_text(zone)
        if raw.isdigit():
            v = int(raw)
            cpu_temp_c = (v / 1000.0) if v > 1000 else float(v)
            break

    load1, load5, load15 = (0.0, 0.0, 0.0)
    try:
        load1, load5, load15 = os.getloadavg()
    except Exception:
        pass

    return {
        "cpu_usage_percent": round(_sampler_cpu_pct(), 1),
        "load_1m": round(load1, 2),
        "load_5m": round(load5, 2),
        "load_15m": round(load15, 2),
        "cpu_temp_c": round(cpu_temp_c, 1) if cpu_temp_c is not None else None,
        "memory_used_percent": round(mem_pct, 1),
        "memory_used": _format_bytes(mem_used_kb * 1024),
        "memory_total": _format_bytes(mem_total_kb * 1024),
        "disk_used_percent": round(disk_pct, 1),
        "disk_used": _format_bytes(disk_used),
        "disk_total": _format_bytes(disk_total),
        "disk_free": _format_bytes(disk_free),
        "uptime_seconds": uptime_seconds,
    }


def _proc_display_name(cmdline_bytes: bytes, comm: str) -> str:
    """Build a human-friendly process name from cmdline.

    For interpreters (python3, sh, bash, node, ...) show: "interpreter: script"
    For regular binaries show just the basename.
    """
    try:
        args = cmdline_bytes.decode("utf-8", errors="replace").split("\x00")
        args = [a for a in args if a]
    except Exception:
        return comm
    if not args:
        return comm
    base0 = args[0].rsplit("/", 1)[-1]
    # Interpreter pattern: first arg is interpreter, find the script arg
    interpreters = {"python3", "python", "python2", "sh", "bash", "dash",
                    "node", "perl", "ruby", "java", "lua"}
    if base0 in interpreters and len(args) > 1:
        # Skip flags (start with -)
        for a in args[1:]:
            if not a.startswith("-"):
                script = a.rsplit("/", 1)[-1]
                return f"{base0}: {script}"
        return base0
    return base0



def _get_top_memory_processes(limit: int = 12) -> list:
    """Top memory processes from background sampler — no subprocess, no /proc walk."""
    _, _, _, procs_b, _, _, ready = _sampler.get_cpu_snapshot()
    if not ready:
        return []
    page_size = 4  # KB per page
    rows = []
    for pid, (_, name, state, rss_pages, vsize_bytes) in procs_b.items():
        rss_kb = rss_pages * page_size
        vsz_kb = vsize_bytes // 1024
        rows.append({
            "pid": pid,
            "name": name,
            "rss": _format_bytes(rss_kb * 1024),
            "vsz": _format_bytes(vsz_kb * 1024),
            "state": state,
            "_rss_kb": rss_kb,
        })
    rows.sort(key=lambda r: r["_rss_kb"], reverse=True)
    for r in rows:
        del r["_rss_kb"]
    return rows[:limit]


def _cpu_summary_instant() -> dict:
    """Fast CPU summary — uses cached sampler data, no /proc walk."""
    load1, load5, load15 = (0.0, 0.0, 0.0)
    try:
        load1, load5, load15 = os.getloadavg()
    except Exception:
        pass
    cpu_temp_c = None
    for zone in ("/sys/class/thermal/thermal_zone0/temp", "/sys/class/thermal/thermal_zone1/temp"):
        raw = _read_text(zone)
        if raw.isdigit():
            v = int(raw)
            cpu_temp_c = (v / 1000.0) if v > 1000 else float(v)
            break
    extra = _sampler.get_extra()
    return {
        "cores": extra["cores"],
        "tasks": extra["tasks"],
        "threads": extra["threads"],
        "running": extra["running"],
        "load_1m": round(load1, 2),
        "load_5m": round(load5, 2),
        "load_15m": round(load15, 2),
        "temp_c": round(cpu_temp_c, 1) if cpu_temp_c is not None else None,
    }


def _cpu_detail_full() -> dict:
    """Full CPU detail from background sampler — no sleep, no /proc walk."""
    a_stat, b_stat, a_procs, b_procs, extra, interval, ready = _sampler.get_cpu_snapshot()
    if not ready:
        return {"usage_percent": -1.0, "per_core": [], "irq_pct": 0, "softirq_pct": 0,
                "user_pct": 0, "system_pct": 0, "iowait_pct": 0,
                "ctxt_per_sec": 0, "intr_per_sec": 0, "rows": []}

    per_core = []
    i = 0
    while True:
        key = f"cpu{i}"
        if key not in a_stat or key not in b_stat:
            break
        dt = b_stat[key][0] - a_stat[key][0]
        didle = b_stat[key][1] - a_stat[key][1]
        if dt > 0:
            per_core.append(round(max(0.0, min(100.0, 100.0 * (dt - didle) / dt)), 1))
        else:
            per_core.append(0.0)
        i += 1

    cpu_pct = round(sum(per_core) / len(per_core), 1) if per_core else -1.0

    # CPU breakdown from overall "cpu" line
    irq_pct = 0.0
    softirq_pct = 0.0
    user_pct = 0.0
    system_pct = 0.0
    iowait_pct = 0.0
    if "cpu" in a_stat and "cpu" in b_stat:
        dt = b_stat["cpu"][0] - a_stat["cpu"][0]
        if dt > 0:
            irq_pct = round(100.0 * (b_stat["cpu"][2] - a_stat["cpu"][2]) / dt, 1)
            softirq_pct = round(100.0 * (b_stat["cpu"][3] - a_stat["cpu"][3]) / dt, 1)
            user_pct = round(100.0 * (b_stat["cpu"][4] - a_stat["cpu"][4]) / dt, 1)
            system_pct = round(100.0 * (b_stat["cpu"][5] - a_stat["cpu"][5]) / dt, 1)
            iowait_pct = round(100.0 * (b_stat["cpu"][6] - a_stat["cpu"][6]) / dt, 1)

    # Context switches/sec and interrupts/sec
    ctxt_per_sec = 0
    intr_per_sec = 0
    if "ctxt" in a_stat and "ctxt" in b_stat:
        ctxt_per_sec = int(round((b_stat["ctxt"] - a_stat["ctxt"]) / interval))
    if "intr" in a_stat and "intr" in b_stat:
        intr_per_sec = int(round((b_stat["intr"] - a_stat["intr"]) / interval))

    # Per-process CPU% from sampler snapshots
    hz = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
    ncpu = os.cpu_count() or 1
    total_ticks = interval * hz * ncpu

    mem = _read_meminfo()
    mem_total_kb = int(mem.get("MemTotal", 0))
    page_size_kb = 4

    rows = []
    for pid, (b_ticks, name, state, rss, _vsize) in b_procs.items():
        if pid not in a_procs:
            continue
        a_ticks = a_procs[pid][0]
        dt = b_ticks - a_ticks
        pct = round(100.0 * dt / total_ticks, 1) if total_ticks > 0 else 0.0
        rss_kb = rss * page_size_kb
        mem_pct = round(100.0 * rss_kb / mem_total_kb, 1) if mem_total_kb > 0 else 0.0
        rows.append({"pid": pid, "name": name, "cpu": str(pct), "mem": str(mem_pct), "state": state})
    rows.sort(key=lambda r: float(r["cpu"]), reverse=True)
    proc_rows = rows[:15]

    return {
        "usage_percent": cpu_pct,
        "per_core": per_core,
        "irq_pct": irq_pct,
        "softirq_pct": softirq_pct,
        "user_pct": user_pct,
        "system_pct": system_pct,
        "iowait_pct": iowait_pct,
        "ctxt_per_sec": ctxt_per_sec,
        "intr_per_sec": intr_per_sec,
        "rows": [
            [r["pid"], r["name"], r["cpu"], r["mem"], r["state"]]
            for r in proc_rows
        ],
    }


def get_device_status_detail(kind: str, summary_only: bool = False) -> dict:
    if kind == "cpu":
        if summary_only:
            # Instant path: no sampling, just read current values
            summary = _cpu_summary_instant()
            return {
                "kind": "cpu",
                "title": "Top CPU Processes",
                "summary": summary,
                "updated_at": int(time.time()),
            }
        full = _cpu_detail_full()
        summary = _cpu_summary_instant()
        summary["usage_percent"] = full["usage_percent"]
        summary["per_core"] = full["per_core"]
        summary["irq_pct"] = full["irq_pct"]
        summary["softirq_pct"] = full["softirq_pct"]
        summary["user_pct"] = full["user_pct"]
        summary["system_pct"] = full["system_pct"]
        summary["iowait_pct"] = full["iowait_pct"]
        summary["ctxt_per_sec"] = full["ctxt_per_sec"]
        summary["intr_per_sec"] = full["intr_per_sec"]
        return {
            "kind": "cpu",
            "title": "Top CPU Processes",
            "summary": summary,
            "columns": ["PID", "Name", "CPU%", "MEM%", "State"],
            "rows": full["rows"],
            "updated_at": int(time.time()),
        }
    if kind == "memory":
        mem = _read_meminfo()
        mem_total_kb = int(mem.get("MemTotal", 0))
        mem_avail_kb = int(mem.get("MemAvailable", mem.get("MemFree", 0)))
        mem_used_kb = max(0, mem_total_kb - mem_avail_kb)
        mem_pct = (100.0 * mem_used_kb / mem_total_kb) if mem_total_kb > 0 else -1.0
        mem_buffers_kb = int(mem.get("Buffers", 0))
        mem_cached_kb = int(mem.get("Cached", 0))
        return {
            "kind": "memory",
            "title": "Top Memory Processes",
            "summary": {
                "used_percent": round(mem_pct, 1),
                "used": _format_bytes(mem_used_kb * 1024),
                "total": _format_bytes(mem_total_kb * 1024),
                "available": _format_bytes(mem_avail_kb * 1024),
                "buffers": _format_bytes(mem_buffers_kb * 1024),
                "cached": _format_bytes(mem_cached_kb * 1024),
            },
            "columns": ["PID", "Name", "RSS", "VSZ", "State"],
            "rows": [
                [r["pid"], r["name"], r["rss"], r["vsz"], r["state"]]
                for r in _get_top_memory_processes(limit=15)
            ],
            "updated_at": int(time.time()),
        }
    if kind == "disk":
        rows = []
        try:
            out = subprocess.run(
                ["df", "-hP"],
                capture_output=True, text=True, timeout=5
            ).stdout or ""
            for line in out.splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 6:
                    rows.append(parts[:6])
        except Exception:
            rows = []
        return {
            "kind": "disk",
            "title": "Disk Usage Details",
            "columns": ["Filesystem", "Size", "Used", "Avail", "Use%", "Mount"],
            "rows": rows,
            "updated_at": int(time.time()),
        }
    return {"error": "Unsupported status detail"}


def _load_rexgend_config() -> dict:
    """Load rexgend.conf values used by LoadSettings()."""
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read(REXGEND_CONFIG_FILE)

    def _getint(section: str, key: str, fallback: int, alt_section: str = None) -> int:
        try:
            if parser.has_section(section) and parser.has_option(section, key):
                return parser.getint(section, key)
            if alt_section and parser.has_section(alt_section) and parser.has_option(alt_section, key):
                return parser.getint(alt_section, key)
        except Exception:
            pass
        return fallback

    return {
        "config_path": REXGEND_CONFIG_FILE,
        "use_socketcan": 1 if _getint("Live data", "use_socketcan", REXGEND_DEFAULTS["use_socketcan"]) else 0,
        "use_space_limit": 1 if _getint("Storage", "use_space_limit", REXGEND_DEFAULTS["use_space_limit"]) else 0,
        "max_space_percent": _getint("Storage", "max_space_percent", REXGEND_DEFAULTS["max_space_percent"]),
        "log_errors": 1 if _getint("CAN bus", "log_errors", REXGEND_DEFAULTS["log_errors"], alt_section="Canbus") else 0,
        "use_ntp": 1 if _getint("System", "use_ntp", REXGEND_DEFAULTS["use_ntp"]) else 0,
        "ntp_update_period": _getint("System", "ntp_update_period", REXGEND_DEFAULTS["ntp_update_period"]),
    }


def _save_rexgend_config(data: dict):
    existing = _load_rexgend_config()
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read(REXGEND_CONFIG_FILE)

    def ensure_section(name: str):
        if not parser.has_section(name):
            parser.add_section(name)

    # Keep existing section naming if present.
    can_section = "CAN bus" if parser.has_section("CAN bus") else ("Canbus" if parser.has_section("Canbus") else "CAN bus")

    ensure_section("Live data")
    ensure_section("Storage")
    ensure_section(can_section)
    ensure_section("System")

    # Update only managed keys; preserve all other keys/sections intact.
    parser.set("Live data", "use_socketcan", str(1 if int(data["use_socketcan"]) else 0))
    parser.set("Storage", "use_space_limit", str(1 if int(data["use_space_limit"]) else 0))
    parser.set("Storage", "max_space_percent", str(int(data["max_space_percent"])))
    parser.set(can_section, "log_errors", str(1 if int(data["log_errors"]) else 0))
    # NTP is intentionally not used for now.
    parser.set("System", "use_ntp", "0")
    parser.set("System", "ntp_update_period", str(int(existing.get("ntp_update_period", REXGEND_DEFAULTS["ntp_update_period"]))))

    Path(REXGEND_CONFIG_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(REXGEND_CONFIG_FILE, "w") as f:
        parser.write(f)


def _load_mender_config() -> dict:
    """Load /etc/mender/mender.conf as JSON."""
    try:
        raw = Path(MENDER_CONFIG_FILE).read_text()
    except Exception as e:
        return {
            "config_path": MENDER_CONFIG_FILE,
            "error": f"Failed to read mender config: {e}",
            "config": {}
        }
    try:
        parsed = json.loads(raw) if raw.strip() else {}
        if not isinstance(parsed, dict):
            return {
                "config_path": MENDER_CONFIG_FILE,
                "error": "mender.conf must contain a JSON object",
                "config": {}
            }
        return {
            "config_path": MENDER_CONFIG_FILE,
            "config": parsed
        }
    except Exception as e:
        return {
            "config_path": MENDER_CONFIG_FILE,
            "error": f"Invalid JSON in mender.conf: {e}",
            "config": {}
        }


def _save_mender_config(config_obj: dict):
    Path(MENDER_CONFIG_FILE).parent.mkdir(parents=True, exist_ok=True)
    backup = f"{MENDER_CONFIG_FILE}.bak"
    try:
        if Path(MENDER_CONFIG_FILE).exists():
            Path(backup).write_text(Path(MENDER_CONFIG_FILE).read_text())
    except Exception:
        pass
    with open(MENDER_CONFIG_FILE, "w") as f:
        json.dump(config_obj, f, indent=2, sort_keys=True)
        f.write("\n")


def _collect_service_statuses(force: bool = False) -> list:
    cache = _SERVICE_STATUS_CACHE
    now = time.time()
    if (not force) and cache["items"] and (now - cache["ts"] < SERVICE_STATUS_CACHE_SECONDS):
        return cache["items"]

    active_map = {}
    enabled_map = {}
    try:
        out = subprocess.run(
            ["systemctl", "list-units", "--type=service", "--all", "--no-pager", "--no-legend"],
            capture_output=True, text=True, timeout=6
        ).stdout or ""
        for line in out.splitlines():
            parts = line.split(None, 4)
            if len(parts) >= 4:
                active_map[parts[0]] = parts[2]
    except Exception:
        pass

    try:
        out = subprocess.run(
            ["systemctl", "list-unit-files", "--type=service", "--no-pager", "--no-legend"],
            capture_output=True, text=True, timeout=6
        ).stdout or ""
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                enabled_map[parts[0]] = parts[1]
    except Exception:
        pass

    units = sorted(set(active_map.keys()) | set(enabled_map.keys()))

    items = []
    for unit in units:
        active = active_map.get(unit, "not-found")
        enabled = enabled_map.get(unit, "")
        try:
            if active == "not-found":
                # Fallback probe in case unit is known to systemd but not currently loaded.
                active = subprocess.run(
                    ["systemctl", "is-active", unit],
                    capture_output=True, text=True, timeout=3
                ).stdout.strip() or "unknown"
        except Exception:
            pass
        try:
            if not enabled:
                enabled = subprocess.run(
                    ["systemctl", "is-enabled", unit],
                    capture_output=True, text=True, timeout=3
                ).stdout.strip() or "unknown"
        except Exception:
            enabled = enabled or "unknown"
        items.append({
            "unit": unit,
            "active": active,
            "enabled": enabled or "unknown"
        })

    cache["ts"] = now
    cache["items"] = items
    return items


def _valid_unit_name(unit: str) -> bool:
    return bool(unit and _UNIT_NAME_RE.match(unit))


def _service_detail(unit: str) -> dict:
    if not _valid_unit_name(unit):
        return {"error": "Invalid service name"}

    try:
        out = subprocess.run(
            ["systemctl", "show", unit,
             "--property=Id,Description,LoadState,UnitFileState,ActiveState,SubState,FragmentPath,MainPID,ExecMainStartTimestamp,ExecMainExitTimestamp,MemoryCurrent,TasksCurrent,Restart,ExecMainStatus"],
            capture_output=True, text=True, timeout=6
        ).stdout or ""
    except Exception as e:
        return {"error": f"Failed to read service details: {e}"}

    data = {"unit": unit}
    for line in out.splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k] = v

    if data.get("LoadState") in (None, "", "not-found"):
        return {"error": f"Service '{unit}' not found", "unit": unit}
    return data


def _service_logs(unit: str, lines: int = 120) -> dict:
    if not _valid_unit_name(unit):
        return {"error": "Invalid service name"}
    try:
        n = int(lines)
    except Exception:
        n = 120
    if n < 20:
        n = 20
    if n > 500:
        n = 500
    try:
        out = subprocess.run(
            ["journalctl", "-u", unit, "-n", str(n), "--no-pager", "-o", "short-iso"],
            capture_output=True, text=True, timeout=8
        )
        text = out.stdout or ""
    except Exception as e:
        return {"error": f"Failed to read logs: {e}", "unit": unit}
    return {"unit": unit, "lines": n, "log": text}


def _load_mender_settings() -> dict:
    """Load managed Mender settings as separate fields."""
    payload = _load_mender_config()
    cfg = payload.get("config", {}) if isinstance(payload.get("config"), dict) else {}
    return {
        "config_path": payload.get("config_path", MENDER_CONFIG_FILE),
        "error": payload.get("error"),
        "server_url": cfg.get("ServerURL", ""),
        "tenant_token": cfg.get("TenantToken", ""),
    }


# ========== API Endpoints ==========

@app.route('/heartbeat', methods=['POST'])
def heartbeat():
    _trace(f"POST /heartbeat from={request.remote_addr}")
    wifi_state.heartbeat()
    return '{"status":"ok"}', 200, {'Content-Type': 'application/json'}


@app.route('/api/theme')
def api_theme():
    theme = request.args.get('set', '').strip()
    if theme in ('dark', 'light'):
        _PERSIST_CFG.write_theme(theme)
    return redirect(request.referrer or '/', code=302)



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
        "ap_settings_error": state.get("ap_settings_error"),
        "ap_settings_last_action": state.get("ap_settings_last_action"),
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
    if not _is_ap_client_request(request.remote_addr):
        return jsonify({"error": "SSID connect is allowed only when accessed via AP."}), 403

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


@app.route('/api/ap-settings/password', methods=['POST'])
def api_ap_settings_password():
    _trace(f"POST /api/ap-settings/password from={request.remote_addr}")
    if wifi_state.get("connect_in_progress", False):
        return busy_connect_response()

    data = request.get_json() or {}
    password = (data.get('password') or '').strip()
    valid, error = validate_ap_password(password)
    if not valid:
        return jsonify({"error": error}), 400

    wifi_state.update({
        "ap_settings_error": None,
        "ap_settings_last_action": None
    })
    wifi_state.request_ap_password_change(password)
    return jsonify({"status": "requested"}), 202


@app.route('/api/device-info')
def api_device_info():
    _trace(f"GET /api/device-info from={request.remote_addr}")
    return jsonify(get_device_info())


@app.route('/api/device-status')
def api_device_status():
    _trace(f"GET /api/device-status from={request.remote_addr}")
    return jsonify(get_device_status())


@app.route('/api/device-status/details/<kind>')
def api_device_status_detail(kind):
    _trace(f"GET /api/device-status/details/{kind} from={request.remote_addr}")
    summary_only = request.args.get("summary") == "1"
    data = get_device_status_detail((kind or "").strip().lower(), summary_only=summary_only)
    if data.get("error"):
        return jsonify(data), 400
    return jsonify(data)


@app.route('/api/process-info/<int:pid>')
def api_process_info(pid):
    _trace(f"GET /api/process-info/{pid} from={request.remote_addr}")
    base = f"/proc/{pid}"
    if not os.path.isdir(base):
        return jsonify({"error": f"Process {pid} not found"}), 404
    info = {"pid": pid}
    # cmdline
    try:
        raw = Path(f"{base}/cmdline").read_bytes()
        args = raw.decode("utf-8", errors="replace").split("\x00")
        args = [a for a in args if a]
        info["cmdline"] = " ".join(args) if args else "--"
        comm = _read_text(f"{base}/comm").strip()
        info["name"] = _proc_display_name(raw, comm) if raw else comm
    except Exception:
        info["cmdline"] = "--"
        info["name"] = "--"
    # status fields
    try:
        for line in _read_text(f"{base}/status").splitlines():
            parts = line.split(":\t", 1)
            if len(parts) != 2:
                continue
            key, val = parts[0].strip(), parts[1].strip()
            if key == "State":
                info["state"] = val
            elif key == "PPid":
                info["ppid"] = val
            elif key == "Uid":
                info["uid"] = val.split()[0] if val else "--"
            elif key == "Gid":
                info["gid"] = val.split()[0] if val else "--"
            elif key == "Threads":
                info["threads"] = val
            elif key == "VmPeak":
                info["vm_peak"] = val
            elif key == "VmSize":
                info["vm_size"] = val
            elif key == "VmRSS":
                info["vm_rss"] = val
            elif key == "VmSwap":
                info["vm_swap"] = val
            elif key == "voluntary_ctxt_switches":
                info["vol_ctx"] = val
            elif key == "nonvoluntary_ctxt_switches":
                info["nonvol_ctx"] = val
    except Exception:
        pass
    # stat: start time, cpu times, nice, priority
    try:
        stat_raw = _read_text(f"{base}/stat")
        # Find the closing ')' of comm field to parse reliably
        ci = stat_raw.rfind(")")
        if ci > 0:
            fields = stat_raw[ci + 2:].split()
            if len(fields) >= 20:
                hz = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
                utime = int(fields[11])
                stime = int(fields[12])
                starttime = int(fields[19])
                info["cpu_time"] = f"{round((utime + stime) / hz, 2)}s"
                info["user_time"] = f"{round(utime / hz, 2)}s"
                info["sys_time"] = f"{round(stime / hz, 2)}s"
                # priority (field 15) and nice (field 16) — 0-indexed from after ')'
                if len(fields) >= 17:
                    info["priority"] = fields[15]
                    info["nice"] = fields[16]
                # Calculate process uptime
                try:
                    uptime_s = float(_read_text("/proc/uptime").split()[0])
                    proc_start_s = starttime / hz
                    proc_age = uptime_s - proc_start_s
                    if proc_age >= 86400:
                        info["uptime"] = f"{int(proc_age // 86400)}d {int((proc_age % 86400) // 3600)}h"
                    elif proc_age >= 3600:
                        info["uptime"] = f"{int(proc_age // 3600)}h {int((proc_age % 3600) // 60)}m"
                    elif proc_age >= 60:
                        info["uptime"] = f"{int(proc_age // 60)}m {int(proc_age % 60)}s"
                    else:
                        info["uptime"] = f"{int(proc_age)}s"
                except Exception:
                    pass
    except Exception:
        pass
    # I/O stats from /proc/<pid>/io
    try:
        for line in _read_text(f"{base}/io").splitlines():
            parts = line.split(":", 1)
            if len(parts) != 2:
                continue
            key, val = parts[0].strip(), parts[1].strip()
            if key == "read_bytes":
                info["io_read"] = _format_bytes(int(val))
            elif key == "write_bytes":
                info["io_write"] = _format_bytes(int(val))
    except Exception:
        pass
    # OOM score
    try:
        info["oom_score"] = _read_text(f"{base}/oom_score").strip()
    except Exception:
        pass
    # cwd
    try:
        info["cwd"] = os.readlink(f"{base}/cwd")
    except Exception:
        info["cwd"] = "--"
    # exe
    try:
        info["exe"] = os.readlink(f"{base}/exe")
    except Exception:
        info["exe"] = "--"
    # open file descriptors count
    try:
        info["open_fds"] = str(len(os.listdir(f"{base}/fd")))
    except Exception:
        info["open_fds"] = "--"
    return jsonify(info)


@app.route('/api/rexgend-config', methods=['GET'])
def api_rexgend_config_get():
    _trace(f"GET /api/rexgend-config from={request.remote_addr}")
    return jsonify(_load_rexgend_config())


@app.route('/api/rexgend-config', methods=['POST'])
def api_rexgend_config_save():
    _trace(f"POST /api/rexgend-config from={request.remote_addr}")
    data = request.get_json() or {}
    try:
        cfg = {
            "use_socketcan": 1 if int(data.get("use_socketcan", 0)) else 0,
            "use_space_limit": 1 if int(data.get("use_space_limit", 0)) else 0,
            "max_space_percent": int(data.get("max_space_percent", REXGEND_DEFAULTS["max_space_percent"])),
            "log_errors": 1 if int(data.get("log_errors", 0)) else 0,
            "use_ntp": 1 if int(data.get("use_ntp", 0)) else 0,
            "ntp_update_period": int(data.get("ntp_update_period", REXGEND_DEFAULTS["ntp_update_period"])),
        }
    except Exception:
        return jsonify({"error": "Invalid settings values"}), 400

    if cfg["max_space_percent"] < 1 or cfg["max_space_percent"] > 100:
        return jsonify({"error": "max_space_percent must be 1-100"}), 400

    restart = bool(data.get("restart", False))
    _save_rexgend_config(cfg)

    if restart:
        try:
            subprocess.run(["systemctl", "restart", REXGEND_SERVICE], check=True, timeout=20)
            is_active = subprocess.run(
                ["systemctl", "is-active", REXGEND_SERVICE],
                capture_output=True, text=True, timeout=5
            ).stdout.strip()
            if is_active != "active":
                return jsonify({"error": "rexgend restart requested but service is not active"}), 500
        except Exception as e:
            return jsonify({"error": f"Failed to restart rexgend: {e}"}), 500

    return jsonify({"status": "ok", "restarted": restart})


@app.route('/api/mender-config', methods=['GET'])
def api_mender_config_get():
    _trace(f"GET /api/mender-config from={request.remote_addr}")
    return jsonify(_load_mender_config())


@app.route('/api/mender-config', methods=['POST'])
def api_mender_config_save():
    _trace(f"POST /api/mender-config from={request.remote_addr}")
    data = request.get_json() or {}
    config = data.get("config")
    if not isinstance(config, dict):
        return jsonify({"error": "config must be a JSON object"}), 400

    restart = bool(data.get("restart", False))
    _save_mender_config(config)

    if restart:
        try:
            restarted_units = _restart_mender_services()
        except Exception as e:
            return jsonify({"error": f"Failed to restart mender: {e}"}), 500

    return jsonify({"status": "ok", "restarted": restart, "units": list(restarted_units) if restart else []})


@app.route('/api/mender-settings', methods=['GET'])
def api_mender_settings_get():
    _trace(f"GET /api/mender-settings from={request.remote_addr}")
    return jsonify(_load_mender_settings())


@app.route('/api/mender-settings', methods=['POST'])
def api_mender_settings_save():
    _trace(f"POST /api/mender-settings from={request.remote_addr}")
    data = request.get_json() or {}

    server_url = (data.get("server_url") or "").strip()
    tenant_token = (data.get("tenant_token") or "").strip()

    if not server_url:
        return jsonify({"error": "Server URL is required"}), 400

    loaded = _load_mender_config()
    config = loaded.get("config", {}) if isinstance(loaded.get("config"), dict) else {}

    # Merge-update only managed keys; preserve everything else.
    config["ServerURL"] = server_url
    config["TenantToken"] = tenant_token
    _save_mender_config(config)

    restart = True
    if restart:
        try:
            restarted_units = _restart_mender_services()
        except Exception as e:
            return jsonify({"error": f"Failed to restart mender: {e}"}), 500

    return jsonify({"status": "ok", "restarted": restart, "units": list(restarted_units) if restart else []})


@app.route('/api/account-security', methods=['GET'])
def api_account_security_get():
    auth = _load_or_init_auth_config()
    return jsonify({
        "username": auth.get("username", CONTROL_CENTER_DEFAULT_USER)
    })


@app.route('/api/account-security', methods=['POST'])
def api_account_security_save():
    data = request.get_json() or {}
    current_password = data.get("current_password") or ""
    new_username = (data.get("new_username") or "").strip()
    new_password = data.get("new_password") or ""

    auth = _load_or_init_auth_config()
    current_username = auth.get("username", CONTROL_CENTER_DEFAULT_USER)
    current_hash = auth.get("password_hash", "")

    if (not current_hash) or (not check_password_hash(current_hash, current_password)):
        return jsonify({"error": "Current password is incorrect"}), 400

    if not new_username:
        new_username = current_username
    if len(new_username) < 3 or len(new_username) > 64:
        return jsonify({"error": "Username must be 3-64 characters"}), 400

    final_hash = current_hash
    if new_password:
        if len(new_password) < 8 or len(new_password) > 128:
            return jsonify({"error": "New password must be 8-128 characters"}), 400
        final_hash = _make_password_hash(new_password)

    username_changed = (new_username != current_username)
    password_changed = bool(new_password)
    if (not username_changed) and (not password_changed):
        return jsonify({"error": "No changes to apply"}), 400

    _save_auth_config(new_username, final_hash)
    session["cc_user"] = new_username

    return jsonify({
        "status": "ok",
        "username": new_username,
        "username_changed": username_changed,
        "password_changed": password_changed
    })


# ========== Web Console (PTY + polling) ==========

class _ConsoleSession:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.master_fd = None
        self.proc = None
        self._buf = bytearray()
        self._buf_lock = threading.Lock()
        self.last_access = time.monotonic()
        self._dead = False

    def start(self):
        master_fd, slave_fd = pty.openpty()
        self.master_fd = master_fd
        env = dict(os.environ)
        env.update({'TERM': 'xterm-256color', 'HOME': '/root', 'USER': 'root', 'SHELL': '/bin/bash'})

        def _preexec():
            # Become session leader so bash can acquire a controlling terminal
            # and enable full job control (no "no job control" warnings).
            os.setsid()
            try:
                fcntl.ioctl(0, termios.TIOCSCTTY, 0)
            except Exception:
                pass

        self.proc = subprocess.Popen(
            ['/bin/bash', '-i'],
            stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
            close_fds=True, env=env,
            preexec_fn=_preexec,
        )
        os.close(slave_fd)
        threading.Thread(target=self._read_loop, daemon=True).start()

    def _read_loop(self):
        while not self._dead:
            try:
                r, _, _ = select.select([self.master_fd], [], [], 0.1)
                if r:
                    data = os.read(self.master_fd, 4096)
                    if data:
                        with self._buf_lock:
                            self._buf.extend(data)
                if self.proc and self.proc.poll() is not None:
                    self._dead = True
                    break
            except Exception:
                self._dead = True
                break

    def write(self, data: bytes):
        self.last_access = time.monotonic()
        if not self._dead and self.master_fd is not None:
            try:
                os.write(self.master_fd, data)
            except Exception:
                self._dead = True

    def read(self) -> bytes:
        self.last_access = time.monotonic()
        with self._buf_lock:
            data = bytes(self._buf)
            self._buf.clear()
        return data

    def resize(self, rows: int, cols: int):
        if self.master_fd is not None and not self._dead:
            try:
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ,
                            struct.pack('HHHH', rows, cols, 0, 0))
            except Exception:
                pass

    def close(self):
        self._dead = True
        if self.proc:
            try: self.proc.terminate()
            except Exception: pass
        if self.master_fd is not None:
            try: os.close(self.master_fd)
            except Exception: pass
            self.master_fd = None


_console_sessions: dict = {}
_console_sessions_lock = threading.Lock()


def _console_cleanup_loop():
    while True:
        time.sleep(30)
        with _console_sessions_lock:
            dead = [sid for sid, s in _console_sessions.items()
                    if s._dead or (time.monotonic() - s.last_access) > 600]
            for sid in dead:
                try: _console_sessions[sid].close()
                except Exception: pass
                del _console_sessions[sid]


threading.Thread(target=_console_cleanup_loop, daemon=True, name="console-cleanup").start()


@app.route('/terminal')
def terminal_page():
    return render_template('terminal.html')


@app.route('/api/console/start', methods=['POST'])
def api_console_start():
    d = request.get_json() or {}
    root_password = d.get('root_password') or ''
    if not root_password:
        return jsonify({'error': 'Root password is required'}), 401
    if not _verify_root_password(root_password):
        return jsonify({'error': 'Incorrect root password'}), 401
    sess = _ConsoleSession()
    try:
        sess.start()
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    with _console_sessions_lock:
        _console_sessions[sess.id] = sess
    return jsonify({'session_id': sess.id, 'dead': False})


@app.route('/api/console/output')
def api_console_output():
    sid = request.args.get('session_id', '')
    with _console_sessions_lock:
        sess = _console_sessions.get(sid)
    if not sess:
        return jsonify({'error': 'Session not found'}), 404
    data = sess.read()
    return jsonify({'data': base64.b64encode(data).decode(), 'dead': sess._dead})


@app.route('/api/console/input', methods=['POST'])
def api_console_input():
    d = request.get_json() or {}
    sid = d.get('session_id', '')
    data = d.get('data', '')
    with _console_sessions_lock:
        sess = _console_sessions.get(sid)
    if not sess:
        return jsonify({'error': 'Session not found'}), 404
    if isinstance(data, str):
        sess.write(data.encode('utf-8'))
    return jsonify({'ok': True})


@app.route('/api/console/resize', methods=['POST'])
def api_console_resize():
    d = request.get_json() or {}
    sid = d.get('session_id', '')
    rows = max(1, int(d.get('rows', 24)))
    cols = max(1, int(d.get('cols', 80)))
    with _console_sessions_lock:
        sess = _console_sessions.get(sid)
    if not sess:
        return jsonify({'error': 'Session not found'}), 404
    sess.resize(rows, cols)
    return jsonify({'ok': True})


@app.route('/api/console/close', methods=['POST'])
def api_console_close():
    d = request.get_json() or {}
    sid = d.get('session_id', '')
    with _console_sessions_lock:
        sess = _console_sessions.pop(sid, None)
    if sess:
        sess.close()
    return jsonify({'ok': True})


def _verify_root_password(password: str) -> bool:
    """Verify password against root's entry in /etc/shadow."""
    try:
        with open("/etc/shadow", "r") as f:
            for line in f:
                parts = line.strip().split(":")
                if len(parts) >= 2 and parts[0] == "root":
                    stored = parts[1]
                    if stored in ("", "!", "*", "!*", "!!", "x"):
                        return False  # locked or no password
                    return crypt.crypt(password, stored) == stored
    except Exception:
        pass
    return False


@app.route('/api/root-password', methods=['POST'])
def api_root_password():
    data = request.get_json() or {}
    current_root_password = data.get("current_password") or ""
    new_root_password = data.get("new_root_password") or ""

    if not current_root_password:
        return jsonify({"error": "Current root password is required"}), 400
    if not _verify_root_password(current_root_password):
        return jsonify({"error": "Current root password is incorrect"}), 400

    if not new_root_password:
        return jsonify({"error": "New root password is required"}), 400
    if len(new_root_password) < 8:
        return jsonify({"error": "Root password must be at least 8 characters"}), 400
    if len(new_root_password) > 128:
        return jsonify({"error": "Root password must be at most 128 characters"}), 400

    try:
        result = subprocess.run(
            ["chpasswd"],
            input=f"root:{new_root_password}\n",
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            err = result.stderr.strip() or "unknown error"
            return jsonify({"error": f"chpasswd failed: {err}"}), 500
    except Exception as e:
        return jsonify({"error": f"Failed to change root password: {e}"}), 500

    return jsonify({"status": "ok"})


def _ssh_control_unit() -> dict:
    """
    Return the best systemd unit to control SSH access.
    Prefer socket-activated SSH first (e.g. sshd.socket on ReXgen), then service units.
    """
    candidates = [
        ("sshd.socket", "socket"),
        ("sshd.service", "service"),
        ("dropbear.service", "service"),
        ("ssh.service", "service"),
        ("openssh.service", "service"),
        ("openssh-server.service", "service"),
        ("dropbear.socket", "socket"),
        ("ssh.socket", "socket"),
    ]
    for unit, kind in candidates:
        try:
            r = subprocess.run(
                ["systemctl", "show", "--no-pager", "--property=LoadState", unit],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0 and "LoadState=loaded" in (r.stdout or ""):
                return {"unit": unit, "kind": kind}
        except Exception:
            pass
    return {}


def _systemctl_state(cmd: str, unit: str, timeout: int = 5) -> str:
    try:
        r = subprocess.run(["systemctl", cmd, unit], capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "").strip() or (r.stderr or "").strip() or "unknown"
    except Exception:
        return "unknown"


def _is_enabled_state(value: str) -> bool:
    return value in ("enabled", "enabled-runtime", "static", "alias", "indirect", "generated")


def _terminate_daemon_by_name(name: str):
    """Best-effort terminate by daemon name without requiring pkill."""
    # First try killall (available on many embedded builds).
    try:
        subprocess.run(["killall", name], capture_output=True, text=True, timeout=5)
    except Exception:
        pass
    # Fallback to pidof + kill in Python for systems without killall/pkill.
    try:
        out = subprocess.run(["pidof", name], capture_output=True, text=True, timeout=5)
        pids = [p.strip() for p in (out.stdout or "").split() if p.strip().isdigit()]
        for pid_s in pids:
            try:
                os.kill(int(pid_s), signal.SIGTERM)
            except Exception:
                pass
    except Exception:
        pass


def _apply_ssh_state(enable: bool, unit: str, kind: str):
    if enable:
        # enable may fail on read-only rootfs — that's OK; start is the critical part
        subprocess.run(["systemctl", "enable", unit], capture_output=True, text=True, timeout=10)
        subprocess.run(["systemctl", "start", unit], capture_output=True, text=True, timeout=15, check=True)
        return

    subprocess.run(["systemctl", "stop", unit], capture_output=True, text=True, timeout=15, check=True)
    subprocess.run(["systemctl", "disable", unit], capture_output=True, text=True, timeout=10)
    # Enforce access disable immediately by terminating any active SSH daemons/sessions.
    for proc in ("sshd", "dropbear"):
        _terminate_daemon_by_name(proc)
    if kind == "socket":
        # Best-effort: stop associated service unit as well when socket-activated SSH is used.
        stem = unit.split(".", 1)[0]
        subprocess.run(["systemctl", "stop", f"{stem}.service"], capture_output=True, text=True, timeout=10)


@app.route('/api/ssh-status', methods=['GET'])
def api_ssh_status_get():
    ctl = _ssh_control_unit()
    if not ctl:
        return jsonify({"available": False})
    unit = ctl["unit"]
    settings = _load_or_init_system_settings()
    desired_enabled = bool(settings.get("ssh_enabled", True))
    enabled_state = _systemctl_state("is-enabled", unit)
    active_state = _systemctl_state("is-active", unit)
    active = active_state == "active"
    enabled = active or _is_enabled_state(enabled_state)
    return jsonify({
        "available": True,
        "unit": unit,
        "kind": ctl["kind"],
        "enabled": enabled,
        "desired_enabled": desired_enabled,
        "active": active,
        "enabled_state": enabled_state,
        "active_state": active_state,
    })


@app.route('/api/ssh-status', methods=['POST'])
def api_ssh_status_set():
    data = request.get_json() or {}
    enable = bool(data.get("enabled", False))
    persist = bool(data.get("persist", True))
    ctl = _ssh_control_unit()
    if not ctl:
        return jsonify({"error": "SSH service not found on this device"}), 404
    unit = ctl["unit"]
    kind = ctl["kind"]
    try:
        _apply_ssh_state(enable, unit, kind)
        if persist:
            _save_system_settings({"ssh_enabled": enable})
    except subprocess.CalledProcessError as e:
        return jsonify({"error": (e.stderr or "").strip() or f"Failed to {'start' if enable else 'stop'} SSH"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    enabled_state = _systemctl_state("is-enabled", unit)
    active_state = _systemctl_state("is-active", unit)
    active = active_state == "active"
    now_enabled = active or _is_enabled_state(enabled_state)
    return jsonify({
        "status": "ok",
        "requested_enabled": enable,
        "persisted": persist,
        "enabled": now_enabled,
        "active": active,
        "unit": unit,
        "kind": kind,
        "enabled_state": enabled_state,
        "active_state": active_state,
    })


def _apply_persisted_ssh_state_on_startup():
    settings = _load_or_init_system_settings()
    desired = bool(settings.get("ssh_enabled", True))
    ctl = _ssh_control_unit()
    if not ctl:
        log.warning(f"SSH control unit not found; persisted SSH state skipped (desired={desired})")
        return
    try:
        _apply_ssh_state(desired, ctl["unit"], ctl["kind"])
        log.info(f"Applied persisted SSH state on startup: unit={ctl['unit']} enabled={desired}")
    except Exception as e:
        log.error(f"Failed to apply persisted SSH state on startup: {e}")


@app.route('/api/https-settings', methods=['GET', 'POST'])
def api_https_settings():
    if request.method == 'GET':
        settings = _load_or_init_settings()
        effective = _configured_https_hostname(settings)
        return jsonify({
            "https_enabled": settings.get("https_enabled", False),
            "https_hostname": settings.get("https_hostname", ""),
            "https_hostname_default": _default_https_hostname(),
            "https_hostname_effective": effective,
        })
    data = request.get_json() or {}
    if "https_enabled" not in data:
        return jsonify({"error": "Missing https_enabled field"}), 400
    old_settings = _load_or_init_settings()
    old_effective = _configured_https_hostname(old_settings)
    old_enabled = bool(old_settings.get("https_enabled", False))
    enabled = bool(data["https_enabled"])
    hostname = _normalize_https_hostname(data.get("https_hostname") or "")
    if hostname:
        if len(hostname) > 253:
            return jsonify({"error": "Hostname must be 1-253 chars"}), 400
        if (not re.fullmatch(r"[a-z0-9.-]+", hostname)) or (".." in hostname) or hostname.startswith("-") or hostname.endswith("-") or hostname.startswith(".") or hostname.endswith("."):
            return jsonify({"error": "Hostname contains invalid characters"}), 400
    _save_settings({"https_enabled": enabled, "https_hostname": hostname})
    _invalidate_settings_cache()
    settings_now = _load_or_init_settings()
    effective = _configured_https_hostname(settings_now)
    try:
        # Always apply effective host so clearing hostname reverts mDNS to default serial hostname.
        _apply_mdns_hostname_from_effective(effective)
    except Exception as e:
        return jsonify({"error": f"Failed to apply mDNS hostname: {e}"}), 500
    hostname_changed = (effective != old_effective)
    # Regenerate server cert when HTTPS is active and host identity or mode changed.
    if enabled and (hostname_changed or (enabled != old_enabled)):
        try:
            _ensure_ssl_cert(force_regen=True)
        except Exception as e:
            return jsonify({"error": f"Failed to prepare HTTPS certificate: {e}"}), 500

    restart_requested = bool(data.get("restart", False))
    if restart_requested:
        try:
            subprocess.Popen(
                ["/bin/sh", "-c", f"sleep 1; systemctl restart {WIFI_DASHBOARD_SERVICE}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            return jsonify({"error": f"Failed to restart dashboard: {e}"}), 500

    scheme = "https" if enabled else "http"
    redirect_url = f"{scheme}://{effective}/" if effective else _dashboard_url()
    return jsonify({
        "ok": True,
        "message": "Saved. Restarting dashboard..." if restart_requested else "Saved. Restart dashboard service to apply.",
        "https_hostname_effective": effective,
        "redirect_url": redirect_url,
        "restart_scheduled": restart_requested,
    })


@app.route('/install-certificate')
def install_certificate():
    return render_template('install_certificate.html')


@app.route('/host-switch')
def host_switch():
    target = (request.args.get("target") or "").strip()
    if not target.startswith("https://"):
        target = _dashboard_url()
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Switching Hostname</title></head>
<body style="font-family:Segoe UI,system-ui,sans-serif;padding:22px;line-height:1.5">
<h3>Applying new HTTPS hostname...</h3>
<p>Trying to open: <b>{target}</b></p>
<p>If it does not open automatically, wait a few seconds for mDNS and tap this link:</p>
<p><a id="target" href="{target}">{target}</a></p>
<script>
var t = {json.dumps(target)};
setTimeout(function() {{ window.location.replace(t); }}, 1500);
setTimeout(function() {{ window.location.replace(t); }}, 4500);
</script>
</body></html>"""


@app.route('/updating')
def updating_page():
    return render_template("updating.html")


@app.route('/api/update-status')
def api_update_status():
    return jsonify({"updating": _is_fw_upgrade_in_progress()})


@app.route('/download-ca-cert')
def download_ca_cert():
    if not SSL_CA_FILE.exists():
        return "Certificate not available", 404
    response = make_response(SSL_CA_FILE.read_bytes())
    response.headers['Content-Type'] = 'application/x-x509-ca-cert'
    response.headers['Content-Disposition'] = 'attachment; filename="rexgen-ca.crt"'
    return response


@app.route('/api/system/reboot', methods=['POST'])
def api_system_reboot():
    _trace(f"POST /api/system/reboot from={request.remote_addr}")
    try:
        subprocess.Popen(["reboot"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return jsonify({"ok": True, "message": "Rebooting..."})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/system/restart-dashboard', methods=['POST'])
def api_system_restart_dashboard():
    _trace(f"POST /api/system/restart-dashboard from={request.remote_addr}")
    try:
        # Run restart asynchronously so this request can return before the process is replaced.
        subprocess.Popen(
            ["/bin/sh", "-c", f"sleep 1; systemctl restart {WIFI_DASHBOARD_SERVICE}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return jsonify({
            "ok": True,
            "message": f"Restarting {WIFI_DASHBOARD_SERVICE}...",
            "redirect_url": _dashboard_url(),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/system-services', methods=['GET'])
def api_system_services():
    _trace(f"GET /api/system-services from={request.remote_addr}")
    force = request.args.get("force", "0") == "1"
    status_filter = (request.args.get("status", "all") or "all").strip().lower()
    all_items = _collect_service_statuses(force=force)

    summary = {
        "total": len(all_items),
        "active": 0,
        "inactive": 0,
        "failed": 0,
        "activating": 0,
        "deactivating": 0,
        "other": 0,
        "unknown": 0,
    }

    for item in all_items:
        state = (item.get("active") or "unknown").strip().lower()
        if state in ("active", "inactive", "failed", "activating", "deactivating"):
            summary[state] += 1
        elif state in ("unknown", "not-found"):
            summary["unknown"] += 1
        else:
            summary["other"] += 1

    valid_filters = {"all", "active", "inactive", "failed", "activating", "deactivating", "unknown", "other"}
    if status_filter not in valid_filters:
        status_filter = "all"

    if status_filter == "all":
        items = all_items
    elif status_filter == "unknown":
        items = [i for i in all_items if (i.get("active") or "").strip().lower() in ("unknown", "not-found")]
    elif status_filter == "other":
        items = [
            i for i in all_items
            if (i.get("active") or "").strip().lower()
            not in ("active", "inactive", "failed", "activating", "deactivating", "unknown", "not-found")
        ]
    else:
        items = [i for i in all_items if (i.get("active") or "").strip().lower() == status_filter]

    return jsonify({
        "updated_at": int(time.time()),
        "cache_seconds": SERVICE_STATUS_CACHE_SECONDS,
        "count": len(items),
        "total_count": len(all_items),
        "status_filter": status_filter,
        "summary": summary,
        "services": items
    })


@app.route('/api/system-services/<path:unit>', methods=['GET'])
def api_system_service_detail(unit):
    _trace(f"GET /api/system-services/{unit} from={request.remote_addr}")
    detail = _service_detail(unit)
    if detail.get("error"):
        return jsonify(detail), 404
    return jsonify(detail)


@app.route('/api/system-services/<path:unit>/logs', methods=['GET'])
def api_system_service_logs(unit):
    _trace(f"GET /api/system-services/{unit}/logs from={request.remote_addr}")
    lines = request.args.get("lines", "120")
    logs = _service_logs(unit, lines=int(lines) if str(lines).isdigit() else 120)
    if logs.get("error"):
        return jsonify(logs), 400
    return jsonify(logs)


# ========== Pipe Readers (rexgend /var/run/rexgen) ==========

REXGEN_PIPE_DIR = "/var/run/rexgen"

class _PipeReader:
    """Background thread that tails a named pipe and buffers the last N lines."""
    def __init__(self, path: str):
        self.path = path
        self._lines: collections.deque = collections.deque(maxlen=300)
        self._seq = 0
        self._lock = threading.Lock()
        self._active = True
        self._partial = ""
        self.last_access = time.time()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while self._active:
            try:
                fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK)
                try:
                    eof_streak = 0
                    while self._active:
                        r, _, _ = select.select([fd], [], [], 0.5)
                        if not r:
                            continue
                        try:
                            data = os.read(fd, 8192)
                        except BlockingIOError:
                            continue
                        if not data:
                            eof_streak += 1
                            if eof_streak >= 4:
                                break  # writer gone, reopen
                            time.sleep(0.25)
                            continue
                        eof_streak = 0
                        text = self._partial + data.decode("utf-8", errors="replace")
                        lines = text.split("\n")
                        self._partial = lines[-1]
                        with self._lock:
                            for line in lines[:-1]:
                                if line.strip():
                                    self._seq += 1
                                    self._lines.append({"seq": self._seq, "text": line})
                finally:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
            except (FileNotFoundError, PermissionError):
                pass
            except Exception:
                pass
            if self._active:
                time.sleep(1)

    def read_since(self, seq: int) -> list:
        self.last_access = time.time()
        with self._lock:
            return [l for l in self._lines if l["seq"] > seq]

    @property
    def last_seq(self) -> int:
        with self._lock:
            return self._seq

    def stop(self):
        self._active = False


_pipe_readers: dict = {}
_pipe_readers_lock = threading.Lock()


def _get_pipe_reader(pipe_rel: str) -> "_PipeReader":
    full = os.path.join(REXGEN_PIPE_DIR, pipe_rel)
    with _pipe_readers_lock:
        if pipe_rel not in _pipe_readers:
            _pipe_readers[pipe_rel] = _PipeReader(full)
        return _pipe_readers[pipe_rel]


def _pipe_reader_cleanup_loop():
    while True:
        time.sleep(60)
        now = time.time()
        with _pipe_readers_lock:
            stale = [k for k, v in _pipe_readers.items() if now - v.last_access > 300]
            for k in stale:
                _pipe_readers[k].stop()
                del _pipe_readers[k]


threading.Thread(target=_pipe_reader_cleanup_loop, daemon=True).start()


def _list_rexgen_pipes() -> list:
    pipes = []
    try:
        if not os.path.isdir(REXGEN_PIPE_DIR):
            return pipes
        for entry in sorted(os.listdir(REXGEN_PIPE_DIR)):
            full = os.path.join(REXGEN_PIPE_DIR, entry)
            if os.path.isdir(full):
                for sub in ("rx", "tx", "err"):
                    p = os.path.join(full, sub)
                    if os.path.exists(p):
                        pipes.append({
                            "path": f"{entry}/{sub}",
                            "channel": entry,
                            "type": sub,
                            "readable": sub != "tx",
                        })
            elif os.path.exists(full) and (os.path.isfile(full) or stat_is_fifo(full)):
                pipes.append({
                    "path": entry,
                    "channel": entry,
                    "type": "sys",
                    "readable": True,
                })
    except Exception:
        pass
    return pipes


def stat_is_fifo(path: str) -> bool:
    try:
        import stat as _stat
        return _stat.S_ISFIFO(os.stat(path).st_mode)
    except Exception:
        return False


@app.route('/api/pipes')
def api_pipes_list():
    _trace(f"GET /api/pipes from={request.remote_addr}")
    pipes = _list_rexgen_pipes()
    return jsonify({"pipes": pipes, "base": REXGEN_PIPE_DIR})


@app.route('/api/pipes/read')
def api_pipes_read():
    pipe_path = request.args.get("pipe", "")
    try:
        seq = int(request.args.get("seq", 0))
    except ValueError:
        seq = 0
    if not pipe_path or ".." in pipe_path or pipe_path.startswith("/"):
        return jsonify({"error": "Invalid pipe path"}), 400
    reader = _get_pipe_reader(pipe_path)
    lines = reader.read_since(seq)
    return jsonify({"lines": lines, "seq": reader.last_seq})


# ========== Web Pages ==========

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if _is_authenticated():
        return redirect('/', code=302)

    error = ""
    next_path = request.args.get("next", "")
    settings = _load_or_init_settings()
    req_host = (request.host or "").split(":", 1)[0].strip().lower()
    ap_http_upgrade = bool(settings.get("https_enabled", False)) and (not request.is_secure) and (req_host == "192.168.51.1")
    ap_secure_target = "https://192.168.51.1/login"
    if request.method == "POST":
        next_path = request.form.get("next", next_path)
        if not _is_safe_next_path(next_path):
            next_path = "/"

        client = _client_key()
        locked_left = _get_login_lock_seconds_left(client)
        if locked_left > 0:
            error = f"Too many failed attempts. Try again in {locked_left}s."
            return render_template(
                "login.html",
                error=error,
                next_path=next_path,
                ap_http_upgrade=ap_http_upgrade,
                ap_secure_target=ap_secure_target,
            )

        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        auth = _load_or_init_auth_config()
        expected_user = auth.get("username") or ""
        expected_hash = auth.get("password_hash") or ""

        user_ok = hmac.compare_digest(username, expected_user)
        pass_ok = check_password_hash(expected_hash, password) if expected_hash else False
        if user_ok and pass_ok:
            session.clear()
            session["cc_auth"] = True
            session["cc_user"] = username
            session["cc_login_ts"] = int(time.time())
            session.permanent = True
            _clear_login_failures(client)
            return redirect(next_path or "/", code=302)

        _register_login_failure(client)
        error = "Invalid username or password."

    if not _is_safe_next_path(next_path):
        next_path = "/"
    return render_template(
        "login.html",
        error=error,
        next_path=next_path,
        ap_http_upgrade=ap_http_upgrade,
        ap_secure_target=ap_secure_target,
    )


@app.route('/logout')
def logout_page():
    session.clear()
    return redirect('/login', code=302)

@app.route('/')
def home():
    # Smart home: AP clients land on WiFi setup; other interfaces land on Device information.
    if _is_ap_client_request(request.remote_addr):
        return redirect('/wifi-settings', code=302)
    return redirect('/device-info', code=302)


@app.route('/wifi-settings')
def index():
    networks = wifi_state.get("networks", [])
    return render_template(
        "wifi_settings.html",
        networks=networks,
        show_back=(not _is_ap_client_request(request.remote_addr)),
        connect_allowed=_is_ap_client_request(request.remote_addr)
    )


@app.route('/saved-networks')
def saved_networks_page():
    return render_template("manage_networks.html")


@app.route('/wifi-network-info')
def wifi_network_info_page():
    return render_template("wifi_network_info.html")


@app.route('/device-info')
def device_info_page():
    return render_template("device_info.html")


@app.route('/services')
def services_page():
    return render_template("services.html")


@app.route('/hardware-detail')
def hardware_detail_page():
    kind = (request.args.get("kind") or "cpu").strip().lower()
    destinations = {"cpu": "/cpu-detail", "memory": "/memory-detail", "disk": "/disk-detail"}
    return redirect(destinations.get(kind, "/cpu-detail"), code=302)


@app.route('/cpu-detail')
def cpu_detail_page():
    return render_template("cpu_detail.html")


@app.route('/memory-detail')
def memory_detail_page():
    return render_template("memory_detail.html")


@app.route('/disk-detail')
def disk_detail_page():
    return render_template("disk_detail.html")


@app.route('/ap-settings')
def ap_settings_page():
    return render_template("ap_settings.html")


@app.route('/ap-client-info')
def ap_client_info_page():
    return render_template("ap_client_info.html")


@app.route('/ap-password')
def ap_password_page():
    return redirect('/ap-settings', code=302)


@app.route('/rexgend-settings')
def rexgend_settings_page():
    return render_template("rexgend_settings.html")


@app.route('/pipe-output')
def pipe_output_page():
    pipe = request.args.get("pipe", "")
    return render_template("pipe_output.html", pipe=pipe)


@app.route('/mender-settings')
def mender_settings_page():
    return redirect('/system-settings', code=302)


@app.route('/system-settings')
def system_settings_page():
    return render_template("system_settings.html")


@app.route('/service-info')
def service_info_page():
    return render_template("service_info.html")


@app.route('/process-info')
def process_info_page():
    return render_template("process_info.html")


@app.route('/rexgen-settings')
def rexgen_settings_page():
    return redirect('/rexgend-settings', code=302)


@app.route('/configure_wifi', methods=['POST'])
def configure_wifi():
    if not _is_ap_client_request(request.remote_addr):
        return "SSID connect is allowed only when accessed via AP.", 403

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

def _captive_portal_url():
    # Use current local host when valid (e.g. LAN access on 192.168.11.x),
    # but fall back to AP address for captive probe domains.
    try:
        req_host = (request.host or "").strip().split(":", 1)[0].strip().lower()
    except RuntimeError:
        req_host = ""

    if req_host:
        try:
            ip = ipaddress.ip_address(req_host)
            if isinstance(ip, ipaddress.IPv4Address):
                if ip.is_private or ip.is_loopback:
                    return f"http://{req_host}/"
        except Exception:
            try:
                local_names = {"localhost"}
                host = socket.gethostname().strip().lower()
                if host:
                    local_names.add(host)
                    if "." not in host:
                        local_names.add(f"{host}.local")
                cfg = _configured_https_hostname()
                if cfg:
                    local_names.add(cfg.lower())
                if req_host in local_names:
                    return f"http://{req_host}/"
            except Exception:
                pass

    return "http://192.168.51.1/"


def _dashboard_url():
    """Return the dashboard root URL using the correct scheme for the current mode."""
    settings = _load_or_init_settings()
    scheme = "https" if settings.get("https_enabled", False) else "http"
    host = _configured_https_hostname(settings) if scheme == "https" else ""
    try:
        req_host = (request.host or "").strip()
        if req_host:
            req = req_host.split(":", 1)[0] or ""
            if req and not host:
                host = req
    except RuntimeError:
        pass
    if (not host) and scheme == "https":
        host = _configured_https_hostname(settings)
    if not host:
        host = "192.168.51.1"
    return f"{scheme}://{host}/"


# Android connectivity check
@app.route('/generate_204')
@app.route('/gen_204')
def android_captive():
    return redirect(_captive_portal_url(), code=302)

# iOS/Apple connectivity check
@app.route('/hotspot-detect.html')
@app.route('/library/test/success.html')
def ios_captive():
    return redirect(_captive_portal_url(), code=302)

# Windows connectivity check
@app.route('/ncsi.txt')
@app.route('/connecttest.txt')
def windows_captive():
    return redirect(_captive_portal_url(), code=302)

# General captive portal
@app.route('/chat', methods=['GET', 'POST'])
def captive_redirect():
    return redirect(_captive_portal_url(), code=302)


@app.route('/favicon.ico')
def favicon():
    return ('', 204)


@app.route('/<path:path>')
def catch_all(path):
    return redirect(_dashboard_url(), code=302)


@app.errorhandler(404)
def not_found(e):
    return redirect(_dashboard_url(), code=302)


# ========== SSL / HTTPS ==========

def _server_cert_sans() -> str:
    sans = {"IP:127.0.0.1", "IP:192.168.51.1", "DNS:localhost"}
    seen_ips = set()

    def _add_ip(token: str):
        t = (token or "").strip()
        if not t:
            return
        if "/" in t:
            t = t.split("/", 1)[0]
        try:
            ip = ipaddress.ip_address(t)
        except Exception:
            return
        if isinstance(ip, ipaddress.IPv4Address):
            c = ip.compressed
            if c not in seen_ips:
                seen_ips.add(c)
                sans.add(f"IP:{c}")

    try:
        out = subprocess.run(
            ["hostname", "-I"],
            check=True,
            timeout=5,
            capture_output=True,
            text=True,
        ).stdout
        for token in out.split():
            _add_ip(token)
    except Exception:
        pass
    try:
        out = subprocess.run(
            ["ip", "-4", "-o", "addr", "show", "scope", "global"],
            check=True,
            timeout=5,
            capture_output=True,
            text=True,
        ).stdout
        for line in out.splitlines():
            m = re.search(r"\binet\s+([0-9.]+(?:/[0-9]+)?)\b", line)
            if m:
                _add_ip(m.group(1))
    except Exception:
        pass
    try:
        host = socket.gethostname().strip()
        if host:
            sans.add(f"DNS:{host}")
            if "." not in host:
                sans.add(f"DNS:{host}.local")
    except Exception:
        pass
    cfg_host = _configured_https_hostname()
    if cfg_host:
        sans.add(f"DNS:{cfg_host}")
    return ",".join(sorted(sans))


def _generate_server_cert():
    """Generate a server key and sign it with the pre-installed CA."""
    csr_file = SSL_CERT_DIR / "dashboard.csr"
    ext_file = SSL_CERT_DIR / "dashboard.ext"
    cn = _configured_https_hostname() or "192.168.51.1"
    try:
        subprocess.run([
            "openssl", "genrsa", "-out", str(SSL_KEY_FILE), "2048"
        ], check=True, timeout=30, capture_output=True)
        subprocess.run([
            "openssl", "req", "-new",
            "-key", str(SSL_KEY_FILE),
            "-out", str(csr_file),
            "-subj", f"/CN={cn}/O=ReXgen"
        ], check=True, timeout=30, capture_output=True)
        ext_file.write_text(
            f"subjectAltName={_server_cert_sans()}\n"
            "basicConstraints=CA:FALSE\n"
            "keyUsage=digitalSignature,keyEncipherment\n"
            "extendedKeyUsage=serverAuth\n"
        )
        subprocess.run([
            "openssl", "x509", "-req",
            "-in", str(csr_file),
            "-CA", str(SSL_CA_FILE),
            "-CAkey", str(SSL_CA_KEY_FILE),
            "-CAcreateserial",
            "-out", str(SSL_CERT_FILE),
            "-days", "3650", "-sha256",
            "-extfile", str(ext_file)
        ], check=True, timeout=30, capture_output=True)
    finally:
        csr_file.unlink(missing_ok=True)
        ext_file.unlink(missing_ok=True)


def _generate_ca():
    """Generate a new CA key and cert. Only used as fallback when no CA is pre-installed."""
    subprocess.run([
        "openssl", "genrsa", "-out", str(SSL_CA_KEY_FILE), "2048"
    ], check=True, timeout=30, capture_output=True)
    subprocess.run([
        "openssl", "req", "-x509", "-new", "-nodes",
        "-key", str(SSL_CA_KEY_FILE),
        "-sha256", "-days", "3650",
        "-out", str(SSL_CA_FILE),
        "-subj", "/CN=ReXgen Control Center CA/O=ReXgen"
    ], check=True, timeout=30, capture_output=True)


def _ensure_ssl_cert(force_regen: bool = False):
    """Ensure a valid server certificate exists, signed by the company CA.

    Production flow (Option A — CA baked into firmware):
      ca.crt + ca.key are pre-installed in the firmware image.
      On first boot this function generates only the server key/cert using the
      pre-installed CA — every device gets a unique server cert, all trusted by
      the same company CA root that users install once.

    Development fallback:
      If no CA is present, a new CA is generated locally. This should not happen
      on production devices where the CA is shipped with the firmware image.
    """
    if (not force_regen) and SSL_CA_FILE.exists() and SSL_CERT_FILE.exists() and SSL_KEY_FILE.exists():
        try:
            verify = subprocess.run(
                ["openssl", "verify", "-CAfile", str(SSL_CA_FILE), str(SSL_CERT_FILE)],
                check=False,
                timeout=10,
                capture_output=True,
                text=True,
            )
            if verify.returncode == 0:
                log.info("SSL certificates already exist and verify against CA")
                return
            log.warning(f"Existing SSL cert does not verify against CA; regenerating: {verify.stderr.strip() or verify.stdout.strip()}")
        except Exception as e:
            log.warning(f"Failed to verify existing SSL cert; regenerating: {e}")
    SSL_CERT_DIR.mkdir(parents=True, exist_ok=True)
    # Remove stale server cert so it gets re-signed with the current CA
    for f in (SSL_CERT_FILE, SSL_KEY_FILE):
        f.unlink(missing_ok=True)
    try:
        if not SSL_CA_FILE.exists():
            log.warning("No CA found — generating a new one (development fallback)")
            _generate_ca()
        log.info("Generating SSL server certificate signed by CA...")
        _generate_server_cert()
        log.info("SSL server certificate generated")
    except Exception as e:
        log.error(f"Failed to generate SSL certificate: {e}")
        raise


# ========== Main ==========

if __name__ == "__main__":
    _apply_persisted_ssh_state_on_startup()
    settings = _load_or_init_settings()
    https_enabled = settings.get("https_enabled", False)
    if https_enabled:
        _ensure_ssl_cert()
        http_server = make_server("0.0.0.0", DASHBOARD_HTTP_PORT, app, threaded=True)
        http_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
        http_thread.start()
        https_server = make_server(
            "0.0.0.0",
            DASHBOARD_PORT,
            app,
            threaded=True,
            ssl_context=(str(SSL_CERT_FILE), str(SSL_KEY_FILE)),
        )
        try:
            https_server.serve_forever()
        finally:
            http_server.shutdown()
            https_server.shutdown()
    else:
        app.run(host='0.0.0.0', port=DASHBOARD_HTTP_PORT, threaded=True, debug=False)
