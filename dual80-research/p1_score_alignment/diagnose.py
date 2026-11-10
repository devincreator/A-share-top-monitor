"""P1 diagnostic: do frozen close x price x past_rank90 scores concentrate in D..D+6?

This script does not fit a model, search a threshold, add a factor, or emit a signal.
Write plan.json first:

    python -B diagnose.py --write-plan-only

Then, without editing plan.json, compute the diagnosis:

    python -B diagnose.py

The measurement path refuses to run if plan.json is missing or differs from the
pre-registered core below. It also refuses to rewrite plan.json.
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
TASKS = ('5_TOP', '5_BOTTOM', '9_TOP', '9_BOTTOM')
REGIONS = ('inside', 'early_shoulder', 'late_shoulder', 'ordinary')
FN_ENTERED = (
    'tail_blocked_by_lock',
    'tail_blocked_by_no_rearm',
    'tail_blocked_by_lock_or_rearm',
    'fired_but_unmatched',
)
FP_PRIORITY = (
    'cohort_boundary_hit',
    'window_goal_already_matched',
    'too_late',
    'too_early',
    'opposite_in_window',
    'trend_continuation',
    'after_turn',
    'oscillation_noise',
    'other',
)
SOURCE_FILES = (
    'ACTIVE_RESEARCH_CONTRACT.json',
    'turning-research-canonical/tables/research_inputs.csv',
    'turning-label-comparison/all_labels.csv',
    'dual80-research/label_clock_v4/scores.csv',
    'dual80-research/label_clock_v4/rank_events.csv',
    'dual80-research/label_clock_v4/rank_metrics.csv',
    'dual80-research/label_clock_v4/rank_thresholds.csv',
    'dual80-research/label_clock_v4/rank_replay.py',
    'dual80-research/label_clock_v4/run.py',
)

CORE = {
    'phase': 'P1',
    'title': 'Score alignment of the frozen close x price x past_rank90 baseline inside D..D+6',
    'contains_measurements': False,
    'hypothesis': (
        'Published close x price scores already separate the seven decision days before a '
        'close pivot from the other scored days (fixed-threshold day-level AUC about 0.70-0.77). '
        'The past_rank90 ledger still produces more alerts than the dual-80 necessary band, with '
        'precision about 15-34% and recall about 39-51%. This run tests whether the causal top '
        'decile is concentrated inside the official hit window, whether false alerts have a '
        'pre-registered timing structure, and whether missed pivots ever enter that same tail. '
        'It does not treat those published rates as a target to optimize.'
    ),
    'freeze': {
        'index': '000985.CSI',
        'label': 'close',
        'features': 'price',
        'fire_rule': 'past_rank90',
        'fire_rule_definition': (
            'Causal quantile: threshold is the linear 0.90 quantile of up to 252 strictly earlier '
            'emitted scores, requiring at least 126 earlier scores. Current score is excluded. '
            'Fire on an armed upward cross; lock through D+6; rearm only on a later score below '
            'that day\'s own historical threshold. Identical to label_clock_v4/rank_replay.py.'
        ),
        'decision_clock': 'pre-open on day D; score last_input must be D-1',
        'hit_window': 'Decision days D = pivot-6 .. pivot inclusive. An alert on D hits a pivot when 0 <= pivot-D <= 6.',
        'matching': 'same scale, same direction, one-to-one, label_clock_v4.run.match',
        'tasks': list(TASKS),
        'intraday_hybrid_used_for_decision': False,
        'new_factors': False,
        'threshold_search': False,
        'alert_quota_from_future_target_counts': False,
        'formal_signal_allowed': False,
        'blind_test': False,
        'PIT_certified': False,
        'production_changed': False,
    },
    'eval_split': {
        'source': 'label_clock_v4 mature cohort, identical to rank_replay.evaluate on the full series',
        'test_start': '2016-01-01',
        'left_boundary': 'pivot index >= first session on or after 2016-01-01, plus 7',
        'frontier_rule': (
            'For each scale, min across close and intraday label variants of the maximum pivot '
            'whose confirmation is at least 140 sessions before the series end. Evaluation only. '
            'The intraday variant is not a scored label in this diagnosis.'
        ),
        'eligible_decision_day': (
            'Session i with i >= test start, i+6 <= frontier, a close/price score, and a causal '
            'threshold. Pending alerts with i+6 > frontier are excluded from precision, recall, '
            'and from the FP taxonomy.'
        ),
        'new_split': False,
        'note': 'Repeatedly inspected history. Diagnostic only. Not a confirmation sample.',
    },
    'region_rules': {
        'inside': 'Eligible day in [pivot-6, pivot] for at least one evaluated same-task target.',
        'early_shoulder': 'Eligible day in [pivot-13, pivot-7] and not inside any evaluated target.',
        'late_shoulder': 'Eligible day in [pivot+1, pivot+6] and not inside and not early-shoulder.',
        'ordinary': 'Eligible day in none of the three sets above.',
        'priority': ['inside', 'early_shoulder', 'late_shoulder', 'ordinary'],
        'shoulder_width_sessions': 7,
        'shoulder_width_reason': 'Equal to the hit window. Not chosen after seeing alignment.',
        'regions_use': 'Evaluated close targets only. Out-of-cohort pivots are counted in the FP cohort bucket, not used to redefine ordinary days.',
    },
    'high_score_tail': {
        'definition': 'score >= that day\'s causal past_rank90 threshold',
        'hindsight_percentile': (
            'Midrank percentile of the score among eligible days of the same task. Descriptive '
            'only. It uses the full eligible sample, including later days, and is not a fire rule.'
        ),
    },
    'fn_rules': {
        'population': 'Evaluated targets not matched to an alert.',
        'candidate_days': 'Eligible decision days inside [pivot-6, pivot].',
        'classes': [
            'no_eligible_day',
            'fired_but_unmatched',
            'tail_blocked_by_lock',
            'tail_blocked_by_no_rearm',
            'tail_blocked_by_lock_or_rearm',
            'never_high',
        ],
        'entered_tail': list(FN_ENTERED),
        'never_high': 'At least one eligible window day, and none of them is in the causal tail.',
        'note': (
            'A tail day inside an active D..D+6 lock, or after a lock while still unarmed, did '
            'enter the tail even though the frozen rule did not emit a new alert.'
        ),
    },
    'fp_rules': {
        'population': 'Evaluated FP alerts only. PENDING excluded. Buckets are retrospective.',
        'inputs': 'Same-scale close pivots of both directions, including pivots outside the mature cohort, plus 000985 closes. Not used as features.',
        'priority': list(FP_PRIORITY),
        'definitions': {
            'cohort_boundary_hit': 'A same-direction pivot lies in [alert, alert+6] and that pivot is not an evaluated goal, and no evaluated goal lies in that span.',
            'window_goal_already_matched': 'An evaluated goal lies in [alert, alert+6] but this alert was not the matched alert. Expected to be rare under a 6-session lock.',
            'too_late': 'A same-direction pivot lies in [alert-6, alert-1].',
            'too_early': 'A same-direction pivot lies in [alert+7, alert+13].',
            'opposite_in_window': 'An opposite-direction pivot lies in [alert, alert+6].',
            'trend_continuation': 'The latest pivot at or before the alert is opposite, and the next same-direction pivot is at least 14 sessions later.',
            'after_turn': 'The latest pivot at or before the alert is same-direction and at least 7 sessions earlier, and the next pivot is opposite.',
            'oscillation_noise': 'None of the above, and (max close - min close) over [alert, alert+6] divided by the previous close is strictly below scale/100.',
            'other': 'Residual, including edges where the surrounding pivot is missing.',
        },
        'economic_fp': 'All FP alerts except cohort_boundary_hit. Structure shares use this subset.',
        'raw_flags': 'The same predicates are also stored without priority, so overlap is visible. Raw flags may sum to more than one.',
    },
    'success_criteria': {
        'sample_floors': {
            'n_inside_min': 30,
            'n_ordinary_min': 100,
            'n_early_shoulder_min': 20,
            'n_late_shoulder_min': 20,
            'n_stride1_ordinary_blocks_min': 30,
            'n_targets_with_eligible_day_min': 10,
        },
        'concentration_all_required': {
            'median_inside_gt_ordinary': True,
            'median_inside_gt_early_shoulder': True,
            'median_inside_gt_late_shoulder': True,
            'auc_inside_vs_ordinary_min': 0.60,
            'tail_gap_inside_minus_ordinary_min': 0.05,
            'tail_ratio_inside_over_ordinary_min': 2.0,
            'tail_ratio_if_ordinary_is_zero_requires_inside_min': 0.10,
            'tail_inside_minus_early_min': 0.02,
            'tail_inside_minus_late_min': 0.02,
            'target_any_tail_minus_stride1_ordinary_block_min': 0.10,
            'mean_score_argmax_offsets': 'Every offset in -13..+6 with n>=10 that ties the maximum mean score, within 1e-12, lies in -6..0.',
            'tail_rate_argmax_offsets': 'Same rule for the causal tail rate.',
        },
        'fn_visibility': {
            'pooled_across_four_tasks': True,
            'denominator': 'FN targets with at least one eligible window day',
            'numerator': 'Those FN targets with at least one eligible causal-tail day',
            'min_share': 0.30,
        },
        'fp_structure_each_task': {
            'inconclusive_if_economic_fp_below': 8,
            'other_share_max': 0.40,
            'top1_share_min': 0.25,
            'top2_share_min': 0.60,
            'rule': 'PASS if other share < 0.40 AND (top1 >= 0.25 OR top2 >= 0.60), shares over economic FP, top buckets excluding other.',
        },
        'decision_order': [
            'BLOCKED_INSUFFICIENT_SAMPLE if any task fails a sample floor',
            'else BLOCKED_NO_CONCENTRATION if any task fails a concentration test',
            'else BLOCKED_FN_INVISIBLE if the pooled FN tail-entry share is below 0.30',
            'else BLOCKED_FP_UNSTRUCTURED if any task fails the FP structure test',
            'else GO_P2',
        ],
        'go_meaning': (
            'A later Phase P2 may pre-register at most three fire-rule variants on these same '
            'close x price scores. P2 is not run here. GO does not mean dual-80 is reachable by '
            'compression, and it does not authorize a new factor, a new label, a new index, or a signal.'
        ),
        'dependence_note': (
            'Days overlap and scores are autocorrelated. These gates are pre-registered descriptive '
            'rules. No p-value is a gate.'
        ),
    },
    'reported_but_not_gates': [
        'nonoverlapping stride-7 ordinary-block tail rate',
        'hindsight top-decile (midrank percentile >= 90) enrichment',
        'median excess of TP alert days versus FP alert days',
        'share of never-high FN whose best hindsight percentile is below 80, and the share in [80, 90)',
        'eligible inside days that also fall in another target early shoulder',
        'same-direction evaluated targets separated by 6 sessions or fewer',
        'causal tail on an ineligible right-boundary window day',
        'dual-80 necessary alert band ceil(0.8T)..floor(T/0.8), as context only',
        'cohort_boundary_hit share, with a prose note if it is at least 0.30',
    ],
    'out_of_scope': [
        'No threshold search and no new fire rule.',
        'No new factor and no D-day feature.',
        'No label change and no index change.',
        'No intraday hybrid promotion.',
        'No production page, collector, official signal, or V-series workflow.',
        'formal_signal_allowed stays false.',
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
    core_on_disk = {k: v for k, v in on_disk.items() if k != 'source_sha256'}
    if core_on_disk != CORE:
        raise SystemExit('plan.json core does not match the pre-registered CORE in diagnose.py')
    if on_disk.get('contains_measurements') is not False:
        raise SystemExit('plan.json must not contain measurements')
    current = source_hashes()
    if on_disk.get('source_sha256') != current:
        raise SystemExit('source files changed after plan.json was written: ' + json.dumps({
            'plan': on_disk.get('source_sha256'), 'current': current,
        }, ensure_ascii=False))
    return on_disk


def write_plan_only() -> None:
    path = HERE / 'plan.json'
    if path.exists():
        raise SystemExit('plan.json already exists and is not rewritten')
    path.write_text(json.dumps(build_plan(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'wrote': str(path), 'contains_measurements': False}, ensure_ascii=False))


def mean(xs) -> float | None:
    return sum(xs) / len(xs) if xs else None


def median(xs) -> float | None:
    if not xs:
        return None
    ys = sorted(xs)
    n = len(ys)
    mid = n // 2
    if n % 2:
        return float(ys[mid])
    return float(0.5 * (ys[mid - 1] + ys[mid]))


def auc(pairs: list[tuple[float, int]]) -> float | None:
    """Tie-aware Mann-Whitney AUC, same estimator as label_clock_v4/diagnose.py."""
    v = sorted(pairs)
    n1 = sum(y for _, y in v)
    n0 = len(v) - n1
    if not n1 or not n0:
        return None
    total = 0.0
    i = 0
    while i < len(v):
        j = i + 1
        while j < len(v) and v[j][0] == v[i][0]:
            j += 1
        total += sum(y for _, y in v[i:j]) * (i + 1 + j) / 2
        i = j
    return (total - n1 * (n1 + 1) / 2) / (n1 * n0)


def midrank_percentile(values: list[float]) -> list[float]:
    n = len(values)
    order = sorted(range(n), key=lambda i: values[i])
    out = [0.0] * n
    i = 0
    while i < n:
        j = i + 1
        while j < n and values[order[j]] == values[order[i]]:
            j += 1
        p = 100.0 * (i + 0.5 * (j - i)) / n
        for k in range(i, j):
            out[order[k]] = p
        i = j
    return out


def quantile_list(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {k: None for k in ('p10', 'p25', 'p75', 'p90', 'p95')}
    q = np.quantile(np.asarray(values, float), [0.10, 0.25, 0.75, 0.90, 0.95], method='linear')
    return {'p10': float(q[0]), 'p25': float(q[1]), 'p75': float(q[2]), 'p90': float(q[3]), 'p95': float(q[4])}


def contiguous_runs(indices) -> list[list[int]]:
    runs: list[list[int]] = []
    cur: list[int] = []
    for i in sorted(indices):
        if cur and i != cur[-1] + 1:
            runs.append(cur)
            cur = [i]
        else:
            cur.append(i)
    if cur:
        runs.append(cur)
    return runs


def blocks_of_seven(runs: list[list[int]], stride: int) -> list[list[int]]:
    out: list[list[int]] = []
    for run in runs:
        if stride == 1:
            out.extend(run[k:k + 7] for k in range(0, len(run) - 6))
        else:
            k = 0
            while k + 7 <= len(run):
                out.append(run[k:k + 7])
                k += stride
    return out


def classify_fp(a: int, scale: int, side: str, same: list[int], opp: list[int],
                ordered: list[tuple[int, str]], goal_set: set[int], closes) -> tuple[str, dict]:
    """Retrospective exclusive bucket. Priority matches plan.json fp_rules.priority."""
    same_in = [p for p in same if 0 <= p - a <= 6]
    goals_in = [p for p in same_in if p in goal_set]
    raw = {
        'cohort_boundary_hit': bool(same_in) and not goals_in,
        'window_goal_already_matched': bool(goals_in),
        'too_late': any(1 <= a - p <= 6 for p in same),
        'too_early': any(7 <= p - a <= 13 for p in same),
        'opposite_in_window': any(0 <= q - a <= 6 for q in opp),
    }
    last = None
    for idx, direction in ordered:
        if idx <= a:
            last = (idx, direction)
        else:
            break
    next_same = next((p for p in same if p > a), None)
    next_any = next(((idx, direction) for idx, direction in ordered if idx > a), None)
    raw['trend_continuation'] = bool(
        last is not None and last[1] != side and next_same is not None and next_same - a >= 14
    )
    raw['after_turn'] = bool(
        last is not None and last[1] == side and a - last[0] >= 7 and next_any is not None and next_any[1] != side
    )
    if a - 1 >= 0 and a + 6 < len(closes) and closes[a - 1] > 0:
        span = max(closes[a:a + 7]) - min(closes[a:a + 7])
        raw['oscillation_noise'] = (span / closes[a - 1]) < (scale / 100.0)
    else:
        raw['oscillation_noise'] = False
    for name in FP_PRIORITY:
        if name == 'other':
            return 'other', raw
        if raw[name]:
            return name, raw
    return 'other', raw


def self_test_classifier() -> None:
    closes = [100.0] * 80
    # Too early: future same-direction pivot 10 sessions ahead.
    bucket, raw = classify_fp(10, 5, 'TOP', [20], [], [(20, 'TOP')], set(), closes)
    assert bucket == 'too_early' and raw['too_early']
    # Too late: same-direction pivot 3 sessions behind.
    bucket, _ = classify_fp(10, 5, 'TOP', [7], [], [(7, 'TOP')], set(), closes)
    assert bucket == 'too_late'
    # Cohort boundary beats a nearby timing label.
    bucket, _ = classify_fp(10, 5, 'TOP', [13], [], [(13, 'TOP')], set(), closes)
    assert bucket == 'cohort_boundary_hit'
    # Evaluated goal inside the alert window.
    bucket, raw = classify_fp(10, 5, 'TOP', [8, 12], [], [(8, 'TOP'), (12, 'TOP')], {12}, closes)
    assert bucket == 'window_goal_already_matched' and raw['too_late']
    # Opposite pivot inside the horizon beats trend continuation.
    ordered = [(0, 'BOTTOM'), (12, 'BOTTOM'), (40, 'TOP')]
    bucket, raw = classify_fp(10, 5, 'TOP', [40], [0, 12], ordered, set(), closes)
    assert bucket == 'opposite_in_window' and raw['trend_continuation']
    # Still approaching a far same-direction pivot.
    ordered = [(0, 'BOTTOM'), (40, 'TOP')]
    bucket, _ = classify_fp(10, 5, 'TOP', [40], [0], ordered, set(), closes)
    assert bucket == 'trend_continuation'
    # Turn already happened; the next pivot is opposite and outside the horizon.
    ordered = [(0, 'TOP'), (30, 'BOTTOM')]
    bucket, _ = classify_fp(15, 5, 'TOP', [0], [30], ordered, set(), closes)
    assert bucket == 'after_turn'
    # No pivots and a flat path.
    bucket, _ = classify_fp(10, 5, 'TOP', [], [], [], set(), closes)
    assert bucket == 'oscillation_noise'
    # No pivots and a range larger than the scale.
    wild = [100.0] * 80
    for i in range(10, 17):
        wild[i] = 100.0 + (i - 10) * 3
    bucket, _ = classify_fp(10, 5, 'TOP', [], [], [], set(), wild)
    assert bucket == 'other'
    # Integer dual-80 band used only as context.
    assert (4 * 38 + 4) // 5 == 31 and (5 * 38) // 4 == 47
    assert (4 * 19 + 4) // 5 == 16 and (5 * 19) // 4 == 23


def plain(value):
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, np.integer):
        value = int(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    raise TypeError(type(value))


def cell(value):
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (list, tuple)):
        return ','.join(str(v) for v in value)
    if isinstance(value, float):
        return f'{value:.10g}'
    if isinstance(value, np.floating):
        return f'{float(value):.10g}'
    return value


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow({k: cell(row.get(k)) for k in fields})


def check(name: str, group: str, passed: bool, actual, expect: str) -> dict:
    return {
        'name': name,
        'group': group,
        'passed': bool(passed),
        'actual': plain(actual),
        'expect': expect,
    }


def load_rows(path: Path) -> list[dict]:
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def replay_and_measure(plan: dict) -> dict:
    sys.path.insert(0, str(CLOCK))
    import run as base

    if (base.D[0], base.D[-1], base.N) != ('2011-08-02', '2026-08-25', 3659):
        raise SystemExit('research calendar does not match the canonical 3659-session table')
    closes = base.C
    front = {}
    for scale in (5, 9):
        front[scale] = min(
            max(g[0] for g in base.LABELS[variant][scale] if g[1] + 140 < base.N)
            for variant in base.LABELS
        )
    published = [
        r for r in load_rows(CLOCK / 'rank_metrics.csv')
        if r['label'] == 'close' and r['group'] == 'price__past_rank90'
    ]
    published_by_task = {r['task']: r for r in published}
    events = [
        r for r in load_rows(CLOCK / 'rank_events.csv')
        if r['label'] == 'close' and r['group'] == 'price__past_rank90'
    ]
    thresholds = [
        r for r in load_rows(CLOCK / 'rank_thresholds.csv')
        if r['label'] == 'close' and r['group'] == 'price'
    ]
    scores = [
        r for r in load_rows(CLOCK / 'scores.csv')
        if r['label'] == 'close' and r['group'] == 'price'
    ]
    integrity = []
    per_task = []
    eligible_rows = []
    target_rows = []
    alert_rows = []
    region_rows = []
    lead_rows = []
    fn_rows = []
    fp_rows = []
    flag_rows = []
    test_rows = []

    for task in TASKS:
        scale_s, side = task.split('_')
        scale = int(scale_s)
        task_scores = sorted((r for r in scores if r['task'] == task), key=lambda r: r['date'])
        if len(task_scores) != len({r['date'] for r in task_scores}):
            raise SystemExit(f'duplicate scores for {task}')
        hist = []
        state = {'until': -1, 'armed': True}
        ledger = []
        days = {}
        recomputed_thresholds = {}
        gaps = 0
        previous_i = None
        for row in task_scores:
            i = base.pos[row['date']]
            if base.pos[row['last_input']] != i - 1:
                raise SystemExit(f'last_input is not D-1 on {task} {row["date"]}')
            if previous_i is not None and i != previous_i + 1:
                gaps += i - previous_i - 1
            previous_i = i
            value = float(row['score'])
            past = [p for j, p in hist if i - 252 <= j < i]
            threshold = None
            fired = False
            locked = i <= state['until']
            armed_before = state['armed']
            if len(past) >= 126:
                threshold = float(np.quantile(np.asarray(past, float), 0.90, method='linear'))
                recomputed_thresholds[row['date']] = (threshold, len(past), base.D[hist[-1][0]])
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
                    raise SystemExit(f'unclassified tail day {task} {row["date"]}')
            causal_ecdf = (sum(p <= value for p in past) / len(past)) if past else None
            days[i] = {
                'i': i,
                'date': row['date'],
                'score': value,
                'threshold': threshold,
                'excess': None if threshold is None else value - threshold,
                'in_tail': threshold is not None and value >= threshold,
                'fired': fired,
                'locked': locked,
                'armed_before': armed_before,
                'block': block,
                'causal_ecdf': causal_ecdf,
            }
            hist.append((i, value))
            hist = [(j, p) for j, p in hist if j >= i - 252]

        file_thresholds = {r['date']: r for r in thresholds if r['task'] == task}
        if set(file_thresholds) != set(recomputed_thresholds):
            raise SystemExit(f'threshold dates do not match rank_thresholds.csv for {task}')
        max_diff = 0.0
        for date, (threshold, n_past, last_input) in recomputed_thresholds.items():
            src = file_thresholds[date]
            max_diff = max(max_diff, abs(float(src['threshold']) - threshold))
            if int(src['prior_scores']) != n_past or src['last_threshold_input'] != last_input:
                raise SystemExit(f'threshold inputs do not match on {task} {date}')
        if max_diff > 1e-8:
            raise SystemExit(f'threshold values differ by {max_diff} on {task}')

        labels = base.LABELS['close'][scale]
        met, pairs, aa = base.evaluate(ledger, labels, side, front[scale], base.N)
        published_row = published_by_task[task]
        if base.D[front[scale]] != published_row['frontier']:
            raise SystemExit(f'frontier mismatch on {task}')
        for key in ('TP', 'FP', 'FN', 'alerts', 'targets', 'pending', 'same_day_hits', 'right_boundary_targets_last6'):
            if int(met[key]) != int(published_row[key]):
                raise SystemExit(f'{task} {key} recomputed {met[key]} != artifact {published_row[key]}')
        if abs(float(met['precision']) - float(published_row['precision'])) > 1e-12:
            raise SystemExit(f'{task} precision mismatch')
        if abs(float(met['recall']) - float(published_row['recall'])) > 1e-12:
            raise SystemExit(f'{task} recall mismatch')
        matched = dict(pairs)
        aa_set = set(aa)
        rebuilt = []
        for a in ledger:
            if a < base.START:
                continue
            if a in matched:
                status, pivot_date = 'TP', base.D[matched[a]]
            elif a in aa_set:
                status, pivot_date = 'FP', ''
            else:
                status, pivot_date = 'PENDING', ''
            rebuilt.append({'date': base.D[a], 'status': status, 'pivot_date': pivot_date})
        artifact_events = [
            {'date': r['date'], 'status': r['status'], 'pivot_date': r['pivot_date']}
            for r in events if r['task'] == task
        ]
        if rebuilt != artifact_events:
            raise SystemExit(f'rank_events.csv does not match the rebuilt ledger for {task}')
        integrity.append({
            'task': task,
            'thresholds': len(recomputed_thresholds),
            'max_abs_threshold_diff': max_diff,
            'alerts_including_pending': len(rebuilt),
            'score_gaps': gaps,
            'ledger_matches_rank_events': True,
            'metrics_match_rank_metrics': True,
        })

        goals = [g for g in labels if g[2] == side and base.START + 7 <= g[0] <= front[scale] and g[1] + 140 < base.N]
        if len(goals) != met['targets']:
            raise SystemExit(f'goal list length mismatch on {task}')
        goal_set = {g[0] for g in goals}
        eligible_idx = [
            i for i, day in days.items()
            if day['threshold'] is not None and i >= base.START and i + 6 <= front[scale]
        ]
        eligible_set = set(eligible_idx)
        inside, early, late = set(), set(), set()
        for pivot, _, _direction in goals:
            inside.update(range(pivot - 6, pivot + 1))
            early.update(range(pivot - 13, pivot - 6))
            late.update(range(pivot + 1, pivot + 7))
        reclassified = len([i for i in eligible_set if i in inside and i in early])

        def region_of(i: int) -> str:
            if i in inside:
                return 'inside'
            if i in early:
                return 'early_shoulder'
            if i in late:
                return 'late_shoulder'
            return 'ordinary'

        eligible_days = []
        for i in sorted(eligible_idx):
            day = dict(days[i])
            day['region'] = region_of(i)
            day['eligible'] = True
            eligible_days.append(day)
            days[i] = day
        pcts = midrank_percentile([d['score'] for d in eligible_days])
        for day, pct in zip(eligible_days, pcts):
            day['hindsight_percentile'] = pct
        by_region = {name: [d for d in eligible_days if d['region'] == name] for name in REGIONS}
        if sum(len(v) for v in by_region.values()) != len(eligible_days):
            raise SystemExit(f'regions do not partition eligible days on {task}')

        region_stats = {}
        for name, group in by_region.items():
            score_vals = [d['score'] for d in group]
            tail_vals = [1.0 if d['in_tail'] else 0.0 for d in group]
            stat = {
                'task': task,
                'region': name,
                'n_days': len(group),
                'share_of_eligible': len(group) / len(eligible_days) if eligible_days else None,
                'score_mean': mean(score_vals),
                'score_median': median(score_vals),
                **quantile_list(score_vals),
                'mean_hindsight_percentile': mean([d['hindsight_percentile'] for d in group]),
                'median_hindsight_percentile': median([d['hindsight_percentile'] for d in group]),
                'tail_rate': mean(tail_vals),
                'mean_excess': mean([d['excess'] for d in group]),
                'median_excess': median([d['excess'] for d in group]),
                'n_tail': int(sum(tail_vals)),
                'hindsight_top_decile_rate': mean([1.0 if d['hindsight_percentile'] >= 90 else 0.0 for d in group]),
            }
            region_stats[name] = stat
            region_rows.append(stat)

        lead = []
        for offset in range(-13, 7):
            chosen = []
            for pivot, _, _direction in goals:
                i = pivot + offset
                if i in eligible_set:
                    chosen.append(days[i])
            lead.append({
                'task': task,
                'offset': offset,
                'n': len(chosen),
                'mean_score': mean([d['score'] for d in chosen]),
                'tail_rate': mean([1.0 if d['in_tail'] else 0.0 for d in chosen]),
                'mean_excess': mean([d['excess'] for d in chosen]),
            })
        lead_rows.extend(lead)
        score_peak_ok, score_peak_value, score_peak_at = peak_inside(lead, 'mean_score')
        tail_peak_ok, tail_peak_value, tail_peak_at = peak_inside(lead, 'tail_rate')

        ordinary_idx = [d['i'] for d in by_region['ordinary']]
        runs = contiguous_runs(ordinary_idx)
        stride1 = blocks_of_seven(runs, 1)
        stride7 = blocks_of_seven(runs, 7)

        def block_hit_rate(blocks):
            if not blocks:
                return None, 0, 0
            hits = sum(any(days[i]['in_tail'] for i in block) for block in blocks)
            return hits / len(blocks), hits, len(blocks)

        block_rate, block_hits, block_n = block_hit_rate(stride1)
        block7_rate, block7_hits, block7_n = block_hit_rate(stride7)
        cover = Counter()
        for pivot, _, _direction in goals:
            for i in range(pivot - 6, pivot + 1):
                if i in eligible_set:
                    cover[i] += 1
        matched_pivot = {p: a for a, p in pairs}
        targets_with_day = 0
        targets_with_tail = 0
        for pivot, confirm, _direction in goals:
            window = [i for i in range(pivot - 6, pivot + 1) if i in eligible_set]
            ineligible_tail = any(
                days[i]['in_tail'] for i in range(pivot - 6, pivot + 1)
                if i in days and days[i]['threshold'] is not None and i not in eligible_set
            )
            ever_tail = any(days[i]['in_tail'] for i in window) if window else False
            if window:
                targets_with_day += 1
                targets_with_tail += int(ever_tail)
            if pivot in matched_pivot:
                status = 'TP'
                alert_i = matched_pivot[pivot]
                fn_class = ''
                fn_detail = ''
            else:
                status = 'FN'
                alert_i = None
                fn_class, fn_detail = classify_fn(pivot, window, days, matched, aa_set)
            best = max(window, key=lambda i: days[i]['score']) if window else None
            target_rows.append({
                'task': task,
                'pivot_date': base.D[pivot],
                'confirmation_date': base.D[confirm],
                'status': status,
                'matched_alert_date': '' if alert_i is None else base.D[alert_i],
                'lead_sessions': '' if alert_i is None else pivot - alert_i,
                'n_eligible_days': len(window),
                'n_tail_days': sum(days[i]['in_tail'] for i in window),
                'max_score': None if best is None else days[best]['score'],
                'max_excess': None if best is None else days[best]['excess'],
                'max_hindsight_percentile': None if best is None else days[best]['hindsight_percentile'],
                'max_causal_ecdf': None if best is None else max(days[i]['causal_ecdf'] for i in window),
                'argmax_offset': None if best is None else best - pivot,
                'ever_tail': ever_tail,
                'fn_class': fn_class,
                'fn_detail': fn_detail,
                'right_boundary_last6': pivot > front[scale] - 6,
                'tail_on_ineligible_window_day': ineligible_tail,
            })
        target_rate = (targets_with_tail / targets_with_day) if targets_with_day else None

        same = sorted(g[0] for g in labels if g[2] == side)
        opp = sorted(g[0] for g in labels if g[2] != side)
        ordered = sorted(((g[0], g[2]) for g in labels), key=lambda g: g[0])
        alternates = all(ordered[k][1] != ordered[k + 1][1] for k in range(len(ordered) - 1))
        alert_excess = {'TP': [], 'FP': []}
        bucket_counts = Counter()
        raw_counts = Counter()
        fp_n = 0
        for a in ledger:
            if a < base.START:
                continue
            if a in matched:
                status, pivot_date, lead_sessions = 'TP', base.D[matched[a]], matched[a] - a
                bucket, raw = '', {}
            elif a in aa_set:
                status, pivot_date, lead_sessions = 'FP', '', ''
                bucket, raw = classify_fp(a, scale, side, same, opp, ordered, goal_set, closes)
                bucket_counts[bucket] += 1
                for name, flag in raw.items():
                    if flag:
                        raw_counts[name] += 1
                fp_n += 1
            else:
                status, pivot_date, lead_sessions = 'PENDING', '', ''
                bucket, raw = '', {}
            day = days[a]
            if status in alert_excess and day['excess'] is not None:
                alert_excess[status].append(day['excess'])
            alert_rows.append({
                'task': task,
                'date': base.D[a],
                'status': status,
                'pivot_date': pivot_date,
                'lead_sessions': lead_sessions,
                'score': day['score'],
                'threshold': day['threshold'],
                'excess': day['excess'],
                'hindsight_percentile': day.get('hindsight_percentile'),
                'exclusive_bucket': bucket,
                'prev_same_sessions': distance_before(a, same),
                'next_same_sessions': distance_after(a, same),
                'next_opposite_sessions': distance_after(a, opp),
                'forward_7d_return': forward_return(closes, a, 6),
                'forward_20d_return': forward_return(closes, a, 20),
                'forward_20d_against_reversal': against_reversal(forward_return(closes, a, 20), side),
                **{f'raw_{k}': raw.get(k, '') for k in FP_PRIORITY if k != 'other'},
            })
        economic = fp_n - bucket_counts['cohort_boundary_hit']
        structure = fp_structure(bucket_counts, economic)
        for name in FP_PRIORITY:
            if name == 'other':
                continue
            flag_rows.append({
                'task': task,
                'flag': name,
                'n_raw': raw_counts[name],
                'share_of_fp': raw_counts[name] / fp_n if fp_n else None,
                'n_exclusive': bucket_counts[name],
                'share_exclusive_of_fp': bucket_counts[name] / fp_n if fp_n else None,
            })
        flag_rows.append({
            'task': task,
            'flag': 'other',
            'n_raw': '',
            'share_of_fp': '',
            'n_exclusive': bucket_counts['other'],
            'share_exclusive_of_fp': bucket_counts['other'] / fp_n if fp_n else None,
        })
        fp_rows.append({
            'task': task,
            'fp': fp_n,
            'economic_fp': economic,
            'cohort_boundary_hit': bucket_counts['cohort_boundary_hit'],
            'cohort_share_of_fp': bucket_counts['cohort_boundary_hit'] / fp_n if fp_n else None,
            **{name: bucket_counts[name] for name in FP_PRIORITY},
            **structure,
        })

        tp_med = median(alert_excess['TP'])
        fp_med = median(alert_excess['FP'])
        higher_threshold_unsupported = None
        if tp_med is not None and fp_med is not None:
            higher_threshold_unsupported = fp_med >= tp_med
        gaps_between_goals = [
            goals[k + 1][0] - goals[k][0] for k in range(len(goals) - 1)
        ]
        inside_scores = [d['score'] for d in by_region['inside']]
        ordinary_scores = [d['score'] for d in by_region['ordinary']]
        auc_value = auc([(s, 1) for s in inside_scores] + [(s, 0) for s in ordinary_scores])
        tail_in = region_stats['inside']['tail_rate']
        tail_ord = region_stats['ordinary']['tail_rate']
        tail_early = region_stats['early_shoulder']['tail_rate']
        tail_late = region_stats['late_shoulder']['tail_rate']
        if tail_ord is None or tail_in is None:
            ratio_ok = False
            ratio = None
        elif tail_ord == 0:
            ratio = None
            ratio_ok = tail_in >= 0.10
        else:
            ratio = tail_in / tail_ord
            ratio_ok = ratio >= 2.0
        sample_checks = [
            check('n_inside', 'sample', region_stats['inside']['n_days'] >= 30, region_stats['inside']['n_days'], '>= 30'),
            check('n_ordinary', 'sample', region_stats['ordinary']['n_days'] >= 100, region_stats['ordinary']['n_days'], '>= 100'),
            check('n_early_shoulder', 'sample', region_stats['early_shoulder']['n_days'] >= 20, region_stats['early_shoulder']['n_days'], '>= 20'),
            check('n_late_shoulder', 'sample', region_stats['late_shoulder']['n_days'] >= 20, region_stats['late_shoulder']['n_days'], '>= 20'),
            check('n_stride1_ordinary_blocks', 'sample', block_n >= 30, block_n, '>= 30'),
            check('n_targets_with_eligible_day', 'sample', targets_with_day >= 10, targets_with_day, '>= 10'),
        ]
        concentration_checks = [
            check('median_inside_gt_ordinary', 'concentration', cmp_gt(region_stats['inside']['score_median'], region_stats['ordinary']['score_median']), region_stats['inside']['score_median'], f"> ordinary median {fmt(region_stats['ordinary']['score_median'], 4)}"),
            check('median_inside_gt_early', 'concentration', cmp_gt(region_stats['inside']['score_median'], region_stats['early_shoulder']['score_median']), region_stats['inside']['score_median'], f"> early median {fmt(region_stats['early_shoulder']['score_median'], 4)}"),
            check('median_inside_gt_late', 'concentration', cmp_gt(region_stats['inside']['score_median'], region_stats['late_shoulder']['score_median']), region_stats['inside']['score_median'], f"> late median {fmt(region_stats['late_shoulder']['score_median'], 4)}"),
            check('auc_inside_vs_ordinary', 'concentration', auc_value is not None and auc_value >= 0.60, auc_value, '>= 0.60'),
            check('tail_gap', 'concentration', tail_in is not None and tail_ord is not None and tail_in - tail_ord >= 0.05, None if tail_in is None or tail_ord is None else tail_in - tail_ord, '>= 0.05'),
            check('tail_ratio', 'concentration', ratio_ok, ratio if ratio is not None else tail_in, '>= 2, or inside >= 0.10 if ordinary tail rate is 0'),
            check('tail_beats_early', 'concentration', tail_in is not None and tail_early is not None and tail_in >= tail_early + 0.02, None if tail_in is None or tail_early is None else tail_in - tail_early, 'inside - early >= 0.02'),
            check('tail_beats_late', 'concentration', tail_in is not None and tail_late is not None and tail_in >= tail_late + 0.02, None if tail_in is None or tail_late is None else tail_in - tail_late, 'inside - late >= 0.02'),
            check('target_vs_ordinary_block', 'concentration', target_rate is not None and block_rate is not None and target_rate - block_rate >= 0.10, None if target_rate is None or block_rate is None else target_rate - block_rate, '>= 0.10'),
            check('mean_score_peak_inside_window', 'concentration', score_peak_ok, score_peak_at, 'all tied argmax offsets in -6..0'),
            check('tail_rate_peak_inside_window', 'concentration', tail_peak_ok, tail_peak_at, 'all tied argmax offsets in -6..0'),
        ]
        sample_pass = all(item['passed'] for item in sample_checks)
        concentration_only = all(item['passed'] for item in concentration_checks)
        hi_in = region_stats['inside']['hindsight_top_decile_rate']
        hi_ord = region_stats['ordinary']['hindsight_top_decile_rate']
        band_lo = (4 * met['targets'] + 4) // 5
        band_hi = (5 * met['targets']) // 4
        task_result = {
            'task': task,
            'scale': scale,
            'side': side,
            'frontier': base.D[front[scale]],
            'metrics': {k: met[k] for k in ('TP', 'FP', 'FN', 'precision', 'recall', 'alerts', 'targets', 'pending', 'same_day_hits', 'right_boundary_targets_last6')},
            'dual80_band': {'low': band_lo, 'high': band_hi, 'alerts_above_band': met['alerts'] > band_hi},
            'n_eligible': len(eligible_days),
            'first_score_date': task_scores[0]['date'],
            'first_threshold_date': min(recomputed_thresholds),
            'score_gaps': gaps,
            'regions': region_stats,
            'reclassified_early_days_counted_inside': reclassified,
            'inside_days_covered_by_two_targets': sum(v > 1 for v in cover.values()),
            'goal_gap_min': min(gaps_between_goals) if gaps_between_goals else None,
            'goal_pairs_gap_le_6': sum(g <= 6 for g in gaps_between_goals),
            'pivots_alternate': alternates,
            'auc_inside_vs_ordinary': auc_value,
            'tail_ratio_inside_over_ordinary': ratio,
            'target_any_tail_rate': target_rate,
            'targets_with_eligible_day': targets_with_day,
            'targets_with_tail': targets_with_tail,
            'ordinary_block_stride1_rate': block_rate,
            'ordinary_block_stride1_hits': block_hits,
            'ordinary_block_stride1_n': block_n,
            'ordinary_block_stride7_rate': block7_rate,
            'ordinary_block_stride7_hits': block7_hits,
            'ordinary_block_stride7_n': block7_n,
            'score_peak_offsets': score_peak_at,
            'score_peak_value': score_peak_value,
            'tail_peak_offsets': tail_peak_at,
            'tail_peak_value': tail_peak_value,
            'hindsight_top_decile_ratio': None if not hi_ord else hi_in / hi_ord,
            'tp_median_excess': tp_med,
            'fp_median_excess': fp_med,
            'higher_threshold_unsupported': higher_threshold_unsupported,
            'fp': fp_rows[-1],
            'sample_pass': sample_pass,
            'concentration_only_pass': concentration_only,
            'concentration_pass': sample_pass and concentration_only,
            'fp_structure_pass': structure['structure_pass'],
            'checks': sample_checks + concentration_checks,
            'lead': lead,
            'eligible_days': eligible_days,
            'stride7_max_excess': [max(days[i]['excess'] for i in block) for block in stride7],
        }
        per_task.append(task_result)
        for item in task_result['checks']:
            test_rows.append({'task': task, **item})
        for day in eligible_days:
            eligible_rows.append({
                'task': task,
                'date': day['date'],
                'index': day['i'],
                'region': day['region'],
                'score': day['score'],
                'threshold': day['threshold'],
                'excess': day['excess'],
                'in_tail': day['in_tail'],
                'hindsight_percentile': day['hindsight_percentile'],
                'causal_ecdf': day['causal_ecdf'],
                'fired': day['fired'],
                'block_reason': day['block'],
            })

    fn_targets = [r for r in target_rows if r['status'] == 'FN']
    fn_den = [r for r in fn_targets if r['n_eligible_days'] > 0]
    fn_num = [r for r in fn_den if r['fn_class'] in FN_ENTERED]
    never = [r for r in fn_den if r['fn_class'] == 'never_high']
    fn_share = len(fn_num) / len(fn_den) if fn_den else None
    fn_summary = {
        'fn_targets': len(fn_targets),
        'denominator_with_eligible_day': len(fn_den),
        'entered_tail': len(fn_num),
        'entered_share': fn_share,
        'min_share': 0.30,
        'pass': bool(fn_den) and fn_share >= 0.30,
        'no_eligible_day': sum(r['fn_class'] == 'no_eligible_day' for r in fn_targets),
        'class_counts': dict(Counter(r['fn_class'] for r in fn_targets)),
        'never_high': len(never),
        'never_high_median_max_hindsight_percentile': median([r['max_hindsight_percentile'] for r in never]),
        'never_high_share_hindsight_below_80': mean([1.0 if r['max_hindsight_percentile'] < 80 else 0.0 for r in never]),
        'never_high_share_hindsight_80_to_90': mean([
            1.0 if r['max_hindsight_percentile'] is not None and 80 <= r['max_hindsight_percentile'] < 90 else 0.0
            for r in never
        ]),
        'never_high_median_max_excess': median([r['max_excess'] for r in never]),
        'by_task': [],
    }
    for task in TASKS:
        subset = [r for r in fn_targets if r['task'] == task]
        den = [r for r in subset if r['n_eligible_days'] > 0]
        entered = [r for r in den if r['fn_class'] in FN_ENTERED]
        never_task = [r for r in den if r['fn_class'] == 'never_high']
        fn_summary['by_task'].append({
            'task': task,
            'fn': len(subset),
            'denominator': len(den),
            'entered_tail': len(entered),
            'entered_share': len(entered) / len(den) if den else None,
            'never_high': len(never_task),
            'never_high_median_max_hindsight_percentile': median([r['max_hindsight_percentile'] for r in never_task]),
            'never_high_median_max_excess': median([r['max_excess'] for r in never_task]),
            'class_counts': dict(Counter(r['fn_class'] for r in subset)),
            'ineligible_tail_on_fn': sum(r['tail_on_ineligible_window_day'] for r in subset),
        })
        fn_rows.append(fn_summary['by_task'][-1])
    test_rows.append(check(
        'pooled_fn_entered_tail_share', 'fn_visibility', fn_summary['pass'], fn_share, '>= 0.30 of FN with an eligible day',
    ) | {'task': 'ALL'})

    if any(not task['sample_pass'] for task in per_task):
        code = 'BLOCKED_INSUFFICIENT_SAMPLE'
    elif any(not task['concentration_only_pass'] for task in per_task):
        code = 'BLOCKED_NO_CONCENTRATION'
    elif not fn_summary['pass']:
        code = 'BLOCKED_FN_INVISIBLE'
    elif any(not task['fp_structure_pass'] for task in per_task):
        code = 'BLOCKED_FP_UNSTRUCTURED'
    else:
        code = 'GO_P2'

    return {
        'integrity': integrity,
        'tasks': [{k: v for k, v in task.items() if k not in ('eligible_days', 'lead', 'stride7_max_excess')} for task in per_task],
        'tasks_full': per_task,
        'fn': fn_summary,
        'decision': code,
        'eligible_rows': eligible_rows,
        'target_rows': target_rows,
        'alert_rows': alert_rows,
        'region_rows': region_rows,
        'lead_rows': lead_rows,
        'fn_rows': fn_rows,
        'fp_rows': fp_rows,
        'flag_rows': flag_rows,
        'test_rows': test_rows,
        'plan': plan,
    }


def peak_inside(rows: list[dict], key: str) -> tuple[bool, float | None, list[int]]:
    usable = [r for r in rows if r['n'] >= 10 and r[key] is not None]
    if not usable:
        return False, None, []
    best = max(r[key] for r in usable)
    winners = [int(r['offset']) for r in usable if abs(r[key] - best) <= 1e-12]
    return all(-6 <= offset <= 0 for offset in winners), float(best), winners


def classify_fn(pivot: int, window: list[int], days: dict, matched: dict, aa_set: set[int]) -> tuple[str, str]:
    if not window:
        return 'no_eligible_day', ''
    fired = [i for i in window if days[i]['fired']]
    if fired:
        details = []
        for i in fired:
            if i in matched and matched[i] != pivot:
                details.append(f'{days[i]["date"]}:consumed_by_earlier_target_index_{matched[i]}')
            elif i in matched:
                details.append(f'{days[i]["date"]}:matched_this_target')
            elif i in aa_set:
                details.append(f'{days[i]["date"]}:counted_fp')
            else:
                details.append(f'{days[i]["date"]}:pending_or_outside_evaluated_alerts')
        return 'fired_but_unmatched', ';'.join(details)
    tail = [i for i in window if days[i]['in_tail']]
    if not tail:
        return 'never_high', ''
    reasons = {days[i]['block'] for i in tail}
    if reasons == {'locked'}:
        return 'tail_blocked_by_lock', ''
    if reasons == {'not_rearmed'}:
        return 'tail_blocked_by_no_rearm', ''
    if reasons <= {'locked', 'not_rearmed'} and reasons:
        return 'tail_blocked_by_lock_or_rearm', ','.join(sorted(reasons))
    raise SystemExit(f'unexpected FN tail reasons {reasons} at pivot index {pivot}')


def distance_before(i: int, pivots: list[int]) -> int | None:
    prev = [p for p in pivots if p < i]
    return None if not prev else i - prev[-1]


def distance_after(i: int, pivots: list[int]) -> int | None:
    nxt = [p for p in pivots if p > i]
    return None if not nxt else nxt[0] - i


def forward_return(closes, a: int, k: int) -> float | None:
    j = a + k
    if a - 1 < 0 or j >= len(closes) or closes[a - 1] <= 0:
        return None
    return float(closes[j] / closes[a - 1] - 1.0)


def against_reversal(ret: float | None, side: str) -> float | None:
    if ret is None:
        return None
    return ret if side == 'TOP' else -ret


def fp_structure(counts: Counter, economic: int) -> dict:
    if economic < 8:
        return {
            'structure_status': 'inconclusive',
            'structure_pass': False,
            'other_share_economic': None,
            'top1_bucket': '',
            'top1_share_economic': None,
            'top2_share_economic': None,
        }
    other = counts['other']
    ranked = sorted(
        ((name, counts[name]) for name in FP_PRIORITY if name not in ('other', 'cohort_boundary_hit')),
        key=lambda item: (-item[1], item[0]),
    )
    top1_name, top1_n = ranked[0] if ranked else ('', 0)
    top2_n = sum(n for _, n in ranked[:2])
    other_share = other / economic
    top1_share = top1_n / economic
    top2_share = top2_n / economic
    passed = other_share < 0.40 and (top1_share >= 0.25 or top2_share >= 0.60)
    return {
        'structure_status': 'pass' if passed else 'fail',
        'structure_pass': passed,
        'other_share_economic': other_share,
        'top1_bucket': top1_name,
        'top1_share_economic': top1_share,
        'top2_share_economic': top2_share,
    }


def cmp_gt(left, right) -> bool:
    return left is not None and right is not None and left > right


def fmt(value, digits: int = 3) -> str:
    if value is None or value == '':
        return '—'
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    try:
        return f'{float(value):.{digits}f}'
    except (TypeError, ValueError):
        return str(value)


def pct(value) -> str:
    if value is None or value == '':
        return '—'
    return f'{100 * float(value):.1f}%'


def md_table(headers: list[str], rows: list[list]) -> str:
    head = '| ' + ' | '.join(headers) + ' |'
    rule = '|---|' + '|'.join('---:' for _ in headers[1:]) + '|'
    body = ['| ' + ' | '.join(str(x) for x in row) + ' |' for row in rows]
    return '\n'.join([head, rule, *body])


def offsets_text(offsets) -> str:
    if not offsets:
        return '—'
    return ', '.join(str(x) for x in offsets)


REGION_ZH = {
    'inside': '窗口内 D..D+6',
    'early_shoulder': '早肩（提前7至13日）',
    'late_shoulder': '晚肩（拐点后1至6日）',
    'ordinary': '普通日',
}
FN_ZH = {
    'never_high': '从未进入因果尾部',
    'tail_blocked_by_lock': '进过尾部，被锁定期挡住',
    'tail_blocked_by_no_rearm': '进过尾部，锁后没有重新武装',
    'tail_blocked_by_lock_or_rearm': '进过尾部，锁定与未武装都有',
    'fired_but_unmatched': '窗口内发过报，但没配到该目标',
    'no_eligible_day': '没有可评分决策日',
}
FP_ZH = {
    'cohort_boundary_hit': '击中成熟队列外的同向拐点',
    'window_goal_already_matched': '窗口内已有目标但被更早警报配走',
    'too_late': '过晚（同向拐点在前1至6日）',
    'too_early': '过早（同向拐点在后7至13日）',
    'opposite_in_window': '窗口内是反向拐点',
    'trend_continuation': '趋势延续（距下次同向拐点至少14日）',
    'after_turn': '拐点已过且超过6日',
    'oscillation_noise': '随后7日振幅小于该档',
    'other': '其他',
}
DECISION_ZH = {
    'GO_P2': '允许进入 P2 发报压缩预登记',
    'BLOCKED_INSUFFICIENT_SAMPLE': '阻断：预注册样本量不足',
    'BLOCKED_NO_CONCENTRATION': '阻断：高分没有集中在 D..D+6',
    'BLOCKED_FN_INVISIBLE': '阻断：漏报大多没有进入高分尾部',
    'BLOCKED_FP_UNSTRUCTURED': '阻断：误报没有可描述的结构',
}
DECISION_EN = {
    'GO_P2': 'GO for a pre-registered Phase P2 alert-compression experiment.',
    'BLOCKED_INSUFFICIENT_SAMPLE': 'BLOCKED. A pre-registered sample floor failed, so alignment is not established.',
    'BLOCKED_NO_CONCENTRATION': 'BLOCKED. High scores do not concentrate inside D..D+6 under the pre-registered tests.',
    'BLOCKED_FN_INVISIBLE': 'BLOCKED. Too many misses never enter the causal high-score tail.',
    'BLOCKED_FP_UNSTRUCTURED': 'BLOCKED. False alerts do not have a describable pre-registered structure.',
}


def decision_paragraphs(result: dict) -> tuple[str, str]:
    code = result['decision']
    tasks = result['tasks']
    fn = result['fn']
    failed = []
    for task in tasks:
        names = [c['name'] for c in task['checks'] if not c['passed']]
        if names:
            failed.append(f"{task['task']}: {', '.join(names)}")
    fail_text = '; '.join(failed) if failed else 'none'
    unsupported = [t['task'] for t in tasks if t['higher_threshold_unsupported']]
    en = [DECISION_EN[code]]
    zh = []
    if code == 'GO_P2':
        en.append(
            'On all four tasks the causal tail is enriched inside the official window relative to '
            'ordinary days and to both shoulders, the lead-profile peak lies inside the window, and '
            f"false alerts have a dominant pre-registered bucket. Pooled FN tail entry is {pct(fn['entered_share'])} "
            f"({fn['entered_tail']}/{fn['denominator_with_eligible_day']})."
        )
        zh.append(
            f"四项任务的因果高分尾部都高于普通日和两侧肩部，领先剖面的峰值落在窗口内，误报有主导分桶。"
            f"合并后 {fn['entered_tail']}/{fn['denominator_with_eligible_day']} 个有可评分日的漏报进过尾部（{pct(fn['entered_share'])}）。"
        )
        en.append(
            'Phase P2, if opened, must write its own plan before running and may test at most three '
            'fire-rule variants on these same close × price scores. This diagnosis did not choose a winner.'
        )
        zh.append('若开 P2，必须先另写 plan.json，且只能在同一套收盘×价格分数上预登记不超过 3 个发报规则。这次没有挑选赢家。')
    elif code == 'BLOCKED_NO_CONCENTRATION':
        ratios = [t['tail_ratio_inside_over_ordinary'] for t in tasks]
        aucs = [t['auc_inside_vs_ordinary'] for t in tasks]
        peaks = ', '.join(
            f"{t['task']} +{offsets_text(t['score_peak_offsets'])}"
            for t in tasks
        )
        shoulder_bits = []
        for task in tasks:
            failed_names = {item['name'] for item in task['checks'] if not item['passed']}
            if 'tail_beats_late' in failed_names:
                shoulder_bits.append(f"{task['task']} late shoulder")
            if 'tail_beats_early' in failed_names:
                shoulder_bits.append(f"{task['task']} early shoulder")
        shoulder_zh = []
        for task in tasks:
            failed_names = {item['name'] for item in task['checks'] if not item['passed']}
            if 'tail_beats_late' in failed_names:
                shoulder_zh.append(f"{task['task']} 晚肩")
            if 'tail_beats_early' in failed_names:
                shoulder_zh.append(f"{task['task']} 早肩")
        shoulder_en = (
            ' Shoulder-average failures: ' + ', '.join(shoulder_bits) + '.'
            if shoulder_bits else ''
        )
        en.append(
            'Ordinary-day enrichment does pass on all four tasks: the inside-window tail rate is '
            f'{min(ratios):.2f} to {max(ratios):.2f} times the ordinary rate, and inside-versus-ordinary AUC is '
            f'{min(aucs):.3f} to {max(aucs):.3f}. The pre-registered test still fails because the mean score and the '
            f'causal tail rate both peak one session after the pivot ({peaks}). That session is the first decision day '
            'whose last input is the pivot close, and an alert then cannot hit the pivot.'
            + shoulder_en
        )
        en.append(
            f"A second, independent gate also fails: only {pct(fn['entered_share'])} of misses with a scoreable day "
            f"entered the causal tail ({fn['entered_tail']}/{fn['denominator_with_eligible_day']}; cutoff 30%). "
            f"{fn['never_high']} misses were never high. Do not only raise the threshold. The highest scores are already "
            'one session too late, so a higher quantile keeps the post-pivot spike and drops the weaker in-window days. '
            'Firing more is not compression: alert counts are already above the dual-80 band. '
            'Next diagnostic, not run here: compare the six frozen price features at offsets -6..0 with offset +1, '
            'without refitting, and see whether anything knowable before the pivot close moves inside the hit window.'
        )
        zh.append(
            f'相对普通日，四项任务的窗口内尾部都更密：尾部比例是普通日的 {min(ratios):.2f} 到 {max(ratios):.2f} 倍，'
            f'窗口对普通日的 AUC 为 {min(aucs):.3f} 到 {max(aucs):.3f}。'
            '预注册检验仍然失败，因为四项任务的平均分数和因果尾部比例都在拐点后的第一个交易日达到峰值。'
            '这一天的最后输入刚好是拐点收盘，发出的警报已经打不中该拐点。'
            + ('肩部均值未通过：' + '、'.join(shoulder_zh) + '。' if shoulder_zh else '')
        )
        zh.append(
            f"另一条独立门槛也没过：有可评分日的漏报里，只有 {pct(fn['entered_share'])} 进过因果尾部"
            f"（{fn['entered_tail']}/{fn['denominator_with_eligible_day']}，下限 30%）。"
            f"{fn['never_high']} 个漏报从未进入尾部。不要只提高阈值。最高分已经落在拐点后一天，"
            '提高分位会留下这个打不中的尖峰，并丢掉窗口内更弱的日子。多发报也不是压缩，警报数已经高于双80必要上限。'
            '下一步不做发报实验，而是在不重训的前提下，比较拐点前 6 日至当天、以及拐点后一天的六个价格特征，'
            '看拐点收盘进入特征之前，窗口内有没有真正移动的坐标。本 PR 不实现该比较。'
        )
    elif code == 'BLOCKED_FN_INVISIBLE':
        en.append(
            f"Only {pct(fn['entered_share'])} of FN targets with an eligible day ever entered the causal tail "
            f"({fn['entered_tail']}/{fn['denominator_with_eligible_day']}). Firing less cannot recover misses that "
            'were never high. Firing more is not alert compression, and alert counts are already above the '
            'dual-80 necessary upper band. Do not only raise thresholds. Next is a feature/label audit of the '
            'never-high misses. It is not implemented here.'
        )
        zh.append(
            f"有可评分日的漏报里，只有 {pct(fn['entered_share'])} 进过因果尾部"
            f"（{fn['entered_tail']}/{fn['denominator_with_eligible_day']}）。少发报找不回从未进入尾部的漏报；"
            '多发报不是压缩，而且警报数已经高于双80必要上限。不要只提高阈值。下一步是这些漏报拐点的特征/标签审计，本 PR 不实现。'
        )
    elif code == 'BLOCKED_FP_UNSTRUCTURED':
        en.append(f'Concentration tests that failed, if any, are listed in the checklist. FP structure failed for at least one task. Case review of the residual buckets should come before any fire-rule trial. Not implemented here.')
        zh.append('至少有一项任务的误报没有形成预注册意义上的主导结构。在做发报压缩之前，应先逐笔看残余桶。本 PR 不开始该实验。')
    elif code == 'BLOCKED_INSUFFICIENT_SAMPLE':
        en.append(f'Sample floors failed: {fail_text}. No alignment claim is made.')
        zh.append(f'样本量下限未达到：{fail_text}。这次不能下富集结论。')
    if unsupported:
        en.append(
            'Median FP excess is at least the median TP excess on '
            + ', '.join(unsupported)
            + '. A higher quantile alone is not supported there; a future fire rule would need a timing or persistence change to be informative.'
        )
        zh.append('这些任务上，误报超额的中位数不低于真阳性：' + '、'.join(unsupported) + '。只提高分位没有依据，后续规则需要动触发时机或持续性。')
    return ' '.join(en), ''.join(zh)


def render_report(result: dict) -> str:
    code = result['decision']
    en, zh = decision_paragraphs(result)
    lines = [
        '# P1 分数是否落在 D..D+6',
        '',
        f'**Decision: `{code}`.** {en}',
        '',
        f'**结论：{DECISION_ZH[code]}。** {zh}',
        '',
        '这是冻结基线的对齐诊断，不是新模型。`formal_signal_allowed` 仍为 false。没有 PIT 认证，没有盲测，没有生产信号。',
        '',
        '## 冻结与复算',
        '',
        '标签 close，特征 price，发报 past_rank90，指数 000985.CSI，决策时钟为 D 日开盘前，命中窗 D..D+6，四任务同幅度同方向一对一。盘中混合标签不进入判定。规则写在 `plan.json`，测量开始前已落盘。',
        '',
        '脚本按 `label_clock_v4/rank_replay.py` 重放因果 90 分位、锁定和重新武装，并与已保存的阈值、警报和指标逐项对齐。',
        '',
        md_table(
            ['任务', '目标', '警报', 'TP', 'FP', 'FN', '精确率', '覆盖率', 'PENDING', '双80警报区间', '区间之上'],
            [[
                t['task'], t['metrics']['targets'], t['metrics']['alerts'], t['metrics']['TP'], t['metrics']['FP'],
                t['metrics']['FN'], pct(t['metrics']['precision']), pct(t['metrics']['recall']), t['metrics']['pending'],
                f"{t['dual80_band']['low']}–{t['dual80_band']['high']}",
                '是' if t['dual80_band']['alerts_above_band'] else '否',
            ] for t in result['tasks']],
        ),
        '',
        '上表与 `label_clock_v4/rank_metrics.csv` 的 close × price × past_rank90 行一致，也与原先展示的 23.6%/44.7%、33.9%/51.3%、15.2%/38.9%、15.7%/42.1% 在一位小数上一致。双80区间只说明现有警报数高于数学上限，不是用未来目标数去定配额。',
        '',
        '## 窗口内、肩部、普通日',
        '',
        '窗口内是能够击中该拐点的决策日：拐点前 6 日至拐点当天。早肩再往前 7 日，晚肩是拐点后 1 至 6 日。一天若落在任一目标窗口内，优先算窗口内。因果尾部指分数不低于当天过去 252 个已发分数的线性 90 分位。',
        '',
        md_table(
            ['任务', '区域', '天数', '分数中位数', '尾部比例', '超额中位数', '事后分位中位数'],
            [[
                row['task'], REGION_ZH[row['region']], row['n_days'], fmt(row['score_median'], 3),
                pct(row['tail_rate']), fmt(row['median_excess'], 3), fmt(row['median_hindsight_percentile'], 1),
            ] for row in result['region_rows']],
        ),
        '',
        md_table(
            ['任务', 'AUC', '尾部倍数', '目标周命中', '普通周命中', '分数峰值偏移', '尾部峰值偏移', '集中度'],
            [[
                t['task'], fmt(t['auc_inside_vs_ordinary'], 3), fmt(t['tail_ratio_inside_over_ordinary'], 2),
                pct(t['target_any_tail_rate']), pct(t['ordinary_block_stride1_rate']),
                offsets_text(t['score_peak_offsets']), offsets_text(t['tail_peak_offsets']),
                'PASS' if t['concentration_pass'] else 'FAIL',
            ] for t in result['tasks']],
        ),
        '',
        'AUC 只比较窗口内与普通日，肩部不进这一对。它和旧诊断里“正例对其余所有日子”的 0.70–0.77 不是同一个分母。目标周命中是“该目标的可评分窗口里至少有一天进入因果尾部”的比例；普通周命中是完全落在普通日上的连续 7 日块、步长 1、至少有一天进入尾部的比例。领先剖面的偏移 0 是拐点当天，-6 是窗口第一天。',
        '',
        '分数在决策日 D 使用截至 D-1 的收盘。偏移 +1 的最后输入就是拐点当天的收盘，也是这个收盘第一次进入特征的决策日；警报窗口从这一天起算，已经不包含该拐点。下表是峰值附近，不是新的判定门槛。',
        '',
        md_table(
            ['任务', '偏移', '样本', '尾部比例', '平均分数', '平均超额', '是否在命中窗'],
            [
                [
                    row['task'], row['offset'], row['n'], pct(row['tail_rate']),
                    fmt(row['mean_score'], 3), fmt(row['mean_excess'], 3),
                    '是' if -6 <= row['offset'] <= 0 else '否',
                ]
                for row in result['lead_rows'] if row['offset'] in (-1, 0, 1, 2)
            ],
        ),
        '',
        '图：`fig_score_ecdf.png`，`fig_tail_rate_by_region.png`，`fig_lead_profile.png`，`fig_lead_mean_score.png`。',
        '',
        '## 漏报有没有进过尾部',
        '',
        md_table(
            ['任务', 'FN', '可评分', '进过尾部', '从未进入', '进过尾部的比例', '从未进入者的最高事后分位中位数', '其最高超额中位数'],
            [[
                row['task'], row['fn'], row['denominator'], row['entered_tail'], row['never_high'],
                pct(row['entered_share']), fmt(row['never_high_median_max_hindsight_percentile'], 1),
                fmt(row['never_high_median_max_excess'], 3),
            ] for row in result['fn']['by_task']],
        ),
        '',
        f"四项合并：进过尾部 {result['fn']['entered_tail']} / {result['fn']['denominator_with_eligible_day']} = {pct(result['fn']['entered_share'])}。预注册下限是 30%。"
        f" 从未进入的漏报里，最高事后分位低于 80 的比例是 {pct(result['fn']['never_high_share_hindsight_below_80'])}，"
        f"落在 [80, 90) 的比例是 {pct(result['fn']['never_high_share_hindsight_80_to_90'])}。"
        ' 事后分位使用了全部可评分日，只用来看漏报离尾部有多远，不参与发报。',
        '',
        '类别计数：',
        '',
        md_table(
            ['任务'] + [FN_ZH[name] for name in (
                'never_high', 'tail_blocked_by_lock', 'tail_blocked_by_no_rearm',
                'tail_blocked_by_lock_or_rearm', 'fired_but_unmatched', 'no_eligible_day',
            )],
            [[
                row['task'],
                *[row['class_counts'].get(name, 0) for name in (
                    'never_high', 'tail_blocked_by_lock', 'tail_blocked_by_no_rearm',
                    'tail_blocked_by_lock_or_rearm', 'fired_but_unmatched', 'no_eligible_day',
                )],
            ] for row in result['fn']['by_task']],
        ),
        '',
        '图：`fig_fn_breakdown.png`，`fig_window_max_excess.png`。后一张图里的普通周是互不重叠的步长 7，只作图示；判定用的是步长 1。',
        '',
        '## 误报结构',
        '',
        '分桶使用事后拐点与事后价格，解释误报，不能当作特征。互斥优先级见 `plan.json`。结构检验把“击中成熟队列外拐点”拿出分母，因为它是队列边界，不是行情机制。原始旗标允许重叠，见 `fp_flag_rates.csv`。',
        '',
        md_table(
            ['任务', 'FP', '经济误报', '队列边界', '主导桶', '主导占比', '前两桶', '其他', '结构'],
            [[
                row['task'], row['fp'], row['economic_fp'], row['cohort_boundary_hit'],
                FP_ZH.get(row['top1_bucket'], row['top1_bucket'] or '—'),
                pct(row['top1_share_economic']), pct(row['top2_share_economic']),
                pct(row['other_share_economic']), row['structure_status'],
            ] for row in result['fp_rows']],
        ),
        '',
        md_table(
            ['任务'] + [FP_ZH[name] for name in FP_PRIORITY],
            [[row['task'], *[row[name] for name in FP_PRIORITY]] for row in result['fp_rows']],
        ),
        '',
        md_table(
            ['任务', 'TP超额中位数', 'FP超额中位数', '只提高分位缺乏依据'],
            [[
                t['task'], fmt(t['tp_median_excess'], 3), fmt(t['fp_median_excess'], 3),
                '是' if t['higher_threshold_unsupported'] else '否',
            ] for t in result['tasks']],
        ),
        '',
        '图：`fig_fp_buckets.png`。',
        '',
        '## 逐项判定',
        '',
        md_table(
            ['任务', '检验', '结果', '实际值', '预注册要求'],
            [[
                row['task'], row['name'], 'PASS' if row['passed'] else 'FAIL',
                fmt(row['actual'], 4) if not isinstance(row['actual'], list) else offsets_text(row['actual']),
                row['expect'],
            ] for row in result['test_rows']],
        ),
        '',
        '## 其他披露',
        '',
    ]
    for task in result['tasks']:
        lines.append(
            f"- {task['task']}: 分数自 {task['first_score_date']}，因果阈值自 {task['first_threshold_date']}，"
            f"可评分日 {task['n_eligible']}，分数日期间断 {task['score_gaps']}，"
            f"同向目标最短间隔 {task['goal_gap_min']}，间隔≤6 的相邻对 {task['goal_pairs_gap_le_6']}，"
            f"被两个窗口同时覆盖的可评分日 {task['inside_days_covered_by_two_targets']}，"
            f"早肩与窗口重叠后改记为窗口内的可评分日 {task['reclassified_early_days_counted_inside']}，"
            f"拐点方向是否交替 {'是' if task['pivots_alternate'] else '否'}，"
            f"事后前十分位倍数 {fmt(task['hindsight_top_decile_ratio'], 2)}，"
            f"步长7普通周尾部比例 {pct(task['ordinary_block_stride7_rate'])}（{task['ordinary_block_stride7_n']} 块），"
            f"成熟边界 {task['frontier']}，右端 6 日内目标 {task['metrics']['right_boundary_targets_last6']}。"
        )
    missing = [
        f"{row['task']} {row['pivot_date']}"
        for row in result['target_rows'] if row['fn_class'] == 'no_eligible_day'
    ]
    if missing:
        lines.append('')
        lines.append(
            '下列目标在公布的 FN 里，但窗口内没有因果阈值，因此不进入 30% 漏报分母：'
            + '，'.join(missing)
            + '。'
            + '；'.join(
                f"{t['task']} 的分数自 {t['first_score_date']} 起、因果阈值自 {t['first_threshold_date']} 起"
                for t in result['tasks'] if t['scale'] == 9
            )
            + '。若把这些目标算作从未进入尾部，进尾比例只会更低。'
        )
    cohort_notes = [
        f"{row['task']} {pct(row['cohort_share_of_fp'])}"
        for row in result['fp_rows'] if (row['cohort_share_of_fp'] or 0) >= 0.30
    ]
    if cohort_notes:
        lines.append('')
        lines.append('队列边界误报占比达到 30% 的任务：' + '，'.join(cohort_notes) + '。这些警报击中了成熟队列不记分的同向拐点，不能当成普通噪声。')
    lines.extend([
        '',
        '## 边界',
        '',
        '- 决策日重叠，分数自相关。预注册门槛是描述性规则，不是独立样本的显著性检验。',
        '- 区域用的是事后才确认的评估拐点。这是对齐诊断，不是可交易信号。',
        '- 因果尾部只用过去分数。事后分位和误报分桶用了后来的日子，已在表内分开。',
        '- 历史被反复看过，不是新的盲测。历史公布时点与指数成分仍未完成全时期 PIT 认证。',
        '- 没有修改生产页面、采集器、正式信号，也没有恢复旧 V 系列。',
        '- 没有把 D 日价格写入特征。用到的分数行都满足 `last_input` 为前一交易日。',
        '',
        '## 复算',
        '',
        '```text',
        'python -B dual80-research/p1_score_alignment/diagnose.py',
        '```',
        '',
        '缺少 `plan.json` 时，测量会停止。`--write-plan-only` 只在文件不存在时写出计划，不读分数分布。',
        '',
    ])
    return '\n'.join(lines) + '\n'


def save_figures(result: dict) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    colors = {
        'inside': '#0072B2',
        'early_shoulder': '#E69F00',
        'late_shoulder': '#CC79A7',
        'ordinary': '#666666',
    }
    labels = {
        'inside': 'Inside D..D+6',
        'early_shoulder': 'Early shoulder',
        'late_shoulder': 'Late shoulder',
        'ordinary': 'Ordinary',
    }
    tasks = result['tasks_full']

    fig, axes = plt.subplots(2, 2, figsize=(11.4, 8.0), sharex=False, sharey=True)
    for ax, task in zip(axes.ravel(), tasks):
        for region in REGIONS:
            scores = sorted(d['score'] for d in task['eligible_days'] if d['region'] == region)
            if not scores:
                continue
            y = np.arange(1, len(scores) + 1) / len(scores)
            ax.step(scores, y, where='post', color=colors[region], lw=1.6, label=labels[region])
        ax.set_title(task['task'])
        ax.set_xlabel('Score')
        ax.set_ylabel('ECDF')
        ax.grid(alpha=0.25)
    axes[0, 0].legend(fontsize=8, loc='lower right')
    fig.suptitle('Close × price score distribution by region')
    fig.tight_layout()
    fig.savefig(HERE / 'fig_score_ecdf.png', dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10.2, 4.8))
    x = np.arange(len(tasks))
    width = 0.18
    for i, region in enumerate(REGIONS):
        vals = [task['regions'][region]['tail_rate'] or 0 for task in tasks]
        ax.bar(x + (i - 1.5) * width, vals, width, color=colors[region], label=labels[region])
    ax.set_xticks(x, [task['task'] for task in tasks])
    ax.set_ylabel('Causal past-rank90 tail rate')
    ax.set_ylim(0, 1)
    ax.legend(fontsize=8)
    ax.grid(axis='y', alpha=0.25)
    ax.set_title('Tail rate inside the hit window, on the shoulders, and on ordinary days')
    fig.tight_layout()
    fig.savefig(HERE / 'fig_tail_rate_by_region.png', dpi=140)
    plt.close(fig)

    def draw_lead(value_key, ylabel, title, path):
        fig, axes = plt.subplots(2, 2, figsize=(11.4, 8.0), sharex=True, sharey=False)
        for ax, task in zip(axes.ravel(), tasks):
            rows = task['lead']
            xs = [r['offset'] for r in rows]
            ys = [np.nan if r[value_key] is None else r[value_key] for r in rows]
            ax.axvspan(-6, 0, color='#0072B2', alpha=0.15, zorder=0)
            ax.axvline(1, color='#D55E00', lw=0.9, ls=':', zorder=1)
            ax.plot(xs, ys, color='#0072B2', marker='o', ms=3.5, lw=1.7, zorder=3)
            if value_key == 'tail_rate':
                ordinary = task['regions']['ordinary']['tail_rate']
                if ordinary is not None:
                    ax.axhline(ordinary, color='#666666', ls='--', lw=1, zorder=2)
                ax.set_ylim(0, 1)
            ax.set_xlim(-13.5, 6.5)
            ax.set_title(task['task'])
            ax.set_xlabel('Sessions relative to pivot (0 = pivot day)')
            ax.set_ylabel(ylabel)
            ax.grid(alpha=0.25)
        fig.suptitle(title)
        fig.tight_layout()
        fig.savefig(path, dpi=140)
        plt.close(fig)

    draw_lead(
        'tail_rate',
        'Causal tail rate',
        'Tail rate by lead. Shade = D..D+6. Dotted line = first session after the pivot.',
        HERE / 'fig_lead_profile.png',
    )
    draw_lead(
        'mean_score',
        'Mean score',
        'Mean score by lead. Shade = D..D+6. Dotted line = first session after the pivot.',
        HERE / 'fig_lead_mean_score.png',
    )

    fn_names = (
        'never_high', 'tail_blocked_by_lock', 'tail_blocked_by_no_rearm',
        'tail_blocked_by_lock_or_rearm', 'fired_but_unmatched', 'no_eligible_day',
    )
    fn_colors = ['#666666', '#0072B2', '#56B4E9', '#009E73', '#E69F00', '#CC79A7']
    fig, ax = plt.subplots(figsize=(10.2, 4.6))
    y = np.arange(len(result['fn']['by_task']))
    left = np.zeros(len(y))
    for name, color in zip(fn_names, fn_colors):
        vals = np.array([row['class_counts'].get(name, 0) for row in result['fn']['by_task']], float)
        ax.barh(y, vals, left=left, color=color, label=name)
        left += vals
    ax.set_yticks(y, [row['task'] for row in result['fn']['by_task']])
    ax.invert_yaxis()
    ax.set_xlabel('FN targets')
    ax.legend(fontsize=7, loc='lower right')
    ax.set_title('Misses: never in the causal tail, or in the tail but not fired/matched')
    fig.tight_layout()
    fig.savefig(HERE / 'fig_fn_breakdown.png', dpi=140)
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(11.4, 8.0))
    for ax, task in zip(axes.ravel(), tasks):
        counts = [task['fp'][name] for name in FP_PRIORITY]
        ax.barh(np.arange(len(FP_PRIORITY)), counts, color='#0072B2')
        ax.set_yticks(np.arange(len(FP_PRIORITY)), list(FP_PRIORITY), fontsize=8)
        ax.invert_yaxis()
        ax.set_title(task['task'])
        ax.set_xlabel('FP alerts')
        ax.grid(axis='x', alpha=0.25)
    fig.suptitle('Exclusive false-alert buckets (cohort boundary kept visible)')
    fig.tight_layout()
    fig.savefig(HERE / 'fig_fp_buckets.png', dpi=140)
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(11.4, 8.0), sharey=True)
    by_target = {}
    for row in result['target_rows']:
        by_target.setdefault(row['task'], {'TP': [], 'FN': []})
        if row['status'] in ('TP', 'FN') and row['max_excess'] is not None:
            by_target[row['task']][row['status']].append(row['max_excess'])
    for ax, task in zip(axes.ravel(), tasks):
        series = [
            by_target[task['task']]['TP'] or [np.nan],
            by_target[task['task']]['FN'] or [np.nan],
            task['stride7_max_excess'] or [np.nan],
        ]
        ax.axhline(0, color='black', lw=0.8)
        ax.boxplot(series, tick_labels=['TP window', 'FN window', 'Ordinary block'], showfliers=False)
        ax.set_title(task['task'])
        ax.set_ylabel('Max excess over causal threshold')
        ax.grid(axis='y', alpha=0.25)
    fig.suptitle('Best window excess. Ordinary blocks are non-overlapping and illustrative.')
    fig.tight_layout()
    fig.savefig(HERE / 'fig_window_max_excess.png', dpi=140)
    plt.close(fig)


def write_artifact_manifest() -> None:
    files = sorted(p for p in HERE.iterdir() if p.is_file() and p.name != 'artifact_manifest.json')
    manifest = {
        p.name: {'bytes': p.stat().st_size, 'sha256': sha256_file(p)}
        for p in files
    }
    (HERE / 'artifact_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def write_outputs(result: dict) -> None:
    public = {
        'phase': 'P1',
        'decision': result['decision'],
        'formal_signal_allowed': False,
        'blind_test': False,
        'PIT_certified': False,
        'production_changed': False,
        'intraday_hybrid_used_for_decision': False,
        'integrity': result['integrity'],
        'tasks': result['tasks'],
        'fn': result['fn'],
        'fp': result['fp_rows'],
    }
    (HERE / 'result.json').write_text(json.dumps(plain(public), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    decision = {
        'decision': result['decision'],
        'formal_signal_allowed': False,
        'blind_test': False,
        'PIT_certified': False,
        'production_changed': False,
        'english': decision_paragraphs(result)[0],
        'chinese': decision_paragraphs(result)[1],
        'task_concentration_pass': {t['task']: t['concentration_pass'] for t in result['tasks']},
        'task_fp_structure_pass': {t['task']: t['fp_structure_pass'] for t in result['tasks']},
        'fn_entered_share': result['fn']['entered_share'],
        'fn_visibility_pass': result['fn']['pass'],
    }
    (HERE / 'decision.json').write_text(json.dumps(plain(decision), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (HERE / 'README.md').write_text(render_report(result), encoding='utf-8')
    write_csv(HERE / 'region_distribution.csv', result['region_rows'], [
        'task', 'region', 'n_days', 'share_of_eligible', 'score_mean', 'score_median', 'p10', 'p25', 'p75', 'p90', 'p95',
        'mean_hindsight_percentile', 'median_hindsight_percentile', 'tail_rate', 'mean_excess', 'median_excess', 'n_tail',
        'hindsight_top_decile_rate',
    ])
    write_csv(HERE / 'lead_profile.csv', result['lead_rows'], [
        'task', 'offset', 'n', 'mean_score', 'tail_rate', 'mean_excess',
    ])
    write_csv(HERE / 'target_windows.csv', result['target_rows'], [
        'task', 'pivot_date', 'confirmation_date', 'status', 'matched_alert_date', 'lead_sessions',
        'n_eligible_days', 'n_tail_days', 'max_score', 'max_excess', 'max_hindsight_percentile', 'max_causal_ecdf',
        'argmax_offset', 'ever_tail', 'fn_class', 'fn_detail', 'right_boundary_last6', 'tail_on_ineligible_window_day',
    ])
    write_csv(HERE / 'alert_detail.csv', result['alert_rows'], [
        'task', 'date', 'status', 'pivot_date', 'lead_sessions', 'score', 'threshold', 'excess', 'hindsight_percentile',
        'exclusive_bucket', 'prev_same_sessions', 'next_same_sessions', 'next_opposite_sessions',
        'forward_7d_return', 'forward_20d_return', 'forward_20d_against_reversal',
        *[f'raw_{name}' for name in FP_PRIORITY if name != 'other'],
    ])
    write_csv(HERE / 'fn_summary.csv', result['fn_rows'], [
        'task', 'fn', 'denominator', 'entered_tail', 'entered_share', 'never_high',
        'never_high_median_max_hindsight_percentile', 'never_high_median_max_excess', 'ineligible_tail_on_fn',
    ])
    write_csv(HERE / 'fp_summary.csv', result['fp_rows'], [
        'task', 'fp', 'economic_fp', 'cohort_share_of_fp', *FP_PRIORITY,
        'structure_status', 'structure_pass', 'other_share_economic', 'top1_bucket', 'top1_share_economic', 'top2_share_economic',
    ])
    write_csv(HERE / 'fp_flag_rates.csv', result['flag_rows'], [
        'task', 'flag', 'n_raw', 'share_of_fp', 'n_exclusive', 'share_exclusive_of_fp',
    ])
    write_csv(HERE / 'task_tests.csv', result['test_rows'], [
        'task', 'group', 'name', 'passed', 'actual', 'expect',
    ])
    write_csv(HERE / 'eligible_days.csv', result['eligible_rows'], [
        'task', 'date', 'index', 'region', 'score', 'threshold', 'excess', 'in_tail',
        'hindsight_percentile', 'causal_ecdf', 'fired', 'block_reason',
    ])
    save_figures(result)
    write_artifact_manifest()


def main() -> None:
    self_test_classifier()
    if '--write-plan-only' in sys.argv:
        write_plan_only()
        return
    plan = assert_plan_frozen()
    result = replay_and_measure(plan)
    write_outputs(result)
    print(json.dumps({
        'decision': result['decision'],
        'fn_entered_share': result['fn']['entered_share'],
        'concentration': {t['task']: t['concentration_pass'] for t in result['tasks']},
        'fp_structure': {t['task']: t['fp_structure_pass'] for t in result['tasks']},
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
