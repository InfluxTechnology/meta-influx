#!/usr/bin/env python3
"""
WiFi Manager Service - Main orchestrator

Components:
- APManager (wlan1) - Access Point, always running
- ClientManager (wlan0) - Connects to external networks via wpa_cli
- LED control for connection status

Note: Failover/routing handled separately by bash scripts
"""

import os
import sys
import subprocess
import time
import logging
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shared_state import wifi_state
from ap_manager import APManager
from client_manager import ClientManager, cleanup_wpa_config
from netservices_config import NetservicesConfig

# ========== Configuration ==========

# Device paths
SERIAL_FILE = "/home/root/rexusb/var/serial"
LED_PATH = "/sys/class/leds/JA35/brightness"

# Log file
LOG_FILE = "/var/log/wifi_manager.log"

# Timing intervals (seconds)
# Keep loop responsive; expensive operations are throttled by cache windows.
MAIN_LOOP_INTERVAL = 1
DEFAULT_NETWORK_SCAN_CONFIG = {
    "cache_seconds": 10,
    "auto_scan_requires_dashboard_client": True
}
DEFAULT_AP_CLIENTS_CONFIG = {
    "cache_seconds": 10,
    "auto_update_requires_dashboard_client": True
}
CONNECT_LOCK_TIMEOUT_SECONDS = 90

# Setup logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("wifi_manager")
TRACE_VERBOSE = os.environ.get("REXGEN_TRACE_VERBOSE", "0") == "1"
CONNECT_FORENSICS = os.environ.get("REXGEN_CONNECT_FORENSICS", "0") == "1"


class WifiManager:
    """Main WiFi manager - orchestrates all network components"""

    def __init__(self):
        self._loop_id = 0
        self.serial = self._get_serial()
        self.network_scan_cfg = dict(DEFAULT_NETWORK_SCAN_CONFIG)
        self.ap_clients_cfg = dict(DEFAULT_AP_CLIENTS_CONFIG)

        # Clean up wpa_supplicant.conf on startup
        removed = cleanup_wpa_config()
        if removed:
            log.info(f"Startup cleanup: removed {removed} invalid networks from wpa_supplicant.conf")

        # Initialize managers
        self.ap = APManager(self.serial, self._run)
        self.client = ClientManager(self._run, self._set_led)
        self.persist_cfg = NetservicesConfig()
        self._sta_restore_done = False
        self._sta_restore_succeeded = False
        self._sta_restore_retries = 0
        self._apply_or_bootstrap_persistent_ap_psk()

        # Cache tracking
        self._last_ap_clients_update = 0
        self._last_networks_update = 0

        # Clear stale connection state from previous run
        wifi_state.update({
            "serial_number": self.serial,
            "connect_in_progress": False,
            "connect_target": None
        })
        log.info(f"WiFi Manager initialized. Serial: {self.serial}")
        self._trace(f"verbose={TRACE_VERBOSE} scan_cfg={self.network_scan_cfg} ap_cfg={self.ap_clients_cfg}")

    def _apply_or_bootstrap_persistent_ap_psk(self):
        """Apply AP PSK from persistent config, or bootstrap config on first run."""
        try:
            if self.persist_cfg.exists():
                data = self.persist_cfg.read()
                persisted_psk = (data.get("ap_psk") or "").strip().lower()
                if self.ap._is_valid_psk_hex(persisted_psk):
                    self.ap.psk = persisted_psk
                    log.info("Applied AP PSK from /data/rexgen/config/netservices.conf")
                else:
                    # Legacy migration path: AP.password in config.
                    legacy_password = (data.get("ap_password") or "").strip()
                    if 8 <= len(legacy_password) <= 63:
                        self.ap.psk = self.ap._derive_psk(self.ap.ssid, legacy_password)
                        self.persist_cfg.write_ap_psk(self.ap.psk)
                        log.info("Migrated legacy AP password to AP PSK in netservices.conf")
                    else:
                        hostapd_psk = (self.ap.get_configured_psk() or "").strip().lower()
                        if self.ap._is_valid_psk_hex(hostapd_psk):
                            self.ap.psk = hostapd_psk
                            self.persist_cfg.write_ap_psk(hostapd_psk)
                            log.info("Persistent AP PSK missing/invalid; synced from /etc/hostapd.conf")
            else:
                hostapd_psk = (self.ap.get_configured_psk() or "").strip().lower()
                if self.ap._is_valid_psk_hex(hostapd_psk):
                    self.ap.psk = hostapd_psk
                self.persist_cfg.write_all(self.ap.psk, self.client.export_saved_networks())
                log.info("Created /data/rexgen/config/netservices.conf from current runtime settings")
        except Exception as e:
            log.warning(f"Persistent AP PSK setup failed: {e}")

    def _restore_sta_networks_from_persistent(self):
        """Apply STA saved networks from persistent config. Retries if wpa_supplicant not ready."""
        if self._sta_restore_done:
            return
        _MAX_RETRIES = 15
        if self._sta_restore_retries >= _MAX_RETRIES:
            log.warning("STA restore: gave up after %d attempts (wpa_supplicant not ready)", _MAX_RETRIES)
            self._sta_restore_done = True
            return
        self._sta_restore_retries += 1
        try:
            if not self.persist_cfg.exists():
                self._sta_restore_done = True
                self._sta_restore_succeeded = True
                return
            data = self.persist_cfg.read()
            networks = data.get("sta_networks") or []
            if not networks:
                self._sta_restore_done = True
                self._sta_restore_succeeded = True
                return
            self.client.import_saved_networks(networks)
            # Verify wpa_supplicant actually accepted the networks (socket was ready)
            if self.client.get_known_networks():
                self._sta_restore_done = True
                self._sta_restore_succeeded = True
                log.info(
                    "Applied %d saved STA networks from netservices.conf (attempt %d)",
                    len(networks), self._sta_restore_retries
                )
            else:
                log.warning(
                    "STA restore attempt %d/%d: wpa_supplicant not ready, will retry",
                    self._sta_restore_retries, _MAX_RETRIES
                )
        except Exception as e:
            log.warning(f"STA restore from persistent config failed: {e}")
            self._sta_restore_done = True

    def _persist_runtime_settings(self):
        """Persist AP PSK and STA saved networks to /data."""
        try:
            exported = self.client.export_saved_networks()
            # Guard: if wpa_supplicant.conf is empty but restore hasn't succeeded yet,
            # only update the PSK to avoid wiping saved networks due to a startup race
            # (e.g. wpa_supplicant not ready when restore ran after a firmware update).
            if not exported and not self._sta_restore_succeeded:
                existing = (self.persist_cfg.read() or {}).get("sta_networks") or []
                if existing:
                    log.warning(
                        "Skipping STA persist: wpa_supplicant.conf empty but %d networks in "
                        "persistent config (restore not confirmed). Updating PSK only.",
                        len(existing)
                    )
                    self.persist_cfg.write_ap_psk(self.ap.psk)
                    return
            self.persist_cfg.write_all(self.ap.psk, exported)
        except Exception as e:
            log.warning(f"Failed to persist netservices settings: {e}")

    def _trace(self, msg: str):
        if TRACE_VERBOSE:
            log.info(f"[TRACE] {msg}")

    @staticmethod
    def _is_connect_sensitive_cmd(cmd: str) -> bool:
        markers = (
            "wpa_cli",
            "ip addr flush dev wlan0",
            "udhcpc -i wlan0",
            "dhclient",
            "iw dev wlan0",
            "iw dev wlan1",
            "ifconfig wlan0",
            "ip link set wlan0",
        )
        c = (cmd or "").lower()
        return any(m in c for m in markers)

    def _ap_station_snapshot(self) -> tuple:
        """Best-effort AP station snapshot: (count, [macs])."""
        try:
            res = subprocess.run(
                "iw dev wlan1 station dump 2>/dev/null",
                shell=True, capture_output=True, text=True, timeout=5
            )
            macs = []
            for line in (res.stdout or "").splitlines():
                m = line.strip()
                if m.startswith("Station "):
                    parts = m.split()
                    if len(parts) >= 2:
                        macs.append(parts[1].lower())
            return len(macs), macs
        except Exception:
            return -1, []

    def _refresh_networks(self, force: bool = False):
        """Refresh scanned networks respecting cache window unless forced."""
        now = time.time()
        cache_seconds = int(self.network_scan_cfg.get("cache_seconds", 15))
        if not force and self._last_networks_update and (now - self._last_networks_update) < cache_seconds:
            self._trace(f"_refresh_networks skipped force={force} age={now - self._last_networks_update:.2f}s cache={cache_seconds}s")
            return
        self._trace(f"_refresh_networks start force={force}")
        networks = self.client.scan_networks()
        networks = self._merge_network_history(wifi_state.get("networks", []), networks)
        wifi_state.update({
            "networks": networks,
            "known_networks": self.client.get_known_networks(),
            "last_scan": now
        })
        self._last_networks_update = now
        self._trace(f"_refresh_networks done networks={len(networks)}")

    def _refresh_ap_clients(self, force: bool = False):
        """Refresh AP clients/blocked cache respecting cache window unless forced."""
        now = time.time()
        cache_seconds = int(self.ap_clients_cfg.get("cache_seconds", 15))
        if not force and self._last_ap_clients_update and (now - self._last_ap_clients_update) < cache_seconds:
            self._trace(f"_refresh_ap_clients skipped force={force} age={now - self._last_ap_clients_update:.2f}s cache={cache_seconds}s")
            return
        self._trace(f"_refresh_ap_clients start force={force}")
        self.ap.cleanup_expired_blocks()
        clients = self.ap.get_connected_clients()
        self.ap.enforce_blocks(connected=clients)
        blocked = self.ap.get_blocked_clients()
        wifi_state.update({
            "ap_clients": clients,
            "ap_blocked": blocked,
            "ap_clients_updated_at": now
        })
        self._last_ap_clients_update = now
        self._trace(f"_refresh_ap_clients done clients={len(clients)} blocked={len(blocked)}")

    @staticmethod
    def _get_mender_artifact() -> str:
        """Read current Mender artifact name from /etc/mender/artifact_info."""
        try:
            content = Path("/etc/mender/artifact_info").read_text()
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("artifact_name="):
                    return line.split("=", 1)[1].strip()
        except Exception:
            pass
        return ""

    def _check_ota_and_reinit(self) -> bool:
        """Detect Mender OTA update by comparing artifact_name with stored value.

        Returns True if an update was detected (caller should force AP/dnsmasq restart).
        Stores the current artifact name in netservices.conf so subsequent boots skip reinit.
        """
        current = self._get_mender_artifact()
        if not current:
            return False
        try:
            stored = self.persist_cfg.read_mender_artifact()
            if stored == current:
                return False
            log.info(
                "OTA update detected: '%s' -> '%s'. Forcing full re-initialization.",
                stored or "(none)", current
            )
            # Record new artifact immediately so a crash/restart doesn't re-trigger.
            self.persist_cfg.write_mender_artifact(current)
            return True
        except Exception as e:
            log.warning(f"OTA artifact check failed: {e}")
            return False

    def _get_serial(self) -> str:
        """Read device serial number"""
        try:
            serial = Path(SERIAL_FILE).read_text().strip()
            return "".join(filter(str.isprintable, serial))
        except Exception as e:
            log.warning(f"Could not read serial: {e}")
            return "UNKNOWN"

    def _set_led(self, on: bool):
        """LED control disabled - handled by separate led_blink.sh script"""
        pass

    def _run(self, cmd: str, timeout: int = 30) -> str:
        """Run shell command safely"""
        try:
            forensic = False
            trace_id = None
            before_count = before_macs = None
            if CONNECT_FORENSICS:
                if wifi_state.get("connect_in_progress", False) and self._is_connect_sensitive_cmd(cmd):
                    forensic = True
                    trace_id = wifi_state.get("connect_trace_id")
                    before_count, before_macs = self._ap_station_snapshot()
                    self._trace(
                        f"[CF] before trace_id={trace_id} cmd='{cmd}' ap_count={before_count} ap_macs={before_macs}"
                    )
            self._trace(f"_run cmd='{cmd}' timeout={timeout}")
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=timeout
            )
            self._trace(f"_run rc={result.returncode} stdout_len={len(result.stdout or '')} stderr_len={len(result.stderr or '')}")
            if forensic:
                after_count, after_macs = self._ap_station_snapshot()
                self._trace(
                    f"[CF] after trace_id={trace_id} cmd='{cmd}' rc={result.returncode} "
                    f"ap_count={after_count} ap_macs={after_macs}"
                )
            return result.stdout
        except subprocess.TimeoutExpired:
            log.error(f"Command timeout: {cmd}")
            return ""
        except Exception as e:
            log.error(f"Command failed: {cmd} - {e}")
            return ""

    def update_state(self):
        """Update shared state with current status"""
        self._trace("update_state start")
        ap_status = self.ap.get_status()
        client_status = self.client.get_status()

        connected_ssid = client_status.get("client_ssid") if client_status.get("client_connected") else None
        client_ip = client_status.get("client_ip")

        # Clear connect_error if now connected
        update_data = {
            **ap_status,
            **client_status,
            "connected_ssid": connected_ssid,
            "client_ip": client_ip,
            "known_networks": self.client.get_known_networks()
        }
        if connected_ssid:
            update_data["connect_error"] = None

        wifi_state.update(update_data)
        self._trace(
            f"update_state done connected_ssid={connected_ssid} client_ip={client_ip} "
            f"ap_mode={ap_status.get('ap_mode')} wpa_state={client_status.get('wpa_state')}"
        )

    @staticmethod
    def _merge_network_history(previous: list, current: list) -> list:
        """Merge scan results with previous data and keep union of detected bands per SSID."""
        prev_map = {}
        for net in previous or []:
            if isinstance(net, dict) and net.get("ssid"):
                prev_map[net["ssid"]] = net

        merged = []
        for net in current or []:
            if not isinstance(net, dict):
                continue
            ssid = net.get("ssid")
            if not ssid:
                continue

            prev = prev_map.get(ssid, {})
            prev_bands = prev.get("bands", []) if isinstance(prev, dict) else []
            curr_bands = net.get("bands", [])
            bands = sorted(set((prev_bands or []) + (curr_bands or [])), key=lambda b: {"2.4 GHz": 0, "5 GHz": 1, "6 GHz": 2}.get(b, 99))

            merged_net = dict(net)
            if bands:
                merged_net["bands"] = bands
            merged.append(merged_net)
        return merged

    @staticmethod
    def _freq_to_channel(freq) -> int:
        try:
            f = int(freq)
        except (TypeError, ValueError):
            return None
        if 2412 <= f <= 2484:
            if f == 2484:
                return 14
            return int((f - 2407) / 5)
        if 5000 <= f <= 5900:
            return int((f - 5000) / 5)
        if 5925 <= f <= 7125:
            return int((f - 5950) / 5)
        return None

    def _target_channel_for_ssid(self, ssid: str) -> int:
        """Best-effort channel detection from cached scan results."""
        best_signal = -999
        best_ch = None
        for net in (wifi_state.get("networks", []) or []):
            if not isinstance(net, dict):
                continue
            if net.get("ssid") != ssid:
                continue
            ch = self._freq_to_channel(net.get("frequency"))
            if not ch:
                continue
            try:
                sig = int(net.get("signal", -100))
            except (TypeError, ValueError):
                sig = -100
            if sig > best_signal:
                best_signal = sig
                best_ch = ch
        return best_ch

    def _preferred_bssid_for_ssid_channel(self, ssid: str, channel: int) -> str:
        """Pick strongest BSSID for SSID on the requested channel from cached scan."""
        best_signal = -999
        best_bssid = None
        for net in (wifi_state.get("networks", []) or []):
            if not isinstance(net, dict):
                continue
            if net.get("ssid") != ssid:
                continue
            if self._freq_to_channel(net.get("frequency")) != channel:
                continue
            bssid = (net.get("bssid") or "").strip()
            if not bssid:
                continue
            try:
                sig = int(net.get("signal", -100))
            except (TypeError, ValueError):
                sig = -100
            if sig > best_signal:
                best_signal = sig
                best_bssid = bssid
        return best_bssid

    def process_requests(self):
        """Process requests from dashboard"""
        self._trace("process_requests tick")
        # Safety watchdog: never leave global connect lock stuck forever.
        if wifi_state.get("connect_in_progress", False):
            started = wifi_state.get("connect_started_at", 0)
            if started and (time.time() - started) > CONNECT_LOCK_TIMEOUT_SECONDS:
                wifi_state.update({
                    "connect_in_progress": False,
                    "connect_target": None,
                    "connect_error": "Connection attempt timed out (watchdog). Please retry.",
                    "connect_finished_at": time.time()
                })
                log.warning("Cleared stale connect_in_progress via watchdog timeout")
            else:
                self._trace(f"connect lock active started_at={started}")

        if wifi_state.get("connect_in_progress", False):
            # While connecting, do not process scan requests or background AP user refresh requests.
            # Only allow finishing the current connect and explicit block/unblock control.
            pass

        # Connect request
        request = wifi_state.get_connect_request()
        if request:
            ssid = request.get("ssid")
            password = request.get("password", "")
            use_saved = request.get("use_saved", False)
            connect_trace_id = f"{int(time.time() * 1000)}-{os.getpid()}"
            self._trace(
                f"connect request received trace_id={connect_trace_id} ssid='{ssid}' use_saved={use_saved} password_len={len(password or '')}"
            )
            wifi_state.update({
                "connect_in_progress": True,
                "connect_target": ssid,
                "connect_started_at": time.time(),
                "connect_error": None,
                "connect_trace_id": connect_trace_id
            })

            target_ch = self._target_channel_for_ssid(ssid)
            ap_ch = self.ap.get_runtime_channel()
            preferred_bssid = self._preferred_bssid_for_ssid_channel(ssid, ap_ch)
            self._trace(f"connect precheck trace_id={connect_trace_id} ssid='{ssid}' target_ch={target_ch} ap_ch={ap_ch}")
            if target_ch:
                self._trace(
                    f"connect precheck trace_id={connect_trace_id} "
                    f"target_ch={target_ch} ap_ch={ap_ch} no_runtime_ap_channel_sync"
                )
            if preferred_bssid:
                self._trace(
                    f"connect precheck trace_id={connect_trace_id} "
                    f"preferred_bssid='{preferred_bssid}' on ap_ch={ap_ch}"
                )

            # If use_saved flag set, try connecting with saved password first
            if use_saved and not password:
                self._trace(f"connect path connect_saved ssid='{ssid}'")
                success, error = self.client.connect_saved(ssid, preferred_bssid=preferred_bssid)
            else:
                self._trace(f"connect path connect ssid='{ssid}'")
                success, error = self.client.connect(ssid, password, preferred_bssid=preferred_bssid)

            if success:
                self._trace(f"connect success trace_id={connect_trace_id} ssid='{ssid}' ip={self.client.get_ip_address()}")
                wifi_state.update({
                    "connected_ssid": ssid,
                    "client_ip": self.client.get_ip_address(),
                    "connect_error": None,
                    "known_networks": self.client.get_known_networks(),
                    "connect_in_progress": False,
                    "connect_target": None,
                    "connect_finished_at": time.time(),
                    "connect_trace_id": connect_trace_id
                })
                self._persist_runtime_settings()
            else:
                self._trace(f"connect failed trace_id={connect_trace_id} ssid='{ssid}' error='{error}'")
                wifi_state.update({
                    "connect_error": error,
                    "connect_in_progress": False,
                    "connect_target": None,
                    "connect_finished_at": time.time(),
                    "connect_trace_id": connect_trace_id
                })
                log.warning(f"Connect failed: {error}")
            return

        # Saved network management request
        saved_req = wifi_state.get_saved_network_request()
        if saved_req:
            self._trace(f"saved network request payload={saved_req}")
            action = saved_req.get("action")
            ssid = (saved_req.get("ssid") or "").strip()
            password = saved_req.get("password", "")

            if action == "add":
                valid, err = self.client.wpa.validate_ssid(ssid)
                if not valid:
                    wifi_state.update({"saved_network_error": err})
                    return
                valid, err = self.client.wpa.validate_password(password)
                if not valid:
                    wifi_state.update({"saved_network_error": err})
                    return

                net_id = self.client.add_network(ssid, password)
                if net_id is None:
                    wifi_state.update({"saved_network_error": "Failed to save network"})
                else:
                    wifi_state.update({
                        "known_networks": self.client.get_known_networks(),
                        "saved_network_error": None,
                        "saved_network_last_action": f"Saved '{ssid}'"
                    })
                    self._persist_runtime_settings()
            elif action == "delete":
                if not ssid:
                    wifi_state.update({"saved_network_error": "SSID is required"})
                    return
                if self.client.remove_network(ssid):
                    wifi_state.update({
                        "known_networks": self.client.get_known_networks(),
                        "saved_network_error": None,
                        "saved_network_last_action": f"Deleted '{ssid}'"
                    })
                    self._persist_runtime_settings()
                else:
                    wifi_state.update({"saved_network_error": f"Network '{ssid}' not found"})
            return

        # AP password change request
        ap_pwd_req = wifi_state.get_ap_password_change_request()
        if ap_pwd_req:
            new_password = (ap_pwd_req.get("password") or "").strip()
            ok, msg = self.ap.set_password(new_password)
            if ok:
                wifi_state.update({
                    "ap_settings_error": None,
                    "ap_settings_last_action": msg
                })
                self._persist_runtime_settings()
            else:
                wifi_state.update({
                    "ap_settings_error": msg
                })
            return

        # Block/unblock AP client requests
        block_req = wifi_state.get_block_request()
        if block_req:
            self._trace(f"block request payload={block_req}")
            mac = block_req.get("mac", "")
            if mac:
                self.ap.block_client(mac)
                self._refresh_ap_clients(force=True)
            return

        unblock_req = wifi_state.get_unblock_request()
        if unblock_req:
            self._trace(f"unblock request payload={unblock_req}")
            mac = unblock_req.get("mac", "")
            if mac:
                self.ap.unblock_client(mac)
                self._refresh_ap_clients(force=True)
            return

        ap_refresh_req = wifi_state.has_ap_clients_refresh_request()
        if ap_refresh_req and not wifi_state.get("connect_in_progress", False):
            # Explicit dashboard request should bypass cache to avoid stale client counts.
            self._trace("ap clients refresh request accepted (force=True)")
            self._refresh_ap_clients(force=True)
            return

        # Scan request (with debounce — skip if last scan was recent)
        if wifi_state.has_scan_request() and not wifi_state.get("connect_in_progress", False):
            self._trace("scan request accepted")
            self._refresh_networks(force=False)

    def _try_known_networks_no_scan(self, available_networks: list) -> bool:
        """Try to connect to a known network without rescanning.
        available_networks is a list of dicts: [{"ssid": "...", "signal": ...}, ...]
        """
        available_ssids = [n["ssid"] if isinstance(n, dict) else n for n in available_networks]
        known = self.client.get_known_networks()
        for ssid in known:
            if ssid in available_ssids:
                log.info(f"Known network in range: '{ssid}', connecting...")
                net_id = self.client.wpa.find_network_by_ssid(ssid)
                if net_id is not None:
                    self.client.wpa.select_network(net_id)
                    # Wait for connection
                    for _ in range(10):
                        time.sleep(1)
                        if self.client.is_connected():
                            self.client.renew_dhcp()
                            log.info(f"Connected to known network '{ssid}'")
                            return True
        return False

    def run(self, check_interval: int = MAIN_LOOP_INTERVAL):
        """Main service loop"""
        log.info("=" * 50)
        log.info("WiFi Manager Service Started")
        log.info(f"AP (wlan1): {self.ap.ssid}")
        log.info(f"Client (wlan0): Ready")
        log.info("=" * 50)

        # Check for Mender OTA update; force full AP reinit if artifact name changed.
        ota_detected = self._check_ota_and_reinit()
        if ota_detected:
            # Reset STA restore state so wpa_supplicant config is re-applied cleanly.
            self._sta_restore_done = False
            self._sta_restore_succeeded = False
            self._sta_restore_retries = 0

        # Start AP (always on); force=True on OTA ensures hostapd/dnsmasq restart
        # even if services appear "active" with a stale pre-update config.
        self.ap.start(force=ota_detected)
        self._restore_sta_networks_from_persistent()

        # Initial scan and populate state BEFORE trying to connect
        # This ensures dashboard has networks to display immediately
        log.info("Performing initial network scan...")
        self._refresh_networks(force=True)
        networks = wifi_state.get("networks", [])
        log.info(f"Initial scan found {len(networks)} networks")

        # Try to connect client to known network (doesn't rescan, just connects)
        self._try_known_networks_no_scan(networks)

        # Persist current state — ensures any legacy plaintext passwords in
        # netservices.conf are immediately migrated to the 64-hex PSK format.
        self._persist_runtime_settings()

        # Update initial state
        self.update_state()

        last_reconnect_attempt = time.time()  # Don't retry immediately after startup
        RECONNECT_INTERVAL = 60  # Only try to reconnect every 60 seconds to minimize AP disruption

        while True:
            try:
                self._loop_id += 1
                # Retry STA restore until wpa_supplicant is ready (handles post-update races)
                self._restore_sta_networks_from_persistent()
                # Ensure AP is running
                self.ap.ensure_running()

                dashboard_active = wifi_state.is_client_connected()
                now = time.time()
                connect_busy = wifi_state.get("connect_in_progress", False)
                self._trace(
                    f"loop={self._loop_id} dashboard_active={dashboard_active} connect_busy={connect_busy} "
                    f"last_scan_age={now - (self._last_networks_update or now):.2f}s "
                    f"last_ap_age={now - (self._last_ap_clients_update or now):.2f}s"
                )

                # Auto-updates only while dashboard has active clients.
                if (not connect_busy) and (dashboard_active or not self.network_scan_cfg.get("auto_scan_requires_dashboard_client", True)):
                    ap_clients = wifi_state.get("ap_clients", []) or []
                    if ap_clients:
                        self._trace(f"auto scan skipped: ap_clients_connected={len(ap_clients)}")
                    else:
                        self._refresh_networks(force=False)
                if (not connect_busy) and (dashboard_active or not self.ap_clients_cfg.get("auto_update_requires_dashboard_client", True)):
                    self._refresh_ap_clients(force=False)

                # Process dashboard requests
                self.process_requests()

                # Check client connection if not connected
                # Only attempt reconnect periodically to avoid disrupting AP clients
                if not self.client.is_connected():
                    if not self.client.check_connection():
                        if now - last_reconnect_attempt >= RECONNECT_INTERVAL:
                            log.info("Attempting to reconnect to known networks...")
                            # Use cached networks if available, otherwise scan
                            cached_networks = wifi_state.get("networks", [])
                            if cached_networks:
                                self._try_known_networks_no_scan(cached_networks)
                            else:
                                self.client.try_known_networks()
                            last_reconnect_attempt = now

                # Update state
                self.update_state()

                # Update LED based on connection status
                self._set_led(self.client.is_connected())

            except Exception as e:
                log.error(f"Error in main loop: {e}", exc_info=True)

            time.sleep(check_interval)


def main():
    manager = WifiManager()
    manager.run()


if __name__ == "__main__":
    main()
