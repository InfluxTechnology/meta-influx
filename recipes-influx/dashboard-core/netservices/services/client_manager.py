#!/usr/bin/env python3
"""
Client Manager - Manages WiFi client connections on wlan0
Connects to external WiFi networks using wpa_cli
"""

import hashlib
import logging
import re
import subprocess
import time
from pathlib import Path
from typing import Optional, List

from netservices_config import NetservicesConfig
try:
    from .constants_network import (
        DEFAULT_DNS_OPTIONS,
        DEFAULT_DNS_SERVERS,
        IFACE_CLIENT,
        WPA_PBKDF2_DKLEN,
        WPA_PBKDF2_ITERATIONS,
    )
    from .constants_paths import RESOLV_CONF, WIFI_STATE_FILE, WPA_CONFIG, WPA_SOCKET_DIR
    from .constants_runtime import CONNECT_FORENSICS
except ImportError:
    from constants_network import (
        DEFAULT_DNS_OPTIONS,
        DEFAULT_DNS_SERVERS,
        IFACE_CLIENT,
        WPA_PBKDF2_DKLEN,
        WPA_PBKDF2_ITERATIONS,
    )
    from constants_paths import RESOLV_CONF, WIFI_STATE_FILE, WPA_CONFIG, WPA_SOCKET_DIR
    from constants_runtime import CONNECT_FORENSICS

log = logging.getLogger(__name__)


def _derive_wpa_psk(ssid: str, passphrase: str) -> str:
    """Derive 64-hex WPA PSK from passphrase and SSID (PBKDF2-HMAC-SHA1, 4096 iters)."""
    return hashlib.pbkdf2_hmac(
        "sha1",
        passphrase.encode("utf-8"),
        ssid.encode("utf-8"),
        WPA_PBKDF2_ITERATIONS,
        WPA_PBKDF2_DKLEN,
    ).hex()
STATE_FILE = WIFI_STATE_FILE

# ========== Configuration ==========

# Interface / wpa / DNS defaults come from shared constants modules.

# Config file header (required for wpa_cli to work)
WPA_CONFIG_HEADER = f"""ctrl_interface={WPA_SOCKET_DIR}
update_config=1
"""


class WpaCli:
    """wpa_cli interface for dynamic WiFi management"""

    def __init__(self, interface: str, run_cmd):
        self.interface = interface
        self._run = run_cmd

    @staticmethod
    def _read_connect_trace_id() -> str:
        try:
            import json
            data = json.loads(Path(STATE_FILE).read_text())
            return str(data.get("connect_trace_id") or "-")
        except Exception:
            return "-"

    @staticmethod
    def _ap_station_snapshot() -> tuple:
        try:
            res = subprocess.run(
                "iw dev wlan1 station dump 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=5
            )
            macs = []
            for line in (res.stdout or "").splitlines():
                s = line.strip()
                if s.startswith("Station "):
                    parts = s.split()
                    if len(parts) >= 2:
                        macs.append(parts[1].lower())
            return len(macs), macs
        except Exception:
            return -1, []

    def _wpa_cli(self, *args) -> str:
        """Run wpa_cli command with proper argument handling (no shell)"""
        cmd = ["wpa_cli", "-i", self.interface] + list(args)
        try:
            forensic = CONNECT_FORENSICS
            trace_id = self._read_connect_trace_id() if forensic else "-"
            if forensic:
                before_count, before_macs = self._ap_station_snapshot()
                log.info(
                    f"[TRACE][WPA][CF] before trace_id={trace_id} cmd={' '.join(cmd)} "
                    f"ap_count={before_count} ap_macs={before_macs}"
                )
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if forensic:
                after_count, after_macs = self._ap_station_snapshot()
                log.info(
                    f"[TRACE][WPA][CF] after trace_id={trace_id} cmd={' '.join(cmd)} rc={result.returncode} "
                    f"ap_count={after_count} ap_macs={after_macs}"
                )
            return result.stdout if result.stdout else ""
        except Exception as e:
            log.error(f"wpa_cli failed: {e}")
            return ""

    @staticmethod
    def validate_ssid(ssid: str) -> tuple:
        """Validate SSID. Returns (is_valid, error_message)"""
        if not ssid:
            return False, "SSID cannot be empty"
        if len(ssid) > 32:
            return False, "SSID too long (max 32 chars)"
        return True, None

    @staticmethod
    def validate_password(password: str) -> tuple:
        """
        Validate WPA password. Returns (is_valid, error_message)
        Empty password = open network (allowed)
        WPA password must be 8-63 characters
        """
        if not password:
            # Open network - no password
            return True, None
        if len(password) < 8:
            return False, f"Password too short ({len(password)} chars, WPA requires min 8)"
        if len(password) > 63:
            return False, f"Password too long ({len(password)} chars, max 63)"
        return True, None

    def scan(self) -> bool:
        """Trigger a network scan"""
        result = self._wpa_cli("scan")
        return "OK" in result

    def scan_results(self) -> List[dict]:
        """Get scan results"""
        output = self._wpa_cli("scan_results")
        networks = []
        for line in output.splitlines()[1:]:  # Skip header
            parts = line.split('\t')
            if len(parts) >= 5:
                networks.append({
                    "bssid": parts[0],
                    "frequency": parts[1],
                    "signal": parts[2],
                    "flags": parts[3],
                    "ssid": parts[4] if len(parts) > 4 else ""
                })
        return networks

    def status(self) -> dict:
        """Get connection status"""
        output = self._wpa_cli("status")
        status = {}
        for line in output.splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                status[key] = value
        return status

    def list_networks(self) -> List[dict]:
        """List configured networks"""
        output = self._wpa_cli("list_networks")
        networks = []
        for line in output.splitlines()[1:]:  # Skip header
            parts = line.split('\t')
            if len(parts) >= 4:
                networks.append({
                    "id": parts[0],
                    "ssid": parts[1],
                    "bssid": parts[2],
                    "flags": parts[3] if len(parts) > 3 else ""
                })
        return networks

    def add_network(self) -> Optional[int]:
        """Add a new network, returns network ID"""
        result = self._wpa_cli("add_network")
        try:
            return int(result.strip())
        except ValueError:
            return None

    def set_network(self, net_id: int, key: str, value: str, quoted: bool = True) -> bool:
        """Set network parameter"""
        if quoted:
            # wpa_cli expects quoted strings like: set_network 0 ssid "MySSID"
            value = f'"{value}"'
        result = self._wpa_cli("set_network", str(net_id), key, value)
        return "OK" in result

    def enable_network(self, net_id: int) -> bool:
        """Enable a network"""
        result = self._wpa_cli("enable_network", str(net_id))
        return "OK" in result

    def disable_network(self, net_id: int) -> bool:
        """Disable a network"""
        result = self._wpa_cli("disable_network", str(net_id))
        return "OK" in result

    def select_network(self, net_id: int) -> bool:
        """Select a network (disable others)"""
        result = self._wpa_cli("select_network", str(net_id))
        return "OK" in result

    def remove_network(self, net_id: int) -> bool:
        """Remove a network"""
        result = self._wpa_cli("remove_network", str(net_id))
        return "OK" in result

    def save_config(self) -> bool:
        """Save configuration to file"""
        result = self._wpa_cli("save_config")
        return "OK" in result

    def reconfigure(self) -> bool:
        """Reload configuration from file"""
        result = self._wpa_cli("reconfigure")
        return "OK" in result

    def disconnect(self) -> bool:
        """Disconnect from current network"""
        result = self._wpa_cli("disconnect")
        return "OK" in result

    def reconnect(self) -> bool:
        """Reconnect to network"""
        result = self._wpa_cli("reconnect")
        return "OK" in result

    def find_network_by_ssid(self, ssid: str) -> Optional[int]:
        """Find network ID by SSID"""
        for net in self.list_networks():
            if net["ssid"] == ssid:
                return int(net["id"])
        return None


def cleanup_wpa_config() -> int:
    """
    Ensure wpa_supplicant.conf exists with proper header.
    Only removes networks with clearly invalid passwords.
    Returns number of removed networks.
    """
    # Ensure socket directory exists
    Path(WPA_SOCKET_DIR).mkdir(parents=True, exist_ok=True)

    config_path = Path(WPA_CONFIG)

    try:
        content = config_path.read_text()
    except FileNotFoundError:
        # Create fresh config with header
        config_path.write_text(WPA_CONFIG_HEADER)
        log.info(f"Created fresh {WPA_CONFIG}")
        return 0

    # If empty or no header, add header but preserve any existing content
    if not content.strip():
        config_path.write_text(WPA_CONFIG_HEADER)
        log.info(f"Config was empty, added header")
        return 0

    if "ctrl_interface" not in content:
        # Prepend header to existing content
        config_path.write_text(WPA_CONFIG_HEADER + "\n" + content)
        log.info("Added missing ctrl_interface header to wpa_supplicant.conf")

    # Only scan for obviously invalid passwords (too short for WPA)
    # Don't rewrite the file unless we find something clearly wrong
    network_pattern = re.compile(r'network\s*=\s*\{([^}]*)\}', re.DOTALL)

    removed_count = 0
    new_content = content

    for match in network_pattern.finditer(content):
        block = match.group(1)
        full_block = match.group(0)

        # Check for PSK that's too short (WPA requires 8-63 chars)
        psk_match = re.search(r'psk\s*=\s*"([^"]*)"', block)
        key_mgmt_match = re.search(r'key_mgmt\s*=\s*NONE', block)

        if psk_match and not key_mgmt_match:
            psk = psk_match.group(1)
            if len(psk) < 8 or len(psk) > 63:
                # Remove this invalid network block
                new_content = new_content.replace(full_block, "")
                removed_count += 1
                log.warning(f"Removed network with invalid password length ({len(psk)} chars)")

    if removed_count > 0:
        # Clean up extra whitespace and write
        new_content = re.sub(r'\n{3,}', '\n\n', new_content)
        config_path.write_text(new_content)
        log.info(f"Cleaned wpa_supplicant.conf: removed {removed_count} invalid networks")

    return removed_count


class ClientManager:
    """Manages WiFi client connections on wlan0"""

    def __init__(self, run_cmd, set_led):
        self.interface = IFACE_CLIENT
        self._run = run_cmd
        self._set_led = set_led
        self._systemctl = lambda action, svc: run_cmd(f"systemctl {action} {svc}")
        self.wpa = WpaCli(self.interface, run_cmd)
        self._persist_cfg = NetservicesConfig()
        self.ping_hosts = list(DEFAULT_DNS_SERVERS)
        self._dns_last_sync_ts = 0.0
        self._dns_sync_interval = 10.0
        self._last_resolv_payload = ""
        self.refresh_dns_settings(force=True)

    # ========== Network Scanning ==========

    @staticmethod
    def _freq_to_band_label(freq) -> Optional[str]:
        """Map MHz frequency to human-readable WiFi band label."""
        try:
            f = int(freq)
        except (TypeError, ValueError):
            return None
        if 2400 <= f <= 2500:
            return "2.4 GHz"
        if 5000 <= f <= 5900:
            return "5 GHz"
        if 5925 <= f <= 7125:
            return "6 GHz"
        return None

    def scan_networks(self) -> list:
        """Scan for available WiFi networks using wpa_cli.
        Returns list of dicts with full info per SSID:
        [{"ssid": "...", "signal": -45, "frequency": "2437", "flags": "[WPA2-PSK-CCMP]", "bssid": "aa:bb:..."}, ...]
        Best signal per SSID is kept when duplicates exist.
        """
        log.info(f"Scanning networks on {self.interface}...")

        # Trigger scan
        self.wpa.scan()
        time.sleep(2)  # Wait for scan to complete

        # Get results — keep best signal per SSID (with all fields)
        seen = {}  # ssid -> full dict
        band_map = {}  # ssid -> set(band labels)
        results = self.wpa.scan_results()
        for net in results:
            ssid = net.get("ssid", "")
            if not ssid:
                continue
            band = self._freq_to_band_label(net.get("frequency"))
            if band:
                if ssid not in band_map:
                    band_map[ssid] = set()
                band_map[ssid].add(band)
            try:
                signal = int(net.get("signal", -100))
            except (ValueError, TypeError):
                signal = -100
            if ssid not in seen or signal > seen[ssid]["signal"]:
                seen[ssid] = {
                    "ssid": ssid,
                    "signal": signal,
                    "frequency": net.get("frequency", ""),
                    "flags": net.get("flags", ""),
                    "bssid": net.get("bssid", "")
                }

        networks = list(seen.values())
        band_order = {"2.4 GHz": 0, "5 GHz": 1, "6 GHz": 2}
        for net in networks:
            ssid = net.get("ssid", "")
            bands = sorted(list(band_map.get(ssid, set())), key=lambda b: band_order.get(b, 99))
            if bands:
                net["bands"] = bands

        # Fallback to iw if wpa_cli didn't work
        if not networks:
            for attempt in range(3):
                output = self._run(f"iw {self.interface} scan 2>/dev/null")
                if output.strip():
                    fallback_seen = {}
                    current = {
                        "ssid": "",
                        "signal": -100,
                        "frequency": "",
                        "flags": "",
                        "bssid": ""
                    }

                    def commit_current():
                        ssid = current.get("ssid", "")
                        if not ssid:
                            return
                        signal = current.get("signal", -100)
                        if ssid not in fallback_seen or signal > fallback_seen[ssid]["signal"]:
                            fallback_seen[ssid] = {
                                "ssid": ssid,
                                "signal": signal,
                                "frequency": current.get("frequency", ""),
                                "flags": current.get("flags", ""),
                                "bssid": current.get("bssid", "")
                            }

                    for raw_line in output.splitlines():
                        line = raw_line.strip()

                        if line.startswith("BSS "):
                            commit_current()
                            parts = line.split()
                            bssid = parts[1] if len(parts) > 1 else ""
                            if "(" in bssid:
                                bssid = bssid.split("(", 1)[0]
                            current = {
                                "ssid": "",
                                "signal": -100,
                                "frequency": "",
                                "flags": "",
                                "bssid": bssid
                            }
                            continue

                        if line.startswith("SSID:"):
                            current["ssid"] = line.split(":", 1)[1].strip()
                            continue

                        if line.startswith("freq:"):
                            current["frequency"] = line.split(":", 1)[1].strip()
                            continue

                        if line.startswith("signal:"):
                            try:
                                current["signal"] = int(float(line.split("signal:", 1)[1].split("dBm")[0].strip()))
                            except (ValueError, IndexError):
                                current["signal"] = -100
                            continue

                        if line.startswith("RSN:") and "WPA2" not in current["flags"]:
                            current["flags"] += "[WPA2]"
                            continue

                        if line.startswith("WPA:") and "WPA]" not in current["flags"]:
                            current["flags"] += "[WPA]"
                            continue

                    commit_current()
                    networks = list(fallback_seen.values())
                    break
                time.sleep(1)

        log.info(f"Found {len(networks)} networks")
        return networks

    # ========== Connection Status ==========

    def is_connected(self, status: dict = None) -> bool:
        """Check if connected to a network"""
        if status is None:
            status = self.wpa.status()
        return status.get("wpa_state") == "COMPLETED"

    def get_connected_ssid(self, status: dict = None) -> str:
        """Get currently connected SSID"""
        if status is None:
            status = self.wpa.status()
        return status.get("ssid")

    def get_ip_address(self, status: dict = None) -> str:
        """Get current IP address"""
        if status is None:
            status = self.wpa.status()
        ip = status.get("ip_address")
        if ip:
            return ip

        # Fallback
        output = self._run(f"ip addr show {self.interface} | grep 'inet ' | awk '{{print $2}}' | cut -d/ -f1")
        return output.strip() or None

    def refresh_dns_settings(self, force: bool = False):
        now = time.time()
        if (not force) and (now - self._dns_last_sync_ts < self._dns_sync_interval):
            return
        self._dns_last_sync_ts = now
        try:
            dns_cfg = self._persist_cfg.read_dns()
            base_servers = list(dns_cfg.get("servers") or [])
            options = (dns_cfg.get("options") or "").strip()
            if not base_servers:
                base_servers = list(DEFAULT_DNS_SERVERS)
            if not options:
                options = DEFAULT_DNS_OPTIONS
            vpn_cfg = self._persist_cfg.read_vpn()
            provider = (vpn_cfg.get("provider") or "none").strip().lower()
            providers = vpn_cfg.get("providers", {}) if isinstance(vpn_cfg.get("providers"), dict) else {}
            provider_cfg = providers.get(provider, {}) if isinstance(providers.get(provider), dict) else {}
            provider_servers = list(provider_cfg.get("dns_servers") or []) if provider != "none" else []
            # Keep base DNS provider-agnostic: if legacy config accidentally contains
            # VPN-specific DNS values there, remove them and let only the active
            # provider re-insert its own DNS with priority.
            provider_dns_all = set()
            for cfg in providers.values():
                if isinstance(cfg, dict):
                    for s in (cfg.get("dns_servers") or []):
                        v = (str(s) if s is not None else "").strip()
                        if v:
                            provider_dns_all.add(v)
            if provider_dns_all:
                base_servers = [s for s in base_servers if s not in provider_dns_all]
                if not base_servers:
                    base_servers = list(DEFAULT_DNS_SERVERS)
        except Exception as e:
            log.warning(f"Failed to read DNS config from netservices.conf: {e}")
            base_servers = list(DEFAULT_DNS_SERVERS)
            options = DEFAULT_DNS_OPTIONS
            provider_servers = []

        # Provider DNS has priority when provider is active; base DNS remains fallback.
        servers = []
        for s in provider_servers + base_servers:
            if s and s not in servers:
                servers.append(s)
        if not servers:
            servers = list(DEFAULT_DNS_SERVERS)

        lines = [f"nameserver {s}" for s in servers]
        lines.append(f"options {options}")
        payload = "\n".join(lines) + "\n"
        self.ping_hosts = list(servers)

        if payload == self._last_resolv_payload:
            try:
                resolv_path = Path(RESOLV_CONF)
                if (not resolv_path.is_symlink()) and resolv_path.exists() and resolv_path.read_text() == payload:
                    return
            except Exception:
                pass
        try:
            resolv_path = Path(RESOLV_CONF)
            if resolv_path.is_symlink():
                # Some images keep /etc/resolv.conf under systemd-resolved control.
                # Replace symlink with a static file so dashboard DNS policy is stable.
                resolv_path.unlink()
            resolv_path.write_text(payload)
            self._last_resolv_payload = payload
            log.info(f"Applied DNS config to {RESOLV_CONF}: servers={servers}")
        except Exception as e:
            log.warning(f"Failed to write {RESOLV_CONF}: {e}")

    def can_ping(self, host: str = None) -> bool:
        """Check internet connectivity by pinging multiple DNS servers.
        Returns True if ANY of them is reachable."""
        self.refresh_dns_settings(force=False)
        hosts = [host] if host else self.ping_hosts

        for h in hosts:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "2", "-I", self.interface, h],
                capture_output=True
            )
            if result.returncode == 0:
                return True
        return False

    def renew_dhcp(self):
        """Renew DHCP lease - ensures only one IP is assigned"""
        log.info("Renewing DHCP...")
        # Kill any existing udhcpc for this interface (portable, avoids pkill dependency)
        self._run(
            f"for p in $(ps | grep '[u]dhcpc' | grep -w '{self.interface}' | awk '{{print $1}}'); do "
            "kill $p 2>/dev/null || true; "
            "done"
        )
        # Flush existing IPs to ensure clean state
        self._run(f"ip addr flush dev {self.interface}")
        # Request new IP
        self._run(f"udhcpc -i {self.interface} -n -q")
        # Keep DNS strictly from netservices.conf order, not from DHCP/Tailscale.
        self.refresh_dns_settings(force=True)

    # ========== Network Management (wpa_cli) ==========

    def get_known_networks(self) -> list:
        """Get list of known SSIDs"""
        networks = self.wpa.list_networks()
        return [net["ssid"] for net in networks]

    @staticmethod
    def _parse_saved_networks_from_wpa_config() -> list:
        """Parse saved SSID/password pairs from wpa_supplicant.conf."""
        try:
            content = Path(WPA_CONFIG).read_text()
        except Exception:
            return []

        out = []
        for match in re.finditer(r"network\s*=\s*\{([^}]*)\}", content, re.DOTALL):
            block = match.group(1) or ""
            ssid_m = re.search(r'^\s*ssid\s*=\s*"([^"]*)"\s*$', block, re.MULTILINE)
            if not ssid_m:
                continue
            ssid = ssid_m.group(1)
            if not ssid:
                continue

            # Open network if key_mgmt=NONE; otherwise extract PSK.
            key_none = re.search(r'^\s*key_mgmt\s*=\s*NONE\s*$', block, re.MULTILINE) is not None
            psk_hex_m = re.search(r'^\s*psk\s*=\s*([0-9a-fA-F]{64})\s*$', block, re.MULTILINE)
            psk_quoted_m = re.search(r'^\s*psk\s*=\s*"([^"]*)"\s*$', block, re.MULTILINE)
            psk = ""
            if not key_none:
                if psk_hex_m:
                    # Pre-derived PSK stored as 64-hex (new format).
                    psk = psk_hex_m.group(1).lower()
                elif psk_quoted_m:
                    # Legacy plaintext passphrase — derive PSK on read so it's never
                    # written back to netservices.conf in plaintext.
                    passphrase = psk_quoted_m.group(1) or ""
                    if passphrase:
                        psk = _derive_wpa_psk(ssid, passphrase)

            out.append({"ssid": ssid, "psk": psk})
        return out

    def export_saved_networks(self) -> list:
        """Export saved STA networks with passwords for persistent backup."""
        return self._parse_saved_networks_from_wpa_config()

    def import_saved_networks(self, networks: list):
        """Apply saved STA networks from persistent config as source-of-truth."""
        target = []
        for item in (networks or []):
            if not isinstance(item, dict):
                continue
            ssid = (item.get("ssid") or "").strip()
            if not ssid:
                continue
            # "password" takes priority: user may have manually set it in the conf
            # file to update a network. Derive PSK from it and let the next
            # _persist_runtime_settings() call clear the plaintext field.
            password = (item.get("password") or "").strip()
            psk_hex = (item.get("psk") or "").strip().lower()
            if password:
                psk_hex = _derive_wpa_psk(ssid, password)
            target.append({"ssid": ssid, "psk": psk_hex})

        target_ssids = {n["ssid"] for n in target}
        current_ssids = set(self.get_known_networks())

        # Remove networks not present in persistent config.
        for ssid in current_ssids - target_ssids:
            self.remove_network(ssid)

        # Add/update configured networks.
        for net in target:
            self._add_network_with_psk(net["ssid"], net["psk"])

    def _add_network_with_psk(self, ssid: str, psk_hex: str) -> Optional[int]:
        """Add a network using a pre-derived 64-hex PSK (skips passphrase derivation)."""
        self.remove_network(ssid)
        net_id = self.wpa.add_network()
        if net_id is None:
            log.error(f"Failed to allocate network slot for '{ssid}'")
            return None
        if not self.wpa.set_network(net_id, "ssid", ssid):
            self.wpa.remove_network(net_id)
            return None
        self.wpa.set_network(net_id, "scan_ssid", "1", quoted=False)
        if psk_hex:
            if not self.wpa.set_network(net_id, "psk", psk_hex, quoted=False):
                log.error(f"Failed to set PSK for '{ssid}'")
                self.wpa.remove_network(net_id)
                return None
        else:
            self.wpa.set_network(net_id, "key_mgmt", "NONE", quoted=False)
        self.wpa.enable_network(net_id)
        self.wpa.save_config()
        log.info(f"Imported network '{ssid}' (psk={'set' if psk_hex else 'open'})")
        return net_id

    def add_network(self, ssid: str, password: str) -> Optional[int]:
        """Add a network using wpa_cli with validation"""
        # Validate inputs
        valid, err = WpaCli.validate_ssid(ssid)
        if not valid:
            log.error(f"Invalid SSID: {err}")
            return None

        valid, err = WpaCli.validate_password(password)
        if not valid:
            log.error(f"Invalid password for '{ssid}': {err}")
            return None

        # Remove existing network with same SSID
        self.remove_network(ssid)

        # Add new network
        net_id = self.wpa.add_network()
        if net_id is None:
            log.error("Failed to add network")
            return None

        # Configure network
        if not self.wpa.set_network(net_id, "ssid", ssid):
            log.error(f"Failed to set SSID for network {net_id}")
            self.wpa.remove_network(net_id)
            return None

        # Enable active scanning for this SSID (helps find networks faster)
        self.wpa.set_network(net_id, "scan_ssid", "1", quoted=False)

        # Set password or open network
        if password:
            # WPA/WPA2: pre-derive 64-hex PSK so plaintext is never stored on disk.
            psk_hex = _derive_wpa_psk(ssid, password)
            if not self.wpa.set_network(net_id, "psk", psk_hex, quoted=False):
                log.error(f"Failed to set PSK for network {net_id}")
                self.wpa.remove_network(net_id)
                return None
        else:
            # Open network - no password
            if not self.wpa.set_network(net_id, "key_mgmt", "NONE", quoted=False):
                log.error(f"Failed to set key_mgmt for open network {net_id}")
                self.wpa.remove_network(net_id)
                return None

        # Enable network
        self.wpa.enable_network(net_id)

        # Save to config file
        self.wpa.save_config()

        log.info(f"Added network '{ssid}' (id={net_id})")
        return net_id

    def remove_network(self, ssid: str) -> bool:
        """Remove a network by SSID using wpa_cli"""
        net_id = self.wpa.find_network_by_ssid(ssid)
        if net_id is not None:
            self.wpa.remove_network(net_id)
            self.wpa.save_config()
            log.info(f"Removed network '{ssid}' (id={net_id})")
            return True
        return False

    # ========== Connection Management ==========

    def _is_connected_to(self, ssid: str) -> bool:
        """True only if WPA is completed AND currently on requested SSID."""
        status = self.wpa.status()
        return self.is_connected(status) and self.get_connected_ssid(status) == ssid

    def connect(self, ssid: str, password: str, preferred_bssid: str = None) -> tuple:
        """
        Connect to a WiFi network using wpa_cli
        Returns: (success: bool, error_message: str or None)
        """
        log.info(f"Connecting to '{ssid}'...")

        # Check if already connected to this SSID
        if self.is_connected() and self.get_connected_ssid() == ssid:
            log.info(f"Already connected to '{ssid}'")
            return True, None

        # Validate first
        valid, err = WpaCli.validate_ssid(ssid)
        if not valid:
            log.error(f"Connection rejected: {err}")
            return False, err

        valid, err = WpaCli.validate_password(password)
        if not valid:
            log.error(f"Connection rejected: {err}")
            return False, err

        # Check if network already exists in config
        net_id = self.wpa.find_network_by_ssid(ssid)
        if net_id is not None:
            log.info(f"Network '{ssid}' already configured (id={net_id}), selecting...")
        else:
            # Add network
            net_id = self.add_network(ssid, password)
            if net_id is None:
                # Check if maybe we got connected anyway
                time.sleep(2)
                if self.is_connected() and self.get_connected_ssid() == ssid:
                    log.info(f"Connected to '{ssid}' despite add_network error")
                    return True, None
                return False, "Failed to add network"

        if preferred_bssid:
            if self.wpa.set_network(net_id, "bssid", preferred_bssid, quoted=False):
                log.info(f"Using preferred BSSID for '{ssid}': {preferred_bssid}")
            else:
                log.warning(f"Failed to set preferred BSSID '{preferred_bssid}' for '{ssid}'")

        # Select this network (connects to it)
        if not self.wpa.select_network(net_id):
            log.warning(f"select_network failed for '{ssid}' (id={net_id}), trying enable+reconnect")
            self.wpa.enable_network(net_id)
            self.wpa.reconnect()

        # Wait for connection with polling
        for i in range(15):  # Max 15 seconds
            time.sleep(1)
            if self._is_connected_to(ssid):
                self._set_led(True)

                # Request DHCP
                self.renew_dhcp()

                # Wait for IP
                for _ in range(5):
                    ip = self.get_ip_address()
                    if ip and self._is_connected_to(ssid):
                        log.info(f"Connected to '{ssid}' with IP {ip}")
                        return True, None
                    time.sleep(1)

                if self._is_connected_to(ssid):
                    log.info(f"Connected to '{ssid}' (no IP yet)")
                    return True, None

        # One last check in case association completed at timeout boundary
        if self._is_connected_to(ssid):
                return True, None

        self._set_led(False)
        self.remove_network(ssid)
        log.warning(f"Failed to connect to '{ssid}'")
        return False, "Connection timeout - check password"

    def disconnect(self) -> bool:
        """Disconnect from current network"""
        return self.wpa.disconnect()

    def connect_saved(self, ssid: str, preferred_bssid: str = None) -> tuple:
        """
        Connect to a network using saved credentials.
        Returns: (success: bool, error_message: str or None)
        """
        log.info(f"Connecting to saved network '{ssid}'...")

        # Check if already connected
        if self.is_connected() and self.get_connected_ssid() == ssid:
            log.info(f"Already connected to '{ssid}'")
            return True, None

        # Find the network in saved config
        net_id = self.wpa.find_network_by_ssid(ssid)
        if net_id is None:
            log.warning(f"Network '{ssid}' not found in saved networks")
            return False, "Network not saved - password required"

        if preferred_bssid:
            if self.wpa.set_network(net_id, "bssid", preferred_bssid, quoted=False):
                log.info(f"Using preferred saved BSSID for '{ssid}': {preferred_bssid}")
            else:
                log.warning(f"Failed to set preferred saved BSSID '{preferred_bssid}' for '{ssid}'")

        # Select this network (connects using saved password)
        if not self.wpa.select_network(net_id):
            log.warning(f"select_network failed for saved '{ssid}' (id={net_id}), trying enable+reconnect")
            self.wpa.enable_network(net_id)
            self.wpa.reconnect()

        # Wait for connection
        for _ in range(15):
            time.sleep(1)
            if self._is_connected_to(ssid):
                self._set_led(True)
                self.renew_dhcp()

                for _ in range(5):
                    ip = self.get_ip_address()
                    if ip and self._is_connected_to(ssid):
                        log.info(f"Connected to '{ssid}' with IP {ip}")
                        return True, None
                    time.sleep(1)

                if self._is_connected_to(ssid):
                    log.info(f"Connected to '{ssid}' (no IP yet)")
                    return True, None

        if self._is_connected_to(ssid):
                return True, None

        self._set_led(False)
        log.warning(f"Failed to connect to saved network '{ssid}'")
        return False, "Connection failed - password may have changed"

    def try_known_networks(self) -> bool:
        """Try to connect to any known network in range"""
        available = self.scan_networks()
        available_ssids = [n["ssid"] for n in available]
        known = self.get_known_networks()

        for ssid in known:
            if ssid in available_ssids:
                log.info(f"Known network in range: '{ssid}'")

                # Find and select this network
                net_id = self.wpa.find_network_by_ssid(ssid)
                if net_id is not None:
                    self.wpa.select_network(net_id)

                    # Wait for connection
                    for _ in range(10):
                        time.sleep(1)
                        if self.is_connected():
                            self._set_led(True)
                            self.renew_dhcp()
                            log.info(f"Connected to '{ssid}'")
                            return True

        return False

    def check_connection(self) -> bool:
        """Check and maintain connection"""
        if self.is_connected():
            if not self.can_ping():
                log.warning("Connected but no internet, renewing DHCP...")
                self.renew_dhcp()
            return True
        return False

    def get_mac_address(self) -> str:
        """Get MAC address of interface"""
        try:
            with open(f"/sys/class/net/{self.interface}/address", "r") as f:
                return f.read().strip().upper()
        except:
            return None

    def get_status(self) -> dict:
        """Get client status"""
        wpa_status = self.wpa.status()
        client_connected = self.is_connected(wpa_status)
        return {
            "client_connected": client_connected,
            "client_ssid": self.get_connected_ssid(wpa_status),
            "client_ip": self.get_ip_address(wpa_status),
            "client_mac": self.get_mac_address(),
            "client_interface": self.interface,
            "wpa_state": wpa_status.get("wpa_state", "UNKNOWN")
        }
