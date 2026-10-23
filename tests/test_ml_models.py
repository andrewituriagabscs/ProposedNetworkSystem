import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import ml_models


class ClassifierComparisonTest(unittest.TestCase):
    def test_compares_three_classifiers_on_the_same_temporal_holdout(self):
        samples = []
        labels = {}
        conditions = (
            ("Normal", True, 5, 0.0, 12.0),
            ("High Latency", True, 5, 0.0, 220.0),
            ("Packet Loss", True, 2, 60.0, 80.0),
            ("Unreachable", False, 0, 100.0, None),
        )
        record_id = 1
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)

        for step in range(20):
            recorded_at = (start + timedelta(minutes=step)).isoformat()
            for label, online, received, loss, latency in conditions:
                samples.append(
                    {
                        "id": record_id,
                        "recorded_at": recorded_at,
                        "device_name": label,
                        "target": label,
                        "online": online,
                        "ping_sent": 5,
                        "ping_received": received,
                        "packet_loss": loss,
                        "latency_ms": latency,
                        "latency_min_ms": latency,
                        "latency_median_ms": latency,
                        "latency_max_ms": latency,
                    }
                )
                labels[record_id] = label
                record_id += 1

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(ml_models, "MODEL_DIR", Path(directory)):
                result = ml_models._train_xgboost(samples, labels)

            self.assertEqual(result["state"], "trained")
            comparison = result["classifier_comparison"]
            self.assertEqual(comparison["train_samples"], 64)
            self.assertEqual(comparison["test_samples"], 16)
            self.assertEqual(
                set(comparison["models"]),
                {"xgboost", "logistic_regression", "random_forest"},
            )
            self.assertEqual(
                set(comparison["models"]["xgboost"]["per_class"]),
                {condition[0] for condition in conditions},
            )
            self.assertEqual(
                {path.name for path in Path(directory).iterdir()},
                {"xgboost_condition.joblib"},
            )

    def test_system2_pipeline_12_temporal_features_and_reviewed_labels(self):
        self.assertEqual(
            ml_models.FEATURE_COLUMNS,
            (
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
            ),
        )
        self.assertEqual(len(ml_models.FEATURE_COLUMNS), 12)
        self.assertEqual(ml_models.PIPELINE_APPROACH["ping_probes_per_check"], 5)
        vec = ml_models._features(
            {
                "online": True,
                "ping_sent": 5,
                "ping_received": 5,
                "latency_min_ms": 10.0,
                "latency_median_ms": 15.0,
                "latency_max_ms": 24.0,
                "packet_loss": 0.0,
                "recorded_at": "2026-10-22T12:00:30+00:00",
            },
            [
                {
                    "online": True,
                    "ping_sent": 5,
                    "ping_received": 5,
                    "latency_min_ms": 9.0,
                    "latency_median_ms": 12.0,
                    "latency_max_ms": 16.0,
                    "packet_loss": 0.0,
                    "recorded_at": "2026-10-22T12:00:00+00:00",
                }
            ],
        )
        self.assertEqual(vec.shape, (12,))
        self.assertAlmostEqual(float(vec[6]), 14.0)  # Jitter = 24 - 10
        self.assertAlmostEqual(float(vec[7]), 3.0)   # ΔLatency = 15 - 12
        self.assertAlmostEqual(float(vec[11]), 30.0) # ΔTime = 30s


if __name__ == "__main__":
    unittest.main()
