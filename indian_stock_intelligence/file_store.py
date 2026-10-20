"""Simple local JSON/CSV persistence; no SQL database or user accounts."""
from __future__ import annotations
import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_DIR = Path(os.getenv("STOCK_DATA_DIR", str(Path(__file__).resolve().parent / "data"))).resolve()
STATE_FILE = DATA_DIR / "app_state.json"


def initialize_store() -> None:
    (DATA_DIR / "snapshots").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "price_history").mkdir(parents=True, exist_ok=True)
    if not STATE_FILE.exists():
        _write_json(STATE_FILE, {"watchlist": [], "score_runs": [], "alert_rules": [], "alert_events": []})


def _write_json(path: Path, content: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(content, stream, ensure_ascii=False, indent=2, default=_json_default)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _json_default(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _read_state() -> dict:
    initialize_store()
    try:
        with STATE_FILE.open("r", encoding="utf-8") as stream:
            state = json.load(stream)
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"Could not read local app data at {STATE_FILE}: {exc}") from exc
    for name in ("watchlist", "score_runs", "alert_rules", "alert_events"):
        state.setdefault(name, [])
    return state


def _save_state(state: dict) -> None:
    _write_json(STATE_FILE, state)


def _symbol_key(symbol: str, exchange: str) -> str:
    safe = re.sub(r"[^A-Z0-9._-]", "_", symbol.upper())
    return f"{exchange.upper()}_{safe}"


def save_stock_snapshot(data: dict) -> tuple[str, str]:
    initialize_store()
    symbol = data["symbol"]
    exchange = "BSE" if symbol.endswith(".BO") else "NSE"
    key = _symbol_key(symbol, exchange)
    meta_path = DATA_DIR / "snapshots" / f"{key}.json"
    history_path = DATA_DIR / "price_history" / f"{key}.csv"
    snapshot = {k: v for k, v in data.items() if k != "history"}
    snapshot["info"] = data.get("info", {})
    snapshot["technical"] = data.get("technical", {})
    _write_json(meta_path, snapshot)
    data["history"].to_csv(history_path, index=True, index_label="Date")
    return str(meta_path), str(history_path)


def get_watch_items() -> list[dict]:
    return _read_state()["watchlist"]


def add_watch_item(symbol: str, exchange: str) -> None:
    state = _read_state()
    symbol, exchange = symbol.upper(), exchange.upper()
    if not any(x["symbol"] == symbol and x["exchange"] == exchange for x in state["watchlist"]):
        state["watchlist"].append({"id": f"{exchange}:{symbol}", "symbol": symbol, "exchange": exchange})
        _save_state(state)


def remove_watch_item(symbol: str, exchange: str) -> None:
    state = _read_state()
    state["watchlist"] = [x for x in state["watchlist"] if not (x["symbol"] == symbol and x["exchange"] == exchange)]
    _save_state(state)


def get_score_history(symbol: str, exchange: str) -> list[dict]:
    rows = [x for x in _read_state()["score_runs"] if x["symbol"] == symbol and x["exchange"] == exchange]
    return sorted(rows, key=lambda x: x["calculated_at"], reverse=True)[:30]


def save_score_run(symbol: str, exchange: str, model_version: str, score: float | None,
                   coverage: float, price: float, market_timestamp: str, source: str,
                   explanation_json: str) -> None:
    state = _read_state()
    state["score_runs"].append({"calculated_at": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol, "exchange": exchange, "model_version": model_version,
        "score": score, "coverage": coverage, "price": price,
        "market_timestamp": market_timestamp, "source": source,
        "explanation_json": explanation_json})
    state["score_runs"] = state["score_runs"][-5000:]
    _save_state(state)


def add_price_alert(symbol: str, exchange: str, threshold: float, rule_type: str = "price_above") -> None:
    if rule_type not in {"price_above", "price_below"} or threshold <= 0:
        raise ValueError("Select a valid price alert and a threshold greater than zero.")
    state = _read_state()
    rule = next((r for r in state["alert_rules"] if r["symbol"] == symbol and r["exchange"] == exchange and r["rule_type"] == rule_type), None)
    if rule:
        rule["threshold"], rule["enabled"] = threshold, True
    else:
        state["alert_rules"].append({"id": str(uuid.uuid4()), "symbol": symbol,
            "exchange": exchange, "rule_type": rule_type, "threshold": threshold,
            "enabled": True, "last_matched": False})
    _save_state(state)


def evaluate_price_alerts(symbol: str, exchange: str, price: float) -> None:
    state = _read_state()
    now = datetime.now(timezone.utc).isoformat()
    for rule in state["alert_rules"]:
        if not rule["enabled"] or rule["symbol"] != symbol or rule["exchange"] != exchange:
            continue
        matched = price >= rule["threshold"] if rule["rule_type"] == "price_above" else price <= rule["threshold"]
        if matched and not rule.get("last_matched", False):
            state["alert_events"].append({"id": str(uuid.uuid4()), "symbol": symbol,
                "exchange": exchange, "type": rule["rule_type"],
                "threshold": rule["threshold"], "observed": price, "at": now, "dismissed": False})
        rule["last_matched"] = matched
    state["alert_events"] = state["alert_events"][-5000:]
    _save_state(state)


def get_alert_events() -> list[dict]:
    return sorted(_read_state()["alert_events"], key=lambda x: x["at"], reverse=True)[:100]


def dismiss_alert(alert_id: str) -> None:
    state = _read_state()
    for event in state["alert_events"]:
        if event["id"] == alert_id:
            event["dismissed"] = True
            break
    _save_state(state)
