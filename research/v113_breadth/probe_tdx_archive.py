#!/usr/bin/env python3
"""HEAD + bounded Range only; verify official TDX all-exchange archive before download."""
import json,urllib.request,hashlib
from pathlib import Path
ROOT=Path("v113_tdx_archive_probe");ROOT.mkdir(exist_ok=True)
url="https://data.tdx.com.cn/vipdoc/hsjday.zip"
out={"url":url,"status":"UNAVAILABLE"}
for method in ("HEAD","RANGE"):
 try:
  headers={"User-Agent":"Mozilla/5.0 (A-share academic research verification)"}
  if method=="RANGE":headers["Range"]="bytes=0-1023"
  r=urllib.request.Request(url,headers=headers,method="GET" if method=="RANGE" else "HEAD")
  with urllib.request.urlopen(r,timeout=55) as res:
   status=res.status
   content=res.read(1024) if method=="RANGE" else b""
   hd=dict(res.headers.items())
  out[method.lower()]={"status":status,"size_header":hd.get("Content-Length",""),
    "content_range":hd.get("Content-Range",""),"content_type":hd.get("Content-Type",""),
    "accept_ranges":hd.get("Accept-Ranges",""),"sample_size":len(content),
    "zip_signature_ok":content.startswith(b"PK\x03\x04") if content else None}
  print(json.dumps({"method":method,**out[method.lower()]},ensure_ascii=False),flush=True)
 except Exception as e:
  out[method.lower()]={"error":type(e).__name__+":"+str(e)[:220]}
  print(json.dumps({"method":method,**out[method.lower()]},ensure_ascii=False),flush=True)
out["status"]="RETRIEVABLE" if out.get("range",{}).get("zip_signature_ok") else "BLOCKED"
(ROOT/"probe.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
