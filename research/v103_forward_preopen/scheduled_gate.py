#!/usr/bin/env python3
"""Verify saved scheduled evidence; never confuse CI success with source observation."""
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from first_capture import verify_first_capture

PASS = "PASS_PREOPEN_RAW_SOURCE_OBSERVED_RESEARCH_ONLY"

def check(root, decision_date):
    folder = Path(root) / decision_date
    manifest = folder / "first_capture.json"
    source = folder / "official_index_raw.json"
    if not manifest.is_file():
        return False, "MISSING_MANIFEST"
    try:
        obj = json.loads(manifest.read_text(encoding="utf-8"))
        if obj["decision_date"] != decision_date:
            return False, "DATE_MISMATCH"
        readback = verify_first_capture(manifest, source)
        if readback["status"] != PASS:
            return False, obj.get("reason") or "BLOCKED"
        return True, "PASS_RESEARCH_ONLY"
    except (OSError, ValueError, KeyError, TypeError) as error:
        return False, "READBACK_ERROR_" + type(error).__name__

if __name__ == "__main__":
    day = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    ok, reason = check("research/v103_forward_preopen/observations", day)
    label = "PASS_RESEARCH_ONLY" if ok else "BLOCKED"
    print(f"V103 {day}: {label} ({reason})")
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(f"### V103 first-observation gate\n\nDate: {day}  \nStatus: **{label}**  \nReason: {reason}\n")
    if not ok:
        print(f"::error::Scheduled source evidence BLOCKED: {reason}")
    raise SystemExit(0 if ok else 1)
