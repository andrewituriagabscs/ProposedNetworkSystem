"""API routes for ML training, inference, labeling, and recommendation feedback."""

import csv
import io
import json
from flask import Blueprint, jsonify, make_response, request
from ml_models import (
    CONDITION_LABELS,
    get_ml_insights,
    get_training_logs,
    get_training_readiness,
    train_models,
    train_single_model,
)
from monitoring import (
    auto_apply_rule_labels,
    get_building_name,
    get_ml_labeling_samples,
    get_ml_training_data,
    get_recommendation_feedback,
    save_condition_label,
    save_recommendation_outcome,
    save_recommendation_selection,
)

api_ml_bp = Blueprint("api_ml", __name__, url_prefix="/api/ml")


@api_ml_bp.get("/status")
def ml_status():
    samples, labels = get_ml_training_data()
    return jsonify(get_training_readiness(samples, labels))


@api_ml_bp.get("/insights")
def ml_insights():
    samples, _ = get_ml_training_data()
    local_samples = [s for s in samples if s.get("protocol") == "icmp"]
    return jsonify({"devices": get_ml_insights(local_samples)})


@api_ml_bp.get("/labels")
def ml_labels():
    return jsonify({"labels": list(CONDITION_LABELS), "samples": get_ml_labeling_samples()})


@api_ml_bp.put("/labels/<int:telemetry_id>")
def ml_label(telemetry_id: int):
    payload = request.get_json(silent=True) or {}
    label = payload.get("label")
    if label not in CONDITION_LABELS:
        return jsonify({"error": "Choose Normal, High Latency, Packet Loss, or Unreachable"}), 400
    if not save_condition_label(telemetry_id, label):
        return jsonify({"error": "Valid ICMP sample not found"}), 404
    return jsonify({"ok": True, "telemetry_id": telemetry_id, "label": label})


@api_ml_bp.post("/auto-label")
def ml_auto_label():
    payload = request.get_json(silent=True) or {}
    overwrite = bool(payload.get("overwrite", True))
    summary = auto_apply_rule_labels(overwrite=overwrite)
    samples, labels = get_ml_training_data()
    return jsonify(
        {
            "ok": True,
            "updated": summary.get("updated", 0),
            "summary": summary,
            "readiness": get_training_readiness(samples, labels),
        }
    )


@api_ml_bp.post("/train")
def train_ml_models():
    auto_apply_rule_labels(overwrite=False)
    samples, labels = get_ml_training_data()
    results = train_models(samples, labels, building_name=get_building_name())
    return jsonify({"models": results, "readiness": get_training_readiness(samples, labels)})


@api_ml_bp.post("/train/<string:model_name>")
def train_single_ml_model(model_name: str):
    if model_name not in ("isolation_forest", "gru", "xgboost"):
        return jsonify({"error": "Choose isolation_forest, gru, or xgboost"}), 400
    auto_apply_rule_labels(overwrite=False)
    samples, labels = get_ml_training_data()
    results = train_single_model(model_name, samples, labels, building_name=get_building_name())
    return jsonify(
        {
            "trained_model": model_name,
            "result": results.get(model_name, {}),
            "models": results,
            "readiness": get_training_readiness(samples, labels),
        }
    )


@api_ml_bp.get("/training-logs")
def ml_training_logs():
    return jsonify({"logs": get_training_logs(limit=50)})


@api_ml_bp.get("/training-logs.csv")
def ml_training_logs_csv():
    logs = get_training_logs(limit=200)
    output = io.StringIO()
    fields = (
        "trained_at",
        "building_name",
        "trigger",
        "telemetry_samples",
        "labeled_samples",
        "label_counts",
        "if_state",
        "if_precision",
        "if_recall",
        "if_f1_score",
        "if_fpr",
        "gru_state",
        "gru_latency_mae_ms",
        "gru_latency_rmse_ms",
        "gru_loss_mae_percent",
        "gru_loss_rmse_percent",
        "gru_reachability_accuracy",
        "xgb_state",
        "xgb_macro_f1",
        "xgb_balanced_accuracy",
    )
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for entry in logs:
        models = entry.get("models") or {}
        if_m = models.get("isolation_forest") or {}
        gru_m = models.get("gru") or {}
        xgb_m = models.get("xgboost") or {}
        writer.writerow(
            {
                "trained_at": entry.get("trained_at"),
                "building_name": entry.get("building_name"),
                "trigger": entry.get("trigger"),
                "telemetry_samples": entry.get("telemetry_samples"),
                "labeled_samples": entry.get("labeled_samples"),
                "label_counts": json.dumps(entry.get("label_counts") or {}),
                "if_state": if_m.get("state"),
                "if_precision": if_m.get("precision"),
                "if_recall": if_m.get("recall"),
                "if_f1_score": if_m.get("f1_score"),
                "if_fpr": if_m.get("false_positive_rate"),
                "gru_state": gru_m.get("state"),
                "gru_latency_mae_ms": gru_m.get("latency_mae_ms"),
                "gru_latency_rmse_ms": gru_m.get("latency_rmse_ms"),
                "gru_loss_mae_percent": gru_m.get("packet_loss_mae_percent"),
                "gru_loss_rmse_percent": gru_m.get("packet_loss_rmse_percent"),
                "gru_reachability_accuracy": gru_m.get("reachability_accuracy"),
                "xgb_state": xgb_m.get("state"),
                "xgb_macro_f1": xgb_m.get("temporal_test_macro_f1"),
                "xgb_balanced_accuracy": xgb_m.get("balanced_accuracy"),
            }
        )
    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=ml_training_logs.csv"
    return response


@api_ml_bp.get("/recommendation-feedback")
def ml_recommendation_feedback():
    return jsonify({"feedback": get_recommendation_feedback()})


@api_ml_bp.post("/recommendation-feedback/<int:telemetry_id>")
def select_ml_recommendation(telemetry_id: int):
    payload = request.get_json(silent=True) or {}
    suggestion_id = payload.get("suggestion_id")
    samples, _ = get_ml_training_data()
    insight = next(
        (item for item in get_ml_insights(samples) if item["telemetry_id"] == telemetry_id),
        None,
    )
    if not insight:
        return jsonify({"error": "Current valid ICMP sample not found"}), 404
    suggestion = next(
        (item for item in insight["suggestions"] if item["id"] == suggestion_id),
        None,
    )
    if not suggestion:
        return jsonify({"error": "That suggestion is not available for this sample"}), 400
    feedback_id = save_recommendation_selection(
        telemetry_id, insight["target"], suggestion
    )
    if feedback_id is None:
        return jsonify({"error": "ICMP sample is no longer available"}), 404
    return jsonify({"ok": True, "feedback_id": feedback_id, "outcome": "pending"}), 201


@api_ml_bp.patch("/recommendation-feedback/<int:feedback_id>")
def update_ml_recommendation_feedback(feedback_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        updated = save_recommendation_outcome(
            feedback_id,
            payload.get("outcome", ""),
            payload.get("verified_finding", ""),
            payload.get("notes", ""),
        )
    except (AttributeError, TypeError, ValueError) as error:
        return jsonify({"error": str(error)}), 400
    if not updated:
        return jsonify({"error": "Selected recommendation not found"}), 404
    return jsonify({"ok": True, "feedback_id": feedback_id})


@api_ml_bp.get("/recommendation-feedback.csv")
def ml_recommendation_feedback_csv():
    rows = get_recommendation_feedback()
    output = io.StringIO()
    fields = (
        "id", "telemetry_id", "recorded_at", "selected_at", "outcome_at",
        "device_name", "target", "model_sources", "evidence", "suggestion_id",
        "suggested_action", "outcome", "verified_finding", "notes",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({
            **row,
            "model_sources": json.dumps(row["model_sources"]),
            "evidence": json.dumps(row["evidence"]),
        })
    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=recommendation_feedback.csv"
    return response
