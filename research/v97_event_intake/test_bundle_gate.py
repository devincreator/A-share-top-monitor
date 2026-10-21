import csv
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
import zipfile
from datetime import date,timedelta
from pathlib import Path

SOURCE=Path(__file__).with_name("bundle_gate.py")
spec=importlib.util.spec_from_file_location("v97_bundle_gate",SOURCE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def bundle(path, *, instrument="000985.CSI", wrong_hash=False, missing_provenance=False):
    d=date(2020,1,1)
    days=[]
    while len(days)<150:
        if d.weekday()<5:
            days.append(d.isoformat())
        d+=timedelta(days=1)
    def csv_bytes(fields,rows):
        o=io.StringIO();writer=csv.DictWriter(o,fieldnames=fields)
        writer.writeheader();writer.writerows(rows)
        return o.getvalue().encode()
    a=csv_bytes(["id","date","scale","direction","event_type"],[
        {"id":"alert-001","date":days[30],"scale":"5","direction":"TOP","event_type":"FORMAL_START"}])
    p=csv_bytes(["id","date","scale","direction","confirmation_date"],[
        {"id":"pivot-001","date":days[35],"scale":"5","direction":"TOP",
         "confirmation_date":days[48]}])
    q=csv_bytes(["date","close"],[
        {"date":dd,"close":5000+i} for i,dd in enumerate(days)])
    raw={"alerts.csv":a,"pivots.csv":p,"prices.csv":q}
    fields={"index_instrument":instrument,
            "label_version":"V52" if instrument=="000985.CSI" else "LONG_CSI300",
            "source_code_commit":"ac0bde1234567890",
            "sha256":{name:hashlib.sha256(value).hexdigest() for name,value in raw.items()}}
    if wrong_hash:fields["sha256"]["alerts.csv"]="0"*64
    if missing_provenance:raw["alerts.csv"]=raw["alerts.csv"].replace(b"FORMAL_START",b"ACTIVE      ")
    raw["manifest.json"]=json.dumps(fields).encode()
    with zipfile.ZipFile(path,"w",zipfile.ZIP_DEFLATED) as f:
        for name,value in raw.items():f.writestr(name,value)


class BundleTests(unittest.TestCase):
    def test_missing_real_replay_is_research_blocker(self):
        r=m.check_bundle("/definitely/nonexistent/original_v68.zip")
        self.assertEqual(r["status"],"BLOCKED_BUNDLE_MISSING")
        self.assertFalse(r["formal_signal_allowed"])

    def test_canonical_bundle_is_not_auto_certified(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"real.zip"
            bundle(path)
            r=m.check_bundle(path)
            self.assertEqual(r["status"],"MAIN_INDEX_BUNDLE_INTAKE_SCHEMA_VALID_NOT_PIT")
            self.assertEqual(r["input_inventory"]["row_counts"]["alerts"],1)
            self.assertFalse(r["main_track_replay_allowed"])

    def test_csi300_must_not_be_claimed_csi_all_share(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"real.zip"
            bundle(path,instrument="000300.CSI")
            r=m.check_bundle(path)
            self.assertEqual(r["status"],"CSI300_SEPARATE_RESEARCH_TRACK_ONLY")
            self.assertFalse(r["formal_signal_allowed"])

    def test_wrong_hash_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"forged.zip";bundle(path,wrong_hash=True)
            self.assertEqual(m.check_bundle(path)["status"],"BLOCKED_CONTENT_OR_PROVENANCE")

    def test_active_rows_cannot_be_formal_starts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"active.zip";bundle(path,missing_provenance=True)
            r=m.check_bundle(path)
            self.assertEqual(r["status"],"BLOCKED_CONTENT_OR_PROVENANCE")

    def test_zip_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"bad.zip"
            with zipfile.ZipFile(path,"w") as z:z.writestr("../alerts.csv","x")
            self.assertEqual(m.check_bundle(path)["status"],"BLOCKED_ARCHIVE_INVALID")

if __name__=="__main__":unittest.main()
