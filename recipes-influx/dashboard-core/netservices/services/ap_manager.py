#!/usr/bin/env python3
"""
AP Manager - Manages Access Point on wlan1
Always running, never stopped
"""

import json
import logging
import os
import re
import time
from pathlib import Path

log = logging.getLogger(__name__)
TRACE_VERBOSE = os.environ.get("REXGEN_TRACE_VERBOSE", "1") == "1"

# ========== Configuration ==========

# Interfaces
IFACE_AP = "wlan1"
IFACE_BASE = "wlan0"  # Base interface for creating virtual AP

# AP Network
AP_IP = "192.168.51.1"
AP_NETMASK = "255.255.255.0"
AP_PASSWORD = "12345678"

# DHCP Range
DHCP_START = "192.168.51.2"
DHCP_END = "192.168.51.40"
DHCP_LEASE = "24h"

# DNS - no external server needed with captive portal (address=/#/)

# WiFi
WIFI_CHANNEL = 6
WIFI_HW_MODE = "g"  # g=2.4GHz, a=5GHz

# Config file paths
HOSTAPD_CONF = "/etc/hostapd.conf"
DNSMASQ_CONF = "/etc/dnsmasq.conf"
HOSTAPD_CTRL_DIR = "/var/run/hostapd"
BLOCKED_FILE = "/tmp/rexgen/ap_blocked.json"
DHCP_LEASES = "/var/lib/misc/dnsmasq.leases"

# Block duration
BLOCK_DURATION = 300  # 5 minutes


class APManager:
    """Manages Access Point mode on wlan1"""

    def __init__(self, serial: str, run_cmd):
        self.serial = serial
        self.ssid = f"INF-{serial}"
        self.password = AP_PASSWORD
        self.ip = AP_IP
        self.channel = WIFI_CHANNEL
        self.interface = IFACE_AP
        self._run = run_cmd
        self._systemctl = lambda action, svc: run_cmd(f"systemctl {action} {svc}")

    def _trace(self, msg: str):
        if TRACE_VERBOSE:
            log.info(f"[TRACE][AP] {msg}")

    def _hostapd_cli(self, cmd: str):
        """Run hostapd_cli against explicit control socket path."""
        self._run(f"hostapd_cli -p {HOSTAPD_CTRL_DIR} -i {self.interface} {cmd}")

    def _hostapd_cli_output(self, cmd: str) -> str:
        """Run hostapd_cli and return raw output."""
        return self._run(f"hostapd_cli -p {HOSTAPD_CTRL_DIR} -i {self.interface} {cmd}")

    def _get_hostapd_config(self) -> str:
        """Generate hostapd configuration"""
        return f"""interface={self.interface}
driver=nl80211
ssid={self.ssid}
hw_mode={WIFI_HW_MODE}
channel={self.channel}
ieee80211n=1
wmm_enabled=1
auth_algs=1
wpa=2
wpa_passphrase={self.password}
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
"""

    def configure_hostapd(self) -> bool:
        """Write hostapd configuration. Returns True if config changed."""
        config = self._get_hostapd_config()
        config_path = Path(HOSTAPD_CONF)

        # Check if config already matches
        if config_path.exists():
            existing = config_path.read_text()
            if existing == config:
                log.info(f"Hostapd config unchanged: SSID={self.ssid}")
                return False

        config_path.write_text(config)
        log.info(f"Hostapd configured: SSID={self.ssid}")
        return True

    def _get_dnsmasq_config(self) -> str:
        """Generate dnsmasq configuration for captive portal"""
        return f"""interface={self.interface}
listen-address={self.ip}
bind-interfaces
dhcp-range={DHCP_START},{DHCP_END},{AP_NETMASK},{DHCP_LEASE}
dhcp-option=3,{self.ip}
dhcp-option=6,{self.ip}
address=/#/{self.ip}
"""

    def configure_dnsmasq(self) -> bool:
        """Write dnsmasq configuration. Returns True if config changed."""
        config = self._get_dnsmasq_config()
        config_path = Path(DNSMASQ_CONF)

        # Check if config already matches
        if config_path.exists():
            existing = config_path.read_text()
            if existing == config:
                log.info("Dnsmasq config unchanged")
                return False

        config_path.write_text(config)
        log.info("Dnsmasq configured")
        return True

    def interface_exists(self) -> bool:
        """Check if AP interface exists"""
        return Path(f"/sys/class/net/{self.interface}").exists()

    def create_virtual_interface(self) -> bool:
        """Create virtual AP interface from base interface (wlan0 -> wlan1)"""
        if self.interface_exists():
            log.info(f"Interface {self.interface} already exists")
            return True

        log.info(f"Creating virtual interface {self.interface} from {IFACE_BASE}")

        # Remove if exists but in bad state
        self._run(f"iw dev {self.interface} del 2>/dev/null || true")

        # Create virtual AP interface
        result = self._run(f"iw dev {IFACE_BASE} interface add {self.interface} type __ap")

        if self.interface_exists():
            log.info(f"Virtual interface {self.interface} created successfully")
            return True
        else:
            log.error(f"Failed to create {self.interface}: {result}")
            return False

    def _get_interface_ip(self) -> str:
        """Get current IP of interface"""
        output = self._run(f"ip -4 addr show {self.interface} 2>/dev/null | grep -oP 'inet \\K[\\d.]+'")
        return output.strip() if output else None

    def get_runtime_channel(self) -> int:
        """Get current AP channel from iw runtime info."""
        out = self._run(f"iw dev {self.interface} info 2>/dev/null")
        m = re.search(r"channel\s+(\d+)\s+\(", out or "")
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                pass
        return self.channel

    def sync_channel(self, target_channel: int) -> tuple:
        """Best-effort AP channel sync. Returns (ok, info_or_none).
        This path must be non-disruptive during STA connects, so it never
        restarts hostapd here.
        """
        try:
            ch = int(target_channel)
        except (TypeError, ValueError):
            return False, "Invalid target channel"

        if ch < 1 or ch > 14:
            return False, f"Unsupported AP channel {ch}"

        current = self.get_runtime_channel()
        if current == ch:
            self.channel = ch
            return True, None

        log.info(f"[TRACE][AP] Sync channel request current={current} target={ch}")
        self.channel = ch
        self.configure_hostapd()
        # Try runtime channel switch if hostapd supports it; if not, keep AP
        # stable and apply the channel on next regular AP start.
        freq = 2484 if ch == 14 else (2407 + ch * 5)
        out = self._hostapd_cli_output(f"chan_switch 3 {freq}")
        self._trace(f"sync_channel chan_switch target={ch} freq={freq} out='{(out or '').strip()}'")
        time.sleep(1)
        new_ch = self.get_runtime_channel()
        if new_ch == ch:
            return True, None
        return True, f"Deferred AP channel switch to {ch} (runtime switch unavailable)"

    def setup_interface(self) -> bool:
        """Configure network interface. Returns True if changes were made."""
        # Ensure interface exists first
        if not self.create_virtual_interface():
            log.error("Cannot setup interface - creation failed")
            return False

        # Check if already configured correctly
        current_ip = self._get_interface_ip()
        if current_ip == self.ip:
            log.info(f"Interface {self.interface} already configured with IP {self.ip}")
            return False  # No changes made

        # Need to configure
        self._run(f"ip addr flush dev {self.interface}")
        self._run(f"ip addr add {self.ip}/24 dev {self.interface}")
        self._run(f"ip link set {self.interface} up")
        log.info(f"Interface {self.interface} configured with IP {self.ip}")
        return True  # Changes made

    def start(self, force: bool = False):
        """Start Access Point. Avoid disruptive service restarts; prefer start-only."""
        log.info(f"Starting AP on {self.interface}: {self.ssid}")

        # Setup interface first
        self.setup_interface()

        # Check if already running correctly
        already_running = self.is_running()

        # Configure (returns True if config changed)
        hostapd_changed = self.configure_hostapd()
        dnsmasq_changed = self.configure_dnsmasq()

        # Start hostapd if needed (no restart to avoid AP drops)
        if force or not already_running or hostapd_changed:
            log.info("Starting hostapd if not active...")
            self._systemctl("unmask", "hostapd")
            self._systemctl("start", "hostapd")
            time.sleep(2)
        else:
            log.info("Hostapd already running with correct config, skipping restart")

        dnsmasq_running = self.is_dnsmasq_running()
        if force or dnsmasq_changed or not dnsmasq_running:
            log.info("Starting dnsmasq if not active...")
            self._systemctl("start", "dnsmasq")
        else:
            log.info("Dnsmasq already running with correct config, skipping restart")

        log.info("AP started successfully")
        return True

    def is_running(self) -> bool:
        """Check if AP is running"""
        output = self._run("systemctl is-active hostapd")
        return "active" in output

    def is_dnsmasq_running(self) -> bool:
        """Check if dnsmasq is running"""
        output = self._run("systemctl is-active dnsmasq")
        return "active" in output

    def is_interface_up(self) -> bool:
        """Check if interface exists and is UP"""
        if not self.interface_exists():
            return False
        output = self._run(f"ip link show {self.interface} 2>/dev/null")
        return "UP" in output and "state UP" in output

    def ensure_running(self):
        """Make sure AP interface and services are running"""
        # Check interface first
        if not self.is_interface_up():
            log.warning(f"AP interface {self.interface} is down, bringing up...")
            self.setup_interface()
            # Start hostapd without restart to avoid dropping existing sessions
            self._systemctl("start", "hostapd")
            return

        # Check if IP is correct
        current_ip = self._get_interface_ip()
        if current_ip != self.ip:
            log.warning(f"AP interface has wrong IP ({current_ip}), reconfiguring...")
            self.setup_interface()

        # Check hostapd
        if not self.is_running():
            log.warning("Hostapd not running, restarting...")
            self.start()
            return

        # Check dnsmasq
        if not self.is_dnsmasq_running():
            log.warning("Dnsmasq not running, starting...")
            self._systemctl("start", "dnsmasq")

    # ========== Client Management ==========

    def get_connected_clients(self) -> list:
        """Get list of clients connected to AP.
        Uses iw station dump as source of truth for *currently associated* clients.
        DHCP leases are used only to enrich station entries with hostname/IP.
        """
        self._trace("get_connected_clients start")
        def parse_iw_stations(raw_output: str) -> dict:
            parsed = {}
            current = None
            for raw_line in (raw_output or "").splitlines():
                line = raw_line.strip()
                m = re.match(r"Station\s+([0-9a-fA-F:]{17})", line)
                if m:
                    current = m.group(1).lower()
                    parsed[current] = {"mac": current, "signal": None, "hostname": None, "ip": None}
                elif current and "signal:" in line:
                    sig_match = re.search(r"signal:\s*(-?\d+)", line)
                    if sig_match:
                        parsed[current]["signal"] = int(sig_match.group(1))
            return parsed

        stations = {}
        for attempt in range(3):
            output = self._run(f"iw dev {self.interface} station dump 2>/dev/null")
            stations = parse_iw_stations(output)
            self._trace(f"iw station parse attempt={attempt + 1} count={len(stations)}")
            if stations:
                break
            if attempt < 2:
                time.sleep(0.15)

        # Fallback: some drivers intermittently return empty station dump.
        if not stations:
            self._trace("iw returned empty stations, trying hostapd_cli list_sta fallback")
            sta_output = self._hostapd_cli_output("list_sta")
            if not (sta_output or "").strip():
                # Alternate hostapd_cli invocation for environments where -p path is unreliable.
                sta_output = self._run(f"hostapd_cli -i {self.interface} list_sta")
            for line in (sta_output or "").splitlines():
                mac = line.strip().lower()
                if re.match(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$", mac):
                    stations[mac] = {"mac": mac, "signal": None, "hostname": None, "ip": None}
            self._trace(f"hostapd list_sta parse count={len(stations)}")

        # Cross-reference with DHCP leases for hostname and IP.
        # Do not add lease-only entries here: leases include recently disconnected devices.
        try:
            now = int(time.time())
            leases = Path(DHCP_LEASES).read_text()
            matched_leases = 0
            for lease_line in leases.splitlines():
                # Format: expiry mac ip hostname client-id
                parts = lease_line.split()
                if len(parts) >= 4:
                    try:
                        expiry = int(parts[0])
                    except ValueError:
                        expiry = 0
                    if expiry and expiry <= now:
                        continue
                    lease_mac = parts[1].lower()
                    if lease_mac not in stations:
                        continue
                    stations[lease_mac]["ip"] = parts[2]
                    hostname = parts[3]
                    if hostname != "*":
                        stations[lease_mac]["hostname"] = hostname
                    matched_leases += 1
            self._trace(f"lease enrichment matched={matched_leases} final_clients={len(stations)}")
        except (FileNotFoundError, IOError):
            self._trace("lease enrichment skipped (lease file missing or unreadable)")

        clients = list(stations.values())
        self._trace(f"get_connected_clients done clients={len(clients)} macs={[c['mac'] for c in clients]}")
        return clients

    def _read_blocked(self) -> dict:
        """Read blocked clients file. Returns {mac: expiry_timestamp}"""
        try:
            with open(BLOCKED_FILE, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, IOError):
            return {}

    def _write_blocked(self, blocked: dict):
        """Write blocked clients file atomically"""
        temp = BLOCKED_FILE + ".tmp"
        with open(temp, "w") as f:
            json.dump(blocked, f)
        os.rename(temp, BLOCKED_FILE)

    def block_client(self, mac: str):
        """Block a client for BLOCK_DURATION seconds"""
        mac = mac.lower()
        log.info(f"Blocking AP client {mac} for {BLOCK_DURATION}s")

        # Force immediate drop (some clients ignore a single deauth/disassoc frame)
        for _ in range(3):
            self._hostapd_cli(f"disassociate {mac}")
            self._hostapd_cli(f"deauthenticate {mac}")
            time.sleep(0.15)

        # Save to blocked list
        blocked = self._read_blocked()
        blocked[mac] = time.time() + BLOCK_DURATION
        self._write_blocked(blocked)

    def unblock_client(self, mac: str):
        """Remove a client from the block list"""
        mac = mac.lower()
        log.info(f"Unblocking AP client {mac}")
        blocked = self._read_blocked()
        blocked.pop(mac, None)
        self._write_blocked(blocked)

    def get_blocked_clients(self) -> dict:
        """Return currently blocked clients {mac: expiry_timestamp}"""
        return self._read_blocked()

    def cleanup_expired_blocks(self):
        """Remove expired entries from block list"""
        blocked = self._read_blocked()
        now = time.time()
        expired = [mac for mac, expiry in blocked.items() if expiry <= now]
        if expired:
            for mac in expired:
                log.info(f"Block expired for {mac}")
                del blocked[mac]
            self._write_blocked(blocked)

    def enforce_blocks(self, connected=None):
        """Re-kick any blocked clients that reconnected"""
        blocked = self._read_blocked()
        if not blocked:
            return
        now = time.time()
        if connected is None:
            connected = self.get_connected_clients()
        for client in connected:
            mac = client["mac"]
            if mac in blocked and blocked[mac] > now:
                log.info(f"Re-kicking blocked client {mac}")
                self._hostapd_cli(f"disassociate {mac}")
                self._hostapd_cli(f"deauthenticate {mac}")

    def get_status(self) -> dict:
        """Get AP status"""
        ap_channel = self.get_runtime_channel()
        return {
            "ap_mode": self.is_running(),
            "ap_ssid": self.ssid,
            "ap_ip": self.ip,
            "ap_interface": self.interface,
            "ap_channel": ap_channel
        }
