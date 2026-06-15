#!/usr/bin/env python3
"""Persistent netservices-lite configuration (JSON). WiFi-only essentials."""

import json
import logging
from pathlib import Path
from typing import Dict, List

try:
    from .constants_paths import NETSERVICES_CONFIG_FILE
except ImportError:
    from constants_paths import NETSERVICES_CONFIG_FILE

log = logging.getLogger("netservices_config")


class NetservicesConfig:
    """Read/write persistent netservices settings from a single JSON file."""

    def __init__(self, path: str = NETSERVICES_CONFIG_FILE):
        self.path = Path(path)

    def exists(self) -> bool:
        return self.path.exists()

    def _default(self) -> Dict:
        return {
            "ap": {"ap_psk": ""},
            "sta": {"networks": []},
            "dashboard": {"theme": "light"},
            "auth": {"username": "", "password_hash": ""},
            "session": {"secret_key": ""},
        }

    def _clean_networks(self, networks: List[Dict]) -> List[Dict]:
        cleaned = []
        for item in (networks or []):
            if not isinstance(item, dict):
                continue
            ssid = (item.get("ssid") or "").strip()
            if not ssid:
                continue
            cleaned.append({
                "ssid": ssid,
                "psk": (item.get("psk") or "").strip(),
                "password": (item.get("password") or "").strip(),
            })
        return cleaned

    def _normalize(self, data: Dict) -> Dict:
        base = self._default()
        if not isinstance(data, dict):
            return base
        ap = data.get("ap")
        if isinstance(ap, dict):
            base["ap"]["ap_psk"] = (ap.get("ap_psk") or "").strip()
            legacy_password = (ap.get("ap_password") or "").strip()
            if legacy_password:
                base["ap"]["ap_password"] = legacy_password
        sta = data.get("sta")
        if isinstance(sta, dict):
            base["sta"]["networks"] = self._clean_networks(sta.get("networks") or [])
        dash = data.get("dashboard")
        if isinstance(dash, dict):
            t = (dash.get("theme") or "light").strip()
            base["dashboard"]["theme"] = "dark" if t == "dark" else "light"
        auth = data.get("auth")
        if isinstance(auth, dict):
            base["auth"]["username"] = (auth.get("username") or "").strip()
            base["auth"]["password_hash"] = (auth.get("password_hash") or "").strip()
        sess = data.get("session")
        if isinstance(sess, dict):
            base["session"]["secret_key"] = (sess.get("secret_key") or "").strip()
        return base

    def _read_all(self) -> Dict:
        if not self.path.exists():
            return self._default()
        raw = self.path.read_text() or ""
        try:
            return self._normalize(json.loads(raw))
        except Exception:
            log.warning("Invalid JSON in netservices.conf; using defaults")
            return self._default()

    def _write_all(self, data: Dict):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._normalize(data)
        with open(self.path, "w") as f:
            json.dump(payload, f, indent=2)
            f.write("\n")

    def read(self) -> Dict:
        data = self._read_all()
        ap = data.get("ap", {})
        sta = data.get("sta", {})
        return {
            "ap_psk": (ap.get("ap_psk") or "").strip(),
            "ap_password": (ap.get("ap_password") or "").strip(),
            "sta_networks": self._clean_networks(sta.get("networks") or []),
        }

    def write_ap_psk(self, ap_psk: str):
        data = self._read_all()
        data.setdefault("ap", {})
        data["ap"]["ap_psk"] = ap_psk or ""
        data["ap"].pop("ap_password", None)
        self._write_all(data)

    def write_sta_networks(self, networks: List[Dict]):
        data = self._read_all()
        data.setdefault("sta", {})
        data["sta"]["networks"] = self._clean_networks(networks)
        self._write_all(data)

    def write_all(self, ap_psk: str, sta_networks: List[Dict]):
        data = self._read_all()
        data.setdefault("ap", {})
        data.setdefault("sta", {})
        data["ap"]["ap_psk"] = ap_psk or ""
        data["ap"].pop("ap_password", None)
        data["sta"]["networks"] = self._clean_networks(sta_networks)
        self._write_all(data)

    def read_theme(self) -> str:
        t = (self._read_all().get("dashboard", {}).get("theme") or "light").strip()
        return "dark" if t == "dark" else "light"

    def write_theme(self, theme: str):
        data = self._read_all()
        data.setdefault("dashboard", {})
        data["dashboard"]["theme"] = "dark" if theme == "dark" else "light"
        self._write_all(data)

    def read_auth(self) -> Dict:
        auth = self._read_all().get("auth", {})
        return {
            "username": (auth.get("username") or "").strip(),
            "password_hash": (auth.get("password_hash") or "").strip(),
        }

    def write_auth(self, payload: Dict):
        data = self._read_all()
        data.setdefault("auth", {})
        if "username" in payload:
            data["auth"]["username"] = (payload.get("username") or "").strip()
        if "password_hash" in payload:
            data["auth"]["password_hash"] = (payload.get("password_hash") or "").strip()
        self._write_all(data)

    def read_session(self) -> Dict:
        sess = self._read_all().get("session", {})
        return {"secret_key": (sess.get("secret_key") or "").strip()}

    def write_session(self, payload: Dict):
        data = self._read_all()
        data.setdefault("session", {})
        if "secret_key" in payload:
            data["session"]["secret_key"] = (payload.get("secret_key") or "").strip()
        self._write_all(data)

    # ---- Compatibility stubs (lite drops these subsystems) ----
    def read_mender_artifact(self) -> str:
        data = self._read_all()
        return (data.get("system", {}).get("mender_artifact") or "").strip()

    def write_mender_artifact(self, artifact: str):
        data = self._read_all()
        data.setdefault("system", {})
        data["system"]["mender_artifact"] = (artifact or "").strip()
        self._write_all(data)

    def read_dns(self) -> Dict:
        return {
            "servers": ["223.5.5.5", "9.9.9.9", "1.1.1.1", "8.8.8.8"],
            "options": "timeout:1 attempts:2",
        }

    def read_vpn(self) -> Dict:
        return {"provider": "none", "providers": {"tailscale": {"dns_servers": []}}}
