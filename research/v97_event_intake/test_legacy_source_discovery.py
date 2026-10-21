import importlib.util
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location("v97_silent_source",
    Path(__file__).with_name("legacy_source_discovery.py"))
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class Tests(unittest.TestCase):
    def test_deleted_original_path_found_in_reachable_commit_changes(self):
        a="a"*40
        x=m.parse_log(["commit:"+a,"old/V68_FORMAL_START_alerts.csv",
             "research/v97_event_intake/observations/partial_v52_derived_objective_pivots.csv"])
        self.assertEqual(x["candidate_count"],1)
        self.assertEqual(x["candidate_paths"][0]["commits"],[a])

    def test_new_fake_research_not_cited_as_original(self):
        self.assertFalse(m.candidate("research/v97_event_intake/original_v68_event_replay.zip"))
        self.assertFalse(m.candidate("research/reports/V63_V68_实测报告.md"))

    def test_unverified_name_never_passes_formal_source(self):
        data=m.inspect({"candidate_count":0},
             [{"tag_name":"old","assets":[{"name":"v63_v68_alert_events.zip","id":1}]}],
             [{"name":"v68_formal_alert","id":2,"expired":False}],[])
        self.assertEqual(data["status"],"BLOCKED_UNVERIFIED_FILE_NAME_LEADS")
        self.assertFalse(data["original_FORMAL_START_events_verified"])
        self.assertFalse(data["formal_signal_allowed"])

    def test_incomplete_api_never_claims_absence(self):
        data=m.inspect({"candidate_count":0},[],[],["GitHub API unauthorized"])
        self.assertEqual(data["status"],"BLOCKED_SCAN_INCOMPLETE")

    def test_no_lead_is_not_pass(self):
        self.assertEqual(m.inspect({"candidate_count":0},[],[],[])["status"],
                         "BLOCKED_NO_NAME_LEADS_IN_SCANNED_SCOPE")

if __name__=="__main__":
    unittest.main()
