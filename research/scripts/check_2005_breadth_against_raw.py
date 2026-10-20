#!/usr/bin/env python3
"""Independently check research-only 2005 traded-stock breadth vs 242 raw daily files.

This is NOT a PIT certificate. 'Observed trading securities' is not equivalent to the
historical full listed market universe. No suspension or listing-episode reconstruction.
"""
from pathlib import Path
import argparse, csv, io, json, math, zipfile, hashlib

def compare(archive, summary_path):
    src=Path(archive); summary=Path(summary_path)
    with summary.open(encoding="utf-8-sig",newline="") as f:
        cached={r["date"]:r for r in csv.DictReader(f)}
    assert len(cached)==242, "Unexpected research table rows"
    issues=[]; rows_total=0
    with zipfile.ZipFile(src) as z:
        manifest=json.loads(z.read("source_manifest_2005.json"))
        for d,expected_sha in sorted(manifest["file_sha256"].items()):
            raw=z.read(f"raw/{d}.csv")
            if hashlib.sha256(raw).hexdigest()!=expected_sha:
                raise RuntimeError(f"Original SHA mismatch on {d}")
            data=list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
            rows_total+=len(data)
            yes=no=flat=0
            for item in data:
                try: chg=float(item["pct_chg"])
                except (TypeError, ValueError, KeyError):
                    issues.append(f"{d}: bad return for {item.get('symbol')}")
                    continue
                if chg>0:yes+=1
                elif chg<0:no+=1
                else:flat+=1
            saved=cached.get(d)
            if not saved:
                issues.append(f"{d}: missing from breadth CSV")
                continue
            expected={"raw_sh_sz_records":len(data),"all_advance":yes,
                      "all_decline":no,"all_flat":flat}
            for key,n in expected.items():
                if int(saved[key])!=n:
                    issues.append(f"{d}: {key} computed={n}, saved={saved[key]}")
            if abs((yes/len(data))-float(saved["all_observed_advance_fraction"]))>1e-9:
                issues.append(f"{d}: advance fraction does not match original")
    if rows_total!=314838:
        issues.append(f"unexpected raw rows {rows_total} not 314838")
    return {"raw_trade_days":len(cached),"raw_daily_bar_rows":rows_total,
            "issues":issues[:50],"issue_count":len(issues),
            "raw_breadth_consistency_pass":not issues,
            "PIT_certified":False,"full_market_universe_verified":False}

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("archive")
    parser.add_argument("summary")
    a=parser.parse_args()
    results=compare(a.archive,a.summary)
    print(json.dumps(results,indent=2,ensure_ascii=False))
    if not results["raw_breadth_consistency_pass"]:
        raise SystemExit(1)
