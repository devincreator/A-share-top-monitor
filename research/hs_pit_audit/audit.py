"""Fail-closed SSE/SZSE historical identity and daily availability checks.
This validates supplied evidence only; never certifies source completeness.
"""
from datetime import date, datetime, time
from zoneinfo import ZoneInfo
import argparse, json
from pathlib import Path

CN=ZoneInfo("Asia/Shanghai")
KINDS={"CONFIRMED_SUSPENDED","SOURCE_GAP","NOT_YET_LISTED","DELISTED","UNRESOLVED"}

def ts(s):
    d=datetime.fromisoformat(s.replace("Z","+00:00"))
    if d.tzinfo is None or d.utcoffset() is None:
        raise ValueError("timezone missing")
    return d

def audit(payload):
    findings=[]
    def error(kind,key,message):
        findings.append(dict(kind=kind,key=str(key),reason=str(message)))
    try:
        decision=ts(payload["decision_at"])
        trade_day=decision.astimezone(CN).date()
        if decision.astimezone(CN).time()>=time(9,30):
            error("CLOCK","decision_at","not preopen")
    except (KeyError,ValueError,TypeError) as ex:
        error("CLOCK","decision_at",ex)
        decision=None
        trade_day=None
    episodes={}
    symbols={}
    for e in payload.get("episodes",[]):
        k=e.get("security_listing_id")
        try:
            if not k or k in episodes: raise ValueError("missing or duplicate episode ID")
            symbol=e["symbol"]
            if not symbol.endswith((".SH",".SZ")): raise ValueError("outside SSE/SZSE")
            start=date.fromisoformat(e["listed_from"])
            end=date.fromisoformat(e["listed_through"]) if e.get("listed_through") else None
            if end and end<start: raise ValueError("end before start")
            if not e.get("listing_evidence_uri"): raise ValueError("missing statutory listing evidence")
            episodes[k]=(symbol,start,end)
            symbols.setdefault(symbol,[]).append((start,end,k))
        except (KeyError,ValueError,TypeError) as ex: error("EPISODE",k,ex)
    for symbol,spans in symbols.items():
        spans.sort(key=lambda s:s[0])
        for a,b in zip(spans,spans[1:]):
            if a[1] is None or a[1]>=b[0]:
                error("EPISODE",symbol,"overlapping same-code issuer episodes")
    seen=set()
    for b in payload.get("bars",[]):
        key=(b.get("security_listing_id"),b.get("date"))
        if key in seen: error("BAR",key,"duplicate bar")
        seen.add(key)
        try:
            symbol,start,end=episodes[key[0]]
            d=date.fromisoformat(key[1])
            if symbol!=b.get("symbol") or d<start or (end and d>end):
                raise ValueError("bar outside listing episode")
            sha=b.get("source_raw_sha256","")
            if len(sha)!=64 or any(c not in "0123456789abcdef" for c in sha):
                raise ValueError("missing/invalid raw SHA256")
        except (KeyError,ValueError,TypeError) as ex: error("BAR",key,ex)
    for m in payload.get("missing",[]):
        key=(m.get("security_listing_id"),m.get("date"))
        try:
            symbol,start,end=episodes[key[0]]
            d=date.fromisoformat(key[1])
            reason=m.get("classification","UNRESOLVED")
            if reason not in KINDS: raise ValueError("invalid missing-bar class")
            if reason!="UNRESOLVED" and not m.get("independent_evidence_uri"):
                raise ValueError("missing independent classification evidence")
            if reason=="CONFIRMED_SUSPENDED" and (d<start or (end and d>end)):
                raise ValueError("suspension outside listing")
            if reason=="NOT_YET_LISTED" and d>=start: raise ValueError("contradicts listing date")
            if reason=="DELISTED" and (end is None or d<=end):
                raise ValueError("contradicts delisting date")
            if reason in ("SOURCE_GAP","UNRESOLVED"): error("MISSING",key,reason)
        except (KeyError,ValueError,TypeError) as ex: error("MISSING",key,ex)
    for f in payload.get("features",[]):
        try:
            if decision is None: raise ValueError("decision clock invalid")
            d=date.fromisoformat(f["observation_date"])
            published=ts(f["published_at"])
            if d>=trade_day: raise ValueError("same-day/future daily feature")
            if published>decision: raise ValueError("not yet published")
            if published<datetime.combine(d,time(15),CN):
                raise ValueError("claimed final feature before close")
            for k in ("source_uri","source_raw_sha256","publication_evidence_uri"):
                if not f.get(k): raise ValueError("missing "+k)
            if f.get("publication_provenance")!="INDEPENDENTLY_VERIFIED":
                raise ValueError("publication not independently verified")
        except (KeyError,ValueError,TypeError) as ex:
            error("FEATURE",f.get("name","?"),ex)
    return dict(status="BLOCKED" if findings else "SCHEMA_CANDIDATE_NOT_PIT_CERTIFIED",
                historical_universe_PIT_certified=False,publication_PIT_certified=False,
                formal_signal_allowed=False,findings=findings,
                counts={k:len(payload.get(k,[])) for k in ("episodes","bars","missing","features")})

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("input");p.add_argument("output")
    args=p.parse_args()
    result=audit(json.loads(Path(args.input).read_text(encoding="utf-8")))
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(result["status"],len(result["findings"]))
