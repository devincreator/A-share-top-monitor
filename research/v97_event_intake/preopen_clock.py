#!/usr/bin/env python3
"""Pre-open feature availability gate for historical event reconstruction.

User contract: at the moment of a trading-day prediction, NONE of that day's
eventual close, index turnover, C50, breadth, financing or other daily factors
may be used. A prior-day factor also needs evidence of availability by the
actual decision timestamp. Historical CSV retrieval is not publication proof.
"""
import argparse
from datetime import date,datetime,time,timedelta,timezone
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

CHINA=ZoneInfo("Asia/Shanghai")
OPEN=time(9,30)
NO_SAME_DAY={
    "INDEX_CLOSE","INDEX_AMOUNT","INDEX_TURNOVER","MARKET_BREADTH",
    "C50","FINANCING_BALANCE","FINANCING_CHANGE","PRICE_MOMENTUM",
    "VOLATILITY","HISTORICAL_PERCENTILE","OTHER_DAILY_FEATURE",
}


def aware(value):
    if not isinstance(value,str):
        raise ValueError("timestamp must be explicit string with timezone")
    ts=datetime.fromisoformat(value.replace("Z","+00:00"))
    if ts.tzinfo is None or ts.utcoffset() is None:
        raise ValueError("naive timestamp cannot prove data availability")
    return ts


def inspect_prediction(prediction,evidence,required_factors=None):
    """Evaluate one actual prediction clock against time-qualified source rows.

    A complete schema can only be a candidate until the historical original
    publication evidence is independently authenticated.
    """
    out={"prediction_id":prediction.get("id"),"status":"BLOCKED",
         "errors":[],"factor_evidence":[],"research_only":True,
         "formal_signal_allowed":False,"publication_PIT_certified":False}
    try:
        when=aware(prediction["decision_at"])
        local=when.astimezone(CHINA)
        day=date.fromisoformat(prediction["prediction_date"])
        if local.date()!=day:
            raise ValueError("prediction clock does not fall on prediction_date in Shanghai")
        if local.weekday()>=5:
            raise ValueError("prediction date cannot be a weekend")
        if local.time().replace(tzinfo=None)>=OPEN:
            raise ValueError("decision is not a before-open prediction (<09:30 Asia/Shanghai)")
        out["decision_at"]=when.isoformat()
    except (ValueError,KeyError,TypeError) as exc:
        out["errors"].append(f"decision clock: {exc}")
        return out
    required=set(required_factors or ())
    if not required:
        out["errors"].append("no explicit required factor contract")
        return out
    got=set()
    for row in evidence:
        factor=row.get("factor")
        item={"factor":factor,"observation_date":row.get("observation_date"),
              "status":"BLOCKED"}
        if factor not in required:
            out["errors"].append(f"unexpected factor {factor}")
            out["factor_evidence"].append(item)
            continue
        if factor in got:
            out["errors"].append(f"duplicate factor {factor}")
            out["factor_evidence"].append(item)
            continue
        got.add(factor)
        try:
            observation=date.fromisoformat(row["observation_date"])
            # Explicit user's strict rule: no same-day DAILY observation.
            if observation>=day:
                raise ValueError("same-day or future daily indicator is unavailable")
            # Require evidence that the original source was actually released
            # before the historical prediction, not simply retrieved in 2026.
            pub=aware(row["published_at"])
            if pub>when:
                raise ValueError("published after historical prediction time")
            if pub.astimezone(CHINA).date()<observation:
                raise ValueError("publication before observation trading date")
            sha=row.get("source_raw_sha256")
            if not isinstance(sha,str) or len(sha)!=64 or any(c not in "0123456789abcdef" for c in sha):
                raise ValueError("no valid SHA256 for the raw input")
            if not row.get("source_uri"):
                raise ValueError("no original source URI")
            provenance=row.get("publication_provenance")
            if provenance!="INDEPENDENTLY_VERIFIED":
                raise ValueError("publication timestamp not independently evidenced")
            if not row.get("publication_evidence_uri"):
                raise ValueError("missing independent publication evidence URI")
            item["status"]="TIME_CONTRACT_SCHEMA_CANDIDATE"
            item["released_at"]=pub.isoformat()
        except (ValueError,TypeError,KeyError) as exc:
            item["reason"]=str(exc)
            out["errors"].append(f"{factor}: {exc}")
        out["factor_evidence"].append(item)
    missing=sorted(required-got)
    if missing:
        out["errors"].append("missing factor evidence: "+",".join(missing))
    if not out["errors"]:
        out["status"]="PREOPEN_SCHEMA_VALID_REQUIRES_SOURCE_AUTHENTICATION"
        # A source-provided 'verified' field is an assertion, not independently
        # tested PIT proof. Never elevate without an external audit gate.
    return out


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True,help="JSON with prediction, evidence and required_factors")
    p.add_argument("--output",required=True)
    a=p.parse_args()
    payload=Path(a.input).read_bytes()
    doc=json.loads(payload)
    status=inspect_prediction(doc["prediction"],doc["evidence"],doc["required_factors"])
    status["input_sha256"]=hashlib.sha256(payload).hexdigest()
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps({"status":status["status"],"errors":status["errors"],
                      "formal_signal_allowed":False},ensure_ascii=False))


if __name__=="__main__":
    main()
