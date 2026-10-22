#!/usr/bin/env python3
"""Resume finite bounded V112 batches, stop on no progress, retain raw bytes."""
import argparse,subprocess,sys,json,time
from pathlib import Path
def run(candidate,ledger,out,batches,batch_size=16):
    ledger=Path(ledger);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    progress=[]
    for k in range(batches):
        previous=len(list((ledger/"records").glob("*/SSE.json")))
        dest=out/("batch_"+str(k+1))
        args=[sys.executable,"research/v92_margin_recovery/recover_batch.py",
              "--candidate",str(candidate),"--ledger",str(ledger),
              "--out",str(dest),"--max-dates",str(batch_size),"--retry-days","0"]
        subprocess.run(args,check=True)
        result=json.loads((dest/"batch_audit.json").read_text())
        current=len(list((ledger/"records").glob("*/SSE.json")))
        entry={"batch":k+1,"selected":len(result.get("selected_dates",[])),
               "source_saved":result.get("sources_saved",0),
               "new_sse_days":current-previous,
               "source_failures":result.get("source_failures",0)}
        progress.append(entry)
        print(json.dumps(entry),flush=True)
        if not result.get("selected_dates") or current==previous:
            print("STOP_NO_ADDITIONAL_VERIFIABLE_SOURCE",flush=True)
            break
        if k+1<batches:time.sleep(5)
    (out/"batch_progress.json").write_text(json.dumps(progress,indent=2)+"\n")
    return progress
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--candidate",required=True);p.add_argument("--ledger",required=True)
    p.add_argument("--out",required=True);p.add_argument("--batches",type=int,default=10)
    a=p.parse_args()
    if not 1<=a.batches<=12:raise SystemExit("unsafe batch count")
    run(a.candidate,a.ledger,a.out,a.batches)
