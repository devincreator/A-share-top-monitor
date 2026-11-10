"""Rebuild the P4c inventory and decision from saved official bytes.

The script does not open a socket, does not edit plan.json, and does not fit a score.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ATTEMPTS = HERE / "attempts"
PLAN_PATH = HERE / "plan.json"

PUBLICATION_LABELS = {
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
    "PubDate",
}
ZONE_IN_TEXT = ("北京时间", "北京时", "Asia/Shanghai")
PAGE_SHELL_LABELS = {"页面生成时间", "createDate"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_plan() -> dict:
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def check_sources(plan: dict) -> None:
    mismatches = []
    for rel, expected in plan["source_sha256"].items():
        path = ROOT / rel
        if not path.is_file():
            mismatches.append(f"missing {rel}")
            continue
        actual = sha256_file(path)
        if actual != expected:
            mismatches.append(f"{rel} {actual}")
    if mismatches:
        sys.stderr.write("PLAN_SOURCE_CHANGED\n" + "\n".join(mismatches) + "\n")
        raise SystemExit(2)


def outside_minimum_items(plan: dict) -> list[str]:
    rel = "A-share-top-monitor-history/完整数据需求清单.md"
    text = (ROOT / rel).read_text(encoding="utf-8")
    marker = "不属于目前已确认的最低需求"
    if marker not in text:
        raise SystemExit("requirements note has no outside-minimum sentence")
    sentence = text.split(marker, 1)[0].split("。")[-1]
    sentence = sentence.replace("和", "、")
    items = [part.strip(" \n；;") for part in sentence.split("、")]
    items = [part for part in items if part]
    expected = ["新闻", "财报", "宏观", "资金流向", "Level-2", "分钟行情"]
    if items != expected:
        raise SystemExit(f"outside-minimum items changed: {items}")
    return items


def load_attempt(stem: str) -> dict:
    meta_path = ATTEMPTS / f"{stem}.meta.json"
    body_path = ATTEMPTS / f"{stem}.body"
    if not meta_path.is_file():
        raise SystemExit(f"missing attempt meta {stem}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    body = body_path.read_bytes() if body_path.is_file() else b""
    recorded = meta.get("body_sha256")
    if body and recorded and recorded != sha256_bytes(body):
        raise SystemExit(f"attempt body hash mismatch {stem}")
    if body and "body_bytes" in meta and meta["body_bytes"] != len(body):
        raise SystemExit(f"attempt body length mismatch {stem}")
    return {"stem": stem, "meta": meta, "body": body}


def as_text(body: bytes) -> str:
    for encoding in ("utf-8", "gb18030"):
        try:
            return body.decode(encoding)
        except UnicodeDecodeError:
            continue
    return body.decode("utf-8", errors="replace")


def as_json(attempt: dict):
    if not attempt["body"]:
        return None
    text = as_text(attempt["body"]).strip()
    if text.startswith("tabData"):
        text = text.split("=", 1)[1].strip()
        if text.endswith(";"):
            text = text[:-1].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def states_beijing(text: str) -> bool:
    return any(marker in text for marker in ZONE_IN_TEXT)


def value_carries_zone(value: str) -> bool:
    if any(marker in value for marker in ZONE_IN_TEXT):
        return True
    return bool(re.search(r"(?:Z|[+-]\d{2}:?\d{2})\s*$", value))


def walk_labeled(node, found: list[dict]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in PUBLICATION_LABELS or key in PAGE_SHELL_LABELS:
                found.append({"key": key, "value": value})
            walk_labeled(value, found)
    elif isinstance(node, list):
        for item in node:
            walk_labeled(item, found)


def all_keys(node, found: set[str], depth: int = 0) -> None:
    if depth > 8:
        return
    if isinstance(node, dict):
        for key, value in node.items():
            found.add(str(key))
            all_keys(value, found, depth + 1)
    elif isinstance(node, list):
        for item in node[:30]:
            all_keys(item, found, depth + 1)


def certify_labeled(key: str, value, file_text: str) -> dict:
    """A labeled field certifies a clock only under the frozen rule."""
    record = {
        "key": key,
        "value_type": type(value).__name__,
        "value_preview": value if isinstance(value, (str, int, float)) else None,
        "certified": False,
    }
    if key in PAGE_SHELL_LABELS or key == "页面生成时间":
        record["reason"] = "page_shell"
        return record
    if key not in PUBLICATION_LABELS:
        record["reason"] = "not_a_publication_label"
        return record
    if not isinstance(value, str):
        record["reason"] = "not_a_timezone_bearing_string"
        return record
    has_clock = bool(re.search(r"\d{1,2}:\d{2}", value))
    if not has_clock:
        record["reason"] = "no_time_of_day"
        return record
    if value_carries_zone(value) or states_beijing(file_text):
        record["certified"] = True
        record["reason"] = "meets_clock_rule_pending_deadline"
        return record
    record["reason"] = "no_timezone"
    return record


def result_rows(payload) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    rows = payload.get("result")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    data = payload.get("data")
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def summarize_attempt(attempt: dict) -> dict:
    meta = attempt["meta"]
    text = as_text(attempt["body"]) if attempt["body"] else ""
    payload = as_json(attempt)
    labeled: list[dict] = []
    if payload is not None:
        walk_labeled(payload, labeled)
    pubdates = re.findall(r'name="PubDate"\s+content="([^"]*)"', text)
    pubdates += re.findall(r'content="([^"]*)"\s+name="PubDate"', text)
    create_dates = re.findall(r'name="createDate"\s+content="([^"]*)"', text)
    page_shells = re.findall(r"页面生成时间\s*([0-9]{4}-[0-9]{2}-[0-9]{2}\s+[0-9:]{8})", text)
    for value in pubdates:
        labeled.append({"key": "PubDate", "value": value})
    judgments = [certify_labeled(item["key"], item["value"], text) for item in labeled]
    keys: list[str] = []
    if payload is not None:
        bucket: set[str] = set()
        all_keys(payload, bucket)
        keys = sorted(bucket)
    rows = result_rows(payload)
    row_keys = sorted(rows[0].keys()) if rows else []
    return {
        "stem": attempt["stem"],
        "url": meta.get("url"),
        "status": meta.get("status"),
        "error": meta.get("error"),
        "detail": meta.get("detail"),
        "body_bytes": len(attempt["body"]),
        "body_sha256": sha256_bytes(attempt["body"]) if attempt["body"] else None,
        "http_date": (meta.get("headers") or {}).get("Date"),
        "last_modified": (meta.get("headers") or {}).get("Last-Modified"),
        "states_beijing": states_beijing(text) if text else False,
        "publication_phrase_present": any(label in text for label in ("公布时间", "披露时间", "发布时间")),
        "page_shell_times": page_shells,
        "pubdates": pubdates,
        "create_dates": create_dates,
        "labeled_judgments": judgments,
        "certified_in_attempt": sum(1 for item in judgments if item["certified"]),
        "json_keys": keys,
        "row_count": len(rows) if payload is not None and (isinstance(payload, dict) and ("result" in payload or "data" in payload)) else None,
        "row_keys": row_keys,
        "top_fields": {
            key: payload.get(key)
            for key in ("report_date", "update_date", "print_date", "o_msg", "tradeDate")
            if isinstance(payload, dict) and key in payload and not isinstance(payload.get(key), (dict, list))
        },
    }


def calendar_facts() -> dict:
    path = ROOT / "turning-research-canonical/tables/research_inputs.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    dates = [row["date"] for row in rows]
    if dates != sorted(set(dates)):
        raise SystemExit("research calendar is not a unique ordered date list")
    if (dates[0], dates[-1], len(dates)) != ("2011-08-02", "2026-08-25", 3659):
        raise SystemExit("research calendar bounds changed")
    return {"rows": 3659, "non_terminal_rows": 3658, "start": dates[0], "end": dates[-1]}


def family_rows(summaries: dict[str, dict], outside_items: list[str]) -> list[dict]:
    def stems(*names: str) -> str:
        return " ".join(names)

    def row_keys(stem: str) -> str:
        return ",".join(summaries[stem]["row_keys"])

    hgt_empty = [
        stem
        for stem in ("sse_hgt_20110802", "sse_hgt_20200713", "sse_hgt_20210913")
        if summaries[stem]["row_count"] == 0
    ]
    hkex_status = {
        stem: summaries[stem]["status"]
        for stem in (
            "hkex_js_20210913",
            "hkex_js_20141117",
            "hkex_js_20240102",
            "hkex_js_20251106",
            "hkex_js_20260825",
            "hkex_js_20261106",
        )
    }
    hkex_keys = summaries["hkex_js_20260825"]["json_keys"]
    if hkex_keys != summaries["hkex_js_20261106"]["json_keys"]:
        raise SystemExit("HKEX daily files do not share one schema")
    if "date" not in hkex_keys or set(hkex_keys) & PUBLICATION_LABELS:
        raise SystemExit(f"HKEX keys need review: {hkex_keys}")
    shfe_updates = {
        stem: summaries[stem]["top_fields"]
        for stem in ("shfe_20110802", "shfe_20200713", "shfe_daily_20210913", "shfe_20260825", "ine_20210913")
    }
    cninfo = summaries["cninfo_20210913"]
    announcement_values = [
        item["value_preview"]
        for item in cninfo["labeled_judgments"]
        if item["key"] == "announcementTime"
    ]
    nbs_pubdates = {
        stem: summaries[stem]["pubdates"]
        for stem in ("nbs_cpi_20261109", "nbs_ppi_20261109", "nbs_price_20261103")
    }
    families = [
        {
            "family_id": "northbound_connect",
            "publisher": "SSE; HKEX",
            "field": "沪股通当日成交总额、成交笔数、ETF 成交额；港交所北向成交额与成交笔数",
            "clock_status": "NO_CERTIFIABLE_CLOCK",
            "coverage": "样本四日里上交所有一行的日期是 2026-08-25，其余三日 result 为空。港交所 2026-08-25 与 2026-11-06 返回日文件，2014-11-17、2021-09-13、2024-01-02、2025-11-06 为 404。认证 0/3658。",
            "blocker": (
                f"上交所空样本 {','.join(hgt_empty)}。2026-08-25 行字段 {row_keys('sse_hgt_20260825')}。"
                f"港交所状态 {hkex_status}。2026-08-25 与 2026-11-06 的键是 {hkex_keys}，其中 date 是交易日。"
                f"深交所沪深港通页面传输失败：{summaries['szse_hgt_page']['error']}。"
            ),
            "evidence_stems": stems(
                "sse_hgt_20110802",
                "sse_hgt_20200713",
                "sse_hgt_20210913",
                "sse_hgt_20260825",
                "hkex_js_20210913",
                "hkex_js_20141117",
                "hkex_js_20240102",
                "hkex_js_20251106",
                "hkex_js_20260825",
                "hkex_js_20261106",
                "szse_hgt_page",
            ),
        },
        {
            "family_id": "exchange_market_statistics",
            "publisher": "SSE; SZSE",
            "field": "上交所每日成交概况（市值、成交、市盈率、换手）；深交所市场总貌目录 1803_sczm",
            "clock_status": "NO_CERTIFIABLE_CLOCK",
            "coverage": "上交所样本四日里只有 2026-08-25 返回行。深交所数据接口没有连上。认证 0/3658。",
            "blocker": (
                f"2026-08-25 行字段 {row_keys('sse_mrgk_20260825')}。2011-08-02、2020-07-13、2021-09-13 的 result 长度为 0。"
                f"深交所接口 {summaries['szse_api_sczm']['error']}：{summaries['szse_api_sczm']['detail']}。"
                "页面壳只有目录编号，没有逐日公布时间。没有改走其他主机。"
            ),
            "evidence_stems": stems(
                "sse_mrgk_20110802",
                "sse_mrgk_20200713",
                "sse_mrgk_20210913",
                "sse_mrgk_20260825",
                "szse_api_sczm",
                "szse_daily_page",
                "sse_overview_page",
            ),
        },
        {
            "family_id": "csi_other_daily",
            "publisher": "CSI",
            "field": "中证全债 H11001 的日行情，对照已保存的 000985 同一接口",
            "clock_status": "NO_CERTIFIABLE_CLOCK",
            "coverage": "抽查 2021-09-13 单日。接口按交易日返回行情。认证 0/3658。",
            "blocker": (
                f"000985 行字段 {row_keys('csi_oneday')}。H11001 行字段 {row_keys('csi_bond_oneday')}。"
                "两边都是 tradeDate 加行情，没有公布时间。这不是把成交额或 000300/000852 再跑一遍。"
            ),
            "evidence_stems": stems("csi_oneday", "csi_bond_oneday", "csi_home"),
        },
        {
            "family_id": "announcement_disclosure",
            "publisher": "cninfo",
            "field": "单份公司公告的 announcementTime，不是指数的一个交易日字段",
            "clock_status": "NO_CERTIFIABLE_CLOCK",
            "coverage": "2021-09-13 的一页返回 5 条公告，当日公告总数 702。没有收成研究日历上的逐日字段。认证 0/3658。",
            "blocker": (
                f"announcementTime 取值 {announcement_values}，类型是整数，正文没有时区。"
                "storageTime 在这 5 条里没有单独的钟点字符串。这是公司文件的时间，不是 000985 的一个交易日字段，本轮不把公告收成指数因子。"
            ),
            "evidence_stems": stems("cninfo_20210913"),
        },
        {
            "family_id": "futures_options_daily",
            "publisher": "SHFE; INE; CFFEX; CZCE; GFEX; DCE",
            "field": "交易所日行情：结算、成交量、持仓量",
            "clock_status": "NO_CERTIFIABLE_CLOCK",
            "coverage": "上期所四个样本日和上海国际能源交易中心 2021-09-13 的日文件已保存。中金所 HTTPS 超时、HTTP 有 CSV。郑商所有当日行情表。广期所页面是壳。大商所 HTTPS 超时、HTTP 412。认证 0/3658。",
            "blocker": (
                f"上期所与能源中心文件字段 {shfe_updates}。update_date 和 print_date 没有时区。"
                "2011-08-02 的 update_date 与 print_date 都落在 2015-06-05，所以这两个字段不是该交易日的公布时间。"
                f"中金所 HTTPS {summaries['cffex_csv_20210913']['error']}。HTTP CSV 表头没有时间列。"
                f"大商所 HTTPS {summaries['dce_https_home']['error']}，HTTP 状态 {summaries['dce_page']['status']}。"
                f"广期所页面生成时间 {summaries['gfex_page']['page_shell_times']}，这是页面模板时间。"
                "没有改走其他主机。日周数据页和交易时间页的正文没有“北京时间”。"
            ),
            "evidence_stems": stems(
                "shfe_20110802",
                "shfe_20200713",
                "shfe_daily_20210913",
                "shfe_20260825",
                "shfe_daily_page",
                "shfe_hours_page",
                "ine_20210913",
                "cffex_csv_20210913",
                "cffex_http_csv",
                "czce_20210913",
                "gfex_page",
                "dce_page",
                "dce_https_home",
            ),
        },
        {
            "family_id": "news",
            "publisher": "SSE",
            "field": "交易所新闻稿列表上的日期",
            "clock_status": "NO_CERTIFIABLE_CLOCK",
            "coverage": "新闻在需求清单的最低集之外。已保存的是上交所媒体中心列表。认证 0/3658。",
            "blocker": (
                f"页面生成时间 {summaries['sse_news_page']['page_shell_times']}。"
                "列表上的标记是日期，没有带时区的发表钟点。稿件日期不是指数的一个交易日字段。"
            ),
            "evidence_stems": stems("sse_news_page"),
        },
        {
            "family_id": "financial_statements",
            "publisher": "cninfo",
            "field": "公司财报公告，与公告家族同一份样本",
            "clock_status": "NO_CERTIFIABLE_CLOCK",
            "coverage": "财报在需求清单的最低集之外。样本与 announcement_disclosure 相同。认证 0/3658。",
            "blocker": "公司公告的 announcementTime 是无时区整数。没有一份带时区的、对齐研究日的指数级财报字段。本轮不下载全部历史公告。",
            "evidence_stems": stems("cninfo_20210913"),
        },
        {
            "family_id": "macro",
            "publisher": "NBS; PBOC",
            "field": "统计局数据发布稿；人民银行调查统计司栏目页",
            "clock_status": "NO_CERTIFIABLE_CLOCK",
            "coverage": "宏观不是研究日历上的每个交易日都发布。抽查了 2026 年 11 月三篇统计局稿件，2021 年 9 月的旧地址返回 404。认证 0/3658。",
            "blocker": (
                f"PubDate {nbs_pubdates}。三篇都没有“北京时间”。"
                f"调查统计司栏目页 createDate {summaries['pbc_stats']['create_dates']}，这是整页的一个时间，不是逐次发布的时钟。"
                f"2021 年样本地址状态 {summaries['nbs_old_try']['status']}。"
            ),
            "evidence_stems": stems(
                "nbs_zxfb",
                "nbs_cpi_20261109",
                "nbs_ppi_20261109",
                "nbs_price_20261103",
                "nbs_old_try",
                "pbc_stats",
            ),
        },
        {
            "family_id": "fund_flow",
            "publisher": "SSE page scripts; no separate official flow field found",
            "field": "清单中的资金流向。北向成交已在 northbound_connect 单独登记",
            "clock_status": "NO_CERTIFIABLE_CLOCK",
            "coverage": "已保存的上交所查询脚本里没有另一套资金流向接口。认证 0/3658。",
            "blocker": "没有找到带逐日公布时间的官方资金流向字段。供应商资金流页面不作为官方时钟。",
            "evidence_stems": stems("sse_js_hgt", "sse_js_stock", "sse_js_table", "sse_publicdata_page"),
        },
        {
            "family_id": "level2",
            "publisher": "SSE public-data catalog",
            "field": "清单中的 Level-2",
            "clock_status": "NO_CERTIFIABLE_CLOCK",
            "coverage": "公开数据目录页没有历史 Level-2 的逐日公布时间。认证 0/3658。",
            "blocker": (
                f"目录页的页面生成时间 {summaries['sse_publicdata_page']['page_shell_times']}。"
                "没有保存到带时区的历史逐笔公布记录。没有使用非官方镜像。"
            ),
            "evidence_stems": stems("sse_publicdata_page"),
        },
        {
            "family_id": "minute_bars",
            "publisher": "SSE public-data catalog",
            "field": "清单中的分钟行情",
            "clock_status": "NO_CERTIFIABLE_CLOCK",
            "coverage": "公开数据目录页没有历史分钟线的逐日公布时间。认证 0/3658。",
            "blocker": "分钟行情会落回价格家族，而且已保存的官方目录没有逐日、带时区的公布时间。本轮不下载分钟线。",
            "evidence_stems": stems("sse_publicdata_page", "sse_overview_page"),
        },
    ]
    by_id = {item["family_id"]: item for item in families}
    expected_ids = [
        "northbound_connect",
        "exchange_market_statistics",
        "csi_other_daily",
        "announcement_disclosure",
        "futures_options_daily",
        "news",
        "financial_statements",
        "macro",
        "fund_flow",
        "level2",
        "minute_bars",
    ]
    mapping = {
        "新闻": "news",
        "财报": "financial_statements",
        "宏观": "macro",
        "资金流向": "fund_flow",
        "Level-2": "level2",
        "分钟行情": "minute_bars",
    }
    if [mapping[item] for item in outside_items] != expected_ids[5:]:
        raise SystemExit("outside-minimum family order drifted")
    if list(by_id) != expected_ids:
        raise SystemExit("family order drifted")
    return families


def cffex_header(attempt: dict) -> str:
    if not attempt["body"]:
        return ""
    line = attempt["body"].splitlines()[0]
    return line.decode("gb18030", errors="replace")


def czce_title(attempt: dict) -> str:
    if not attempt["body"]:
        return ""
    return as_text(attempt["body"]).splitlines()[0].strip()


def write_inventory(families: list[dict]) -> None:
    path = HERE / "inventory.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["family_id", "publisher", "field", "clock_status", "coverage", "blocker", "evidence_stems"],
        )
        writer.writeheader()
        writer.writerows(families)


def decision_text(calendar: dict, families: list[dict], certified: int) -> dict:
    searched = len(families)
    english = (
        f"NO_CERTIFIABLE_FAMILY. Certified pre-09:15 clocks: {certified}/{calendar['non_terminal_rows']} "
        f"non-terminal research dates from {calendar['start']} to {calendar['end']} "
        f"({calendar['rows']} rows, the last date has no next session). "
        f"Families searched: {searched}. Families with a certifiable clock: 0. Families collected: 0. "
        "SSE northbound and SSE daily market statistics return tradeDate and values on 2026-08-25 and no publication time; "
        "the 2011-08-02, 2020-07-13, and 2021-09-13 queries returned empty results. "
        "HKEX daily files that returned HTTP 200 carry a trading date and no publication time; "
        "2014-11-17, 2021-09-13, 2024-01-02, and 2025-11-06 returned HTTP 404. "
        "CSI 000985 and H11001 rows are tradeDate plus prices. "
        "cninfo announcementTime values are integers with no timezone, on company documents, not a session-level index field. "
        "SHFE update_date and print_date have no timezone; on 2011-08-02 both read 2015-06-05, so they are file update times. "
        "The saved SHFE daily-data page and trading-hours page do not contain 北京时间. "
        "CFFEX HTTPS timed out and the HTTP CSV has no time column. DCE HTTPS timed out and the HTTP page returned 412. "
        "SZSE API requests failed the TLS handshake. No second host was used. "
        "NBS PubDate values have no timezone. The PBOC createDate is one time on a section page. "
        "SSE news dates and 页面生成时间 are not session clocks. "
        "No family was admitted and no score was fit. formal_signal_allowed stays false. "
        "This is not PIT, not a blind test, and not a formal signal. "
        "P4a remains NO_FAMILY_ADMITTED. P4b remains CLOCKS_UNAVAILABLE. "
        "P1 remains BLOCKED_NO_CONCENTRATION. P1b remains GO_PRE_PIVOT_COORDINATE. "
        "P1c remains BLOCKED_NO_WINDOW_PEAK. P1d remains GO_NEW_FACTORS."
    )
    chinese = (
        f"NO_CERTIFIABLE_FAMILY。认证的、早于下一研究日 09:15 的披露时点是 {certified}/{calendar['non_terminal_rows']} "
        f"（研究日历 {calendar['start']} 至 {calendar['end']} 共 {calendar['rows']} 日，最后一日没有下一交易日）。"
        f"检索家族 {searched} 个。有可认证时钟的家族 0 个。本轮收集的家族 0 个。"
        "上交所沪股通和每日成交概况在 2026-08-25 返回交易日和数值，没有公布时间；2011-08-02、2020-07-13、2021-09-13 的结果为空。"
        "港交所返回 HTTP 200 的日文件只有交易日，没有公布时间；2014-11-17、2021-09-13、2024-01-02、2025-11-06 为 HTTP 404。"
        "中证指数 000985 与中证全债 H11001 的行是交易日加行情。"
        "巨潮公告的 announcementTime 是没有时区的整数，挂在公司文件上，不是指数的一个交易日字段。"
        "上期所 update_date 和 print_date 没有时区；2011-08-02 这两项都是 2015-06-05，所以它们是文件更新时间。"
        "已保存的上期所日周数据页和交易时间页没有“北京时间”。"
        "中金所 HTTPS 超时，HTTP CSV 没有时间列。大商所 HTTPS 超时，HTTP 页面状态 412。"
        "深交所数据接口 TLS 握手失败。没有改用另一台主机。"
        "统计局 PubDate 没有时区。人民银行 createDate 是栏目页上的一个时间。"
        "上交所新闻列表上的日期和页面生成时间不是交易日字段的披露时钟。"
        "没有准入任何家族，也没有拟合分数。formal_signal_allowed 仍为 false。"
        "这不是 PIT，不是盲测，也不是正式信号。"
        "P4a 仍是 NO_FAMILY_ADMITTED。P4b 仍是 CLOCKS_UNAVAILABLE。"
        "P1 仍是 BLOCKED_NO_CONCENTRATION。P1b 仍是 GO_PRE_PIVOT_COORDINATE。"
        "P1c 仍是 BLOCKED_NO_WINDOW_PEAK。P1d 仍是 GO_NEW_FACTORS。"
    )
    return {"english": english, "chinese": chinese}


def write_readme(calendar: dict, families: list[dict], certified: int) -> None:
    lines = [
        "# P4c 扩大官方家族的披露时钟检索",
        "",
        f"**结论：`NO_CERTIFIABLE_FAMILY`。** 认证时钟 {certified}/{calendar['non_terminal_rows']}。研究日历 {calendar['start']} 至 {calendar['end']} 共 {calendar['rows']} 日，最后一日没有下一交易日，可认证上限是 {calendar['non_terminal_rows']} 日。检索 {len(families)} 个家族，可认证时钟的家族是 0 个，本轮收集的家族是 0 个。",
        "",
        "这一步只回答：现有仓库里的非价格家族已经过了 P4a 和 P4b 之后，官方来源里还有没有一个家族，能拿出发布者自己的、带时区的、严格早于下一研究日上海时间 09:15 的公布时间。`formal_signal_allowed` 仍为 false。没有拟合，没有准入。这不是 PIT，不是盲测，也不是正式信号。",
        "",
        "## 时钟规则",
        "",
        "时钟必须来自发布者自己的正文，或同一发布者的正式发布时间记录。它要带时区，或者同一份官方证据写明北京时间、北京时或 Asia/Shanghai。观察日必须早于决策日 D。公布时间必须严格早于 `research_inputs.csv` 下一行的上海时间 09:15。最后一日 2026-08-25 没有下一行，不为它编造交易日。",
        "",
        "日程、2026 年的下载或捕获时间、HTTP Date、页面生成时间、供应商转载、数据来源、参数“最新”、插值日期，都不是时钟。",
        "",
        "## 检索结果",
        "",
        "| 家族 | 发布者 | 时钟 | 覆盖 |",
        "|---|---|---|---|",
    ]
    for item in families:
        lines.append(
            f"| `{item['family_id']}` | {item['publisher']} | `{item['clock_status']}` | {item['coverage']} |"
        )
    lines.extend(
        [
            "",
            "各行的缺口写在 `inventory.csv` 的 `blocker` 列。原始正文、URL、HTTP 状态和 SHA256 在 `attempts/`，摘要在 `evidence.json`。",
            "",
            "上期所日文件里能看到 `update_date` 和 `print_date`。2011-08-02 的两项都是 2015-06-05 15:33:53 与 2015-06-05 16:10:15，晚于该交易日多年，因此它们记录的是文件更新，不是该日行情的公布时间。其余样本日的钟点也没有时区，已保存的日周数据页和交易时间页没有“北京时间”。",
            "",
            "巨潮 2021-09-13 的 `announcementTime` 是整数。正文没有说明时区。这些行是公司公告，不是中证全指的一个交易日字段，所以没有把历史公告全部收进来。",
            "",
            "深交所数据接口、中金所 HTTPS、大商所 HTTPS 的传输失败都记在对应的 meta 里。没有换主机，也没有用非官方镜像代替。",
            "",
            "## 没有做的事",
            "",
            "- 没有改写 `plan.json`。计划在读取这些证据之前已经提交。",
            "- 没有收集任何一个家族的全历史，因为没有任何一个家族通过时钟规则。",
            "- 没有重查融资余额。P4b 已经得到 `CLOCKS_UNAVAILABLE`。没有重跑成交额和 000300/000852。",
            "- 没有把换手率、成分广度、peg、consNumber 或价格变换重新打开。`return3` 和 `change_in_return3` 没有加回。",
            "- 没有拟合分数，没有打开 P2，没有提高阈值。",
            "- 没有写入 `turning-research-canonical/tables/disclosure_timestamps.csv`。",
            "- 没有修改生产页面、采集器或正式信号，没有恢复旧 V 系列。",
            "- P1 仍是 `BLOCKED_NO_CONCENTRATION`。P1b 仍是 `GO_PRE_PIVOT_COORDINATE`。P1c 仍是 `BLOCKED_NO_WINDOW_PEAK`。P1d 仍是 `GO_NEW_FACTORS`。P4a 仍是 `NO_FAMILY_ADMITTED`。P4b 仍是 `CLOCKS_UNAVAILABLE`。",
            "",
            "## 复算",
            "",
            "在仓库根目录运行：",
            "",
            "```text",
            "python -B dual80-research/p4c_external_clock_feasibility/survey.py --offline",
            "```",
            "",
            "脚本只读 `plan.json` 和 `attempts/` 里的原始正文，核对计划里的 SHA256，重写本目录的清单、证据、结论和本页。它不联网。`--offline` 与不加参数是同一条路径。原始回执已经保存在 `attempts/`，缺文件时脚本会停，不会补造时点。",
            "",
        ]
    )
    (HERE / "README.md").write_text("\n".join(lines), encoding="utf-8")


def write_artifact_manifest() -> None:
    files = sorted(
        path
        for path in HERE.rglob("*")
        if path.is_file() and path.name != "artifact_manifest.json" and "__pycache__" not in path.parts
    )
    manifest = {
        str(path.relative_to(HERE)): {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in files
    }
    (HERE / "artifact_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    if any(arg not in {"--offline"} for arg in sys.argv[1:]):
        raise SystemExit("only --offline is accepted; this script does not open a socket")
    plan_before = sha256_file(PLAN_PATH)
    plan = load_plan()
    check_sources(plan)
    outside_items = outside_minimum_items(plan)
    calendar = calendar_facts()
    stems = sorted(path.name[: -len(".meta.json")] for path in ATTEMPTS.glob("*.meta.json"))
    attempts = [load_attempt(stem) for stem in stems]
    summaries = {item["stem"]: summarize_attempt(item) for item in attempts}
    certified_hits = [
        {"stem": stem, "judgment": judgment}
        for stem, summary in summaries.items()
        for judgment in summary["labeled_judgments"]
        if judgment["certified"]
    ]
    if certified_hits:
        sys.stderr.write("CERTIFIABLE_CLOCK_FOUND\n" + json.dumps(certified_hits, ensure_ascii=False) + "\n")
        raise SystemExit(3)
    if any(summary["states_beijing"] for summary in summaries.values()):
        raise SystemExit("a saved body states Beijing time; review it before calling the family uncertifiable")
    if any(summary["publication_phrase_present"] for summary in summaries.values()):
        raise SystemExit("a saved body contains 公布时间/披露时间/发布时间; review it before a negative decision")
    header = cffex_header(load_attempt("cffex_http_csv"))
    if "时间" in header:
        raise SystemExit(f"CFFEX header contains 时间: {header}")
    families = family_rows(summaries, outside_items)
    certified = 0
    texts = decision_text(calendar, families, certified)
    decision = {
        "decision": "NO_CERTIFIABLE_FAMILY",
        "formal_signal_allowed": False,
        "family_admitted": False,
        "model_fit": False,
        "blind_test": False,
        "PIT_certified": False,
        "production_changed": False,
        "p4a_decision": "NO_FAMILY_ADMITTED",
        "p4b_decision": "CLOCKS_UNAVAILABLE",
        "p4a_rewritten": False,
        "p4b_rewritten": False,
        "admission_gate_loosened": False,
        "certified_rows": certified,
        "non_terminal_research_dates": calendar["non_terminal_rows"],
        "research_dates": calendar["rows"],
        "coverage": f"{certified}/{calendar['non_terminal_rows']}",
        "families_searched": len(families),
        "families_with_certifiable_clock": 0,
        "families_collected": 0,
        "deferred_families": [],
        "date_range": [calendar["start"], calendar["end"]],
        "canonical_disclosure_table_written": False,
        "english": texts["english"],
        "chinese": texts["chinese"],
        "p1_decision": "BLOCKED_NO_CONCENTRATION",
        "p1b_decision": "GO_PRE_PIVOT_COORDINATE",
        "p1c_decision": "BLOCKED_NO_WINDOW_PEAK",
        "p1d_decision": "GO_NEW_FACTORS",
    }
    evidence = {
        "phase": "P4c",
        "decision": decision["decision"],
        "calendar": calendar,
        "outside_minimum_items": outside_items,
        "certified_rows": certified,
        "coverage": decision["coverage"],
        "beijing_time_phrase_in_any_saved_body": False,
        "publication_phrase_in_any_saved_body": False,
        "cffex_http_header": header,
        "czce_title": czce_title(load_attempt("czce_20210913")),
        "shfe_file_times": {
            stem: summaries[stem]["top_fields"]
            for stem in ("shfe_20110802", "shfe_20200713", "shfe_daily_20210913", "shfe_20260825", "ine_20210913")
        },
        "not_reopened": [
            "financing_balance",
            "turnover_rate",
            "market_breadth_rebuilt_from_constituents",
            "index_trading_amount",
            "style_000300_000852",
            "peg_and_consNumber",
            "price_transforms",
        ],
        "http_date_and_last_modified_are_not_clocks": True,
        "families": families,
        "attempts": [
            {
                "stem": summary["stem"],
                "url": summary["url"],
                "status": summary["status"],
                "error": summary["error"],
                "detail": summary["detail"],
                "body_bytes": summary["body_bytes"],
                "body_sha256": summary["body_sha256"],
                "states_beijing": summary["states_beijing"],
                "page_shell_times": summary["page_shell_times"],
                "pubdates": summary["pubdates"],
                "create_dates": summary["create_dates"],
                "row_count": summary["row_count"],
                "row_keys": summary["row_keys"],
                "json_keys": summary["json_keys"],
                "top_fields": summary["top_fields"],
                "labeled_judgments": summary["labeled_judgments"],
                "certified_in_attempt": summary["certified_in_attempt"],
            }
            for summary in (summaries[stem] for stem in stems)
        ],
    }
    result = {
        "phase": "P4c",
        "decision": "NO_CERTIFIABLE_FAMILY",
        "certified_rows": certified,
        "non_terminal_research_dates": calendar["non_terminal_rows"],
        "coverage": decision["coverage"],
        "families_searched": len(families),
        "families_collected": 0,
        "formal_signal_allowed": False,
        "family_admitted": False,
        "model_fit": False,
        "blind_test": False,
        "PIT_certified": False,
    }
    write_inventory(families)
    (HERE / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (HERE / "decision.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (HERE / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_readme(calendar, families, certified)
    if sha256_file(PLAN_PATH) != plan_before:
        raise SystemExit("plan.json changed while surveying")
    write_artifact_manifest()
    print(json.dumps({"decision": decision["decision"], "coverage": decision["coverage"], "families": len(families)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
