"""Synthetic event matching proofs only; NEVER historical formal-alarm results."""
import importlib.util
from itertools import combinations
from pathlib import Path
import unittest

module=Path(__file__).with_name("preopen_event_audit.py")
spec=importlib.util.spec_from_file_location("v97_matching_proof",module)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

DATES=[f"2026-10-{day:02d}" for day in range(1,12)]
POSITION={__import__("datetime").date.fromisoformat(d):i for i,d in enumerate(DATES)}


def alerts(indices):
    return [{"date":DATES[i],"id":f"a{i}"} for i in indices]


def pivots(indices):
    return [{"date":DATES[i],"id":f"p{i}"} for i in indices]


def exhaustive_cardinality(aa,pp,maxlead):
    """Independent exhaustive solver, not the implementation under test."""
    options=[]
    for a in aa:
        choices=[j for j,p in enumerate(pp)
                 if 1<=int(p["date"][-2:])-int(a["date"][-2:])<=maxlead]
        options.append(choices)
    def recurse(k,used):
        if k>=len(options):
            return 0
        skip=recurse(k+1,used)
        selected=max([1+recurse(k+1,used|{j}) for j in options[k] if j not in used] or [0])
        return max(skip,selected)
    return recurse(0,set())


class ChronologicalMatchingTests(unittest.TestCase):
    def test_two_alarms_two_pivots_do_not_cross(self):
        # Old augmenting-path DFS chose later pivot for earlier alert.
        aa=alerts((1,2))
        pp=pivots((5,6))
        matched=m.max_match(aa,pp,POSITION,10)
        self.assertEqual(matched,{0:0,1:1})
        self.assertEqual(len(matched),2)

    def test_exact_threshold_and_same_day_not_early(self):
        self.assertEqual(m.max_match(alerts((3,)),pivots((3,)),POSITION,3),{})
        self.assertEqual(m.max_match(alerts((3,)),pivots((6,)),POSITION,3),{0:0})
        self.assertEqual(m.max_match(alerts((3,)),pivots((7,)),POSITION,3),{})

    def test_unmatched_earlier_pivot_must_not_prevent_newer_match(self):
        result=m.max_match(alerts((0,5)),pivots((4,6)),POSITION,2)
        self.assertEqual(result,{1:1})

    def test_ordered_for_replay_is_explicit(self):
        with self.assertRaisesRegex(ValueError,"alerts not chronological"):
            m.max_match(alerts((5,1)),pivots((6,7)),POSITION,10)
        with self.assertRaisesRegex(ValueError,"pivots not chronological"):
            m.max_match(alerts((0,1)),pivots((6,2)),POSITION,10)

    def test_exhaustive_small_case_matches_max_cardinality(self):
        # Thousands of independent comparisons across boundary and overlap
        # cases; this is about ALGORITHM correctness, not market performance.
        idx=range(8)
        subsets=[tuple()] + [
            subset for size in (1,2,3)
            for subset in combinations(idx,size)
        ]
        checked=0
        for maxlead in (1,2,3,4):
            for aa_indices in subsets:
                aa=alerts(aa_indices)
                for pp_indices in subsets:
                    pp=pivots(pp_indices)
                    result=m.max_match(aa,pp,POSITION,maxlead)
                    optimal=exhaustive_cardinality(aa,pp,maxlead)
                    self.assertEqual(len(result),optimal, (aa_indices,pp_indices,maxlead))
                    pairs=sorted(result.items())
                    self.assertEqual([j for _,j in pairs],
                                     sorted(j for _,j in pairs),
                                     "crossed objective pivot assignment")
                    for a,p in pairs:
                        self.assertTrue(1<=pp_indices[p]-aa_indices[a]<=maxlead)
                    checked+=1
        self.assertGreater(checked,30000)


if __name__=="__main__":
    unittest.main()
