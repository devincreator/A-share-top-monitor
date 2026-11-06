"""Deterministic market-coverage and feature-release gate; never asserts PIT PASS."""
import argparse,csv,hashlib,json
from collections import Counter
from datetime import date,datetime,time
from pathlib import Path
from zoneinfo import ZoneInfo
CN=ZoneInfo("Asia/Shanghai")
ALLOWED=("CONFIRMED_SUSPENDED","SOURCE_GAP","NOT_YET_LISTED","DELISTED","UNRESOLVED")

def evaluate(rows,asof,required_calendar=None):
    errors=[]; seen=set(); results=[]; daily={}
    for r in rows:
        key=(r.get("date"),r.get("security_listing_id"))
        if key in seen: errors.append({"key":key,"error":"DUPLICATE_SECURITY_DAY"})
        seen.add(key)
        status=r.get("status","UNRESOLVED")
        if status not in ALLOWED+("TRADED",): errors.append({"key":key,"error":"UNKNOWN_STATUS"})
        if status!="TRADED" and status!="UNRESOLVED" and not r.get("independent_evidence_uri"):
            errors.append({"key":key,"error":"CLASSIFICATION_HAS_NO_EVIDENCE"})
        if status=="TRADED" and not r.get("source_raw_sha256"):
            errors.append({"key":key,"error":"TRADE_HAS_NO_SOURCE_HASH"})
        day=r.get("date")
        daily.setdefault(day,Counter())[status]+=1
    for day,counts in sorted(daily.items()):
        unresolved=counts["UNRESOLVED"]+counts["SOURCE_GAP"]
        results.append({"date":day,"total_classified":sum(counts.values()),
                        "traded":counts["TRADED"],"confirmed_suspended":counts["CONFIRMED_SUSPENDED"],
                        "unresolved_or_source_gap":unresolved,
                        "scope_status":"BLOCKED" if unresolved else "COVERAGE_SCHEMA_ONLY_NOT_PIT"})
    if required_calendar is not None:
        expected=set(required_calendar)
        for day in sorted(expected-set(daily)): errors.append({"key":day,"error":"MISSING_CALENDAR_DAY"})
        for day in sorted(set(daily)-expected): errors.append({"key":day,"error":"UNEXPECTED_CALENDAR_DAY"})
    return {"status":"BLOCKED" if errors or any(x["unresolved_or_source_gap"] for x in results) else "RESEARCH_SCHEMA_ONLY",
            "asof":asof,"PIT_certified":False,"formal_training_allowed":False,
            "days":results,"findings":errors}

def feature_gate(rows,decision_at):
    decision=datetime.fromisoformat(decision_at)
    if decision.tzinfo is None: raise ValueError("decision clock needs timezone")
    local=decision.astimezone(CN)
    results=[]
    for r in rows:
        why=[]
        try:
            observed=date.fromisoformat(r["observation_date"])
            released=datetime.fromisoformat(r["published_at"])
            if released.tzinfo is None: raise ValueError("publication timezone missing")
            if local.time()>=time(9,30): why.append("NOT_PREOPEN")
            if observed>=local.date(): why.append("SAME_OR_FUTURE_DAY")
            if released>decision: why.append("LATE_PUBLICATION")
            if released<datetime.combine(observed,time(15,0),CN): why.append("BEFORE_FINAL_CLOSE")
            if not r.get("publication_evidence_uri"): why.append("NO_PUBLICATION_PROOF")
            if r.get("publication_provenance")!="INDEPENDENTLY_VERIFIED": why.append("UNVERIFIED_PUBLICATION_PROVENANCE")
            sha=r.get("source_raw_sha256","")
            if len(sha)!=64 or any(ch not in "0123456789abcdef" for ch in sha): why.append("INVALID_SOURCE_SHA")
        except (ValueError,KeyError,TypeError) as ex: why.append("INVALID_FIELDS:"+str(ex))
        results.append({"factor":r.get("factor"),"observation_date":r.get("observation_date"),
                        "status":"BLOCKED" if why else "SCHEMA_ONLY_NOT_SOURCE_AUTHENTICATED","reasons":why})
    return {"decision_at":decision_at,"publication_PIT_certified":False,
            "status":"BLOCKED" if any(x["reasons"] for x in results) else "SCHEMA_ONLY_NOT_SOURCE_AUTHENTICATED",
            "factors":results}

def main():
    p=argparse.ArgumentParser();p.add_argument("input");p.add_argument("output");args=p.parse_args()
    doc=json.loads(Path(args.input).read_text(encoding="utf-8"))
    out={"coverage":evaluate(doc.get("security_days",[]),doc.get("asof"),doc.get("calendar")),
         "features":feature_gate(doc.get("features",[]),doc["decision_at"])}
    out["formal_training_allowed"]=False
    Path(args.output).write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
if __name__=="__main__":main()
