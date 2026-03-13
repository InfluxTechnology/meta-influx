# Changelog

## 1.1.3 (2026-03-09)

### Scope
- Tailscale runtime behavior updates:
  - `tailscale up` now always uses `--accept-dns=false` so Tailscale does not overwrite resolver policy.
  - Tailscale advertise tags are now config-driven (`advertise_tags_enabled`, `advertise_tags`) instead of hardcoded.
- DNS model refactor for VPN extensibility:
  - new persistent DNS section in `netservices.conf` (`dns.servers`, `dns.options`) used as base resolver policy.
  - provider-specific DNS support added under VPN provider config (currently `vpn.providers.tailscale.dns_servers`).
  - effective DNS order now prepends active-provider DNS, then base DNS fallback with dedupe.
  - provider DNS is excluded when provider is not active, preventing stale Tailscale DNS leakage after reboot.
- Connectivity checks:
  - `client_manager` now builds ping host list from the same effective DNS order used for `/etc/resolv.conf`.
- DNS apply reliability fixes:
  - base DNS defaults were corrected to exclude Tailscale DNS from `dns.servers` (Tailscale DNS stays provider-specific).
  - resolver apply now handles systems where `/etc/resolv.conf` is a symlink (replaces with static file for deterministic policy).
  - resolver cache skip logic now verifies actual file state, preventing stale external overwrites from being silently kept.
  - VPN Save now triggers immediate DNS refresh in `wifi-manager` through shared-state request (`dns_refresh_request`) instead of waiting for reconnect/reboot.

## 1.1.2 (2026-03-06)

### Scope
- VPN control expanded for Tailscale operational flow:
  - `tailscaled.service` is now explicitly managed (enable/start when VPN provider is `tailscale`, stop/disable when provider is `disabled`).
  - startup apply includes image/artifact change awareness and re-apply path.
  - Tailscale auth status persistence refined (`auth_status`, key hash, last error) with clearer status reporting.
- VPN UI and status behavior updates:
  - dedicated VPN section behavior refined for provider-specific controls.
  - reduced popup noise by surfacing operational errors through VPN status line.
  - Tailscale effective hostname surfaced from runtime status.
- Device Info interface presentation updates:
  - interface rows now show concise `IP / MAC` format.
  - explicit hostname rows for `wlan0/wlan1` and `tailscale0`.
  - interface list includes Tailscale runtime context when selected.
- Version metadata:
  - `DASHBOARD_VERSION` bumped to `1.1.2`.
  - removed stale `DASHBOARD_BUILD` constant.

## 1.1.0 (SVN r8375, 2026-02-25)
Baseline: **1.0.0 (SVN r8368, 2026-02-24)**  
Release commits:  
- **r8372** (`version 1.1.0 - added security options`)  
- **r8375** (`last version 1.1.0 including CA sert`)

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

### File-level delta (SVN summarize r8368 -> r8375)
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
  - `ssl/ca.crt`
  - `ssl/ca.key`
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
Baseline: **1.1.0 final (SVN r8375, 2026-02-25)**  
Feature commits in range: **r8377, r8380, r8383, r8384**  
Release commit: **r8384** (`v1.1.1: OTA detection and re-init, AP DHCP fix (dnsmasq restart), persistent state to /data/rexgen/tmp, WPA PSK pre-derivation, experimental flag, rexgend settings JS fix`)

### Scope of technical delta
- New browser terminal subsystem (PTY shell over authenticated polling API).
- New live pipe-read subsystem for rexgend runtime pipes.
- OTA artifact detection + forced AP/DHCP re-init after image change.
- AP DHCP reliability fix (`dnsmasq` restart semantics + config path update).
- State persistence moved from volatile `/tmp` to persistent `/data/rexgen/tmp`.
- Wi-Fi credentials model migrated to pre-derived WPA PSK (64-hex), no plaintext writeback.
- Config schema extended with theme/lang/experimental and system OTA metadata fields.
- Rexgend settings JS render-path bug fixed (core config JS now always rendered).
- Service-status fetch load reduced (`SERVICE_STATUS_CACHE_SECONDS`: `5` -> `30`).

### Commit-level map (1.1.0 -> 1.1.1)
- `r8377`: HTTPS GUI text/links improvements (`system_settings.html`).
- `r8380`: terminal feature (`app.py`, `system_settings.html`, `terminal.html`).
- `r8383`: live pipe support (`app.py`, `pipe_output.html`, `rexgend_settings.html`).
- `r8384`: OTA/AP/DHCP/persistence/PSK/config/theme/footer/topnav/device/rexgend/service-unit updates.

### Web terminal subsystem (`r8380`)
- Added route:
  - `GET /terminal` -> `terminal.html`
- Added terminal session backend in `dashboard/app.py`:
  - `_ConsoleSession` class
  - PTY lifecycle via `pty.openpty()`
  - interactive shell spawn: `['/bin/bash', '-i']`
  - session-leader/controlling-TTY setup via `os.setsid()` + `TIOCSCTTY`
  - async read loop using `select.select()` and in-memory ring-like byte buffer
  - runtime resize via `TIOCSWINSZ`
  - idle/dead cleanup thread (`_console_cleanup_loop`, 30 s tick, 600 s idle timeout)
- Added terminal API:
  - `POST /api/console/start`
  - `GET /api/console/output?session_id=...`
  - `POST /api/console/input`
  - `POST /api/console/resize`
  - `POST /api/console/close`
- Protocol specifics:
  - output payload is base64-encoded binary stream
  - input payload is UTF-8 text chunk
  - root password is verified against `/etc/shadow` before session creation
- `system_settings.html` adds "Terminal" action row in System section linking to `/terminal`.

### Pipe streaming subsystem (`r8383`)
- Added pipe reader primitives in `dashboard/app.py`:
  - `_PipeReader` background reader for named pipes
  - incremental sequence-based read model
  - in-memory bounded line deque (`maxlen=300`)
  - idle reader cleanup thread (5 min stale timeout)
- Added routes:
  - `GET /api/pipes` (enumerate available runtime pipes)
  - `GET /api/pipes/read?pipe=...&seq=...` (poll new lines since sequence)
  - `GET /pipe-output?pipe=...` (viewer page)
- Added new template:
  - `dashboard/templates/pipe_output.html`
  - polling UI with pause/clear/status indicators and line class styling by channel/type
- `rexgend_settings.html` gains experimental sensor card with per-pipe tabs and polling integration.

### OTA detection and AP re-initialization (`r8384`)
- `services/wifi_manager.py`:
  - added `_get_mender_artifact()` (reads `/etc/mender/artifact_info`)
  - added `_check_ota_and_reinit()` (compares stored/current artifact, persists new value)
  - on detected artifact change:
    - resets STA restore state machine
    - calls `ap.start(force=True)` to force hostapd/dnsmasq re-initialization
- `services/netservices_config.py`:
  - added `system.mender_artifact`
  - added `read_mender_artifact()` / `write_mender_artifact()`

### AP DHCP reliability and path corrections (`r8384`)
- `services/ap_manager.py`:
  - `DNSMASQ_CONF`: `/etc/dnsmasq.conf` -> `/etc/dnsmasq.d/rexgen-ap.conf`
  - dnsmasq lifecycle:
    - previous: conditional `systemctl start dnsmasq`
    - new: unconditional `systemctl restart dnsmasq` when AP starts
  - `ensure_running()` now uses restart semantics for dnsmasq recovery
  - ensures parent directory exists before writing dnsmasq config
- Resulting behavior: fixes stale-bind scenarios when dnsmasq started before wlan1 IP was ready.

### Persistent state migration (`r8384`)
- `services/shared_state.py`:
  - state dir: `/tmp/rexgen` -> `/data/rexgen/tmp`
  - atomic writer now creates target directory proactively
- `services/ap_manager.py`:
  - blocked clients file: `/tmp/rexgen/ap_blocked.json` -> `/data/rexgen/tmp/ap_blocked.json`
  - blocked-state writer now ensures parent directory exists
- `systemd/wifi-manager.service`:
  - adds `ExecStartPre` mkdir for:
    - `/data/rexgen/tmp`
    - `/data/rexgen/config`
    - `/var/run/wpa_supplicant`

### Wi-Fi credential hardening (`r8384`)
- `services/client_manager.py`:
  - adds `_derive_wpa_psk(ssid, passphrase)` using `PBKDF2-HMAC-SHA1(iter=4096,len=32)` -> 64-hex PSK
  - `add_network()` now sets unquoted hex `psk` (never plaintext passphrase)
  - parser accepts:
    - `psk=<64hex>` (native)
    - legacy `psk="passphrase"` (derived on import)
  - `import_saved_networks()` prioritizes explicit `password` when present, derives PSK, and imports via `_add_network_with_psk()`
- `services/netservices_config.py`:
  - `sta.networks` entries now normalized with both fields:
    - `psk` (derived hex)
    - `password` (typically empty, retained for manual migration path)
- `services/wifi_manager.py`:
  - `_persist_runtime_settings()` runs after initial connect path to migrate legacy data immediately
  - guards added to avoid wiping persistent STA list when wpa_supplicant is not ready yet
  - STA restore now has retry loop (`_MAX_RETRIES=15`) and success tracking flags

### Config schema extensions (`r8384`)
- `dashboard` section extended:
  - `theme` (`light|dark`)
  - `lang` (`en|zh|bg`)
  - `experimental` (bool)
- `system` section extended:
  - `mender_artifact` (string)
- New accessors in `netservices_config.py`:
  - `read_theme()/write_theme()`
  - `read_lang()/write_lang()`
  - `read_experimental()`
  - `read_mender_artifact()/write_mender_artifact()`
- `dashboard/app.py` context injection now includes:
  - `theme`
  - `experimental`

### UI and UX changes (`r8377-r8384`)
- `system_settings.html`:
  - HTTPS info label/text adjusted
  - CA install callout made explicit
  - Terminal action added in System section
- `device_info.html`:
  - service count fetch decoupled from core device status fetch
  - service count loaded in a separate function and triggered after device-info fetch completion
- `_topnav.html`:
  - tab labels annotated with `data-i18n` attributes (`nav.device`, `nav.wifi`, `nav.ap`, `nav.system`)
- `_footer.html`:
  - dark theme CSS coverage greatly expanded
  - theme applied via Jinja context (`{{ theme }}` -> `html.dark`)
  - exposes `window._t = function(s){ return s; }` identity translator

### Backend runtime tweaks (`r8384`)
- `DASHBOARD_VERSION`: `1.1.0` -> `1.1.1`
- `SERVICE_STATUS_CACHE_SECONDS`: `5` -> `30`
- Added `GET /api/theme?set=dark|light` endpoint (writes theme and redirects back)
- Added explicit `GET /favicon.ico` route returning `204`

### systemd unit delta (`r8384`)
- `systemd/wifi-manager.service`:
  - removed hard `Requires=wpa_supplicant@wlan0.service`
  - expanded `Wants=... wpa_supplicant@wlan0.service`
  - added `ExecStartPre=/bin/mkdir -p /data/rexgen/tmp /data/rexgen/config /var/run/wpa_supplicant`

### File-level delta (SVN summarize r8375 -> r8384)
- **Added**
  - `dashboard/templates/terminal.html`
  - `dashboard/templates/pipe_output.html`
- **Modified**
  - `dashboard/app.py`
  - `dashboard/templates/system_settings.html`
  - `dashboard/templates/rexgend_settings.html`
  - `dashboard/templates/device_info.html`
  - `dashboard/templates/_topnav.html`
  - `dashboard/templates/_footer.html`
  - `services/wifi_manager.py`
  - `services/client_manager.py`
  - `services/ap_manager.py`
  - `services/netservices_config.py`
  - `services/shared_state.py`
  - `systemd/wifi-manager.service`

---

## Post-1.1.0 cleanup (SVN r8373, 2026-02-25)
- Removed obsolete templates:
  - `dashboard/templates/hardware_detail.html`
  - `dashboard/templates/index.html`
