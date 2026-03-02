# Changelog

## 1.1.0 (SVN r8372, 2026-02-25)
Baseline: **1.0.0 (SVN r8368, 2026-02-24)**  
Release commit: **r8372** (`version 1.1.0 - added security options`)

### Scope of technical delta
- Main backend redesign in `dashboard/app.py`:
  - security/session layer
  - HTTPS runtime and certificate management
  - firmware-update guard
  - system control APIs (SSH/HTTPS/account/reboot/restart)
  - service monitor API model changes
- Persistent config model refactor in `services/netservices_config.py`.
- System settings UX rewritten (`dashboard/templates/system_settings.html`) from service-centric screen to sectioned security/control screen.
- Deployment flow extended to include SSL assets (`install.sh`, `scpme.sh`).

### Runtime and platform changes
- Dashboard runtime ports:
  - `DASHBOARD_PORT = 443`
  - `DASHBOARD_HTTP_PORT = 80`
- Session security defaults:
  - `SESSION_COOKIE_HTTPONLY = True`
  - `SESSION_COOKIE_SAMESITE = Lax`
  - `PERMANENT_SESSION_LIFETIME = 30 minutes`
- Login brute-force limits:
  - `LOGIN_ATTEMPT_WINDOW_SECONDS = 600`
  - `LOGIN_LOCK_SECONDS = 900`
  - `LOGIN_MAX_FAILURES = 5`

### Authentication and authorization model
- Added explicit auth guard via `@app.before_request`:
  - Unauthenticated UI requests redirect to `/login?next=...`
  - Unauthenticated API requests return `401 {"error":"Authentication required"}`
  - Public endpoint allow-list introduced (`/login`, captive endpoints, update status, cert download, static paths).
- Added dashboard credential persistence in `netservices.conf` (`auth` section, password hash only).
- Added session secret persistence in `netservices.conf` (`session.secret_key`).
- Added `/login` (GET/POST) and `/logout` routes.

### HTTPS and certificate subsystem
- Added HTTPS settings API: `GET/POST /api/https-settings`
  - Request contract (POST):
    - required: `https_enabled` (bool)
    - optional: `https_hostname` (string)
    - optional: `restart` (bool)
  - Response contract includes:
    - `https_hostname_effective`
    - `redirect_url`
    - `restart_scheduled`
- Hostname validation/normalization:
  - lower-case, `_` -> `-`, strict character checks, length limits
  - `.local` fallback behavior from serial-based default
- mDNS/system hostname apply path:
  - `hostnamectl set-hostname` (fallback to `/etc/hostname` + `hostname`)
  - `systemctl restart avahi-daemon`
- Certificate lifecycle:
  - CA/key expected in `/data/rexgen/config/ssl/ca.crt` + `ca.key`
  - server cert regenerated when host identity/mode changes
  - OpenSSL verify and forced reissue logic
- Added certificate UX routes:
  - `/install-certificate`
  - `/download-ca-cert`
  - `/host-switch`

### SSH and Linux access controls
- Added SSH control API:
  - `GET /api/ssh-status`
  - `POST /api/ssh-status`
- SSH unit handling supports socket/service forms with runtime detection:
  - `sshd.socket`, `sshd.service`, `dropbear.service`, etc.
- Added persisted desired SSH policy:
  - `system.ssh_enabled` in `netservices.conf`
  - policy applied on dashboard startup (`_apply_persisted_ssh_state_on_startup`)

### Account and password management APIs
- Added `GET/POST /api/account-security`:
  - username + dashboard password update
  - current password verification required
  - password policy: 8..128 chars
- Added `POST /api/root-password`:
  - current root password verification against `/etc/shadow`
  - update via `chpasswd`

### Firmware update guard behavior
- Added background poller for `fw_printenv influx_upgrade`.
- Added update lock routing:
  - when update flag is active, non-exempt routes are redirected to `/updating`
  - APIs outside exempt list return `503` update-in-progress error
- Added:
  - `/updating`
  - `/api/update-status`

### System/service APIs
- `/api/system-services` changed to dynamic full-unit discovery model:
  - removed fixed core-only unit list behavior
  - added status summary counters and status filtering
  - response now includes `summary`, `status_filter`, `total_count`
- Added:
  - `POST /api/system/reboot`
  - `POST /api/system/restart-dashboard`
- Existing detail/log routes retained:
  - `GET /api/system-services/<unit>`
  - `GET /api/system-services/<unit>/logs`

### Device info data model changes
- Added network interface composite fields in `/api/device-info`:
  - `iface_eth0`, `iface_wlan0`, `iface_wlan1` (format: `ip, mac`)
- Added dedicated detail pages:
  - `/cpu-detail`
  - `/memory-detail`
  - `/disk-detail`
- `/hardware-detail` changed from direct template to redirect dispatcher by `kind`.

### UI/template architecture changes
- New shared template partials:
  - `_topnav.html`, `_logout.html`, `_footer.html`
- New pages:
  - `login.html`
  - `services.html`
  - `updating.html`
  - `cpu_detail.html`
  - `memory_detail.html`
  - `disk_detail.html`
  - `install_certificate.html`
  - `wifi_settings.html` (replaces old index page usage)
- `system_settings.html` technical redesign:
  - Sections introduced:
    - Dashboard Account
    - Linux System Access
    - HTTPS
    - Remote Update
    - System
  - Added save flows for account/root password/SSH/HTTPS/reboot
  - Added HTTPS info block and hostname/effective-host UX

### Persistent config refactor (`netservices_config.py`)
- Storage backend changed from INI parser approach to normalized JSON object.
- Default schema introduced:
  - `ap.ap_psk`
  - `sta.networks[]`
  - `dashboard.https_enabled`, `dashboard.https_hostname`
  - `system.ssh_enabled`
  - `auth.username`, `auth.password_hash`
  - `session.secret_key`
- Added normalization and migration-friendly behavior:
  - cleans malformed/missing keys to defaults
  - preserves legacy AP password key when present
  - materializes missing `system.ssh_enabled` key on read

### Deployment/install pipeline changes
- `scpme.sh` now uploads `ssl/` directory together with services/dashboard/scripts/install.
- `install.sh` phase update:
  - Added dedicated SSL CA deployment phase prior to service installation.
  - CA/key copied to `/data/rexgen/config/ssl`.
  - Existing server cert/key removed to force re-sign with current CA.

### Route map additions in 1.1.0 (high-impact)
- Auth/UI:
  - `/login`, `/logout`, `/services`, `/updating`, `/install-certificate`, `/host-switch`
- Security/system API:
  - `/api/account-security` (GET/POST)
  - `/api/root-password` (POST)
  - `/api/ssh-status` (GET/POST)
  - `/api/https-settings` (GET/POST)
  - `/api/system/reboot` (POST)
  - `/api/system/restart-dashboard` (POST)
  - `/api/update-status` (GET)
  - `/download-ca-cert` (GET)

### File-level delta (SVN summarize r8368 -> r8372)
- **Modified**
  - `install.sh`
  - `scpme.sh`
  - `services/netservices_config.py`
  - `dashboard/app.py`
  - `dashboard/templates/rexgend_settings.html`
  - `dashboard/templates/ap_settings.html`
  - `dashboard/templates/wifi_network_info.html`
  - `dashboard/templates/manage_networks.html`
  - `dashboard/templates/process_info.html`
  - `dashboard/templates/system_settings.html`
  - `dashboard/templates/ap_client_info.html`
  - `dashboard/templates/device_info.html`
  - `dashboard/templates/service_info.html`
- **Added**
  - `dashboard/templates/disk_detail.html`
  - `dashboard/templates/wifi_settings.html`
  - `dashboard/templates/services.html`
  - `dashboard/templates/memory_detail.html`
  - `dashboard/templates/_footer.html`
  - `dashboard/templates/_topnav.html`
  - `dashboard/templates/login.html`
  - `dashboard/templates/install_certificate.html`
  - `dashboard/templates/_logout.html`
  - `dashboard/templates/cpu_detail.html`
  - `dashboard/templates/updating.html`

---

## 1.1.1 (SVN r8384, 2026-02-27)
Baseline: **1.1.0 (SVN r8372, 2026-02-25)**
Release commit: **r8384** (`v1.1.1: OTA detection and re-init, AP DHCP fix, persistent state, WPA PSK derivation, experimental flag, rexgend settings fix`)

### Scope of technical delta
- OTA/Mender update detection and forced full re-initialization in `services/wifi_manager.py`.
- AP DHCP reliability fix in `services/ap_manager.py` (dnsmasq always restarted, config path corrected).
- Runtime state persistence moved from `/tmp/rexgen/` to `/data/rexgen/tmp/` in `services/ap_manager.py` and `services/shared_state.py`.
- WPA PSK security improvement in `services/client_manager.py` — no plaintext passwords stored.
- Experimental feature flag added to config model (`services/netservices_config.py`) and dashboard injected context (`dashboard/app.py`).
- Bug fix: rexgend settings page JS functions unreachable when experimental flag off (`dashboard/templates/rexgend_settings.html`).
- systemd unit hardening (`systemd/wifi-manager.service`).

### OTA detection and re-initialization
- Added `_get_mender_artifact()` static method in `WifiManager`:
  - reads `/etc/mender/artifact_info`, extracts `artifact_name` field.
- Added `_check_ota_and_reinit()` method:
  - compares stored artifact name (`netservices.conf["system"]["mender_artifact"]`) against current value.
  - returns `True` and writes new artifact name when a change is detected.
- `run()` now calls OTA check before AP start:
  - on OTA detected: resets STA restore state flags, passes `force=True` to `ap.start()`.
  - ensures hostapd and dnsmasq are fully restarted after a Mender image swap.
- New `netservices.conf` field: `system.mender_artifact` (string, default `""`).
- New read/write accessors: `read_mender_artifact()`, `write_mender_artifact()`.

### AP DHCP fix — dnsmasq always restarted
- `ap_manager.py` `start()`: changed from conditional `systemctl start` to unconditional `systemctl restart dnsmasq`.
  - Fixes "obtaining IP address" failure on AP clients after OTA or boot, caused by dnsmasq binding before wlan1 had its IP.
- `ap_manager.py` `ensure_running()`: similarly uses `restart` when dnsmasq is found not running.
- `DNSMASQ_CONF` path changed from `/etc/dnsmasq.conf` to `/etc/dnsmasq.d/rexgen-ap.conf` (drop-in directory, avoids conflict with base config).
- `configure_dnsmasq()`: added `config_path.parent.mkdir(parents=True, exist_ok=True)` before write.

### Persistent state directory
- `BLOCKED_FILE` in `ap_manager.py` moved from `/tmp/rexgen/ap_blocked.json` to `/data/rexgen/tmp/ap_blocked.json`.
  - AP block state now survives reboots.
- `STATE_DIR` in `shared_state.py` moved from `/tmp/rexgen` to `/data/rexgen/tmp`.
  - `_write()` now calls `os.makedirs(os.path.dirname(temp_file), exist_ok=True)` before writing.
- `_write_blocked()` in `ap_manager.py`: added `os.makedirs(os.path.dirname(temp), exist_ok=True)`.

### WPA PSK pre-derivation — no plaintext passwords in config
- Added module-level `_derive_wpa_psk(ssid, passphrase)` in `client_manager.py`:
  - `hashlib.pbkdf2_hmac("sha1", passphrase, ssid, 4096, 32).hex()` → 64-character hex PSK.
- `add_network()`: derives 64-hex PSK before handing to `wpa_cli set_network`, never stores passphrase.
- `_parse_saved_networks_from_wpa_config()`: handles both formats:
  - `psk=<64hex>` — stored as-is.
  - `psk="passphrase"` (legacy quoted) — derives PSK at import time.
- `import_saved_networks()`: `password` field takes priority over `psk` field; derives PSK if password non-empty, then clears.
- Added `_add_network_with_psk(ssid, psk_hex)` internal helper used by `import_saved_networks()`.
- `netservices_config.py` `_clean_networks()`: always emits both `psk` (64-hex) and `password` (empty string) fields.
  - `password` field is intentionally retained: users may populate it manually in the conf file; startup auto-converts and clears it.
- `run()` in `WifiManager` calls `_persist_runtime_settings()` unconditionally after initial network connect to ensure PSK migration on first startup after upgrade.

### Experimental feature flag
- New `netservices.conf` field: `dashboard.experimental` (bool, default `False`).
- `_normalize()` propagates the field; `read_experimental()` accessor added.
- `_inject_globals()` in `app.py` now injects `"experimental": _PERSIST_CFG.read_experimental()` into all template contexts.
- `rexgend_settings.html`: sensor chart card HTML and all sensor JS code wrapped in `{% if experimental %}...{% endif %}`.

### Bug fix — rexgend settings page always functional
- Root cause: all JavaScript in `rexgend_settings.html` (sensor chart code AND rexgend config functions `setStatus`, `setValues`, `loadConfig`, `saveConfig`) was inside a single `{% if experimental %}` block.
- When `experimental=False`, none of the JS was rendered; `loadConfig()` call on page load and Reload button `onclick` both silently failed.
- Fix: `{% endif %}` moved to close immediately after `loadSensors()`. Config functions are now always rendered regardless of the flag.

### systemd unit hardening
- `wifi-manager.service`:
  - `Requires=wpa_supplicant.service` → `Wants=wpa_supplicant.service` to avoid hard dependency failure.
  - `ExecStartPre` now creates required persistent directories:
    `/data/rexgen/tmp`, `/data/rexgen/config`, `/var/run/wpa_supplicant`.

### File-level delta (SVN r8373 -> r8384)
- **Modified**
  - `dashboard/app.py`
  - `dashboard/templates/_footer.html`
  - `dashboard/templates/_topnav.html`
  - `dashboard/templates/device_info.html`
  - `dashboard/templates/rexgend_settings.html`
  - `services/ap_manager.py`
  - `services/client_manager.py`
  - `services/netservices_config.py`
  - `services/shared_state.py`
  - `services/wifi_manager.py`
  - `systemd/wifi-manager.service`

---

## Post-1.1.0 cleanup (SVN r8373, 2026-02-25)
- Removed obsolete templates:
  - `dashboard/templates/hardware_detail.html`
  - `dashboard/templates/index.html`
