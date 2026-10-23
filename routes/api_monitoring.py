"""API routes for monitoring status, polling, and dataset exports."""

import csv
import io
from flask import Blueprint, jsonify, make_response
from ml_models import is_valid_ping_sample
from monitoring import (
    get_ml_training_data,
    get_monitoring_data,
    poll_once,
)

api_monitoring_bp = Blueprint("api_monitoring", __name__, url_prefix="/api")


@api_monitoring_bp.post("/monitor-now")
def monitor_now():
    return jsonify({"samples": poll_once()})


@api_monitoring_bp.get("/status")
def status():
    return jsonify(get_monitoring_data())


@api_monitoring_bp.get("/dataset.csv")
def dataset_csv():
    """Export persisted ICMP ping observations for analysis."""
    samples, labels = get_ml_training_data()
    rows = [
        {**sample, "reviewed_condition_label": labels.get(int(sample["id"]), "")}
        for sample in samples
        if is_valid_ping_sample(sample)
    ]
    output = io.StringIO()
    fields = (
        "id", "recorded_at", "device_name", "target", "online",
        "ping_sent", "ping_received", "packet_loss", "latency_min_ms",
        "latency_median_ms", "latency_max_ms", "latency_readings",
        "latency_min_display", "latency_median_display", "latency_max_display",
        "anomaly_score", "anomaly_label", "reviewed_condition_label", "error",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    if rows:
        writer.writerows(rows)
    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=ping_dataset.csv"
    return response


@api_monitoring_bp.get("/model-records.csv")
def model_records_csv():
    """Export the anomaly model's inference history separately from features."""
    rows = get_monitoring_data()["ml_records"]
    output = io.StringIO()
    fields = ("id", "recorded_at", "device_name", "model_version", "result", "confidence", "status")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    if rows:
        writer.writerows(rows)
    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=ping_model_records.csv"
    return response
