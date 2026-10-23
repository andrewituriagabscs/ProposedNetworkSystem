"""CLI Pipeline Trainer for SYSTEM 2: Proposed / Enhanced Approach.

Usage examples:
  python train_pipeline.py --status
  python train_pipeline.py --model isolation_forest
  python train_pipeline.py --model gru
  python train_pipeline.py --model xgboost
  python train_pipeline.py --model all
  python train_pipeline.py --import-online --model all
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from ml_models import (
    CONDITION_LABELS,
    FEATURE_COLUMNS,
    HISTORY_PATH,
    MODEL_DIR,
    STATUS_PATH,
    get_training_readiness,
    is_valid_ping_sample,
    train_models,
    train_single_model,
)
from monitoring import (
    auto_apply_rule_labels,
    get_building_name,
    get_ml_training_data,
    import_online_training_dataset,
)


def _pct(value: Any) -> str:
    if value is None:
        return "N/A"
    return f"{float(value) * 100:.2f}%"


def _divider(char: str = "=", width: int = 78) -> str:
    return char * width


def _print_pipeline_header(building_name: str, valid_count: int, readiness: dict[str, Any]) -> None:
    print(_divider("="))
    print("  SYSTEM 2: Proposed / Enhanced Approach -- CLI ML Pipeline Trainer")
    print(_divider("="))
    print(f"  Active Building DB : {building_name}")
    print(f"  [Step 1] Ping Mode : 5-Probe ICMP Burst + Dual Reference (Min/Median/Max RTT + Gateway & 1.1.1.1 + Switch OUI/Ports)")
    print(f"  [Step 2] Features  : 12 Temporal Features (Jitter, Delta-Latency, Delta-Loss, 5-Sample Trend, Streak, Delta-Time)")
    print(f"                       {list(FEATURE_COLUMNS)}")
    print(f"  [Step 3] Labeling  : Human-in-the-Loop Labeling (Admin-Reviewed Condition Labels)")
    print(f"  Valid Ping Samples : {valid_count}")
    print(_divider("-"))
    print("  Condition Label Breakdown (Step 3 Admin-Reviewed Condition Labels):")
    per_cond = readiness.get("per_condition_readiness") or {}
    for label in CONDITION_LABELS:
        info = per_cond.get(label) or {"count": 0, "required": 5, "ready": False}
        badge = "[READY]" if info["ready"] else f"[NEEDS {max(0, info['required'] - info['count'])} MORE]"
        print(f"    - {label:<15}: {info['count']:>5} / {info['required']} required  {badge}")
    print(_divider("-"))
    if_info = readiness.get("isolation_forest") or {}
    gru_info = readiness.get("gru") or {}
    xgb_info = readiness.get("xgboost") or {}
    print("  Model Readiness:")
    print(
        f"    1. Isolation Forest (Unsupervised) : "
        f"{'READY' if if_info.get('ready') else 'NOT READY'} "
        f"({if_info.get('normal_samples', 0)}/{if_info.get('required_normal_samples', 20)} Normal samples)"
    )
    print(
        f"    2. GRU (Time-Series Forecast)      : "
        f"{'READY' if gru_info.get('ready') else 'NOT READY'} "
        f"({gru_info.get('sequence_windows', 0)}/{gru_info.get('required_sequence_windows', 30)} windows, len={gru_info.get('sequence_length', 12)})"
    )
    print(
        f"    3. XGBoost (Supervised Classifier) : "
        f"{'READY' if xgb_info.get('ready') else 'NOT READY'} "
        f"(Eligible classes >=5 samples: {xgb_info.get('eligible_classes', [])})"
    )
    print(_divider("="))


def _print_table_1(if_result: dict[str, Any]) -> None:
    print("\n" + _divider("-"))
    print("  TABLE 1: Isolation Forest Effectiveness (Unsupervised Anomaly Detection)")
    print(_divider("-"))
    if if_result.get("state") != "trained":
        print(f"  State  : {if_result.get('state', 'not_trained')}")
        if if_result.get("reason"):
            print(f"  Reason : {if_result['reason']}")
        return
    cm = if_result.get("confusion_matrix") or {}
    print(f"  State                      : TRAINED (Normal baseline samples = {if_result.get('samples')})")
    print(f"  Holdout Evaluation Samples : {if_result.get('evaluation_samples')}")
    print(f"  Precision                  : {_pct(if_result.get('precision'))}")
    print(f"  Recall                     : {_pct(if_result.get('recall'))}")
    print(f"  F1-Score                   : {_pct(if_result.get('f1_score'))}")
    print(f"  False Positive Rate (FPR)  : {_pct(if_result.get('false_positive_rate'))}")
    print(
        f"  Confusion Matrix           : "
        f"TP={cm.get('tp', 0)}, FP={cm.get('fp', 0)}, TN={cm.get('tn', 0)}, FN={cm.get('fn', 0)}"
    )
    print(f"  Saved Checkpoint           : {MODEL_DIR / 'isolation_forest.joblib'}")


def _print_table_2(gru_result: dict[str, Any]) -> None:
    print("\n" + _divider("-"))
    print("  TABLE 2: GRU Effectiveness (Time-Series Forecasting)")
    print(_divider("-"))
    if gru_result.get("state") != "trained":
        print(f"  State  : {gru_result.get('state', 'not_trained')}")
        if gru_result.get("reason"):
            print(f"  Reason : {gru_result['reason']}")
        return
    print(f"  State                      : TRAINED (Total windows = {gru_result.get('sequence_windows')})")
    print(f"  Chronological Test Windows : {gru_result.get('temporal_test_windows')}")
    print(f"  Latency MAE                : {gru_result.get('latency_mae_ms')} ms")
    print(f"  Latency RMSE               : {gru_result.get('latency_rmse_ms')} ms")
    print(f"  Packet Loss MAE            : {gru_result.get('packet_loss_mae_percent')}%")
    print(f"  Packet Loss RMSE           : {gru_result.get('packet_loss_rmse_percent')}%")
    print(f"  Reachability Accuracy      : {_pct(gru_result.get('reachability_accuracy'))}")
    print(f"  Saved Checkpoint           : {MODEL_DIR / 'gru_forecast.joblib'}")


def _print_table_3(xgb_result: dict[str, Any]) -> None:
    print("\n" + _divider("-"))
    print("  TABLE 3: XGBoost Effectiveness (Supervised Condition Classification)")
    print(_divider("-"))
    if xgb_result.get("state") != "trained":
        print(f"  State  : {xgb_result.get('state', 'not_trained')}")
        if xgb_result.get("reason"):
            print(f"  Reason : {xgb_result['reason']}")
        return
    print(f"  State                      : TRAINED (Labeled samples = {xgb_result.get('samples')})")
    print(f"  Chronological Test Samples : {xgb_result.get('temporal_test_samples')}")
    print(f"  Macro-F1                   : {_pct(xgb_result.get('temporal_test_macro_f1'))}")
    print(f"  Balanced Accuracy          : {_pct(xgb_result.get('balanced_accuracy'))}")
    if xgb_result.get("skipped_classes"):
        print(f"  Skipped Classes (<5 rows)  : {xgb_result.get('skipped_classes')}")
    per_class = xgb_result.get("per_class") or {}
    if per_class:
        print("  Per-Condition Metrics (XGBoost):")
        for label, metrics in per_class.items():
            print(
                f"    - {label:<15}: "
                f"Precision={_pct(metrics.get('precision'))}, "
                f"Recall={_pct(metrics.get('recall'))}, "
                f"F1={_pct(metrics.get('f1'))} "
                f"(test support n={metrics.get('support', 0)})"
            )
    print(f"  Saved Checkpoint           : {MODEL_DIR / 'xgboost_condition.joblib'}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Train SYSTEM 2 Proposed ML models (Isolation Forest, GRU, XGBoost) from the terminal."
    )
    parser.add_argument(
        "--model",
        choices=("isolation_forest", "gru", "xgboost", "all"),
        default="all",
        help="Which model to train: isolation_forest, gru, xgboost, or all (default: all).",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Only inspect data readiness and current model status without training.",
    )
    parser.add_argument(
        "--import-online",
        action="store_true",
        help="Probe online internet servers and import a 4-condition online benchmark dataset before training.",
    )
    parser.add_argument(
        "--import-csv",
        type=str,
        default=None,
        help="Import a CSV dataset from a URL (https://...) or local file path before training.",
    )
    args = parser.parse_args()

    if args.import_online or args.import_csv:
        print(_divider("="))
        print("  ONLINE DATASET IMPORTER (Live Internet Calibration + 4-Condition Benchmark)")
        print(_divider("-"))
        import_summary = import_online_training_dataset(csv_source=args.import_csv)
        probes = import_summary.get("live_online_probes") or []
        if probes:
            print("  Live Online Internet Probes:")
            for p in probes:
                status_str = f"{p['latency_ms']} ms" if p.get("online") else "Timeout"
                print(f"    - {p['name']:<22} ({p['target']}): {status_str}")
        print(f"  Calibrated Base Online RTT : {import_summary.get('calibrated_base_rtt_ms')} ms")
        print(f"  Imported Benchmark Samples : {import_summary.get('imported_samples')}")
        print(f"  Imported Class Breakdown   : {import_summary.get('class_counts')}")
        print(_divider("=") + "\n")

    # Step 3: Ensure rule-based auto labels (>150ms threshold) are applied to all valid samples
    auto_apply_rule_labels(overwrite=False)
    building_name = get_building_name()
    samples, labels = get_ml_training_data()
    valid_samples = [s for s in samples if is_valid_ping_sample(s)]
    readiness = get_training_readiness(samples, labels)

    _print_pipeline_header(building_name, len(valid_samples), readiness)

    if args.status:
        models_state = readiness.get("models") or {}
        _print_table_1(models_state.get("isolation_forest") or {"state": "not_trained"})
        _print_table_2(models_state.get("gru") or {"state": "not_trained"})
        _print_table_3(models_state.get("xgboost") or {"state": "not_trained"})
        print("\n" + _divider("="))
        return 0

    print(f"\n  [Step 4] Training model selection: {args.model.upper()} ...")
    if args.model == "all":
        results = train_models(samples, labels, building_name=building_name)
        _print_table_1(results.get("isolation_forest") or {})
        _print_table_2(results.get("gru") or {})
        _print_table_3(results.get("xgboost") or {})
    else:
        results = train_single_model(args.model, samples, labels, building_name=building_name)
        if args.model == "isolation_forest":
            _print_table_1(results.get("isolation_forest") or {})
        elif args.model == "gru":
            _print_table_2(results.get("gru") or {})
        elif args.model == "xgboost":
            _print_table_3(results.get("xgboost") or {})

    print("\n" + _divider("="))
    print(f"  Crash-Safe Status Saved  : {STATUS_PATH}")
    print(f"  Training History Appended: {HISTORY_PATH}")
    print("  Web UI (ML Insights) will automatically use the updated model(s) on next refresh.")
    print(_divider("="))
    return 0


if __name__ == "__main__":
    sys.exit(main())
