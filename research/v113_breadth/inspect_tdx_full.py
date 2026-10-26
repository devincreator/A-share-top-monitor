#!/usr/bin/env python3
"""V113 official TDX historical raw archive, bounded resumable, sample stock-day validation."""
import csv,hashlib,json,os,re,struct,time,urllib.request,zipfile
from pathlib import Path
ROOT=Path("v113_tdx_pilot");ROOT.mkdir(exist_ok=True)
URL="https://data.tdx.com.cn/vipdoc/hsjday.zip"
ARCHIVE=ROOT/"hsjday.zip"
SIZE_LIMIT=700_000_000
def get():
 for attempt in range(4):
  start=ARCHIVE.stat().st_size if ARCHIVE.exists() else 0
  headers={"User-Agent":"Mozilla/5.0"}
  if start:headers["Range"]="bytes="+str(start)+"-"
  req=urllib.request.Request(URL,headers=headers)
  try:
   with urllib.request.urlopen(req,timeout=80) as r:
    if r.status not in (200,206):raise ValueError("BAD_STATUS")
    mode="ab" if start and r.status==206 else "wb"
    with ARCHIVE.open(mode) as f:
     while True:
      chunk=r.read(4_194_304)
      if not chunk:break
      f.write(chunk)
      if f.tell()>SIZE_LIMIT:raise ValueError("TOO_LARGE")
   if zipfile.is_zipfile(ARCHIVE):break
   raise ValueError("INVALID_OR_INCOMPLETE_ZIP")
  except Exception as e:
   print(json.dumps({"download_retry":attempt,"size":ARCHIVE.stat().st_size if ARCHIVE.exists() else 0,
       "error":str(e)[:180]}),flush=True)
   if attempt>=3:raise
   time.sleep(3*(attempt+1))
 return hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
def inspect():
 sha=get()
 with zipfile.ZipFile(ARCHIVE) as z:
  entries=z.infolist()
  bymarket={"sh":[],"sz":[],"bj":[],"other":[]}
  for info in entries:
   name=info.filename.replace("\\","/")
   base=name.rsplit("/",1)[-1].lower()
   key=base[:2] if re.match(r"^(sh|sz|bj)\d{6}\.day$",base) else "other"
   bymarket[key].append(info)
  result={"source":URL,"zip_sha256":sha,"archive_size_bytes":ARCHIVE.stat().st_size,
       "all_entries":len(entries),"security_file_counts":{k:len(v) for k,v in bymarket.items()},
       "examples":{k:[v.filename for v in bymarket[k][:5]] for k in bymarket}}
  fmt=struct.Struct("<IIIIIfII")
  result["samples"]={}
  for code in ("sh600000","sz000001","bj920931","bj920680","bj872931"):
   for info in entries:
    name=info.filename.replace("\\","/").split("/")[-1].lower()
    if name!=code+".day":continue
    raw=z.read(info)
    if len(raw)%32:raise ValueError("BAD_TDX_STOCK_FILE_LENGTH_"+code)
    total=len(raw)//32
    head=[fmt.unpack_from(raw,i*32)[:6] for i in range(min(2,total))]
    tail=[fmt.unpack_from(raw,(total-1-i)*32)[:6] for i in range(min(2,total))]
    result["samples"][code]={"records":total,"first":head,"last":tail,
       "file_sha256":hashlib.sha256(raw).hexdigest(),"zip_path":info.filename}
  (ROOT/"structure_audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
  print(json.dumps(result,ensure_ascii=False),flush=True)
if __name__=="__main__":inspect()
