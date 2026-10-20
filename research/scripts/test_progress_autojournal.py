#!/usr/bin/env python3
"""Regression tests for the GitHub research-only progress journal."""
import importlib.util
import json
import os
import pathlib
import tempfile
import unittest
from unittest.mock import patch

MODULE = pathlib.Path(__file__).with_name("progress_autojournal.py")
spec = importlib.util.spec_from_file_location("progress_autojournal", MODULE)
journal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(journal)


class ProgressJournalTests(unittest.TestCase):
    def test_allowed_research_workflows(self):
        for path in (".github/workflows/v76-https-source-probe.yml",
                     ".github/workflows/v78-monthly-backfill.yml",
                     ".github/workflows/v79-2006-quarterly-backfill.yml",
                     ".github/workflows/v82-new-phase.yml",
                     ".github/workflows/research-handoff-selftest.yml"):
            self.assertTrue(journal.eligible({"path": path}), path)

    def test_production_and_own_workflow_never_logged(self):
        for path in (".github/workflows/research-progress-autojournal.yml",
                     ".github/workflows/v27-source-audit.yml",
                     ".github/workflows/production-deploy.yml",
                     "collector/v81-monthly-backfill.yml"):
            self.assertFalse(journal.eligible({"path": path}), path)

    def test_workflow_success_does_not_claim_pit_or_dual80(self):
        with patch.object(journal, "load_pages", return_value=[]):
            r=journal.github_run_record({
                "id": 10005,"run_attempt":1,"name":"V82 dataset smoke",
                "path": ".github/workflows/v82-smoke.yml",
                "head_sha":"fake-commit","head_branch":"main",
                "status":"completed","conclusion":"success",
                "html_url":"https://github.com/devincreator/A-share-top-monitor/actions/runs/10005"
            },"devincreator/A-share-top-monitor","dummy-token")
        self.assertEqual(r["data_gate"], "NOT_ASSESSED_BY_AUTOMATIC_JOURNAL")
        self.assertIsNone(r["PIT_certified"])
        self.assertIsNone(r["dual80_achieved"])

    def test_manual_requires_evidence_in_project_repo(self):
        with patch.dict(os.environ, {"GITHUB_RUN_ID":"1009"}, clear=False):
            with self.assertRaises(ValueError):
                journal.manual_record({"inputs":{"task_title":"V82",
                    "summary":"Sample audited","evidence_url":"https://other.net/no-evidence"}},
                    "devincreator/A-share-top-monitor")
            d=journal.manual_record({"inputs":{"task_title":"V82",
                "summary":"Sample audited","evidence_url":"https://github.com/devincreator/A-share-top-monitor/issues/1",
                "result":"blocked"}},"devincreator/A-share-top-monitor")
        self.assertEqual(d["data_gate"], "MANUAL_EVIDENCE_REQUIRES_SEPARATE_QA")
        self.assertEqual(d["conclusion"],"blocked")

    def test_history_idempotent_and_manual_index_visible(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(journal,"ROOT",pathlib.Path(td)):
                with patch.object(journal,"RUNS",pathlib.Path(td)/"runs"):
                    x={"record_type":"github_actions_completion",
                       "run_id":1001,"run_attempt":1,
                       "recorded_at_utc":"2026-10-20T07:30:00+00:00",
                       "updated_at":"2026-10-20T07:29:59Z",
                       "workflow_name":"V78 smoke","conclusion":"failure",
                       "status":"completed","run_url":"https://github.com/devincreator/A-share-top-monitor/actions/runs/1001","artifacts":[]}
                    self.assertTrue(journal.write_history(x))
                    self.assertFalse(journal.write_history(x))
                    manual=pathlib.Path(td)/"manual"
                    manual.mkdir()
                    (manual/"20261020T080000Z-test.json").write_text(json.dumps({
                        "record_type":"manually_reported_research_milestone",
                        "recorded_at_utc":"2026-10-20T08:00:00Z",
                        "workflow_name":"V82 local audit",
                        "conclusion":"blocked",
                        "evidence_url":"https://github.com/devincreator/A-share-top-monitor/issues/1",
                        "data_gate":"UNVERIFIED","dual80_achieved":None
                    }),encoding="utf-8")
                    journal.render_index()
                    latest=json.loads((pathlib.Path(td)/"latest.json").read_text())
                    self.assertEqual(latest["entry_count"],2)
                    self.assertEqual(latest["latest"]["conclusion"],"blocked")
                    index=(pathlib.Path(td)/"README.md").read_text()
                    self.assertIn("V82 local audit",index)
                    self.assertIn("V78 smoke",index)


if __name__=="__main__":
    unittest.main()
