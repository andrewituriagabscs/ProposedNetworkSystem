"""Device polling, persistence, and ML monitoring records (SYSTEM 2: Proposed / Enhanced Approach)."""

from __future__ import annotations

import asyncio
import os
import platform
import re
import json
import statistics
import sqlite3
import subprocess
import ipaddress
import socket
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil

BASE_DIR = Path(__file__).resolve().parent
POLL_INTERVAL_SECONDS = int(os.getenv("MONITORING_POLL_SECONDS", "30"))
SNMP_TIMEOUT_SECONDS = 1.5

try:
    SNMP_PORT = max(1, min(int(os.getenv("SNMP_PORT", "161")), 65535))
except ValueError:
    SNMP_PORT = 161

SNMP_MAX_INTERFACES = 512

# MAC OUI database for phone/device detection
PHONE_MANUFACTURERS = {
    "00:1a:2b", "00:1a:2d", "00:1a:5e", "00:1d:4f", "00:25:86", "00:50:f2",  # Apple
    "b0:35:9f", "5c:f3:70", "00:1e:52", "9c:a6:15", "04:fd:55", "74:33:c3",  # Samsung
    "e4:54:e8", "54:6a:5c", "e8:ba:70",  # Huawei
    "1e:10:3d", "90:a2:da", "d0:76:d0",  # OnePlus
    "8c:72:f8", "00:aa:33",  # Xiaomi
    "bc:f5:ac", "28:11:95",  # LG
    "00:0d:93", "a4:ae:12",  # Google Pixel
    "5c:6d:7e", "00:e0:4c",  # Motorola
    "7c:7a:91", "a4:2b:8c",  # HTC
    "f4:f1:e0", "84:89:ad",  # Sony
    "08:62:66", "e8:99:c4",  # Amazon
}
# MAC OUI prefixes for known network switch / router manufacturers
SWITCH_MANUFACTURERS = {
    # Cisco Systems
    "00:00:0c", "00:1a:a1", "00:1b:d4", "00:1c:57", "00:1d:70", "00:1e:be",
    "00:1f:26", "00:21:1b", "00:22:55", "00:23:04", "00:24:13", "00:25:45",
    "00:26:0a", "00:26:cb", "00:27:0d", "58:8d:09", "a4:56:30", "d0:c7:89",
    "e8:ba:70", "f4:cf:e2", "f8:72:ea",
    # HP / Aruba Networks
    "00:0b:86", "00:1a:1e", "00:17:c8", "00:18:fe", "24:be:05", "6c:c2:17",
    "9c:8c:d8", "b4:5d:50", "d8:c7:c8", "94:b4:0f", "f0:5c:d5",
    # Netgear
    "00:09:5b", "00:0f:b5", "00:14:6c", "00:18:4d", "00:1b:2f", "00:1e:2a",
    "00:22:3f", "00:24:b2", "08:36:c9", "20:4e:7f", "28:c6:8e", "30:46:9a",
    "44:94:fc", "a0:21:b7", "c4:04:15",
    # TP-Link Technologies
    "00:27:19", "14:cc:20", "1c:3b:f3", "50:c7:bf", "54:a7:03", "60:32:b1",
    "6c:5a:b0", "74:da:38", "80:ea:96", "90:f6:52", "a0:f3:c1", "b0:be:76",
    "c4:6e:1f", "d8:0d:17", "e8:de:27", "f4:f2:6d",
    # MikroTik
    "00:0c:42", "18:fd:74", "2c:c8:1b", "48:8f:5a", "6c:3b:6b", "74:4d:28",
    "b8:69:f4", "cc:2d:e0", "d4:ca:6d", "e4:8d:8c",
    # Ubiquiti Networks
    "00:27:22", "04:18:d6", "18:e8:29", "24:a4:3c", "44:d9:e7", "68:72:51",
    "78:8a:20", "80:2a:a8", "b4:fb:e4", "dc:9f:db", "f0:9f:c2",
    # D-Link Systems
    "00:05:5d", "00:0d:88", "00:11:95", "00:13:46", "00:15:e9", "00:17:9a",
    "00:19:5b", "00:1b:11", "00:1c:f0", "00:1e:58", "00:21:91", "00:22:b0",
    "00:24:01", "1c:7e:e5", "28:10:7b", "34:08:04", "84:c9:b2", "c8:be:19",
    # Juniper Networks
    "00:10:db", "00:12:1e", "00:19:e2", "2c:21:72", "28:8a:1c", "3c:61:04",
    "40:b4:f0", "54:e0:32", "64:87:88", "78:19:f7",
    # Extreme Networks / Enterasys
    "00:01:30", "00:04:96", "00:0e:02", "00:11:88", "00:13:f7", "00:19:c6",
    # Zyxel Communications
    "00:13:49", "00:19:cb", "00:a0:c5", "28:28:5d", "4c:09:b4", "50:67:f0",
    "58:8b:f3", "ac:59:75",
    # Linksys (Belkin)
    "00:06:25", "00:0c:41", "00:0e:08", "00:12:17", "00:14:bf", "00:16:b6",
    "00:18:39", "00:1a:70", "00:1c:10", "00:1d:7e", "00:21:29", "00:22:6b",
}

_active_db_lock = threading.Lock()
_active_building_name_cache: str | None = None


def _snmp_configuration_state() -> str:
    version = os.getenv("SNMP_VERSION", "2c").strip().lower()
    if version in ("2", "2c", "v2c"):
        return "configured" if os.getenv("SNMP_COMMUNITY", "").strip() else "not_configured"
    if version in ("3", "v3"):
        required = ("SNMP_V3_USER", "SNMP_V3_AUTH_KEY", "SNMP_V3_PRIV_KEY")
        return "configured" if all(os.getenv(name, "").strip() for name in required) else "not_configured"
    return "unsupported_version"


def _snmp_auth_data() -> tuple[Any | None, str]:
    state = _snmp_configuration_state()
    if state != "configured":
        return None, state

    try:
        from pysnmp.hlapi.v3arch.asyncio import (
            CommunityData,
            UsmUserData,
            usmAesCfb128Protocol,
            usmHMACSHAAuthProtocol,
        )
    except ImportError:
        return None, "dependency_missing"

    version = os.getenv("SNMP_VERSION", "2c").strip().lower()
    if version in ("2", "2c", "v2c"):
        return CommunityData(os.environ["SNMP_COMMUNITY"].strip(), mpModel=1), "configured"

    return UsmUserData(
        os.environ["SNMP_V3_USER"].strip(),
        os.environ["SNMP_V3_AUTH_KEY"],
        os.environ["SNMP_V3_PRIV_KEY"],
        authProtocol=usmHMACSHAAuthProtocol,
        privProtocol=usmAesCfb128Protocol,
    ), "configured"


def _empty_snmp_snapshot(status: str, error: str | None = None) -> dict[str, Any]:
    return {
        "status": status,
        "sys_name": None,
        "sys_description": None,
        "sys_object_id": None,
        "uptime_ticks": None,
        "interfaces_total": None,
        "interfaces_up": None,
        "interfaces_down": None,
        "interface_error": None,
        "error": error,
    }


async def _query_switch_snmp(target: str, auth_data: Any) -> dict[str, Any]:
    from pysnmp.hlapi.v3arch.asyncio import (
        ContextData,
        ObjectIdentity,
        ObjectType,
        SnmpEngine,
        UdpTransportTarget,
        get_cmd,
        walk_cmd,
    )

    engine = SnmpEngine()
    try:
        transport = await UdpTransportTarget.create(
            (target, SNMP_PORT),
            timeout=SNMP_TIMEOUT_SECONDS,
            retries=0,
        )
        error, error_status, error_index, values = await get_cmd(
            engine,
            auth_data,
            transport,
            ContextData(),
            ObjectType(ObjectIdentity("1.3.6.1.2.1.1.1.0")),
            ObjectType(ObjectIdentity("1.3.6.1.2.1.1.2.0")),
            ObjectType(ObjectIdentity("1.3.6.1.2.1.1.3.0")),
            ObjectType(ObjectIdentity("1.3.6.1.2.1.1.5.0")),
        )
        if error:
            return _empty_snmp_snapshot("unreachable", str(error))
        if error_status:
            return _empty_snmp_snapshot(
                "error",
                f"{error_status.prettyPrint()} at varbind {error_index}",
            )

        sys_description, sys_object_id, uptime_ticks, sys_name = (
            value.prettyPrint() for _, value in values
        )
        interface_count = 0
        interfaces_up = 0
        interfaces_down = 0
        interface_error = None

        async for error, error_status, error_index, var_binds in walk_cmd(
            engine,
            auth_data,
            transport,
            ContextData(),
            ObjectType(ObjectIdentity("1.3.6.1.2.1.2.2.1.8")),
            lexicographicMode=False,
        ):
            if error:
                interface_error = str(error)
                break
            if error_status:
                interface_error = f"{error_status.prettyPrint()} at varbind {error_index}"
                break
            for _, value in var_binds:
                interface_count += 1
                operational_status = int(value)
                if operational_status == 1:
                    interfaces_up += 1
                elif operational_status == 2:
                    interfaces_down += 1
                if interface_count >= SNMP_MAX_INTERFACES:
                    interface_error = "Interface walk capped at 512 entries"
                    break
            if interface_count >= SNMP_MAX_INTERFACES:
                break

        return {
            "status": "available",
            "sys_name": sys_name,
            "sys_description": sys_description,
            "sys_object_id": sys_object_id,
            "uptime_ticks": int(uptime_ticks),
            "interfaces_total": interface_count,
            "interfaces_up": interfaces_up,
            "interfaces_down": interfaces_down,
            "interface_error": interface_error,
            "error": None,
        }
    finally:
        try:
            engine.close_dispatcher()
        except Exception:
            pass


def _poll_switch_snmp(target: str) -> dict[str, Any]:
    auth_data, state = _snmp_auth_data()
    if auth_data is None:
        return _empty_snmp_snapshot(state)
    try:
        return asyncio.run(_query_switch_snmp(target, auth_data))
    except Exception as error:
        return _empty_snmp_snapshot("error", f"{type(error).__name__}: {error}"[:240])


def _get_database_dir() -> Path:
    """Get the active database directory (shared_database if configured/available, otherwise BASE_DIR)."""
    env_dir = os.environ.get("MONITORING_DB_DIR")
    if env_dir:
        p = Path(env_dir)
        if not p.is_absolute():
            p = (BASE_DIR / p).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p
    shared_dir = (BASE_DIR.parent / "shared_database").resolve()
    if shared_dir.exists():
        return shared_dir
    return BASE_DIR


def _sanitize_building_name(name: str) -> str:
    """Sanitize building name for safe filesystem usage."""
    sanitized = re.sub(r'[\s/\\:*?"<>|]+', '_', name.strip())
    sanitized = sanitized.strip('_')[:60]
    return sanitized or "Unknown_Building"


def _get_active_building_name() -> str:
    """Get the currently selected building name from master settings or cache."""
    global _active_building_name_cache
    if _active_building_name_cache:
        return _active_building_name_cache
    master_db = _get_database_dir() / "monitoring.db"
    if master_db.exists():
        try:
            with sqlite3.connect(master_db, timeout=10) as conn:
                conn.row_factory = sqlite3.Row
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS application_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
                )
                row = conn.execute(
                    "SELECT value FROM application_settings WHERE key = 'active_building_name' LIMIT 1"
                ).fetchone()
                if not row:
                    row = conn.execute(
                        "SELECT value FROM application_settings WHERE key = 'building_name' LIMIT 1"
                    ).fetchone()
                if row and row["value"]:
                    _active_building_name_cache = str(row["value"]).strip()
                    return _active_building_name_cache
        except Exception:
            pass
    return "Unknown Building"


def _get_database_path_for_name(building_name: str) -> Path:
    """Get the database file path for a specific building name."""
    sanitized = _sanitize_building_name(building_name)
    return _get_database_dir() / f"monitoring_{sanitized}.db"


def _get_database_path() -> Path:
    """Get the database path based on the active building name."""
    active_name = _get_active_building_name()
    db_dir = _get_database_dir()
    target_path = _get_database_path_for_name(active_name)
    if target_path.exists():
        return target_path
    if active_name == "Unknown Building":
        unknown_db = db_dir / "monitoring_Unknown_Building.db"
        if unknown_db.exists():
            return unknown_db
        master_db = db_dir / "monitoring.db"
        if master_db.exists():
            return master_db
    return target_path


@property
def DATABASE_PATH():
    return _get_database_path()


DATABASE_PATH = _get_database_path()

_db_lock = threading.Lock()
_reference_poll_lock = threading.Lock()
_worker: threading.Thread | None = None
_stop_event = threading.Event()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    db_path = _get_database_path()
    connection = sqlite3.connect(db_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=30000")
    connection.execute("PRAGMA synchronous=NORMAL")
    return connection


def _initialize_database_file(db_path: Path, building_name: str | None = None) -> None:
    """Initialize schema on a specific database file."""
    with _db_lock, sqlite3.connect(db_path, timeout=10) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT NOT NULL,
                device_name TEXT NOT NULL,
                target TEXT NOT NULL,
                device_type TEXT NOT NULL,
                protocol TEXT NOT NULL,
                online INTEGER NOT NULL,
                latency_ms REAL,
                packet_loss REAL NOT NULL,
                cpu_percent REAL,
                memory_percent REAL,
                bandwidth_percent REAL,
                send_kbps REAL NOT NULL DEFAULT 0,
                receive_kbps REAL NOT NULL DEFAULT 0,
                throughput_kbps REAL NOT NULL DEFAULT 0,
                mib_in_octets REAL,
                mib_out_octets REAL,
                mib_in_errors REAL,
                mib_out_errors REAL,
                mib_in_rate REAL,
                mib_out_rate REAL,
                anomaly_score REAL NOT NULL DEFAULT 0,
                anomaly_label TEXT NOT NULL DEFAULT 'normal',
                error TEXT
            );
            CREATE TABLE IF NOT EXISTS ml_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT NOT NULL,
                device_name TEXT NOT NULL,
                model_version TEXT NOT NULL,
                result TEXT NOT NULL,
                confidence REAL NOT NULL,
                status TEXT NOT NULL,
                composite_risk REAL,
                forecast_horizons TEXT,
                xai_factors TEXT,
                uncertainty REAL
            );
            CREATE TABLE IF NOT EXISTS condition_labels (
                telemetry_id INTEGER PRIMARY KEY,
                label TEXT NOT NULL,
                reviewed_at TEXT NOT NULL,
                FOREIGN KEY (telemetry_id) REFERENCES telemetry(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS recommendation_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telemetry_id INTEGER NOT NULL,
                target TEXT NOT NULL,
                suggestion_id TEXT NOT NULL,
                suggested_action TEXT NOT NULL,
                model_sources TEXT NOT NULL,
                evidence TEXT NOT NULL,
                selected_at TEXT NOT NULL,
                outcome TEXT NOT NULL DEFAULT 'pending',
                verified_finding TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                outcome_at TEXT,
                FOREIGN KEY (telemetry_id) REFERENCES telemetry(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT NOT NULL,
                device_name TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT NOT NULL,
                open INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS monitored_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                target TEXT NOT NULL UNIQUE,
                active INTEGER NOT NULL DEFAULT 0,
                interval_seconds INTEGER NOT NULL DEFAULT 10,
                added_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS switch_telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT NOT NULL,
                monitored_device_id INTEGER NOT NULL,
                target TEXT NOT NULL,
                status TEXT NOT NULL,
                sys_name TEXT,
                sys_description TEXT,
                sys_object_id TEXT,
                uptime_ticks INTEGER,
                interfaces_total INTEGER,
                interfaces_up INTEGER,
                interfaces_down INTEGER,
                interface_error TEXT,
                error TEXT,
                FOREIGN KEY (monitored_device_id) REFERENCES monitored_devices(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS application_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reference_telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT NOT NULL,
                reference_kind TEXT NOT NULL,
                reference_name TEXT NOT NULL,
                target TEXT NOT NULL,
                online INTEGER NOT NULL,
                latency_ms REAL,
                latency_min_ms REAL,
                latency_median_ms REAL,
                latency_max_ms REAL,
                packet_loss REAL NOT NULL,
                ping_sent INTEGER NOT NULL,
                ping_received INTEGER NOT NULL,
                latency_readings TEXT NOT NULL DEFAULT '[]'
            );
            """
        )
        external_reference = os.getenv("EXTERNAL_PING_REFERENCE", "1.1.1.1")
        try:
            external_reference = str(ipaddress.IPv4Address(external_reference))
        except ipaddress.AddressValueError:
            external_reference = "1.1.1.1"
        connection.execute(
            "INSERT OR IGNORE INTO application_settings (key, value) VALUES ('external_reference_ipv4', ?)",
            (external_reference,),
        )
        if building_name:
            connection.execute(
                "INSERT INTO application_settings (key, value) VALUES ('building_name', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (building_name.strip(),),
            )
        columns = {row[1] for row in connection.execute("PRAGMA table_info(telemetry)")}
        for column in ("send_kbps", "receive_kbps", "throughput_kbps", "mib_in_octets", "mib_out_octets", "mib_in_errors", "mib_out_errors", "mib_in_rate", "mib_out_rate", "anomaly_score", "anomaly_label"):
            if column not in columns:
                column_type = "TEXT NOT NULL DEFAULT 'normal'" if column == "anomaly_label" else "REAL NOT NULL DEFAULT 0"
                connection.execute(f"ALTER TABLE telemetry ADD COLUMN {column} {column_type}")
        columns = {row[1] for row in connection.execute("PRAGMA table_info(telemetry)")}
        additions = {
            "latency_min_ms": "REAL",
            "latency_median_ms": "REAL",
            "latency_max_ms": "REAL",
            "ping_sent": "INTEGER NOT NULL DEFAULT 5",
            "ping_received": "INTEGER NOT NULL DEFAULT 0",
            "latency_readings": "TEXT NOT NULL DEFAULT '[]'",
        }
        for column, declaration in additions.items():
            if column not in columns:
                connection.execute(f"ALTER TABLE telemetry ADD COLUMN {column} {declaration}")
        monitored_columns = {row[1] for row in connection.execute("PRAGMA table_info(monitored_devices)")}
        if "mac_address" not in monitored_columns:
            connection.execute("ALTER TABLE monitored_devices ADD COLUMN mac_address TEXT DEFAULT ''")
        if "device_type" not in monitored_columns:
            connection.execute("ALTER TABLE monitored_devices ADD COLUMN device_type TEXT DEFAULT 'pc'")
        ml_columns = {row[1] for row in connection.execute("PRAGMA table_info(ml_records)")}
        for col_name, col_type in (
            ("composite_risk", "REAL"),
            ("forecast_horizons", "TEXT"),
            ("xai_factors", "TEXT"),
            ("uncertainty", "REAL"),
        ):
            if col_name not in ml_columns:
                try:
                    connection.execute(f"ALTER TABLE ml_records ADD COLUMN {col_name} {col_type}")
                except Exception:
                    pass
        connection.commit()


def initialize_database() -> None:
    db_path = _get_database_path()
    building_name = _get_active_building_name()
    _initialize_database_file(db_path, building_name)


def _auto_condition_label(sample: dict[str, Any]) -> str:
    """Suggested condition label for Human-in-the-Loop review (5-probe burst & jitter aware)."""
    if not bool(sample.get("online")):
        return "Unreachable"
    latency = float(sample.get("latency_median_ms") or sample.get("latency_ms") or 0.0)
    loss = float(sample.get("packet_loss") or 0.0)
    if latency > 150.0:
        return "High Latency"
    if loss > 0.0:
        return "Packet Loss"
    return "Normal"


def _ping(target: str, count: int = 5, timeout_ms: int = 1000) -> dict[str, Any]:
    """Step 1: 5-Probe ICMP Burst Collection (Min/Median/Max RTT, Jitter & Packet Loss)."""
    probe_count = max(1, min(count, 5))
    wait_ms = str(max(200, int(timeout_ms)))
    wait_sec = str(max(1, round(int(timeout_ms) / 1000)))
    command = (
        ["ping", "-n", str(probe_count), "-w", wait_ms, target]
        if platform.system() == "Windows"
        else ["ping", "-c", str(probe_count), "-W", wait_sec, target]
    )
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=max(1.5, probe_count * (int(timeout_ms) / 1000.0) + 1.5),
            check=False,
        )
        output = f"{result.stdout}\n{result.stderr}"
        readings = []
        for match in re.finditer(r"time(?P<operator>[=<])\s*(?P<value>\d+(?:\.\d+)?)\s*ms", output, re.IGNORECASE):
            value = float(match.group("value"))
            readings.append({"display": f"<{match.group('value')}" if match.group("operator") == "<" else match.group("value"), "upper_bound_ms": value})
        values = [reading["upper_bound_ms"] for reading in readings]
        received = len(readings)
        online = received > 0 or result.returncode == 0
        median = statistics.median(values) if values else None
        ordered_readings = sorted(readings, key=lambda reading: reading["upper_bound_ms"])
        median_reading = ordered_readings[len(ordered_readings) // 2] if ordered_readings else None
        median_display = (
            f"<{median_reading['upper_bound_ms']:g} ms"
            if received == probe_count and median_reading and median_reading["display"].startswith("<")
            else f"{median:g} ms"
            if median is not None
            else "-"
        )
        return {
            "online": online,
            "latency_ms": median,
            "latency_min_ms": min(values) if values else None,
            "latency_median_ms": median,
            "latency_max_ms": max(values) if values else None,
            "latency_min_display": f"<{min(values):g} ms" if any(reading["display"].startswith("<") and reading["upper_bound_ms"] == min(values) for reading in readings) else f"{min(values):g} ms" if values else "-",
            "latency_median_display": median_display,
            "latency_max_display": f"<{max(values):g} ms" if values and all(reading["display"].startswith("<") for reading in readings) else f"{max(values):g} ms" if values else "-",
            "ping_sent": probe_count,
            "ping_received": received,
            "packet_loss": round((probe_count - received) * 100 / probe_count, 1),
            "latency_readings": json.dumps([reading["display"] for reading in readings]),
            "error": None if online else "No ping response",
        }
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"online": False, "latency_ms": None, "latency_min_ms": None, "latency_median_ms": None, "latency_max_ms": None, "latency_min_display": "-", "latency_median_display": "-", "latency_max_display": "-", "ping_sent": probe_count, "ping_received": 0, "packet_loss": 100.0, "latency_readings": "[]", "error": str(error)}


def _collect_device(device: dict[str, Any]) -> dict[str, Any]:
    target = str(device.get("target", ""))
    result = _ping(target, count=5, timeout_ms=1000)
    dev_type = str(device.get("device_type") or "pc").upper()
    result.update({
        "recorded_at": _utc_now(),
        "device_name": device.get("name", target),
        "target": target,
        "device_type": dev_type,
        "protocol": "icmp",
        "packet_loss": result["packet_loss"],
    })
    return result


def _classify(sample: dict[str, Any]) -> tuple[str, float, str]:
    if not sample["online"]:
        return "Device unreachable", 0.99, "Flagged"
    score = 0.0
    reasons = []
    if sample.get("latency_ms") and sample["latency_ms"] > 150:
        score += 0.8
        reasons.append("high latency")
    if sample.get("packet_loss", 0) > 0:
        score += 0.8
        reasons.append("packet loss")
    if score >= 0.6:
        return "Ping anomaly: " + ", ".join(reasons), min(0.99, round(score, 2)), "Flagged"
    return "Normal ping", 0.96, "Normal"


def get_local_network() -> dict[str, str]:
    candidates = []
    for interface, addresses in psutil.net_if_addrs().items():
        stats = psutil.net_if_stats().get(interface)
        if not stats or not stats.isup:
            continue
        lowered = interface.lower()
        if any(token in lowered for token in ("vethernet", "hyper-v", "virtual", "docker", "wsl", "vmware", "vbox", "loopback")):
            continue
        for address in addresses:
            if address.family.name != "AF_INET" or address.address.startswith("127.") or not address.netmask:
                continue
            network = ipaddress.ip_network(f"{address.address}/{address.netmask}", strict=False)
            is_wifi = any(token in lowered for token in ("wi-fi", "wifi", "wireless", "wlan"))
            is_ethernet = any(token in lowered for token in ("ethernet", "eth", "lan"))
            is_vpn = "vpn" in lowered
            is_tunnel = "tunnel" in lowered
            is_radmin = "radmin" in lowered
            if is_wifi:
                rank = 0
            elif is_ethernet:
                rank = 1
            elif is_vpn:
                rank = 2
            elif is_tunnel:
                rank = 3
            elif is_radmin:
                rank = 4
            else:
                rank = 5
            suggested = network if network.num_addresses <= 256 else ipaddress.ip_network(f"{address.address}/24", strict=False)
            candidates.append((rank, interface, address.address, network, suggested))
    if not candidates:
        raise ValueError("Could not determine an active local IPv4 subnet")
    _, interface, address, network, suggested = sorted(candidates)[0]
    return {"interface": interface, "address": address, "subnet": str(network), "suggested_subnet": str(suggested), "virtual": "false"}


def _get_mac_address(target: str) -> str:
    """Get MAC address for a given IP address using ARP cache."""
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["arp", "-a", target],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            match = re.search(r"([0-9a-f]{2}(?:-[0-9a-f]{2}){5})", result.stdout, re.IGNORECASE)
            if match:
                return match.group(1).lower()
        else:
            result = subprocess.run(
                ["arp", "-n", target],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            match = re.search(r"([0-9a-f]{2}(?::[0-9a-f]{2}){5})", result.stdout, re.IGNORECASE)
            if match:
                return match.group(1).lower()
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def _probe_switch_ports(target: str, timeout: float = 0.4) -> bool:
    """Return True if the target looks like a managed switch based on open TCP ports."""
    cli_ports = (22, 23)
    web_ports = (80, 443)

    def _is_open(port: int) -> bool:
        try:
            with socket.create_connection((target, port), timeout=timeout):
                return True
        except OSError:
            return False

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {port: executor.submit(_is_open, port) for port in (*cli_ports, *web_ports)}
        results = {port: future.result() for port, future in futures.items()}

    has_cli = any(results[p] for p in cli_ports)
    has_web = any(results[p] for p in web_ports)
    return has_cli and has_web


def _detect_device_type(mac_address: str, target: str = "") -> str:
    """Detect device type using MAC OUI lookup and TCP port fingerprinting."""
    if mac_address:
        mac_normalized = mac_address.lower().replace("-", ":")
        oui = ":".join(mac_normalized.split(":")[:3]) if len(mac_normalized.split(":")) >= 3 else ""
        if oui in PHONE_MANUFACTURERS:
            return "phone"
        if oui in SWITCH_MANUFACTURERS:
            return "switch"

    if target:
        try:
            if _probe_switch_ports(target):
                return "switch"
        except Exception:
            pass

    return "pc" if mac_address else "unknown"


def _resolve_hostname(target: str) -> str:
    """Resolve hostname from IP address using reverse DNS or NetBIOS."""
    try:
        hostname, _, _ = socket.gethostbyaddr(target)
        if hostname and hostname != target:
            return hostname.split('.')[0]
    except (socket.herror, socket.timeout, OSError):
        pass

    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["nbtstat", "-A", target],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            for line in result.stdout.split('\n'):
                if '<20>' in line or '<00>' in line:
                    parts = line.split()
                    if parts:
                        name = parts[0].strip()
                        if name and name != target:
                            return name
        except (OSError, subprocess.TimeoutExpired):
            pass

    return target


def _get_default_gateway(local_address: str, interface: str) -> str | None:
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["route.exe", "print", "-4"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            routes = re.findall(
                r"^\s*0\.0\.0\.0\s+0\.0\.0\.0\s+(\S+)\s+(\d{1,3}(?:\.\d{1,3}){3})\s+\d+\s*$",
                result.stdout,
                re.MULTILINE,
            )
            for gateway, route_interface in routes:
                if route_interface == local_address:
                    try:
                        return str(ipaddress.IPv4Address(gateway))
                    except ipaddress.AddressValueError:
                        continue
            candidate = []
        else:
            result = subprocess.run(
                ["ip", "-4", "route", "show", "default", "dev", interface],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            candidate = re.findall(r"\bvia\s+(\d{1,3}(?:\.\d{1,3}){3})\b", result.stdout)
        for value in candidate:
            try:
                return str(ipaddress.IPv4Address(value))
            except ipaddress.AddressValueError:
                continue
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return None


def get_external_reference_target() -> str:
    initialize_database()
    with _db_lock, _connect() as connection:
        row = connection.execute(
            "SELECT value FROM application_settings WHERE key = 'external_reference_ipv4'"
        ).fetchone()
    return str(row["value"]) if row else "1.1.1.1"


def save_external_reference_target(target: str) -> str:
    try:
        address = str(ipaddress.IPv4Address(target.strip()))
    except (AttributeError, ipaddress.AddressValueError) as error:
        raise ValueError("Enter a valid external IPv4 reference address") from error
    initialize_database()
    with _db_lock, _connect() as connection:
        connection.execute(
            "INSERT INTO application_settings (key, value) VALUES ('external_reference_ipv4', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (address,),
        )
    return address


def get_network_reference_targets() -> list[dict[str, str]]:
    external_target = get_external_reference_target()
    try:
        local = get_local_network()
        gateway_target = _get_default_gateway(local["address"], local["interface"])
    except (KeyError, ValueError):
        gateway_target = None
    targets = []
    if gateway_target:
        targets.append({"kind": "gateway", "name": "Local gateway", "target": gateway_target})
    if external_target != gateway_target:
        targets.append({"kind": "external", "name": "External reference", "target": external_target})
    return targets


def _poll_network_references() -> list[dict[str, Any]]:
    if not _reference_poll_lock.acquire(blocking=False):
        return []
    try:
        targets = get_network_reference_targets()
        if not targets:
            return []
        try:
            with ThreadPoolExecutor(max_workers=max(1, len(targets))) as executor:
                results = list(executor.map(lambda target: (target, _ping(target["target"], count=5, timeout_ms=1000)), targets))
        except RuntimeError:
            return []
        recorded_at = _utc_now()
        with _db_lock, _connect() as connection:
            for target, result in results:
                result.update(target)
                result["recorded_at"] = recorded_at
                connection.execute(
                    """
                    INSERT INTO reference_telemetry
                        (recorded_at, reference_kind, reference_name, target, online, latency_ms,
                         latency_min_ms, latency_median_ms, latency_max_ms, packet_loss,
                         ping_sent, ping_received, latency_readings)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        recorded_at,
                        target["kind"],
                        target["name"],
                        target["target"],
                        int(result["online"]),
                        result["latency_ms"],
                        result["latency_min_ms"],
                        result["latency_median_ms"],
                        result["latency_max_ms"],
                        result["packet_loss"],
                        result["ping_sent"],
                        result["ping_received"],
                        result["latency_readings"],
                    ),
                )
        return [{**target, **result, "recorded_at": recorded_at} for target, result in results]
    finally:
        _reference_poll_lock.release()


def poll_network_references() -> list[dict[str, Any]]:
    return _poll_network_references()


def _rolling_ping_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    recent = rows[-5:]
    if not recent:
        return {"sample_count": 0, "online": None, "packet_loss_percent": None, "latency_median_ms": None, "latency_variation_ms": None}
    sent = sum(int(row.get("ping_sent") or 0) for row in recent)
    received = sum(int(row.get("ping_received") or 0) for row in recent)
    latencies = [
        float(row.get("latency_median_ms") or row.get("latency_ms"))
        for row in recent
        if row.get("latency_median_ms") is not None or row.get("latency_ms") is not None
    ]
    changes = [abs(later - earlier) for earlier, later in zip(latencies, latencies[1:])]
    return {
        "sample_count": len(recent),
        "online": bool(recent[-1].get("online")),
        "packet_loss_percent": round((sent - received) * 100 / sent, 1) if sent else None,
        "latency_median_ms": round(statistics.median(latencies), 2) if latencies else None,
        "latency_variation_ms": round(statistics.median(changes), 2) if changes else None,
        "latest_recorded_at": recent[-1].get("recorded_at"),
    }


def get_network_reference_status() -> dict[str, Any]:
    targets = get_network_reference_targets()
    with _db_lock, _connect() as connection:
        reference_rows = connection.execute(
            "SELECT * FROM reference_telemetry ORDER BY id DESC LIMIT 200"
        ).fetchall()
        pc_rows = connection.execute(
            """
            SELECT * FROM telemetry WHERE protocol = 'icmp' AND device_type = 'PC'
            ORDER BY id DESC LIMIT 2000
            """
        ).fetchall()
    references_by_target: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in reversed(reference_rows):
        references_by_target[str(row["target"])].append(_row_dict(row))
    reference_summaries = []
    for target in targets:
        rows = references_by_target.get(target["target"], [])
        summary = _rolling_ping_summary(rows)
        reference_summaries.append({**target, **summary})
    gateway = next((item for item in reference_summaries if item["kind"] == "gateway"), None)
    external = next((item for item in reference_summaries if item["kind"] == "external"), None)

    devices_by_target: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in reversed(pc_rows):
        sample = _row_dict(row)
        if (sample["online"] and sample["ping_received"] > 0 and (sample["latency_median_ms"] is not None or sample["latency_ms"] is not None)) or (not sample["online"] and sample["ping_received"] == 0):
            devices_by_target[str(sample["target"])].append(sample)
    devices = []
    for target, rows in devices_by_target.items():
        summary = _rolling_ping_summary(rows)
        if gateway is None or gateway["sample_count"] == 0:
            comparison = "Gateway comparison unavailable; continue using the PC's own rolling ping results."
        elif not gateway["online"]:
            comparison = "Gateway did not reply; local-path degradation is possible, but ICMP filtering may also explain it."
        elif external is not None and external["sample_count"] and not external["online"]:
            comparison = "Gateway replies but the external reference does not; upstream path issues or external ICMP filtering are possible."
        elif not summary["online"] and gateway["online"]:
            comparison = "Gateway replies while this PC does not; check the endpoint, its connection, or its ICMP policy."
        elif summary["packet_loss_percent"] is not None and summary["packet_loss_percent"] > 0:
            comparison = "PC packet loss is present; compare its rolling loss and latency variation with the gateway and other PCs."
        else:
            comparison = "PC and gateway are responding; no clear shared-path issue is visible in these samples."
        devices.append({"target": target, **summary, "comparison": comparison})
    return {
        "gateway": gateway,
        "external": external,
        "external_reference_target": get_external_reference_target(),
        "devices": devices,
        "window_samples": 5,
        "probes_per_sample": 5,
        "note": "ICMP comparisons are indicators only; filtering and endpoint policies can affect replies.",
    }


def get_network_reference_samples(limit: int = 2000) -> list[dict[str, Any]]:
    initialize_database()
    with _db_lock, _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM reference_telemetry ORDER BY id DESC LIMIT ?",
            (max(1, min(int(limit), 10000)),),
        ).fetchall()
    return [_row_dict(row) for row in reversed(rows)]


def discover_hosts(subnet: str, limit: int = 0) -> list[dict[str, str]]:
    local_network = ipaddress.ip_network(get_local_network()["subnet"], strict=False)
    requested_network = ipaddress.ip_network(subnet, strict=False)
    if requested_network.version != 4 or not requested_network.subnet_of(local_network):
        raise ValueError("Discovery is limited to an IPv4 subnet within the active local network")
    if requested_network.num_addresses > 256:
        raise ValueError("Choose a subnet with no more than 256 addresses")
    candidates = [str(address) for address in requested_network.hosts()]
    found = []
    limit_val = max(1, min(int(limit), 999)) if limit > 0 else len(candidates)
    with ThreadPoolExecutor(max_workers=128) as executor:
        tasks = {executor.submit(_ping, target, 1, 400): target for target in candidates}
        for task in as_completed(tasks):
            if len(found) >= limit_val:
                break
            target = tasks[task]
            try:
                result = task.result()
            except Exception:
                continue
            if result["online"]:
                mac_addr = _get_mac_address(target)
                device_type = _detect_device_type(mac_addr, target)
                found.append({"name": target, "target": target, "mac_address": mac_addr, "device_type": device_type})
    return sorted(found, key=lambda item: ipaddress.ip_address(item["target"]))


def get_monitored_devices() -> list[dict[str, Any]]:
    initialize_database()
    with _db_lock, _connect() as connection:
        rows = connection.execute("SELECT * FROM monitored_devices ORDER BY name COLLATE NOCASE").fetchall()
        switch_rows = connection.execute(
            """
            SELECT snapshot.*
            FROM switch_telemetry AS snapshot
            JOIN (
                SELECT monitored_device_id, MAX(id) AS latest_id
                FROM switch_telemetry
                GROUP BY monitored_device_id
            ) AS latest ON latest.latest_id = snapshot.id
            """
        ).fetchall()
    latest_switch_data = {int(row["monitored_device_id"]): _row_dict(row) for row in switch_rows}
    snmp_configured = _snmp_configuration_state() == "configured"
    devices = [_row_dict(row) for row in rows]
    for device in devices:
        if device.get("device_type") == "switch":
            device["snmp"] = latest_switch_data.get(
                int(device["id"]),
                {"status": "waiting" if snmp_configured else _snmp_configuration_state()},
            )
        else:
            device["snmp"] = None
    return devices


def add_monitored_device(name: str, target: str, device_type: str | None = None) -> dict[str, Any]:
    initialize_database()
    address = ipaddress.ip_address(target)
    mac_addr = _get_mac_address(str(address))
    if not device_type or device_type == "auto":
        resolved_device_type = _detect_device_type(mac_addr, str(address))
    else:
        resolved_device_type = str(device_type).strip().lower()
    if resolved_device_type not in ("pc", "phone", "switch"):
        resolved_device_type = "pc"

    clean_name = name.strip()[:100] if name.strip() else ""
    if not clean_name or clean_name == str(address):
        resolved_name = _resolve_hostname(str(address))
        if resolved_name and resolved_name != str(address):
            clean_name = resolved_name
        else:
            clean_name = str(address)

    with _db_lock, _connect() as connection:
        connection.execute(
            "INSERT INTO monitored_devices (name, target, active, interval_seconds, added_at, mac_address, device_type) VALUES (?, ?, 0, ?, ?, ?, ?) ON CONFLICT(target) DO UPDATE SET name = excluded.name, mac_address = excluded.mac_address, device_type = excluded.device_type",
            (clean_name, str(address), POLL_INTERVAL_SECONDS, _utc_now(), mac_addr, resolved_device_type),
        )
        row = connection.execute("SELECT * FROM monitored_devices WHERE target = ?", (str(address),)).fetchone()
    return _row_dict(row)


def update_monitored_device(device_id: int, *, active: bool | None = None, interval_seconds: int | None = None, device_type: str | None = None) -> bool:
    initialize_database()
    with _db_lock, _connect() as connection:
        if active is not None:
            connection.execute("UPDATE monitored_devices SET active = ? WHERE id = ?", (int(active), device_id))
        if interval_seconds is not None:
            interval = max(5, min(int(interval_seconds), 3600))
            connection.execute("UPDATE monitored_devices SET interval_seconds = ? WHERE id = ?", (interval, device_id))
        if device_type is not None:
            device_type_normalized = str(device_type).lower().strip()
            if device_type_normalized not in ("pc", "phone", "switch"):
                device_type_normalized = "pc"
            connection.execute("UPDATE monitored_devices SET device_type = ? WHERE id = ?", (device_type_normalized, device_id))
        return connection.execute("SELECT changes()").fetchone()[0] > 0


def reclassify_monitored_devices() -> list[dict[str, Any]]:
    """Re-run MAC OUI and TCP port detection for all saved monitored devices."""
    initialize_database()
    devices = get_monitored_devices()
    updated = []
    for device in devices:
        target = str(device.get("target", ""))
        mac_addr = device.get("mac_address") or _get_mac_address(target)
        new_type = _detect_device_type(mac_addr, target)
        if new_type == "unknown":
            new_type = device.get("device_type") or "pc"
        with _db_lock, _connect() as connection:
            connection.execute(
                "UPDATE monitored_devices SET mac_address = ?, device_type = ? WHERE id = ?",
                (mac_addr, new_type, int(device["id"])),
            )
        updated.append({"id": int(device["id"]), "target": target, "device_type": new_type, "mac_address": mac_addr})
    return updated


def remove_monitored_device(device_id: int) -> bool:
    initialize_database()
    with _db_lock, _connect() as connection:
        connection.execute("DELETE FROM switch_telemetry WHERE monitored_device_id = ?", (device_id,))
        connection.execute("DELETE FROM monitored_devices WHERE id = ?", (device_id,))
        return connection.execute("SELECT changes()").fetchone()[0] > 0


def _poll_devices(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    with ThreadPoolExecutor(max_workers=min(32, max(1, len(devices)))) as executor:
        samples = list(executor.map(_collect_device, devices))
    switch_devices = [device for device in devices if device.get("device_type") == "switch"]
    switch_snapshots: dict[int, dict[str, Any]] = {}
    if switch_devices:
        with ThreadPoolExecutor(max_workers=min(8, len(switch_devices))) as executor:
            futures = {
                int(device["id"]): executor.submit(_poll_switch_snmp, str(device["target"]))
                for device in switch_devices
            }
            switch_snapshots = {device_id: future.result() for device_id, future in futures.items()}
    with _db_lock, _connect() as connection:
        for sample in samples:
            result, confidence, status = _classify(sample)
            anomaly_score = 1.0 if status == "Flagged" else 0.0
            auto_label = _auto_condition_label(sample)
            sample.update({
                "anomaly_label": result,
                "anomaly_score": anomaly_score,
                "status": status,
                "condition_label": auto_label,
            })
            cursor = connection.execute(
                "INSERT INTO telemetry (recorded_at, device_name, target, device_type, protocol, online, latency_ms, packet_loss, latency_min_ms, latency_median_ms, latency_max_ms, ping_sent, ping_received, latency_readings, anomaly_score, anomaly_label, error) VALUES (?, ?, ?, ?, 'icmp', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (sample["recorded_at"], sample["device_name"], sample["target"], sample.get("device_type", "PC"), int(sample["online"]), sample["latency_ms"], sample["packet_loss"], sample["latency_min_ms"], sample["latency_median_ms"], sample["latency_max_ms"], sample["ping_sent"], sample["ping_received"], sample["latency_readings"], anomaly_score, result, sample["error"]),
            )
            telemetry_id = int(cursor.lastrowid)
            # Step 3: Rule-Based Auto Labeling (Rigid >150ms Threshold)
            connection.execute(
                """
                INSERT INTO condition_labels (telemetry_id, label, reviewed_at)
                VALUES (?, ?, ?)
                ON CONFLICT(telemetry_id) DO UPDATE SET
                    label = excluded.label,
                    reviewed_at = excluded.reviewed_at
                """,
                (telemetry_id, auto_label, sample["recorded_at"]),
            )
            connection.execute(
                "INSERT INTO ml_records (recorded_at, device_name, model_version, result, confidence, status) VALUES (?, ?, 'icmp-ping-v1', ?, ?, ?)",
                (sample["recorded_at"], sample["device_name"], result, confidence, status),
            )
            if status == "Flagged":
                connection.execute(
                    "INSERT INTO alerts (recorded_at, device_name, message, severity) VALUES (?, ?, ?, ?)",
                    (sample["recorded_at"], sample["device_name"], result, "high" if not sample["online"] else "medium"),
                )
        for device in switch_devices:
            device_id = int(device["id"])
            snapshot = switch_snapshots.get(device_id)
            if not snapshot:
                continue
            connection.execute(
                """
                INSERT INTO switch_telemetry
                    (recorded_at, monitored_device_id, target, status, sys_name, sys_description,
                     sys_object_id, uptime_ticks, interfaces_total, interfaces_up, interfaces_down,
                     interface_error, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _utc_now(),
                    device_id,
                    str(device["target"]),
                    snapshot["status"],
                    snapshot["sys_name"],
                    snapshot["sys_description"],
                    snapshot["sys_object_id"],
                    snapshot["uptime_ticks"],
                    snapshot["interfaces_total"],
                    snapshot["interfaces_up"],
                    snapshot["interfaces_down"],
                    snapshot["interface_error"],
                    snapshot["error"],
                ),
            )
    return samples


def poll_once() -> list[dict[str, Any]]:
    initialize_database()
    devices = [device for device in get_monitored_devices() if device["active"]]
    return _poll_devices(devices)


def _poll_loop() -> None:
    last_poll: dict[int, float] = {}
    last_reference_poll = 0.0
    reference_worker: threading.Thread | None = None
    while not _stop_event.is_set():
        try:
            now = time.monotonic()
            if now - last_reference_poll >= POLL_INTERVAL_SECONDS and (
                reference_worker is None or not reference_worker.is_alive()
            ):
                last_reference_poll = now
                reference_worker = threading.Thread(
                    target=_poll_network_references,
                    name="network-reference-monitor",
                    daemon=True,
                )
                reference_worker.start()
            due = []
            for device in get_monitored_devices():
                if not device["active"]:
                    last_poll.pop(device["id"], None)
                    continue
                if now - last_poll.get(device["id"], 0) >= device["interval_seconds"]:
                    due.append(device)
                    last_poll[device["id"]] = now
            if due:
                _poll_devices(due)
        except Exception:
            pass
        _stop_event.wait(0.5)


def start_monitoring() -> None:
    global _worker
    initialize_database()
    if _worker and _worker.is_alive():
        return
    _stop_event.clear()
    _worker = threading.Thread(target=_poll_loop, name="network-monitor", daemon=True)
    _worker.start()


def stop_monitoring() -> None:
    _stop_event.set()


def _row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def _latency_display(sample: dict[str, Any], statistic: str) -> str:
    readings = json.loads(sample.get("latency_readings") or "[]")
    sub_ms_count = sum(str(reading).startswith("<") for reading in readings)
    value = sample.get(f"latency_{statistic}_ms")
    if value is None and statistic == "median":
        value = sample.get("latency_ms")
    if value is None:
        return "-"
    sent = int(sample.get("ping_sent") or 1)
    if statistic == "min" and sub_ms_count and value <= 1:
        return "<1 ms"
    if statistic == "median" and ((sent == 1 and sub_ms_count >= 1) or (sent == 5 and sub_ms_count >= 3)) and value <= 1:
        return "<1 ms"
    if statistic == "max" and readings and sub_ms_count == len(readings) and value <= 1:
        return "<1 ms"
    return f"{value:g} ms"


def get_monitoring_data() -> dict[str, Any]:
    initialize_database()
    with _db_lock, _connect() as connection:
        telemetry = [
            _row_dict(row)
            for row in connection.execute(
                """
                SELECT * FROM telemetry
                WHERE protocol = 'icmp'
                  AND ((online = 1 AND ping_received > 0
                        AND COALESCE(latency_median_ms, latency_ms) IS NOT NULL)
                       OR (online = 0 AND ping_received = 0))
                ORDER BY id DESC LIMIT 100
                """
            )
        ]
        ml_records = [_row_dict(row) for row in connection.execute("SELECT * FROM ml_records WHERE model_version = 'icmp-ping-v1' ORDER BY id DESC LIMIT 50")]
        alerts = [_row_dict(row) for row in connection.execute("SELECT alerts.* FROM alerts WHERE open = 1 AND EXISTS (SELECT 1 FROM ml_records WHERE ml_records.recorded_at = alerts.recorded_at AND ml_records.device_name = alerts.device_name AND ml_records.model_version = 'icmp-ping-v1') ORDER BY alerts.id DESC LIMIT 20")]
    for sample in telemetry:
        sample["latency_min_display"] = _latency_display(sample, "min")
        sample["latency_median_display"] = _latency_display(sample, "median")
        sample["latency_max_display"] = _latency_display(sample, "max")
    return {"devices": get_monitored_devices(), "telemetry": telemetry, "ml_records": ml_records, "alerts": alerts}


def auto_apply_rule_labels(overwrite: bool = False) -> dict[str, int]:
    """Step 3: Apply Rule-Based Auto Labeling (Rigid >150ms Threshold) to telemetry samples."""
    initialize_database()
    counts: dict[str, int] = defaultdict(int)
    now = _utc_now()
    with _db_lock, _connect() as connection:
        rows = connection.execute(
            """
            SELECT telemetry.id, telemetry.online, telemetry.latency_median_ms,
                   telemetry.latency_ms, telemetry.packet_loss,
                   condition_labels.label AS existing_label
            FROM telemetry
            LEFT JOIN condition_labels ON condition_labels.telemetry_id = telemetry.id
            WHERE telemetry.protocol IN ('icmp', 'icmp_online')
              AND ((telemetry.online = 1 AND telemetry.ping_received > 0
                    AND COALESCE(telemetry.latency_median_ms, telemetry.latency_ms) IS NOT NULL)
                   OR (telemetry.online = 0 AND telemetry.ping_received = 0))
            """
        ).fetchall()
        updates = []
        for row in rows:
            sample = _row_dict(row)
            label = _auto_condition_label(sample)
            if overwrite or not sample.get("existing_label"):
                updates.append((int(sample["id"]), label, now))
                counts[label] += 1
            else:
                counts[str(sample["existing_label"])] += 1
        if updates:
            connection.executemany(
                """
                INSERT INTO condition_labels (telemetry_id, label, reviewed_at)
                VALUES (?, ?, ?)
                ON CONFLICT(telemetry_id) DO UPDATE SET
                    label = excluded.label,
                    reviewed_at = excluded.reviewed_at
                """,
                updates,
            )
            connection.commit()
    return dict(counts)


def import_online_training_dataset(csv_source: str | None = None) -> dict[str, Any]:
    """Import 5-probe burst online benchmark data (all 4 conditions) + live internet probes for SYSTEM 2 ML training."""
    import csv
    import io
    import random
    import urllib.request
    from datetime import timedelta

    initialize_database()
    live_probes: list[dict[str, Any]] = []
    online_targets = [
        ("Cloudflare DNS", "1.1.1.1"),
        ("Google Public DNS", "8.8.8.8"),
        ("Quad9 Security DNS", "9.9.9.9"),
        ("OpenDNS Resolver", "208.67.222.222"),
    ]
    for name, target in online_targets:
        try:
            probe = _ping(target, 5, 1000)
            live_probes.append(
                {
                    "name": name,
                    "target": target,
                    "online": probe["online"],
                    "latency_min_ms": probe["latency_min_ms"],
                    "latency_ms": probe["latency_median_ms"],
                    "latency_max_ms": probe["latency_max_ms"],
                    "packet_loss": probe["packet_loss"],
                }
            )
        except Exception:
            continue

    base_rtt = 18.0
    online_rtts = [float(p["latency_ms"]) for p in live_probes if p.get("online") and p.get("latency_ms") is not None]
    if online_rtts:
        base_rtt = max(5.0, min(80.0, statistics.median(online_rtts)))

    records_to_insert: list[tuple[Any, ...]] = []
    start_time = datetime.now(timezone.utc) - timedelta(hours=6)

    if csv_source:
        if csv_source.startswith(("http://", "https://")):
            with urllib.request.urlopen(csv_source, timeout=15) as response:
                content = response.read().decode("utf-8", errors="replace")
        else:
            content = Path(csv_source).read_text(encoding="utf-8")
        reader = csv.DictReader(io.StringIO(content))
        for idx, row in enumerate(reader):
            online = str(row.get("online", "1")).strip().lower() in ("1", "true", "yes")
            sent = max(1, int(float(row.get("ping_sent") or 5)))
            received = int(float(row.get("ping_received") or (sent if online else 0)))
            loss = float(row.get("packet_loss") or (0.0 if online else 100.0))
            lat_med = float(row.get("latency_median_ms") or row.get("latency_ms") or 20.0) if online else None
            lat_min = float(row.get("latency_min_ms") or (lat_med * 0.85 if lat_med is not None else 0.0)) if online else None
            lat_max = float(row.get("latency_max_ms") or (lat_med * 1.15 if lat_med is not None else 0.0)) if online else None
            rec_at = row.get("recorded_at") or (start_time + timedelta(seconds=idx * 30)).isoformat(timespec="seconds")
            dev_name = row.get("device_name") or f"Online-Host-{idx % 4 + 1}"
            target = row.get("target") or f"198.51.100.{idx % 4 + 1}"
            sample_dict = {
                "online": online,
                "latency_ms": lat_med,
                "latency_min_ms": lat_min,
                "latency_median_ms": lat_med,
                "latency_max_ms": lat_max,
                "packet_loss": loss,
            }
            label = row.get("reviewed_condition_label") or row.get("label") or _auto_condition_label(sample_dict)
            if label not in ("Normal", "High Latency", "Packet Loss", "Unreachable"):
                label = _auto_condition_label(sample_dict)
            records_to_insert.append(
                (rec_at, dev_name, target, int(online), lat_min, lat_med, lat_max, loss, sent, received, label)
            )
    else:
        rng = random.Random(42)
        profiles = [
            ("Online-Edge-1 (Cloudflare)", "1.1.1.1"),
            ("Online-Edge-2 (Google)", "8.8.8.8"),
            ("Online-Edge-3 (Quad9)", "9.9.9.9"),
            ("Online-Edge-4 (OpenDNS)", "208.67.222.222"),
        ]
        # Build 80 chronological 5-probe burst steps per endpoint (320 samples covering all 4 conditions)
        for step in range(80):
            rec_at = (start_time + timedelta(seconds=step * 30)).isoformat(timespec="seconds")
            for p_idx, (dev_name, target) in enumerate(profiles):
                phase = (step + p_idx * 20) % 80
                sent = 5
                if phase < 32:
                    # Normal (5/5 replies, low RTT & low jitter <= 6ms)
                    online = 1
                    received = 5
                    loss = 0.0
                    lat_med = round(max(1.0, min(120.0, base_rtt + rng.uniform(-3.0, 22.0))), 2)
                    jitter_half = round(rng.uniform(0.4, 2.8), 2)
                    lat_min = round(max(0.5, lat_med - jitter_half), 2)
                    lat_max = round(lat_med + jitter_half, 2)
                    label = "Normal"
                elif phase < 50:
                    # High Latency (5/5 replies, elevated RTT >150ms + high burst jitter 18-65ms)
                    online = 1
                    received = 5
                    loss = 0.0
                    ramp = (phase - 32) * 8.5
                    lat_med = round(min(420.0, 160.0 + ramp + rng.uniform(-10.0, 35.0)), 2)
                    lat_min = round(max(135.0, lat_med - rng.uniform(10.0, 28.0)), 2)
                    lat_max = round(lat_med + rng.uniform(15.0, 48.0), 2)
                    label = "High Latency"
                elif phase < 66:
                    # Packet Loss (1-4 of 5 replies received -> 20% to 80% loss, moderate RTT + burst jitter)
                    online = 1
                    received = rng.choice([1, 2, 3, 4])
                    loss = round((sent - received) * 100.0 / sent, 1)
                    lat_med = round(rng.uniform(35.0, 140.0), 2)
                    lat_min = round(max(10.0, lat_med - rng.uniform(5.0, 18.0)), 2)
                    lat_max = round(lat_med + rng.uniform(8.0, 25.0), 2)
                    label = "Packet Loss"
                else:
                    # Unreachable (0/5 replies, 100% loss, consecutive failure streak)
                    online = 0
                    received = 0
                    loss = 100.0
                    lat_min, lat_med, lat_max = None, None, None
                    label = "Unreachable"
                records_to_insert.append(
                    (rec_at, dev_name, target, online, lat_min, lat_med, lat_max, loss, sent, received, label)
                )

    inserted_counts: dict[str, int] = defaultdict(int)
    now = _utc_now()
    with _db_lock, _connect() as connection:
        old_ids = [
            int(r["id"])
            for r in connection.execute("SELECT id FROM telemetry WHERE protocol = 'icmp_online'").fetchall()
        ]
        if old_ids:
            connection.execute("DELETE FROM condition_labels WHERE telemetry_id IN (SELECT id FROM telemetry WHERE protocol = 'icmp_online')")
            connection.execute("DELETE FROM telemetry WHERE protocol = 'icmp_online'")
        for rec_at, dev_name, target, online, lat_min, lat_med, lat_max, loss, sent, received, label in records_to_insert:
            readings = json.dumps([lat_min, lat_med, lat_med, lat_med, lat_max][:received] if lat_med is not None else [])
            cursor = connection.execute(
                """
                INSERT INTO telemetry (
                    recorded_at, device_name, target, device_type, protocol,
                    online, latency_ms, packet_loss, latency_min_ms, latency_median_ms,
                    latency_max_ms, ping_sent, ping_received, latency_readings,
                    anomaly_score, anomaly_label, error
                ) VALUES (?, ?, ?, 'pc', 'icmp_online', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    rec_at,
                    dev_name,
                    target,
                    int(online),
                    lat_med,
                    loss,
                    lat_min,
                    lat_med,
                    lat_max,
                    sent,
                    received,
                    readings,
                    0.0 if label == "Normal" else 1.0,
                    label,
                ),
            )
            telemetry_id = int(cursor.lastrowid)
            connection.execute(
                """
                INSERT INTO condition_labels (telemetry_id, label, reviewed_at)
                VALUES (?, ?, ?)
                ON CONFLICT(telemetry_id) DO UPDATE SET
                    label = excluded.label,
                    reviewed_at = excluded.reviewed_at
                """,
                (telemetry_id, label, now),
            )
            inserted_counts[label] += 1
        connection.commit()

    return {
        "imported_samples": len(records_to_insert),
        "live_online_probes": live_probes,
        "calibrated_base_rtt_ms": round(base_rtt, 2),
        "class_counts": dict(inserted_counts),
    }


def get_ml_training_data() -> tuple[list[dict[str, Any]], dict[int, str]]:
    initialize_database()
    auto_apply_rule_labels(overwrite=False)
    with _db_lock, _connect() as connection:
        samples = [
            _row_dict(row)
            for row in connection.execute(
                "SELECT * FROM telemetry WHERE protocol IN ('icmp', 'icmp_online') ORDER BY id"
            )
        ]
        labels = {
            int(row["telemetry_id"]): str(row["label"])
            for row in connection.execute("SELECT telemetry_id, label FROM condition_labels")
        }
    return samples, labels


def get_ml_labeling_samples(limit: int = 100) -> list[dict[str, Any]]:
    initialize_database()
    auto_apply_rule_labels(overwrite=False)
    with _db_lock, _connect() as connection:
        rows = connection.execute(
            """
            SELECT telemetry.id, telemetry.recorded_at, telemetry.device_name, telemetry.target,
                   telemetry.online, telemetry.latency_min_ms, telemetry.latency_median_ms,
                   telemetry.latency_max_ms, telemetry.latency_ms,
                   telemetry.packet_loss, telemetry.ping_sent, telemetry.ping_received,
                   condition_labels.label AS condition_label
            FROM telemetry
            LEFT JOIN condition_labels ON condition_labels.telemetry_id = telemetry.id
            WHERE telemetry.protocol IN ('icmp', 'icmp_online')
              AND ((telemetry.online = 1 AND telemetry.ping_received > 0
                    AND COALESCE(telemetry.latency_median_ms, telemetry.latency_ms) IS NOT NULL)
                   OR (telemetry.online = 0 AND telemetry.ping_received = 0))
            ORDER BY CASE WHEN telemetry.protocol = 'icmp' THEN 0 ELSE 1 END, telemetry.id DESC LIMIT ?
            """,
            (max(1, min(int(limit), 500)),),
        ).fetchall()
    results = []
    for row in rows:
        d = _row_dict(row)
        lat = float(d.get("latency_median_ms") or d.get("latency_ms") or 0.0)
        loss = float(d.get("packet_loss") or 0.0)
        is_uncertain = (120.0 <= lat <= 180.0) or (1.0 <= loss <= 30.0)
        d["needs_review"] = is_uncertain
        d["uncertainty_score"] = 0.45 if is_uncertain else 0.10
        results.append(d)
    return results


def save_condition_label(telemetry_id: int, label: str) -> bool:
    allowed_labels = {"Normal", "High Latency", "Packet Loss", "Unreachable"}
    if label not in allowed_labels:
        raise ValueError("Choose a supported condition label")
    initialize_database()
    with _db_lock, _connect() as connection:
        sample = connection.execute(
            """
            SELECT id FROM telemetry
            WHERE id = ? AND protocol IN ('icmp', 'icmp_online')
              AND ((online = 1 AND ping_received > 0
                    AND COALESCE(latency_median_ms, latency_ms) IS NOT NULL)
                   OR (online = 0 AND ping_received = 0))
            """,
            (telemetry_id,),
        ).fetchone()
        if not sample:
            return False
        connection.execute(
            """
            INSERT INTO condition_labels (telemetry_id, label, reviewed_at)
            VALUES (?, ?, ?)
            ON CONFLICT(telemetry_id) DO UPDATE SET label = excluded.label, reviewed_at = excluded.reviewed_at
            """,
            (telemetry_id, label, _utc_now()),
        )
    return True


def save_recommendation_selection(
    telemetry_id: int,
    target: str,
    suggestion: dict[str, Any],
) -> int | None:
    initialize_database()
    with _db_lock, _connect() as connection:
        sample = connection.execute(
            """
            SELECT id FROM telemetry
            WHERE id = ? AND target = ? AND protocol = 'icmp'
              AND ((online = 1 AND ping_received > 0
                    AND COALESCE(latency_median_ms, latency_ms) IS NOT NULL)
                   OR (online = 0 AND ping_received = 0))
            """,
            (telemetry_id, target),
        ).fetchone()
        if not sample:
            return None
        cursor = connection.execute(
            """
            INSERT INTO recommendation_feedback
                (telemetry_id, target, suggestion_id, suggested_action, model_sources,
                 evidence, selected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                telemetry_id,
                target,
                suggestion["id"],
                suggestion["action"],
                json.dumps(suggestion["model_sources"]),
                json.dumps(suggestion["evidence"]),
                _utc_now(),
            ),
        )
        return int(cursor.lastrowid)


def get_recommendation_feedback(limit: int = 100) -> list[dict[str, Any]]:
    initialize_database()
    with _db_lock, _connect() as connection:
        rows = connection.execute(
            """
            SELECT recommendation_feedback.*, telemetry.device_name, telemetry.recorded_at
            FROM recommendation_feedback
            JOIN telemetry ON telemetry.id = recommendation_feedback.telemetry_id
            ORDER BY recommendation_feedback.id DESC LIMIT ?
            """,
            (max(1, min(int(limit), 500)),),
        ).fetchall()
    results = [_row_dict(row) for row in rows]
    for row in results:
        row["model_sources"] = json.loads(row["model_sources"])
        row["evidence"] = json.loads(row["evidence"])
    return results


def save_recommendation_outcome(
    feedback_id: int,
    outcome: str,
    verified_finding: str,
    notes: str,
) -> bool:
    allowed_outcomes = {"resolved", "not_resolved", "unknown"}
    allowed_findings = {
        "",
        "Shared path degradation",
        "Device-specific issue",
        "ICMP blocked",
        "No issue found",
        "Other / unknown",
    }
    if outcome not in allowed_outcomes:
        raise ValueError("Choose Resolved, Not resolved, or Unknown")
    if verified_finding not in allowed_findings:
        raise ValueError("Choose a supported verified finding")
    initialize_database()
    with _db_lock, _connect() as connection:
        connection.execute(
            """
            UPDATE recommendation_feedback
            SET outcome = ?, verified_finding = ?, notes = ?, outcome_at = ?
            WHERE id = ?
            """,
            (outcome, verified_finding, notes.strip()[:1000], _utc_now(), feedback_id),
        )
        return connection.execute("SELECT changes()").fetchone()[0] > 0


def get_building_name() -> str:
    """Get the current building name from master settings or active db."""
    return _get_active_building_name()


def save_building_name(name: str) -> str:
    """Create/register a building database and make it the active database."""
    global _active_building_name_cache
    clean_name = name.strip()[:100] or "Unknown Building"
    target_path = _get_database_path_for_name(clean_name)

    _initialize_database_file(target_path, clean_name)

    master_db = _get_database_dir() / "monitoring.db"
    try:
        with sqlite3.connect(master_db, timeout=10) as master_conn:
            master_conn.execute(
                "CREATE TABLE IF NOT EXISTS application_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            master_conn.execute(
                "INSERT INTO application_settings (key, value) VALUES ('active_building_name', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (clean_name,),
            )
            master_conn.execute(
                "INSERT INTO application_settings (key, value) VALUES ('building_name', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (clean_name,),
            )
            master_conn.commit()
    except Exception:
        pass

    with _active_db_lock:
        _active_building_name_cache = clean_name

    return clean_name


def switch_to_database(name: str) -> str:
    """Switch active database to the specified building."""
    global _active_building_name_cache
    clean_name = name.strip()
    target_path = _get_database_path_for_name(clean_name)

    if not target_path.exists():
        for db_file in _get_database_dir().glob("monitoring_*.db"):
            try:
                with sqlite3.connect(db_file, timeout=2) as conn:
                    conn.row_factory = sqlite3.Row
                    row = conn.execute(
                        "SELECT value FROM application_settings WHERE key = 'building_name' LIMIT 1"
                    ).fetchone()
                    if row and str(row["value"]).strip().lower() == clean_name.lower():
                        target_path = db_file
                        clean_name = str(row["value"]).strip()
                        break
            except Exception:
                pass

    if not target_path.exists() and (_get_database_dir() / "monitoring.db").exists() and clean_name == "Unknown Building":
        target_path = _get_database_dir() / "monitoring.db"

    _initialize_database_file(target_path, clean_name)

    master_db = _get_database_dir() / "monitoring.db"
    try:
        with sqlite3.connect(master_db, timeout=10) as master_conn:
            master_conn.execute(
                "CREATE TABLE IF NOT EXISTS application_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            master_conn.execute(
                "INSERT INTO application_settings (key, value) VALUES ('active_building_name', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (clean_name,),
            )
            master_conn.execute(
                "INSERT INTO application_settings (key, value) VALUES ('building_name', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (clean_name,),
            )
            master_conn.commit()
    except Exception:
        pass

    with _active_db_lock:
        _active_building_name_cache = clean_name

    return clean_name


def get_available_databases() -> list[dict[str, str]]:
    """Get list of available databases (monitoring_*.db files)."""
    databases = []
    seen_names = set()
    try:
        for db_file in sorted(_get_database_dir().glob("monitoring_*.db")):
            b_name = None
            try:
                with sqlite3.connect(db_file, timeout=2) as conn:
                    conn.row_factory = sqlite3.Row
                    row = conn.execute(
                        "SELECT value FROM application_settings WHERE key = 'building_name' LIMIT 1"
                    ).fetchone()
                    if row and row["value"]:
                        b_name = str(row["value"]).strip()
            except Exception:
                pass
            if not b_name:
                b_name = db_file.stem.replace("monitoring_", "").replace("_", " ").strip()
            if b_name and b_name not in seen_names:
                databases.append({"name": b_name, "filename": db_file.name, "path": str(db_file)})
                seen_names.add(b_name)

        master_db = _get_database_dir() / "monitoring.db"
        if master_db.exists():
            master_name = None
            try:
                with sqlite3.connect(master_db, timeout=2) as conn:
                    conn.row_factory = sqlite3.Row
                    row = conn.execute(
                        "SELECT value FROM application_settings WHERE key = 'building_name' LIMIT 1"
                    ).fetchone()
                    if row and row["value"]:
                        master_name = str(row["value"]).strip()
            except Exception:
                pass
            if not master_name:
                master_name = "Unknown Building"
            if master_name not in seen_names and "Unknown Building" not in seen_names:
                databases.append({"name": master_name, "filename": master_db.name, "path": str(master_db)})
                seen_names.add(master_name)

        current = get_building_name()
        if current and current not in seen_names:
            target_path = _get_database_path_for_name(current)
            databases.append({"name": current, "filename": target_path.name, "path": str(target_path)})
    except Exception:
        pass

    return sorted(databases, key=lambda x: x["name"].lower())
