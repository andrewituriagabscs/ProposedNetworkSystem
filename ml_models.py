"""Train and persist ICMP anomaly, forecasting, and condition models (SYSTEM 2: Proposed / Enhanced Approach)."""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"
STATUS_PATH = MODEL_DIR / "training_status.json"
HISTORY_PATH = MODEL_DIR / "training_history.jsonl"

# Step 2: Temporal Feature Engineering (12 Features: Jitter, ΔLatency, ΔLoss, 5-Sample Trend, Streak, ΔTime)
FEATURE_COLUMNS = (
    "online",
    "latency_min_ms",
    "latency_median_ms",
    "latency_max_ms",
    "packet_loss",
    "ping_received_ratio",
    "latency_jitter_ms",
    "latency_delta_ms",
    "packet_loss_delta_percent",
    "latency_trend_ms_per_minute",
    "failure_streak",
    "elapsed_seconds",
)
CONDITION_LABELS = ("Normal", "High Latency", "Packet Loss", "Unreachable")
SEQUENCE_LENGTH = 12
MIN_NORMAL_SAMPLES = 20
MIN_SAMPLES_PER_CLASS = 5
MIN_GRU_WINDOWS = 30

PIPELINE_APPROACH = {
    "system_name": "SYSTEM 2: Proposed / Enhanced Approach",
    "steps": [
        "1. 5-Probe ICMP Burst + Dual Reference (Min/Median/Max RTT + Gateway & 1.1.1.1 + Switch OUI/Ports)",
        "2. Temporal Feature Engineering (12 Features: Jitter, ΔLatency, ΔLoss, 5-Sample Trend, Streak, ΔTime)",
        "3. Human-in-the-Loop Labeling (Admin-Reviewed Condition Labels)",
        "4. Train & Run the 3 Models (Isolation Forest, GRU, XGBoost)",
    ],
    "features": list(FEATURE_COLUMNS),
    "labeling_mode": "Human-in-the-Loop Labeling (Admin-Reviewed Condition Labels)",
    "ping_probes_per_check": 5,
}


def auto_rule_label(sample: dict[str, Any]) -> str:
    """Suggested condition label for Human-in-the-Loop review."""
    if not bool(sample.get("online")):
        return "Unreachable"
    latency = float(sample.get("latency_median_ms") or sample.get("latency_ms") or 0.0)
    loss = float(sample.get("packet_loss") or 0.0)
    if latency > 150.0:
        return "High Latency"
    if loss > 0.0:
        return "Packet Loss"
    return "Normal"


def _dependencies() -> dict[str, bool]:
    from importlib.util import find_spec

    return {
        "scikit-learn": find_spec("sklearn") is not None,
        "xgboost": find_spec("xgboost") is not None,
        "torch": find_spec("torch") is not None,
    }


def _features(sample: dict[str, Any], history: list[dict[str, Any]] | None = None):
    """Extract the 12 temporal & 5-probe burst features: Jitter, ΔLatency, ΔLoss, 5-Sample Trend, Streak, ΔTime."""
    import numpy as np

    history = history or []
    sent = max(int(sample.get("ping_sent") or 5), 1)
    online = bool(sample.get("online"))
    raw_med = sample.get("latency_median_ms") if sample.get("latency_median_ms") is not None else sample.get("latency_ms")
    raw_min = sample.get("latency_min_ms") if sample.get("latency_min_ms") is not None else raw_med
    raw_max = sample.get("latency_max_ms") if sample.get("latency_max_ms") is not None else raw_med
    current_latency = float(raw_med) if (online and raw_med is not None) else (0.0 if online else 1000.0)
    latency_min = float(raw_min) if (online and raw_min is not None) else (0.0 if online else 1000.0)
    latency_max = float(raw_max) if (online and raw_max is not None) else (0.0 if online else 1000.0)
    current_loss = float(sample.get("packet_loss") if sample.get("packet_loss") is not None else (0.0 if online else 100.0))
    recent = history[-5:]
    prior_latencies = [
        float(row.get("latency_median_ms") if row.get("latency_median_ms") is not None else row.get("latency_ms"))
        for row in recent
        if row.get("latency_median_ms") is not None or row.get("latency_ms") is not None
    ]
    previous_latency = prior_latencies[-1] if prior_latencies else None
    previous_loss = float(recent[-1].get("packet_loss") if recent[-1].get("packet_loss") is not None else 0.0) if recent else None
    trend_rows = [
        row
        for row in recent + [sample]
        if row.get("latency_median_ms") is not None or row.get("latency_ms") is not None
    ]
    latency_trend = 0.0
    if len(trend_rows) >= 2:
        elapsed_minutes = _elapsed_seconds(
            trend_rows[0].get("recorded_at"), trend_rows[-1].get("recorded_at")
        ) / 60.0
        if elapsed_minutes > 0:
            first_latency = float(trend_rows[0].get("latency_median_ms") or trend_rows[0].get("latency_ms") or 0.0)
            last_latency = float(trend_rows[-1].get("latency_median_ms") or trend_rows[-1].get("latency_ms") or 0.0)
            latency_trend = (last_latency - first_latency) / elapsed_minutes
    failure_streak = 0
    if not online:
        failure_streak = 1
        for row in reversed(history):
            if row.get("online"):
                break
            failure_streak += 1
    return np.asarray(
        [
            float(online),
            latency_min,
            current_latency,
            latency_max,
            current_loss,
            float(sample.get("ping_received") or 0) / sent,
            max(0.0, latency_max - latency_min),
            (current_latency - previous_latency) if previous_latency is not None else 0.0,
            (current_loss - previous_loss) if previous_loss is not None else 0.0,
            latency_trend,
            float(failure_streak),
            _elapsed_seconds(history[-1].get("recorded_at"), sample.get("recorded_at")) if history else 0.0,
        ],
        dtype="float32",
    )


def is_valid_ping_sample(sample: dict[str, Any]) -> bool:
    sent = int(sample.get("ping_sent") or 0)
    received = int(sample.get("ping_received") or 0)
    if sent < 1 or received < 0 or received > sent:
        return False
    if bool(sample.get("online")):
        return received > 0 and (sample.get("latency_median_ms") is not None or sample.get("latency_ms") is not None)
    return received == 0


def _atomic_write_text(path: Path, content: str) -> None:
    """Crash-safe atomic write so sudden shutdown never corrupts JSON status files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


def _atomic_dump_joblib(payload: Any, path: Path) -> None:
    """Crash-safe atomic save for .joblib model artifacts."""
    import joblib

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    joblib.dump(payload, tmp_path)
    os.replace(tmp_path, path)


def _save_status(results: dict[str, dict[str, Any]]) -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    previous = get_model_status()
    previous.update(results)
    _atomic_write_text(STATUS_PATH, json.dumps(previous, indent=2))


def get_model_status() -> dict[str, dict[str, Any]]:
    if not STATUS_PATH.exists():
        return {}
    try:
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _append_training_log(
    trigger: str,
    results: dict[str, dict[str, Any]],
    samples: list[dict[str, Any]],
    labels: dict[int, str],
    building_name: str = "Active Building",
) -> dict[str, Any]:
    """Append a crash-safe persistent training run entry to models/training_history.jsonl."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    effective_labels = {
        int(sample["id"]): labels.get(int(sample["id"])) or auto_rule_label(sample)
        for sample in samples
    }
    label_counts = Counter(effective_labels.values())
    class_counts = {label: label_counts[label] for label in CONDITION_LABELS if label_counts[label]}
    entry = {
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "building_name": building_name,
        "trigger": trigger,
        "telemetry_samples": len(samples),
        "labeled_samples": sum(label_counts.values()),
        "label_counts": class_counts,
        "models": results,
    }
    with open(HISTORY_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return entry


def get_training_logs(limit: int = 50) -> list[dict[str, Any]]:
    """Read persistent training logs from models/training_history.jsonl (newest first)."""
    if not HISTORY_PATH.exists():
        return []
    entries: list[dict[str, Any]] = []
    try:
        for line in HISTORY_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    entries.reverse()
    return entries[: max(1, limit)]


def get_training_readiness(
    samples: list[dict[str, Any]], labels: dict[int, str]
) -> dict[str, Any]:
    samples = [sample for sample in samples if is_valid_ping_sample(sample)]
    valid_ids = {int(sample["id"]) for sample in samples}
    effective_labels = {
        int(sample["id"]): labels.get(int(sample["id"])) or auto_rule_label(sample)
        for sample in samples
        if int(sample["id"]) in valid_ids
    }
    label_counts = Counter(effective_labels.values())
    normal_count = label_counts["Normal"]
    anomaly_count = sum(count for label, count in label_counts.items() if label != "Normal")
    class_counts = {label: label_counts[label] for label in CONDITION_LABELS if label_counts[label]}
    eligible_classes = [
        label for label in CONDITION_LABELS if label_counts[label] >= MIN_SAMPLES_PER_CLASS
    ]
    per_condition_readiness = {
        label: {
            "count": int(label_counts[label]),
            "required": MIN_SAMPLES_PER_CLASS,
            "ready": int(label_counts[label]) >= MIN_SAMPLES_PER_CLASS,
        }
        for label in CONDITION_LABELS
    }
    sequence_windows = sum(
        max(0, len(rows) - SEQUENCE_LENGTH)
        for rows in _samples_by_device(samples).values()
    )
    return {
        "pipeline": PIPELINE_APPROACH,
        "telemetry_samples": len(samples),
        "labeled_samples": sum(label_counts.values()),
        "label_counts": class_counts,
        "per_condition_readiness": per_condition_readiness,
        "isolation_forest": {
            "ready": normal_count >= MIN_NORMAL_SAMPLES,
            "normal_samples": normal_count,
            "anomaly_samples": anomaly_count,
            "required_normal_samples": MIN_NORMAL_SAMPLES,
        },
        "xgboost": {
            "ready": len(eligible_classes) >= 2,
            "eligible_classes": eligible_classes,
            "required_classes": 2,
            "required_samples_per_class": MIN_SAMPLES_PER_CLASS,
        },
        "gru": {
            "ready": sequence_windows >= MIN_GRU_WINDOWS,
            "sequence_windows": sequence_windows,
            "required_sequence_windows": MIN_GRU_WINDOWS,
            "sequence_length": SEQUENCE_LENGTH,
        },
        "dependencies": _dependencies(),
        "models": get_model_status(),
        "training_logs": get_training_logs(limit=30),
    }


def _samples_by_device(samples: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        grouped[str(sample.get("target") or sample.get("device_name") or "unknown")].append(sample)
    for rows in grouped.values():
        rows.sort(key=lambda row: (row.get("recorded_at") or "", int(row.get("id") or 0)))
    return grouped


def _feature_map(samples: list[dict[str, Any]]):
    import numpy as np

    vectors = {}
    for rows in _samples_by_device(samples).values():
        for index, row in enumerate(rows):
            vectors[int(row["id"])] = _features(row, rows[:index])
    return {sample_id: np.asarray(vector, dtype="float32") for sample_id, vector in vectors.items()}


def _result(state: str, **details: Any) -> dict[str, Any]:
    return {"state": state, **details}


def _train_isolation_forest(samples: list[dict[str, Any]], labels: dict[int, str]):
    effective_labels = {
        int(sample["id"]): labels.get(int(sample["id"])) or auto_rule_label(sample)
        for sample in samples
    }
    baseline = [sample for sample in samples if effective_labels.get(int(sample["id"])) == "Normal"]
    if len(baseline) < MIN_NORMAL_SAMPLES:
        return _result(
            "not_ready",
            reason=f"Collect at least {MIN_NORMAL_SAMPLES} normal ping samples to build a baseline.",
            samples=len(baseline),
        )

    import joblib
    import numpy as np
    from sklearn.ensemble import IsolationForest
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    feature_vectors = _feature_map(samples)
    features = np.vstack([feature_vectors[int(sample["id"])] for sample in baseline])
    model = make_pipeline(
        StandardScaler(),
        IsolationForest(
            n_estimators=200,
            contamination=0.05,
            random_state=42,
        ),
    )
    model.fit(features)

    # Evaluate Table 1 Effectiveness Metrics (Precision, Recall, F1-Score, False Positive Rate)
    ordered_samples = sorted(samples, key=lambda row: (row.get("recorded_at") or "", int(row.get("id") or 0)))
    split_at = max(1, int(len(ordered_samples) * 0.8))
    eval_samples = ordered_samples[split_at:] if len(ordered_samples) >= 10 else ordered_samples
    if not any(effective_labels.get(int(row["id"])) != "Normal" for row in eval_samples):
        eval_samples = ordered_samples

    eval_x = np.vstack([feature_vectors[int(row["id"])] for row in eval_samples])
    scores = model.decision_function(eval_x)
    predicted_anomaly = scores < 0
    actual_anomaly = np.asarray([effective_labels.get(int(row["id"])) != "Normal" for row in eval_samples], dtype=bool)

    tp = int(np.sum(predicted_anomaly & actual_anomaly))
    fp = int(np.sum(predicted_anomaly & ~actual_anomaly))
    tn = int(np.sum(~predicted_anomaly & ~actual_anomaly))
    fn = int(np.sum(~predicted_anomaly & actual_anomaly))

    precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
    recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
    f1 = round(2 * precision * recall / (precision + recall), 4) if (precision + recall) > 0 else 0.0
    fpr = round(fp / (fp + tn), 4) if (fp + tn) > 0 else 0.0

    _atomic_dump_joblib(
        {"model": model, "features": FEATURE_COLUMNS, "version": "isolation-forest-v2"},
        MODEL_DIR / "isolation_forest.joblib",
    )
    return _result(
        "trained",
        samples=len(baseline),
        evaluation_samples=len(eval_samples),
        precision=precision,
        recall=recall,
        f1_score=f1,
        false_positive_rate=fpr,
        confusion_matrix={"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        method="normal-baseline anomaly detection (12 temporal features, 5-probe burst)",
    )


def _train_xgboost(samples: list[dict[str, Any]], labels: dict[int, str]):
    effective_labels = {
        int(sample["id"]): labels.get(int(sample["id"])) or auto_rule_label(sample)
        for sample in samples
    }
    all_rows = [sample for sample in samples if int(sample["id"]) in labels] if labels else list(samples)
    used_labels = labels if labels else effective_labels
    all_counts = Counter(used_labels[int(sample["id"])] for sample in all_rows)
    eligible_classes = {label for label, count in all_counts.items() if count >= MIN_SAMPLES_PER_CLASS}
    skipped_classes = {label: count for label, count in all_counts.items() if count < MIN_SAMPLES_PER_CLASS}
    if len(eligible_classes) < 2:
        return _result(
            "not_ready",
            reason=f"Provide at least {MIN_SAMPLES_PER_CLASS} examples in each of two or more conditions.",
            class_counts=dict(all_counts),
        )
    rows = [sample for sample in all_rows if used_labels[int(sample["id"])] in eligible_classes]
    counts = Counter(used_labels[int(sample["id"])] for sample in rows)

    import joblib
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import balanced_accuracy_score, f1_score, precision_recall_fscore_support
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from xgboost import XGBClassifier

    feature_vectors = _feature_map(samples)
    rows.sort(key=lambda row: (row.get("recorded_at") or "", int(row.get("id") or 0)))
    classes = sorted(counts)
    class_to_id = {label: index for index, label in enumerate(classes)}
    split_at = max(1, int(len(rows) * 0.8))
    test_start = rows[split_at].get("recorded_at") or ""
    train_rows = [row for row in rows if (row.get("recorded_at") or "") < test_start]
    test_rows = [row for row in rows if (row.get("recorded_at") or "") >= test_start]
    train_classes = {used_labels[int(row["id"])] for row in train_rows}
    test_classes = {used_labels[int(row["id"])] for row in test_rows}
    missing_train_classes = set(classes) - train_classes
    missing_test_classes = set(classes) - test_classes

    # If a global timestamp split misses rare condition classes in train or test,
    # apply a chronological 80/20 split per condition class so all classes are represented.
    if missing_train_classes or missing_test_classes or not test_rows:
        train_rows = []
        test_rows = []
        for condition_name in classes:
            class_rows = [row for row in rows if used_labels[int(row["id"])] == condition_name]
            class_split = max(1, min(len(class_rows) - 1, int(len(class_rows) * 0.8)))
            train_rows.extend(class_rows[:class_split])
            test_rows.extend(class_rows[class_split:])
        train_rows.sort(key=lambda row: (row.get("recorded_at") or "", int(row.get("id") or 0)))
        test_rows.sort(key=lambda row: (row.get("recorded_at") or "", int(row.get("id") or 0)))
        test_start = test_rows[0].get("recorded_at") or "" if test_rows else ""

    if not train_rows or not test_rows:
        return _result(
            "not_ready",
            reason="Need both earlier training samples and later chronological test samples.",
            class_counts=dict(counts),
        )

    def make_xgboost_estimator():
        return XGBClassifier(
            n_estimators=120,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="multi:softprob",
            num_class=len(classes),
            eval_metric="mlogloss",
            random_state=42,
            n_jobs=1,
        )

    train_x = np.vstack([feature_vectors[int(row["id"])] for row in train_rows])
    train_y = np.asarray([class_to_id[used_labels[int(row["id"])]] for row in train_rows])
    test_x = np.vstack([feature_vectors[int(row["id"])] for row in test_rows])
    test_y = np.asarray([class_to_id[used_labels[int(row["id"])]] for row in test_rows])
    evaluation_models = {
        "xgboost": make_xgboost_estimator(),
        "logistic_regression": make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=2000, random_state=42),
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=200,
            random_state=42,
            n_jobs=1,
        ),
    }
    comparison_results = {}
    class_ids = np.arange(len(classes))
    for model_name, evaluation_model in evaluation_models.items():
        evaluation_model.fit(train_x, train_y)
        raw_predictions = evaluation_model.predict(test_x)
        predictions = (
            np.argmax(raw_predictions, axis=1)
            if getattr(raw_predictions, "ndim", 1) > 1
            else np.asarray(raw_predictions, dtype=int)
        )
        precision, recall, class_f1, support = precision_recall_fscore_support(
            test_y,
            predictions,
            labels=class_ids,
            zero_division=0,
        )
        comparison_results[model_name] = {
            "macro_f1": round(float(f1_score(
                test_y,
                predictions,
                labels=class_ids,
                average="macro",
                zero_division=0,
            )), 4),
            "balanced_accuracy": round(float(balanced_accuracy_score(test_y, predictions)), 4),
            "per_class": {
                label: {
                    "precision": round(float(precision[index]), 4),
                    "recall": round(float(recall[index]), 4),
                    "f1": round(float(class_f1[index]), 4),
                    "support": int(support[index]),
                }
                for index, label in enumerate(classes)
            },
        }

    macro_f1 = comparison_results["xgboost"]["macro_f1"]
    balanced_acc = comparison_results["xgboost"]["balanced_accuracy"]

    final_model = make_xgboost_estimator()
    all_x = np.vstack([feature_vectors[int(row["id"])] for row in rows])
    all_y = np.asarray([class_to_id[used_labels[int(row["id"])]] for row in rows])
    final_model.fit(all_x, all_y)
    _atomic_dump_joblib(
        {
            "model": final_model,
            "features": FEATURE_COLUMNS,
            "classes": classes,
            "version": "xgboost-condition-v2",
        },
        MODEL_DIR / "xgboost_condition.joblib",
    )
    return _result(
        "trained",
        samples=len(rows),
        class_counts=dict(counts),
        skipped_classes=skipped_classes,
        temporal_test_samples=len(test_rows),
        temporal_test_start=test_start,
        temporal_test_macro_f1=macro_f1,
        balanced_accuracy=balanced_acc,
        per_class=comparison_results["xgboost"]["per_class"],
        classifier_comparison={
            "protocol": "single chronological 80/20 holdout",
            "train_samples": len(train_rows),
            "test_samples": len(test_rows),
            "test_start": test_start,
            "models": comparison_results,
            "note": "SYSTEM 2 Proposed Evaluation on 12 temporal features (5-probe burst) and Admin-Reviewed condition labels.",
        },
    )


def _build_gru(torch, input_size: int, hidden_size: int = 24):
    from torch import nn

    class PingGRU(nn.Module):
        def __init__(self):
            super().__init__()
            self.recurrent = nn.GRU(input_size, hidden_size, batch_first=True)
            self.head = nn.Linear(hidden_size, 3)

        def forward(self, values):
            output, _ = self.recurrent(values)
            return self.head(output[:, -1, :])

    return PingGRU()


def _elapsed_seconds(previous: str | None, current: str | None) -> float:
    if not previous or not current:
        return 0.0
    try:
        delta = (
            datetime.fromisoformat(current.replace("Z", "+00:00"))
            - datetime.fromisoformat(previous.replace("Z", "+00:00"))
        ).total_seconds()
    except ValueError:
        return 0.0
    return max(0.0, min(float(delta), 3600.0))


def _supervised_recommendation(item: dict[str, Any]) -> dict[str, Any]:
    """Build a recommendation combining Step 4's 3 Models (Isolation Forest, GRU, XGBoost) on 12 Temporal Features."""
    current = item["current"]
    xgb = item.get("xgboost", {})
    if_model = item.get("isolation_forest", {})
    gru_model = item.get("gru", {})
    trained = xgb.get("state") == "ready"
    condition = xgb.get("condition") if trained else current.get("auto_rule_label", "Normal")
    confidence = xgb.get("confidence") if trained else None
    latency = float(current.get("latency_median_ms") or 0.0) if current.get("online") else None
    jitter = float(current.get("latency_jitter_ms") or 0.0) if current.get("online") else 0.0
    if_anomaly = if_model.get("state") == "ready" and if_model.get("result") == "Anomaly"
    gru_risks = gru_model.get("risk_indicators", {}) if gru_model.get("state") == "ready" else {}
    gru_high_risk = any(v == "High" for v in gru_risks.values())

    if condition == "High Latency":
        if latency is not None and (latency >= 300.0 or jitter >= 45.0):
            return {
                "trained": trained,
                "model": "XGBoost + Isolation Forest + GRU (12-Feature System 2)" if trained else "System 2 (Untrained — 5-Probe Preview)",
                "condition": "High Latency",
                "confidence": confidence,
                "severity": "critical",
                "possible_cause": f"Possible DDoS / Traffic Flood or Severe Burst Jitter ({jitter:g} ms spread)",
                "recommended_action": "Block / Rate-Limit: Block suspicious source IPs on the firewall, enable ICMP flood protection / rate-limiting on the switch port, or isolate the overloaded host.",
            }
        return {
            "trained": trained,
            "model": "XGBoost + Isolation Forest + GRU (12-Feature System 2)" if trained else "System 2 (Untrained — 5-Probe Preview)",
            "condition": "High Latency",
            "confidence": confidence,
            "severity": "warning",
            "possible_cause": f"Network Bottleneck / Rising 5-Sample Trend (Jitter: {jitter:g} ms)",
            "recommended_action": "Prioritize / Throttle: Compare against Local Gateway & 1.1.1.1, check for heavy transfers on this host, apply QoS prioritization, or inspect switch port load.",
        }

    if condition == "Packet Loss":
        return {
            "trained": trained,
            "model": "XGBoost + Isolation Forest + GRU (12-Feature System 2)" if trained else "System 2 (Untrained — 5-Probe Preview)",
            "condition": "Packet Loss",
            "confidence": confidence,
            "severity": "warning",
            "possible_cause": "5-Probe Burst Packet Drop / Unstable Link or Broadcast Storm",
            "recommended_action": "Inspect Link / Switch Port: Compare against Dual Reference (Gateway & 1.1.1.1), check physical Ethernet cable or Wi-Fi signal, inspect switch port for CRC/duplex errors, or block broadcast storms.",
        }

    if condition == "Unreachable":
        return {
            "trained": trained,
            "model": "XGBoost + Isolation Forest + GRU (12-Feature System 2)" if trained else "System 2 (Untrained — 5-Probe Preview)",
            "condition": "Unreachable",
            "confidence": confidence,
            "severity": "critical",
            "possible_cause": "Host Offline (0/5 Probes), Cable Unplugged, or DoS / Firewall Block",
            "recommended_action": "Check Host / Mitigate DoS: Compare with Dual Reference (Gateway & 1.1.1.1) and Switch OUI/Ports. If powered on, check firewall ICMP rules or block attacking IPs if a DoS flood knocked the host offline.",
        }

    if if_anomaly or gru_high_risk:
        cause_parts = []
        if if_anomaly:
            cause_parts.append(f"Isolation Forest Temporal Anomaly (score {if_model.get('anomaly_score')})")
        if gru_high_risk:
            cause_parts.append(
                f"GRU Forecast Risk (next {gru_model.get('next_latency_ms')} ms, {gru_model.get('next_packet_loss_percent')}% loss)"
            )
        return {
            "trained": trained,
            "model": "Isolation Forest + GRU Early Warning (12-Feature System 2)",
            "condition": "Normal (Early Warning)",
            "confidence": confidence,
            "severity": "warning",
            "possible_cause": " + ".join(cause_parts),
            "recommended_action": "Proactive Check: Compare 5-probe burst jitter and 5-sample trend against Local Gateway & 1.1.1.1 before degradation escalates.",
        }

    return {
        "trained": trained,
        "model": "XGBoost + Isolation Forest + GRU (12-Feature System 2)" if trained else "System 2 (Untrained — 5-Probe Preview)",
        "condition": "Normal",
        "confidence": confidence,
        "severity": "normal",
        "possible_cause": "Healthy 5-Probe Burst Response (Low Jitter, 0% Loss)",
        "recommended_action": "Continue monitoring — no action required.",
    }


def _suggestions(item: dict[str, Any]) -> list[dict[str, Any]]:
    action_text = {
        "check_endpoint": "Check that the PC is powered on and connected to the network.",
        "check_gateway": "Ping the local gateway and compare its result with other monitored PCs.",
        "check_icmp_policy": "Verify that the PC and its firewall allow ICMP echo replies.",
        "compare_latency": "Compare this PC's recent latency with its baseline and the gateway.",
        "compare_packet_loss": "Repeat pings to this PC and the gateway, then compare packet loss across PCs.",
        "inspect_shared_path": "Check the shared router or network path if several PCs show the same degradation.",
        "continue_monitoring": "No strong anomaly signal is present; continue monitoring for a change.",
    }
    suggestions: dict[str, dict[str, Any]] = {}

    def add(action_id: str, model: str, evidence: str) -> None:
        suggestion = suggestions.setdefault(
            action_id,
            {
                "id": action_id,
                "action": action_text[action_id],
                "model_sources": [],
                "evidence": [],
            },
        )
        if model not in suggestion["model_sources"]:
            suggestion["model_sources"].append(model)
        if evidence not in suggestion["evidence"]:
            suggestion["evidence"].append(evidence)

    current = item["current"]
    if not current["online"]:
        add("check_endpoint", "ICMP observation", "The latest sample received no ping replies.")
        add("check_gateway", "ICMP observation", "Compare endpoint reachability with the local gateway.")
        add("check_icmp_policy", "ICMP observation", "A host or firewall may suppress ping replies.")

    anomaly = item.get("isolation_forest", {})
    if anomaly.get("state") == "ready" and anomaly.get("result") == "Anomaly":
        add("compare_latency", "Isolation Forest", "The ping feature pattern differs from the learned normal baseline.")

    condition = item.get("xgboost", {})
    if condition.get("state") == "ready":
        condition_name = condition.get("condition")
        if condition_name == "High Latency":
            add("compare_latency", "XGBoost", "The classifier predicts the High Latency condition.")
        elif condition_name == "Packet Loss":
            add("compare_packet_loss", "XGBoost", "The classifier predicts the Packet Loss condition.")
        elif condition_name == "Unreachable":
            add("check_endpoint", "XGBoost", "The classifier predicts the Unreachable condition.")
            add("check_gateway", "XGBoost", "Compare endpoint reachability with the local gateway.")

    forecast = item.get("gru", {})
    risks = forecast.get("risk_indicators", {}) if forecast.get("state") == "ready" else {}
    if risks.get("bottleneck") in ("High", "Watch"):
        add("compare_latency", "GRU", f"Forecast bottleneck risk is {risks['bottleneck']}.")
    if risks.get("congestion") in ("High", "Watch"):
        add("compare_packet_loss", "GRU", f"Forecast congestion-like risk is {risks['congestion']}.")
        add("inspect_shared_path", "GRU", "Compare other PCs before investigating a shared path.")
    if risks.get("failure") in ("High", "Watch"):
        add("check_gateway", "GRU", f"Forecast reachability/failure risk is {risks['failure']}.")
        add("check_endpoint", "GRU", "Confirm the PC remains powered on and connected.")

    if not suggestions:
        add("continue_monitoring", "System", "No trained model or current ping signal indicates an action is needed.")
    return list(suggestions.values())


def _train_gru(samples: list[dict[str, Any]]):
    import numpy as np

    sequences = []
    targets = []
    window_times = []
    for rows in _samples_by_device(samples).values():
        if len(rows) <= SEQUENCE_LENGTH:
            continue
        vectors = []
        for index, row in enumerate(rows):
            vectors.append(_features(row, rows[:index]))
        for index in range(SEQUENCE_LENGTH, len(rows)):
            sequences.append(vectors[index - SEQUENCE_LENGTH : index])
            target = rows[index]
            targets.append(
                [
                    float(target.get("latency_median_ms") or target.get("latency_ms") or 0),
                    float(target.get("packet_loss") or 0),
                    float(bool(target.get("online"))),
                ]
            )
            window_times.append(target.get("recorded_at") or "")

    if len(sequences) < MIN_GRU_WINDOWS:
        return _result(
            "not_ready",
            reason=f"Need at least {MIN_GRU_WINDOWS} chronological training windows; each window uses {SEQUENCE_LENGTH} prior samples from one PC.",
            sequence_windows=len(sequences),
        )

    import joblib
    import torch
    from sklearn.preprocessing import StandardScaler
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset

    order = sorted(range(len(sequences)), key=lambda index: (window_times[index], index))
    split_at = max(1, int(len(sequences) * 0.8))
    test_start = window_times[order[split_at]]
    train_indices = [index for index in order if window_times[index] < test_start]
    test_indices = [index for index in order if window_times[index] >= test_start]
    if not train_indices or not test_indices:
        train_indices = order[:split_at]
        test_indices = order[split_at:]
    sequences = np.asarray(sequences, dtype="float32")
    targets = np.asarray(targets, dtype="float32")
    if not train_indices or not test_indices:
        return _result("not_ready", reason="Need later samples for a chronological test set.")

    train_x, test_x = sequences[train_indices], sequences[test_indices]
    train_y, test_y = targets[train_indices], targets[test_indices]
    input_scaler = StandardScaler().fit(train_x.reshape(-1, train_x.shape[-1]))
    target_scaler = StandardScaler().fit(train_y[:, :2])
    train_x = input_scaler.transform(train_x.reshape(-1, train_x.shape[-1])).reshape(train_x.shape)
    test_x_scaled = input_scaler.transform(test_x.reshape(-1, test_x.shape[-1])).reshape(test_x.shape)
    train_y_scaled = target_scaler.transform(train_y[:, :2])
    train_reachability = train_y[:, 2:3]

    torch.manual_seed(42)
    torch.set_num_threads(1)
    model = _build_gru(torch, train_x.shape[-1])
    optimizer = torch.optim.Adam(model.parameters(), lr=0.005)
    loss_function = nn.MSELoss()
    reachability_loss = nn.BCEWithLogitsLoss()
    dataset = TensorDataset(
        torch.from_numpy(train_x),
        torch.from_numpy(train_y_scaled.astype("float32")),
        torch.from_numpy(train_reachability.astype("float32")),
    )
    loader = DataLoader(dataset, batch_size=min(16, len(dataset)), shuffle=True)
    model.train()
    for _ in range(40):
        for batch_x, batch_y, batch_reachability in loader:
            optimizer.zero_grad()
            prediction = model(batch_x)
            loss = loss_function(prediction[:, :2], batch_y) + reachability_loss(
                prediction[:, 2:3], batch_reachability
            )
            loss.backward()
            optimizer.step()

    model.eval()
    with torch.no_grad():
        test_output = model(torch.from_numpy(test_x_scaled)).cpu().numpy()
    predicted = target_scaler.inverse_transform(test_output[:, :2])
    mae = np.mean(np.abs(predicted - test_y[:, :2]), axis=0)
    rmse = np.sqrt(np.mean(np.square(predicted - test_y[:, :2]), axis=0))
    reachability_probability = 1 / (1 + np.exp(-test_output[:, 2]))
    reachability_accuracy = float(
        np.mean((reachability_probability >= 0.5) == (test_y[:, 2] >= 0.5))
    )
    state = {key: value.detach().cpu() for key, value in model.state_dict().items()}
    _atomic_dump_joblib(
        {
            "state_dict": state,
            "input_scaler": input_scaler,
            "target_scaler": target_scaler,
            "features": FEATURE_COLUMNS,
            "sequence_length": SEQUENCE_LENGTH,
            "hidden_size": 24,
            "version": "gru-ping-forecast-v3",
        },
        MODEL_DIR / "gru_forecast.joblib",
    )
    return _result(
        "trained",
        sequence_windows=len(sequences),
        temporal_test_windows=len(test_x),
        temporal_test_start=test_start,
        latency_mae_ms=round(float(mae[0]), 4),
        packet_loss_mae_percent=round(float(mae[1]), 4),
        latency_rmse_ms=round(float(rmse[0]), 4),
        packet_loss_rmse_percent=round(float(rmse[1]), 4),
        reachability_accuracy=round(reachability_accuracy, 4),
    )


def train_single_model(
    model_name: str,
    samples: list[dict[str, Any]],
    labels: dict[int, str],
    building_name: str = "Active Building",
) -> dict[str, dict[str, Any]]:
    """Train a single model (isolation_forest, gru, or xgboost) without overwriting the others."""
    trainers = {
        "isolation_forest": (_train_isolation_forest, ("scikit-learn",)),
        "gru": (_train_gru, ("scikit-learn", "torch")),
        "xgboost": (_train_xgboost, ("scikit-learn", "xgboost")),
    }
    if model_name not in trainers:
        raise ValueError(f"Unknown model '{model_name}'. Choose isolation_forest, gru, or xgboost.")

    samples = [sample for sample in samples if is_valid_ping_sample(sample)]
    valid_ids = {int(sample["id"]) for sample in samples}
    labels = {
        int(sample["id"]): labels.get(int(sample["id"])) or auto_rule_label(sample)
        for sample in samples
        if int(sample["id"]) in valid_ids
    }
    dependencies = _dependencies()
    trainer, required = trainers[model_name]
    missing = [package for package in required if not dependencies[package]]
    if missing:
        result = _result("dependency_missing", packages=missing)
    else:
        try:
            result = trainer(samples, labels) if model_name != "gru" else trainer(samples)
        except Exception as error:
            result = _result("failed", reason=f"{type(error).__name__}: {error}")

    results = {model_name: result}
    _save_status(results)
    _append_training_log(model_name, results, samples, labels, building_name=building_name)
    return get_model_status()


def train_models(
    samples: list[dict[str, Any]],
    labels: dict[int, str],
    building_name: str = "Active Building",
) -> dict[str, dict[str, Any]]:
    samples = [sample for sample in samples if is_valid_ping_sample(sample)]
    valid_ids = {int(sample["id"]) for sample in samples}
    labels = {
        int(sample["id"]): labels.get(int(sample["id"])) or auto_rule_label(sample)
        for sample in samples
        if int(sample["id"]) in valid_ids
    }
    dependencies = _dependencies()
    results: dict[str, dict[str, Any]] = {}
    trainers = {
        "isolation_forest": (_train_isolation_forest, ("scikit-learn",)),
        "gru": (_train_gru, ("scikit-learn", "torch")),
        "xgboost": (_train_xgboost, ("scikit-learn", "xgboost")),
    }
    for name, (trainer, required) in trainers.items():
        missing = [package for package in required if not dependencies[package]]
        if missing:
            results[name] = _result("dependency_missing", packages=missing)
            continue
        try:
            results[name] = trainer(samples, labels) if name != "gru" else trainer(samples)
        except Exception as error:
            results[name] = _result("failed", reason=f"{type(error).__name__}: {error}")
    _save_status(results)
    _append_training_log("all", results, samples, labels, building_name=building_name)
    return results


def get_ml_insights(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    valid_samples = [sample for sample in samples if is_valid_ping_sample(sample)]
    devices = _samples_by_device(valid_samples)
    artifacts = {
        "isolation_forest": MODEL_DIR / "isolation_forest.joblib",
        "xgboost": MODEL_DIR / "xgboost_condition.joblib",
        "gru": MODEL_DIR / "gru_forecast.joblib",
    }
    results = []
    for target, rows in devices.items():
        latest = rows[-1]
        item: dict[str, Any] = {
            "telemetry_id": int(latest["id"]),
            "target": target,
            "device_name": latest.get("device_name", target),
            "recorded_at": latest.get("recorded_at"),
            "current": {
                "online": bool(latest.get("online")),
                "latency_min_ms": latest.get("latency_min_ms"),
                "latency_median_ms": latest.get("latency_median_ms") or latest.get("latency_ms"),
                "latency_max_ms": latest.get("latency_max_ms"),
                "latency_jitter_ms": round(
                    max(
                        0.0,
                        float(latest.get("latency_max_ms") or 0.0)
                        - float(latest.get("latency_min_ms") or 0.0),
                    ),
                    2,
                )
                if latest.get("online")
                else 0.0,
                "packet_loss": latest.get("packet_loss", 0),
                "auto_rule_label": auto_rule_label(latest),
            },
            "isolation_forest": {"state": "not_trained"},
            "xgboost": {"state": "not_trained"},
            "gru": {"state": "not_trained"},
        }
        if artifacts["isolation_forest"].exists():
            try:
                import joblib

                artifact = joblib.load(artifacts["isolation_forest"])
                if artifact.get("version") != "isolation-forest-v2" or tuple(artifact.get("features", ())) != FEATURE_COLUMNS:
                    item["isolation_forest"] = {"state": "retrain_required"}
                else:
                    features = _features(latest, rows[:-1]).reshape(1, -1)
                    score = float(artifact["model"].decision_function(features)[0])
                    item["isolation_forest"] = {
                        "state": "ready",
                        "result": "Anomaly" if score < 0 else "Normal",
                        "anomaly_score": round(-score, 5),
                    }
            except Exception as error:
                item["isolation_forest"] = {"state": "error", "reason": str(error)}
        if artifacts["xgboost"].exists():
            try:
                import joblib

                artifact = joblib.load(artifacts["xgboost"])
                if artifact.get("version") != "xgboost-condition-v2" or tuple(artifact.get("features", ())) != FEATURE_COLUMNS:
                    item["xgboost"] = {"state": "retrain_required"}
                else:
                    features = _features(latest, rows[:-1]).reshape(1, -1)
                    probabilities = artifact["model"].predict_proba(features)[0]
                    class_index = int(probabilities.argmax())
                    item["xgboost"] = {
                        "state": "ready",
                        "condition": artifact["classes"][class_index],
                        "confidence": round(float(probabilities[class_index]), 4),
                    }
            except Exception as error:
                item["xgboost"] = {"state": "error", "reason": str(error)}
        if artifacts["gru"].exists():
            try:
                import joblib
                import numpy as np
                import torch

                artifact = joblib.load(artifacts["gru"])
                if artifact.get("version") != "gru-ping-forecast-v3" or tuple(artifact.get("features", ())) != FEATURE_COLUMNS:
                    item["gru"] = {"state": "retrain_required"}
                    sequence_length = 0
                else:
                    sequence_length = int(artifact["sequence_length"])
                if item["gru"].get("state") == "retrain_required":
                    pass
                elif len(rows) < sequence_length:
                    item["gru"] = {
                        "state": "not_enough_history",
                        "required_samples": sequence_length,
                    }
                else:
                    first_index = len(rows) - sequence_length
                    vectors = [
                        _features(row, rows[:index])
                        for index, row in enumerate(rows[first_index:], start=first_index)
                    ]
                    values = np.asarray(vectors, dtype="float32")
                    scaled = artifact["input_scaler"].transform(values)[None, :, :]
                    model = _build_gru(torch, scaled.shape[-1], int(artifact["hidden_size"]))
                    model.load_state_dict(artifact["state_dict"])
                    model.eval()
                    with torch.no_grad():
                        prediction = model(torch.from_numpy(scaled)).cpu().numpy()
                    forecast = artifact["target_scaler"].inverse_transform(prediction[:, :2])[0]
                    reachability_probability = float(
                        1 / (1 + np.exp(-np.clip(prediction[0, 2], -60, 60)))
                    )
                    next_latency = round(max(0.0, float(forecast[0])), 3)
                    next_packet_loss = round(min(100.0, max(0.0, float(forecast[1]))), 2)
                    recent_latencies = [
                        float(row.get("latency_median_ms") or row.get("latency_ms"))
                        for row in rows[-5:]
                        if row.get("latency_median_ms") is not None or row.get("latency_ms") is not None
                    ]
                    sustained_high_latency = sum(value >= 150 for value in recent_latencies) >= 3
                    bottleneck_level = (
                        "High" if next_latency >= 150 and sustained_high_latency
                        else "Watch" if next_latency >= 150 or sustained_high_latency
                        else "Low"
                    )
                    congestion_level = (
                        "High" if next_latency >= 150 and next_packet_loss >= 20
                        else "Watch" if next_latency >= 100 or next_packet_loss >= 10
                        else "Low"
                    )
                    failure_level = (
                        "High" if reachability_probability < 0.5 or next_packet_loss >= 80
                        else "Watch" if reachability_probability < 0.8 or next_packet_loss >= 40
                        else "Low"
                    )
                    item["gru"] = {
                        "state": "ready",
                        "next_latency_ms": next_latency,
                        "next_packet_loss_percent": next_packet_loss,
                        "next_reachability_probability": round(reachability_probability, 4),
                        "risk_indicators": {
                            "bottleneck": bottleneck_level,
                            "congestion": congestion_level,
                            "failure": failure_level,
                        },
                    }
            except Exception as error:
                item["gru"] = {"state": "error", "reason": str(error)}
        item["supervised_recommendation"] = _supervised_recommendation(item)
        item["suggestions"] = _suggestions(item)
        results.append(item)
    return results
