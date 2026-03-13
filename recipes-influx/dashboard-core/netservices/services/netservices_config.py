#!/usr/bin/env python3
"""Persistent unified netservices configuration (JSON)."""

import ipaddress
import json
import logging
from pathlib import Path
from typing import Dict, List

log = logging.getLogger("netservices_config")

NETSERVICES_CONFIG_FILE = "/data/rexgen/config/netservices.conf"


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
            "dashboard": {"https_enabled": False, "https_hostname": "", "theme": "light", "lang": "en", "experimental": False},
            "system": {"ssh_enabled": True, "mender_artifact": ""},
            "dns": {
                "servers": ["223.5.5.5", "9.9.9.9", "1.1.1.1", "8.8.8.8"],
                "options": "timeout:1 attempts:2",
            },
            "vpn": {
                "provider": "none",
                "providers": {
                    "tailscale": {
                        "auth_key": "",
                        "auth_status": "never",
                        "last_auth_key_sha256": "",
                        "last_error": "",
                        "advertise_tags_enabled": False,
                        "advertise_tags": "",
                        "dns_servers": ["100.100.100.100"],
                    },
                    "openvpn": {"config": "", "username": "", "password": ""},
                },
            },
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
            # Always store both fields. "psk" holds the derived 64-hex PSK (no
            # plaintext). "password" is normally empty but can be filled manually
            # in the conf file — import_saved_networks() auto-converts it to PSK
            # on next startup and clears it.
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
            base["dashboard"]["https_enabled"] = bool(dash.get("https_enabled", False))
            base["dashboard"]["https_hostname"] = (dash.get("https_hostname") or "").strip()
            t = (dash.get("theme") or "light").strip()
            base["dashboard"]["theme"] = "dark" if t == "dark" else "light"
            l = (dash.get("lang") or "en").strip()
            base["dashboard"]["lang"] = l if l in ("en", "zh", "bg") else "en"
            base["dashboard"]["experimental"] = bool(dash.get("experimental", False))
        system = data.get("system")
        if isinstance(system, dict):
            base["system"]["ssh_enabled"] = bool(system.get("ssh_enabled", True))
            base["system"]["mender_artifact"] = (system.get("mender_artifact") or "").strip()
        dns = data.get("dns")
        if isinstance(dns, dict):
            base["dns"]["servers"] = self._clean_dns_servers(dns.get("servers") or [])
            base["dns"]["options"] = (dns.get("options") or "").strip() or self._default()["dns"]["options"]
        vpn = data.get("vpn")
        if isinstance(vpn, dict):
            provider = (vpn.get("provider") or "none").strip().lower()
            base["vpn"]["provider"] = provider if provider in ("none", "tailscale") else "none"
            providers = vpn.get("providers")
            if isinstance(providers, dict):
                ts = providers.get("tailscale")
                if isinstance(ts, dict):
                    base["vpn"]["providers"]["tailscale"]["auth_key"] = (ts.get("auth_key") or "").strip()
                    status = (ts.get("auth_status") or "never").strip().lower()
                    base["vpn"]["providers"]["tailscale"]["auth_status"] = status if status in ("never", "ok", "pending", "error") else "never"
                    base["vpn"]["providers"]["tailscale"]["last_auth_key_sha256"] = (ts.get("last_auth_key_sha256") or "").strip()
                    base["vpn"]["providers"]["tailscale"]["last_error"] = (ts.get("last_error") or "").strip()
                    base["vpn"]["providers"]["tailscale"]["advertise_tags_enabled"] = bool(ts.get("advertise_tags_enabled", False))
                    base["vpn"]["providers"]["tailscale"]["advertise_tags"] = (ts.get("advertise_tags") or "").strip()
                    base["vpn"]["providers"]["tailscale"]["dns_servers"] = self._clean_dns_servers(ts.get("dns_servers") or [])
                ovpn = providers.get("openvpn")
                if isinstance(ovpn, dict):
                    base["vpn"]["providers"]["openvpn"]["config"] = (ovpn.get("config") or "").strip()
                    base["vpn"]["providers"]["openvpn"]["username"] = (ovpn.get("username") or "").strip()
                    base["vpn"]["providers"]["openvpn"]["password"] = (ovpn.get("password") or "").strip()
        auth = data.get("auth")
        if isinstance(auth, dict):
            base["auth"]["username"] = (auth.get("username") or "").strip()
            base["auth"]["password_hash"] = (auth.get("password_hash") or "").strip()
        sess = data.get("session")
        if isinstance(sess, dict):
            base["session"]["secret_key"] = (sess.get("secret_key") or "").strip()
        return base

    def _clean_dns_servers(self, servers: List) -> List[str]:
        cleaned = []
        seen = set()
        for raw in (servers or []):
            v = (str(raw) if raw is not None else "").strip()
            if not v:
                continue
            try:
                ipaddress.ip_address(v)
            except ValueError:
                continue
            if v in seen:
                continue
            seen.add(v)
            cleaned.append(v)
        if cleaned:
            return cleaned
        return list(self._default()["dns"]["servers"])

    def _read_all(self) -> Dict:
        if not self.path.exists():
            return self._default()
        raw = self.path.read_text() or ""
        try:
            parsed = json.loads(raw)
            return self._normalize(parsed)
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

    def read_dashboard(self) -> Dict:
        data = self._read_all()
        dash = data.get("dashboard", {})
        return {
            "https_enabled": bool(dash.get("https_enabled", False)),
            "https_hostname": (dash.get("https_hostname") or "").strip(),
        }

    def write_dashboard(self, payload: Dict):
        data = self._read_all()
        data.setdefault("dashboard", {})
        if "https_enabled" in payload:
            data["dashboard"]["https_enabled"] = bool(payload.get("https_enabled"))
        if "https_hostname" in payload:
            data["dashboard"]["https_hostname"] = (payload.get("https_hostname") or "").strip()
        self._write_all(data)

    def read_experimental(self) -> bool:
        data = self._read_all()
        return bool(data.get("dashboard", {}).get("experimental", False))

    def read_theme(self) -> str:
        data = self._read_all()
        t = (data.get("dashboard", {}).get("theme") or "light").strip()
        return "dark" if t == "dark" else "light"

    def write_theme(self, theme: str):
        data = self._read_all()
        data.setdefault("dashboard", {})
        data["dashboard"]["theme"] = "dark" if theme == "dark" else "light"
        self._write_all(data)

    def read_lang(self) -> str:
        data = self._read_all()
        l = (data.get("dashboard", {}).get("lang") or "en").strip()
        return l if l in ("en", "zh", "bg") else "en"

    def write_lang(self, lang: str):
        data = self._read_all()
        data.setdefault("dashboard", {})
        data["dashboard"]["lang"] = lang if lang in ("en", "zh", "bg") else "en"
        self._write_all(data)

    def read_system(self) -> Dict:
        had_ssh_on_disk = False
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text() or "{}")
                if isinstance(raw, dict):
                    raw_system = raw.get("system")
                    if isinstance(raw_system, dict):
                        had_ssh_on_disk = ("ssh_enabled" in raw_system)
            except Exception:
                had_ssh_on_disk = False

        data = self._read_all()
        system = data.get("system", {})
        if (not had_ssh_on_disk) or (not isinstance(system, dict)) or ("ssh_enabled" not in system):
            data.setdefault("system", {})
            data["system"]["ssh_enabled"] = bool(system.get("ssh_enabled", True))
            self._write_all(data)
        return {"ssh_enabled": bool(system.get("ssh_enabled", True))}

    def write_system(self, payload: Dict):
        data = self._read_all()
        data.setdefault("system", {})
        if "ssh_enabled" in payload:
            data["system"]["ssh_enabled"] = bool(payload.get("ssh_enabled"))
        self._write_all(data)

    def read_dns(self) -> Dict:
        data = self._read_all()
        dns = data.get("dns", {}) if isinstance(data.get("dns"), dict) else {}
        servers = self._clean_dns_servers(dns.get("servers") or [])
        options = (dns.get("options") or "").strip() or self._default()["dns"]["options"]
        return {"servers": servers, "options": options}

    def write_dns(self, payload: Dict):
        data = self._read_all()
        data.setdefault("dns", {})
        if "servers" in payload:
            data["dns"]["servers"] = self._clean_dns_servers(payload.get("servers") or [])
        if "options" in payload:
            data["dns"]["options"] = (payload.get("options") or "").strip() or self._default()["dns"]["options"]
        self._write_all(data)

    def read_vpn(self) -> Dict:
        data = self._read_all()
        vpn = data.get("vpn", {})
        provider = (vpn.get("provider") or "none").strip().lower()
        provider = provider if provider in ("none", "tailscale") else "none"
        providers = vpn.get("providers", {}) if isinstance(vpn.get("providers"), dict) else {}
        tailscale = providers.get("tailscale", {}) if isinstance(providers.get("tailscale"), dict) else {}
        openvpn = providers.get("openvpn", {}) if isinstance(providers.get("openvpn"), dict) else {}
        return {
            "provider": provider,
            "providers": {
                "tailscale": {
                    "auth_key": (tailscale.get("auth_key") or "").strip(),
                    "auth_status": (tailscale.get("auth_status") or "never").strip().lower(),
                    "last_auth_key_sha256": (tailscale.get("last_auth_key_sha256") or "").strip(),
                    "last_error": (tailscale.get("last_error") or "").strip(),
                    "advertise_tags_enabled": bool(tailscale.get("advertise_tags_enabled", False)),
                    "advertise_tags": (tailscale.get("advertise_tags") or "").strip(),
                    "dns_servers": self._clean_dns_servers(tailscale.get("dns_servers") or []),
                },
                "openvpn": {
                    "config": (openvpn.get("config") or "").strip(),
                    "username": (openvpn.get("username") or "").strip(),
                    "password": (openvpn.get("password") or "").strip(),
                },
            },
        }

    def write_vpn(self, payload: Dict):
        data = self._read_all()
        data.setdefault("vpn", {})
        data["vpn"].setdefault("providers", {})
        data["vpn"]["providers"].setdefault("tailscale", {})
        data["vpn"]["providers"].setdefault("openvpn", {})
        if "provider" in payload:
            provider = (payload.get("provider") or "none").strip().lower()
            data["vpn"]["provider"] = provider if provider in ("none", "tailscale") else "none"
        providers = payload.get("providers")
        if isinstance(providers, dict):
            tailscale = providers.get("tailscale")
            if isinstance(tailscale, dict):
                if "auth_key" in tailscale:
                    data["vpn"]["providers"]["tailscale"]["auth_key"] = (tailscale.get("auth_key") or "").strip()
                if "auth_status" in tailscale:
                    status = (tailscale.get("auth_status") or "never").strip().lower()
                    data["vpn"]["providers"]["tailscale"]["auth_status"] = status if status in ("never", "ok", "pending", "error") else "never"
                if "last_auth_key_sha256" in tailscale:
                    data["vpn"]["providers"]["tailscale"]["last_auth_key_sha256"] = (tailscale.get("last_auth_key_sha256") or "").strip()
                if "last_error" in tailscale:
                    data["vpn"]["providers"]["tailscale"]["last_error"] = (tailscale.get("last_error") or "").strip()
                if "advertise_tags_enabled" in tailscale:
                    data["vpn"]["providers"]["tailscale"]["advertise_tags_enabled"] = bool(tailscale.get("advertise_tags_enabled", False))
                if "advertise_tags" in tailscale:
                    data["vpn"]["providers"]["tailscale"]["advertise_tags"] = (tailscale.get("advertise_tags") or "").strip()
                if "dns_servers" in tailscale:
                    data["vpn"]["providers"]["tailscale"]["dns_servers"] = self._clean_dns_servers(tailscale.get("dns_servers") or [])
            openvpn = providers.get("openvpn")
            if isinstance(openvpn, dict):
                if "config" in openvpn:
                    data["vpn"]["providers"]["openvpn"]["config"] = (openvpn.get("config") or "").strip()
                if "username" in openvpn:
                    data["vpn"]["providers"]["openvpn"]["username"] = (openvpn.get("username") or "").strip()
                if "password" in openvpn:
                    data["vpn"]["providers"]["openvpn"]["password"] = (openvpn.get("password") or "").strip()
        self._write_all(data)

    def read_mender_artifact(self) -> str:
        data = self._read_all()
        return (data.get("system", {}).get("mender_artifact") or "").strip()

    def write_mender_artifact(self, artifact: str):
        data = self._read_all()
        data.setdefault("system", {})
        data["system"]["mender_artifact"] = (artifact or "").strip()
        self._write_all(data)

    def read_auth(self) -> Dict:
        data = self._read_all()
        auth = data.get("auth", {})
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
        data = self._read_all()
        sess = data.get("session", {})
        return {"secret_key": (sess.get("secret_key") or "").strip()}

    def write_session(self, payload: Dict):
        data = self._read_all()
        data.setdefault("session", {})
        if "secret_key" in payload:
            data["session"]["secret_key"] = (payload.get("secret_key") or "").strip()
        self._write_all(data)
