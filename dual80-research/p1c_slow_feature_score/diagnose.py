"""P1c: does an equal-weight score of the four presence-passing slow features
peak inside offsets -6..0?

Write the plan before any measurement. This path hashes sources and does not
read feature values:

    python -B diagnose.py --write-plan-only

Then run the one pre-registered score. It refuses to start without plan.json
and refuses to rewrite the plan:

    python -B diagnose.py
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
P1B = ROOT / 'dual80-research' / 'p1b_feature_timing'
TASKS = ('5_TOP', '5_BOTTOM', '9_TOP', '9_BOTTOM')
SLOW_FEATURES = (
    'return20_scaled',
    'distance_to_20day_high_scaled',
    'distance_to_20day_low_scaled',
    'position63',
)
EXCLUDED_FAST = ('return3_scaled', 'change_in_return3_scaled')
PEAK_OFFSETS = list(range(-13, 7))
WINDOW_OFFSETS = list(range(-6, 1))
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
    'dual80-research/p1_score_alignment/lead_profile.csv',
    'dual80-research/p1_score_alignment/eligible_days.csv',
    'dual80-research/p1_score_alignment/target_windows.csv',
    'dual80-research/p1b_feature_timing/plan.json',
    'dual80-research/p1b_feature_timing/decision.json',
)

CORE = {
    'phase': 'P1c',
    'title': 'Equal-weight slow-feature score: does the peak sit inside offsets -6..0?',
    'contains_measurements': False,
    'hypothesis': (
        'P1 found that the frozen six-feature close x price logistic score, fired with '
        'past_rank90, peaks at offset +1 on all four tasks. That session cannot hit the '
        'pivot. P1b found that four slow inputs already depart from ordinary days inside '
        'offsets -6..0, while the pivot close adds a further increment at +1. This '
        'experiment asks whether a score that uses only those four features, combined '
        'with fixed equal weights and the economic signs already written in the P1b plan, '
        'moves the lead-profile peak into the hittable window. Dual-80 precision and '
        'recall are reported against the frozen close x price x past_rank90 baseline. '
        'They are not a search target.'
    ),
    'freeze': {
        'index': '000985.CSI',
        'label': 'close',
        'feature_family': 'price',
        'feature_source': (
            'label_clock_v4 X["price"], produced by make_features(closes, turnover, style, '
            'scale=5) from broad_experiments_v2/run.py. The price block does not read '
            'scale, turnover, or style. Columns, in order: return3_scaled, return20_scaled, '
            'change_in_return3_scaled, distance_to_20day_high_scaled, '
            'distance_to_20day_low_scaled, position63.'
        ),
        'features_in_score': list(SLOW_FEATURES),
        'feature_columns': {
            'return20_scaled': 1,
            'distance_to_20day_high_scaled': 3,
            'distance_to_20day_low_scaled': 4,
            'position63': 5,
        },
        'excluded_from_primary_score': list(EXCLUDED_FAST),
        'excluded_reason': (
            'P1b presence did not clear return3_scaled or change_in_return3_scaled on two '
            'tasks. They stay out of this primary score. No sensitivity adds them.'
        ),
        'new_factors': False,
        'refit_six_feature_model': False,
        'coefficient_search': False,
        'threshold_search': False,
        'grid_search': False,
        'p2_alert_compression': False,
        'formal_signal_allowed': False,
        'blind_test': False,
        'PIT_certified': False,
        'production_changed': False,
        'decision_clock': 'pre-open on day D; feature row D uses closes through D-1',
        'offset_definition': (
            'Offset k is decision index pivot_index + k. Its last input index is '
            'pivot_index + k - 1. Offset 0 last input is the previous close. Offset +1 '
            'last input is the pivot close, and an alert that day cannot hit the pivot.'
        ),
        'hittable_window': 'Offsets -6..0.',
        'hit_rule': 'An alert on decision index a hits pivot p when 0 <= p - a <= 6.',
        'matching': 'same scale, same direction, one-to-one, label_clock_v4.run.match',
    },
    'score': {
        'name': 'equal_weight_sign_aligned_expanding_z_sum',
        'formula': (
            'score(task, i) = sum_k sign(task, k) * (x_k(i) - mu_k(i)) / sd_k(i), '
            'over the four slow features only.'
        ),
        'weights': 'Each included feature has weight 1. There is no intercept and no rescaling of the sum.',
        'clip': 'none',
        'probability': False,
        'signs': {
            'source': (
                'P1b plan economic signs for these four features. Tops are positive and '
                'bottoms are negative on every included feature. The signs were written '
                'before the P1b measurement and are not re-estimated from the P1c profile.'
            ),
            '5_TOP': {'return20_scaled': 1, 'distance_to_20day_high_scaled': 1, 'distance_to_20day_low_scaled': 1, 'position63': 1},
            '5_BOTTOM': {'return20_scaled': -1, 'distance_to_20day_high_scaled': -1, 'distance_to_20day_low_scaled': -1, 'position63': -1},
            '9_TOP': {'return20_scaled': 1, 'distance_to_20day_high_scaled': 1, 'distance_to_20day_low_scaled': 1, 'position63': 1},
            '9_BOTTOM': {'return20_scaled': -1, 'distance_to_20day_high_scaled': -1, 'distance_to_20day_low_scaled': -1, 'position63': -1},
        },
        'shared_series': (
            'The price block ignores scale and the signs do not differ by scale, so 5_TOP '
            'and 9_TOP share one score series and the two bottom tasks share its negation. '
            'Tasks still differ in targets, frontier, and eligible days. This does not '
            'authorize a scale-specific weight.'
        ),
        'standardization': {
            'estimator': 'expanding, causal, label-free',
            'rows': 'Feature rows j with 252 <= j < i. Row i is excluded. Rows before 252 are undefined and are excluded.',
            'minimum_rows': 126,
            'center': 'arithmetic mean',
            'scale': 'sample standard deviation, ddof=1',
            'sd_floor': 'If any feature has variance below 1e-12, the run aborts. There is no silent floor and no clip.',
            'not_used': 'Evaluation-sample ordinary-day moments, full-sample moments, and any moment that includes row i or a later row.',
        },
        'fitting': (
            'No coefficient is fit. No walk-forward logistic regression. The expanding mean '
            'and standard deviation are the only estimated numbers, and they are not chosen '
            'to maximize precision, recall, or a peak location. The 2016-01-01 date is the '
            'inherited evaluation start, not a split used to pick this formula.'
        ),
    },
    'fire_rule': {
        'name': 'past_rank90',
        'same_as': 'label_clock_v4/rank_replay.py and the P1 replay',
        'lookback_sessions': 252,
        'minimum_previous_scores': 126,
        'quantile': 0.90,
        'quantile_method': 'numpy linear',
        'threshold_inputs': 'Strictly earlier emitted scores inside the lookback. The current score is excluded.',
        'policy': (
            'Fire on an armed upward cross of that day\'s own threshold. Lock through '
            'decision index i+6. Rearm only on a later score strictly below that later '
            'day\'s own threshold. The quantile is not searched.'
        ),
        'applied_to': 'The slow-feature score, separately on each task series. The baseline ledger is replayed only to lock the rule and to report the frozen comparison.',
    },
    'cohort': {
        'source': 'P1 eligible_days.csv and target_windows.csv',
        'test_start': '2016-01-01',
        'eligible_day': (
            'A P1 eligible day: a close x price score exists, the baseline causal threshold '
            'exists, the session is on or after the test start, and the session plus 6 is '
            'on or before the mature frontier. This experiment also requires the slow-feature '
            'score and its own causal threshold on that same day. A missing slow-score '
            'threshold aborts the run rather than dropping the day.'
        ),
        'targets': {'5_TOP': 38, '5_BOTTOM': 39, '9_TOP': 18, '9_BOTTOM': 19},
        'eligible_days': {'5_TOP': 2396, '5_BOTTOM': 2396, '9_TOP': 2057, '9_BOTTOM': 2057},
        'regions': {
            '5_TOP': {'inside': 266, 'early_shoulder': 259, 'late_shoulder': 216, 'ordinary': 1655},
            '5_BOTTOM': {'inside': 267, 'early_shoulder': 273, 'late_shoulder': 209, 'ordinary': 1647},
            '9_TOP': {'inside': 112, 'early_shoulder': 112, 'late_shoulder': 96, 'ordinary': 1737},
            '9_BOTTOM': {'inside': 106, 'early_shoulder': 112, 'late_shoulder': 87, 'ordinary': 1752},
        },
        'region_priority': ['inside', 'early_shoulder', 'late_shoulder', 'ordinary'],
        'inside': 'Eligible day in [pivot-6, pivot] for at least one evaluated same-task target.',
        'early_shoulder': 'Eligible day in [pivot-13, pivot-7] and not inside.',
        'late_shoulder': 'Eligible day in [pivot+1, pivot+6] and not inside and not early.',
        'ordinary': 'Eligible day in none of those sets.',
        'p1_decision': 'BLOCKED_NO_CONCENTRATION',
        'p1b_decision': 'GO_PRE_PIVOT_COORDINATE',
        'new_split': False,
        'note': 'Repeatedly inspected history. Not a confirmation sample and not a blind test.',
    },
    'tests': {
        'sample_floors': {
            'n_inside_min': 30,
            'n_ordinary_min': 100,
            'n_targets_min': 10,
            'per_offset_min': 10,
            'offsets': PEAK_OFFSETS,
            'rule': 'Every offset from -13 through +6 must have at least 10 evaluated pivots whose decision day is eligible.',
        },
        'task_pass': {
            'mean_score_argmax': (
                'Among offsets -13..+6 with n>=10, every offset whose mean score is within '
                '1e-12 of the maximum lies in -6..0.'
            ),
            'tail_rate_argmax': 'The same rule for the causal past_rank90 tail rate.',
            'richer_than_ordinary': (
                'The median slow-feature score on eligible inside days is strictly greater '
                'than the median on eligible ordinary days, and the causal tail rate on '
                'inside days is strictly greater than the causal tail rate on ordinary days. '
                'numpy.median: even counts use the average of the two middle values.'
            ),
            'all_three_required': True,
            'tie_tolerance': 1e-12,
        },
        'majority': {
            'n_tasks': 4,
            'minimum_passing_tasks': 3,
            'rule': (
                'GO_WINDOW_PEAK requires at least 3 of the 4 tasks to pass all three '
                'task-level checks. Two passing tasks are not a majority.'
            ),
        },
        'decision_order': [
            'BLOCKED_INSUFFICIENT_SAMPLE if any task fails a sample floor',
            'else GO_WINDOW_PEAK if at least 3 tasks pass all three checks',
            'else BLOCKED_NO_WINDOW_PEAK',
        ],
        'blocked_meaning': (
            'BLOCKED_NO_WINDOW_PEAK means the pre-registered peak and richness gates failed. '
            'If the argmax stays outside -6..0, the pre-pivot feature movement does not '
            'survive combination into this decision score. The gates are not loosened and '
            'the two fast features are not added.'
        ),
        'go_meaning': (
            'The slow-feature score peaks inside the hittable window on a majority of tasks '
            'and those windows are richer than ordinary days. Dual-80 is reported, not '
            'claimed. GO_WINDOW_PEAK does not open Phase P2, does not authorize a signal, '
            'and does not refit the six-feature model.'
        ),
        'dependence_note': 'Days overlap and scores are autocorrelated. These gates are descriptive rules. No p-value is a gate.',
    },
    'reported_not_gates': [
        'precision, recall, TP, FP, FN, alerts, pending, and the dual-80 necessary band ceil(0.8*T)..floor(T/0.8)',
        'the same metrics for the frozen six-feature past_rank90 baseline',
        'mean score and tail rate at each offset, including the frozen six-feature profile',
        'plus1 mean minus the best mean inside -6..0, and the same gap for the tail rate',
        'early-shoulder and late-shoulder medians and tail rates',
        'share of evaluated targets with at least one eligible in-window causal-tail day',
        'expanding mean and standard deviation at the first and last eligible sessions',
        'the fact that the two top tasks share a score series and the two bottom tasks share its negation',
    ],
    'leakage': [
        'Putting the decision session close, the pivot close, or any later close into a feature row at offsets -6..0.',
        'Treating offset 0 as if its last input were the pivot close.',
        'Using row i, or a later row, in mu(i) or sd(i).',
        'Using ordinary-day moments from the evaluation sample, a label, a confirmation date, or a match status in the score.',
        'Fitting or editing logistic coefficients, weights, signs, or the 0.90 quantile after seeing the lead profile.',
        'Adding return3_scaled, change_in_return3_scaled, amount, style, swing, or any other input.',
        'Dropping an eligible day because its slow score is inconvenient.',
        'Choosing a different formula or a higher threshold after seeing precision or the argmax.',
        'Using future target counts as an alert quota.',
        'Changing the label, the index, or the hit window.',
    ],
    'out_of_scope': [
        'No refit of the six-feature model.',
        'No Phase P2 alert compression.',
        'No threshold change on the frozen score.',
        'No fast-feature sensitivity.',
        'No new external factor and no D-day feature.',
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
    plan = json.loads(json.dumps(CORE))
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
    names = list(on_disk['freeze']['features_in_score'])
    if names != list(SLOW_FEATURES):
        raise SystemExit('feature freeze drifted')
    if set(on_disk['freeze']['excluded_from_primary_score']) != set(EXCLUDED_FAST):
        raise SystemExit('fast-feature exclusion drifted')
    return on_disk


def write_plan_only() -> None:
    path = HERE / 'plan.json'
    if path.exists():
        raise SystemExit('plan.json already exists and is not rewritten')
    path.write_text(json.dumps(build_plan(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'wrote': str(path), 'contains_measurements': False}, ensure_ascii=False))


def price_row(closes: np.ndarray, i: int) -> np.ndarray:
    rets = np.diff(np.log(closes[i - 20:i + 1]))
    vol = max(float(np.std(rets, ddof=1)), 0.001)
    r3 = float(np.log(closes[i] / closes[i - 3]))
    r20 = float(np.log(closes[i] / closes[i - 20]))
    prev = float(np.log(closes[i - 3] / closes[i - 6]))
    hi20 = float(np.max(closes[i - 19:i + 1]))
    lo20 = float(np.min(closes[i - 19:i + 1]))
    hi63 = float(np.max(closes[i - 62:i + 1]))
    lo63 = float(np.min(closes[i - 62:i + 1]))
    pos = (float(closes[i]) - lo63) / (hi63 - lo63) if hi63 > lo63 else 0.5
    return np.array([
        r3 / vol,
        r20 / (vol * math.sqrt(20.0)),
        (r3 - prev) / vol,
        math.log(float(closes[i]) / hi20) / vol,
        math.log(float(closes[i]) / lo20) / vol,
        pos,
    ], dtype=float)


def self_test_clock() -> None:
    closes = np.full(80, 100.0)
    closes[60] = 110.0
    closes[70] = 120.0
    before = price_row(closes, 69)
    after = price_row(closes, 70)
    if not (before[3] < 0.0 and after[3] == 0.0 and after[5] == 1.0 and before[5] < 1.0):
        raise SystemExit('clock self-test failed')
    leaked = closes.copy()
    leaked[71] += 5.0
    if not np.array_equal(price_row(leaked, 70), after):
        raise SystemExit('a later close entered the feature')
    same_day = closes.copy()
    same_day[70] += 5.0
    if not np.array_equal(price_row(same_day, 69), before):
        raise SystemExit('the decision-day close entered that day feature')


def self_test_peak() -> None:
    def rows_with(mean_at: dict[int, float], tail_at: dict[int, float] | None = None, n: int = 12):
        out = []
        for offset in PEAK_OFFSETS:
            out.append({
                'offset': offset,
                'n': n,
                'mean_score': mean_at.get(offset, 0.0),
                'tail_rate': (tail_at or mean_at).get(offset, 0.0),
            })
        return out

    ok, winners, _best = peak_inside(rows_with({0: 1.0}), 'mean_score')
    if not ok or winners != [0]:
        raise SystemExit('peak self-test failed on an interior maximum')
    ok, winners, _best = peak_inside(rows_with({0: 1.0, 1: 1.0 + 5e-13}), 'mean_score')
    if ok or sorted(winners) != [0, 1]:
        raise SystemExit('peak self-test failed on a tie with offset +1')
    ok, winners, _best = peak_inside(rows_with({1: 2.0}), 'mean_score')
    if ok or winners != [1]:
        raise SystemExit('peak self-test failed on an offset-+1 maximum')
    thin = rows_with({-10: 5.0, 0: 1.0})
    for row in thin:
        if row['offset'] == -10:
            row['n'] = 9
    ok, winners, _best = peak_inside(thin, 'mean_score')
    if not ok or winners != [0]:
        raise SystemExit('peak self-test failed when a thin offset was ignored')
    low, high = necessary_band(38)
    if (low, high) != (31, 47):
        raise SystemExit('dual-80 band self-test failed')
    if necessary_band(39) != (32, 48) or necessary_band(18) != (15, 22) or necessary_band(19) != (16, 23):
        raise SystemExit('dual-80 band self-test failed')


def self_test_expanding() -> None:
    rng = np.random.default_rng(7)
    raw = rng.normal(size=(400, 4))
    got = expanding_sum(raw, np.array([1.0, 1.0, 1.0, 1.0]))
    if np.isfinite(got[:252 + 126]).any():
        raise SystemExit('expanding score started before 126 history rows')
    for i in (378, 399):
        hist = raw[252:i]
        mu = hist.mean(axis=0)
        sd = hist.std(axis=0, ddof=1)
        expect = float(np.sum((raw[i] - mu) / sd))
        if abs(got[i] - expect) > 1e-8:
            raise SystemExit('expanding score does not match the slice formula')
    rolled = raw.copy()
    rolled[:, 0] = np.roll(raw[:, 0], 1)
    # Column 0 is not a slow-feature slot in this unit test; the scorer uses every
    # column it is given. The production call passes only the four slow columns.
    if np.allclose(expanding_sum(raw, np.ones(4)), expanding_sum(rolled, np.ones(4)), equal_nan=True):
        raise SystemExit('expanding score ignored a column it was given')


def peak_inside(rows: list[dict], key: str) -> tuple[bool, list[int], float | None]:
    usable = [r for r in rows if r['n'] >= 10 and r[key] is not None]
    if not usable:
        return False, [], None
    best = max(r[key] for r in usable)
    winners = [int(r['offset']) for r in usable if abs(r[key] - best) <= 1e-12]
    return all(-6 <= offset <= 0 for offset in winners), winners, float(best)


def necessary_band(targets: int) -> tuple[int, int]:
    return (4 * targets + 4) // 5, (targets * 5) // 4


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


def moments_at(raw: np.ndarray, i: int) -> tuple[int, np.ndarray, np.ndarray]:
    hist = raw[252:i]
    if len(hist) < 126:
        raise SystemExit('moments requested before the minimum history')
    return len(hist), hist.mean(axis=0), hist.std(axis=0, ddof=1)


def load_rows(path: Path) -> list[dict]:
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def load_base():
    sys.path.insert(0, str(CLOCK))
    import run as base
    return base


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
        prior_scores = None
        last_input_index = None
        if len(past) >= 126:
            threshold = float(np.quantile(np.asarray(past, dtype=float), 0.90, method='linear'))
            prior_scores = len(past)
            last_input_index = hist[-1][0]
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
            'i': i,
            'score': value,
            'threshold': threshold,
            'excess': None if threshold is None else value - threshold,
            'in_tail': threshold is not None and value >= threshold,
            'fired': fired,
            'block': block,
            'prior_scores': prior_scores,
            'last_input_index': last_input_index,
        }
        hist.append((i, value))
        hist = [(j, p) for j, p in hist if j >= i - 252]
    return days, ledger


def assert_baseline_replay(base) -> dict:
    scores = [
        r for r in load_rows(CLOCK / 'scores.csv')
        if r['label'] == 'close' and r['group'] == 'price'
    ]
    published_metrics = {
        r['task']: r for r in load_rows(CLOCK / 'rank_metrics.csv')
        if r['label'] == 'close' and r['group'] == 'price__past_rank90'
    }
    events = [
        r for r in load_rows(CLOCK / 'rank_events.csv')
        if r['label'] == 'close' and r['group'] == 'price__past_rank90'
    ]
    thresholds = [
        r for r in load_rows(CLOCK / 'rank_thresholds.csv')
        if r['label'] == 'close' and r['group'] == 'price'
    ]
    front = {
        scale: min(
            max(g[0] for g in base.LABELS[variant][scale] if g[1] + 140 < base.N)
            for variant in base.LABELS
        )
        for scale in (5, 9)
    }
    max_diff = 0.0
    for task in TASKS:
        scale = int(task.split('_')[0])
        side = task.split('_')[1]
        task_scores = sorted((r for r in scores if r['task'] == task), key=lambda r: r['date'])
        values = np.full(base.N, np.nan)
        for row in task_scores:
            i = base.pos[row['date']]
            if base.pos[row['last_input']] != i - 1:
                raise SystemExit(f'baseline last_input is not D-1 on {task} {row["date"]}')
            values[i] = float(row['score'])
        days, ledger = replay_series(values)
        file_thresholds = {r['date']: r for r in thresholds if r['task'] == task}
        got_dates = {base.D[i] for i, day in days.items() if day['threshold'] is not None}
        if got_dates != set(file_thresholds):
            raise SystemExit(f'baseline threshold dates differ for {task}')
        for date, src in file_thresholds.items():
            day = days[base.pos[date]]
            max_diff = max(max_diff, abs(float(src['threshold']) - day['threshold']))
            if int(src['prior_scores']) != day['prior_scores']:
                raise SystemExit(f'baseline prior-score count differs on {task} {date}')
            if src['last_threshold_input'] != base.D[day['last_input_index']]:
                raise SystemExit(f'baseline threshold input differs on {task} {date}')
            if src['last_threshold_input'] >= date:
                raise SystemExit('published threshold uses the current day')
        if max_diff > 1e-8:
            raise SystemExit(f'baseline threshold values differ by {max_diff}')
        met, pairs, aa = base.evaluate(ledger, base.LABELS['close'][scale], side, front[scale], base.N)
        published = published_metrics[task]
        for key in ('TP', 'FP', 'FN', 'alerts', 'targets', 'pending'):
            if int(met[key]) != int(published[key]):
                raise SystemExit(f'baseline {task} {key} {met[key]} != {published[key]}')
        if abs(float(met['precision']) - float(published['precision'])) > 1e-12:
            raise SystemExit(f'baseline precision mismatch on {task}')
        if abs(float(met['recall']) - float(published['recall'])) > 1e-12:
            raise SystemExit(f'baseline recall mismatch on {task}')
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
            rebuilt.append((base.D[a], status, pivot_date))
        artifact = [(r['date'], r['status'], r['pivot_date']) for r in events if r['task'] == task]
        if rebuilt != artifact:
            raise SystemExit(f'baseline ledger does not match rank_events.csv for {task}')
    return {'max_abs_threshold_diff': max_diff, 'metrics_match': True, 'events_match': True}


def assert_price_matrix(base, closes: np.ndarray) -> np.ndarray:
    frozen = np.asarray(base.X['price'], dtype=float)
    if frozen.shape != (base.N, 6):
        raise SystemExit(f'price matrix shape {frozen.shape}')
    if not np.isfinite(frozen[252:]).all():
        raise SystemExit('price matrix has a non-finite value on or after session 252')
    if np.isfinite(frozen[:252]).any():
        raise SystemExit('price matrix is finite before session 252')
    for i in (251, 999, 1072, 2000, base.N - 2):
        if not np.allclose(price_row(closes, i), frozen[i + 1], atol=1e-8, rtol=0):
            raise SystemExit(f'price formula mismatch at last input {i}')
    if np.nanmax(frozen[252:, 3]) > 1e-8:
        raise SystemExit('distance_to_20day_high_scaled is not the non-positive column')
    if np.nanmin(frozen[252:, 4]) < -1e-8:
        raise SystemExit('distance_to_20day_low_scaled is not the non-negative column')
    if np.nanmin(frozen[252:, 5]) < -1e-8 or np.nanmax(frozen[252:, 5]) > 1 + 1e-8:
        raise SystemExit('position63 left the unit interval')
    prefix = base.make_features(base.C[:2500], base.A[:2500], base.S[:2500], 5)
    if not np.allclose(prefix['price'][252:2500], frozen[252:2500], atol=1e-8, rtol=0, equal_nan=True):
        raise SystemExit('price features failed the 2500-session prefix check')
    return frozen


def sign_vector(plan: dict, task: str) -> np.ndarray:
    signs = plan['score']['signs'][task]
    ordered = [int(signs[name]) for name in SLOW_FEATURES]
    if any(value not in (-1, 1) for value in ordered):
        raise SystemExit(f'sign is not +1 or -1 on {task}')
    if task.endswith('TOP') and ordered != [1, 1, 1, 1]:
        raise SystemExit('top signs drifted')
    if task.endswith('BOTTOM') and ordered != [-1, -1, -1, -1]:
        raise SystemExit('bottom signs drifted')
    return np.asarray(ordered, dtype=float)


def build_scores(plan: dict, frozen: np.ndarray) -> dict[str, np.ndarray]:
    columns = [int(plan['freeze']['feature_columns'][name]) for name in SLOW_FEATURES]
    if columns != [1, 3, 4, 5]:
        raise SystemExit('slow-feature columns drifted')
    if 0 in columns or 2 in columns:
        raise SystemExit('a fast feature entered the score')
    raw = frozen[:, columns]
    scrambled = frozen.copy()
    scrambled[:, 0] = np.roll(frozen[:, 0], 5)
    scrambled[:, 2] = np.roll(frozen[:, 2], 7)
    top = expanding_sum(raw, sign_vector(plan, '5_TOP'))
    top_scrambled = expanding_sum(scrambled[:, columns], sign_vector(plan, '5_TOP'))
    if not np.allclose(top, top_scrambled, equal_nan=True):
        raise SystemExit('fast-feature columns changed the slow-feature score')
    moved = frozen.copy()
    moved[1000, 1] += 3.0
    moved_score = expanding_sum(moved[:, columns], sign_vector(plan, '5_TOP'))
    if np.allclose(top[np.isfinite(top)], moved_score[np.isfinite(moved_score)], atol=1e-10, rtol=0):
        raise SystemExit('return20_scaled did not enter the score')
    out = {}
    for task in TASKS:
        series = expanding_sum(raw, sign_vector(plan, task))
        out[task] = series
    if not np.array_equal(out['5_TOP'], out['9_TOP'], equal_nan=True):
        raise SystemExit('top tasks did not share the pre-registered score series')
    if not np.allclose(out['5_BOTTOM'], -out['5_TOP'], equal_nan=True):
        raise SystemExit('bottom score is not the negation of the top score')
    if not np.array_equal(out['5_BOTTOM'], out['9_BOTTOM'], equal_nan=True):
        raise SystemExit('bottom tasks did not share the pre-registered score series')
    return out


def load_cohort(base, plan: dict) -> tuple[dict, dict]:
    eligible: dict[str, dict[int, str]] = {task: {} for task in TASKS}
    for row in load_rows(P1 / 'eligible_days.csv'):
        task = row['task']
        index = int(row['index'])
        if base.D[index] != row['date']:
            raise SystemExit(f'eligible date mismatch {task} {row["date"]}')
        if index in eligible[task]:
            raise SystemExit(f'duplicate eligible day {task} {row["date"]}')
        eligible[task][index] = row['region']
    targets: dict[str, list[int]] = {task: [] for task in TASKS}
    seen: dict[str, set[int]] = {task: set() for task in TASKS}
    for row in load_rows(P1 / 'target_windows.csv'):
        task = row['task']
        pivot = base.pos[row['pivot_date']]
        if pivot in seen[task]:
            raise SystemExit(f'duplicate pivot {task} {row["pivot_date"]}')
        seen[task].add(pivot)
        targets[task].append(pivot)
    for task in TASKS:
        targets[task].sort()
        if len(targets[task]) != plan['cohort']['targets'][task]:
            raise SystemExit(f'{task} target count drifted')
        if len(eligible[task]) != plan['cohort']['eligible_days'][task]:
            raise SystemExit(f'{task} eligible count drifted')
        counts = defaultdict(int)
        for region in eligible[task].values():
            counts[region] += 1
        for region, expected in plan['cohort']['regions'][task].items():
            if counts[region] != expected:
                raise SystemExit(f'{task} {region} count drifted')
        recomputed = region_map(targets[task], set(eligible[task]))
        for index, region in eligible[task].items():
            if recomputed[index] != region:
                raise SystemExit(f'region mismatch on {task} {base.D[index]}')
    p1_decision = json.loads((P1 / 'decision.json').read_text(encoding='utf-8'))
    p1b_decision = json.loads((P1B / 'decision.json').read_text(encoding='utf-8'))
    if p1_decision.get('decision') != 'BLOCKED_NO_CONCENTRATION':
        raise SystemExit('P1 decision text is not the frozen BLOCKED_NO_CONCENTRATION')
    if p1b_decision.get('decision') != 'GO_PRE_PIVOT_COORDINATE':
        raise SystemExit('P1b decision text is not the frozen GO_PRE_PIVOT_COORDINATE')
    presence = [(item['feature'], tuple(item['tasks'])) for item in p1b_decision['presence_go']]
    expect = [(name, TASKS) for name in SLOW_FEATURES]
    if presence != expect:
        raise SystemExit('P1b presence-passing list does not match the four slow features')
    return eligible, targets


def region_map(pivots: list[int], eligible: set[int]) -> dict[int, str]:
    inside, early, late = set(), set(), set()
    for pivot in pivots:
        inside.update(range(pivot - 6, pivot + 1))
        early.update(range(pivot - 13, pivot - 6))
        late.update(range(pivot + 1, pivot + 7))
    out = {}
    for index in eligible:
        if index in inside:
            out[index] = 'inside'
        elif index in early:
            out[index] = 'early_shoulder'
        elif index in late:
            out[index] = 'late_shoulder'
        else:
            out[index] = 'ordinary'
    return out


def assert_p1_profile(base, eligible, targets) -> None:
    published = {}
    for row in load_rows(P1 / 'lead_profile.csv'):
        published[(row['task'], int(row['offset']))] = (int(row['n']), float(row['mean_score']), float(row['tail_rate']))
    scores = {
        (r['task'], r['date']): float(r['score'])
        for r in load_rows(CLOCK / 'scores.csv')
        if r['label'] == 'close' and r['group'] == 'price'
    }
    for task in TASKS:
        for offset in PEAK_OFFSETS:
            chosen = []
            for pivot in targets[task]:
                index = pivot + offset
                if index in eligible[task]:
                    chosen.append(scores[(task, base.D[index])])
            n_pub, mean_pub, _tail = published[(task, offset)]
            if len(chosen) != n_pub:
                raise SystemExit(f'P1 profile n mismatch {task} {offset}')
            if abs(float(np.mean(chosen)) - mean_pub) > 1e-8:
                raise SystemExit(f'P1 profile mean mismatch {task} {offset}')


def measure(base, plan, frozen, scores, eligible, targets) -> dict:
    published_profile = {}
    for row in load_rows(P1 / 'lead_profile.csv'):
        published_profile[(row['task'], int(row['offset']))] = row
    published_metrics = {
        r['task']: r for r in load_rows(CLOCK / 'rank_metrics.csv')
        if r['label'] == 'close' and r['group'] == 'price__past_rank90'
    }
    front = {
        scale: min(
            max(g[0] for g in base.LABELS[variant][scale] if g[1] + 140 < base.N)
            for variant in base.LABELS
        )
        for scale in (5, 9)
    }
    raw = frozen[:, [1, 3, 4, 5]]
    first_eligible = min(min(eligible[task]) for task in TASKS)
    last_eligible = max(max(eligible[task]) for task in TASKS)
    moments = {}
    for label, index in (('first_eligible', first_eligible), ('last_eligible', last_eligible)):
        count, mu, sd = moments_at(raw, index)
        moments[label] = {
            'date': base.D[index],
            'history_rows': count,
            'mean': {name: float(mu[k]) for k, name in enumerate(SLOW_FEATURES)},
            'std': {name: float(sd[k]) for k, name in enumerate(SLOW_FEATURES)},
        }
    lead_rows = []
    region_rows = []
    test_rows = []
    metric_rows = []
    eligible_rows = []
    alert_rows = []
    task_summary = {}
    floor_failures = []
    for task in TASKS:
        scale = int(task.split('_')[0])
        side = task.split('_')[1]
        days, ledger = replay_series(scores[task])
        missing = [index for index in eligible[task] if index not in days or days[index]['threshold'] is None]
        if missing:
            raise SystemExit(f'{task} has {len(missing)} eligible days without a slow-score threshold')
        for index, region in sorted(eligible[task].items()):
            day = days[index]
            eligible_rows.append({
                'task': task,
                'date': base.D[index],
                'index': index,
                'region': region,
                'score': day['score'],
                'threshold': day['threshold'],
                'excess': day['excess'],
                'in_tail': day['in_tail'],
                'fired': day['fired'],
                'block': day['block'],
            })
        by_region = {name: [] for name in ('inside', 'early_shoulder', 'late_shoulder', 'ordinary')}
        for index, region in eligible[task].items():
            by_region[region].append(days[index])
        region_stats = {}
        for name, group in by_region.items():
            score_vals = [day['score'] for day in group]
            tail_vals = [1.0 if day['in_tail'] else 0.0 for day in group]
            stat = {
                'task': task,
                'region': name,
                'n_days': len(group),
                'score_mean': float(np.mean(score_vals)),
                'score_median': float(np.median(score_vals)),
                'tail_rate': float(np.mean(tail_vals)),
                'n_tail': int(sum(tail_vals)),
                'mean_excess': float(np.mean([day['excess'] for day in group])),
                'median_excess': float(np.median([day['excess'] for day in group])),
            }
            region_stats[name] = stat
            region_rows.append(stat)
        task_lead = []
        for offset in PEAK_OFFSETS:
            chosen = []
            for pivot in targets[task]:
                index = pivot + offset
                if index in eligible[task]:
                    chosen.append(days[index])
            published = published_profile[(task, offset)]
            row = {
                'task': task,
                'offset': offset,
                'n': len(chosen),
                'mean_score': float(np.mean([day['score'] for day in chosen])) if chosen else None,
                'tail_rate': float(np.mean([1.0 if day['in_tail'] else 0.0 for day in chosen])) if chosen else None,
                'mean_excess': float(np.mean([day['excess'] for day in chosen])) if chosen else None,
                'in_hittable_window': -6 <= offset <= 0,
                'p1_n': int(published['n']),
                'p1_mean_score': float(published['mean_score']),
                'p1_tail_rate': float(published['tail_rate']),
            }
            if row['n'] != row['p1_n']:
                raise SystemExit(f'lead n drifted from P1 on {task} offset {offset}')
            task_lead.append(row)
            lead_rows.append(row)
        for offset in PEAK_OFFSETS:
            n = next(row['n'] for row in task_lead if row['offset'] == offset)
            if n < 10:
                floor_failures.append(f'{task} offset {offset} n {n} < 10')
        if region_stats['inside']['n_days'] < 30:
            floor_failures.append(f'{task} inside n {region_stats["inside"]["n_days"]} < 30')
        if region_stats['ordinary']['n_days'] < 100:
            floor_failures.append(f'{task} ordinary n {region_stats["ordinary"]["n_days"]} < 100')
        if len(targets[task]) < 10:
            floor_failures.append(f'{task} targets {len(targets[task])} < 10')
        mean_ok, mean_at, mean_best = peak_inside(task_lead, 'mean_score')
        tail_ok, tail_at, tail_best = peak_inside(task_lead, 'tail_rate')
        rich_median = region_stats['inside']['score_median'] > region_stats['ordinary']['score_median']
        rich_tail = region_stats['inside']['tail_rate'] > region_stats['ordinary']['tail_rate']
        rich_ok = rich_median and rich_tail
        passed = mean_ok and tail_ok and rich_ok
        window_means = [row['mean_score'] for row in task_lead if row['offset'] in WINDOW_OFFSETS]
        window_tails = [row['tail_rate'] for row in task_lead if row['offset'] in WINDOW_OFFSETS]
        plus1 = next(row for row in task_lead if row['offset'] == 1)
        checks = [
            ('n_inside', region_stats['inside']['n_days'] >= 30, region_stats['inside']['n_days'], '>= 30'),
            ('n_ordinary', region_stats['ordinary']['n_days'] >= 100, region_stats['ordinary']['n_days'], '>= 100'),
            ('n_targets', len(targets[task]) >= 10, len(targets[task]), '>= 10'),
            ('offsets_n_at_least_10', all(row['n'] >= 10 for row in task_lead), min(row['n'] for row in task_lead), 'minimum n across offsets -13..+6 >= 10'),
            ('mean_score_peak_inside_window', mean_ok, mean_at, 'all tied argmax offsets in -6..0'),
            ('tail_rate_peak_inside_window', tail_ok, tail_at, 'all tied argmax offsets in -6..0'),
            ('median_inside_gt_ordinary', rich_median, region_stats['inside']['score_median'], f'> ordinary median {region_stats["ordinary"]["score_median"]:.6g}'),
            ('tail_inside_gt_ordinary', rich_tail, region_stats['inside']['tail_rate'], f'> ordinary tail rate {region_stats["ordinary"]["tail_rate"]:.6g}'),
        ]
        for name, ok, actual, expect in checks:
            test_rows.append({'task': task, 'check': name, 'passed': bool(ok), 'actual': actual, 'expect': expect})
        met, pairs, aa = base.evaluate(ledger, base.LABELS['close'][scale], side, front[scale], base.N)
        matched = dict(pairs)
        aa_set = set(aa)
        targets_with_tail = 0
        for pivot in targets[task]:
            if any(days[i]['in_tail'] for i in range(pivot - 6, pivot + 1) if i in eligible[task]):
                targets_with_tail += 1
        for a in ledger:
            if a < base.START:
                continue
            if a in matched:
                status, pivot_date = 'TP', base.D[matched[a]]
            elif a in aa_set:
                status, pivot_date = 'FP', ''
            else:
                status, pivot_date = 'PENDING', ''
            alert_rows.append({
                'task': task,
                'date': base.D[a],
                'index': a,
                'status': status,
                'pivot_date': pivot_date,
                'score': days[a]['score'],
                'threshold': days[a]['threshold'],
                'excess': days[a]['excess'],
            })
        band_low, band_high = necessary_band(int(met['targets']))
        metric_rows.append({
            'task': task,
            'source': 'slow_feature_score',
            'TP': met['TP'],
            'FP': met['FP'],
            'FN': met['FN'],
            'precision': met['precision'],
            'recall': met['recall'],
            'alerts': met['alerts'],
            'targets': met['targets'],
            'pending': met['pending'],
            'band_low': band_low,
            'band_high': band_high,
            'alerts_above_band': met['alerts'] > band_high,
            'dual80': False,
        })
        base_row = published_metrics[task]
        base_low, base_high = necessary_band(int(base_row['targets']))
        metric_rows.append({
            'task': task,
            'source': 'frozen_six_feature_past_rank90',
            'TP': int(base_row['TP']),
            'FP': int(base_row['FP']),
            'FN': int(base_row['FN']),
            'precision': float(base_row['precision']),
            'recall': float(base_row['recall']),
            'alerts': int(base_row['alerts']),
            'targets': int(base_row['targets']),
            'pending': int(base_row['pending']),
            'band_low': base_low,
            'band_high': base_high,
            'alerts_above_band': int(base_row['alerts']) > base_high,
            'dual80': False,
        })
        task_summary[task] = {
            'passed': passed,
            'mean_peak_offsets': mean_at,
            'tail_peak_offsets': tail_at,
            'mean_peak_value': mean_best,
            'tail_peak_value': tail_best,
            'mean_peak_inside': mean_ok,
            'tail_peak_inside': tail_ok,
            'richer_than_ordinary': rich_ok,
            'inside_median': region_stats['inside']['score_median'],
            'ordinary_median': region_stats['ordinary']['score_median'],
            'inside_tail_rate': region_stats['inside']['tail_rate'],
            'ordinary_tail_rate': region_stats['ordinary']['tail_rate'],
            'early_tail_rate': region_stats['early_shoulder']['tail_rate'],
            'late_tail_rate': region_stats['late_shoulder']['tail_rate'],
            'plus1_minus_best_window_mean': plus1['mean_score'] - max(window_means),
            'plus1_minus_best_window_tail': plus1['tail_rate'] - max(window_tails),
            'targets_with_any_window_tail': targets_with_tail,
            'targets': len(targets[task]),
            'metrics': {k: met[k] for k in ('TP', 'FP', 'FN', 'precision', 'recall', 'alerts', 'targets', 'pending')},
        }
    n_pass = sum(1 for task in TASKS if task_summary[task]['passed'])
    if floor_failures:
        decision = 'BLOCKED_INSUFFICIENT_SAMPLE'
    elif n_pass >= 3:
        decision = 'GO_WINDOW_PEAK'
    else:
        decision = 'BLOCKED_NO_WINDOW_PEAK'
    return {
        'decision': decision,
        'n_pass': n_pass,
        'floor_failures': floor_failures,
        'tasks': task_summary,
        'lead_rows': lead_rows,
        'region_rows': region_rows,
        'test_rows': test_rows,
        'metric_rows': metric_rows,
        'eligible_rows': eligible_rows,
        'alert_rows': alert_rows,
        'moments': moments,
    }


def offset_text(offsets: list[int]) -> str:
    return ', '.join(f'{offset:+d}' for offset in offsets)


def fmt_num(value, digits=3) -> str:
    if value is None:
        return ''
    return f'{float(value):.{digits}f}'


def fmt_pct(value) -> str:
    if value is None:
        return ''
    return f'{100 * float(value):.1f}%'


def comparison_phrases(result: dict) -> tuple[str, str]:
    english = []
    chinese = []
    for row in result['metric_rows']:
        if row['source'] != 'slow_feature_score':
            continue
        base = next(
            item for item in result['metric_rows']
            if item['task'] == row['task'] and item['source'] != 'slow_feature_score'
        )
        english.append(
            f"{row['task']} {fmt_pct(row['precision'])}/{fmt_pct(row['recall'])} "
            f"versus baseline {fmt_pct(base['precision'])}/{fmt_pct(base['recall'])}"
        )
        chinese.append(
            f"{row['task']} {fmt_pct(row['precision'])}/{fmt_pct(row['recall'])}，"
            f"基线 {fmt_pct(base['precision'])}/{fmt_pct(base['recall'])}"
        )
    return '; '.join(english), '；'.join(chinese)


def decision_paragraphs(result: dict) -> tuple[str, str]:
    tasks = result['tasks']
    peaks = ', '.join(
        f"{task} mean {offset_text(tasks[task]['mean_peak_offsets'])} / tail {offset_text(tasks[task]['tail_peak_offsets'])}"
        for task in TASKS
    )
    peaks_cn = '；'.join(
        f"{task} 平均 {offset_text(tasks[task]['mean_peak_offsets'])}，尾部 {offset_text(tasks[task]['tail_peak_offsets'])}"
        for task in TASKS
    )
    passing = [task for task in TASKS if tasks[task]['passed']]
    metrics, metrics_cn = comparison_phrases(result)
    rich_all = all(tasks[task]['richer_than_ordinary'] for task in TASKS)
    rich_note = (
        ' Inside-window medians and causal tail rates are strictly above ordinary days on all four tasks.'
        if rich_all else ''
    )
    rich_note_cn = '四项任务的窗口内中位数和因果尾部比例都严格高于普通日。' if rich_all else ''
    if result['decision'] == 'GO_WINDOW_PEAK':
        english = (
            f"GO_WINDOW_PEAK. The equal-weight slow-feature score peaks inside offsets -6..0 "
            f"on {result['n_pass']} of 4 tasks ({', '.join(passing)}). A task passes only when "
            f"every tied mean-score argmax and every tied causal-tail argmax lies in -6..0, and "
            f"the inside-window median and tail rate are both strictly above ordinary days. "
            f"Peaks: {peaks}. Baseline comparison, reported and not optimized: {metrics}. "
            f"Dual-80 is not claimed. formal_signal_allowed stays false. This is not PIT, not a "
            f"blind test, and not a signal."
        )
        chinese = (
            f"放行。四个慢变量的等权分数在 {result['n_pass']} / 4 个任务上，平均分数和因果尾部的峰值都落在 −6..0，"
            f"并且窗口内中位数和尾部比例都高于普通日。通过的任务：{'、'.join(passing)}。峰值：{peaks_cn}。"
            f"与冻结基线的精确率/覆盖率对照（只报告，没有拿来选公式）：{metrics_cn}。不声称双80。"
            f"formal_signal_allowed 仍为 false。这不是 PIT，不是盲测，也不是信号。"
        )
        return english, chinese
    if result['decision'] == 'BLOCKED_INSUFFICIENT_SAMPLE':
        english = (
            'BLOCKED_INSUFFICIENT_SAMPLE. A pre-registered sample floor failed, so the peak '
            'gate was not used. ' + '; '.join(result['floor_failures'])
        )
        chinese = '样本不足，峰值门槛没有启用。' + '；'.join(result['floor_failures'])
        return english, chinese
    outside = [
        task for task in TASKS
        if not (tasks[task]['mean_peak_inside'] and tasks[task]['tail_peak_inside'])
    ]
    if outside:
        implication = (
            'The pre-pivot movement of the four slow features does not survive combination '
            'into this decision score.'
        )
        implication_cn = '四个慢变量在拐点前的移动，合成决策分数之后没有保住可命中窗口里的峰值。'
    else:
        implication = (
            'The argmax sits inside -6..0, and the richness check against ordinary days is the failure.'
        )
        implication_cn = '峰值落在窗口内，未通过的是相对普通日的富集。'
    english = (
        f"BLOCKED. The pre-registered slow-feature score does not clear the window-peak gate "
        f"on a majority of tasks ({result['n_pass']} of 4 pass; the rule requires 3). Peaks: {peaks}. "
        f"{implication}{rich_note} Baseline comparison, reported and not optimized: {metrics}. "
        f"Dual-80 is not claimed. The two fast features stay out of the score. P1 remains "
        f"BLOCKED_NO_CONCENTRATION. P1b remains GO_PRE_PIVOT_COORDINATE. formal_signal_allowed "
        f"stays false. This is not PIT, not a blind test, and not a signal."
    )
    chinese = (
        f"阻断。预注册的慢变量分数没有在多数任务上通过窗口峰值门槛（{result['n_pass']} / 4 通过，规则要求 3 个）。"
        f"峰值：{peaks_cn}。{implication_cn}{rich_note_cn}"
        f"与冻结基线的精确率/覆盖率对照（只报告）：{metrics_cn}。不声称双80。两个快变量不进入这个分数。"
        f"P1 仍是 BLOCKED_NO_CONCENTRATION。P1b 仍是 GO_PRE_PIVOT_COORDINATE。"
        f"formal_signal_allowed 仍为 false。这不是 PIT，不是盲测，也不是信号。"
    )
    return english, chinese


def render_report(result: dict) -> str:
    english, chinese = decision_paragraphs(result)
    lines = [
        '# P1c 四个慢变量的等权分数能否在 −6..0 达到峰值',
        '',
        f"**Decision: `{result['decision']}`.** {english}",
        '',
        f"**结论：`{result['decision']}`。** {chinese}",
        '',
        '这是一项预注册实验。`formal_signal_allowed` 仍为 false。没有 PIT 认证，没有盲测，没有生产信号。P1 的 `BLOCKED_NO_CONCENTRATION` 与 P1b 的 `GO_PRE_PIVOT_COORDINATE` 不改写。',
        '',
        '## 冻结的分数',
        '',
        '标签 close，指数 000985.CSI，决策时钟为 D 日开盘前。分数只用 P1b 存在检验在四个任务上都通过的四个慢变量：20日收益、距20日高点、距20日低点、63日区间位置。3日收益和3日收益变化不进入这个分数。',
        '',
        '每个特征减去严格更早的扩展均值，再除以严格更早的样本标准差（ddof=1，至少 126 行，当天不进入）。顶部四个符号都是 +1，底部四个符号都是 −1，符号来自 P1b 计划里事先写好的经济方向。四项权重都是 1，没有截距，没有截断，没有系数搜索。5% 顶部和 9% 顶部共用同一条分数，两条底部共用它的相反数；任务之间的差别在目标、成熟前沿和可评分日。',
        '',
        '发报规则与冻结基线相同：过去 252 个已发分数的线性 90 分位，至少 126 个历史分数，当天不参与阈值，向上越过时发报，锁定到 D+6，之后只有分数低于当天自身阈值才重新武装。分位没有搜索。',
        '',
        '## 门槛',
        '',
        '一个任务同时满足三条才算通过：在 −13..+6 且样本不少于 10 的偏移里，平均分数的全部并列峰值都落在 −6..0；因果尾部比例同样如此；窗口内分数中位数和尾部比例都严格高于普通日。四项里至少三项通过，结论才是 `GO_WINDOW_PEAK`。精确率和覆盖率只与 close × price × past_rank90 对照，不参与选择。',
        '',
        '## 领先剖面',
        '',
        '偏移 0 是拐点当天，最后输入是前一日收盘。偏移 +1 的最后输入才是拐点收盘，这一天的警报打不中该拐点。下表是峰值附近。完整的 −13..+6 在 `lead_profile.csv`。',
        '',
        '| 任务 | 偏移 | 样本 | 慢变量平均分数 | 慢变量尾部 | 冻结六特征平均分数 | 冻结六特征尾部 | 在命中窗 |',
        '|---|---:|---:|---:|---:|---:|---:|---|',
    ]
    for row in result['lead_rows']:
        if row['offset'] not in (-2, -1, 0, 1, 2):
            continue
        lines.append(
            f"| {row['task']} | {row['offset']:+d} | {row['n']} | {fmt_num(row['mean_score'])} | "
            f"{fmt_pct(row['tail_rate'])} | {fmt_num(row['p1_mean_score'])} | {fmt_pct(row['p1_tail_rate'])} | "
            f"{'是' if row['in_hittable_window'] else '否'} |"
        )
    lines += [
        '',
        '| 任务 | 平均分数峰值 | 尾部峰值 | 窗口内中位数 | 普通日中位数 | 窗口内尾部 | 普通日尾部 | +1 减窗口内最高平均 | +1 减窗口内最高尾部 | 通过 |',
        '|---|---|---|---:|---:|---:|---:|---:|---:|---|',
    ]
    for task in TASKS:
        item = result['tasks'][task]
        lines.append(
            f"| {task} | {offset_text(item['mean_peak_offsets'])} | {offset_text(item['tail_peak_offsets'])} | "
            f"{fmt_num(item['inside_median'])} | {fmt_num(item['ordinary_median'])} | "
            f"{fmt_pct(item['inside_tail_rate'])} | {fmt_pct(item['ordinary_tail_rate'])} | "
            f"{fmt_num(item['plus1_minus_best_window_mean'])} | {fmt_num(item['plus1_minus_best_window_tail'])} | "
            f"{'PASS' if item['passed'] else 'FAIL'} |"
        )
    rich_all = all(result['tasks'][task]['richer_than_ordinary'] for task in TASKS)
    peak_note = ''
    if rich_all and result['decision'] == 'BLOCKED_NO_WINDOW_PEAK':
        locs = '；'.join(
            f"{task} 平均 {offset_text(result['tasks'][task]['mean_peak_offsets'])}、"
            f"尾部 {offset_text(result['tasks'][task]['tail_peak_offsets'])}"
            for task in TASKS
        )
        peak_note = (
            '四项任务的窗口内中位数和尾部比例都高于普通日。没有通过的是峰值位置：'
            f'{locs}。早肩和晚肩只列在下表，不进入门槛。'
        )
    lines += [
        '',
        peak_note,
        '',
        '图：`fig_lead_profile.png` 是 −13..+6 的平均分数和尾部比例，绿带是可命中窗口，橙线是偏移 +1。`fig_region_tail.png` 比较窗口、两肩和普通日的尾部比例。',
        '',
        '## 区域',
        '',
        '| 任务 | 区域 | 天数 | 分数中位数 | 尾部比例 |',
        '|---|---|---:|---:|---:|',
    ]
    region_name = {
        'inside': '窗口内',
        'early_shoulder': '早肩',
        'late_shoulder': '晚肩',
        'ordinary': '普通日',
    }
    for row in result['region_rows']:
        lines.append(
            f"| {row['task']} | {region_name[row['region']]} | {row['n_days']} | "
            f"{fmt_num(row['score_median'])} | {fmt_pct(row['tail_rate'])} |"
        )
    lines += [
        '',
        '## 与冻结基线对照',
        '',
        '下表是同一成熟队列、同一对一匹配、同一 past_rank90 规则下的计数。双80必要警报区间只说明警报数和目标数的算术关系，没有用来配额。',
        '',
        '| 任务 | 分数 | 目标 | 警报 | TP | FP | FN | 精确率 | 覆盖率 | PENDING | 双80警报区间 |',
        '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|',
    ]
    source_name = {
        'slow_feature_score': '四慢变量等权',
        'frozen_six_feature_past_rank90': '冻结六特征',
    }
    for row in result['metric_rows']:
        lines.append(
            f"| {row['task']} | {source_name[row['source']]} | {row['targets']} | {row['alerts']} | "
            f"{row['TP']} | {row['FP']} | {row['FN']} | {fmt_pct(row['precision'])} | {fmt_pct(row['recall'])} | "
            f"{row['pending']} | {row['band_low']}–{row['band_high']} |"
        )
    lines += [
        '',
        '| 任务 | 有可评分窗口日且至少一天进入因果尾部的目标 | 目标数 |',
        '|---|---:|---:|',
    ]
    for task in TASKS:
        item = result['tasks'][task]
        lines.append(f"| {task} | {item['targets_with_any_window_tail']} | {item['targets']} |")
    lines += [
        '',
        '## 逐项判定',
        '',
        '| 任务 | 检验 | 结果 | 实际值 | 预注册要求 |',
        '|---|---|---|---|---|',
    ]
    for row in result['test_rows']:
        actual = row['actual']
        if isinstance(actual, list):
            shown = offset_text(actual)
        elif isinstance(actual, float):
            shown = f'{actual:.6g}'
        else:
            shown = str(actual)
        lines.append(
            f"| {row['task']} | {row['check']} | {'PASS' if row['passed'] else 'FAIL'} | {shown} | {row['expect']} |"
        )
    lines += [
        '',
        '## 边界',
        '',
        '- 决策日重叠，分数自相关。门槛是描述规则。',
        '- 拐点是事后确认的收盘标签。这是研究诊断，不是可交易信号。',
        '- 历史被反复看过。历史公布时点与指数成分仍未完成全时期 PIT 认证。',
        '- 标准化只用当天之前的特征行。偏移 0 的最后输入是拐点前一日。',
        '- 没有重训六个价格特征的逻辑回归，没有打开 P2，没有提高冻结分数的阈值。',
        '- 没有把 D 日收盘写进当日特征，没有更换标签或指数。',
        '- 没有修改生产页面、采集器、正式信号，也没有恢复旧 V 系列。',
        '',
        '## 复算',
        '',
        '```text',
        'python -B dual80-research/p1c_slow_feature_score/diagnose.py',
        '```',
        '',
        '缺少 `plan.json` 时测量会停止。`--write-plan-only` 只在文件不存在时写出计划，不读特征数值。',
        '',
    ]
    return '\n'.join(lines)


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
                elif isinstance(value, list):
                    out[field] = offset_text(value)
                elif value is None:
                    out[field] = ''
                else:
                    out[field] = value
            writer.writerow(out)


def plain(value):
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if math.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def save_figures(result: dict) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(3, 4, figsize=(14.2, 8.2), sharex=True)
    offsets = PEAK_OFFSETS
    for col, task in enumerate(TASKS):
        rows = {row['offset']: row for row in result['lead_rows'] if row['task'] == task}
        xs = np.asarray(offsets)
        panels = (
            (0, [rows[k]['mean_score'] for k in offsets], '#08519c', 'slow-feature mean'),
            (1, [rows[k]['p1_mean_score'] for k in offsets], '#636363', 'frozen six-feature mean'),
            (2, None, None, None),
        )
        for row_i, series, color, _label in panels[:2]:
            ax = axes[row_i, col]
            ax.axvspan(-6, 0, color='#c7e9c0', zorder=0)
            ax.axvline(1, color='#d95f0e', lw=1)
            ax.plot(xs, series, color=color, marker='o', ms=3)
            ax.grid(alpha=0.25)
            ax.set_title(task if row_i == 0 else '')
        ax = axes[2, col]
        ax.axvspan(-6, 0, color='#c7e9c0', zorder=0)
        ax.axvline(1, color='#d95f0e', lw=1)
        ax.plot(xs, [rows[k]['tail_rate'] for k in offsets], color='#08519c', marker='o', ms=3, label='slow-feature tail')
        ax.plot(xs, [rows[k]['p1_tail_rate'] for k in offsets], color='#bdbdbd', marker='o', ms=3, label='frozen six-feature tail')
        ax.set_ylim(-0.02, 1.02)
        ax.grid(alpha=0.25)
        ax.set_xlabel('offset')
    axes[0, 0].set_ylabel('mean score')
    axes[1, 0].set_ylabel('frozen mean score')
    axes[2, 0].set_ylabel('causal tail rate')
    axes[2, 0].legend(fontsize=7, loc='upper left')
    fig.suptitle('Green band: hittable offsets -6..0. Orange line: offset +1, which cannot hit the pivot.')
    fig.tight_layout()
    fig.savefig(HERE / 'fig_lead_profile.png', dpi=140)
    plt.close(fig)

    fig, axes = plt.subplots(1, 4, figsize=(13.2, 3.8), sharey=True)
    order = ('inside', 'early_shoulder', 'late_shoulder', 'ordinary')
    labels = ('inside', 'early', 'late', 'ordinary')
    colors = ('#31a354', '#9ecae1', '#fdae6b', '#bdbdbd')
    for ax, task in zip(axes, TASKS):
        stats = {row['region']: row for row in result['region_rows'] if row['task'] == task}
        vals = [stats[name]['tail_rate'] for name in order]
        ax.bar(labels, vals, color=colors)
        ax.set_title(task)
        ax.set_ylim(0, 1)
        ax.grid(axis='y', alpha=0.25)
    axes[0].set_ylabel('causal tail rate')
    fig.suptitle('Slow-feature tail rate by pre-registered region')
    fig.tight_layout()
    fig.savefig(HERE / 'fig_region_tail.png', dpi=140)
    plt.close(fig)


def write_artifact_manifest() -> None:
    files = sorted(path for path in HERE.iterdir() if path.is_file() and path.name != 'artifact_manifest.json')
    manifest = {path.name: {'bytes': path.stat().st_size, 'sha256': sha256_file(path)} for path in files}
    (HERE / 'artifact_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def write_outputs(result: dict, plan_sha: str, baseline_lock: dict) -> None:
    english, chinese = decision_paragraphs(result)
    decision = {
        'decision': result['decision'],
        'formal_signal_allowed': False,
        'blind_test': False,
        'PIT_certified': False,
        'production_changed': False,
        'refit_six_feature_model': False,
        'p2_opened': False,
        'fast_features_in_primary_score': False,
        'english': english,
        'chinese': chinese,
        'passing_tasks': [task for task in TASKS if result['tasks'][task]['passed']],
        'n_pass': result['n_pass'],
        'minimum_passing_tasks': 3,
        'mean_peak_offsets': {task: result['tasks'][task]['mean_peak_offsets'] for task in TASKS},
        'tail_peak_offsets': {task: result['tasks'][task]['tail_peak_offsets'] for task in TASKS},
    }
    (HERE / 'decision.json').write_text(json.dumps(plain(decision), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    payload = {
        'phase': 'P1c',
        'decision': result['decision'],
        'formal_signal_allowed': False,
        'blind_test': False,
        'PIT_certified': False,
        'production_changed': False,
        'refit_six_feature_model': False,
        'p2_alert_compression': False,
        'plan_sha256': plan_sha,
        'p1_decision': 'BLOCKED_NO_CONCENTRATION',
        'p1b_decision': 'GO_PRE_PIVOT_COORDINATE',
        'baseline_lock': baseline_lock,
        'floor_failures': result['floor_failures'],
        'n_pass': result['n_pass'],
        'tasks': result['tasks'],
        'moments': result['moments'],
        'metrics': result['metric_rows'],
    }
    (HERE / 'result.json').write_text(json.dumps(plain(payload), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (HERE / 'README.md').write_text(render_report(result), encoding='utf-8')
    write_csv(HERE / 'lead_profile.csv', result['lead_rows'], [
        'task', 'offset', 'n', 'mean_score', 'tail_rate', 'mean_excess', 'in_hittable_window',
        'p1_n', 'p1_mean_score', 'p1_tail_rate',
    ])
    write_csv(HERE / 'region_summary.csv', result['region_rows'], [
        'task', 'region', 'n_days', 'score_mean', 'score_median', 'tail_rate', 'n_tail',
        'mean_excess', 'median_excess',
    ])
    write_csv(HERE / 'task_tests.csv', result['test_rows'], ['task', 'check', 'passed', 'actual', 'expect'])
    write_csv(HERE / 'metrics_compare.csv', result['metric_rows'], [
        'task', 'source', 'TP', 'FP', 'FN', 'precision', 'recall', 'alerts', 'targets', 'pending',
        'band_low', 'band_high', 'alerts_above_band', 'dual80',
    ])
    write_csv(HERE / 'eligible_days.csv', result['eligible_rows'], [
        'task', 'date', 'index', 'region', 'score', 'threshold', 'excess', 'in_tail', 'fired', 'block',
    ])
    write_csv(HERE / 'alerts.csv', result['alert_rows'], [
        'task', 'date', 'index', 'status', 'pivot_date', 'score', 'threshold', 'excess',
    ])
    save_figures(result)
    write_artifact_manifest()


def main() -> None:
    unknown = [arg for arg in sys.argv[1:] if arg != '--write-plan-only']
    if unknown:
        raise SystemExit('unknown arguments: ' + ' '.join(unknown))
    if '--write-plan-only' in sys.argv:
        write_plan_only()
        return
    plan = assert_plan_frozen()
    self_test_clock()
    self_test_peak()
    self_test_expanding()
    base = load_base()
    if (base.D[0], base.D[-1], base.N) != ('2011-08-02', '2026-08-25', 3659):
        raise SystemExit('research calendar does not match the canonical table')
    closes = np.asarray(base.C, dtype=float)
    frozen = assert_price_matrix(base, closes)
    baseline_lock = assert_baseline_replay(base)
    eligible, targets = load_cohort(base, plan)
    assert_p1_profile(base, eligible, targets)
    for task in TASKS:
        for pivot in targets[task]:
            if not np.allclose(frozen[pivot], price_row(closes, pivot - 1), atol=1e-8, rtol=0):
                raise SystemExit('offset 0 feature does not use the previous close')
            if not np.allclose(frozen[pivot + 1], price_row(closes, pivot), atol=1e-8, rtol=0):
                raise SystemExit('offset +1 feature does not use the pivot close')
    scores = build_scores(plan, frozen)
    # Spot-check the expanding formula on the real matrix at two dates.
    raw = frozen[:, [1, 3, 4, 5]]
    signs = sign_vector(plan, '5_TOP')
    for index in (400, 1073, 2500):
        count, mu, sd = moments_at(raw, index)
        expect = float(np.dot(signs, (raw[index] - mu) / sd))
        if abs(float(scores['5_TOP'][index]) - expect) > 1e-8:
            raise SystemExit(f'production score drifted from the slice formula at {index}')
        if count != index - 252:
            raise SystemExit('history row count is not the strict past')
    result = measure(base, plan, frozen, scores, eligible, targets)
    plan_sha = sha256_file(HERE / 'plan.json')
    write_outputs(result, plan_sha, baseline_lock)
    print(json.dumps({
        'decision': result['decision'],
        'n_pass': result['n_pass'],
        'mean_peak_offsets': {task: result['tasks'][task]['mean_peak_offsets'] for task in TASKS},
        'tail_peak_offsets': {task: result['tasks'][task]['tail_peak_offsets'] for task in TASKS},
        'formal_signal_allowed': False,
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
