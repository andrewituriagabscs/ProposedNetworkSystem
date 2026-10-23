"""API routes for system settings, building databases, and reference ping targets."""

import csv
import io
from flask import Blueprint, jsonify, make_response, request
from monitoring import (
    get_available_databases,
    get_building_name,
    get_network_reference_samples,
    get_network_reference_status,
    initialize_database,
    poll_network_references,
    save_building_name,
    save_external_reference_target,
    start_monitoring,
    stop_monitoring,
    switch_to_database,
)

api_settings_bp = Blueprint("api_settings", __name__, url_prefix="/api")


@api_settings_bp.get("/settings/building-name")
def get_settings_building_name():
    return jsonify({"building_name": get_building_name()})


@api_settings_bp.patch("/settings/building-name")
def update_building_name():
    payload = request.get_json(silent=True) or {}
    try:
        building_name = save_building_name(payload.get("building_name", ""))
        initialize_database()
    except (AttributeError, TypeError, ValueError) as error:
        return jsonify({"error": str(error)}), 400
    return jsonify({"ok": True, "building_name": building_name})


@api_settings_bp.get("/settings/databases")
def list_databases():
    current_building = get_building_name()
    databases = get_available_databases()
    return jsonify({"databases": databases, "current_building": current_building})


@api_settings_bp.post("/settings/databases/select")
def select_database():
    payload = request.get_json(silent=True) or {}
    building_name = payload.get("building_name", "")
    if not building_name:
        return jsonify({"error": "Building name is required"}), 400
    try:
        saved_name = switch_to_database(building_name)
    except (AttributeError, TypeError, ValueError) as error:
        return jsonify({"error": str(error)}), 400
    return jsonify({"ok": True, "building_name": saved_name, "message": f"Switched to {saved_name} database"})


@api_settings_bp.post("/control/restart-monitoring")
def restart_monitoring():
    try:
        stop_monitoring()
        start_monitoring()
        return jsonify({"ok": True, "message": "Monitoring service restarted successfully!"})
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@api_settings_bp.get("/network-references")
def network_references():
    return jsonify(get_network_reference_status())


@api_settings_bp.post("/network-references/poll")
def poll_network_reference_targets():
    poll_network_references()
    return jsonify(get_network_reference_status())


@api_settings_bp.get("/network-references.csv")
def network_reference_csv():
    rows = get_network_reference_samples()
    output = io.StringIO()
    fields = (
        "id", "recorded_at", "reference_kind", "reference_name", "target", "online",
        "latency_ms", "latency_min_ms", "latency_median_ms", "latency_max_ms",
        "packet_loss", "ping_sent", "ping_received", "latency_readings",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    if rows:
        writer.writerows(rows)
    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=network_reference_ping_data.csv"
    return response


@api_settings_bp.patch("/settings/external-reference")
def update_external_reference():
    payload = request.get_json(silent=True) or {}
    try:
        target = save_external_reference_target(payload.get("target"))
    except (AttributeError, TypeError, ValueError) as error:
        return jsonify({"error": str(error)}), 400
    return jsonify({"ok": True, "target": target})
