"""API routes for local device discovery, monitoring list, and device configuration."""

import ipaddress
from flask import Blueprint, jsonify, request
from monitoring import (
    add_monitored_device,
    discover_hosts,
    get_local_network,
    get_monitoring_data,
    reclassify_monitored_devices,
    remove_monitored_device,
    update_monitored_device,
)

api_devices_bp = Blueprint("api_devices", __name__, url_prefix="/api")


@api_devices_bp.get("/devices")
def devices():
    return jsonify({
        "devices": get_monitoring_data()["devices"],
        "local_network": get_local_network(),
    })


@api_devices_bp.post("/discover")
def discover():
    payload = request.get_json(silent=True) or {}
    try:
        subnet = payload.get("subnet") or get_local_network()["subnet"]
        limit = payload.get("limit", 0)
        return jsonify({"hosts": discover_hosts(subnet, limit)})
    except (ValueError, ipaddress.AddressValueError) as error:
        return jsonify({"error": str(error)}), 400


@api_devices_bp.post("/devices")
def add_devices():
    payload = request.get_json(silent=True) or {}
    selected = payload.get("devices", [])
    if not isinstance(selected, list):
        return jsonify({"error": "devices must be a list"}), 400
    try:
        local_network = ipaddress.ip_network(get_local_network()["subnet"], strict=False)
        added = []
        for device in selected[:256]:
            address = ipaddress.ip_address(device["target"])
            if address not in local_network:
                raise ValueError(f"{address} is outside the active local network")
            added.append(
                add_monitored_device(
                    str(device.get("name", address)),
                    str(address),
                    device_type=device.get("device_type"),
                )
            )
        return jsonify({"devices": added}), 201
    except (KeyError, TypeError, ValueError) as error:
        return jsonify({"error": str(error)}), 400


@api_devices_bp.patch("/devices/<int:device_id>")
def update_device(device_id: int):
    payload = request.get_json(silent=True) or {}
    if "active" not in payload and "interval_seconds" not in payload and "device_type" not in payload:
        return jsonify({"error": "provide active, interval_seconds, or device_type"}), 400
    try:
        updated = update_monitored_device(
            device_id,
            active=payload.get("active"),
            interval_seconds=payload.get("interval_seconds"),
            device_type=payload.get("device_type"),
        )
    except (TypeError, ValueError) as error:
        return jsonify({"error": str(error)}), 400
    return (jsonify({"ok": True}) if updated else (jsonify({"error": "device not found"}), 404))


@api_devices_bp.post("/devices/reclassify")
def reclassify_devices():
    try:
        results = reclassify_monitored_devices()
        return jsonify({"ok": True, "reclassified": results})
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@api_devices_bp.delete("/devices/<int:device_id>")
def delete_device(device_id: int):
    removed = remove_monitored_device(device_id)
    return (jsonify({"ok": True}) if removed else (jsonify({"error": "device not found"}), 404))
