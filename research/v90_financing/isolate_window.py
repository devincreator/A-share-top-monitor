#!/usr/bin/env python3
"""V90 financing history anomaly isolation. Research only; never impute or publish signals."""
import datetime as dt
import math

def isolate_financing(rows,asof,lookback=60):
    asof=dt.date.fromisoformat(asof)
    seen=set()
    valid={}
    rejected=[]
    for row in rows:
        day=dt.date.fromisoformat(str(row["date"])[:10])
        if day in seen:
            raise ValueError("duplicate financing date")
        seen.add(day)
        if day>asof:
            continue
        try:
            sh=float(row["balance_sh_yuan"]);sz=float(row["balance_sz_yuan"])
            if not(math.isfinite(sh) and math.isfinite(sz) and sh>0 and sz>0):
                raise ValueError("nonpositive or nonfinite financing balance")
        except (ValueError,TypeError,KeyError) as exc:
            rejected.append({"date":day.isoformat(),"reason":str(exc)})
            continue
        valid[day.isoformat()]=sh+sz
    if asof.isoformat() not in valid:
        return {"status":"BLOCKED_ASOF_NOT_VERIFIED","rejected":rejected,
                "formal_signal_allowed":False}
    history=sorted(valid)
    # This is a calendar-gap and anomaly-aware RESEARCH window, not an official
    # exchange-calendar or release-time certification.
    last=history[-(lookback+1):]
    if len(last)<lookback+1:
        status="BLOCKED_SHORT_WINDOW"
    elif any(dt.date.fromisoformat(r["date"])>=dt.date.fromisoformat(last[0])
             for r in rejected):
        status="BLOCKED_ANOMALY_IN_WINDOW"
    else:
        status="CANDIDATE_WINDOW_ONLY_NOT_PIT"
    return {"status":status,"asof":asof.isoformat(),
            "window_first":last[0] if last else None,
            "window_last":last[-1] if last else None,
            "valid_window_rows":len(last),
            "rejected":rejected,"formal_signal_allowed":False,
            "publication_time_verified":False,
            "exchange_calendar_verified":False}

if __name__=="__main__":
    import argparse,json
    from pathlib import Path
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True)
    p.add_argument("--asof",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    src=json.loads(Path(a.input).read_text())
    result=isolate_financing(src["financing"],a.asof)
    Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"status":result["status"],"rejected":len(result["rejected"])},ensure_ascii=False))
