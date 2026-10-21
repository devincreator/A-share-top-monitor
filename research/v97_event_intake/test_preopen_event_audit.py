import importlib.util
import unittest
from datetime import date,timedelta
from pathlib import Path

HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location("preopen_event_audit",HERE/"preopen_event_audit.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def inputs():
    days=[]
    d=date(2022,1,3)
    while len(days)<540:
        if d.weekday()<5:
            days.append(d.isoformat())
        d+=timedelta(days=1)
    prices=[{"date":day,"close":str(100+i*.2)} for i,day in enumerate(days)]
    return days,prices

def alert(days,n,uid,scale="5",direction="TOP"):
    return {"id":uid,"date":days[n],"decision_at":days[n]+"T08:50:00+08:00",
            "scale":scale,"direction":direction,"event_type":"FORMAL_START"}

def pivot(days,n,uid,scale="5",direction="TOP",confirm_delay=30):
    return {"id":uid,"date":days[n],"confirmation_date":days[n+confirm_delay],
            "scale":scale,"direction":direction}

def evidence(days,a):
    k=days.index(a["date"])
    return [{"factor":"INDEX_CLOSE","observation_date":days[k-1],
             "published_at":days[k-1]+"T18:00:00+08:00",
             "source_raw_sha256":"f"*64,"source_uri":"https://example.org/original",
             "publication_provenance":"INDEPENDENTLY_VERIFIED",
             "publication_evidence_uri":"https://example.org/notices"},
            {"factor":"FINANCING_BALANCE","observation_date":days[k-2],
             "published_at":days[k-1]+"T08:45:00+08:00",
             "source_raw_sha256":"e"*64,"source_uri":"https://example.org/financing",
             "publication_provenance":"INDEPENDENTLY_VERIFIED",
             "publication_evidence_uri":"https://example.org/announcements"}]

class PreopenEventTests(unittest.TestCase):
    def test_scoring_one_to_one_with_pending(self):
        days,prices=inputs()
        aa=[alert(days,200,"a1"),alert(days,201,"a2"),alert(days,535,"recent")]
        pp=[pivot(days,208,"p1")]
        mapping={a["id"]:evidence(days,a) for a in aa}
        out=m.audit_preopen(aa,pp,prices,mapping,["INDEX_CLOSE","FINANCING_BALANCE"],days[-1])
        row=out["tasks"]["5_TOP"]
        self.assertEqual((row["tp"],row["fp"],row["fn"],row["pending"]),(1,1,0,1))
        self.assertEqual(row["formal_alerts"],3)
        self.assertFalse(out["formal_signal_allowed"])

    def test_same_day_close_change_cannot_change_attribution(self):
        days,prices=inputs()
        aa=[alert(days,210,"a1")]
        lookup={"a1":evidence(days,aa[0])}
        one=m.audit_preopen(aa,[],prices,lookup,["INDEX_CLOSE","FINANCING_BALANCE"],days[-1])
        changed=[dict(row) for row in prices]
        for i in range(210,len(changed)):
            changed[i]["close"]="1000000"
        two=m.audit_preopen(aa,[],changed,lookup,["INDEX_CLOSE","FINANCING_BALANCE"],days[-1])
        first=one["tasks"]["5_TOP"]["events"][0]
        second=two["tasks"]["5_TOP"]["events"][0]
        self.assertEqual(first["regime_using_prior_day"],second["regime_using_prior_day"])
        self.assertEqual(first["last_feature_price_date"],days[209])
        self.assertEqual(second["last_feature_price_date"],days[209])

    def test_stale_but_published_close_controls_regime_not_unpublished_d_minus_one(self):
        days,prices=inputs()
        a=alert(days,210,"stale_price")
        available=evidence(days,a)
        available[0]["observation_date"]=days[207]
        available[0]["published_at"]=days[207]+"T18:00:00+08:00"
        first=m.audit_preopen([a],[],prices,{"stale_price":available},
                              ["INDEX_CLOSE","FINANCING_BALANCE"],days[-1])
        event=first["tasks"]["5_TOP"]["events"][0]
        self.assertEqual(event["last_feature_price_date"],days[207])
        self.assertEqual(event["regime_using_prior_day"],"MIXED_OR_RANGE")
        revised=[dict(row) for row in prices]
        # D-1/D-2 closes were NOT proven available at the preopen decision.
        revised[209]["close"]="999999"
        revised[208]["close"]="999999"
        revised[210]["close"]="999999"
        second=m.audit_preopen([a],[],revised,{"stale_price":available},
                               ["INDEX_CLOSE","FINANCING_BALANCE"],days[-1])
        self.assertEqual(event["regime_using_prior_day"],
                         second["tasks"]["5_TOP"]["events"][0]["regime_using_prior_day"])
        self.assertEqual(second["tasks"]["5_TOP"]["events"][0]["last_feature_price_date"],days[207])

    def test_no_index_close_evidence_leaves_market_regime_unknown(self):
        days,prices=inputs()
        a=alert(days,210,"finance_only")
        evidence_finance=[row for row in evidence(days,a)
                          if row["factor"]=="FINANCING_BALANCE"]
        result=m.audit_preopen([a],[],prices,{"finance_only":evidence_finance},
                               ["FINANCING_BALANCE"],days[-1])
        event=result["tasks"]["5_TOP"]["events"][0]
        self.assertEqual(event["regime_using_prior_day"],"NO_INDEX_CLOSE_ASOF_SOURCE")
        self.assertIsNone(event["last_feature_price_date"])

    def test_available_index_close_must_exist_in_original_trading_calendar(self):
        days,prices=inputs()
        a=alert(days,210,"off_calendar")
        ev=evidence(days,a)
        ev[0]["observation_date"]="2021-12-31"
        ev[0]["published_at"]=days[207]+"T18:00:00+08:00"
        result=m.audit_preopen([a],[],prices,{"off_calendar":ev},
                               ["INDEX_CLOSE","FINANCING_BALANCE"],days[-1])
        self.assertEqual(result["status"],"BLOCKED_FEATURE_CLOCK_OR_PROVENANCE")
        self.assertEqual(result["tasks"],{})
        self.assertIn("archived price calendar",str(result["invalid_alert_clock_examples"]))

    def test_historical_financing_late_released_blocks_replay(self):
        days,prices=inputs()
        a=alert(days,200,"a1")
        raw=evidence(days,a)
        raw[1]["published_at"]=days[200]+"T09:00:00+08:00"
        result=m.audit_preopen([a],[pivot(days,208,"p1")],prices,
                               {"a1":raw},["INDEX_CLOSE","FINANCING_BALANCE"],days[-1])
        self.assertEqual(result["status"],"BLOCKED_FEATURE_CLOCK_OR_PROVENANCE")
        self.assertEqual(result["tasks"],{})

    def test_same_day_factor_blocks_all_scoring(self):
        days,prices=inputs()
        a=alert(days,200,"a1")
        raw=evidence(days,a);raw[0]["observation_date"]=days[200]
        raw[0]["published_at"]=days[200]+"T08:00:00+08:00"
        result=m.audit_preopen([a],[],prices,{"a1":raw},
                               ["INDEX_CLOSE","FINANCING_BALANCE"],days[-1])
        self.assertEqual(result["status"],"BLOCKED_FEATURE_CLOCK_OR_PROVENANCE")

    def test_recent_unconfirmed_signal_never_classified_fp(self):
        days,prices=inputs()
        a=alert(days,534,"near_end")
        result=m.audit_preopen([a],[],prices,{"near_end":evidence(days,a)},
                               ["INDEX_CLOSE","FINANCING_BALANCE"],days[-1])
        task=result["tasks"]["5_TOP"]
        self.assertEqual((task["pending"],task["fp"]),(1,0))
        self.assertIsNone(task["precision_scored"])

    def test_same_day_pivot_not_early_hit(self):
        days,prices=inputs()
        a=alert(days,200,"a")
        p=pivot(days,200,"p")
        result=m.audit_preopen([a],[p],prices,{"a":evidence(days,a)},
                               ["INDEX_CLOSE","FINANCING_BALANCE"],days[-1])
        self.assertEqual((result["tasks"]["5_TOP"]["tp"],result["tasks"]["5_TOP"]["fn"]),(0,1))

    def test_old_turning_but_recent_confirmation_stays_unmatured(self):
        days,prices=inputs()
        a=alert(days,200,"alert_old")
        p=pivot(days,205,"pivot_late",confirm_delay=210)
        # Turning is old enough, but confirmation day has not received
        # the 140-session maturity buffer at evaluation asof.
        observed=m.audit_preopen([a],[p],prices,{"alert_old":evidence(days,a)},
                                 ["INDEX_CLOSE","FINANCING_BALANCE"],days[-1])
        row=observed["tasks"]["5_TOP"]
        self.assertEqual((row["tp"],row["fn"],row["mature_pivots"]),(0,0,0))
        self.assertEqual((row["fp"],row["pending"]),(0,1))
        self.assertEqual(row["events"][0]["pivot_id"],None)

    def test_mature_confirmation_requires_full_140_session_buffer(self):
        days,prices=inputs()
        a=alert(days,200,"alert_early")
        # confirm index 400, 139 days of subsequent sessions: not mature.
        p=pivot(days,205,"pivot_late",confirm_delay=195)
        observed=m.audit_preopen([a],[p],prices,{"alert_early":evidence(days,a)},
                                 ["INDEX_CLOSE","FINANCING_BALANCE"],days[-1])
        self.assertEqual(observed["tasks"]["5_TOP"]["mature_pivots"],0)
        # After cutting evaluation even shorter it must remain unscored.
        observed2=m.audit_preopen([a],[p],prices,{"alert_early":evidence(days,a)},
                                  ["INDEX_CLOSE","FINANCING_BALANCE"],days[-2])
        self.assertEqual(observed2["tasks"]["5_TOP"]["mature_pivots"],0)

    def test_index_missing_confirmation_fails_not_future_labels(self):
        days,prices=inputs()
        a=alert(days,200,"a")
        p=pivot(days,208,"p")
        p["confirmation_date"]="2027-09-09"
        with self.assertRaisesRegex(ValueError,"confirmation beyond"):
            m.audit_preopen([a],[p],prices,{"a":evidence(days,a)},
                            ["INDEX_CLOSE","FINANCING_BALANCE"],days[-1])

    def test_partial_history_left_censored_extreme_excluded_from_recall(self):
        days,prices=inputs()
        pivot_row=pivot(days,215,"left")
        pivot_row["first_segment_left_censored"]="true"
        a=alert(days,210,"alert_near_unobservable_start")
        out=m.audit_preopen([a],[pivot_row],prices,{a["id"]:evidence(days,a)},
                            ["INDEX_CLOSE","FINANCING_BALANCE"],days[-1])
        row=out["tasks"]["5_TOP"]
        self.assertEqual((row["tp"],row["fp"],row["fn"],row["pending"]),(0,0,0,0))
        self.assertEqual(row["excluded_left_censored_alerts"],1)
        self.assertEqual(row["excluded_left_censored_pivots"],1)
        self.assertEqual(row["scored_formal_alerts"],0)
        self.assertIsNone(row["precision_scored"])
        self.assertIsNone(row["recall_mature"])
        self.assertEqual(row["events"][0]["result"],"EXCLUDED_LEFT_CENSORED")

    def test_left_censored_label_does_not_hide_valid_mature_event(self):
        days,prices=inputs()
        left=pivot(days,205,"truncated")
        left["first_segment_left_censored"]="true"
        normal=pivot(days,305,"valid",confirm_delay=25)
        alerts=[alert(days,200,"near_left"),alert(days,300,"near_valid")]
        report=m.audit_preopen(alerts,[left,normal],prices,
                               {a["id"]:evidence(days,a) for a in alerts},
                               ["INDEX_CLOSE","FINANCING_BALANCE"],days[-1])
        task=report["tasks"]["5_TOP"]
        self.assertEqual((task["tp"],task["fp"],task["fn"]),(1,0,0))
        self.assertEqual(task["excluded_left_censored_alerts"],1)
        self.assertEqual(task["excluded_left_censored_pivots"],1)
        self.assertEqual(task["mature_pivots"],1)
        self.assertEqual(task["precision_scored"],1)
        self.assertEqual(task["recall_mature"],1)
        self.assertFalse(report["formal_signal_allowed"])

    def test_left_censor_must_be_first_label_per_scale(self):
        days,prices=inputs()
        first=pivot(days,200,"first")
        later=pivot(days,245,"later")
        later["first_segment_left_censored"]="true"
        with self.assertRaisesRegex(ValueError,"must be earliest"):
            m.audit_preopen([], [first,later],prices,{},["INDEX_CLOSE"],days[-1])

    def test_multiple_left_boundary_labels_rejected(self):
        days,prices=inputs()
        a=pivot(days,200,"left1")
        b=pivot(days,205,"left2")
        a["first_segment_left_censored"]="true"
        b["first_segment_left_censored"]="true"
        with self.assertRaisesRegex(ValueError,"multiple left-censored"):
            m.audit_preopen([], [a,b],prices,{},["INDEX_CLOSE"],days[-1])

    def test_boundary_is_specific_to_scale_not_global(self):
        days,prices=inputs()
        a=alert(days,210,"scale9_alert",scale="9")
        left=pivot(days,215,"left5")
        left["first_segment_left_censored"]="true"
        # Only 5% TOP is left-censored. A 9% TOP alert remains scoreable.
        report=m.audit_preopen([a],[left],prices,{a["id"]:evidence(days,a)},
                               ["INDEX_CLOSE","FINANCING_BALANCE"],days[-1])
        t=report["tasks"]["9_TOP"]
        self.assertEqual((t["fp"],t["excluded_left_censored_alerts"]),(1,0))


    def test_legacy_active_updates_are_not_new_alerts(self):
        days,prices=inputs()
        a=alert(days,200,"a")
        a["event_type"]="ACTIVE"
        with self.assertRaisesRegex(ValueError,"ACTIVE"):
            m.audit_preopen([a],[],prices,{"a":evidence(days,a)},
                            ["INDEX_CLOSE","FINANCING_BALANCE"],days[-1])

    def test_four_scales_separate(self):
        days,prices=inputs()
        aa=[alert(days,200,"a5","5"),alert(days,200,"a9","9"),
            alert(days,220,"bottom","9","BOTTOM")]
        pp=[pivot(days,215,"p5","5"),pivot(days,215,"p9","9")]
        av={a["id"]:evidence(days,a) for a in aa}
        result=m.audit_preopen(aa,pp,prices,av,
                               ["INDEX_CLOSE","FINANCING_BALANCE"],days[-1])
        self.assertEqual(result["tasks"]["5_TOP"]["tp"],0)
        self.assertEqual(result["tasks"]["9_TOP"]["tp"],1)
        self.assertEqual(result["tasks"]["9_BOTTOM"]["fp"],1)

    def test_prices_sorted(self):
        days,prices=inputs()
        swapped=list(prices)
        swapped[100],swapped[101]=swapped[101],swapped[100]
        with self.assertRaisesRegex(ValueError,"strictly increasing"):
            m.audit_preopen([],[],swapped,{},["INDEX_CLOSE"],days[-1])


if __name__=="__main__":
    unittest.main()
