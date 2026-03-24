#!/usr/bin/env python3
"""Shared constants for rexgen/rexgend dashboard modules."""

from pathlib import Path

REXGEND_CONFIG_FILE = "/data/rexgen/config/rexgend.conf"
REXGEND_CONFIG_PATH = Path(REXGEND_CONFIG_FILE)

STRUCTURE_JSON_FILE = "/home/root/rexusb/status/structure.json"
STRUCTURE_JSON_PATH = Path(STRUCTURE_JSON_FILE)

REXGEN_PIPE_DIR = "/var/run/rexgen"

REXGEND_SERVICE = "rexgend.service"
WIFI_DASHBOARD_SERVICE = "wifi-dashboard.service"
