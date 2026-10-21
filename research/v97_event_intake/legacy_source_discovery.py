#!/usr/bin/env python3
"""V97/E1: metadata-only historic source discovery, never authenticates alerts."""
import argparse, json, os, re, subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote

CLUES=("v63","v64","v65","v66","v67","v68","formal_start",
       "formal_alert","alert_events","event_replay","original_events")
SUFFIX=(".zip",".csv",".parquet",".jsonl",".sqlite",".pkl")
EXCLUDED=("research/v97_event_intake/","research/progress/","research/reports/")
MAX_LEADS=100

def candidate(name,kind="git"):
    s=str(name).lower().replace("\\","/")
    if kind=="git" and s.startswith(EXCLUDED):
        return False
    return (s.endswith(SUFFIX) or kind=="artifact") and (
        any(w in s for w in CLUES) or s.endswith(("/alerts.csv","/pivots.csv")))

def parse_log(lines):
    lead={};last=None;count=0
    for l in lines:
        count+=1
        if count>200000:
            raise ValueError("git history file list limit hit")
        l=l.strip()
        if l.startswith("commit:"):
            last=l[7:] if re.fullmatch(r"[a-f0-9]{40}",l[7:]) else None
        elif l and last and candidate(l):
            row=lead.setdefault(l,{"path":l,"commits":[]})
            if len(row["commits"])<3:
                row["commits"].append(last)
    return {"paths_examined":count,"candidate_count":len(lead),
            "candidate_paths":[lead[k] for k in sorted(lead)][:MAX_LEADS]}

def api_pages(root,name,token,key=None):
    data=[];errors=[]
    for page in range(1,6):
        url=f"{root}/{name}?per_page=100&page={page}"
        headers={"Accept":"application/vnd.github+json",
                 "User-Agent":"V97-Original-Event-Source-Inventory"}
        if token: headers["Authorization"]="Bearer "+token
        try:
            with urlopen(Request(url,headers=headers),timeout=20) as response:
                obj=json.loads(response.read(5000000))
            chunk=obj if key is None else obj[key]
            if not isinstance(chunk,list):
                raise ValueError("unexpected listing response")
            data.extend(chunk)
            if len(chunk)<100: break
            if page==5: errors.append(name+" API list truncated")
        except Exception as exc:
            errors.append(name+" listing failed "+type(exc).__name__)
            break
    return data,errors

def inspect(git_result,releases,artifacts,errors):
    ra=[]
    for release in releases:
        for asset in release.get("assets",[]):
            if candidate(asset.get("name",""),"release"):
                ra.append({"tag":release.get("tag_name"),"name":asset.get("name"),
                           "asset_id":asset.get("id"),"verified":False})
    aa=[{"name":a.get("name"),"artifact_id":a.get("id"),"verified":False}
        for a in artifacts if not a.get("expired") and candidate(a.get("name",""),"artifact")]
    count=git_result.get("candidate_count",0)+len(ra)+len(aa)
    status=("BLOCKED_SCAN_INCOMPLETE" if errors else
            "BLOCKED_UNVERIFIED_FILE_NAME_LEADS" if count else
            "BLOCKED_NO_NAME_LEADS_IN_SCANNED_SCOPE")
    return {"status":status,"research_only":True,
            "scanned_at_utc":datetime.now(timezone.utc).isoformat(),
            "git":git_result,"releases_scanned":len(releases),
            "release_asset_candidates":ra[:MAX_LEADS],
            "artifacts_scanned":len(artifacts),
            "artifact_candidates":aa[:MAX_LEADS],"errors":errors,
            "original_FORMAL_START_events_verified":False,
            "historical_PIT_verified":False,"formal_signal_allowed":False,
            "interpretation":"Only reachable Git tracked filenames, Releases and unexpired Actions artifact names; external, deleted untracked, expired and unreachable evidence not covered. Names are never source proof."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repository",default=os.getenv("GITHUB_REPOSITORY"))
    p.add_argument("--output",default="v97_source_inventory/scan.json")
    args=p.parse_args()
    if not args.repository or not re.fullmatch(r"[\w.-]+/[\w.-]+",args.repository):
        raise SystemExit("missing repository owner/name")
    errors=[]
    try:
        lines=subprocess.run(["git","log","--all","--format=commit:%H",
                             "--name-only","--diff-filter=ACDMRT"],
                            check=True,capture_output=True,text=True,timeout=90).stdout.splitlines()
        git_result=parse_log(lines)
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        git_result={"candidate_count":0,"candidate_paths":[]}
        errors.append("git history scan failed "+type(exc).__name__)
    root="https://api.github.com/repos/"+quote(args.repository,safe="/")
    rel,er=api_pages(root,"releases",os.getenv("GITHUB_TOKEN"))
    art,ea=api_pages(root,"actions/artifacts",os.getenv("GITHUB_TOKEN"),"artifacts")
    report=inspect(git_result,rel,art,errors+er+ea)
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":report["status"],
                      "git_candidates":report["git"]["candidate_count"],
                      "release_candidates":len(report["release_asset_candidates"]),
                      "artifact_candidates":len(report["artifact_candidates"]),
                      "formal_signal_allowed":False},ensure_ascii=False))

if __name__=="__main__":
    main()
