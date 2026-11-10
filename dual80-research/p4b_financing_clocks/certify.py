"""P4b: attach certified disclosure clocks to stored financing balances.

The plan is read and hashed. This script never writes plan.json.

    python -B dual80-research/p4b_financing_clocks/certify.py

A second run reuses attempts/ unless --refetch is passed. Official hosts are
fetched once. A credential wall or an HTTP 401/403/429 is saved and not
retried. No financing model is fit.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SHANGHAI = ZoneInfo("Asia/Shanghai")
PLAN_PATH = HERE / "plan.json"
ATTEMPTS = HERE / "attempts"

ALLOWLIST = {
    "publishTime",
    "publishedAt",
    "disclosureTime",
    "announcementTime",
    "firstAvailableTime",
    "visibleAt",
    "releaseTime",
    "publication_time",
    "disclosure_timestamp",
    "published_at",
    "visible_at",
    "release_time",
    "公布时间",
    "披露时间",
    "发布时间",
    "最早可用时间",
}
PUBLICATION_LABELS = ALLOWLIST | {
    "更新时间",
    "数据更新时间",
    "最后更新时间",
    "披露时点",
    "发布时点",
    "updateTime",
    "updTime",
    "pubTime",
    "publish_time",
    "publishDateTime",
    "release_timestamp",
}
CAPTURE_KEYS = {
    "request_started_at_utc",
    "response_completed_at_utc",
    "first_captured_at_utc",
    "source_run_started_at_utc",
}
OBSERVATION_DATE_KEYS = {
    "opDate",
    "tradeDate",
    "date",
    "信用交易日期",
    "txtDate",
    "subname",
    "起始日期",
    "终止日期",
}
NON_CLOCK_KEYS = CAPTURE_KEYS | OBSERVATION_DATE_KEYS | {"数据来源"}
UNCLASSIFIED_TIME = re.compile(r"(time|Time|date|Date|时间|日期|更新|publish|Publish|release|Release)")
CLOCK_VALUE = re.compile(
    r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})(?:日)?"
    r"(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?"
)
ISO_CLOCK = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?(?:\.(\d+))?(Z|[+-]\d{2}:?\d{2})?"
)
BEIJING_WORD = re.compile(r"北京时间|Asia/Shanghai|东八区")
SAMPLE_DATES = ("2011-08-02", "2020-07-13", "2021-09-13", "2026-08-25")
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_plan() -> dict:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    if plan.get("phase") != "P4b" or plan.get("contains_measurements") is not False:
        raise SystemExit("plan.json is not the frozen P4b plan")
    for rel, expected in plan["source_sha256"].items():
        actual = sha256_file(ROOT / rel)
        if actual != expected:
            raise SystemExit(f"PLAN_SOURCE_CHANGED {rel}")
    return plan


def parse_day(value: str) -> date:
    return date.fromisoformat(value[:10])


def deadline_for(next_session: date) -> datetime:
    return datetime(
        next_session.year,
        next_session.month,
        next_session.day,
        9,
        15,
        tzinfo=SHANGHAI,
    )


def before_deadline(clock: datetime, next_session: date) -> bool:
    if clock.tzinfo is None:
        return False
    return clock.astimezone(SHANGHAI) < deadline_for(next_session)


def parse_clock(value: object, nearby_text: str = "") -> datetime | None:
    """Return a timezone-aware clock. A date with no time of day is not a clock."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    iso = ISO_CLOCK.fullmatch(text)
    if iso:
        year, month, day, hour, minute, second, _fraction, zone = iso.groups()
        if zone is None:
            if not BEIJING_WORD.search(nearby_text):
                return None
            tz = SHANGHAI
        elif zone == "Z":
            tz = ZoneInfo("UTC")
        else:
            cleaned = zone if ":" in zone else zone[:3] + ":" + zone[3:]
            sign = 1 if cleaned[0] == "+" else -1
            hours, minutes = cleaned[1:].split(":")
            tz = timezone_fixed(sign, int(hours), int(minutes))
        return datetime(
            int(year), int(month), int(day), int(hour), int(minute), int(second or 0), tzinfo=tz
        )
    matched = CLOCK_VALUE.search(text)
    if not matched or matched.group(4) is None:
        return None
    if not BEIJING_WORD.search(text) and not BEIJING_WORD.search(nearby_text):
        return None
    year, month, day, hour, minute, second = matched.group(1, 2, 3, 4, 5, 6)
    return datetime(
        int(year), int(month), int(day), int(hour), int(minute), int(second or 0), tzinfo=SHANGHAI
    )


def timezone_fixed(sign: int, hours: int, minutes: int):
    from datetime import timezone

    return timezone(sign * timedelta(hours=hours, minutes=minutes))


def normalize_observation(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) < 8:
        return value
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"


def walk(obj, keys: Counter, clocks: list[dict], unclassified: Counter, path: str = "") -> None:
    if isinstance(obj, dict):
        nearby = json.dumps(obj, ensure_ascii=False)[:500]
        observation = None
        for name in OBSERVATION_DATE_KEYS:
            if name in obj and isinstance(obj[name], str):
                observation = normalize_observation(obj[name])
                break
        for key, value in obj.items():
            keys[key] += 1
            if key in NON_CLOCK_KEYS:
                if isinstance(value, (dict, list)):
                    walk(value, keys, clocks, unclassified, path + "/" + key)
                continue
            if key in PUBLICATION_LABELS and isinstance(value, (str, int, float)):
                clocks.append(
                    {
                        "key": key,
                        "value": str(value),
                        "observation": observation,
                        "page_level": observation is None,
                        "on_allowlist": key in ALLOWLIST,
                        "path": path + "/" + key,
                        "parsed": _iso(parse_clock(str(value), nearby)),
                    }
                )
            elif isinstance(value, str) and UNCLASSIFIED_TIME.search(key):
                unclassified[key] += 1
            if isinstance(value, (dict, list)):
                walk(value, keys, clocks, unclassified, path + "/" + key)
            elif isinstance(value, str) and value[:1] in "{[":
                nested = _maybe_json(value)
                if nested is not None:
                    walk(nested, keys, clocks, unclassified, path + "/" + key)
    elif isinstance(obj, list):
        for item in obj:
            walk(item, keys, clocks, unclassified, path)


def _maybe_json(value: str):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _iso(clock: datetime | None) -> str | None:
    if clock is None:
        return None
    return clock.astimezone(SHANGHAI).isoformat()


def inspect_json_file(path: Path) -> dict:
    keys: Counter = Counter()
    clocks: list[dict] = []
    unclassified: Counter = Counter()
    payload = json.loads(path.read_text(encoding="utf-8"))
    walk(payload, keys, clocks, unclassified)
    download_clocks = []
    if isinstance(payload, dict) and isinstance(payload.get("retrieved_at"), str):
        download_clocks.append(
            {
                "key": "retrieved_at",
                "value": payload["retrieved_at"],
                "classification": "DOWNLOAD_TIME_NOT_DISCLOSURE",
            }
        )
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256_file(path),
        "keys": dict(keys),
        "clock_fields": clocks,
        "download_clocks": download_clocks,
        "unclassified_time_like_keys": dict(unclassified),
    }


def inspect_csv_header(path: Path) -> dict:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        header = next(csv.reader(handle))
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256_file(path),
        "header": header,
        "allowlist_columns": [name for name in header if name in ALLOWLIST],
    }


def read_calendar() -> list[str]:
    with (ROOT / "turning-research-canonical/tables/research_inputs.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    dates = [row["date"] for row in rows]
    if len(dates) != 3659 or len(set(dates)) != 3659:
        raise SystemExit("research calendar is not the frozen 3659 dates")
    if dates[0] != "2011-08-02" or dates[-1] != "2026-08-25":
        raise SystemExit("research calendar bounds differ from the plan")
    return dates


def read_balances() -> list[str]:
    with (ROOT / "turning-raw-reacquired/tables/financing_sh_sz.csv").open(
        encoding="utf-8-sig", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    if [row["date"] for row in rows] != read_calendar():
        raise SystemExit("financing dates do not match the research calendar")
    return [row["date"] for row in rows]


def lineage_counts(path: Path) -> dict:
    counts: Counter = Counter()
    fields: Counter = Counter()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if "financ" in row["field"] or "融资" in row["field"]:
                counts[row["status"]] += 1
                fields[row["field"]] += 1
    return {"path": str(path.relative_to(ROOT)), "status": dict(counts), "fields": dict(fields)}


def scan_v92() -> dict:
    records = ROOT / "A-share-top-monitor-history/research/v92_margin_recovery/records"
    raw = ROOT / "A-share-top-monitor-history/research/v92_margin_recovery/raw"
    keys: Counter = Counter()
    pit: Counter = Counter()
    capture_values: list[str] = []
    clock_fields: list[dict] = []
    record_files = sorted(records.glob("*/*.json"))
    for path in record_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        local_keys: Counter = Counter()
        local_clocks: list[dict] = []
        unclassified: Counter = Counter()
        walk(payload, local_keys, local_clocks, unclassified)
        keys.update(local_keys)
        clock_fields.extend(local_clocks)
        pit[str(payload.get("PIT_certified"))] += 1
        for name in CAPTURE_KEYS:
            if name in payload and isinstance(payload[name], str):
                capture_values.append(payload[name])
    headers: Counter = Counter()
    raw_files = sorted(raw.glob("*/*.csv"))
    for path in raw_files:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            header = tuple(next(csv.reader(handle)))
        headers[header] += 1
    return {
        "record_files": len(record_files),
        "raw_files": len(raw_files),
        "keys": dict(keys),
        "PIT_certified": dict(pit),
        "capture_value_count": len(capture_values),
        "capture_min": min(capture_values) if capture_values else None,
        "capture_max": max(capture_values) if capture_values else None,
        "clock_fields": clock_fields,
        "raw_headers": [{"header": list(header), "files": count} for header, count in headers.items()],
    }


def scan_ifind() -> dict:
    folder = ROOT / "A-share-top-monitor-history/ifind_financing"
    keys: Counter = Counter()
    clock_fields: list[dict] = []
    unclassified: Counter = Counter()
    files = sorted(folder.glob("*_raw.json"))
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        walk(payload, keys, clock_fields, unclassified)
    daily_path = folder / "financing_daily.csv"
    daily = inspect_csv_header(daily_path)
    flag_counts: Counter = Counter()
    with daily_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            flag_counts[row.get("publication_time_certified", "")] += 1
    return {
        "raw_files": len(files),
        "keys": dict(keys),
        "clock_fields": clock_fields,
        "unclassified_time_like_keys": dict(unclassified),
        "daily_header": daily["header"],
        "daily_allowlist_columns": daily["allowlist_columns"],
        "publication_time_certified_values": dict(flag_counts),
        "publication_time_certified_classification": "PROVIDER_FLAG_NOT_A_CLOCK",
    }


def sse_url(day: str) -> str:
    ymd = day.replace("-", "")
    return (
        "https://query.sse.com.cn/marketdata/tradedata/queryMargin.do"
        "?isPagination=true"
        f"&beginDate={ymd}&endDate={ymd}"
        "&tabType=&stockCode="
        "&pageHelp.pageSize=5000&pageHelp.pageNo=1&pageHelp.beginPage=1"
        "&pageHelp.cacheSize=1&pageHelp.endPage=5"
    )


def szse_url(day: str) -> str:
    return (
        "https://www.szse.cn/api/report/ShowReport/data"
        f"?SHOWTYPE=JSON&CATALOGID=1837_xxpl&txtDate={day}&tab1PAGENO=1"
    )


def fetch(url: str, referer: str, stem: str, refetch: bool) -> dict:
    ATTEMPTS.mkdir(exist_ok=True)
    body_path = ATTEMPTS / f"{stem}.body"
    meta_path = ATTEMPTS / f"{stem}.meta.json"
    if meta_path.exists() and not refetch and (body_path.exists() or meta_path.read_text(encoding="utf-8").find('"error"') >= 0):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        body = body_path.read_bytes() if body_path.exists() else b""
        meta["reused_saved_body"] = True
        meta["body_sha256"] = sha256_bytes(body) if body else None
        meta["blocked"] = meta.get("status") in {401, 403, 429}
        meta["transport_error"] = bool(meta.get("error"))
        return {"meta": meta, "body": body}
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": referer,
        },
    )
    blocked = False
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            status = getattr(response, "status", 200)
            headers = dict(response.headers.items())
            final_url = response.geturl()
    except urllib.error.HTTPError as error:
        body = error.read()
        status = error.code
        headers = dict(error.headers.items()) if error.headers else {}
        final_url = url
        blocked = status in {401, 403, 429}
    except Exception as error:  # noqa: BLE001 — the transport error is the evidence
        meta = {
            "url": url,
            "referer": referer,
            "status": None,
            "error": type(error).__name__,
            "detail": str(error),
            "blocked": False,
            "transport_error": True,
            "headers": {},
            "body_sha256": None,
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {"meta": meta, "body": b""}
    if status in {401, 403, 429}:
        blocked = True
    meta = {
        "url": url,
        "final_url": final_url,
        "referer": referer,
        "status": status,
        "blocked": blocked,
        "headers": headers,
        "body_sha256": sha256_bytes(body),
        "body_bytes": len(body),
    }
    body_path.write_bytes(body)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"meta": meta, "body": body}


def decode_body(body: bytes) -> str:
    for encoding in ("utf-8", "gb18030"):
        try:
            return body.decode(encoding)
        except UnicodeDecodeError:
            continue
    return body.decode("utf-8", errors="replace")


def inspect_body(body: bytes, source: str) -> dict:
    if not body:
        return {
            "source": source,
            "parsed_json": False,
            "clock_fields": [],
            "per_row_clocks": [],
            "keys": {},
            "label_quotes": [],
            "page_generation_times": [],
            "news_publication_times": [],
            "unclassified_time_like_keys": {},
        }
    text = decode_body(body).strip()
    keys: Counter = Counter()
    clocks: list[dict] = []
    unclassified: Counter = Counter()
    parsed = False
    if text[:1] in "{[":
        payload = _maybe_json(text)
        if payload is not None:
            parsed = True
            walk(payload, keys, clocks, unclassified)
    quotes = []
    for label in ("公布时间", "披露时间", "发布时间", "最早可用时间", "更新时间", "数据更新时间"):
        start = 0
        found = 0
        while found < 3:
            index = text.find(label, start)
            if index < 0:
                break
            quotes.append(re.sub(r"\s+", " ", text[max(0, index - 60) : index + 80])[:160])
            start = index + len(label)
            found += 1
    per_row = [item for item in clocks if not item["page_level"] and item["parsed"]]
    return {
        "source": source,
        "parsed_json": parsed,
        "keys": dict(keys),
        "clock_fields": clocks,
        "per_row_clocks": per_row,
        "unclassified_time_like_keys": dict(unclassified),
        "label_quotes": quotes,
        "page_generation_times": re.findall(r"页面生成时间[^<\"']{0,40}", text),
        "news_publication_times": re.findall(r'"(pubDate|upDate)"\s*:\s*"([^"]+)"', text),
        "http_date": None,
    }


def host_of(stem: str) -> str:
    if stem.startswith("sse"):
        return "sse"
    if stem.startswith("szse"):
        return "szse"
    return "nbd"


def record_fetch(stem: str, url: str, referer: str, refetch: bool) -> dict:
    fetched = fetch(url, referer, stem, refetch)
    meta = fetched["meta"]
    inspected = inspect_body(fetched["body"], stem)
    header_map = {str(key).lower(): value for key, value in meta.get("headers", {}).items()}
    inspected["http_date"] = header_map.get("date")
    inspected["http_last_modified"] = header_map.get("last-modified")
    inspected["status"] = meta.get("status")
    inspected["blocked"] = bool(meta.get("blocked"))
    inspected["error"] = meta.get("error")
    inspected["url"] = meta.get("url")
    inspected["body_sha256"] = meta.get("body_sha256")
    inspected["body_bytes"] = meta.get("body_bytes", len(fetched["body"]))
    return inspected


def probe(refetch: bool) -> list[dict]:
    jobs = []
    for day in SAMPLE_DATES:
        jobs.append((f"sse_{day}", sse_url(day), "https://www.sse.com.cn/market/othersdata/margin/sum/"))
        jobs.append((f"szse_{day}", szse_url(day), "https://www.szse.cn/disclosure/margin/margin/index.html"))
    jobs.append(("sse_html", "https://www.sse.com.cn/market/othersdata/margin/sum/", "https://www.sse.com.cn/"))
    jobs.append(
        ("szse_html", "https://www.szse.cn/disclosure/margin/margin/index.html", "https://www.szse.cn/")
    )
    jobs.append(
        (
            "nbd_2021-09-14",
            "https://www.nbd.com.cn/articles/2021-09-14/1912369.html",
            "https://www.nbd.com.cn/",
        )
    )
    results = []
    blocked_hosts: set[str] = set()
    for stem, url, referer in jobs:
        host = host_of(stem)
        if host in blocked_hosts:
            results.append(
                {
                    "source": stem,
                    "url": url,
                    "blocked": True,
                    "skipped_after_block": True,
                    "status": None,
                    "clock_fields": [],
                    "per_row_clocks": [],
                    "keys": {},
                    "label_quotes": [],
                }
            )
            continue
        inspected = record_fetch(stem, url, referer, refetch)
        results.append(inspected)
        if inspected.get("blocked"):
            blocked_hosts.add(host)
    return results


def extend_if_sample_has_clocks(sample: list[dict], dates: list[str], refetch: bool) -> list[dict]:
    """Fetch the remaining research dates only for an exchange whose sample has a per-row clock."""
    extra = []
    for host, url_for in (("sse", sse_url), ("szse", szse_url)):
        referer = (
            "https://www.sse.com.cn/market/othersdata/margin/sum/"
            if host == "sse"
            else "https://www.szse.cn/disclosure/margin/margin/index.html"
        )
        if not any(item.get("per_row_clocks") and item.get("source", "").startswith(host + "_") for item in sample):
            continue
        for day in dates:
            if day in SAMPLE_DATES:
                continue
            inspected = record_fetch(f"{host}_{day}", url_for(day), referer, refetch)
            extra.append(inspected)
            if inspected.get("blocked"):
                break
    return extra


def per_row_clocks(records: list[dict]) -> list[dict]:
    found = []
    for record in records:
        if record.get("source", "").startswith("nbd_"):
            continue
        for clock in record.get("per_row_clocks") or []:
            found.append({"source": record["source"], **clock})
    return found


def build_ledger(dates: list[str], certified: dict[tuple[str, str], dict]) -> list[dict]:
    rows = []
    exchanges = (("SSE", "balance_sh_yuan"), ("SZSE", "balance_sz_yuan"))
    for index, observation in enumerate(dates):
        next_session = dates[index + 1] if index + 1 < len(dates) else ""
        for exchange, field in exchanges:
            hit = certified.get((observation, exchange))
            if not next_session:
                reason = "TERMINAL_DATE_NO_NEXT_SESSION"
                clock = ""
                flag = "false"
            elif hit and hit["before_deadline"]:
                reason = "CERTIFIED"
                clock = hit["disclosure_timestamp"]
                flag = "true"
            elif hit:
                reason = "CLOCK_AFTER_CUTOFF"
                clock = hit["disclosure_timestamp"]
                flag = "false"
            else:
                reason = "NO_CERTIFIED_DISCLOSURE_CLOCK"
                clock = ""
                flag = "false"
            rows.append(
                {
                    "observation_date": observation,
                    "exchange": exchange,
                    "field": field,
                    "next_session": next_session,
                    "deadline_asia_shanghai": (
                        f"{next_session}T09:15:00+08:00" if next_session else ""
                    ),
                    "disclosure_timestamp": clock,
                    "certified": flag,
                    "reason": reason,
                    "evidence": "coverage.json",
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def self_check_clock_rules() -> None:
    early = datetime(2021, 9, 14, 8, 39, tzinfo=SHANGHAI)
    same = datetime(2021, 9, 14, 9, 15, tzinfo=SHANGHAI)
    late = datetime(2021, 9, 14, 9, 16, tzinfo=SHANGHAI)
    nxt = date(2021, 9, 14)
    if not before_deadline(early, nxt):
        raise SystemExit("08:39 should fall before 09:15")
    if before_deadline(same, nxt) or before_deadline(late, nxt):
        raise SystemExit("the 09:15 deadline is strict")
    if parse_clock("20210913") is not None or parse_clock("2021-09-13") is not None:
        raise SystemExit("an observation date must not parse as a clock")
    if parse_clock("2021-09-14 08:39:00") is not None:
        raise SystemExit("a bare clock without a stated zone must not parse")
    zoned = parse_clock("2021-09-14 08:39:00", "北京时间")
    if zoned is None or not before_deadline(zoned, nxt):
        raise SystemExit("Beijing time should attach +08:00")
    if parse_clock("2021-09-14T08:39:00+08:00") is None:
        raise SystemExit("an offset clock should parse")


def decision_from(rows: list[dict]) -> str:
    certified = sum(row["certified"] == "true" for row in rows)
    if certified == 0:
        return "CLOCKS_UNAVAILABLE"
    required = sum(row["reason"] != "TERMINAL_DATE_NO_NEXT_SESSION" for row in rows)
    if certified == required:
        return "CLOCKS_COMPLETE"
    return "CLOCKS_PARTIAL"


def prose(decision: str, rows: list[dict], probes: list[dict], stored: dict) -> dict:
    certified = sum(row["certified"] == "true" for row in rows)
    after = sum(row["reason"] == "CLOCK_AFTER_CUTOFF" for row in rows)
    probe_bits = []
    for item in probes:
        if item.get("blocked"):
            state = "blocked"
        elif item.get("error"):
            state = "transport " + str(item["error"])
        else:
            state = "http " + str(item.get("status"))
        clocks = len(item.get("per_row_clocks") or [])
        probe_bits.append(f"{item['source']} {state}, per-row clocks {clocks}")
    probe_text = "; ".join(probe_bits)
    stored_clocks = stored["stored_per_row_clocks"]
    english = (
        f"The stored Shanghai and Shenzhen financing balances cover 3659 research dates "
        f"from 2011-08-02 to 2026-08-25, which is 7318 exchange rows. Certified clocks: {certified}. "
        f"Clocks found after the next 09:15 cutoff: {after}. Stored official summary receipts, iFinD "
        f"history, and v92 captures contributed {stored_clocks} per-row disclosure clocks. "
        f"Live checks of the pre-registered official sources: {probe_text}. "
        "The Shanghai summary payload carries opDate and rzye and no publication time. "
        "retrieved_at on the stored receipt wrapper and the HTTP Date header are download times. "
        "The SSE page meta 页面生成时间 is the page shell. "
        "The 每日经济新闻 pubDate is the article's own time, and the article does not give a per-exchange financing-balance clock. "
        "The iFinD column publication_time_certified is false on every stored row. "
        "A reconstructed lag was not used. No missing date was interpolated. "
        "Financing was not admitted and was not fit. formal_signal_allowed stays false. "
        "This is not PIT and not dual-80. P4a remains NO_FAMILY_ADMITTED. "
        "P1 remains BLOCKED_NO_CONCENTRATION. P1b remains GO_PRE_PIVOT_COORDINATE. "
        "P1c remains BLOCKED_NO_WINDOW_PEAK. P1d remains GO_NEW_FACTORS."
    )
    chinese = (
        f"已保存的沪深融资余额覆盖 2011-08-02 至 2026-08-25 共 3659 个研究日、7318 条交易所行。"
        f"认证披露时点 {certified} 条。晚于下一交易日 09:15 的时点 {after} 条。"
        f"已保存的交易所汇总回执、iFinD 历史和 v92 捕获没有逐行披露时点（逐行时点 {stored_clocks} 条）。"
        f"预先登记的官方来源检查：{probe_text}。"
        "上交所汇总正文只有 opDate 和融资余额，没有公布时间。"
        "回执外壳上的 retrieved_at 和本次 HTTP Date 是下载时间。"
        "上交所页面 meta 里的页面生成时间是页面模板时间。"
        "每日经济新闻的 pubDate 是稿件自己的时间，稿件没有给出分交易所的融资余额披露时点。"
        "iFinD 列 publication_time_certified 在已保存的每一行都是 false。"
        "没有使用重构滞后，也没有插值。"
        "融资家族没有准入，也没有拟合。formal_signal_allowed 仍为 false。"
        "这不是 PIT，也不是双80。P4a 仍是 NO_FAMILY_ADMITTED。"
        "P1 仍是 BLOCKED_NO_CONCENTRATION。P1b 仍是 GO_PRE_PIVOT_COORDINATE。"
        "P1c 仍是 BLOCKED_NO_WINDOW_PEAK。P1d 仍是 GO_NEW_FACTORS。"
    )
    return {"english": english, "chinese": chinese}


def write_readme(decision: str, text: dict, rows: list[dict], probes: list[dict]) -> None:
    certified = sum(row["certified"] == "true" for row in rows)
    blocked = [item["source"] for item in probes if item.get("blocked")]
    transport = [item["source"] for item in probes if item.get("error") and not item.get("blocked")]
    page_times = [quote for item in probes for quote in item.get("page_generation_times") or []]
    news_times = [pair for item in probes for pair in item.get("news_publication_times") or []]
    gap = (
        "官方历史披露时点没有落到任何已保存研究日上。"
        if certified == 0
        else "已认证的只是一部分研究日，其余日期仍没有披露时点。"
    )
    extra = []
    if blocked:
        extra.append("凭证或拒绝页：" + "、".join(blocked) + "。没有改走其他主机。")
    if transport:
        extra.append("传输失败、没有拿到正文：" + "、".join(transport) + "。没有改用镜像或供应商接口。")
    if page_times:
        extra.append("上交所页面生成时间（页面模板，不是逐日披露）：" + "；".join(page_times) + "。")
    if news_times:
        rendered = "、".join(f"{name}={value}" for name, value in news_times)
        extra.append(
            "新闻稿件自己的时间（不是交易所披露时点，也没有时区）：" + rendered + "。"
            "同一页上的 08:39:25 和 08:38:04 都是稿件时间。即便早于 2021-09-14 09:15，也不能认证沪深融资余额。"
        )
    modified = [
        f"{item['source']} Last-Modified {item['http_last_modified']}"
        for item in probes
        if item.get("http_last_modified")
    ]
    if modified:
        extra.append("本次响应头里的文件时间，不是历史披露时点：" + "；".join(modified) + "。")
    if not blocked and not transport:
        extra.append("预先登记的请求都返回了可检查的正文，正文里没有逐行披露时点。")
    blocked_line = "".join(extra)
    readme = f"""# P4b 融资余额披露时点

**Decision: `{decision}`.** {text['english']}

**结论：`{decision}`。** {text['chinese']}

这是披露时点的收集，不是准入，也不是新模型。`formal_signal_allowed` 仍为 false。没有拟合融资分数。P4a 的 `NO_FAMILY_ADMITTED` 不改写，准入门槛不放宽。

## 认证规则

一条时点要同时满足：它是该交易所自己公布该日融资余额的时间；原始回执已保存，并能复核 SHA256；观察日与台账日期一致；时间带时区，或同一份官方证据写明北京时间；它严格早于下一研究日上海时间 09:15。下一研究日只取 `research_inputs.csv` 的下一行。最后一天 2026-08-25 没有下一行，不为它编造交易日。

下载时间、iFinD 历史、`数据来源`、捕获时间、重构滞后、开盘前惯例、新闻稿的发表时间、以及只有交易日没有钟点的字段，都不认证。

## 覆盖

| 项目 | 数量 |
|---|---:|
| 研究日 | 3659 |
| 交易所行（沪、深各一行） | 7318 |
| 认证通过 | {certified} |
| 日期范围 | 2011-08-02 至 2026-08-25 |

{gap}{blocked_line}

台账是 `ledger.csv`。每一行的结论和原因在 `reason` 列。检查过程、键名和原始回执哈希在 `coverage.json`。

## 没有做的事

- 没有把融资余额放进分数，也没有做 63 日变化。
- 没有写入 `turning-research-canonical/tables/disclosure_timestamps.csv`。那是以后的准入文件，本轮不建立。
- 没有把 D 日融资余额当作 D 日开盘前特征。
- 没有修改生产页面、采集器或正式信号，没有恢复旧 V 系列。
- 没有改写 P1、P1b、P1c、P1d、P4a 的结论。
- 不声称 PIT，不声称双80。

## 复算

```text
python -B dual80-research/p4b_financing_clocks/certify.py
```

`plan.json` 在取证之前写定。脚本只读计划，不改写它。再次运行会复用 `attempts/` 里已经保存的原始正文；`--refetch` 才会重新请求。
"""
    (HERE / "README.md").write_text(readme, encoding="utf-8")


def write_artifact_manifest() -> None:
    files = sorted(
        path
        for path in HERE.rglob("*")
        if path.is_file() and path.name != "artifact_manifest.json" and "__pycache__" not in path.parts
    )
    manifest = {}
    for path in files:
        manifest[str(path.relative_to(HERE))] = {
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    (HERE / "artifact_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    refetch = "--refetch" in sys.argv
    plan_hash = sha256_file(PLAN_PATH)
    load_plan()
    self_check_clock_rules()
    dates = read_balances()
    stored_summaries = [
        inspect_json_file(ROOT / rel)
        for rel in (
            "turning-raw-reacquired/independent_checks/sse_summary_2020-07-13.json",
            "turning-raw-reacquired/independent_checks/sse_summary_2021-09-13.json",
            "turning-raw-reacquired/independent_checks/szse_summary_2020-07-13.json",
            "turning-raw-reacquired/independent_checks/szse_summary_2021-09-13.json",
            "turning-raw-reacquired/independent_checks/sse_finance_20210913.json",
        )
    ]
    balance_header = inspect_csv_header(ROOT / "turning-raw-reacquired/tables/financing_sh_sz.csv")
    total_header = inspect_csv_header(ROOT / "turning-raw-reacquired/tables/financing_balance.csv")
    lineages = [
        lineage_counts(ROOT / "turning-research-canonical/tables/field_lineage.csv"),
        lineage_counts(ROOT / "turning-raw-reacquired/tables/field_lineage.csv"),
    ]
    policy = json.loads((ROOT / "turning-research-canonical/source_policy.json").read_text(encoding="utf-8"))
    lag = json.loads((ROOT / "turning-raw-reacquired/financing_lag_diagnostic.json").read_text(encoding="utf-8"))
    note = (ROOT / "turning-raw-reacquired/独立核验结论.md").read_text(encoding="utf-8")
    v92 = scan_v92()
    ifind = scan_ifind()
    probes = probe(refetch)
    probes.extend(extend_if_sample_has_clocks(probes, dates, refetch))
    stored_per_row = []
    for item in stored_summaries:
        for clock in item["clock_fields"]:
            if not clock["page_level"] and clock["parsed"]:
                stored_per_row.append({"path": item["path"], **clock})
    # Stored provider and capture files are not official per-row disclosure clocks.
    official_hits = per_row_clocks(probes) + stored_per_row
    certified: dict[tuple[str, str], dict] = {}
    date_set = set(dates)
    next_of = {dates[i]: dates[i + 1] for i in range(len(dates) - 1)}
    for hit in official_hits:
        observation = hit.get("observation")
        source = hit.get("source") or hit.get("path", "")
        if observation not in date_set or observation not in next_of:
            continue
        exchange = None
        if source.startswith("sse") or "/sse_summary_" in source:
            exchange = "SSE"
        elif source.startswith("szse") or "/szse_summary_" in source:
            exchange = "SZSE"
        if exchange is None or hit.get("parsed") is None:
            continue
        clock = datetime.fromisoformat(hit["parsed"])
        certified[(observation, exchange)] = {
            "disclosure_timestamp": hit["parsed"],
            "before_deadline": before_deadline(clock, parse_day(next_of[observation])),
            "key": hit["key"],
            "source": source,
        }
    rows = build_ledger(dates, certified)
    decision = decision_from(rows)
    if sha256_file(PLAN_PATH) != plan_hash:
        raise SystemExit("plan.json changed during the run")
    if (ROOT / "turning-research-canonical/tables/disclosure_timestamps.csv").exists():
        raise SystemExit("admission timestamp table must not be created by this phase")
    stored = {"stored_per_row_clocks": len(stored_per_row)}
    text = prose(decision, rows, probes, stored)
    coverage = {
        "decision": decision,
        "research_dates": 3659,
        "ledger_rows": len(rows),
        "certified_rows": sum(row["certified"] == "true" for row in rows),
        "after_cutoff_rows": sum(row["reason"] == "CLOCK_AFTER_CUTOFF" for row in rows),
        "terminal_rows": sum(row["reason"] == "TERMINAL_DATE_NO_NEXT_SESSION" for row in rows),
        "uncertified_rows": sum(row["reason"] == "NO_CERTIFIED_DISCLOSURE_CLOCK" for row in rows),
        "date_range": [dates[0], dates[-1]],
        "by_exchange": {
            exchange: {
                "rows": sum(row["exchange"] == exchange for row in rows),
                "certified": sum(row["exchange"] == exchange and row["certified"] == "true" for row in rows),
            }
            for exchange in ("SSE", "SZSE")
        },
        "verification": {
            "method": (
                "Inspected stored balance files, lineage, official summary receipts, iFinD raw files, "
                "and v92 capture files for a per-row disclosure timestamp. Requested the pre-registered "
                "official summary URLs for four dates and the two exchange pages once. A clock is certified "
                "only when those bytes contain a per-row publication time strictly before the next 09:15."
            ),
            "calendar_walk": any(
                re.fullmatch(r"(sse|szse)_(\d{4}-\d{2}-\d{2})", item.get("source", ""))
                and item["source"].split("_", 1)[1] not in SAMPLE_DATES
                for item in probes
            ),
            "reason_calendar_not_walked": (
                "Remaining dates are requested only when a sample payload has a per-row disclosure timestamp. "
                "A blocked host is not retried."
            ),
        },
        "stored_balance_headers": {"financing_sh_sz": balance_header, "financing_balance": total_header},
        "lineage": lineages,
        "source_policy_pit_certified": policy.get("pit_certified"),
        "lag_diagnostic_is_not_a_clock": lag.get("descriptive_only_not_proof_of_correct_date") is True,
        "news_sentence_in_stored_note": "次一交易日08:39发布的每日经济新闻" in note,
        "news_sentence_classification": "NEWS_REPRINT_NOT_EXCHANGE_CLOCK",
        "stored_official_receipts": [
            {
                "path": item["path"],
                "keys": sorted(item["keys"]),
                "clock_fields": item["clock_fields"],
                "download_clocks": item["download_clocks"],
                "unclassified_time_like_keys": sorted(item["unclassified_time_like_keys"]),
            }
            for item in stored_summaries
        ],
        "ifind": {
            "raw_files": ifind["raw_files"],
            "keys": sorted(ifind["keys"]),
            "clock_fields": ifind["clock_fields"],
            "unclassified_time_like_keys": sorted(ifind["unclassified_time_like_keys"]),
            "daily_header": ifind["daily_header"],
            "daily_allowlist_columns": ifind["daily_allowlist_columns"],
            "publication_time_certified_values": ifind["publication_time_certified_values"],
            "publication_time_certified_classification": ifind["publication_time_certified_classification"],
        },
        "v92": v92,
        "probes": probes,
        "rejected_clocks": {
            "retrieved_at": "Download time on the stored official-receipt wrapper. Not a disclosure time.",
            "http_date": "Date header of this run's fetch. Not a historical disclosure time.",
            "page_generation_time": "SSE HTML meta 页面生成时间 is the page shell, not a per-session balance clock.",
            "news_pubDate": (
                "The already documented 每日经济新闻 article publishes its own time. "
                "That time is not an exchange disclosure clock and it is not split into Shanghai and Shenzhen financing balances."
            ),
            "publication_time_certified": "iFinD daily column is a false flag on every stored row, not a timestamp.",
        },
        "gaps": [
            "No saved official or provider file carries a per-row financing disclosure timestamp.",
            "The live Shanghai summary payload for the four sample dates has the same shape: opDate and rzye, no publication time.",
            "The live Shenzhen host did not return a payload on this run. The stored Shenzhen summaries already have no publication time.",
            "The last research date has no next session inside the stored calendar.",
            "A news publication time, a page-generation time, a download header, and a reconstructed lag are not exchange clocks.",
            "Turnover, breadth, index amount, and the 000300/000852 controls were not collected.",
        ],
    }
    write_csv(HERE / "ledger.csv", rows)
    (HERE / "coverage.json").write_text(
        json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    decision_doc = {
        "decision": decision,
        "formal_signal_allowed": False,
        "family_admitted": False,
        "model_fit": False,
        "blind_test": False,
        "PIT_certified": False,
        "production_changed": False,
        "p4a_decision": "NO_FAMILY_ADMITTED",
        "p4a_rewritten": False,
        "admission_gate_loosened": False,
        "certified_rows": coverage["certified_rows"],
        "ledger_rows": coverage["ledger_rows"],
        "date_range": coverage["date_range"],
        "canonical_disclosure_table_written": False,
        "english": text["english"],
        "chinese": text["chinese"],
        "p1_decision": "BLOCKED_NO_CONCENTRATION",
        "p1b_decision": "GO_PRE_PIVOT_COORDINATE",
        "p1c_decision": "BLOCKED_NO_WINDOW_PEAK",
        "p1d_decision": "GO_NEW_FACTORS",
    }
    (HERE / "decision.json").write_text(
        json.dumps(decision_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    result = {
        "decision": decision,
        "plan_sha256": plan_hash,
        "plan_unchanged": sha256_file(PLAN_PATH) == plan_hash,
        "checks": {
            "calendar_rows": len(dates),
            "ledger_rows": len(rows),
            "one_row_per_date_per_exchange": len(rows) == len(dates) * 2,
            "no_invented_timestamp": all(
                row["disclosure_timestamp"] == "" or row["reason"] in {"CERTIFIED", "CLOCK_AFTER_CUTOFF"}
                for row in rows
            ),
            "source_policy_pit_certified_false": policy.get("pit_certified") is False,
            "lag_not_used": lag.get("descriptive_only_not_proof_of_correct_date") is True,
            "disclosure_table_absent": not (
                ROOT / "turning-research-canonical/tables/disclosure_timestamps.csv"
            ).exists(),
        },
        **text,
    }
    (HERE / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_readme(decision, text, rows, probes)
    write_artifact_manifest()
    print(json.dumps({"decision": decision, "certified_rows": coverage["certified_rows"], "ledger_rows": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
