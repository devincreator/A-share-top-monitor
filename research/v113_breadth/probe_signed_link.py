#!/usr/bin/env python3
"""Check publicly advertised signed-link workflow at a low request rate; no token."""
import json,urllib.parse,urllib.request,hashlib,csv,io,time
from pathlib import Path
root=Path("v113_signed_link_probe");root.mkdir(exist_ok=True)
reports=[]
for day in ("20260814","20260921","20260930","20261021"):
    path=f"/daily_kline/date/{day}.csv"
    sign="https://money-tree.eyunzhu.com/v1/sign?"+urllib.parse.urlencode({"path":path})
    row={"day":day,"status":"BLOCKED"}
    try:
        req=urllib.request.Request(sign,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,timeout=15) as res:
            b=res.read(200001);row["sign_status"]=res.status
        doc=json.loads(b)
        row["sign_response_keys"]=list(doc) if isinstance(doc,dict) else []
        url=(doc.get("data") or {}).get("url") if isinstance(doc,dict) else None
        if not isinstance(url,str) or not url.startswith("https://"):
            raise ValueError("SIGN_ENDPOINT_NO_URL: "+str(doc)[:120])
        row["signed_link_received"]=True
        with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=30) as res:
            body=res.read(3000001)
            row["download_status"]=res.status
        if len(body)>3000000:raise ValueError("OVERSIZE")
        lines=list(csv.DictReader(io.StringIO(body.decode("utf-8-sig"))))
        if not lines or "trade_date" not in lines[0]:raise ValueError("UNEXPECTED_CSV")
        valid=sum(x.get("trade_date")==day for x in lines)
        if valid!=len(lines) or valid<1000:raise ValueError("DATE_OR_COVERAGE_MISMATCH")
        (root/f"daily_{day}.csv").write_bytes(body)
        row.update(status="SOURCE_CSV_VERIFIED",rows=valid,sha256=hashlib.sha256(body).hexdigest())
    except Exception as e:row["error"]=type(e).__name__+":"+str(e)[:170]
    reports.append(row)
    print(json.dumps(row,ensure_ascii=False),flush=True)
    time.sleep(3)
(root/"probe.json").write_text(json.dumps(reports,ensure_ascii=False,indent=2)+"\n")
