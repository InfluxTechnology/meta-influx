#!/usr/bin/env python3
"""Routes for rexgen dashboard module."""

import json
import importlib.util
from pathlib import Path

from flask import Blueprint, jsonify, render_template

_constants_file = Path(__file__).with_name("constants.py")
_spec = importlib.util.spec_from_file_location("netservices_rexgen_constants", str(_constants_file))
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Cannot load constants from {_constants_file}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

REXGEND_CONFIG_PATH = _mod.REXGEND_CONFIG_PATH
STRUCTURE_JSON_PATH = _mod.STRUCTURE_JSON_PATH

_ROOT = Path(__file__).resolve().parent
router = Blueprint(
    "rexgen_router",
    __name__,
    template_folder="templates",
    root_path=str(_ROOT),
)


@router.route("/rexgen")
def rexgen_home():
    return render_template("rexgen_home.html")


@router.route("/structure")
@router.route("/rexgen/structure")
def rexgen_structure_page():
    return render_template("structure.html")


@router.route("/api/rexgen/structure")
def rexgen_structure():
    if not STRUCTURE_JSON_PATH.exists():
        return jsonify({
            "error": "structure.json not found",
            "path": str(STRUCTURE_JSON_PATH),
        }), 404

    try:
        payload = json.loads(STRUCTURE_JSON_PATH.read_text() or "{}")
    except Exception as exc:
        return jsonify({
            "error": f"Failed to parse structure.json: {exc}",
            "path": str(STRUCTURE_JSON_PATH),
        }), 500

    if not isinstance(payload, dict):
        return jsonify({
            "error": "structure.json must contain a JSON object",
            "path": str(STRUCTURE_JSON_PATH),
        }), 500

    payload["_meta"] = {"path": str(STRUCTURE_JSON_PATH)}
    return jsonify(payload)


def _read_structure_payload() -> dict:
    if not STRUCTURE_JSON_PATH.exists():
        return {}
    try:
        data = json.loads(STRUCTURE_JSON_PATH.read_text() or "{}")
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _read_rexgend_conf() -> dict:
    cfg = {}
    if not REXGEND_CONFIG_PATH.exists():
        return cfg
    try:
        for raw in REXGEND_CONFIG_PATH.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            cfg[key.strip()] = value.strip()
    except Exception:
        return {}
    return cfg


def _extract_can_count(payload: dict) -> int:
    blocks = payload.get("blocks")
    if not isinstance(blocks, list):
        return 0

    count = 0
    for block in blocks:
        if not isinstance(block, dict):
            continue
        type_name = str(block.get("type_name", "")).lower()
        label = str(block.get("label", "")).lower()
        lane = str(block.get("lane", "")).lower()
        group = str(block.get("group", "")).lower()
        if (
            type_name == "can_interface"
            or "can interface" in label
            or lane == "can"
            or (group == "interfaces" and "can" in type_name)
        ):
            count += 1
    return count


@router.route("/api/rexgen/runtime")
def rexgen_runtime():
    payload = _read_structure_payload()
    cfg = _read_rexgend_conf()
    use_socketcan = str(cfg.get("use_socketcan", "0")).strip() in ("1", "true", "True")
    can_count = _extract_can_count(payload)
    return jsonify({
        "use_socketcan": use_socketcan,
        "can_mode": "socketcan" if use_socketcan else "pipe",
        "can_count": can_count,
        "config_path": str(REXGEND_CONFIG_PATH),
        "structure_path": str(STRUCTURE_JSON_PATH),
    })
