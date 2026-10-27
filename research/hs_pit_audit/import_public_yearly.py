#!/usr/bin/env python3
"""Import verifiable existing public GitHub daily files by year, research-only.
No completeness/PIT claims. First source: guidebee/china-stock-data (2026).
"""
import argparse,csv,hashlib,io,json,re,urllib.request
from pathlib import Path
API="https://api.github.com/repos/guidebee/china-stock-data/git/trees/main?recursive=1"
RAW="https://raw.githubusercontent.com/guidebee/china-stock-data/main/"
PAT=re.compile(r"data/price/(20\d{2})/(\d{2})/stock_price_(20\d{2})_(\d{2})_(\d{2})\.csv$")
def get(url):
 req=urllib.request.Request(url,headers={"User-Agent":"A-share-research-evidence/1.0","Accept":"application/vnd.github+json"})
 with urllib.request.urlopen(req,timeout=40) as resp:return resp.read()
def run(out,limit=0):
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 tree=json.loads(get(API))
 if tree.get("truncated"):raise RuntimeError("source Git tree truncated")
 files=[]
 for x in tree["tree"]:
  m=PAT.fullmatch(x["path"])
  if m and x["type"]=="blob" and m[1]==m[3] and m[2]==m[4]:
   files.append((f"{m[1]}-{m[2]}-{m[5]}",x))
 files.sort()
 if limit:files=files[:limit]
 manifest={"source":API,"upstream_repo":"guidebee/china-stock-data","scope":"SSE/SZSE daily traded rows only, BSE excluded","PIT_certified":False,"universe_complete":False,"files":[],"errors":[]}
 for day,x in files:
  try:
   raw=get(RAW+x["path"])
   s=raw.decode("utf-8-sig")
   rows=list(csv.reader(io.StringIO(s)))
   if not rows:raise ValueError("empty source file")
   output=[]
   for row in rows:
    if len(row)<8: raise ValueError("unexpected columns")
    if row[1]!=day:raise ValueError("source date mismatch")
    if row[0].startswith(("sh","sz")) and len(row[0])==8 and row[0][2:].isdigit():
     output.append(row)
   if not output:raise ValueError("no SSE/SZSE records")
   year=day[:4];d=out/year/"daily";d.mkdir(parents=True,exist_ok=True)
   target=d/(day+".csv")
   with target.open("w",encoding="utf-8",newline="") as f:csv.writer(f,lineterminator="\n").writerows(output)
   payload=target.read_bytes()
   manifest["files"].append({"date":day,"path":str(target.relative_to(out)),"rows":len(output),
      "upstream_blob_sha":x["sha"],"upstream_raw_sha256":hashlib.sha256(raw).hexdigest(),
      "filtered_sha256":hashlib.sha256(payload).hexdigest(),"source_url":RAW+x["path"],
      "schema":"symbol,date,open,close,high,low,volume,amount (upstream column order; independent verification required)"})
  except Exception as e:
   manifest["errors"].append({"date":day,"source_url":RAW+x["path"],"error":str(e)})
 for y in range(2006,2027):
  p=out/str(y);p.mkdir(exist_ok=True)
  subset=[x for x in manifest["files"] if x["date"].startswith(str(y))]
  annual={"year":y,"verified_import_count":len(subset),"imported_rows":sum(z["rows"] for z in subset),
    "research_only":True,"PIT_certified":False,"full_year_stock_universe_certified":False,
    "files":subset,"missing_or_unchecked_dates_not_implied_closed":True}
  if y==2006:
   annual["existing_original_archive"]="https://github.com/devincreator/A-share-top-monitor/releases/download/research-v85-2006-20261020/v85_2006_raw_241days.zip"
   annual["archive_status"]="RAW_241_241_VERIFIED_NOT_PIT; stored in Release, not duplicated in git"
  (p/"manifest.json").write_text(json.dumps(annual,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 (out/"import_result.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 if manifest["errors"]:raise RuntimeError(str(len(manifest["errors"]))+" source days could not be imported, see import_result.json")
 return manifest
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--out",default="research/historical_data");p.add_argument("--limit",type=int,default=0)
 a=p.parse_args();r=run(a.out,a.limit)
 print(json.dumps({"imported_days":len(r["files"]),"rows":sum(x["rows"] for x in r["files"]),"errors":len(r["errors"])}))
