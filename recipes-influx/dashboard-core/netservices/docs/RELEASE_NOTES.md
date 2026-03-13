# ReXgen Control Center Release Notes

## ReXgen Control Center 1.1.3 - VPN-Aware DNS Policy and Tailscale Resolver Guard

Release type: Networking policy and VPN integration refinement  
Baseline: 1.1.2  
Primary goal: make DNS resolution deterministic across VPN state transitions and future multi-provider VPN support.

### Highlights
- Dashboard version bump to `1.1.3`.
- Tailscale `up` path now forces `--accept-dns=false` to avoid resolver overwrite from Tailscale.
- Tailscale tags moved from hardcoded defaults to optional config-driven values.
- Added persistent DNS policy section in `netservices.conf`:
  - base DNS list and resolver options (`dns.servers`, `dns.options`)
  - provider DNS list support (`vpn.providers.<provider>.dns_servers`, currently Tailscale)
- Effective DNS behavior:
  - active provider DNS is applied first (priority)
  - base DNS follows as fallback
  - duplicates removed, order preserved
  - inactive-provider DNS is excluded from resolver/ping flow (fixes stale Tailscale DNS after reboot when provider is disabled)
- Connectivity probing now reuses the same effective DNS order used to build `/etc/resolv.conf`.
- Post-integration DNS behavior fixes:
  - base DNS defaults no longer include Tailscale DNS; Tailscale DNS is kept only in provider-specific config.
  - resolver writer now replaces `/etc/resolv.conf` symlink with a static file when needed (for images using `systemd-resolved` symlink mode).
  - resolver write-skip cache now validates real file state before skipping.
  - VPN Save now sends immediate DNS refresh request to `wifi-manager`, so resolver is updated immediately after provider change.

## ReXgen Control Center 1.1.2 - VPN Operational Integration and Interface Visibility

Release type: Operational behavior update  
Baseline: 1.1.1  
Primary goal: make VPN runtime behavior deterministic across OTA images and improve operator visibility in dashboard pages.

### Highlights
- Dashboard version bump to `1.1.2` and cleanup of stale build constant usage.
- Tailscale operational flow hardening:
  - explicit `tailscaled.service` enable/start/stop/disable management tied to VPN provider state.
  - startup apply now includes image-change-aware re-apply path.
  - persistent auth-state/error tracking in VPN config.
- System Settings VPN UX improvements:
  - provider-focused controls and status-line-first error reporting.
  - effective Tailscale hostname shown in VPN section.
- Device Info updates:
  - concise interface value format (`IP / MAC`).
  - hostname rows for Wi-Fi and Tailscale interfaces.

## ReXgen Control Center 1.1.1 - Runtime Stability, OTA Recovery, and Operations Tooling

Release type: Reliability + security hardening + operator tooling  
Baseline: 1.1.0 final (`SVN r8375`)  
Release commit: `SVN r8384`  
Feature commits in range: `r8377, r8380, r8383, r8384`  
Primary goal: improve post-OTA networking reliability, remove plaintext Wi-Fi credential persistence, add controlled browser terminal and live pipe diagnostics, and stabilize rexgend settings rendering.

### 1. Browser terminal subsystem (new operator capability)
- Added dedicated terminal page: `GET /terminal`.
- Added authenticated PTY API:
  - `POST /api/console/start`
  - `GET /api/console/output`
  - `POST /api/console/input`
  - `POST /api/console/resize`
  - `POST /api/console/close`
- Backend uses a real PTY (`pty.openpty`) with interactive shell (`/bin/bash -i`), proper session/TTY setup (`setsid`, controlling TTY), and asynchronous output buffering.
- Terminal session open requires root password verification against `/etc/shadow` (separate from dashboard login session).
- Added idle session cleanup loop (10-minute inactivity timeout) to prevent stale shell accumulation.
- Added System Settings entry for direct terminal launch.

Operational impact:
- Field/service users can perform advanced diagnostics without external SSH tooling.
- Access remains privileged and auditable through explicit root password confirmation.

### 2. OTA artifact tracking and forced AP re-initialization
- Added artifact detection from `/etc/mender/artifact_info`.
- Added persistent artifact tracking in `netservices.conf` (`system.mender_artifact`).
- On artifact change detection after OTA, Wi-Fi manager forces AP/DHCP re-initialization and resets STA restore state.
- Prevents stale runtime state from carrying across rootfs transition.

Operational impact:
- AP recovery after OTA is deterministic and does not depend on previous runtime state quality.

### 3. AP DHCP reliability fix (dnsmasq lifecycle correction)
- AP manager switched dnsmasq config target to `/etc/dnsmasq.d/rexgen-ap.conf`.
- Startup behavior changed from conditional `systemctl start dnsmasq` to explicit `systemctl restart dnsmasq`.
- `ensure_running()` path now follows restart semantics as well.
- Parent directory creation added before config/state writes.

Operational impact:
- Resolves cases where AP clients remain on "Obtaining IP address" after boot/OTA due to stale dnsmasq bind state.

### 4. Persistent runtime state migration to `/data`
- Shared state path migrated from `/tmp/rexgen` to `/data/rexgen/tmp`.
- AP blocked-clients state file moved to `/data/rexgen/tmp/ap_blocked.json`.
- Added proactive directory creation in state writer and in `wifi-manager.service` (`ExecStartPre`).

Operational impact:
- Runtime coordination state survives reboot and Mender image switch.

### 5. Wi-Fi credential hardening (no plaintext persistence)
- `client_manager` now derives WPA PSK via `PBKDF2-HMAC-SHA1` (`4096` iterations, `32` bytes -> `64` hex chars).
- Save path stores unquoted hex `psk` and does not persist plaintext passphrase.
- Legacy data migration:
  - quoted `psk="passphrase"` entries are converted to derived hex PSK,
  - optional config `password` field is consumed/derived and then cleared on persist path.
- `sta.networks` schema normalized with both `psk` and `password` keys for migration compatibility.

Security impact:
- Eliminates long-term plaintext Wi-Fi password exposure in normal runtime persistence flow.

### 6. rexgend settings stability fix
- Fixed page-initialization regression where core config JS was gated by `{% if experimental %}` and therefore missing when experimental mode was off.
- Core settings JS now always rendered; only experimental sensor/pipe block remains conditional.

Operational impact:
- rexgend settings page now loads and reloads consistently in default (non-experimental) deployments.

### 7. Live pipe diagnostics integration
- Added backend pipe reader service with sequence-based polling and bounded in-memory buffer.
- Added routes:
  - `GET /api/pipes`
  - `GET /api/pipes/read`
  - `GET /pipe-output`
- Added `pipe_output.html` viewer and rexgend UI links/tabs for experimental sensor pipe observation.

Operational impact:
- Enables real-time visibility into selected runtime pipes without SSH.

### 8. Runtime/API and UI adjustments
- `DASHBOARD_VERSION` bumped to `1.1.1`.
- `SERVICE_STATUS_CACHE_SECONDS` increased from `5` to `30` to reduce frequent service-enumeration load.
- Added `GET /api/theme?set=dark|light`.
- Added explicit `GET /favicon.ico` (`204`) to suppress noisy browser requests.
- Device page service-count fetch split from core device-info fetch to improve perceived load responsiveness.
- HTTPS section text/callout cleanup in System Settings.
- Footer dark-theme coverage extended.

### 9. systemd unit hardening
- `wifi-manager.service`:
  - replaced hard `Requires=wpa_supplicant@wlan0.service` with soft `Wants=...`,
  - added `ExecStartPre` mkdir for `/data/rexgen/tmp`, `/data/rexgen/config`, `/var/run/wpa_supplicant`.

Operational impact:
- Wi-Fi manager startup is less fragile when wpa_supplicant timing/order varies during boot.

---

## ReXgen Control Center 1.1.0 - Security & Platform Hardening Update

Release type: Functional + Security update  
Baseline: 1.0.0  
Primary goal: keep 1.0.0 operator workflow intact while adding access control, HTTPS/certificate management, stronger system controls, and improved service/runtime observability.

### 1. Security and access control
- Added login/logout flow for Control Center access.
- Added session-based auth guard across UI and API endpoints.
- Added persistent dashboard account credentials (username + password hash).
- Added login brute-force limits:
  - attempt window: 10 min
  - lock time: 15 min
  - threshold: 5 failed attempts
- Unauthenticated browser requests are redirected to `/login`.
- Unauthenticated API calls return `401`.

### 2. Linux System Access controls
- Added Linux access section in System Settings:
  - SSH enable/disable
  - root password change flow
- Added `/api/ssh-status` (GET/POST):
  - controls actual SSH runtime unit (`sshd.socket`, `sshd.service`, `dropbear`, etc.)
  - supports persisted desired state in config
- Added `/api/root-password` (POST) with current password verification.
- Added persisted SSH policy in `netservices.conf`: `system.ssh_enabled`.

### 3. HTTPS, hostname, and certificate management
- Added `/api/https-settings` (GET/POST) for HTTPS mode and hostname settings.
- Added HTTPS runtime support on `:443` with HTTP support on `:80`.
- Added SSL certificate lifecycle handling:
  - server cert generation/signing
  - CA verification/regeneration flow
- Added certificate UX routes:
  - `/install-certificate`
  - `/download-ca-cert`
  - `/host-switch`
- Added redirect flow based on effective hostname after save/restart.

### 4. Firmware update protection
- Added update-state polling (`influx_upgrade`).
- Added guarded behavior while update is active:
  - UI redirects to `/updating`
  - non-exempt APIs return update-in-progress response
- Added `/api/update-status`.

### 5. Config model refactor
- Refactored persistent config to unified JSON model in `/data/rexgen/config/netservices.conf`.
- Added grouped schema families:
  - `ap`, `sta`, `dashboard`, `system`, `auth`, `session`
- Added normalization/default materialization logic.

### 6. Diagnostics and UI expansion
- Added new pages:
  - `login`, `services`, `updating`, `cpu_detail`, `memory_detail`, `disk_detail`, `install_certificate`, `wifi_settings`
- Added shared UI partials:
  - `_topnav`, `_logout`, `_footer`
- Expanded Device/System observability and drill-down paths.

### 7. Service and system operations
- Improved `/api/system-services` model with richer status filtering/summary.
- Added system control endpoints:
  - `POST /api/system/reboot`
  - `POST /api/system/restart-dashboard`

### 8. Install/deploy pipeline updates
- `scpme.sh` now deploys `ssl/` assets.
- `install.sh` now includes SSL CA deployment phase.
- Server cert reissue path aligned with deployed CA.

---

## ReXgen Control Center 1.0.0 - Functional Release Documentation

### Product Purpose
ReXgen Control Center is the on-device web interface for commissioning, operating, and diagnosing ReXgen units.  
It is designed for field use from phone/PC over AP, and for service/maintenance over existing uplink.

Core goals:
1. Configure network connectivity safely (STA + AP).
2. Keep AP-based access available during setup.
3. Expose device, service, and runtime health in operator-friendly views.
4. Provide deterministic behavior under concurrent users.

---

### Information Architecture
The UI is organized into 5 top-level domains, always accessible from the icon bar:

1. Device  
System identity, hardware monitor, OS/runtime metadata, ReXgen identity metadata.

2. Wi-Fi  
STA-side connectivity workflow: connected network, saved networks, available networks, network details.

3. AP  
Access Point operational settings + currently connected AP clients + client details.

4. rexgend  
Application-level runtime settings mapped to `rexgend.conf`, with controlled save/restart flow.

5. System  
System-level configuration (Mender connection settings) and service observability.

This structure mirrors operational responsibility boundaries:
- "Device" for read-only observability,
- "Wi-Fi/AP" for communication plane control,
- "rexgend/System" for service and platform behavior control.

---

### Navigation Model
- Top icon switch is global and persistent for fast context switching.
- Detail pages are focused drill-down views (network info, client info, service/process/hardware details).
- Navigation prefers direct task completion:
  - user selects domain,
  - sees sectionized lists,
  - opens detail/edit action where needed,
  - returns without losing primary context.

Why this works:
- reduces cognitive load under field pressure,
- keeps high-frequency tasks one click away,
- avoids deeply nested menus.

---

### Page Structure Pattern
Each major page uses the same hierarchy:

1. Global top switch (domain navigation)
2. Page title
3. Section blocks with gray caption rows
4. Row-based data/action lists
5. Optional detail links
6. Global footer with control-center version

Why this works:
- predictable scanning pattern,
- consistent interaction grammar across all domains,
- faster operator learning.

---

### Device Domain - Deep Behavior
The Device page is split by information semantics:

1. Hardware Monitor (dynamic runtime status)
- CPU load/usage/temp
- Memory usage
- Disk usage/free
- Uptime
- Drill-down links to process/resource details

2. Linux Information (platform software identity)
- Image version
- Kernel
- OS distribution identity
- Mender metadata
- ReXgend version (+ release date from VAR source)

3. ReXgen Information (product identity/config identity)
- Serial number
- Firmware version
- CPU type (MCU/control plane identity)
- Configuration name/UID

4. Linux Hardware (host hardware/network identity)
- Architecture
- CPU summary (SoC + core count)
- Interface set
- Interface MACs

Why separated this way:
- runtime health is operationally different from static identity.
- Linux platform identity and ReXgen identity serve different troubleshooting paths.
- field technicians need quick verification without parsing raw shell output.

---

### Wi-Fi Domain - Deep Behavior
Wi-Fi page models STA workflow explicitly:

1. Connected
- currently active STA link and key quick fields.

2. Saved Networks
- persisted credentials and auto-connect actions.

3. Available Networks
- scan-discovered SSIDs with join path.

4. Network Detail View
- expanded telemetry and security/PHY context:
  status, IP/MAC, signal, security, technology, band/channel/BSSID/frequency/flags.

Why this works:
- aligns with real operator decision flow: "where am I connected?", "what can I reconnect quickly?", "what is available now?"
- detail view isolates technical diagnostics from the main list, avoiding clutter.

Operational controls and guards
- Connect operations are treated as critical transactions.
- During critical operations, conflicting actions are blocked to avoid race conditions.
- Scan/update pressure is moderated through cached/polled backend behavior.
- Access policy can restrict connection actions to AP-origin sessions when required by deployment policy.

Why:
- STA connect/scan and AP stability compete for radio/driver resources on constrained systems.
- deterministic locking avoids multi-user conflicting commands.

---

### AP Domain - Deep Behavior
AP page combines provisioning and live client management:

1. AP Configuration
- SSID/password and AP behavior fields.
- explicit save/discard semantics.
- explicit warning when applied settings require AP restart (client drop expected).

2. Connected Clients
- current AP client list with identity rows.
- per-client detail page with available station telemetry (driver-dependent fields).

Why this structure:
- AP setup and AP client observation are tightly coupled operationally.
- operators must understand impact of AP config save on active sessions.

---

### rexgend Domain - Deep Behavior
This page exposes managed `rexgend.conf` settings as typed UI controls.

Design principles:
1. Present only controlled options in operator language.
2. Preserve unmanaged config keys during save (non-destructive merge behavior).
3. Apply via explicit save operation.
4. Confirm/communicate service restart effect (`rexgend.service`).

Why:
- config file remains source-of-truth,
- UI remains safe for non-expert operators,
- advanced/manual parameters are not accidentally lost.

---

### System Domain - Deep Behavior
System page focuses on platform-level remote update setup and service visibility.

1. Mender Settings
- field-based editing (`ServerURL`, `TenantToken`) rather than raw JSON editor.
- save with deterministic service application path.
- restart sequence targets active image architecture:
  - `mender-authd.service`
  - `mender-updated.service`

2. Service Status / Service Details
- summary of key services
- detail view for unit-level inspection/log context

Why:
- update connectivity/auth and service health are the two most common platform support concerns.
- field editing with controlled restart reduces misconfiguration risk.

---

### Concurrency and Multi-User Behavior Model
The interface assumes multiple AP clients may access simultaneously.

Control model:
1. Critical operations (connect/save that affect radio/service state) are serialized.
2. Non-critical reads use cached snapshots where possible.
3. Clients receive operation state and are prevented from issuing conflicting actions.

Why:
- prevents double-submit conflicts and hidden races,
- protects AP availability during active setup,
- keeps UI consistent between users.

---

### Data Source Strategy
UI values are sourced by semantic authority:

1. ReXgen identity/config metadata  
From persistent VAR files (`/home/root/rexusb/var/...`).

2. Linux/runtime telemetry  
From kernel/procfs/system commands or derived service APIs.

3. Configurable services  
From their canonical config files (e.g. `rexgend.conf`, `mender.conf`) via merge-preserving read/write paths.

Why:
- each data family has one clear owner,
- reduces drift between displayed values and effective runtime state.

---

### Service Interaction Semantics
Save/apply actions are explicit and tied to service lifecycles:
- `rexgend` settings save => `rexgend.service` restart path.
- Mender settings save => restart of mender auth/update services.
- AP-impacting settings communicate AP client disconnect implications.

Why:
- makes side effects visible and predictable,
- aligns UI with systemd-managed operational reality.

---

### UI Behavior Guarantees
1. Consistent row/list interaction semantics across pages.
2. Centered domain titles and stable top switch.
3. Fixed version footer with safe page spacing.
4. Detail pages follow same visual grammar as primary pages.

Why:
- consistency lowers operator error rate,
- predictable behavior improves trust in field tools.

---

### Versioning
The control panel is explicitly versioned in-page:
- ReXgen Control Center Version 1.0.0
- shown globally in footer across all pages.

Purpose of visible UI version:
- support teams can match screenshots/issues to exact UI behavior,
- allows controlled rollouts and release accountability.

---

### Sub-Pages (Detailed)

1. Wi-Fi Network Info (`/wifi-network-info?...`)  
- Purpose: Full technical details for a selected SSID entry.  
- Shows: status, saved state, IP/MAC (if connected), signal, security, technology class, band, channel, BSSID, frequency, raw flags.  
- Why: Main Wi-Fi list stays clean; diagnostics are available on-demand.

2. Manage Saved Networks (`/manage-networks`)  
- Purpose: Dedicated credential management view.  
- Actions: add network, update password, delete saved entries, optional password visibility.  
- Why: Separates persistent credential administration from live scan/connect actions.

3. AP Client Info (`/ap-client-info?...`)  
- Purpose: Drill-down for one connected AP client.  
- Shows: client identity + available station metrics from AP/runtime source (driver dependent), e.g. connected/inactive time and link-related details when available.  
- Why: AP page remains operationally focused while deep client diagnostics are still accessible.

4. Hardware Detail (`/hardware-detail?kind=cpu|memory|disk`)  
- Purpose: Extended runtime diagnostics behind Device "Hardware monitor" links.  
- CPU view: top CPU processes and CPU-related snapshot info.  
- Memory view: top memory consumers and usage details.  
- Disk view: filesystem usage breakdown/details.  
- Why: Keeps Device page concise; enables deeper performance troubleshooting only when needed.

5. Service Info (`/service-info?...`)  
- Purpose: Detailed per-service inspection from System service list.  
- Shows: unit state/status and service metadata used for troubleshooting.  
- Why: Operators can validate service health without shell access.

6. Process Info (`/process-info?...`)  
- Purpose: Process-level details for runtime investigation.  
- Shows: selected process metrics and context relevant to load/debug scenarios.  
- Why: Complements hardware/service views with process granularity.
