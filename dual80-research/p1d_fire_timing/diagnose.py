"""P1d: attribute frozen past_rank90 fires, hits, and misses.

Write the plan before any measurement. This path hashes sources and does not
read feature values or event rows:

    python -B diagnose.py --write-plan-only

Then attribute the two frozen scores. The script refuses to start without
plan.json and refuses to rewrite the plan:

    python -B diagnose.py
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CLOCK = ROOT / 'dual80-research' / 'label_clock_v4'
P1 = ROOT / 'dual80-research' / 'p1_score_alignment'
P1B = ROOT / 'dual80-research' / 'p1b_feature_timing'
P1C = ROOT / 'dual80-research' / 'p1c_slow_feature_score'
TASKS = ('5_TOP', '5_BOTTOM', '9_TOP', '9_BOTTOM')
SCORES = ('frozen_six', 'slow_four')
SLOW_FEATURES = (
    'return20_scaled',
    'distance_to_20day_high_scaled',
    'distance_to_20day_low_scaled',
    'position63',
)
SOURCE_FILES = (
    'ACTIVE_RESEARCH_CONTRACT.json',
    'turning-research-canonical/tables/research_inputs.csv',
    'turning-label-comparison/all_labels.csv',
    'dual80-research/broad_experiments_v2/run.py',
    'dual80-research/label_clock_v4/run.py',
    'dual80-research/label_clock_v4/rank_replay.py',
    'dual80-research/label_clock_v4/scores.csv',
    'dual80-research/label_clock_v4/rank_metrics.csv',
    'dual80-research/label_clock_v4/rank_events.csv',
    'dual80-research/label_clock_v4/rank_thresholds.csv',
    'dual80-research/p1_score_alignment/plan.json',
    'dual80-research/p1_score_alignment/decision.json',
    'dual80-research/p1_score_alignment/target_windows.csv',
    'dual80-research/p1_score_alignment/eligible_days.csv',
    'dual80-research/p1b_feature_timing/plan.json',
    'dual80-research/p1b_feature_timing/decision.json',
    'dual80-research/p1c_slow_feature_score/plan.json',
    'dual80-research/p1c_slow_feature_score/decision.json',
    'dual80-research/p1c_slow_feature_score/metrics_compare.csv',
    'dual80-research/p1c_slow_feature_score/alerts.csv',
    'dual80-research/p1c_slow_feature_score/eligible_days.csv',
)

FINE_TO_SUMMARY = {
    'hit_on_first_window_tail': 'hit',
    'hit_after_earlier_window_tail': 'hit',
    'delay_fire_at_plus1': 'delay_to_plus1',
    'delay_fire_at_plus2_to_plus6': 'delay_to_plus1',
    'weak_no_eligible_day': 'in_window_too_weak',
    'weak_never_in_tail': 'in_window_too_weak',
    'other_fired_in_window_unmatched': 'other',
    'other_late_fire_belongs_to_other_pivot': 'other',
    'other_tail_blocked_by_lock': 'other',
    'other_tail_blocked_by_no_rearm': 'other',
    'other_tail_blocked_by_lock_or_rearm': 'other',
}
SUMMARY_BUCKETS = ('delay_to_plus1', 'in_window_too_weak', 'other')
FP_BUCKETS = (
    'too_late_last_input_is_pivot_close',
    'too_late_last_input_after_pivot_close',
    'in_window_false_alarm',
)

CORE = {
    'phase': 'P1d',
    'title': 'Are past_rank90 misses delayed until offset +1, or is the hittable window too weak?',
    'contains_measurements': False,
    'hypothesis': (
        'P1 found that the frozen six-feature score peaks at offset +1, and that only '
        '21% of misses with a scoreable day ever entered the causal tail. P1c found that '
        'the equal-weight slow-feature score also peaks at offset +1, with lower or '
        'similar precision and recall. This run does not search a new fire rule. It '
        'attributes the actual past_rank90 hits, misses, and false positives of both '
        'frozen scores: a fire at offset +1 or later while a hittable day was already '
        'in the causal tail, versus a hittable window that never entered the tail.'
    ),
    'freeze': {
        'index': '000985.CSI',
        'label': 'close',
        'tasks': list(TASKS),
        'decision_clock': 'pre-open on day D; feature row D uses closes through D-1',
        'offset_definition': (
            'Offset k is decision index pivot_index + k. Its last input index is '
            'pivot_index + k - 1. Offset 0 last input is the previous close. Offset +1 '
            'last input is the pivot close, and an alert that day cannot hit the pivot.'
        ),
        'hittable_window': 'Offsets -6..0. An alert on decision index a hits pivot p when 0 <= p - a <= 6.',
        'matching': 'same scale, same direction, one-to-one, label_clock_v4.run.match',
        'cohort': 'P1 eligible_days.csv and target_windows.csv. The same mature frontier as rank_replay.evaluate.',
        'targets': {'5_TOP': 38, '5_BOTTOM': 39, '9_TOP': 18, '9_BOTTOM': 19},
        'eligible_days': {'5_TOP': 2396, '5_BOTTOM': 2396, '9_TOP': 2057, '9_BOTTOM': 2057},
        'formal_signal_allowed': False,
        'blind_test': False,
        'PIT_certified': False,
        'production_changed': False,
        'new_factors': False,
        'refit_six_feature_model': False,
        'threshold_search': False,
        'fire_rule_search': False,
        'p2_alert_compression': False,
        'fast_features_added': False,
        'prior_decisions_unchanged': {
            'P1': 'BLOCKED_NO_CONCENTRATION',
            'P1b': 'GO_PRE_PIVOT_COORDINATE',
            'P1c': 'BLOCKED_NO_WINDOW_PEAK',
        },
    },
    'scores': {
        'frozen_six': (
            'label_clock_v4 close x price logistic score, group price. Replayed with the '
            'same past_rank90 state machine. Not refit.'
        ),
        'slow_four': (
            'P1c equal-weight sign-aligned expanding z-sum of return20_scaled, '
            'distance_to_20day_high_scaled, distance_to_20day_low_scaled, and position63. '
            'Signs and weights stay as written in the P1c plan. The two fast features stay out.'
        ),
    },
    'fire_rule': {
        'name': 'past_rank90',
        'same_as': 'label_clock_v4/rank_replay.py, the P1 replay, and the P1c replay',
        'lookback_sessions': 252,
        'minimum_previous_scores': 126,
        'quantile': 0.90,
        'quantile_method': 'numpy linear',
        'threshold_inputs': 'Strictly earlier emitted scores inside the lookback. The current score is excluded.',
        'causal_tail': 'A day with a threshold whose score is greater than or equal to that day\'s own threshold.',
        'policy': (
            'Fire on an armed upward cross of that day\'s own threshold. Lock through '
            'decision index i+6. Rearm only on a later score strictly below that later '
            'day\'s own threshold. The quantile is not searched and the lock is not edited.'
        ),
    },
    'populations': {
        'true_hit': 'An evaluated target matched to an alert. The fire offset is a - p and must lie in -6..0. A hit cannot be a +1 fire. If one appears, the run aborts.',
        'false_negative': 'An evaluated target with no matched alert.',
        'false_positive': 'An evaluated alert that match() did not pair with an evaluated target. PENDING alerts are excluded from this population and from the timing buckets.',
        'eligible_window_day': 'A P1 eligible day whose decision index lies in [pivot-6, pivot].',
    },
    'target_buckets': {
        'priority': [
            'hit_on_first_window_tail',
            'hit_after_earlier_window_tail',
            'other_fired_in_window_unmatched',
            'delay_fire_at_plus1',
            'delay_fire_at_plus2_to_plus6',
            'other_late_fire_belongs_to_other_pivot',
            'other_tail_blocked_by_lock',
            'other_tail_blocked_by_no_rearm',
            'other_tail_blocked_by_lock_or_rearm',
            'weak_no_eligible_day',
            'weak_never_in_tail',
        ],
        'definitions': {
            'hit_on_first_window_tail': 'Matched alert in -6..0, and no earlier eligible day in that window is in the causal tail.',
            'hit_after_earlier_window_tail': 'Matched alert in -6..0, and at least one earlier eligible day in that window is already in the causal tail. Those earlier days did not fire.',
            'other_fired_in_window_unmatched': 'False negative, but some eligible day in -6..0 did fire. The alert was consumed by another target or was not the matched alert. This outranks a later fire.',
            'delay_fire_at_plus1': 'False negative, at least one eligible day in -6..0 is in the causal tail, no fire inside -6..0, and an unmatched fire at offset exactly +1.',
            'delay_fire_at_plus2_to_plus6': 'False negative, at least one eligible day in -6..0 is in the causal tail, no fire inside -6..0, no unmatched fire at +1, and an unmatched fire at an offset in +2..+6.',
            'other_late_fire_belongs_to_other_pivot': 'False negative, the window has a causal-tail day, and every fire at +1..+6 is matched to a different evaluated target. That fire is the other pivot\'s hit, not a delayed fire for this one.',
            'other_tail_blocked_by_lock': 'False negative, every eligible in-window tail day is blocked by an active lock, and there is no fire at +1..+6.',
            'other_tail_blocked_by_no_rearm': 'False negative, every eligible in-window tail day is blocked because the rule has not rearmed, and there is no fire at +1..+6.',
            'other_tail_blocked_by_lock_or_rearm': 'False negative, the in-window tail days are a mix of lock and no-rearm, and there is no fire at +1..+6.',
            'weak_no_eligible_day': 'False negative with no eligible day in -6..0.',
            'weak_never_in_tail': 'False negative with at least one eligible day in -6..0, and none of those days is in the causal tail. A fire or a tail at +1 does not move this bucket.',
        },
        'summary': {
            'delay_to_plus1': ['delay_fire_at_plus1', 'delay_fire_at_plus2_to_plus6'],
            'in_window_too_weak': ['weak_no_eligible_day', 'weak_never_in_tail'],
            'other': [
                'other_fired_in_window_unmatched',
                'other_late_fire_belongs_to_other_pivot',
                'other_tail_blocked_by_lock',
                'other_tail_blocked_by_no_rearm',
                'other_tail_blocked_by_lock_or_rearm',
            ],
            'hit': ['hit_on_first_window_tail', 'hit_after_earlier_window_tail'],
        },
        'unmatched_fire': (
            'A fire at offset +1..+6 is unmatched when match() did not pair it with a '
            'different evaluated target. False positives and pending fires count as '
            'unmatched. A fire paired with another evaluated target does not.'
        ),
        'later_cap': (
            'Later means offsets +2..+6 only. A fire at +7 or beyond is outside the '
            'pre-registered late shoulder, which has the same width as the hit window. '
            'That cap was not chosen from these counts.'
        ),
        'not_delay': (
            'A tail or a fire at +1 with no eligible causal-tail day inside -6..0 is not '
            'delay-to-+1. The same threshold would not have fired on a hittable day. '
            'That case stays in-window-too-weak and is reported separately.'
        ),
    },
    'false_positive_buckets': {
        'population': 'Evaluated false positives only. Pending alerts are excluded.',
        'pivots_used': 'All close-label same-scale same-direction pivots, including pivots outside the mature cohort. Retrospective labels, not features.',
        'priority': list(FP_BUCKETS),
        'definitions': {
            'too_late_last_input_is_pivot_close': 'Some same-direction pivot index equals alert_index - 1. The last input is that pivot close. This is the +1-style fire.',
            'too_late_last_input_after_pivot_close': 'No pivot at alert_index - 1, and some same-direction pivot lies in [alert-6, alert-2]. The last input is already after that pivot close.',
            'in_window_false_alarm': 'No same-direction pivot lies in [alert-6, alert-1]. The fire is not a +1..+6 post-pivot emission. The name means a false alarm that is not too late, not a claim that the day sits inside a target window.',
        },
    },
    'decision_rule': {
        'unit': 'One evaluated false negative on one score. Hits are reported and are not in this denominator, because a hit already fired on a hittable day.',
        'counts': {
            'D': 'False negatives whose summary is delay_to_plus1.',
            'W': 'False negatives whose summary is in_window_too_weak.',
            'O': 'False negatives whose summary is other.',
            'identity': 'D + W + O = FN. TP + FN = targets. The three false-positive buckets sum to FP.',
        },
        'task_class': {
            'DELAY': 'D * 2 > FN. This is the integer form of D/FN > 1/2.',
            'WEAK': 'W * 2 > FN.',
            'OTHER': 'O * 2 > FN.',
            'SPLIT': 'None of the three inequalities holds, including an exact tie such as 4 and 4 out of 8.',
            'exclusive': 'At most one of D, W, O can satisfy count * 2 > FN, because the three counts sum to FN.',
        },
        'score_class': {
            'EARLY': 'At least 3 of the 4 tasks are DELAY.',
            'WEAK': 'At least 3 of the 4 tasks are WEAK.',
            'MIXED': 'Otherwise, including 2 and 2 and a majority of OTHER or SPLIT.',
        },
        'pr_decision_order': [
            'BLOCKED_INSUFFICIENT_SAMPLE if any task on either score has FN < 8 or FP < 8',
            'else GO_EARLY_FIRE_TRIAL if both scores are EARLY',
            'else GO_NEW_FACTORS if both scores are WEAK',
            'else MIXED',
        ],
        'majority_share_integer': 'count * 2 > FN',
        'minimum_tasks': 3,
        'n_tasks': 4,
        'fn_min': 8,
        'fp_min': 8,
        'why_denominator_is_all_misses': (
            'The gap is the misses. D/FN > 1/2 means delay-to-+1, not a weak window and '
            'not lock or rearm, is the majority explanation of those misses. Using only '
            'D/(D+O) would call the task DELAY even when almost every miss never entered '
            'the tail. That would contradict GO_NEW_FACTORS. Hits stay in the tables. '
            'D/(D+O) and D/(TP+D+O) are reported and are not gates.'
        ),
        'go_early_meaning': (
            'Both scores have a 3-of-4 task majority of misses explained by an unmatched '
            'fire at +1..+6 while a hittable day was already in the causal tail. The '
            'single pre-registered variant below may be recommended. It is not implemented '
            'in this PR. GO_EARLY_FIRE_TRIAL does not loosen the P1 or P1c gates, does not '
            'open P2, does not raise a threshold, and does not authorize a signal.'
        ),
        'go_new_factors_meaning': (
            'On both scores, a 3-of-4 task majority of misses never entered the causal tail '
            'on a hittable day. Moving the fire earlier on this same threshold cannot '
            'recover them. The next step is features outside this price family, each gated '
            'on point-in-time availability. That work is not implemented here. The two fast '
            'price features are not added back.'
        ),
        'mixed_meaning': (
            'The two scores disagree, or a score has no 3-of-4 DELAY or WEAK majority. '
            'Report the counts. Do not relabel OTHER as delay. Do not loosen the buckets.'
        ),
        'examples': {
            'DELAY': '5 delay, 3 other, 0 weak out of 8, because 5 * 2 > 8.',
            'SPLIT_tie': '4 delay and 4 weak out of 8, because 4 * 2 > 8 is false.',
            'WEAK': '3 delay and 6 weak out of 9, because 6 * 2 > 9 and 3 * 2 > 9 is false.',
        },
    },
    'conditional_variant_not_run': {
        'name': 'emit_on_suppressed_hittable_tail',
        'recommended_only_if': 'GO_EARLY_FIRE_TRIAL',
        'implemented': False,
        'score': 'frozen_six only',
        'change': (
            'Keep the causal past_rank90 threshold. On a day that is in that tail and does '
            'not fire only because the state is locked or not rearmed, emit an alert that '
            'day. Do not change the quantile, the features, the label, the index, or the '
            'hit window. Do not search another variant.'
        ),
    },
    'reported_not_gates': [
        'precision, recall, TP, FP, FN, alerts, and pending, copied from the locked ledgers',
        'the hit-offset histogram on -6..0',
        'hits with an earlier in-window causal-tail day',
        'hits for which offset +1 is also in the causal tail',
        'within each false-negative summary, how many have offset +1 in the causal tail, and how many fire at offset +1',
        'the fine buckets inside delay_to_plus1 and other',
        'the three false-positive timing buckets',
        'pooled sums across the four tasks',
        'D/(D+O) among tail-entering misses, and D/(TP+D+O) among tail-entering targets',
    ],
    'leakage': [
        'Editing a bucket, the +6 cap, or the majority test after seeing the counts.',
        'Calling a +1 tail a delay when no hittable day was in the tail.',
        'Calling another pivot\'s matched fire a delayed fire for this pivot.',
        'Treating offset +1 as a hit.',
        'Searching a threshold, a lock length, or a new fire rule in this PR.',
        'Adding return3_scaled, change_in_return3_scaled, or any feature outside the frozen scores.',
        'Refitting the six-feature model or changing P1c weights or signs.',
        'Using a future target count as an alert quota.',
        'Changing the label, the index, or the hit window.',
        'Putting the decision session close into a feature at offsets -6..0.',
    ],
    'out_of_scope': [
        'No implementation of emit_on_suppressed_hittable_tail.',
        'No new factor and no point-in-time audit of a new factor.',
        'No Phase P2 alert compression.',
        'No production page, collector, official signal, or V-series workflow.',
        'P1, P1b, and P1c conclusions are not rewritten.',
        'formal_signal_allowed stays false.',
        'Not PIT and not a blind test. Not dual-80.',
    ],
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes() -> dict[str, str]:
    return {rel: sha256_file(ROOT / rel) for rel in SOURCE_FILES}


def build_plan() -> dict:
    plan = dict(CORE)
    plan['source_sha256'] = source_hashes()
    return plan


def assert_plan_frozen() -> dict:
    path = HERE / 'plan.json'
    if not path.exists():
        raise SystemExit('plan.json is missing. Run: python -B diagnose.py --write-plan-only')
    on_disk = json.loads(path.read_text(encoding='utf-8'))
    core_on_disk = {key: value for key, value in on_disk.items() if key != 'source_sha256'}
    if core_on_disk != CORE:
        raise SystemExit('plan.json core does not match the pre-registered CORE in diagnose.py')
    if on_disk.get('contains_measurements') is not False:
        raise SystemExit('plan.json must not contain measurements')
    current = source_hashes()
    if on_disk.get('source_sha256') != current:
        raise SystemExit('source files changed after plan.json was written')
    rule = on_disk['decision_rule']
    if rule['minimum_tasks'] != 3 or rule['n_tasks'] != 4 or rule['fn_min'] != 8 or rule['fp_min'] != 8:
        raise SystemExit('decision floors drifted')
    if rule['majority_share_integer'] != 'count * 2 > FN':
        raise SystemExit('majority test drifted')
    if set(FINE_TO_SUMMARY) != set(on_disk['target_buckets']['priority']):
        raise SystemExit('bucket names drifted from the pre-registered priority')
    return on_disk


def write_plan_only() -> None:
    path = HERE / 'plan.json'
    if path.exists():
        raise SystemExit('plan.json already exists and is not rewritten')
    path.write_text(json.dumps(build_plan(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'wrote': str(path), 'contains_measurements': False}, ensure_ascii=False))


def load_rows(path: Path) -> list[dict]:
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def as_bool(text: str) -> bool:
    if text == 'true':
        return True
    if text == 'false':
        return False
    raise SystemExit(f'expected true or false, got {text!r}')


def task_class(delay: int, weak: int, other: int) -> str:
    fn = delay + weak + other
    if delay * 2 > fn:
        return 'DELAY'
    if weak * 2 > fn:
        return 'WEAK'
    if other * 2 > fn:
        return 'OTHER'
    return 'SPLIT'


def score_class(classes: list[str]) -> str:
    if len(classes) != 4:
        raise SystemExit('a score must have four task classes')
    if sum(item == 'DELAY' for item in classes) >= 3:
        return 'EARLY'
    if sum(item == 'WEAK' for item in classes) >= 3:
        return 'WEAK'
    return 'MIXED'


def pr_decision(floors_ok: bool, frozen_class: str, slow_class: str) -> str:
    if not floors_ok:
        return 'BLOCKED_INSUFFICIENT_SAMPLE'
    if frozen_class == 'EARLY' and slow_class == 'EARLY':
        return 'GO_EARLY_FIRE_TRIAL'
    if frozen_class == 'WEAK' and slow_class == 'WEAK':
        return 'GO_NEW_FACTORS'
    return 'MIXED'


def classify_fp(alert: int, same_pivots: list[int]) -> str:
    look = [pivot for pivot in same_pivots if alert - 6 <= pivot <= alert - 1]
    if any(pivot == alert - 1 for pivot in look):
        return 'too_late_last_input_is_pivot_close'
    if look:
        return 'too_late_last_input_after_pivot_close'
    return 'in_window_false_alarm'


def classify_target(pivot: int, alert: int | None, window: list[int], days: dict,
                    matched_alert_to_pivot: dict[int, int]) -> tuple[str, dict]:
    window_tail = [i for i in window if days[i]['in_tail']]
    window_fires = [i for i in window if days[i]['fired']]
    if len(window_fires) > 1:
        raise SystemExit(f'more than one fire inside a seven-session window at pivot {pivot}')
    late = [i for i in range(pivot + 1, pivot + 7) if i in days and days[i]['fired']]
    unmatched_late = []
    for i in late:
        other = matched_alert_to_pivot.get(i)
        if other is None:
            unmatched_late.append(i)
        elif other == pivot:
            raise SystemExit('a post-pivot fire matched this same pivot')
    plus1 = days.get(pivot + 1)
    flags = {
        'n_window_tail': len(window_tail),
        'late_offsets': [i - pivot for i in late],
        'unmatched_late_offsets': [i - pivot for i in unmatched_late],
        'plus1_in_tail': bool(plus1 and plus1['in_tail']),
        'plus1_fired': bool(plus1 and plus1['fired']),
        'earlier_blocks': [],
        'fire_offset': None if alert is None else alert - pivot,
        'fire_day_eligible': alert in window if alert is not None else False,
    }
    if alert is not None:
        if not (-6 <= alert - pivot <= 0):
            raise SystemExit('matched alert is outside offsets -6..0')
        if alert not in days or not days[alert]['fired'] or not days[alert]['in_tail']:
            raise SystemExit('matched alert is not an in-tail fire')
        # The slow score can fire on a day that is not in this task's P1 eligible set.
        # The hit rule only requires the offset to lie in -6..0. Earlier-tail uses eligible days.
        if alert in window:
            if window_fires != [alert]:
                raise SystemExit('the matched fire is missing from the eligible window')
        elif window_fires:
            raise SystemExit('eligible window fired while the matched alert lies outside it')
        earlier = [i for i in window_tail if i < alert]
        flags['earlier_blocks'] = sorted({days[i]['block'] for i in earlier})
        if any(block not in ('locked', 'not_rearmed') for block in flags['earlier_blocks']):
            raise SystemExit(f'earlier tail block is not lock or rearm: {flags["earlier_blocks"]}')
        bucket = 'hit_after_earlier_window_tail' if earlier else 'hit_on_first_window_tail'
        return bucket, flags
    if window_fires:
        bucket = 'other_fired_in_window_unmatched'
    elif window_tail and unmatched_late:
        if 1 in flags['unmatched_late_offsets']:
            bucket = 'delay_fire_at_plus1'
        else:
            bucket = 'delay_fire_at_plus2_to_plus6'
    elif window_tail and late:
        bucket = 'other_late_fire_belongs_to_other_pivot'
    elif window_tail:
        reasons = {days[i]['block'] for i in window_tail}
        if reasons == {'locked'}:
            bucket = 'other_tail_blocked_by_lock'
        elif reasons == {'not_rearmed'}:
            bucket = 'other_tail_blocked_by_no_rearm'
        elif reasons <= {'locked', 'not_rearmed'} and reasons:
            bucket = 'other_tail_blocked_by_lock_or_rearm'
        else:
            raise SystemExit(f'unexpected in-window tail blocks {reasons} at pivot {pivot}')
    elif not window:
        bucket = 'weak_no_eligible_day'
    else:
        bucket = 'weak_never_in_tail'
    return bucket, flags


def self_test() -> None:
    def day(in_tail=False, fired=False, block=''):
        return {'in_tail': in_tail, 'fired': fired, 'block': block, 'threshold': 0.0}

    def expect(bucket, **kwargs):
        got, _flags = classify_target(**kwargs)
        if got != bucket:
            raise SystemExit(f'self-test expected {bucket}, got {got}')

    days = {i: day() for i in range(0, 20)}
    expect('weak_no_eligible_day', pivot=10, alert=None, window=[], days=days, matched_alert_to_pivot={})
    expect('weak_never_in_tail', pivot=10, alert=None, window=[8, 9, 10], days=days, matched_alert_to_pivot={})
    days[11] = day(in_tail=True, fired=True, block='fired')
    expect(
        'weak_never_in_tail', pivot=10, alert=None, window=[8, 9, 10], days=days,
        matched_alert_to_pivot={},
    )
    days[9] = day(in_tail=True, block='locked')
    expect(
        'delay_fire_at_plus1', pivot=10, alert=None, window=[8, 9, 10], days=days,
        matched_alert_to_pivot={},
    )
    days[11] = day(in_tail=True, block='locked')
    days[13] = day(in_tail=True, fired=True, block='fired')
    expect(
        'delay_fire_at_plus2_to_plus6', pivot=10, alert=None, window=[8, 9, 10], days=days,
        matched_alert_to_pivot={},
    )
    days[9] = day(in_tail=True, block='locked')
    days[11] = day()
    days[13] = day()
    expect(
        'other_tail_blocked_by_lock', pivot=10, alert=None, window=[8, 9, 10], days=days,
        matched_alert_to_pivot={},
    )
    days[8] = day(in_tail=True, fired=True, block='fired')
    days[11] = day(in_tail=True, fired=True, block='fired')
    expect(
        'other_fired_in_window_unmatched', pivot=10, alert=None, window=[8, 9, 10], days=days,
        matched_alert_to_pivot={8: 4},
    )
    days[8] = day(in_tail=True, block='not_rearmed')
    days[11] = day(in_tail=True, fired=True, block='fired')
    expect(
        'other_late_fire_belongs_to_other_pivot', pivot=10, alert=None, window=[8, 9, 10],
        days=days, matched_alert_to_pivot={11: 16},
    )
    days = {i: day() for i in range(0, 20)}
    days[6] = day(in_tail=True, block='not_rearmed')
    days[8] = day(in_tail=True, fired=True, block='fired')
    expect(
        'hit_after_earlier_window_tail', pivot=10, alert=8, window=[4, 5, 6, 7, 8, 9, 10],
        days=days, matched_alert_to_pivot={8: 10},
    )
    days[6] = day()
    expect(
        'hit_on_first_window_tail', pivot=10, alert=8, window=[4, 5, 6, 7, 8, 9, 10],
        days=days, matched_alert_to_pivot={8: 10},
    )
    outside = {i: day() for i in range(0, 20)}
    outside[8] = day(in_tail=True, fired=True, block='fired')
    expect(
        'hit_on_first_window_tail', pivot=10, alert=8, window=[], days=outside,
        matched_alert_to_pivot={8: 10},
    )
    if classify_fp(10, [9]) != 'too_late_last_input_is_pivot_close':
        raise SystemExit('fp +1 bucket failed')
    if classify_fp(10, [7]) != 'too_late_last_input_after_pivot_close':
        raise SystemExit('fp later bucket failed')
    if classify_fp(10, [9, 6]) != 'too_late_last_input_is_pivot_close':
        raise SystemExit('fp +1 priority failed')
    if classify_fp(10, [13]) != 'in_window_false_alarm':
        raise SystemExit('fp future pivot failed')
    if classify_fp(10, [3]) != 'in_window_false_alarm':
        raise SystemExit('fp pivot outside six sessions failed')
    if task_class(5, 3, 0) != 'DELAY' or task_class(4, 4, 0) != 'SPLIT':
        raise SystemExit('task class boundary failed')
    if task_class(3, 6, 0) != 'WEAK' or task_class(2, 2, 5) != 'OTHER' or task_class(3, 3, 3) != 'SPLIT':
        raise SystemExit('task class split failed')
    if score_class(['DELAY', 'DELAY', 'DELAY', 'WEAK']) != 'EARLY':
        raise SystemExit('score EARLY failed')
    if score_class(['WEAK', 'WEAK', 'WEAK', 'DELAY']) != 'WEAK':
        raise SystemExit('score WEAK failed')
    if score_class(['DELAY', 'DELAY', 'WEAK', 'WEAK']) != 'MIXED':
        raise SystemExit('score tie failed')
    if pr_decision(False, 'EARLY', 'EARLY') != 'BLOCKED_INSUFFICIENT_SAMPLE':
        raise SystemExit('floor priority failed')
    if pr_decision(True, 'EARLY', 'EARLY') != 'GO_EARLY_FIRE_TRIAL':
        raise SystemExit('early decision failed')
    if pr_decision(True, 'WEAK', 'WEAK') != 'GO_NEW_FACTORS':
        raise SystemExit('weak decision failed')
    if pr_decision(True, 'EARLY', 'WEAK') != 'MIXED' or pr_decision(True, 'MIXED', 'WEAK') != 'MIXED':
        raise SystemExit('mixed decision failed')
    if set(FINE_TO_SUMMARY) != set(CORE['target_buckets']['priority']):
        raise SystemExit('fine buckets do not match the plan')
    for name, summary in FINE_TO_SUMMARY.items():
        if name.startswith('hit') and summary != 'hit':
            raise SystemExit('hit summary drifted')
        if name.startswith('delay') and summary != 'delay_to_plus1':
            raise SystemExit('delay summary drifted')
        if name.startswith('weak') and summary != 'in_window_too_weak':
            raise SystemExit('weak summary drifted')
        if name.startswith('other') and summary != 'other':
            raise SystemExit('other summary drifted')


def replay_series(values: np.ndarray) -> tuple[dict, list[int]]:
    hist: list[tuple[int, float]] = []
    state = {'until': -1, 'armed': True}
    ledger: list[int] = []
    days: dict[int, dict] = {}
    for i, value in enumerate(values):
        if not math.isfinite(float(value)):
            continue
        value = float(value)
        past = [p for j, p in hist if i - 252 <= j < i]
        threshold = None
        fired = False
        locked = i <= state['until']
        armed_before = state['armed']
        if len(past) >= 126:
            threshold = float(np.quantile(np.asarray(past, dtype=float), 0.90, method='linear'))
            if i > state['until'] and value < threshold:
                state['armed'] = True
            if i > state['until'] and state['armed'] and value >= threshold:
                fired = True
                ledger.append(i)
                state['until'] = i + 6
                state['armed'] = False
        block = ''
        if threshold is not None and value >= threshold:
            if fired:
                block = 'fired'
            elif locked:
                block = 'locked'
            elif not armed_before:
                block = 'not_rearmed'
            else:
                raise SystemExit(f'unclassified tail day at index {i}')
        days[i] = {
            'score': value,
            'threshold': threshold,
            'in_tail': threshold is not None and value >= threshold,
            'fired': fired,
            'block': block,
        }
        hist.append((i, value))
        hist = [(j, p) for j, p in hist if j >= i - 252]
    gaps = [ledger[k] - ledger[k - 1] for k in range(1, len(ledger))]
    if any(gap < 7 for gap in gaps):
        raise SystemExit('two fires are fewer than 7 sessions apart')
    return days, ledger


def expanding_sum(raw: np.ndarray, signs: np.ndarray) -> np.ndarray:
    n_rows, width = raw.shape
    if signs.shape != (width,):
        raise SystemExit('sign vector does not match the feature width')
    scores = np.full(n_rows, np.nan)
    sum_x = np.zeros(width, dtype=float)
    sum_x2 = np.zeros(width, dtype=float)
    count = 0
    for i in range(n_rows):
        row = raw[i]
        finite = bool(np.isfinite(row).all())
        if finite and count >= 126:
            mu = sum_x / count
            var = (sum_x2 - (sum_x * sum_x) / count) / (count - 1)
            if float(np.min(var)) < 1e-12:
                raise SystemExit(f'feature variance below 1e-12 at row {i}')
            scores[i] = float(np.dot(signs, (row - mu) / np.sqrt(var)))
        if finite and i >= 252:
            sum_x += row
            sum_x2 += row * row
            count += 1
        elif i >= 252 and not finite:
            raise SystemExit(f'non-finite feature row at {i}')
    return scores


def load_base():
    sys.path.insert(0, str(CLOCK))
    import run as base
    return base


def assert_prior_decisions() -> None:
    expected = {
        P1 / 'decision.json': 'BLOCKED_NO_CONCENTRATION',
        P1B / 'decision.json': 'GO_PRE_PIVOT_COORDINATE',
        P1C / 'decision.json': 'BLOCKED_NO_WINDOW_PEAK',
    }
    for path, code in expected.items():
        if json.loads(path.read_text(encoding='utf-8')).get('decision') != code:
            raise SystemExit(f'{path.name} decision is not the frozen {code}')


def build_score_matrix(base) -> dict[str, dict[str, np.ndarray]]:
    frozen_rows = [
        row for row in load_rows(CLOCK / 'scores.csv')
        if row['label'] == 'close' and row['group'] == 'price'
    ]
    frozen: dict[str, np.ndarray] = {}
    for task in TASKS:
        values = np.full(base.N, np.nan)
        for row in frozen_rows:
            if row['task'] != task:
                continue
            index = base.pos[row['date']]
            if base.pos[row['last_input']] != index - 1:
                raise SystemExit(f'frozen last_input is not D-1 on {task} {row["date"]}')
            values[index] = float(row['score'])
        frozen[task] = values
    price = np.asarray(base.X['price'], dtype=float)
    if price.shape != (base.N, 6):
        raise SystemExit(f'price matrix shape {price.shape}')
    raw = price[:, [1, 3, 4, 5]]
    top = expanding_sum(raw, np.ones(4))
    bottom = expanding_sum(raw, -np.ones(4))
    if not np.allclose(bottom, -top, equal_nan=True):
        raise SystemExit('slow bottom score is not the negation of the top score')
    slow = {'5_TOP': top, '9_TOP': top, '5_BOTTOM': bottom, '9_BOTTOM': bottom}
    return {'frozen_six': frozen, 'slow_four': slow}


def load_eligible(base, plan: dict) -> dict[str, set[int]]:
    eligible = {task: set() for task in TASKS}
    for row in load_rows(P1 / 'eligible_days.csv'):
        index = int(row['index'])
        if base.D[index] != row['date']:
            raise SystemExit(f'eligible date mismatch {row["task"]} {row["date"]}')
        if index in eligible[row['task']]:
            raise SystemExit(f'duplicate eligible day {row["task"]} {row["date"]}')
        eligible[row['task']].add(index)
    for task in TASKS:
        if len(eligible[task]) != plan['freeze']['eligible_days'][task]:
            raise SystemExit(f'{task} eligible count drifted')
    return eligible


def load_published_targets(base) -> dict[str, dict[str, dict]]:
    out = {task: {} for task in TASKS}
    for row in load_rows(P1 / 'target_windows.csv'):
        if row['pivot_date'] in out[row['task']]:
            raise SystemExit(f'duplicate P1 target {row["task"]} {row["pivot_date"]}')
        out[row['task']][row['pivot_date']] = row
        if base.pos[row['pivot_date']] < 0:
            raise SystemExit('pivot date missing from the calendar')
    return out


def lock_eligible_replay(base, days: dict, task: str, score_name: str) -> None:
    if score_name == 'frozen_six':
        path = P1 / 'eligible_days.csv'
        block_field = 'block_reason'
    else:
        path = P1C / 'eligible_days.csv'
        block_field = 'block'
    seen = 0
    for row in load_rows(path):
        if row['task'] != task:
            continue
        seen += 1
        day = days[int(row['index'])]
        if as_bool(row['in_tail']) != day['in_tail'] or as_bool(row['fired']) != day['fired']:
            raise SystemExit(f'{score_name} tail or fire drifted on {task} {row["date"]}')
        if (row.get(block_field) or '') != day['block']:
            raise SystemExit(f'{score_name} block drifted on {task} {row["date"]}')
        if abs(float(row['score']) - day['score']) > 1e-8:
            raise SystemExit(f'{score_name} score drifted on {task} {row["date"]}')
        if day['threshold'] is None or abs(float(row['threshold']) - day['threshold']) > 1e-8:
            raise SystemExit(f'{score_name} threshold drifted on {task} {row["date"]}')
    if seen == 0:
        raise SystemExit(f'no eligible rows for {task}')


def lock_alerts(base, ledger: list[int], pairs, aa_set: set[int], task: str, score_name: str) -> None:
    matched = dict(pairs)
    rebuilt = []
    for alert in ledger:
        if alert < base.START:
            continue
        if alert in matched:
            status, pivot_date = 'TP', base.D[matched[alert]]
        elif alert in aa_set:
            status, pivot_date = 'FP', ''
        else:
            status, pivot_date = 'PENDING', ''
        rebuilt.append((base.D[alert], status, pivot_date))
    if score_name == 'frozen_six':
        artifact = [
            (row['date'], row['status'], row['pivot_date'])
            for row in load_rows(CLOCK / 'rank_events.csv')
            if row['label'] == 'close' and row['group'] == 'price__past_rank90' and row['task'] == task
        ]
    else:
        artifact = [
            (row['date'], row['status'], row['pivot_date'])
            for row in load_rows(P1C / 'alerts.csv')
            if row['task'] == task
        ]
    if rebuilt != artifact:
        raise SystemExit(f'{score_name} alert ledger does not match the frozen file for {task}')


def lock_metrics(met: dict, task: str, score_name: str) -> None:
    if score_name == 'frozen_six':
        rows = [
            row for row in load_rows(CLOCK / 'rank_metrics.csv')
            if row['label'] == 'close' and row['group'] == 'price__past_rank90' and row['task'] == task
        ]
    else:
        rows = [
            row for row in load_rows(P1C / 'metrics_compare.csv')
            if row['source'] == 'slow_feature_score' and row['task'] == task
        ]
    if len(rows) != 1:
        raise SystemExit(f'missing published metrics for {score_name} {task}')
    published = rows[0]
    for key in ('TP', 'FP', 'FN', 'alerts', 'targets', 'pending'):
        if int(met[key]) != int(published[key]):
            raise SystemExit(f'{score_name} {task} {key} {met[key]} != {published[key]}')
    if abs(float(met['precision']) - float(published['precision'])) > 1e-12:
        raise SystemExit(f'{score_name} {task} precision drifted')
    if abs(float(met['recall']) - float(published['recall'])) > 1e-12:
        raise SystemExit(f'{score_name} {task} recall drifted')


def crosswalk_p1(row: dict, published: dict) -> None:
    if published['status'] != row['status']:
        raise SystemExit(f'P1 status drifted for {row["task"]} {row["pivot_date"]}')
    if int(published['n_eligible_days']) != row['n_eligible_window']:
        raise SystemExit(f'P1 window length drifted for {row["task"]} {row["pivot_date"]}')
    if int(published['n_tail_days']) != row['n_window_tail']:
        raise SystemExit(f'P1 tail count drifted for {row["task"]} {row["pivot_date"]}')
    if row['status'] == 'TP':
        if row['summary'] != 'hit' or published['matched_alert_date'] != row['fire_date']:
            raise SystemExit(f'P1 hit drifted for {row["task"]} {row["pivot_date"]}')
        return
    p1_class = published['fn_class']
    if p1_class == 'no_eligible_day' and row['bucket'] != 'weak_no_eligible_day':
        raise SystemExit(f'P1 no-eligible miss was rebucketed for {row["pivot_date"]}')
    if p1_class == 'never_high' and row['bucket'] != 'weak_never_in_tail':
        raise SystemExit(f'P1 never-high miss was rebucketed for {row["pivot_date"]}')
    if p1_class == 'fired_but_unmatched' and row['bucket'] != 'other_fired_in_window_unmatched':
        raise SystemExit(f'P1 unmatched in-window fire was rebucketed for {row["pivot_date"]}')
    tail_classes = {
        'tail_blocked_by_lock', 'tail_blocked_by_no_rearm', 'tail_blocked_by_lock_or_rearm',
    }
    if p1_class in tail_classes and row['summary'] not in ('delay_to_plus1', 'other'):
        raise SystemExit(f'P1 tail miss left the delay/other split for {row["pivot_date"]}')
    if p1_class in ('never_high', 'no_eligible_day') and row['summary'] != 'in_window_too_weak':
        raise SystemExit(f'P1 weak miss left the weak bucket for {row["pivot_date"]}')


def measure(plan: dict) -> dict:
    assert_prior_decisions()
    base = load_base()
    if (base.D[0], base.D[-1], base.N) != ('2011-08-02', '2026-08-25', 3659):
        raise SystemExit('research calendar does not match the canonical 3659-session table')
    matrices = build_score_matrix(base)
    eligible = load_eligible(base, plan)
    published_targets = load_published_targets(base)
    front = {
        scale: min(
            max(goal[0] for goal in base.LABELS[variant][scale] if goal[1] + 140 < base.N)
            for variant in base.LABELS
        )
        for scale in (5, 9)
    }
    target_rows = []
    fp_rows = []
    summaries = []
    for score_name in SCORES:
        for task in TASKS:
            scale = int(task.split('_')[0])
            side = task.split('_')[1]
            days, ledger = replay_series(matrices[score_name][task])
            lock_eligible_replay(base, days, task, score_name)
            labels = base.LABELS['close'][scale]
            met, pairs, aa = base.evaluate(ledger, labels, side, front[scale], base.N)
            lock_metrics(met, task, score_name)
            lock_alerts(base, ledger, pairs, set(aa), task, score_name)
            matched_alert = dict(pairs)
            matched_pivot = {pivot: alert for alert, pivot in pairs}
            goals = [
                goal for goal in labels
                if goal[2] == side and base.START + 7 <= goal[0] <= front[scale] and goal[1] + 140 < base.N
            ]
            if len(goals) != met['targets'] or len(goals) != plan['freeze']['targets'][task]:
                raise SystemExit(f'{task} target count drifted')
            goal_dates = {base.D[goal[0]] for goal in goals}
            if goal_dates != set(published_targets[task]):
                raise SystemExit(f'{task} pivot set drifted from P1 target_windows.csv')
            same = sorted(goal[0] for goal in labels if goal[2] == side)
            fine = Counter()
            plus1_tail_by_summary = Counter()
            plus1_fire_by_summary = Counter()
            for pivot, confirm, _direction in goals:
                window = [i for i in range(pivot - 6, pivot + 1) if i in eligible[task]]
                for index in window:
                    if index not in days or days[index]['threshold'] is None:
                        raise SystemExit(f'eligible day has no threshold on {task} {base.D[index]}')
                alert = matched_pivot.get(pivot)
                bucket, flags = classify_target(pivot, alert, window, days, matched_alert)
                summary = FINE_TO_SUMMARY[bucket]
                fine[bucket] += 1
                if flags['plus1_in_tail']:
                    plus1_tail_by_summary[summary] += 1
                if flags['plus1_fired']:
                    plus1_fire_by_summary[summary] += 1
                best = None
                if window:
                    best = max(window, key=lambda i: (days[i]['score'], -i))
                row = {
                    'task': task,
                    'score': score_name,
                    'pivot_date': base.D[pivot],
                    'confirmation_date': base.D[confirm],
                    'status': 'TP' if alert is not None else 'FN',
                    'bucket': bucket,
                    'summary': summary,
                    'fire_date': '' if alert is None else base.D[alert],
                    'fire_offset': flags['fire_offset'],
                    'n_eligible_window': len(window),
                    'n_window_tail': flags['n_window_tail'],
                    'earlier_tail_blocks': ';'.join(flags['earlier_blocks']),
                    'late_fire_offsets': ';'.join(f'{offset:+d}' for offset in flags['late_offsets']),
                    'unmatched_late_fire_offsets': ';'.join(
                        f'{offset:+d}' for offset in flags['unmatched_late_offsets']
                    ),
                    'plus1_in_tail': flags['plus1_in_tail'],
                    'plus1_fired': flags['plus1_fired'],
                    'fire_day_eligible': flags['fire_day_eligible'],
                    'best_window_offset': None if best is None else best - pivot,
                    'best_window_excess': (
                        None if best is None or days[best]['threshold'] is None
                        else days[best]['score'] - days[best]['threshold']
                    ),
                }
                if score_name == 'frozen_six':
                    crosswalk_p1(row, published_targets[task][row['pivot_date']])
                target_rows.append(row)
            evaluated_fp = []
            for alert in ledger:
                if alert < base.START or alert not in set(aa) or alert in matched_alert:
                    continue
                bucket = classify_fp(alert, same)
                latest = [pivot for pivot in same if alert - 6 <= pivot <= alert - 1]
                nearest = max(latest) if latest else None
                inside = any(pivot - 6 <= alert <= pivot for pivot, _confirm, direction in goals if direction == side)
                fp_rows.append({
                    'task': task,
                    'score': score_name,
                    'date': base.D[alert],
                    'index': alert,
                    'bucket': bucket,
                    'latest_same_pivot_date': '' if nearest is None else base.D[nearest],
                    'latest_same_offset': '' if nearest is None else alert - nearest,
                    'last_input_date': base.D[alert - 1],
                    'inside_evaluated_window': inside,
                })
                evaluated_fp.append(bucket)
            fp_counts = Counter(evaluated_fp)
            if sum(fp_counts.values()) != met['FP']:
                raise SystemExit(f'{score_name} {task} FP buckets do not sum to FP')
            delay = fine['delay_fire_at_plus1'] + fine['delay_fire_at_plus2_to_plus6']
            weak = fine['weak_no_eligible_day'] + fine['weak_never_in_tail']
            other = sum(fine[name] for name, summary in FINE_TO_SUMMARY.items() if summary == 'other')
            hits = fine['hit_on_first_window_tail'] + fine['hit_after_earlier_window_tail']
            if delay + weak + other != met['FN'] or hits != met['TP'] or hits + met['FN'] != met['targets']:
                raise SystemExit(f'{score_name} {task} attribution does not partition the targets')
            floors_ok = met['FN'] >= 8 and met['FP'] >= 8
            summaries.append({
                'task': task,
                'score': score_name,
                'targets': met['targets'],
                'TP': met['TP'],
                'FP': met['FP'],
                'FN': met['FN'],
                'pending': met['pending'],
                'precision': met['precision'],
                'recall': met['recall'],
                'delay_to_plus1': delay,
                'delay_fire_at_plus1': fine['delay_fire_at_plus1'],
                'delay_fire_at_plus2_to_plus6': fine['delay_fire_at_plus2_to_plus6'],
                'in_window_too_weak': weak,
                'weak_no_eligible_day': fine['weak_no_eligible_day'],
                'weak_never_in_tail': fine['weak_never_in_tail'],
                'other': other,
                'other_fired_in_window_unmatched': fine['other_fired_in_window_unmatched'],
                'other_late_fire_belongs_to_other_pivot': fine['other_late_fire_belongs_to_other_pivot'],
                'other_tail_blocked_by_lock': fine['other_tail_blocked_by_lock'],
                'other_tail_blocked_by_no_rearm': fine['other_tail_blocked_by_no_rearm'],
                'other_tail_blocked_by_lock_or_rearm': fine['other_tail_blocked_by_lock_or_rearm'],
                'hit_on_first_window_tail': fine['hit_on_first_window_tail'],
                'hit_after_earlier_window_tail': fine['hit_after_earlier_window_tail'],
                'task_class': task_class(delay, weak, other),
                'floors_ok': floors_ok,
                'plus1_in_tail_among_delay': plus1_tail_by_summary['delay_to_plus1'],
                'plus1_in_tail_among_weak': plus1_tail_by_summary['in_window_too_weak'],
                'plus1_in_tail_among_other': plus1_tail_by_summary['other'],
                'plus1_in_tail_among_hits': plus1_tail_by_summary['hit'],
                'plus1_fired_among_weak': plus1_fire_by_summary['in_window_too_weak'],
                'plus1_fired_among_hits': plus1_fire_by_summary['hit'],
                'fp_too_late_plus1': fp_counts['too_late_last_input_is_pivot_close'],
                'fp_too_late_later': fp_counts['too_late_last_input_after_pivot_close'],
                'fp_in_window_false_alarm': fp_counts['in_window_false_alarm'],
            })
    by_score = {}
    floors_ok = all(row['floors_ok'] for row in summaries)
    for score_name in SCORES:
        classes = [row['task_class'] for row in summaries if row['score'] == score_name]
        by_score[score_name] = score_class(classes)
    decision = pr_decision(floors_ok, by_score['frozen_six'], by_score['slow_four'])
    return {
        'decision': decision,
        'floors_ok': floors_ok,
        'score_class': by_score,
        'summaries': summaries,
        'target_rows': target_rows,
        'fp_rows': fp_rows,
        'variant_recommended': decision == 'GO_EARLY_FIRE_TRIAL',
        'variant_implemented': False,
    }


def offset_text(value) -> str:
    if value is None or value == '':
        return ''
    return f'{int(value):+d}'


def fmt_pct(value) -> str:
    if value is None:
        return ''
    return f'{100 * float(value):.1f}%'


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            out = {}
            for field in fields:
                value = row.get(field)
                if isinstance(value, float):
                    out[field] = f'{value:.12g}'
                elif isinstance(value, bool):
                    out[field] = 'true' if value else 'false'
                elif value is None:
                    out[field] = ''
                else:
                    out[field] = value
            writer.writerow(out)


def pooled(rows: list[dict], score_name: str) -> dict:
    chosen = [row for row in rows if row['score'] == score_name]
    keys = (
        'TP', 'FN', 'FP', 'delay_to_plus1', 'in_window_too_weak', 'other',
        'delay_fire_at_plus1', 'delay_fire_at_plus2_to_plus6',
        'hit_on_first_window_tail', 'hit_after_earlier_window_tail',
        'fp_too_late_plus1', 'fp_too_late_later', 'fp_in_window_false_alarm',
        'plus1_in_tail_among_weak', 'plus1_fired_among_weak', 'plus1_in_tail_among_hits',
    )
    return {key: sum(row[key] for row in chosen) for key in keys}


def decision_paragraphs(result: dict) -> tuple[str, str]:
    score_name = {'frozen_six': 'frozen six-feature', 'slow_four': 'slow-feature'}
    score_name_cn = {'frozen_six': '冻结六特征', 'slow_four': '四慢变量'}
    bits = []
    bits_cn = []
    for row in result['summaries']:
        bits.append(
            f"{row['task']} {score_name[row['score']]} delay {row['delay_to_plus1']} / "
            f"weak {row['in_window_too_weak']} / other {row['other']} "
            f"of {row['FN']} misses ({row['task_class']})"
        )
        bits_cn.append(
            f"{row['task']} {score_name_cn[row['score']]}：推迟 {row['delay_to_plus1']}，"
            f"窗口内太弱 {row['in_window_too_weak']}，其他 {row['other']}，"
            f"漏报 {row['FN']}（{row['task_class']}）"
        )
    frozen = result['score_class']['frozen_six']
    slow = result['score_class']['slow_four']
    if result['decision'] == 'GO_EARLY_FIRE_TRIAL':
        tail = (
            ' The pre-registered variant emit_on_suppressed_hittable_tail may be tried in a '
            'later PR on the frozen six-feature score only. It is not implemented here.'
        )
        tail_cn = '可以在以后的 PR 里只对冻结六特征预注册 emit_on_suppressed_hittable_tail。本 PR 不实现。'
    elif result['decision'] == 'GO_NEW_FACTORS':
        tail = (
            ' Delay does not explain the gap. The next step is features outside this price '
            'family, each gated on point-in-time availability. That work is not implemented '
            'here, and the two fast price features are not added back.'
        )
        tail_cn = '推迟发报解释不了这个缺口。下一步是价格家族之外、并且先过披露时点门禁的特征。本 PR 不实现，也不把两个快变量加回来。'
    else:
        tail = (
            ' Neither an early-fire variant nor a new factor is adopted. The pre-registered '
            'variant was not run.'
        )
        tail_cn = '不采用提前发报变体，也不在这里引入新因子。预登记的变体没有运行。'
    english = (
        "A miss is delay-to-+1 only when an eligible day in -6..0 is "
        "already in the causal tail and an unmatched past_rank90 fire occurs at offset +1..+6. "
        f"A miss is in-window-too-weak when no eligible day in -6..0 is in that tail. A task "
        f"class requires count * 2 > FN; a score requires 3 of 4 tasks. Both scores must agree. "
        f"Frozen six-feature score class: {frozen}. Slow-feature score class: {slow}. "
        + ' '.join(bits)
        + tail
        + ' P1 remains BLOCKED_NO_CONCENTRATION. P1b remains GO_PRE_PIVOT_COORDINATE. '
        'P1c remains BLOCKED_NO_WINDOW_PEAK. formal_signal_allowed stays false. This is not '
        'PIT, not a blind test, and not a signal.'
    )
    chinese = (
        "漏报算作推迟到 +1，必须是 −6..0 里已有可评分因果尾部日，并且 +1..+6 "
        f"有一次没有配给其他拐点的 past_rank90 发报。窗口内没有任何可评分日进入因果尾部，就算窗口内太弱。"
        f"任务类别要求计数的两倍大于漏报数；一条分数要 4 项里至少 3 项同类。两条分数必须一致。"
        f"冻结六特征是 {frozen}。四慢变量是 {slow}。"
        + ' '.join(bits_cn)
        + '。' + tail_cn
        + 'P1 仍是 BLOCKED_NO_CONCENTRATION。P1b 仍是 GO_PRE_PIVOT_COORDINATE。'
        'P1c 仍是 BLOCKED_NO_WINDOW_PEAK。formal_signal_allowed 仍为 false。这不是 PIT，不是盲测，也不是信号。'
    )
    return english, chinese


def render_report(result: dict) -> str:
    english, chinese = decision_paragraphs(result)
    lines = [
        '# P1d 已有 past_rank90 发报是推迟到 +1，还是窗口内根本没进尾部',
        '',
        f"**Decision: `{result['decision']}`.** {english}",
        '',
        f"**结论：`{result['decision']}`。** {chinese}",
        '',
        '这是归因，不是新的发报规则。`formal_signal_allowed` 仍为 false。没有 PIT 认证，没有盲测，没有生产信号。P1、P1b、P1c 的结论不改写，门槛不放宽。',
        '',
        '## 预登记的分桶',
        '',
        '两条分数用同一成熟队列、同一因果 past_rank90：冻结的六个价格特征逻辑回归分数，以及 P1c 四个慢变量的等权符号对齐标准化和。分位、锁定和重新武装都不改。',
        '',
        '偏移 0 的最后输入是拐点前一日收盘，这一天的警报还能打中该拐点。偏移 +1 的最后输入才是拐点收盘，这一天的警报打不中该拐点。真阳性的发报偏移因此只能落在 −6..0；出现 +1 命中会中止，而不是放进推迟桶。',
        '',
        '漏报的三个互斥合计：',
        '',
        '- **推迟到 +1**：−6..0 里已有可评分因果尾部日，窗口内没有发报，并且 +1..+6 有一次没有配给其他拐点的发报。',
        '- **窗口内太弱**：−6..0 里没有可评分日进入因果尾部。即便 +1 进入尾部或在 +1 发报，也不改这个桶。',
        '- **其他**：窗口内发了但没配上，尾部日被锁定或尚未重新武装且 +1..+6 没有未配对发报，或者 +1..+6 的发报其实命中了另一个拐点。',
        '',
        '任务类别用整数比较：某一类计数的两倍大于该任务漏报数，才算这一类占多数。4 对 4 是 SPLIT，不是多数。一条分数要 4 项任务里至少 3 项同为 DELAY 才是 EARLY，至少 3 项同为 WEAK 才是 WEAK。两条分数都是 EARLY 才是 `GO_EARLY_FIRE_TRIAL`；都是 WEAK 才是 `GO_NEW_FACTORS`；样本门槛是每个任务、每条分数的漏报和误报都至少 8。其余是 `MIXED`。',
        '',
        '## 漏报归因',
        '',
        '合计一行只便于阅读，不进入门槛。',
        '',
        '| 分数 | 任务 | 真阳性 | 漏报 | 推迟到 +1 | 其中恰好 +1 | 其中 +2..+6 | 窗口内太弱 | 其他 | 类别 |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---|',
    ]
    score_title = {'frozen_six': '冻结六特征', 'slow_four': '四慢变量'}
    for row in result['summaries']:
        lines.append(
            f"| {score_title[row['score']]} | {row['task']} | {row['TP']} | {row['FN']} | "
            f"{row['delay_to_plus1']} | {row['delay_fire_at_plus1']} | {row['delay_fire_at_plus2_to_plus6']} | "
            f"{row['in_window_too_weak']} | {row['other']} | {row['task_class']} |"
        )
    for score_name in SCORES:
        total = pooled(result['summaries'], score_name)
        lines.append(
            f"| {score_title[score_name]} | 合计（非门槛） | {total['TP']} | {total['FN']} | "
            f"{total['delay_to_plus1']} | {total['delay_fire_at_plus1']} | {total['delay_fire_at_plus2_to_plus6']} | "
            f"{total['in_window_too_weak']} | {total['other']} |  |"
        )
    lines += [
        '',
        '| 分数 | 任务 | 窗口内发了但未配上 | 晚发报属于别的拐点 | 锁定 | 未重新武装 | 锁定与未武装混合 | 无评分日 | 有评分日但从未进尾部 | 弱漏报里 +1 已在尾部 | 弱漏报里 +1 发了报 |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for row in result['summaries']:
        lines.append(
            f"| {score_title[row['score']]} | {row['task']} | {row['other_fired_in_window_unmatched']} | "
            f"{row['other_late_fire_belongs_to_other_pivot']} | {row['other_tail_blocked_by_lock']} | "
            f"{row['other_tail_blocked_by_no_rearm']} | {row['other_tail_blocked_by_lock_or_rearm']} | "
            f"{row['weak_no_eligible_day']} | {row['weak_never_in_tail']} | "
            f"{row['plus1_in_tail_among_weak']} | {row['plus1_fired_among_weak']} |"
        )
    lines += [
        '',
        '图 `fig_miss_buckets.png` 是每个任务的三段漏报计数。弱漏报里「+1 已在尾部」只说明拐点收盘进入特征后分数才到尾部，同一条阈值在可命中日不会发报。',
        '',
        '## 真阳性发在哪一天',
        '',
        '下表是命中这个拐点的警报偏移。有较早尾部日，表示发报之前窗口里已经有因果尾部日，但当天被锁定或尚未重新武装，后来仍在 −6..0 内再次越过并发报。+1 也在尾部，表示拐点后一天同样进入尾部；那一天打不中这个已经配对的拐点。',
        '',
        '| 分数 | 任务 | 真阳性 | 窗口内第一个尾部日就发报 | 更早的尾部日之后才发报 | 命中且 +1 也在尾部 | 命中且 +1 也发了报 |',
        '|---|---|---:|---:|---:|---:|---:|',
    ]
    for row in result['summaries']:
        lines.append(
            f"| {score_title[row['score']]} | {row['task']} | {row['TP']} | "
            f"{row['hit_on_first_window_tail']} | {row['hit_after_earlier_window_tail']} | "
            f"{row['plus1_in_tail_among_hits']} | {row['plus1_fired_among_hits']} |"
        )
    lines += [
        '',
        '| 分数 | 任务 | −6 | −5 | −4 | −3 | −2 | −1 | 0 |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for score_name in SCORES:
        for task in TASKS:
            counts = Counter(
                row['fire_offset'] for row in result['target_rows']
                if row['score'] == score_name and row['task'] == task and row['status'] == 'TP'
            )
            cells = ' | '.join(str(counts[offset]) for offset in range(-6, 1))
            lines.append(f"| {score_title[score_name]} | {task} | {cells} |")
    lines += [
        '',
        '图 `fig_hit_offsets.png` 是这张偏移计数。命中日本身的锁定会覆盖到拐点当天或更后，锁定结束后的第一个交易日不能在同一天既重新武装又发报，所以命中之后的 +1 不会再发一次。',
        '',
    ]
    outside = [
        row for row in result['target_rows']
        if row['status'] == 'TP' and not row['fire_day_eligible']
    ]
    if outside:
        listed = '；'.join(
            f"{row['task']} {row['pivot_date']} 的发报日 {row['fire_date']}（偏移 {offset_text(row['fire_offset'])}）"
            for row in outside
        )
        lines.append(
            f"有 {len(outside)} 次命中的发报日不在该任务的可评分集合里：{listed}。"
            '四慢变量与 5% 共用分数，可以在 9% 冻结分数尚未有阈值的日期发报。偏移仍在 −6..0，按命中计入；窗口内没有更早的可评分尾部日。其余命中的发报日都在可评分集合里。'
        )
        lines.append('')
    lines += [
        '## 误报是拐点之后才发，还是窗口内的假警报',
        '',
        '只计已评价的误报，不含 PENDING。同一幅度、同一方向的全部收盘拐点都用来判断时点，包括成熟队列之外的拐点；这些标签不进入特征。恰好 +1 表示最后输入就是某个同向拐点的收盘。+2..+6 表示最后输入已经晚于该拐点收盘。两类都算太晚。其余误报在警报前六个交易日里没有同向拐点，记为不是事后补发的假警报。',
        '',
        '| 分数 | 任务 | 误报 | 最后输入就是拐点收盘 | 最后输入已经晚于拐点收盘 | 不是事后补发的假警报 | 精确率 | 覆盖率 |',
        '|---|---|---:|---:|---:|---:|---:|---:|',
    ]
    for row in result['summaries']:
        lines.append(
            f"| {score_title[row['score']]} | {row['task']} | {row['FP']} | {row['fp_too_late_plus1']} | "
            f"{row['fp_too_late_later']} | {row['fp_in_window_false_alarm']} | "
            f"{fmt_pct(row['precision'])} | {fmt_pct(row['recall'])} |"
        )
    lines += [
        '',
        '精确率和覆盖率与冻结账本相同，没有重新搜索。图 `fig_fp_timing.png` 是这三段误报计数。',
        '',
        '## 没有做的事',
        '',
        '- 没有实现 `emit_on_suppressed_hittable_tail`，也没有搜索第二种发报规则。',
        '- 没有重训六个价格特征，没有把 3 日收益或 3 日收益变化加回分数。',
        '- 没有打开 P2，没有提高分位，没有用未来目标数做警报配额。',
        '- 没有更换标签或指数，没有把 D 日收盘写进当日特征。',
        '- 没有修改生产页面、采集器、正式信号，也没有恢复旧 V 系列。',
        '- 不声称双80，不声称 PIT，不声称这是盲测。',
        '',
        '## 复算',
        '',
        '```text',
        'python -B dual80-research/p1d_fire_timing/diagnose.py',
        '```',
        '',
        '缺少 `plan.json` 时测量会停止。`--write-plan-only` 只在文件不存在时写出计划，不读特征数值，也不读警报行。',
        '',
    ]
    return '\n'.join(lines)


def save_figures(result: dict) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    score_title = {'frozen_six': 'frozen six-feature', 'slow_four': 'slow four-feature'}
    colors = {
        'delay_to_plus1': '#d95f0e',
        'in_window_too_weak': '#756bb1',
        'other': '#bdbdbd',
    }
    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.2), sharey=True)
    x = np.arange(len(TASKS))
    width = 0.24
    for ax, score_name in zip(axes, SCORES):
        rows = {row['task']: row for row in result['summaries'] if row['score'] == score_name}
        for shift, key, label in (
            (-width, 'delay_to_plus1', 'delay to +1'),
            (0, 'in_window_too_weak', 'in-window too weak'),
            (width, 'other', 'other'),
        ):
            vals = [rows[task][key] for task in TASKS]
            ax.bar(x + shift, vals, width=width, color=colors[key], label=label)
        ax.set_xticks(x, TASKS)
        ax.set_title(score_title[score_name])
        ax.grid(axis='y', alpha=0.25)
    axes[0].set_ylabel('false negatives')
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.02))
    fig.suptitle('Pre-registered miss buckets. A majority is count * 2 > FN, then 3 of 4 tasks.', y=1.12)
    fig.tight_layout()
    fig.savefig(HERE / 'fig_miss_buckets.png', dpi=140, bbox_inches='tight')
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.2), sharey=True)
    offsets = list(range(-6, 1))
    for ax, score_name in zip(axes, SCORES):
        for task in TASKS:
            counts = Counter(
                row['fire_offset'] for row in result['target_rows']
                if row['score'] == score_name and row['task'] == task and row['status'] == 'TP'
            )
            ax.plot(offsets, [counts[offset] for offset in offsets], marker='o', ms=4, label=task)
        ax.axvspan(-6, 0, color='#c7e9c0', zorder=0)
        ax.set_xticks(offsets)
        ax.set_xlabel('fire offset')
        ax.set_title(score_title[score_name])
        ax.grid(alpha=0.25)
    axes[0].set_ylabel('true hits')
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.02))
    fig.suptitle('Hit fire offset. Green band is the hittable window. Offset +1 cannot be a hit.', y=1.12)
    fig.tight_layout()
    fig.savefig(HERE / 'fig_hit_offsets.png', dpi=140, bbox_inches='tight')
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.2), sharey=True)
    fp_colors = ('#d95f0e', '#fe9929', '#9ecae1')
    fp_keys = (
        ('fp_too_late_plus1', 'last input is pivot close'),
        ('fp_too_late_later', 'last input after pivot close'),
        ('fp_in_window_false_alarm', 'not a post-pivot fire'),
    )
    for ax, score_name in zip(axes, SCORES):
        rows = {row['task']: row for row in result['summaries'] if row['score'] == score_name}
        for shift, (key, label), color in zip((-width, 0, width), fp_keys, fp_colors):
            vals = [rows[task][key] for task in TASKS]
            ax.bar(x + shift, vals, width=width, color=color, label=label)
        ax.set_xticks(x, TASKS)
        ax.set_title(score_title[score_name])
        ax.grid(axis='y', alpha=0.25)
    axes[0].set_ylabel('false positives')
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.02))
    fig.suptitle('False-positive timing. Pending alerts are excluded.', y=1.12)
    fig.tight_layout()
    fig.savefig(HERE / 'fig_fp_timing.png', dpi=140, bbox_inches='tight')
    plt.close(fig)


def write_artifact_manifest() -> None:
    files = sorted(path for path in HERE.iterdir() if path.is_file() and path.name != 'artifact_manifest.json')
    manifest = {path.name: {'bytes': path.stat().st_size, 'sha256': sha256_file(path)} for path in files}
    (HERE / 'artifact_manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
    )


def write_outputs(result: dict, plan_sha: str) -> None:
    english, chinese = decision_paragraphs(result)
    decision = {
        'decision': result['decision'],
        'formal_signal_allowed': False,
        'blind_test': False,
        'PIT_certified': False,
        'production_changed': False,
        'refit_six_feature_model': False,
        'p2_opened': False,
        'fast_features_added': False,
        'variant_name': 'emit_on_suppressed_hittable_tail',
        'variant_recommended': result['variant_recommended'],
        'variant_implemented': False,
        'score_class': result['score_class'],
        'floors_ok': result['floors_ok'],
        'english': english,
        'chinese': chinese,
        'p1_decision': 'BLOCKED_NO_CONCENTRATION',
        'p1b_decision': 'GO_PRE_PIVOT_COORDINATE',
        'p1c_decision': 'BLOCKED_NO_WINDOW_PEAK',
    }
    (HERE / 'decision.json').write_text(
        json.dumps(decision, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
    )
    payload = {
        'phase': 'P1d',
        'decision': result['decision'],
        'formal_signal_allowed': False,
        'plan_sha256': plan_sha,
        'score_class': result['score_class'],
        'variant_recommended': result['variant_recommended'],
        'variant_implemented': False,
        'summaries': result['summaries'],
        'pooled': {score: pooled(result['summaries'], score) for score in SCORES},
    }
    (HERE / 'result.json').write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
    )
    (HERE / 'README.md').write_text(render_report(result), encoding='utf-8')
    summary_fields = list(result['summaries'][0])
    write_csv(HERE / 'summary_by_task.csv', result['summaries'], summary_fields)
    write_csv(HERE / 'target_attribution.csv', result['target_rows'], list(result['target_rows'][0]))
    write_csv(HERE / 'fp_attribution.csv', result['fp_rows'], list(result['fp_rows'][0]))
    save_figures(result)
    write_artifact_manifest()


def main() -> None:
    unknown = [arg for arg in sys.argv[1:] if arg != '--write-plan-only']
    if unknown:
        raise SystemExit('unknown arguments: ' + ' '.join(unknown))
    self_test()
    if '--write-plan-only' in sys.argv:
        write_plan_only()
        return
    plan = assert_plan_frozen()
    result = measure(plan)
    write_outputs(result, sha256_file(HERE / 'plan.json'))
    print(json.dumps({
        'decision': result['decision'],
        'score_class': result['score_class'],
        'variant_recommended': result['variant_recommended'],
        'variant_implemented': False,
        'formal_signal_allowed': False,
        'counts': [
            {
                'task': row['task'],
                'score': row['score'],
                'class': row['task_class'],
                'delay': row['delay_to_plus1'],
                'weak': row['in_window_too_weak'],
                'other': row['other'],
                'fn': row['FN'],
                'tp': row['TP'],
            }
            for row in result['summaries']
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
