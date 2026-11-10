"""P1b diagnostic: do the six frozen price features move before the pivot close?

This script does not fit a model, search a threshold, add a factor, or emit a signal.
Write plan.json first, without reading feature profiles:

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
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CLOCK = ROOT / 'dual80-research' / 'label_clock_v4'
P1 = ROOT / 'dual80-research' / 'p1_score_alignment'
TASKS = ('5_TOP', '5_BOTTOM', '9_TOP', '9_BOTTOM')
FEATURES = (
    'return3_scaled',
    'return20_scaled',
    'change_in_return3_scaled',
    'distance_to_20day_high_scaled',
    'distance_to_20day_low_scaled',
    'position63',
)
# Reported only. decide() does not read these signs.
ECONOMIC_SIGN = {
    '5_TOP': {
        'return3_scaled': 1,
        'return20_scaled': 1,
        'change_in_return3_scaled': -1,
        'distance_to_20day_high_scaled': 1,
        'distance_to_20day_low_scaled': 1,
        'position63': 1,
    },
    '5_BOTTOM': {
        'return3_scaled': -1,
        'return20_scaled': -1,
        'change_in_return3_scaled': 1,
        'distance_to_20day_high_scaled': -1,
        'distance_to_20day_low_scaled': -1,
        'position63': -1,
    },
    '9_TOP': {
        'return3_scaled': 1,
        'return20_scaled': 1,
        'change_in_return3_scaled': -1,
        'distance_to_20day_high_scaled': 1,
        'distance_to_20day_low_scaled': 1,
        'position63': 1,
    },
    '9_BOTTOM': {
        'return3_scaled': -1,
        'return20_scaled': -1,
        'change_in_return3_scaled': 1,
        'distance_to_20day_high_scaled': -1,
        'distance_to_20day_low_scaled': -1,
        'position63': -1,
    },
}
SHORT = {
    'return3_scaled': 'return 3d',
    'return20_scaled': 'return 20d',
    'change_in_return3_scaled': 'change in return 3d',
    'distance_to_20day_high_scaled': 'distance to 20d high',
    'distance_to_20day_low_scaled': 'distance to 20d low',
    'position63': 'position in 63d range',
}
CN_FEATURE = {
    'return3_scaled': '3日收益',
    'return20_scaled': '20日收益',
    'change_in_return3_scaled': '3日收益变化',
    'distance_to_20day_high_scaled': '距20日高点',
    'distance_to_20day_low_scaled': '距20日低点',
    'position63': '63日区间位置',
}
OFFSETS = list(range(-6, 3))
WINDOW = list(range(-6, 1))
SOURCE_FILES = (
    'ACTIVE_RESEARCH_CONTRACT.json',
    'turning-research-canonical/tables/research_inputs.csv',
    'turning-label-comparison/all_labels.csv',
    'dual80-research/broad_experiments_v2/run.py',
    'dual80-research/label_clock_v4/run.py',
    'dual80-research/label_clock_v4/scores.csv',
    'dual80-research/p1_score_alignment/plan.json',
    'dual80-research/p1_score_alignment/decision.json',
    'dual80-research/p1_score_alignment/lead_profile.csv',
    'dual80-research/p1_score_alignment/eligible_days.csv',
    'dual80-research/p1_score_alignment/target_windows.csv',
    'dual80-research/p1_score_alignment/diagnose.py',
)

CORE = {
    'phase': 'P1b',
    'title': 'Feature-timing audit of the six frozen price inputs at offsets -6..+1',
    'contains_measurements': False,
    'hypothesis': (
        'P1 found that the frozen close x price x past_rank90 score peaks at offset +1 on all '
        'four tasks. Offset +1 is the first pre-open decision whose last input is the pivot '
        'close, and an alert that day cannot hit that pivot. This audit asks whether any of '
        'the six price inputs that already enter that frozen score moves inside offsets -6..0, '
        'where the last input is still before the pivot close. It does not refit the model. '
        'A pass means a later gated experiment may pre-register that coordinate. A fail means '
        'the marginal feature movement is dominated by the pivot close, and the feature layer '
        'stays blocked.'
    ),
    'freeze': {
        'index': '000985.CSI',
        'label': 'close',
        'features': 'price',
        'feature_names': list(FEATURES),
        'feature_source': (
            'label_clock_v4 imports make_features from broad_experiments_v2/run.py and calls '
            'make_features(closes, turnover, style, scale=5). The price block does not read '
            'scale, turnover, or style. This audit uses that same matrix. It does not rebuild '
            'a second feature family.'
        ),
        'formulas_at_last_input_index_i': {
            'v': 'max(sample stdev of diff(log(c[i-20:i+1])), ddof=1, floor 0.001)',
            'return3_scaled': 'log(c[i]/c[i-3]) / v',
            'return20_scaled': 'log(c[i]/c[i-20]) / (v * sqrt(20))',
            'change_in_return3_scaled': '(log(c[i]/c[i-3]) - log(c[i-3]/c[i-6])) / v',
            'distance_to_20day_high_scaled': 'log(c[i] / max(c[i-19:i+1])) / v',
            'distance_to_20day_low_scaled': 'log(c[i] / min(c[i-19:i+1])) / v',
            'position63': '(c[i] - min(c[i-62:i+1])) / (max(c[i-62:i+1]) - min(c[i-62:i+1])), or 0.5 if the range is 0',
            'slice_note': 'Python half-open slices. c[i-19:i+1] is the 20 closes ending at i. The pivot close is outside that window when i <= pivot-1.',
        },
        'fire_rule': 'not used. past_rank90 remains the frozen P1 rule and is not re-estimated.',
        'decision_clock': 'pre-open on day D; feature row D uses closes through D-1',
        'offset_definition': (
            'Offset k is decision index pivot_index + k. Its last input index is '
            'pivot_index + k - 1. Offset 0 is the pivot session and its last input is the '
            'previous close. Offset +1 is the next session and its last input is the pivot close.'
        ),
        'hittable_window': 'Offsets -6..0. An alert on those decision days can still hit the pivot. The pivot close is not an input.',
        'offset_plus1': 'First decision day whose last input is the pivot close. An alert that day cannot hit the pivot.',
        'offset_plus2': 'Shoulder. Last input is the session after the pivot. Reported, not a gate.',
        'new_factors': False,
        'refit': False,
        'threshold_search': False,
        'alert_quota_from_future_target_counts': False,
        'formal_signal_allowed': False,
        'blind_test': False,
        'PIT_certified': False,
        'production_changed': False,
        'p2_alert_compression': False,
    },
    'cohort_lock': {
        'source': 'P1 eligible_days.csv and target_windows.csv, close x price mature cohort',
        'targets': {'5_TOP': 38, '5_BOTTOM': 39, '9_TOP': 18, '9_BOTTOM': 19},
        'eligible_days': {'5_TOP': 2396, '5_BOTTOM': 2396, '9_TOP': 2057, '9_BOTTOM': 2057},
        'regions': {
            '5_TOP': {'inside': 266, 'early_shoulder': 259, 'late_shoulder': 216, 'ordinary': 1655},
            '5_BOTTOM': {'inside': 267, 'early_shoulder': 273, 'late_shoulder': 209, 'ordinary': 1647},
            '9_TOP': {'inside': 112, 'early_shoulder': 112, 'late_shoulder': 96, 'ordinary': 1737},
            '9_BOTTOM': {'inside': 106, 'early_shoulder': 112, 'late_shoulder': 87, 'ordinary': 1752},
        },
        'p1_decision': 'BLOCKED_NO_CONCENTRATION',
        'ordinary_definition': 'P1 region ordinary: eligible day in no evaluated target window and in neither shoulder.',
    },
    'hold_last_close': {
        'definition': (
            'At the offset-+1 decision, recompute the same six formulas after replacing the '
            'pivot close with the previous close. The difference actual minus held is the '
            'isolated pivot-close jump. It is not a score, not a feature to train, and not '
            'written back onto the canonical close series.'
        ),
        'uses_new_model': False,
    },
    'standardization': {
        'center': 'mean of the feature on P1 ordinary eligible days of the same task',
        'scale': 'sample standard deviation of those ordinary days, ddof=1',
        'z': '(event mean - ordinary mean) / ordinary std',
        'median': 'numpy median; even counts use the average of the two middle values',
    },
    'samples': {
        'all_eligible': 'Evaluated pivots whose decision day at that offset is a P1 eligible day. Used for the lead profile and for the P1 score-profile lock.',
        'complete_case': 'Evaluated pivots with every offset -6..+1 eligible. Gates use this set so the window and offset +1 contain the same pivots.',
        'offset_plus2': 'Reported on complete-case pivots that also have offset +2 eligible. Not a gate.',
    },
    'tests': {
        'sample_floors': {
            'complete_case_min': 10,
            'ordinary_min': 100,
            'per_offset_eligible_min': 10,
            'offsets': WINDOW + [1],
        },
        'presence': {
            'name': 'presence',
            'requires_abs_z_plus1_min': 0.25,
            'same_sign_window_min': 0.2,
            'window_over_abs_plus1_min': 0.5,
            'same_sign_offset0_min': 0.15,
            'window_over_same_sign_jump_min': 0.5,
            'median_strictly_on_anchor_side': True,
            'offset_z_floor': 0.1,
            'min_offsets': 4,
            'window_offsets': WINDOW,
            'anchor': 'sign of z at offset +1, defined only when abs(z at +1) clears the floor. This sign is the direction of the pivot-close session. It is not an economic sign chosen after inspecting which side passes.',
        },
        'build': {
            'name': 'build',
            'abs_late_minus_early_min': 0.35,
            'must_exceed_abs_jump': True,
            'must_exceed_abs_plus1_minus_offset0': True,
            'abs_late_min': 0.2,
            'median_strictly_on_build_side': True,
            'early_offsets': [-6, -5, -4],
            'late_offsets': [-2, -1, 0],
        },
        'go': {
            'presence_on_at_least_n_tasks': 2,
            'build_on_at_least_n_tasks': 2,
            'single_task_requires_both_tests': True,
            'single_task_abs_z_win_min': 0.5,
            'code': 'GO_PRE_PIVOT_COORDINATE',
            'meaning': (
                'A later experiment may pre-register only the named feature-task cells. '
                'It does not authorize a refit of all six features, Phase P2 alert compression, '
                'a higher threshold, a new factor, or a signal.'
            ),
        },
        'blocked_pivot_close': {
            'jump_abs_min': 0.25,
            'jump_abs_gt_window_abs': True,
            'plus1_abs_min': 0.25,
            'plus1_abs_gt_window_abs': True,
            'plus1_abs_gt_offset0_abs': True,
            'code': 'BLOCKED_PIVOT_CLOSE_DOMINATED',
            'rule': (
                'Used only when the GO rule fails. A cell is pivot-close dominated when the '
                'absolute isolated jump clears 0.25 and exceeds the absolute window departure, '
                'or when the absolute offset-+1 departure clears 0.25 and exceeds both the '
                'absolute window departure and the absolute offset-0 departure.'
            ),
        },
        'blocked_no_marginal_move': {
            'code': 'BLOCKED_NO_MARGINAL_MOVE',
            'rule': 'GO failed, sample floors passed, and no cell meets the pivot-close dominance rule.',
        },
        'decision_order': [
            'BLOCKED_INSUFFICIENT_SAMPLE if any task fails a sample floor',
            'else GO_PRE_PIVOT_COORDINATE if any feature passes presence on at least two tasks, or build on at least two tasks, or both tests on one task with abs(z_win) >= 0.5',
            'else BLOCKED_PIVOT_CLOSE_DOMINATED if any cell meets the dominance rule',
            'else BLOCKED_NO_MARGINAL_MOVE',
        ],
        'dependence_note': (
            'Days overlap and features are autocorrelated. These gates are pre-registered '
            'descriptive rules. No p-value is a gate. Economic signs are reported and are not gates.'
        ),
    },
    'reported_not_gates': [
        'economic sign agreement with the offset-+1 anchor',
        'path fraction (z(0) - z(-6)) / (z(+1) - z(-6))',
        'aging = z(held at +1) - z(0)',
        'Pearson correlation of the offset-+1 minus offset-0 score change with the same change in each feature',
        'Pearson correlation of that score change with the isolated pivot-close jump',
        'share of complete-case pivots whose offset-0 and offset-+1 values lie on the anchor side of the ordinary median',
        'z at offset +2',
        'all-eligible lead profile beside the complete-case profile',
    ],
    'leakage': [
        'Putting the pivot close, or any later close, into a value assigned to offsets -6..0.',
        'Treating offset 0 as if its last input were the pivot close. Offset 0 last input is the previous session.',
        'Using the decision session close inside the feature for that same decision session.',
        'Using a confirmation date, a later pivot, the label, or the match status as a feature.',
        'Fitting, refitting, or editing logistic coefficients, standardizers, or thresholds.',
        'Choosing a feature sign, a favorite offset, or a numeric gate after seeing the lead profile.',
        'Adding amount, style, swing, interaction, intraday, or any input outside the frozen price block.',
        'Writing a score, an alert, or a production signal from the held-close counterfactual.',
        'Declaring GO because offset +1 is large.',
        'Changing the label, the index, or the hit window.',
        'Using future target counts as a quota.',
    ],
    'out_of_scope': [
        'No Phase P2 alert compression.',
        'No threshold change and no new fire rule.',
        'No refit and no new factor.',
        'No label change and no index change.',
        'No production page, collector, official signal, or V-series workflow.',
        'formal_signal_allowed stays false.',
        'Not PIT and not a blind test.',
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
        raise SystemExit('source files changed after plan.json was written')
    return on_disk


def write_plan_only() -> None:
    self_test_clock()
    path = HERE / 'plan.json'
    if path.exists():
        raise SystemExit('plan.json already exists and is not rewritten')
    plan = build_plan()
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    loaded = json.loads(path.read_text(encoding='utf-8'))
    if {k: v for k, v in loaded.items() if k != 'source_sha256'} != CORE:
        path.unlink()
        raise SystemExit('plan.json did not round-trip onto CORE')
    print(json.dumps({'wrote': str(path), 'contains_measurements': False}, ensure_ascii=False))


def price_row(closes: np.ndarray, i: int) -> np.ndarray:
    """Six frozen price formulas at last-input index i. Decision day is i+1."""
    rets = np.diff(np.log(closes[i - 20:i + 1]))
    v = max(float(np.std(rets, ddof=1)), 0.001)
    r3 = float(np.log(closes[i] / closes[i - 3]))
    r20 = float(np.log(closes[i] / closes[i - 20]))
    prev = float(np.log(closes[i - 3] / closes[i - 6]))
    hi20 = float(np.max(closes[i - 19:i + 1]))
    lo20 = float(np.min(closes[i - 19:i + 1]))
    hi63 = float(np.max(closes[i - 62:i + 1]))
    lo63 = float(np.min(closes[i - 62:i + 1]))
    pos = (float(closes[i]) - lo63) / (hi63 - lo63) if hi63 > lo63 else 0.5
    return np.array([
        r3 / v,
        r20 / (v * math.sqrt(20.0)),
        (r3 - prev) / v,
        math.log(float(closes[i]) / hi20) / v,
        math.log(float(closes[i]) / lo20) / v,
        pos,
    ], dtype=float)


def self_test_clock() -> None:
    closes = np.full(80, 100.0)
    closes[60] = 110.0
    closes[70] = 120.0
    before = price_row(closes, 69)
    after = price_row(closes, 70)
    if not (before[3] < 0.0 and after[3] == 0.0 and after[5] == 1.0 and before[5] < 1.0):
        raise SystemExit('clock self-test failed: the spike close is visible on the wrong decision day')
    if not (before[0] == 0.0 and after[0] > 0.0):
        raise SystemExit('clock self-test failed: return3 saw the spike too early')
    held_closes = closes.copy()
    held_closes[70] = held_closes[69]
    held = price_row(held_closes, 70)
    if not (held[3] < 0.0 and held[5] < 1.0):
        raise SystemExit('clock self-test failed: withholding the spike did not remove it')
    leaked = closes.copy()
    leaked[71] += 5.0
    if not np.array_equal(price_row(leaked, 70), after):
        raise SystemExit('clock self-test failed: a later close entered the feature')
    same_day = closes.copy()
    same_day[70] += 5.0
    if not np.array_equal(price_row(same_day, 69), before):
        raise SystemExit('clock self-test failed: the decision-day close entered that day\'s feature')
    moved = closes.copy()
    moved[69] += 5.0
    if np.array_equal(price_row(moved, 69), before):
        raise SystemExit('clock self-test failed: the last input did not enter the feature')


def load_rows(path: Path) -> list[dict]:
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def load_base():
    sys.path.insert(0, str(CLOCK))
    import run as base
    return base


def sign(value: float) -> float:
    if value > 0:
        return 1.0
    if value < 0:
        return -1.0
    return 0.0


def mean(values: list[float]) -> float:
    if not values:
        raise SystemExit('mean of an empty sample')
    return float(sum(values) / len(values))


def corr(xs: list[float], ys: list[float]) -> float | None:
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    if len(x) < 3 or float(np.std(x)) < 1e-12 or float(np.std(y)) < 1e-12:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def assert_formula_matches_frozen_matrix(base, closes: np.ndarray) -> None:
    frozen = np.asarray(base.X['price'], dtype=float)
    if frozen.shape != (len(closes), 6):
        raise SystemExit(f'frozen price matrix shape {frozen.shape} is not {(len(closes), 6)}')
    for i in range(251, len(closes) - 1):
        got = price_row(closes, i)
        if not np.allclose(got, frozen[i + 1], atol=1e-8, rtol=0):
            raise SystemExit(f'price formula does not match label_clock_v4 X["price"] at last input {i}')
    if not np.isfinite(frozen[252:]).all():
        raise SystemExit('frozen price matrix has a non-finite value on or after session 252')
    leaked = closes.copy()
    leaked[1000] += 1.0
    if not np.array_equal(price_row(leaked, 999), price_row(closes, 999)):
        raise SystemExit('decision-day close changed the feature for that decision day')
    moved = closes.copy()
    moved[999] += 1.0
    if np.allclose(price_row(moved, 999), price_row(closes, 999), atol=1e-8, rtol=0):
        raise SystemExit('last-input close did not change the feature')
    prefix = base.make_features(base.C[:2500], base.A[:2500], base.S[:2500], 5)
    if not np.allclose(prefix['price'][252:2500], frozen[252:2500], atol=1e-8, rtol=0, equal_nan=True):
        raise SystemExit('price features failed the 2500-session prefix check')
    other = base.make_features(base.C, base.A, base.S, 9)
    if not np.allclose(other['price'], frozen, atol=1e-8, rtol=0, equal_nan=True):
        raise SystemExit('price block changed with scale; the frozen pipeline builds it once at scale 5')


def load_p1(base) -> tuple[dict, dict, dict, dict]:
    eligible: dict[str, dict[int, str]] = {task: {} for task in TASKS}
    region_counts: dict[str, dict[str, int]] = {task: defaultdict(int) for task in TASKS}
    for row in load_rows(P1 / 'eligible_days.csv'):
        task = row['task']
        if task not in eligible:
            raise SystemExit(f'unexpected task in eligible_days.csv: {task}')
        index = int(row['index'])
        if base.D[index] != row['date'] or base.pos[row['date']] != index:
            raise SystemExit(f'eligible day index does not match the research calendar: {task} {row["date"]}')
        if index in eligible[task]:
            raise SystemExit(f'duplicate eligible day {task} {row["date"]}')
        eligible[task][index] = row['region']
        region_counts[task][row['region']] += 1
    targets: dict[str, list[int]] = {task: [] for task in TASKS}
    seen: dict[str, set[int]] = {task: set() for task in TASKS}
    for row in load_rows(P1 / 'target_windows.csv'):
        task = row['task']
        if task not in targets:
            raise SystemExit(f'unexpected task in target_windows.csv: {task}')
        pivot = base.pos[row['pivot_date']]
        if base.D[pivot] != row['pivot_date']:
            raise SystemExit(f'pivot date is not on the research calendar: {row["pivot_date"]}')
        if pivot in seen[task]:
            raise SystemExit(f'duplicate pivot {task} {row["pivot_date"]}')
        seen[task].add(pivot)
        targets[task].append(pivot)
    for task in TASKS:
        targets[task].sort()
    scores: dict[str, dict[str, float]] = {task: {} for task in TASKS}
    last_input: dict[str, dict[str, str]] = {task: {} for task in TASKS}
    for row in load_rows(CLOCK / 'scores.csv'):
        if row['label'] != 'close' or row['group'] != 'price':
            continue
        task = row['task']
        if task not in scores:
            continue
        if row['date'] in scores[task]:
            raise SystemExit(f'duplicate close/price score {task} {row["date"]}')
        decision = base.pos[row['date']]
        if base.pos[row['last_input']] != decision - 1:
            raise SystemExit(f'score last_input is not D-1 on {task} {row["date"]}')
        scores[task][row['date']] = float(row['score'])
        last_input[task][row['date']] = row['last_input']
    for task, days in eligible.items():
        for index in days:
            date = base.D[index]
            if date not in scores[task]:
                raise SystemExit(f'eligible day has no close/price score: {task} {date}')
    return eligible, targets, scores, last_input


def assert_cohort(plan: dict, eligible: dict, targets: dict) -> None:
    lock = plan['cohort_lock']
    for task in TASKS:
        if len(targets[task]) != lock['targets'][task]:
            raise SystemExit(f'{task} target count {len(targets[task])} != P1 lock {lock["targets"][task]}')
        if len(eligible[task]) != lock['eligible_days'][task]:
            raise SystemExit(f'{task} eligible count {len(eligible[task])} != P1 lock {lock["eligible_days"][task]}')
        counts = defaultdict(int)
        for region in eligible[task].values():
            counts[region] += 1
        for region, expected in lock['regions'][task].items():
            if counts[region] != expected:
                raise SystemExit(f'{task} {region} count {counts[region]} != P1 lock {expected}')
    decision = json.loads((P1 / 'decision.json').read_text(encoding='utf-8'))
    if decision.get('decision') != lock['p1_decision']:
        raise SystemExit('P1 decision.json is not BLOCKED_NO_CONCENTRATION')
    if decision.get('formal_signal_allowed') is not False:
        raise SystemExit('P1 formal_signal_allowed is not false')
    contract = json.loads((ROOT / 'ACTIVE_RESEARCH_CONTRACT.json').read_text(encoding='utf-8'))
    window = contract['user_confirmed_window']
    if window['minimum_lead_sessions'] != 0 or window['maximum_lead_sessions'] != 6:
        raise SystemExit('active contract window is not D..D+6')


def assert_score_profile(base, plan_unused, eligible, targets, scores) -> float:
    published = {}
    for row in load_rows(P1 / 'lead_profile.csv'):
        published[(row['task'], int(row['offset']))] = (int(row['n']), float(row['mean_score']))
    max_diff = 0.0
    for task in TASKS:
        days = eligible[task]
        for offset in range(-13, 7):
            chosen = []
            for pivot in targets[task]:
                index = pivot + offset
                if index in days:
                    chosen.append(scores[task][base.D[index]])
            key = (task, offset)
            if key not in published:
                raise SystemExit(f'P1 lead profile missing {task} offset {offset}')
            n_pub, mean_pub = published[key]
            if len(chosen) != n_pub:
                raise SystemExit(f'score profile n mismatch {task} offset {offset}: {len(chosen)} != {n_pub}')
            got = mean(chosen) if chosen else None
            if got is None or abs(got - mean_pub) > 1e-8:
                raise SystemExit(f'score profile mean mismatch {task} offset {offset}: {got} != {mean_pub}')
            max_diff = max(max_diff, abs(got - mean_pub))
    return max_diff


def assert_clock(base, targets, last_input) -> None:
    for task in TASKS:
        for pivot in targets[task]:
            pivot_date = base.D[pivot]
            for offset in OFFSETS:
                decision = pivot + offset
                if decision <= 0 or decision >= base.N:
                    raise SystemExit(f'offset {offset} falls off the calendar for {task} {pivot_date}')
                last_index = decision - 1
                if (last_index == pivot) != (offset == 1):
                    raise SystemExit('offset +1 is not the unique offset whose last input is the pivot')
                if (last_index < pivot) != (offset <= 0):
                    raise SystemExit('hittable offsets are not exactly those whose last input is before the pivot')
                date = base.D[decision]
                if date in last_input[task] and last_input[task][date] != base.D[last_index]:
                    raise SystemExit(f'published last_input disagrees with the offset clock on {task} {date}')


def sample_counts(eligible: dict, targets: dict) -> dict:
    out = {}
    for task in TASKS:
        days = eligible[task]
        per_offset = {}
        for offset in OFFSETS:
            per_offset[offset] = sum(1 for pivot in targets[task] if pivot + offset in days)
        complete = [
            pivot for pivot in targets[task]
            if all(pivot + offset in days for offset in WINDOW + [1])
        ]
        plus2 = [pivot for pivot in complete if pivot + 2 in days]
        ordinary = [index for index, region in days.items() if region == 'ordinary']
        out[task] = {
            'per_offset': per_offset,
            'complete': complete,
            'plus2': plus2,
            'ordinary': ordinary,
        }
    return out


def sample_floor_failures(plan: dict, counts: dict) -> list[str]:
    floors = plan['tests']['sample_floors']
    failures = []
    for task in TASKS:
        item = counts[task]
        if len(item['complete']) < floors['complete_case_min']:
            failures.append(f'{task} complete_case {len(item["complete"])} < {floors["complete_case_min"]}')
        if len(item['ordinary']) < floors['ordinary_min']:
            failures.append(f'{task} ordinary {len(item["ordinary"])} < {floors["ordinary_min"]}')
        for offset in floors['offsets']:
            n = item['per_offset'][offset]
            if n < floors['per_offset_eligible_min']:
                failures.append(f'{task} offset {offset} n {n} < {floors["per_offset_eligible_min"]}')
    return failures


def evaluate(base, closes, eligible, targets, scores, counts) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    frozen = np.asarray(base.X['price'], dtype=float)
    lead_rows = []
    test_rows = []
    panel_rows = []
    hold_rows = []
    for task in TASKS:
        days = eligible[task]
        ordinary = counts[task]['ordinary']
        complete = counts[task]['complete']
        plus2 = counts[task]['plus2']
        ordinary_mu = []
        ordinary_sd = []
        ordinary_med = []
        for feature_index in range(6):
            column = frozen[np.asarray(ordinary, dtype=int), feature_index]
            sd = float(np.std(column, ddof=1))
            if sd < 1e-6:
                raise SystemExit(f'ordinary std below 1e-6 for {task} {FEATURES[feature_index]}')
            ordinary_mu.append(float(np.mean(column)))
            ordinary_sd.append(sd)
            ordinary_med.append(float(np.median(column)))
        values = {offset: [] for offset in OFFSETS}
        score_values = {offset: [] for offset in OFFSETS}
        for pivot in targets[task]:
            pivot_date = base.D[pivot]
            in_complete = pivot in complete
            for offset in OFFSETS:
                decision = pivot + offset
                eligible_day = decision in days
                row = {
                    'task': task,
                    'pivot_date': pivot_date,
                    'offset': offset,
                    'decision_date': base.D[decision],
                    'last_input_date': base.D[decision - 1],
                    'in_hittable_window': -6 <= offset <= 0,
                    'last_input_is_pivot_close': offset == 1,
                    'eligible': eligible_day,
                    'complete_case': in_complete,
                    'score': scores[task][base.D[decision]] if eligible_day else None,
                }
                for feature_index, name in enumerate(FEATURES):
                    row[name] = float(frozen[decision, feature_index]) if eligible_day else None
                panel_rows.append(row)
                if eligible_day:
                    values[offset].append(frozen[decision].copy())
                    score_values[offset].append(scores[task][base.D[decision]])
        complete_values = {offset: [] for offset in WINDOW + [1]}
        plus2_values = []
        jumps = []
        score_steps = []
        feature_steps = []
        for pivot in complete:
            for offset in WINDOW + [1]:
                complete_values[offset].append(frozen[pivot + offset].copy())
            if pivot in plus2:
                plus2_values.append(frozen[pivot + 2].copy())
            held_closes = closes.copy()
            held_closes[pivot] = held_closes[pivot - 1]
            held = price_row(held_closes, pivot)
            actual = frozen[pivot + 1]
            if not np.allclose(actual, price_row(closes, pivot), atol=1e-8, rtol=0):
                raise SystemExit(f'offset +1 row is not the formula at the pivot close on {task} {base.D[pivot]}')
            jump = actual - held
            jumps.append(jump)
            score_steps.append(scores[task][base.D[pivot + 1]] - scores[task][base.D[pivot]])
            feature_steps.append(actual - frozen[pivot])
            for feature_index, name in enumerate(FEATURES):
                hold_rows.append({
                    'task': task,
                    'pivot_date': base.D[pivot],
                    'feature': name,
                    'actual': float(actual[feature_index]),
                    'held': float(held[feature_index]),
                    'jump': float(jump[feature_index]),
                })
        jumps_arr = np.vstack(jumps)
        complete_arr = {offset: np.vstack(complete_values[offset]) for offset in WINDOW + [1]}
        window_mean = np.mean(np.stack([complete_arr[offset] for offset in WINDOW], axis=0), axis=0)
        z_complete = {}
        for offset, arr in complete_arr.items():
            z_complete[offset] = (arr.mean(axis=0) - np.asarray(ordinary_mu)) / np.asarray(ordinary_sd)
        z_from_offsets = np.mean(np.vstack([z_complete[offset] for offset in WINDOW]), axis=0)
        z_win = (window_mean.mean(axis=0) - np.asarray(ordinary_mu)) / np.asarray(ordinary_sd)
        if not np.allclose(z_win, z_from_offsets, atol=1e-9, rtol=0):
            raise SystemExit(f'window z is not the mean of offset z on {task}')
        z_jump = jumps_arr.mean(axis=0) / np.asarray(ordinary_sd)
        z_held = z_complete[1] - z_jump
        if not np.allclose(z_jump, z_complete[1] - z_held, atol=1e-9, rtol=0):
            raise SystemExit(f'jump identity failed on {task}')
        z_early = np.mean(np.vstack([z_complete[offset] for offset in (-6, -5, -4)]), axis=0)
        z_late = np.mean(np.vstack([z_complete[offset] for offset in (-2, -1, 0)]), axis=0)
        z_plus2 = None
        if plus2_values:
            z_plus2 = (np.vstack(plus2_values).mean(axis=0) - np.asarray(ordinary_mu)) / np.asarray(ordinary_sd)
        for feature_index, name in enumerate(FEATURES):
            for sample_name, bag in (('all_eligible', values), ('complete', complete_values)):
                offsets = OFFSETS if sample_name == 'all_eligible' else WINDOW + [1]
                for offset in offsets:
                    column = [row[feature_index] for row in bag[offset]] if sample_name == 'all_eligible' else bag[offset][:, feature_index].tolist()
                    mu = mean(column)
                    lead_rows.append({
                        'task': task,
                        'feature': name,
                        'offset': offset,
                        'sample': sample_name,
                        'n': len(column),
                        'mean': mu,
                        'median': float(np.median(np.asarray(column, dtype=float))),
                        'z': (mu - ordinary_mu[feature_index]) / ordinary_sd[feature_index],
                        'in_hittable_window': -6 <= offset <= 0,
                        'last_input_is_pivot_close': offset == 1,
                    })
            if z_plus2 is not None:
                column = np.vstack(plus2_values)[:, feature_index]
                mu = float(column.mean())
                lead_rows.append({
                    'task': task,
                    'feature': name,
                    'offset': 2,
                    'sample': 'complete_plus2',
                    'n': int(column.shape[0]),
                    'mean': mu,
                    'median': float(np.median(column)),
                    'z': float(z_plus2[feature_index]),
                    'in_hittable_window': False,
                    'last_input_is_pivot_close': False,
                })
            z = {offset: float(z_complete[offset][feature_index]) for offset in WINDOW + [1]}
            z2 = None if z_plus2 is None else float(z_plus2[feature_index])
            den = z[1] - z[-6]
            path_fraction = None if abs(den) < 1e-12 else (z[0] - z[-6]) / den
            anchor = sign(z[1])
            median_0 = float(np.median(complete_arr[0][:, feature_index]))
            side_0 = [
                1.0 if anchor * (value - ordinary_med[feature_index]) > 0 else 0.0
                for value in complete_arr[0][:, feature_index]
            ]
            side_1 = [
                1.0 if anchor * (value - ordinary_med[feature_index]) > 0 else 0.0
                for value in complete_arr[1][:, feature_index]
            ]
            steps = [float(row[feature_index]) for row in feature_steps]
            jump_list = [float(row[feature_index]) for row in jumps_arr]
            economic = ECONOMIC_SIGN[task][name]
            all_z = {}
            for offset in WINDOW + [1]:
                column = [row[feature_index] for row in values[offset]]
                all_z[offset] = (mean(column) - ordinary_mu[feature_index]) / ordinary_sd[feature_index]
            test_rows.append({
                'task': task,
                'feature': name,
                'complete_n': len(complete),
                'plus2_n': len(plus2),
                'ordinary_n': len(ordinary),
                'ordinary_mean': ordinary_mu[feature_index],
                'ordinary_std': ordinary_sd[feature_index],
                'ordinary_median': ordinary_med[feature_index],
                'z_m6': z[-6],
                'z_m5': z[-5],
                'z_m4': z[-4],
                'z_m3': z[-3],
                'z_m2': z[-2],
                'z_m1': z[-1],
                'z_0': z[0],
                'z_p1': z[1],
                'z_p2': z2,
                'z_win': float(z_win[feature_index]),
                'z_early': float(z_early[feature_index]),
                'z_late': float(z_late[feature_index]),
                'z_jump': float(z_jump[feature_index]),
                'z_held': float(z_held[feature_index]),
                'aging': float(z_held[feature_index] - z[0]),
                'build': float(z_late[feature_index] - z_early[feature_index]),
                'path_fraction': path_fraction,
                'median_0': median_0,
                'share_offset0_on_anchor_side': mean(side_0) if anchor else None,
                'share_plus1_on_anchor_side': mean(side_1) if anchor else None,
                'score_step_corr': corr(score_steps, steps),
                'jump_score_corr': corr(score_steps, jump_list),
                'economic_sign': economic,
                'plus1_matches_economic_sign': bool(anchor != 0 and anchor == economic),
                'all_eligible_n_m6': counts[task]['per_offset'][-6],
                'all_eligible_n_0': counts[task]['per_offset'][0],
                'all_eligible_n_p1': counts[task]['per_offset'][1],
                'max_abs_z_gap_complete_vs_all': max(abs(z[offset] - all_z[offset]) for offset in WINDOW + [1]),
                'z_map': z,
                'median_gap': median_0 - ordinary_med[feature_index],
            })
    return lead_rows, test_rows, panel_rows, hold_rows


def apply_tests(plan: dict, rows: list[dict]) -> None:
    presence = plan['tests']['presence']
    build = plan['tests']['build']
    for row in rows:
        z = row['z_map']
        anchor = sign(row['z_p1'])
        reasons = []
        anchor_ok = abs(row['z_p1']) >= presence['requires_abs_z_plus1_min'] and anchor != 0
        if not anchor_ok:
            reasons.append('plus1_anchor_below_0.25')
        same_window = anchor * row['z_win']
        same_0 = anchor * row['z_0']
        same_jump = anchor * row['z_jump']
        n_side = sum(1 for offset in presence['window_offsets'] if anchor * z[offset] >= presence['offset_z_floor'])
        median_ok = anchor * row['median_gap'] > 0
        checks = {
            'window_level': same_window >= presence['same_sign_window_min'],
            'window_majority_of_plus1': same_window > presence['window_over_abs_plus1_min'] * abs(row['z_p1']),
            'offset0_level': same_0 >= presence['same_sign_offset0_min'],
            'window_exceeds_half_jump': same_window > presence['window_over_same_sign_jump_min'] * same_jump,
            'median': median_ok,
            'four_offsets': n_side >= presence['min_offsets'],
        }
        if anchor_ok:
            for name, passed in checks.items():
                if not passed:
                    reasons.append(name)
        row['offsets_on_anchor_side'] = n_side
        row['pass_presence'] = bool(anchor_ok and all(checks.values()))
        build_sign = sign(row['build'])
        build_checks = {
            'abs_build': abs(row['build']) >= build['abs_late_minus_early_min'],
            'exceeds_jump': abs(row['build']) > abs(row['z_jump']),
            'exceeds_plus1_step': abs(row['build']) > abs(row['z_p1'] - row['z_0']),
            'late_level': abs(row['z_late']) >= build['abs_late_min'],
            'build_sign': build_sign != 0,
            'median': build_sign * row['median_gap'] > 0,
        }
        row['pass_build'] = bool(all(build_checks.values()))
        if not row['pass_build']:
            row['build_fail_reasons'] = [name for name, passed in build_checks.items() if not passed]
        else:
            row['build_fail_reasons'] = []
        row['presence_fail_reasons'] = reasons
        dominance = plan['tests']['blocked_pivot_close']
        row['jump_dominates'] = bool(
            abs(row['z_jump']) >= dominance['jump_abs_min'] and abs(row['z_jump']) > abs(row['z_win'])
        )
        row['plus1_level_dominates'] = bool(
            abs(row['z_p1']) >= dominance['plus1_abs_min']
            and abs(row['z_p1']) > abs(row['z_win'])
            and abs(row['z_p1']) > abs(row['z_0'])
        )


def decide(plan: dict, rows: list[dict], floor_failures: list[str]) -> dict:
    go_rule = plan['tests']['go']
    presence_hits = defaultdict(list)
    build_hits = defaultdict(list)
    single_hits = []
    for row in rows:
        if row['pass_presence']:
            presence_hits[row['feature']].append(row['task'])
        if row['pass_build']:
            build_hits[row['feature']].append(row['task'])
        if row['pass_presence'] and row['pass_build'] and abs(row['z_win']) >= go_rule['single_task_abs_z_win_min']:
            single_hits.append({'feature': row['feature'], 'task': row['task'], 'z_win': row['z_win']})
    presence_go = [
        {'feature': feature, 'tasks': tasks}
        for feature, tasks in presence_hits.items()
        if len(tasks) >= go_rule['presence_on_at_least_n_tasks']
    ]
    build_go = [
        {'feature': feature, 'tasks': tasks}
        for feature, tasks in build_hits.items()
        if len(tasks) >= go_rule['build_on_at_least_n_tasks']
    ]
    go = bool(presence_go or build_go or single_hits)
    if floor_failures:
        code = 'BLOCKED_INSUFFICIENT_SAMPLE'
    elif go:
        code = 'GO_PRE_PIVOT_COORDINATE'
    elif any(row['jump_dominates'] or row['plus1_level_dominates'] for row in rows):
        code = 'BLOCKED_PIVOT_CLOSE_DOMINATED'
    else:
        code = 'BLOCKED_NO_MARGINAL_MOVE'
    return {
        'decision': code,
        'go': code.startswith('GO'),
        'blocked': code.startswith('BLOCKED'),
        'formal_signal_allowed': False,
        'presence_go': presence_go,
        'build_go': build_go,
        'single_task_go': single_hits,
        'presence_hits': dict(presence_hits),
        'build_hits': dict(build_hits),
        'sample_floor_failures': floor_failures,
        'n_pass_presence': sum(row['pass_presence'] for row in rows),
        'n_pass_build': sum(row['pass_build'] for row in rows),
        'n_jump_dominates': sum(row['jump_dominates'] for row in rows),
        'n_plus1_level_dominates': sum(row['plus1_level_dominates'] for row in rows),
    }


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
            writer.writerow({key: cell(row.get(key)) for key in fields})


def fmt(value, digits: int = 3) -> str:
    if value is None:
        return '—'
    return f'{value:.{digits}f}'


def pct(value) -> str:
    if value is None:
        return '—'
    return f'{100 * value:.1f}%'


def extremum(rows: list[dict], key: str) -> dict:
    return max(rows, key=lambda row: abs(row[key]))


def decision_paragraphs(rows: list[dict], decision: dict, counts: dict) -> tuple[str, str]:
    code = decision['decision']
    jump = extremum(rows, 'z_jump')
    window = extremum(rows, 'z_win')
    plus = extremum(rows, 'z_p1')
    n_text = ', '.join(
        f"{task} {len(counts[task]['complete'])} complete of {counts[task]['per_offset'][0]} eligible at offset 0"
        for task in TASKS
    )
    named = []
    for item in decision['presence_go']:
        named.append(f"{item['feature']} presence on {', '.join(item['tasks'])}")
    for item in decision['build_go']:
        named.append(f"{item['feature']} build on {', '.join(item['tasks'])}")
    for item in decision['single_task_go']:
        named.append(f"{item['feature']} both tests on {item['task']}")
    named_text = '; '.join(named) if named else 'none'
    jump_cell = f"{jump['task']} {jump['feature']} isolated jump {jump['z_jump']:+.3f} ordinary SD"
    window_cell = f"{window['task']} {window['feature']} window departure {window['z_win']:+.3f} ordinary SD"
    plus_cell = f"{plus['task']} {plus['feature']} offset +1 departure {plus['z_p1']:+.3f} ordinary SD"
    passes = f"presence passes {decision['n_pass_presence']} of 24 cells; build passes {decision['n_pass_build']} of 24"
    if code == 'GO_PRE_PIVOT_COORDINATE':
        english = (
            f"GO. A pre-pivot coordinate clears the frozen tests. {named_text}. {passes}. "
            f"Largest absolute window departure: {window_cell}. Largest absolute isolated pivot-close jump: {jump_cell}. "
            f"Samples: {n_text}. A later experiment may pre-register only those feature-task cells. "
            "The six-feature model stays unfitted. Phase P2 alert compression stays closed. "
            "The threshold stays unsearched. formal_signal_allowed stays false. "
            "This is not PIT, not a blind test, and not a signal. P1 remains BLOCKED_NO_CONCENTRATION."
        )
        chinese = (
            f"放行。有拐点收盘进入特征之前就已经移动、并且通过冻结检验的坐标。{named_text}。{passes}。"
            f"窗口偏离绝对值最大的一格：{window_cell}。孤立拐点收盘跳跃绝对值最大的一格：{jump_cell}。"
            f"样本：{n_text}。后续实验只可预注册这些特征与任务。六个价格特征的模型保持不重训。"
            "P2 发报压缩保持关闭。阈值保持不搜索。formal_signal_allowed 仍为 false。"
            "这不是 PIT，不是盲测，也不是信号。P1 仍是 BLOCKED_NO_CONCENTRATION。"
        )
    elif code == 'BLOCKED_PIVOT_CLOSE_DOMINATED':
        english = (
            f"BLOCKED. No frozen price feature clears the pre-pivot tests. {passes}. "
            f"The marginal move is dominated by offset +1, the first decision day whose last input is the pivot close. "
            f"Largest absolute isolated pivot-close jump: {jump_cell}. Largest absolute offset-+1 departure: {plus_cell}. "
            f"Largest absolute window departure: {window_cell}. Samples: {n_text}. "
            f"Cells whose isolated jump exceeds the window departure: {decision['n_jump_dominates']}. "
            f"Cells whose offset-+1 level is farther from ordinary than both the window and offset 0: {decision['n_plus1_level_dominates']}. "
            "Stay blocked at the feature layer. These six inputs do not supply a hittable coordinate that is already present before the pivot close. "
            "Phase P2 alert compression stays closed. Raising the threshold stays unsupported, because P1 already showed the score peak on the session that cannot hit the pivot. "
            "A different information set would be a new proposal. formal_signal_allowed stays false. "
            "This is not PIT, not a blind test, and not a signal. P1 remains BLOCKED_NO_CONCENTRATION."
        )
        chinese = (
            f"阻断。六个冻结价格特征没有一格通过拐点前检验。{passes}。"
            "边际移动由偏移 +1 主导。这一天的最后输入才是拐点收盘，当天发出的警报已经打不中该拐点。"
            f"孤立拐点收盘跳跃绝对值最大的一格：{jump_cell}。偏移 +1 偏离绝对值最大的一格：{plus_cell}。"
            f"窗口偏离绝对值最大的一格：{window_cell}。样本：{n_text}。"
            f"孤立跳跃大于窗口偏离的格子：{decision['n_jump_dominates']}。"
            f"偏移 +1 的水平比窗口和偏移 0 都更远离普通日的格子：{decision['n_plus1_level_dominates']}。"
            "停在特征层。这六个输入在拐点收盘进入之前，没有已经可用、且达到预注册幅度的可命中坐标。"
            "P2 发报压缩保持关闭。只提高阈值仍然没有依据，因为 P1 已经表明分数峰值落在打不中该拐点的那一天。"
            "另一套信息要另案提出。formal_signal_allowed 仍为 false。这不是 PIT，不是盲测，也不是信号。P1 仍是 BLOCKED_NO_CONCENTRATION。"
        )
    elif code == 'BLOCKED_NO_MARGINAL_MOVE':
        english = (
            f"BLOCKED. No frozen price feature clears the pre-pivot tests, and no cell shows a material marginal jump isolated at offset +1 either. {passes}. "
            f"Largest absolute window departure: {window_cell}. Largest absolute isolated jump: {jump_cell}. Largest absolute offset-+1 departure: {plus_cell}. "
            f"Samples: {n_text}. The P1 score peak at offset +1 is not a single-feature level shift in these six inputs. "
            "Stay blocked at the feature layer. Phase P2 stays closed. This audit does not fit a combination. "
            "formal_signal_allowed stays false. P1 remains BLOCKED_NO_CONCENTRATION."
        )
        chinese = (
            f"阻断。六个冻结价格特征没有通过拐点前检验，也没有格子在偏移 +1 出现达到预注册幅度的边际跳跃。{passes}。"
            f"窗口偏离绝对值最大的一格：{window_cell}。孤立跳跃绝对值最大的一格：{jump_cell}。偏移 +1 偏离绝对值最大的一格：{plus_cell}。"
            f"样本：{n_text}。P1 的分数峰值不是这六个输入里某一个特征的水平移动。"
            "停在特征层。P2 保持关闭。本审计不拟合特征组合。formal_signal_allowed 仍为 false。P1 仍是 BLOCKED_NO_CONCENTRATION。"
        )
    else:
        english = (
            "BLOCKED. The complete-case sample does not meet the pre-registered floor: "
            + '; '.join(decision['sample_floor_failures'])
            + ". No coordinate is declared. formal_signal_allowed stays false."
        )
        chinese = (
            "阻断。完整样本没有达到预注册下限："
            + '；'.join(decision['sample_floor_failures'])
            + "。不宣布坐标。formal_signal_allowed 仍为 false。"
        )
    return english, chinese


def render_report(rows: list[dict], decision: dict, counts: dict, score_diff: float) -> str:
    english, chinese = decision_paragraphs(rows, decision, counts)
    lines = [
        '# P1b 六个价格特征在拐点收盘之前有没有移动',
        '',
        f"**Decision: `{decision['decision']}`.** {english}",
        '',
        f"**结论：`{decision['decision']}`。** {chinese}",
        '',
        '这是冻结基线的特征时点审计，不是新模型，不是发报实验。`formal_signal_allowed` 仍为 false。没有 PIT 认证，没有盲测，没有生产信号。P1 的 `BLOCKED_NO_CONCENTRATION` 不改写。',
        '',
        '## 冻结与时钟',
        '',
        '标签 close，特征 price，指数 000985.CSI，决策时钟为 D 日开盘前。特征行用到的最后收盘是 D−1。六个特征沿用 `label_clock_v4` 已经算好的价格矩阵，公式与 `broad_experiments_v2` 的 `make_features` 价格块一致，审计开始前用逐行比对锁住。不重训，不搜索阈值，不新增因子。',
        '',
        '| 偏移 | 决策日 | 最后输入 | 能否打中该拐点 |',
        '|---:|---|---|---|',
        '| −6..0 | 拐点前 6 日至拐点当天 | 拐点前 7 日至拐点前 1 日 | 能。窗口内。 |',
        '| +1 | 拐点后第 1 日 | 拐点当天收盘 | 不能。拐点收盘第一次进入特征。 |',
        '| +2 | 拐点后第 2 日 | 拐点后第 1 日收盘 | 不能。肩部，只报告。 |',
        '',
        '普通日沿用 P1 的 ordinary 区域。z 是该任务普通日上的标准差单位，中心是普通日均值。检验只用完整样本：同一批拐点在 −6..+1 每天都可评分。对照“把拐点收盘换成前一日收盘”只用同一套公式，不产生分数。',
        '',
        '## 检验',
        '',
        '检验 P（存在）：偏移 +1 相对普通日的偏离至少 0.25 个标准差时，才有一个可解释的锚。窗口均值要与这个锚同号，绝对值至少 0.20，并且超过锚的一半；偏移 0 同号且至少 0.15；窗口均值还要超过孤立拐点收盘跳跃的一半；偏移 0 的中位数要严格落在锚的一侧；七个窗口偏移里至少四个的同号 z 达到 0.10。',
        '',
        '检验 B（推移）：窗口后段（−2..0）减去前段（−6..−4）的绝对值至少 0.35，并且大于孤立跳跃，也大于从偏移 0 到 +1 的一步；后段本身离开普通日至少 0.20；偏移 0 的中位数落在推移方向上。',
        '',
        '放行条件：同一特征在至少两个任务上通过检验 P，或在至少两个任务上通过检验 B，或在一个任务上两个检验都通过且窗口偏离的绝对值至少 0.50。否则，若有格子的孤立跳跃或偏移 +1 水平按预注册规则盖过窗口，结论是拐点收盘主导；都没有，则是没有边际移动。经济方向只作对照列，不参与判定。',
        '',
        '## 结果',
        '',
        'z 为完整样本上的普通日标准差单位。窗口是 −6..0 的平均。跳跃是把拐点收盘换成前一日收盘之后，偏移 +1 的变化。推移是窗口后段减前段。',
        '',
        '| 任务 | 特征 | n | z(−6) | z(0) | z(+1) | z(+2) | 窗口 | 跳跃 | 推移 | 检验P | 检验B |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|',
    ]
    for row in rows:
        lines.append(
            '| {task} | {feature} | {n} | {m6} | {z0} | {p1} | {p2} | {win} | {jump} | {build} | {p} | {b} |'.format(
                task=row['task'],
                feature=row['feature'],
                n=row['complete_n'],
                m6=fmt(row['z_m6']),
                z0=fmt(row['z_0']),
                p1=fmt(row['z_p1']),
                p2=fmt(row['z_p2']),
                win=fmt(row['z_win']),
                jump=fmt(row['z_jump']),
                build=fmt(row['build']),
                p='PASS' if row['pass_presence'] else 'FAIL',
                b='PASS' if row['pass_build'] else 'FAIL',
            )
        )
    lines.extend([
        '',
        '| 任务 | 完整样本 | 偏移0可评分拐点 | 偏移+2 | 普通日 |',
        '|---|---:|---:|---:|---:|',
    ])
    for task in TASKS:
        item = counts[task]
        lines.append(
            f"| {task} | {len(item['complete'])} | {item['per_offset'][0]} | {len(item['plus2'])} | {len(item['ordinary'])} |"
        )
    lines.extend([
        '',
        '特征名称：`return3_scaled` 3日收益，`return20_scaled` 20日收益，`change_in_return3_scaled` 3日收益变化，`distance_to_20day_high_scaled` 距20日高点（小于等于 0），`distance_to_20day_low_scaled` 距20日低点（大于等于 0），`position63` 在 63 日高低区间的位置。',
        '',
        '图：`fig_feature_lead.png` 是六个特征在 −6..+2 的路径，绿色带是可命中窗口，橙色点是偏移 +1，空心点是扣掉拐点收盘后的偏移 +1。`fig_window_vs_plus1.png` 比较窗口、偏移 +1 和孤立跳跃。`fig_hold_last_close.png` 把偏移 0、扣掉拐点收盘的 +1、以及真实 +1 放在一起。',
        '',
        '## 对照，不是门槛',
        '',
        '下表的路径比例是 (z(0)−z(−6)) / (z(+1)−z(−6))。比例接近 0 表示偏移 0 还停在窗口起点；接近 1 表示走到 +1 之前，这段位移已经完成。分数相关是完整样本上，偏移 +1 的分数减去偏移 0 的分数，与特征的同一步变化或孤立跳跃的 Pearson 相关。相关不用来判定。',
        '',
        '| 任务 | 特征 | 路径比例 | 老化 | 锚侧占比@0 | 锚侧占比@+1 | 分数步相关 | 跳跃与分数相关 | 经济方向与+1一致 |',
        '|---|---|---:|---:|---:|---:|---:|---:|---|',
    ])
    for row in rows:
        lines.append(
            '| {task} | {feature} | {path} | {aging} | {s0} | {s1} | {c1} | {c2} | {econ} |'.format(
                task=row['task'],
                feature=row['feature'],
                path=fmt(row['path_fraction']),
                aging=fmt(row['aging']),
                s0=pct(row['share_offset0_on_anchor_side']),
                s1=pct(row['share_plus1_on_anchor_side']),
                c1=fmt(row['score_step_corr']),
                c2=fmt(row['jump_score_corr']),
                econ='是' if row['plus1_matches_economic_sign'] else '否',
            )
        )
    lines.extend([
        '',
        '经济方向是计划里事先写下的：顶部预期 3 日和 20 日收益为正、3 日收益变化为负、更接近 20 日高点、远离 20 日低点、63 日位置更高；底部相反。它不翻转任何一格的通过与否。',
        '',
        '## 与 P1 分数的对齐',
        '',
        f'用 P1 的可评分日和目标，重算了 `lead_profile.csv` 里 −13..+6 的平均分数。最大绝对差是 {score_diff:.3e}。偏移 +1 的分数高于偏移 0 这一事实沿用 P1，不在这里重新判定。扣掉最新收盘之后的分数，就是已经发表的偏移 0 分数；本审计没有系数，不能在不重训的前提下改写逻辑回归。',
        '',
        '## 边界',
        '',
        '- 决策日重叠，特征自相关。门槛是描述规则，不是独立样本的显著性检验。',
        '- 拐点是事后确认的收盘标签。这是时点审计，不是可交易信号。',
        '- 历史被反复看过，不是新的盲测。历史公布时点与指数成分仍未完成全时期 PIT 认证。',
        '- 没有把 D 日收盘写进当日特征。偏移 0 的最后输入是拐点前一日。',
        '- 没有修改生产页面、采集器、正式信号，也没有恢复旧 V 系列。',
        '- 没有把未来目标数当作配额。双80仍未达到。',
        '',
        '## 复算',
        '',
        '```text',
        'python -B dual80-research/p1b_feature_timing/diagnose.py',
        '```',
        '',
        '缺少 `plan.json` 时测量会停止。`--write-plan-only` 只在文件不存在时写出计划，不读特征路径。',
        '',
    ])
    return '\n'.join(lines)


def save_figures(rows: list[dict], lead_rows: list[dict]) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    by_lead = {}
    for row in lead_rows:
        by_lead[(row['task'], row['feature'], row['sample'], row['offset'])] = row
    by_test = {(row['task'], row['feature']): row for row in rows}

    fig, axes = plt.subplots(6, 4, figsize=(12.8, 14.6), sharex=True, sharey='row')
    for row_index, feature in enumerate(FEATURES):
        for col, task in enumerate(TASKS):
            ax = axes[row_index, col]
            ax.axvspan(-6.5, 0.5, color='#d9ead3', zorder=0)
            ax.axvspan(0.5, 2.5, color='#fce5cd', zorder=0)
            ax.axhline(0, color='#666666', lw=0.6)
            xs, ys, colors = [], [], []
            for offset in OFFSETS:
                sample = 'complete' if offset < 2 else 'complete_plus2'
                item = by_lead.get((task, feature, sample, offset))
                if item is None:
                    continue
                xs.append(offset)
                ys.append(item['z'])
                if -6 <= offset <= 0:
                    colors.append('#2c7fb8')
                elif offset == 1:
                    colors.append('#d95f0e')
                else:
                    colors.append('#756bb1')
            ax.plot(xs, ys, color='#333333', lw=1, zorder=2)
            ax.scatter(xs, ys, c=colors, s=22, zorder=3)
            held = by_test[(task, feature)]['z_held']
            ax.scatter([1], [held], facecolors='none', edgecolors='black', s=46, zorder=4)
            if col == 0:
                ax.set_ylabel(SHORT[feature])
            if row_index == 0:
                ax.set_title(task)
            ax.set_xticks(OFFSETS)
            ax.grid(axis='y', alpha=0.25)
    fig.suptitle(
        'Frozen price features around close pivots. Green band: hittable offsets -6..0. '
        'Orange point: offset +1, first day whose last input is the pivot close. '
        'Open circle: offset +1 with the pivot close replaced by the previous close.',
        fontsize=10,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(HERE / 'fig_feature_lead.png', dpi=140)
    plt.close(fig)

    fig, axes = plt.subplots(1, 4, figsize=(13.2, 5.6), sharey=True)
    y = np.arange(len(FEATURES))
    height = 0.24
    for ax, task in zip(axes, TASKS):
        task_rows = [by_test[(task, feature)] for feature in FEATURES]
        ax.axvline(0, color='#666666', lw=0.6)
        ax.barh(y - height, [row['z_win'] for row in task_rows], height=height, color='#2c7fb8', label='window -6..0')
        ax.barh(y, [row['z_p1'] for row in task_rows], height=height, color='#d95f0e', label='offset +1')
        ax.barh(y + height, [row['z_jump'] for row in task_rows], height=height, color='#7f2704', label='pivot-close jump')
        labels = []
        for row in task_rows:
            mark = ''
            if row['pass_presence']:
                mark += ' P'
            if row['pass_build']:
                mark += ' B'
            labels.append(SHORT[row['feature']] + mark)
        ax.set_yticks(y, labels)
        ax.set_title(f"{task} n={task_rows[0]['complete_n']}")
        ax.grid(axis='x', alpha=0.25)
    axes[0].legend(loc='lower right', fontsize=8)
    fig.suptitle('Window level, offset +1, and the isolated pivot-close jump, in ordinary standard deviations')
    fig.tight_layout()
    fig.savefig(HERE / 'fig_window_vs_plus1.png', dpi=140)
    plt.close(fig)

    fig, axes = plt.subplots(1, 4, figsize=(13.2, 5.6), sharey=True)
    for ax, task in zip(axes, TASKS):
        task_rows = [by_test[(task, feature)] for feature in FEATURES]
        ax.axvline(0, color='#666666', lw=0.6)
        ax.barh(y - height, [row['z_0'] for row in task_rows], height=height, color='#2c7fb8', label='offset 0')
        ax.barh(y, [row['z_held'] for row in task_rows], height=height, color='#f5f5f5', edgecolor='black', label='+1 with pivot close held out')
        ax.barh(y + height, [row['z_p1'] for row in task_rows], height=height, color='#d95f0e', label='offset +1 actual')
        ax.set_yticks(y, [SHORT[feature] for feature in FEATURES])
        ax.set_title(task)
        ax.grid(axis='x', alpha=0.25)
    axes[0].legend(loc='lower right', fontsize=8)
    fig.suptitle('Holding out the pivot close at the offset-+1 decision')
    fig.tight_layout()
    fig.savefig(HERE / 'fig_hold_last_close.png', dpi=140)
    plt.close(fig)


def write_artifact_manifest() -> None:
    files = sorted(p for p in HERE.iterdir() if p.is_file() and p.name != 'artifact_manifest.json')
    manifest = {path.name: {'bytes': path.stat().st_size, 'sha256': sha256_file(path)} for path in files}
    (HERE / 'artifact_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def write_outputs(rows, lead_rows, panel_rows, hold_rows, decision, counts, score_diff, plan_sha) -> None:
    public_rows = []
    for row in rows:
        item = dict(row)
        item.pop('z_map', None)
        item.pop('median_gap', None)
        item['presence_fail_reasons'] = ','.join(row['presence_fail_reasons'])
        item['build_fail_reasons'] = ','.join(row['build_fail_reasons'])
        public_rows.append(item)
    result = {
        'phase': 'P1b',
        'decision': decision['decision'],
        'formal_signal_allowed': False,
        'blind_test': False,
        'PIT_certified': False,
        'production_changed': False,
        'refit': False,
        'p2_alert_compression': False,
        'plan_sha256': plan_sha,
        'p1_decision': 'BLOCKED_NO_CONCENTRATION',
        'score_profile_max_abs_diff': score_diff,
        'summary': {key: decision[key] for key in (
            'go', 'blocked', 'presence_go', 'build_go', 'single_task_go', 'presence_hits', 'build_hits',
            'sample_floor_failures', 'n_pass_presence', 'n_pass_build', 'n_jump_dominates', 'n_plus1_level_dominates',
        )},
        'samples': {
            task: {
                'complete_n': len(item['complete']),
                'plus2_n': len(item['plus2']),
                'ordinary_n': len(item['ordinary']),
                'per_offset_n': {str(offset): item['per_offset'][offset] for offset in OFFSETS},
            }
            for task, item in counts.items()
        },
        'tests': public_rows,
    }
    (HERE / 'result.json').write_text(json.dumps(plain(result), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    english, chinese = decision_paragraphs(rows, decision, counts)
    (HERE / 'decision.json').write_text(json.dumps(plain({
        'decision': decision['decision'],
        'formal_signal_allowed': False,
        'blind_test': False,
        'PIT_certified': False,
        'production_changed': False,
        'refit': False,
        'p2_opened': False,
        'english': english,
        'chinese': chinese,
        'presence_go': decision['presence_go'],
        'build_go': decision['build_go'],
        'single_task_go': decision['single_task_go'],
        'n_pass_presence': decision['n_pass_presence'],
        'n_pass_build': decision['n_pass_build'],
    }), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (HERE / 'README.md').write_text(render_report(rows, decision, counts, score_diff), encoding='utf-8')
    test_fields = [
        'task', 'feature', 'complete_n', 'plus2_n', 'ordinary_n', 'ordinary_mean', 'ordinary_std', 'ordinary_median',
        'z_m6', 'z_m5', 'z_m4', 'z_m3', 'z_m2', 'z_m1', 'z_0', 'z_p1', 'z_p2',
        'z_win', 'z_early', 'z_late', 'z_jump', 'z_held', 'aging', 'build', 'path_fraction',
        'median_0', 'offsets_on_anchor_side', 'share_offset0_on_anchor_side', 'share_plus1_on_anchor_side',
        'pass_presence', 'pass_build', 'presence_fail_reasons', 'build_fail_reasons',
        'jump_dominates', 'plus1_level_dominates', 'score_step_corr', 'jump_score_corr',
        'economic_sign', 'plus1_matches_economic_sign',
        'all_eligible_n_m6', 'all_eligible_n_0', 'all_eligible_n_p1', 'max_abs_z_gap_complete_vs_all',
    ]
    write_csv(HERE / 'feature_tests.csv', public_rows, test_fields)
    write_csv(HERE / 'feature_lead.csv', lead_rows, [
        'task', 'feature', 'offset', 'sample', 'n', 'mean', 'median', 'z',
        'in_hittable_window', 'last_input_is_pivot_close',
    ])
    write_csv(HERE / 'pivot_offsets.csv', panel_rows, [
        'task', 'pivot_date', 'offset', 'decision_date', 'last_input_date',
        'in_hittable_window', 'last_input_is_pivot_close', 'eligible', 'complete_case', 'score', *FEATURES,
    ])
    write_csv(HERE / 'hold_last_close.csv', hold_rows, [
        'task', 'pivot_date', 'feature', 'actual', 'held', 'jump',
    ])
    save_figures(rows, lead_rows)
    write_artifact_manifest()


def main() -> None:
    if '--write-plan-only' in sys.argv:
        write_plan_only()
        return
    self_test_clock()
    plan = assert_plan_frozen()
    base = load_base()
    closes = np.asarray(base.C, dtype=float)
    assert_formula_matches_frozen_matrix(base, closes)
    eligible, targets, scores, last_input = load_p1(base)
    assert_cohort(plan, eligible, targets)
    assert_clock(base, targets, last_input)
    score_diff = assert_score_profile(base, plan, eligible, targets, scores)
    counts = sample_counts(eligible, targets)
    floor_failures = sample_floor_failures(plan, counts)
    lead_rows, test_rows, panel_rows, hold_rows = evaluate(base, closes, eligible, targets, scores, counts)
    apply_tests(plan, test_rows)
    decision = decide(plan, test_rows, floor_failures)
    plan_sha = sha256_file(HERE / 'plan.json')
    write_outputs(test_rows, lead_rows, panel_rows, hold_rows, decision, counts, score_diff, plan_sha)
    print(json.dumps({
        'decision': decision['decision'],
        'n_pass_presence': decision['n_pass_presence'],
        'n_pass_build': decision['n_pass_build'],
        'n_jump_dominates': decision['n_jump_dominates'],
        'n_plus1_level_dominates': decision['n_plus1_level_dominates'],
        'score_profile_max_abs_diff': score_diff,
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
