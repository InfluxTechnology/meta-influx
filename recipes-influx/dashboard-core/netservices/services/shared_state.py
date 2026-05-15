#!/usr/bin/env python3
"""
Shared State Module
IPC between WiFi Manager and Dashboard services via JSON file
"""

import json
import os
import threading
import time
import logging
from pathlib import Path

try:
    from .constants_paths import REXGEN_TMP_DIR, WIFI_STATE_FILE
    from .constants_runtime import HEARTBEAT_TIMEOUT_SECONDS, TRACE_VERBOSE
except ImportError:
    from constants_paths import REXGEN_TMP_DIR, WIFI_STATE_FILE
    from constants_runtime import HEARTBEAT_TIMEOUT_SECONDS, TRACE_VERBOSE

# ========== Configuration ==========

# State file location — /data/rexgen/tmp persists across reboots and Mender OTA updates
STATE_DIR = REXGEN_TMP_DIR
STATE_FILE = WIFI_STATE_FILE

# Heartbeat timeout (seconds)
HEARTBEAT_TIMEOUT = HEARTBEAT_TIMEOUT_SECONDS
log = logging.getLogger("shared_state")


class WifiState:
    """Thread-safe shared state between services"""

    def __init__(self):
        self._lock = threading.Lock()
        self._ensure_state_dir()

    @staticmethod
    def _trace(msg: str):
        if TRACE_VERBOSE:
            log.info(f"[TRACE][STATE] {msg}")

    def _ensure_state_dir(self):
        """Create state directory if it doesn't exist"""
        Path(STATE_DIR).mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict:
        """Read state from file"""
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return self._default_state()

    def _write(self, state: dict):
        """Write state to file atomically"""
        temp_file = f"{STATE_FILE}.tmp"
        os.makedirs(os.path.dirname(temp_file), exist_ok=True)
        with open(temp_file, 'w') as f:
            json.dump(state, f, indent=2)
        os.rename(temp_file, STATE_FILE)

    def _default_state(self) -> dict:
        """Default state structure"""
        return {
            "networks": [],
            "connected_ssid": None,
            "ap_mode": False,
            "last_scan": 0,
            "last_heartbeat": 0,
            "ip_address": None,
            "serial_number": None
        }

    def get(self, key: str, default=None):
        """Get a single value from state"""
        with self._lock:
            state = self._read()
            return state.get(key, default)

    def set(self, key: str, value):
        """Set a single value in state"""
        with self._lock:
            state = self._read()
            state[key] = value
            self._write(state)
            self._trace(f"set key={key} value_type={type(value).__name__}")

    def update(self, updates: dict):
        """Update multiple values in state"""
        with self._lock:
            state = self._read()
            state.update(updates)
            self._write(state)
            self._trace(f"update keys={sorted(list(updates.keys()))}")

    def get_all(self) -> dict:
        """Get entire state"""
        with self._lock:
            return self._read()

    def heartbeat(self):
        """Update heartbeat timestamp"""
        self.set("last_heartbeat", time.monotonic())

    def is_client_connected(self, timeout=HEARTBEAT_TIMEOUT) -> bool:
        """Check if a client has sent heartbeat recently"""
        last = self.get("last_heartbeat", 0)
        return (time.monotonic() - last) <= timeout

    def request_scan(self):
        """Request a network scan"""
        Path(f"{STATE_DIR}/scan_request").touch()
        self._trace("request_scan touched")

    def has_scan_request(self) -> bool:
        """Check if scan was requested"""
        request_file = Path(f"{STATE_DIR}/scan_request")
        if request_file.exists():
            request_file.unlink()
            self._trace("has_scan_request consumed=True")
            return True
        return False

    def request_connect(self, ssid: str, password: str, use_saved: bool = False):
        """Request connection to a network"""
        with open(f"{STATE_DIR}/connect_request.json", 'w') as f:
            json.dump({"ssid": ssid, "password": password, "use_saved": use_saved}, f)
        self._trace(f"request_connect ssid='{ssid}' use_saved={use_saved} password_len={len(password or '')}")

    def get_connect_request(self) -> dict:
        """Get and clear connection request"""
        request_file = Path(f"{STATE_DIR}/connect_request.json")
        if request_file.exists():
            try:
                with open(request_file, 'r') as f:
                    data = json.load(f)
                request_file.unlink()
                self._trace(f"get_connect_request consumed ssid='{data.get('ssid')}' use_saved={data.get('use_saved')}")
                return data
            except (json.JSONDecodeError, IOError):
                pass
        return None

    def request_saved_network_add(self, ssid: str, password: str):
        """Request adding/updating a saved network"""
        with open(f"{STATE_DIR}/saved_network_request.json", 'w') as f:
            json.dump({"action": "add", "ssid": ssid, "password": password}, f)
        self._trace(f"request_saved_network_add ssid='{ssid}' password_len={len(password or '')}")

    def request_saved_network_delete(self, ssid: str):
        """Request deleting a saved network"""
        with open(f"{STATE_DIR}/saved_network_request.json", 'w') as f:
            json.dump({"action": "delete", "ssid": ssid}, f)
        self._trace(f"request_saved_network_delete ssid='{ssid}'")

    def get_saved_network_request(self) -> dict:
        """Get and clear saved network management request"""
        request_file = Path(f"{STATE_DIR}/saved_network_request.json")
        if request_file.exists():
            try:
                with open(request_file, 'r') as f:
                    data = json.load(f)
                request_file.unlink()
                self._trace(f"get_saved_network_request consumed action={data.get('action')} ssid='{data.get('ssid')}'")
                return data
            except (json.JSONDecodeError, IOError):
                pass
        return None

    def request_block_client(self, mac: str):
        """Request blocking an AP client"""
        with open(f"{STATE_DIR}/block_request.json", 'w') as f:
            json.dump({"mac": mac}, f)
        self._trace(f"request_block_client mac={mac}")

    def request_unblock_client(self, mac: str):
        """Request unblocking an AP client"""
        with open(f"{STATE_DIR}/unblock_request.json", 'w') as f:
            json.dump({"mac": mac}, f)
        self._trace(f"request_unblock_client mac={mac}")

    def get_block_request(self) -> dict:
        """Get and clear block request"""
        request_file = Path(f"{STATE_DIR}/block_request.json")
        if request_file.exists():
            try:
                with open(request_file, 'r') as f:
                    data = json.load(f)
                request_file.unlink()
                self._trace(f"get_block_request consumed mac={data.get('mac')}")
                return data
            except (json.JSONDecodeError, IOError):
                pass
        return None

    def get_unblock_request(self) -> dict:
        """Get and clear unblock request"""
        request_file = Path(f"{STATE_DIR}/unblock_request.json")
        if request_file.exists():
            try:
                with open(request_file, 'r') as f:
                    data = json.load(f)
                request_file.unlink()
                self._trace(f"get_unblock_request consumed mac={data.get('mac')}")
                return data
            except (json.JSONDecodeError, IOError):
                pass
        return None

    def request_ap_clients_refresh(self):
        """Request AP clients list refresh"""
        Path(f"{STATE_DIR}/ap_clients_refresh").touch()
        self._trace("request_ap_clients_refresh touched")

    def has_ap_clients_refresh_request(self) -> bool:
        """Check if AP clients refresh was requested"""
        request_file = Path(f"{STATE_DIR}/ap_clients_refresh")
        if request_file.exists():
            request_file.unlink()
            self._trace("has_ap_clients_refresh_request consumed=True")
            return True
        return False

    def request_dns_refresh(self):
        """Request immediate DNS/resolver refresh."""
        Path(f"{STATE_DIR}/dns_refresh_request").touch()
        self._trace("request_dns_refresh touched")

    def has_dns_refresh_request(self) -> bool:
        """Check if DNS refresh was requested."""
        request_file = Path(f"{STATE_DIR}/dns_refresh_request")
        if request_file.exists():
            request_file.unlink()
            self._trace("has_dns_refresh_request consumed=True")
            return True
        return False

    def request_ap_password_change(self, password: str):
        """Request AP password change"""
        with open(f"{STATE_DIR}/ap_password_request.json", 'w') as f:
            json.dump({"password": password}, f)
        self._trace(f"request_ap_password_change password_len={len(password or '')}")

    def get_ap_password_change_request(self) -> dict:
        """Get and clear AP password change request"""
        request_file = Path(f"{STATE_DIR}/ap_password_request.json")
        if request_file.exists():
            try:
                with open(request_file, 'r') as f:
                    data = json.load(f)
                request_file.unlink()
                self._trace("get_ap_password_change_request consumed=True")
                return data
            except (json.JSONDecodeError, IOError):
                pass
        return None


# Global instance
wifi_state = WifiState()
