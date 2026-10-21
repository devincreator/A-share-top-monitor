#!/usr/bin/env python3
"""V97: strict, source-hashed event replay bundle intake (not event generation).

Refuses to invent dated alerts from aggregate TP/FP counts. CSI300 research
cannot be silently relabeled as the 000985 CSI All Share 5/9 main test track.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tempfile
import zipfile
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"v86_event_models"))
from input_inventory import inspect_inputs

REQUIRED={"alerts.csv","pivots.csv","prices.csv","manifest.json"}
MAX_MEMBER_BYTES=30_000_000
MAX_TOTAL_BYTES=90_000_000
ALLOWED_TRACKS=("000985.CSI","000300.CSI")
EXPECTED_LABELS={"000985.CSI":"V52","000300.CSI":"LONG_CSI300"}
MAIN_TRACK="000985.CSI"


def checksum(raw):
    return hashlib.sha256(raw).hexdigest()


def check_bundle(path):
    result={"status":"BLOCKED_BUNDLE_MISSING","research_only":True,
            "main_track_replay_allowed":False,"formal_signal_allowed":False,
            "source_bundle":str(path),"errors":[]}
    source=Path(path)
    if not source.is_file():
        result["errors"].append("original V63/V68 event-level replay bundle not available")
        return result
    result["source_zip_sha256"]=checksum(source.read_bytes())
    try:
        with zipfile.ZipFile(source) as archive:
            names=archive.namelist()
            if len(names)!=len(set(names)):
                raise ValueError("duplicate ZIP entry")
            for info in archive.infolist():
                parts=PurePosixPath(info.filename)
                if (info.filename.startswith("/") or ".." in parts.parts or
                    info.is_dir() or info.file_size>MAX_MEMBER_BYTES):
                    raise ValueError("unsafe archive entry")
            if sum(x.file_size for x in archive.infolist())>MAX_TOTAL_BYTES:
                raise ValueError("archive exceeds bounded size")
            if set(names)!=REQUIRED:
                raise ValueError(f"bundle entries must be exactly {sorted(REQUIRED)}")
            document={k:archive.read(k) for k in names}
    except (zipfile.BadZipFile,ValueError,RuntimeError,OSError) as exc:
        result["status"]="BLOCKED_ARCHIVE_INVALID"
        result["errors"].append(str(exc)[:250])
        return result
    try:
        manifest=json.loads(document["manifest.json"])
        track=manifest["index_instrument"]
        label=manifest["label_version"]
        result["index_instrument"]=track
        result["label_version"]=label
        if track not in ALLOWED_TRACKS or label!=EXPECTED_LABELS[track]:
            raise ValueError("unverified index identity or frozen label engine")
        if not isinstance(manifest.get("source_code_commit"),str) or len(manifest["source_code_commit"])<8:
            raise ValueError("original source code commit not supplied")
        expected=manifest["sha256"]
        for name in ("alerts.csv","pivots.csv","prices.csv"):
            if checksum(document[name])!=expected[name]:
                raise ValueError(f"raw SHA256 mismatch for {name}")
        with tempfile.TemporaryDirectory() as tmp:
            location=Path(tmp)
            for name in ("alerts.csv","pivots.csv","prices.csv"):
                (location/name).write_bytes(document[name])
            check=inspect_inputs(location/"alerts.csv",location/"pivots.csv",location/"prices.csv")
        result["input_inventory"]={"status":check["status"],"issues":check["issues"],
            "row_counts":{name:record["rows"] for name,record in check["files"].items()}}
        if check["status"]!="INPUT_SCHEMA_READY_NOT_YET_AUDITED":
            raise ValueError("event and price input schema failed structural validation")
        # Explicit FORMAL_START and objective pivot confirmation required.
        alert_rows=list(csv.DictReader(io.StringIO(document["alerts.csv"].decode("utf-8-sig"))))
        pivot_rows=list(csv.DictReader(io.StringIO(document["pivots.csv"].decode("utf-8-sig"))))
        if "event_type" not in (alert_rows[0] if alert_rows else {}):
            raise ValueError("FORMAL_START evidence column is missing")
        if any(r["event_type"]!="FORMAL_START" for r in alert_rows):
            raise ValueError("non-FORMAL_START alerts in bundle")
        if "confirmation_date" not in (pivot_rows[0] if pivot_rows else {}):
            raise ValueError("mature objective pivot confirmation date absent")
        result["source_file_hashes"]={n:checksum(document[n]) for n in (
            "alerts.csv","pivots.csv","prices.csv")}
        result["status"]=("MAIN_INDEX_BUNDLE_INTAKE_SCHEMA_VALID_NOT_PIT"
                          if track==MAIN_TRACK else "CSI300_SEPARATE_RESEARCH_TRACK_ONLY")
        result["main_track_replay_allowed"]=False
        result["reason_not_promoted"]=(
            "Schema and SHA only: original model/alert source provenance, "
            "pivot maturity, PIT and historical as-of evidence not independently proven")
    except (ValueError,KeyError,TypeError,UnicodeDecodeError,json.JSONDecodeError) as exc:
        result["status"]="BLOCKED_CONTENT_OR_PROVENANCE"
        result["errors"].append(str(exc)[:250])
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--bundle",default="research/v97_event_intake/original_v68_event_replay.zip")
    p.add_argument("--output",default="v97_event_intake_output/source_status.json")
    args=p.parse_args()
    out=check_bundle(args.bundle)
    dest=Path(args.output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:out[k] for k in ("status","main_track_replay_allowed","formal_signal_allowed")},
                     ensure_ascii=False))
    return 0  # Missing historical evidence is a scientific blocker, not a CI crash.


if __name__=="__main__":
    raise SystemExit(main())
