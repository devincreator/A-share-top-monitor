#!/usr/bin/env python3
"""V90: audit exchange financing against a pinned index-session sequence.

Missing sessions and source zeros are never backfilled. A clean recent window
is research-only and does not permit trading predictions or prove publication-time PIT.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path

# For a t-vs-t-63 balance growth, 64 observations are needed.
# Prior 756 growth observations, each with 63-session lookback, require
# t-819..t inclusive = 820 price-index sessions.
WINDOWS = {"finance_growth63": 64, "finance_recent252": 253,
           "finance_growth63_prior756_rank": 820}


def canonical_date(value):
    s = str(value).strip()
    try:
        return dt.date.fromisoformat(s).isoformat()
    except ValueError:
        return dt.datetime.strptime(s, "%Y%m%d").date().isoformat()


def grouped_missing_ranges(expected, absent):
    """Group consecutive missing *index sessions*, not natural-calendar days."""
    absent = set(absent)
    result = []
    start = end = None
    count = 0
    for trading_date in expected:
        if trading_date in absent:
            if start is None:
                start = trading_date
                count = 0
            end = trading_date
            count += 1
        elif start is not None:
            result.append({"start": start, "end": end, "missing_sessions": count})
            start = end = None
    if start is not None:
        result.append({"start": start, "end": end, "missing_sessions": count})
    return result


def audit_financing(rows, index_rows, asof, windows=None):
    """Return factual window coverage; use index dates as calendar proxy only.

    Index rows must have an identity code bound to 000985; calendar is still
    not independently exchange-PIT certified.
    """
    asof = canonical_date(asof)
    windows = dict(windows or WINDOWS)
    result = {
        "schema_version": 2, "asof": asof, "status": "BLOCKED",
        "source_scope": "Jin10/AKShare SH+SZ financing vs 000985 price-index sessions",
        "research_only": True, "formal_signal_allowed": False,
        "finance_publication_timestamp_verified": False,
        "index_calendar_officially_certified": False,
        "source_errors": [], "source_anomalies": [], "windows": {},
        "complete_formal_factor_history": False
    }
    calendar = []
    for item in index_rows:
        if item.get("code") != "000985":
            raise ValueError("index session record not bound to 000985")
        d = canonical_date(item["date"])
        if d <= asof:
            if dt.date.fromisoformat(d).weekday() >= 5:
                raise ValueError(f"weekend index calendar date {d}")
            calendar.append(d)
    if len(set(calendar)) != len(calendar):
        raise ValueError("duplicate index session")
    calendar = sorted(calendar)
    if not calendar or calendar[-1] != asof:
        result["source_errors"].append("index calendar lacks requested asof session")
        return result
    if not isinstance(rows, list):
        raise ValueError("financing rows are not a list")
    finance = {}
    for item in rows:
        d = canonical_date(item["date"])
        if d > asof:
            continue  # Future response rows do not enter this asof observation.
        if d in finance:
            raise ValueError(f"duplicate financing date {d}")
        try:
            sh = float(item["balance_sh_yuan"])
            sz = float(item["balance_sz_yuan"])
        except (ValueError, TypeError, KeyError) as exc:
            finance[d] = None
            result["source_anomalies"].append({"date": d, "reason": "UNPARSEABLE_BALANCE"})
            continue
        if not all(math.isfinite(x) and x > 0 for x in (sh, sz)):
            finance[d] = None
            result["source_anomalies"].append({"date": d, "reason": "NONPOSITIVE_OR_NONFINITE",
                                               "balance_sh_yuan": str(sh), "balance_sz_yuan": str(sz)})
            continue
        finance[d] = sh + sz
    on_calendar = set(calendar)
    result["source_anomalies"].extend(
        {"date": d, "reason": "FINANCING_DATE_NOT_IN_INDEX_SESSIONS"}
        for d in sorted(finance.keys() - on_calendar) if d >= calendar[0])
    usable = {d: value for d, value in finance.items()
              if d in on_calendar and value is not None}
    result["finance_rows_received_through_asof"] = len(finance)
    result["finance_valid_index_aligned_rows"] = len(usable)
    result["index_session_rows_through_asof"] = len(calendar)
    for name, size in windows.items():
        if not isinstance(size, int) or size < 2:
            raise ValueError("window size must be integer >=2")
        expected = calendar[-size:]
        absent = [d for d in expected if d not in finance]
        invalid = [d for d in expected if d in finance and finance[d] is None]
        item = {
            "required_sessions": size,
            "calendar_sessions_available": len(expected),
            "window_start": expected[0], "window_end": expected[-1],
            "missing_session_count": len(absent),
            "invalid_balance_count": len(invalid),
            "missing_dates_head": absent[:12],
            "missing_session_ranges": grouped_missing_ranges(expected, absent),
            "invalid_dates": invalid[:12],
            "window_complete": len(expected) == size and not absent and not invalid
        }
        if len(expected) != size:
            item["status"] = "BLOCKED_INSUFFICIENT_INDEX_HISTORY"
        elif absent or invalid:
            item["status"] = "BLOCKED_SOURCE_GAPS_OR_ANOMALIES"
        else:
            item["status"] = "CANDIDATE_WINDOW_ONLY_NOT_PIT"
            item["asof_balance_sh_sz_yuan"] = usable[asof]
            if name == "finance_growth63" and size == 64:
                previous = usable[expected[0]]
                item["growth63_pct"] = 100 * (usable[asof] / previous - 1)
        result["windows"][name] = item
    result["status"] = ("RECENT_WINDOW_CANDIDATE_LONG_FACTOR_BLOCKED"
                        if result["windows"].get("finance_growth63", {}).get("window_complete")
                        else "BLOCKED_FINANCING_RECENT_WINDOW")
    if all(x["window_complete"] for x in result["windows"].values()):
        result["status"] = "ALL_WINDOWS_SCHEMA_VALID_NOT_PIT"
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Original V89 candidate_inputs.json")
    parser.add_argument("--asof", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payload = Path(args.input).read_bytes()
    doc = json.loads(payload)
    report = audit_financing(doc.get("financing", []),
                             doc.get("indices", {}).get("000985", []), args.asof)
    report["candidate_input_sha256"] = hashlib.sha256(payload).hexdigest()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                      encoding="utf-8")
    print(json.dumps({"status": report["status"],
                      "window_statuses": {k: v["status"] for k, v in report["windows"].items()},
                      "formal_signal_allowed": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
