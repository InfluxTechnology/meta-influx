#!/usr/bin/env python3
"""Routes for the standalone rexgen dashboard."""

import json

from flask import Blueprint, jsonify, render_template

try:
    from .rexgen_constants import REXGEND_CONFIG_PATH, STRUCTURE_JSON_PATH
except ImportError:
    from rexgen_constants import REXGEND_CONFIG_PATH, STRUCTURE_JSON_PATH

rexgend_router = Blueprint("rexgend_router", __name__, template_folder="templates_rexgen")


@rexgend_router.route("/rexgen")
def rexgen_home():
    return render_template("rexgen_home.html")


@rexgend_router.route("/structure")
@rexgend_router.route("/rexgen/structure")
def rexgen_structure_page():
    return render_template("structure.html")


@rexgend_router.route("/api/rexgen/structure")
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


@rexgend_router.route("/api/rexgen/runtime")
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
