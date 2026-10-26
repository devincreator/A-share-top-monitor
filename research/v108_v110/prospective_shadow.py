#!/usr/bin/env python3
"""V108/V110: immutable prospective *research* shadow, no production signals."""
import argparse
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/"v103_forward_preopen"))
from first_capture import verify_first_capture, parse_official, CODE, ZONE

REQUIRED="PASS_PREOPEN_RAW_SOURCE_OBSERVED_RESEARCH_ONLY"
VERSION="V108_PRICE_STATE_CANDIDATE_PREDECLARED_20261022"
PARAMS={"lookback":63,"momentum":20,"short":5,"high_position":0.8,"low_position":0.2}
PARAM_SHA=hashlib.sha256(json.dumps(PARAMS,sort_keys=True).encode()).hexdigest()

def signal_from_raw(raw, d):
    doc=json.loads(raw)
    pairs=sorted((str(x["tradeDate"]),Decimal(str(x["close"])))
        for x in doc["data"] if str(x.get("indexCode"))==CODE and
        date.fromisoformat(str(x["tradeDate"])[:4]+"-"+str(x["tradeDate"])[4:6]+"-"+str(x["tradeDate"])[6:]) < d and
        date.fromisoformat(str(x["tradeDate"])[:4]+"-"+str(x["tradeDate"])[4:6]+"-"+str(x["tradeDate"])[6:]).weekday()<5)
    prices=[v for _,v in pairs]
    if len(prices)<127: raise ValueError("INSUFFICIENT_PAST_CLOSES")
    window=prices[-63:]
    high,low=max(window),min(window)
    pos=(prices[-1]-low)/(high-low) if high!=low else Decimal(".5")
    ret5=prices[-1]/prices[-6]-1
    ret20=prices[-1]/prices[-21]-1
    ret63=prices[-1]/prices[-64]-1
    if pos>=Decimal(".8") and ret20>0 and ret5>0: state="UPTREND"
    elif pos<=Decimal(".2") and ret20<0 and ret5<0: state="DOWNTREND"
    elif ret20<0 and ret5>0: state="BOUNCE_IN_WEAK_TREND"
    elif ret20>0 and ret5<0: state="PULLBACK_IN_STRONG_TREND"
    else: state="MIXED"
    return {"state":state,"position_63":str(pos),"ret5":str(ret5),
            "ret20":str(ret20),"ret63":str(ret63),
            "asof_last_close":pairs[-1][0]}

def build_record(manifest_path, raw_path, *, now=None):
    manifest_path=Path(manifest_path)
    raw_path=Path(raw_path)
    audit=verify_first_capture(manifest_path,raw_path)
    if audit["status"]!=REQUIRED: raise ValueError("SOURCE_GATE_BLOCKED")
    manifest=json.loads(manifest_path.read_text())
    d=date.fromisoformat(manifest["decision_date"])
    # A shadow run cannot claim to have existed by 09:20 if produced later.
    now=now or datetime.now(timezone.utc)
    local=now.astimezone(ZONE)
    if local.date()!=d or not (local.hour==9 and local.minute<20):
        raise ValueError("SHADOW_AFTER_DECISION_CUTOFF")
    if now.astimezone(timezone.utc) < datetime.fromisoformat(manifest["response_completed_at_utc"]).astimezone(timezone.utc):
        raise ValueError("SHADOW_BEFORE_CAPTURE")
    raw=raw_path.read_bytes()
    parse_official(raw,d)
    return {"schema":"V108_RESEARCH_SHADOW_V1","model_version":VERSION,
            "parameters_sha256":PARAM_SHA,"decision_date":d.isoformat(),
            "created_at_utc":now.astimezone(timezone.utc).isoformat(),
            "source_manifest_sha256":audit["manifest_sha256"],"source_raw_sha256":audit["raw_sha256"],
            "source_pit_status":"FIRST_OBSERVED_ONLY_NOT_HISTORICAL_PUBLISHER_PIT",
            "status":"UNSCORED_PENDING_FUTURE_OUTCOME","research_only":True,
            "formal_signal_allowed":False,"production_updated":False,
            "candidate":signal_from_raw(raw,d)}

def write_once(record,path):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    payload=(json.dumps(record,sort_keys=True,indent=2)+"\n").encode()
    with path.open("xb") as f:f.write(payload)
    return hashlib.sha256(payload).hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--capture-root",required=True)
    ap.add_argument("--output-root",required=True)
    args=ap.parse_args()
    day=datetime.now(ZONE).date().isoformat()
    folder=Path(args.capture_root)/day
    record=build_record(folder/"first_capture.json",folder/"official_index_raw.json")
    output=Path(args.output_root)/day/"shadow.json"
    print("RESEARCH_SHADOW_WRITTEN",write_once(record,output))
if __name__=="__main__": main()
