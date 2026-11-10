"""P4a: admit at most one non-price family, and only with disclosure timestamps.

Write the plan before any evidence file is interpreted. This path hashes the
listed sources and does not read their fields:

    python -B audit.py --write-plan-only

Then audit the files named in the plan. The script refuses to start without
plan.json and refuses to rewrite the plan:

    python -B audit.py

No family is fit here. A passing gate aborts, because the comparison is not
implemented until a family actually passes.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SHANGHAI = ZoneInfo('Asia/Shanghai')
TASKS = ('5_TOP', '5_BOTTOM', '9_TOP', '9_BOTTOM')
CALENDAR_START = '2011-08-02'
CALENDAR_END = '2026-08-25'
CALENDAR_ROWS = 3659
PREOPEN_HOUR = 9
PREOPEN_MINUTE = 15

DISCLOSURE_KEYS = (
    'publishTime',
    'publishedAt',
    'disclosureTime',
    'announcementTime',
    'firstAvailableTime',
    'visibleAt',
    'releaseTime',
    'publication_time',
    'disclosure_timestamp',
    'published_at',
    'visible_at',
    'release_time',
    '公布时间',
    '披露时间',
    '发布时间',
    '最早可用时间',
)
CAPTURE_KEYS = (
    'request_started_at_utc',
    'response_completed_at_utc',
    'first_captured_at_utc',
)
DISCLOSURE_COLUMNS = DISCLOSURE_KEYS

SOURCE_FILES = (
    'ACTIVE_RESEARCH_CONTRACT.json',
    'turning-research-canonical/tables/research_inputs.csv',
    'turning-research-canonical/tables/field_lineage.csv',
    'turning-research-canonical/source_policy.json',
    'turning-research-canonical/turnover_selection_audit.json',
    'turning-research-canonical/README.md',
    'turning-research-canonical/raw/official/000985_20110802_20260825.receipt.json',
    'turning-research-canonical/raw/official/000985_20110802_20260825.response.json',
    'turning-research-canonical/raw/official/000300_20110802_20260825.receipt.json',
    'turning-research-canonical/raw/official/000300_20110802_20260825.response.json',
    'turning-research-canonical/raw/official/000852_20110802_20260825.receipt.json',
    'turning-research-canonical/raw/official/000852_20110802_20260825.response.json',
    'turning-research-canonical/raw/turnover/ifind_definition_request.json',
    'turning-research-canonical/raw/turnover/float_a_history/repair_2020-03-17_2020-03-17.json',
    'turning-raw-reacquired/README.md',
    'turning-raw-reacquired/data_dictionary.json',
    'turning-raw-reacquired/tables/field_lineage.csv',
    'turning-raw-reacquired/tables/financing_sh_sz.csv',
    'A-share-top-monitor-history/ifind_financing/2022-02-23_2022-03-31_raw.json',
    'A-share-top-monitor-history/完整数据需求清单.md',
    'A-share-top-monitor-history/补数验收说明.md',
    'A-share-top-monitor-history/research/v92_margin_recovery/records/2024-06-26/SSE.json',
    'A-share-top-monitor-history/research/v92_margin_recovery/raw/SSE/2024-06-26.csv',
    'dual80-research/label_clock_v4/rank_metrics.csv',
    'dual80-research/p1_score_alignment/decision.json',
    'dual80-research/p1b_feature_timing/decision.json',
    'dual80-research/p1c_slow_feature_score/decision.json',
    'dual80-research/p1d_fire_timing/decision.json',
    'dual80-research/broad_experiments_v2/失败原因与优化建议_20261102.md',
    'turning-rebuild/prepare_data.py',
    'turning-rebuild/sources/a_share_5_9_daily_reconstruction.csv',
)

ADMISSION_ORDER = ('financing_balance', 'turnover_rate', 'market_breadth')
STATUS_ENUM = (
    'ADMITTED',
    'QUEUED_NOT_RUN',
    'RESEARCH_ONLY',
    'CITED_NOT_RERUN',
    'CONTROL_NOT_A_TARGET',
    'NOT_A_CANDIDATE',
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def source_hashes() -> dict[str, str]:
    return {rel: sha256_file(ROOT / rel) for rel in SOURCE_FILES}


def preopen_deadline(session: date) -> datetime:
    return datetime(session.year, session.month, session.day, PREOPEN_HOUR, PREOPEN_MINUTE, tzinfo=SHANGHAI)


def disclosure_visible(observation: date, disclosed: datetime, decision: date) -> bool:
    """observation_date < D, and the clock is strictly before D pre-open."""
    if disclosed.tzinfo is None:
        return False
    return observation < decision and disclosed.astimezone(SHANGHAI) < preopen_deadline(decision)


def core_plan() -> dict:
    return {
        'phase': 'P4a',
        'title': 'Which stored non-price family has a disclosure timestamp before the D pre-open?',
        'contains_measurements': False,
        'hypothesis': (
            'P1d found that both frozen scores are WEAK: most misses never entered the causal tail '
            'inside offsets -6..0. The next step named there is a feature outside the price family, '
            'gated on point-in-time availability. This phase only decides whether any non-price family '
            'already stored or already documented in this repository passes that gate. It does not search '
            'for a dual-80 result.'
        ),
        'freeze': {
            'index': '000985.CSI',
            'style_controls': ['000300', '000852'],
            'style_controls_are_not_targets': True,
            'label': 'close',
            'tasks': list(TASKS),
            'decision_clock': (
                'Pre-open on research session D. The deadline is 09:15 Asia/Shanghai on D, '
                'the start of the opening call auction, before the 09:30 continuous open.'
            ),
            'observation_rule': (
                'A used field is visible only when its observation_date is a research session strictly '
                'before D and its disclosure timestamp is strictly earlier than that deadline. A tradeDate '
                'equal to D is the session being decided. A tradeDate of D-1 without a disclosure timestamp '
                'is not proof.'
            ),
            'calendar': {
                'file': 'turning-research-canonical/tables/research_inputs.csv',
                'start': CALENDAR_START,
                'end': CALENDAR_END,
                'rows': CALENDAR_ROWS,
            },
            'cohort_if_a_comparison_runs': 'The same close-label mature cohort as label_clock_v4 rank_replay and P1. Not used unless a family is admitted.',
            'formal_signal_allowed': False,
            'blind_test': False,
            'PIT_certified': False,
            'production_changed': False,
            'refit_six_feature_model': False,
            'fast_features_added': False,
            'threshold_search': False,
            'p2_alert_compression': False,
            'early_fire_implemented': False,
            'new_external_download': False,
            'prior_decisions_unchanged': {
                'P1': 'BLOCKED_NO_CONCENTRATION',
                'P1b': 'GO_PRE_PIVOT_COORDINATE',
                'P1c': 'BLOCKED_NO_WINDOW_PEAK',
                'P1d': 'GO_NEW_FACTORS',
            },
        },
        'admission_gate': {
            'default_status': 'RESEARCH_ONLY',
            'admit_only_with_positive_evidence': True,
            'prose_is_not_evidence': (
                'A sentence that says timing is certified does not admit a family. A sentence that says '
                'timing is uncertified is recorded, and it does not replace the missing timestamp file.'
            ),
            'required_for_ADMITTED': [
                'The family role is candidate.',
                'Every field the family would use has a file already in this repository. This phase does not download or scrape a replacement.',
                'Every used field has a structured disclosure timestamp on every research session it would enter. The only structured places that count are a CSV column or a JSON key whose name is on the disclosure allowlist.',
                'Each observation_date is strictly before the decision session D, and each disclosure timestamp is timezone-aware and strictly earlier than 09:15 Asia/Shanghai on D.',
                'Financing, turnover, and market breadth are not exempt from the same proof.',
                'An index aggregate whose membership is documented as uncertified also needs that constituent-scope certification. Timestamps alone do not admit it.',
                'At most one family is admitted. The order is financing_balance, then turnover_rate, then market_breadth. A later passer would be QUEUED_NOT_RUN and would not be fit.',
            ],
            'insufficient_evidence': [
                'The file is absent.',
                'The file has dates and values but no disclosure-allowlist column or key.',
                'The only clocks are capture or request times: request_started_at_utc, response_completed_at_utc, first_captured_at_utc.',
                'Parameter metadata says 最新, including 交易日期 or 截止日期 equal to 最新.',
                'Lineage status is OFFICIAL_HISTORY_NOT_PIT, PROVIDER_HISTORY_NOT_PIT, or PROVIDER_HISTORY_REACQUIRED_NOT_PIT.',
                'source_policy.pit_certified, historical_publication_times_certified, or a record PIT_certified flag is false and no per-session disclosure file supersedes it.',
                'Coverage is a subset of the 3659 research sessions.',
                'A vendor reprint names an exchange as 数据来源, or gives 起始日期 and 终止日期 as series bounds. Those are not disclosure clocks.',
                'An assumed T+0 or T+1 publication lag with no per-session clock.',
                'Style-index levels promoted to a new official target.',
                'Unused raw fields promoted because they sit on a receipt.',
                'A derived table whose construction clock is AFTER_CLOSE.',
            ],
            'disclosure_allowlist': list(DISCLOSURE_KEYS),
            'capture_keys_do_not_count': list(CAPTURE_KEYS),
            'recognized_disclosure_table': {
                'path': 'turning-research-canonical/tables/disclosure_timestamps.csv',
                'required_columns': ['observation_date', 'field', 'disclosure_timestamp'],
                'created_by_this_phase': False,
                'absence_is_a_gap': True,
            },
            'status_enum': list(STATUS_ENUM),
            'status_rule': [
                'excluded_price_family, out_of_scope, and raw_field_not_used are NOT_A_CANDIDATE.',
                'control_not_a_target is CONTROL_NOT_A_TARGET even if timestamps existed.',
                'cited_already_compared is CITED_NOT_RERUN. This phase does not re-run price_amount_style.',
                'A candidate whose gate passes is ADMITTED, except that only the first passer in admission_order is ADMITTED and any later passer is QUEUED_NOT_RUN.',
                'Every other candidate is RESEARCH_ONLY.',
            ],
        },
        'families': [
            {
                'family_id': 'financing_balance',
                'name': 'Shanghai plus Shenzhen financing balance',
                'role': 'candidate',
                'why_in_inventory': 'Full-calendar provider series on the research main table and in financing_sh_sz.csv. Sparse exchange captures exist under v92. Not inside the frozen six-feature price model.',
                'fields_that_would_be_used': ['balance_sh_yuan', 'balance_sz_yuan'],
                'not_auto_admitted': True,
                'constituent_scope_required': False,
            },
            {
                'family_id': 'turnover_rate',
                'name': 'Project-recomputed float-A share turnover, with the vendor native rate kept as a control',
                'role': 'candidate',
                'why_in_inventory': 'turnover_rate is on the research main table. The selected series is official tradingVol divided by an iFinD float-A denominator. Financing and turnover are not auto-admitted.',
                'fields_that_would_be_used': ['official_tradingVol', 'ifind_float_a_shares', 'turnover_rate'],
                'not_auto_admitted': True,
                'constituent_scope_required': True,
            },
            {
                'family_id': 'market_breadth',
                'name': 'Constituent breadth: advance share or new-low share, and the documented C50 path',
                'role': 'candidate',
                'why_in_inventory': 'Named in the current research notes as the participation observation that price, amount, and style do not provide. Documented as not yet collected.',
                'fields_that_would_be_used': [
                    'historical_constituents_including_later_delistings',
                    'halt_and_suspension_status',
                    'advance_or_new_low_counts',
                    'disclosure_timestamps',
                ],
                'not_auto_admitted': True,
                'constituent_scope_required': True,
            },
            {
                'family_id': 'index_trading_amount',
                'name': 'CSI 000985 tradingValue, stored in the column named turnover',
                'role': 'cited_already_compared',
                'why_in_inventory': 'Non-price input already used as the three amount features inside label_clock_v4 price_amount_style. Cite that result. Do not refit it as a new family.',
                'fields_that_would_be_used': ['tradingValue'],
                'not_auto_admitted': True,
                'constituent_scope_required': False,
            },
            {
                'family_id': 'style_index_controls',
                'name': '000300 and 000852 closes, used only as the style ratio',
                'role': 'control_not_a_target',
                'why_in_inventory': 'Already used as the three style features inside price_amount_style. They stay style controls. They are not a new official target and not a new family.',
                'fields_that_would_be_used': ['hs300_close', 'zz1000_close'],
                'not_auto_admitted': True,
                'constituent_scope_required': False,
            },
            {
                'family_id': 'official_peg',
                'name': 'peg on the official index receipt',
                'role': 'raw_field_not_used',
                'why_in_inventory': 'The key is present on the official 000985 row. It is not a research-input column and it is not a documented research family.',
                'fields_that_would_be_used': ['peg'],
                'not_auto_admitted': True,
                'constituent_scope_required': False,
            },
            {
                'family_id': 'official_constituent_count',
                'name': 'consNumber on the official index receipt',
                'role': 'raw_field_not_used',
                'why_in_inventory': 'A constituent count shipped on the same official row. It is not the documented advance or new-low breadth family, and it is not used as a feature.',
                'fields_that_would_be_used': ['consNumber'],
                'not_auto_admitted': True,
                'constituent_scope_required': True,
            },
            {
                'family_id': 'price_transforms',
                'name': 'Returns, distances, range position, realized volatility, interactions, and swing state',
                'role': 'excluded_price_family',
                'why_in_inventory': 'These are the frozen price family and its transforms. P1 through P1d already cover them. They are listed so this inventory does not treat them as new non-price information.',
                'fields_that_would_be_used': [],
                'not_auto_admitted': True,
                'constituent_scope_required': False,
            },
            {
                'family_id': 'named_outside_minimum_set',
                'name': 'News, financial statements, macro, fund flow, level-2, and minute bars',
                'role': 'out_of_scope',
                'why_in_inventory': 'The data-requirements note says these are not part of the current minimum set. They are not research data already used here.',
                'fields_that_would_be_used': [],
                'not_auto_admitted': True,
                'constituent_scope_required': False,
            },
        ],
        'derived_columns_are_not_new_families': {
            'file': 'turning-rebuild/sources/a_share_5_9_daily_reconstruction.csv',
            'examples': [
                'turnover_amt_p252_pct',
                'turnover_rate_p252_pct',
                'style_dd20_pct',
                'finance_63d_growth_p756_pct',
                'rv_p756_pct',
            ],
            'clock_file': 'turning-rebuild/prepare_data.py',
            'clock_sentence': 'AFTER_CLOSE: uses same-day close; NOT D-day preopen',
            'rule': 'A percentile or growth rate of an unadmitted family stays unadmitted. An after-close construction is not a pre-open feature.',
        },
        'citation_not_a_rerun': {
            'experiment': 'dual80-research/label_clock_v4',
            'file': 'dual80-research/label_clock_v4/rank_metrics.csv',
            'rows': 'label close, groups price__past_rank90 and price_amount_style__past_rank90',
            'rule': (
                'Copy the stored precision and recall. Do not refit. The displayed baseline stayed on the '
                'price group. Mixed task-level differences are not a reason to reopen amount or style, and '
                'they are not an admission gate.'
            ),
        },
        'conditional_comparison': {
            'implemented': False,
            'runs_only_if_decision': 'ADMITTED_ONE_FAMILY',
            'at_most_one_family': True,
            'admission_order': list(ADMISSION_ORDER),
            'baseline': 'Frozen label_clock_v4 close x six price features x past_rank90. The logistic model is not refit.',
            'same_calendar': 'research_inputs.csv',
            'same_targets': 'close labels, four tasks, the P1 mature cohort',
            'same_fire_rule': 'past_rank90, lookback 252, minimum 126 earlier scores, quantile 0.90, current score excluded, lock through offset +6',
            'placement': 'Beside the frozen baseline. Not inside the six-feature logistic model. Amount and style are not added. The two fast price features are not added.',
            'no_threshold_search': True,
            'no_dual80_search': True,
            'no_future_target_quota': True,
            'financing_if_admitted': {
                'fields': ['balance_sh_yuan', 'balance_sz_yuan'],
                'transform': (
                    '63-session log change of the sum. A session enters only when both balances have certified '
                    'disclosure timestamps before that decision pre-open. No other lag is assumed. No 756-session '
                    'percentile and no window search.'
                ),
                'score': (
                    'That single series as an expanding causal z-score. The economic sign, written before any '
                    'financing lead profile, is positive for tops and negative for bottoms: rising financing '
                    'raises the top score and falling financing raises the bottom score. Fired with past_rank90.'
                ),
            },
            'turnover_if_admitted': {
                'fields': ['turnover_rate'],
                'transform': 'The recomputed level itself. No percentile-window search and no second formula.',
                'score': 'Expanding causal z-score, positive for tops and negative for bottoms, past_rank90, beside the baseline.',
            },
            'breadth_if_admitted': {
                'transform': 'Not defined. The family cannot pass until the missing files exist. This plan does not invent the formula.',
            },
            'report_if_run': [
                'Precision and recall against the frozen baseline on each of the four close tasks.',
                'Lead-profile peak offset of the mean score on the same -6..+6 grid used in P1.',
            ],
            'beat_baseline_only_if': (
                'Precision and recall are both strictly higher on at least 3 of 4 tasks, and the mean-score '
                'peak lies in -6..0 on at least 3 of 4 tasks. If the peak remains at +1, or the metrics do not '
                'clear that bar, say so. Do not try a second transform.'
            ),
        },
        'next_step_if_none_admitted': {
            'implemented': False,
            'name': 'collect_financing_disclosure_timestamps',
            'why_this_family': (
                'It is the first candidate in the fixed order. A full-calendar file is already in the repository, '
                'it is outside the frozen price model, and it was not part of the price_amount_style comparison. '
                'Turnover stays second because its float-A denominator is still marked 最新 and its constituent '
                'scope is uncertified, so timestamps alone would not admit it. Breadth stays blocked on missing '
                'constituent, halt, and breadth files. Amount and style stay cited, not re-run.'
            ),
            'artifact_that_would_be_required': (
                'One row per research date for the Shanghai balance and one row per research date for the '
                'Shenzhen balance. Columns: observation_date, field, disclosure_timestamp. The timestamp must '
                'be timezone-aware and strictly before 09:15 Asia/Shanghai on the next research session. A 2026 '
                'capture time, an iFinD reprint, a 数据来源 label, or a sample of exchange files does not qualify.'
            ),
            'do_not': [
                'Do not scrape or download that file in this phase.',
                'Do not assume a next-morning lag.',
                'Do not fit the 63-session change, or any other transform, while the file is absent.',
                'Do not collect breadth or a new external series in this phase.',
            ],
        },
        'leakage': [
            'Using the decision session close, amount, volume, turnover, financing balance, peg, or constituent count at that same pre-open.',
            'Treating a download clock or a 最新 parameter as a historical disclosure time.',
            'Treating 数据来源, 起始日期, or 终止日期 as a disclosure time.',
            'Admitting a family from a subset of dates.',
            'Assuming a publication lag that is not written as a per-session clock.',
            'Choosing which family to fit after seeing a lead profile or a precision number.',
            'Re-running price_amount_style, refitting the six price features, or putting the two fast price features back.',
            'Opening P2, raising the 0.90 quantile, or using a future target count as an alert quota.',
            'Changing the label, the official index, or the hit window.',
            'Promoting 000300 or 000852 from a style control to the official target.',
            'Backfilling breadth from the names that are listed today.',
            'Editing this plan after the evidence counts are known.',
        ],
        'out_of_scope': [
            'No production page, collector, official signal, or V-series workflow.',
            'No new external dataset.',
            'No label change and no index change.',
            'No D-day feature.',
            'formal_signal_allowed stays false.',
            'Not PIT and not a blind test. Not dual-80.',
            'P1, P1b, P1c, and P1d conclusions are not rewritten.',
        ],
        'decision_rule': [
            'BLOCKED_PLAN_MISMATCH if the frozen plan, the contract, or a prior decision file disagrees with this pre-registration. Abort before a decision.',
            'ADMITTED_ONE_FAMILY if one candidate passes the gate. Then, and only then, run the single pre-registered comparison. This implementation aborts instead of fitting, so a pass cannot silently skip the comparison or invent a second transform.',
            'NO_FAMILY_ADMITTED if no candidate passes. Report the inventory and the missing evidence. Name the financing disclosure-timestamp collection. Do not implement it.',
        ],
    }


def build_plan() -> dict:
    plan = json.loads(json.dumps(core_plan()))
    plan['source_sha256'] = source_hashes()
    return plan


def write_plan_only() -> None:
    path = HERE / 'plan.json'
    if path.exists():
        raise SystemExit('plan.json already exists and is not rewritten')
    path.write_text(json.dumps(build_plan(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'wrote': 'dual80-research/p4a_factor_admission/plan.json', 'contains_measurements': False}, ensure_ascii=False))


def assert_plan_frozen() -> dict:
    path = HERE / 'plan.json'
    if not path.exists():
        raise SystemExit('plan.json is missing. Run: python -B audit.py --write-plan-only')
    on_disk = json.loads(path.read_text(encoding='utf-8'))
    core_on_disk = {key: value for key, value in on_disk.items() if key != 'source_sha256'}
    if core_on_disk != core_plan():
        raise SystemExit('plan.json core does not match the pre-registered core in audit.py')
    if on_disk.get('contains_measurements') is not False:
        raise SystemExit('plan.json must not contain measurements')
    if on_disk.get('source_sha256') != source_hashes():
        raise SystemExit('source files changed after plan.json was written')
    return on_disk


def self_test() -> None:
    plan = core_plan()
    if plan['contains_measurements'] is not False:
        raise SystemExit('plan core must not contain measurements')
    if tuple(plan['conditional_comparison']['admission_order']) != ADMISSION_ORDER:
        raise SystemExit('admission order drifted')
    if set(DISCLOSURE_KEYS) & set(CAPTURE_KEYS):
        raise SystemExit('disclosure keys and capture keys overlap')
    roles = {item['family_id']: item['role'] for item in plan['families']}
    for family_id in ADMISSION_ORDER:
        if roles[family_id] != 'candidate':
            raise SystemExit(f'{family_id} must stay a candidate')
    if roles['style_index_controls'] == 'candidate' or roles['index_trading_amount'] == 'candidate':
        raise SystemExit('style controls and traded amount are not admission candidates')
    if plan['conditional_comparison']['implemented'] is not False:
        raise SystemExit('the comparison must stay unimplemented in the plan')
    visible = disclosure_visible(date(2024, 6, 26), datetime(2024, 6, 26, 16, 0, tzinfo=SHANGHAI), date(2024, 6, 27))
    too_late = disclosure_visible(date(2024, 6, 26), datetime(2024, 6, 27, 9, 15, tzinfo=SHANGHAI), date(2024, 6, 27))
    just_early = disclosure_visible(date(2024, 6, 26), datetime(2024, 6, 27, 9, 14, tzinfo=SHANGHAI), date(2024, 6, 27))
    downloaded_later = disclosure_visible(date(2024, 6, 26), datetime(2026, 10, 21, tzinfo=SHANGHAI), date(2024, 6, 27))
    same_day = disclosure_visible(date(2024, 6, 27), datetime(2024, 6, 26, 16, 0, tzinfo=SHANGHAI), date(2024, 6, 27))
    naive = disclosure_visible(date(2024, 6, 26), datetime(2024, 6, 26, 16, 0), date(2024, 6, 27))
    if [visible, too_late, just_early, downloaded_later, same_day, naive] != [True, False, True, False, False, False]:
        raise SystemExit('pre-open clock self-test failed')
    for rel in SOURCE_FILES:
        if not (ROOT / rel).is_file():
            raise SystemExit(f'missing source file {rel}')


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def walk_keys(obj, found: set[str]) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            found.add(str(key))
            walk_keys(value, found)
    elif isinstance(obj, list):
        for item in obj:
            walk_keys(item, found)
    elif isinstance(obj, str) and obj[:1] in '{[':
        try:
            parsed = json.loads(obj)
        except json.JSONDecodeError:
            return
        walk_keys(parsed, found)


def disclosure_keys_in(keys) -> list[str]:
    return sorted(key for key in keys if key in DISCLOSURE_KEYS)


def csv_header_and_dates(path: Path, date_column: str) -> dict:
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        if date_column not in columns:
            raise SystemExit(f'{path} has no {date_column} column')
        dates = []
        filled = {column: 0 for column in columns if column != date_column}
        for row in reader:
            dates.append(row[date_column])
            for column in filled:
                if row[column] != '':
                    filled[column] += 1
    return {
        'path': str(path.relative_to(ROOT)),
        'columns': columns,
        'disclosure_columns': disclosure_keys_in(columns),
        'rows': len(dates),
        'unique_dates': len(set(dates)),
        'start': dates[0] if dates else None,
        'end': dates[-1] if dates else None,
        'nonempty_counts': filled,
    }


def research_calendar(path: Path) -> list[date]:
    info = csv_header_and_dates(path, 'date')
    expected = ['date', 'all_a_close', 'hs300_close', 'zz1000_close', 'turnover', 'turnover_rate', 'financing_balance']
    if info['columns'] != expected:
        raise SystemExit(f'research_inputs columns changed: {info["columns"]}')
    dates = [date.fromisoformat(item) for item in _date_list(path)]
    if [dates[0].isoformat(), dates[-1].isoformat(), len(dates), len(set(dates))] != [CALENDAR_START, CALENDAR_END, CALENDAR_ROWS, CALENDAR_ROWS]:
        raise SystemExit('research calendar does not match the frozen 3659-session table')
    if any(dates[index] >= dates[index + 1] for index in range(len(dates) - 1)):
        raise SystemExit('research calendar is not strictly increasing')
    info['dates'] = dates
    return info


def _date_list(path: Path) -> list[str]:
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return [row['date'] for row in csv.DictReader(handle)]


def lineage_counts(path: Path) -> dict:
    counts: dict[str, Counter] = {}
    rows = 0
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        if 'field' not in columns or 'status' not in columns:
            raise SystemExit(f'{path} has no field/status lineage')
        for row in reader:
            rows += 1
            counts.setdefault(row['field'], Counter())[row['status']] += 1
    return {
        'path': str(path.relative_to(ROOT)),
        'columns': columns,
        'disclosure_columns': disclosure_keys_in(columns),
        'rows': rows,
        'by_field': {field: dict(counter) for field, counter in sorted(counts.items())},
    }


def official_response_schema(path: Path) -> dict:
    payload = load_json(path)
    rows = payload['data']
    keys = list(rows[0].keys())
    keyset = set(keys)
    mismatches = 0
    null_cons = 0
    null_peg = 0
    for row in rows:
        if set(row) != keyset:
            mismatches += 1
        if row.get('consNumber') is None:
            null_cons += 1
        if row.get('peg') is None:
            null_peg += 1
    return {
        'path': str(path.relative_to(ROOT)),
        'top_level_keys': list(payload.keys()),
        'row_keys': keys,
        'disclosure_keys': disclosure_keys_in(list(payload.keys()) + keys),
        'rows': len(rows),
        'key_mismatches': mismatches,
        'null_consNumber': null_cons if 'consNumber' in keyset else None,
        'null_peg': null_peg if 'peg' in keyset else None,
    }


def official_receipt(path: Path) -> dict:
    payload = load_json(path)
    keys = list(payload.keys())
    return {
        'path': str(path.relative_to(ROOT)),
        'keys': keys,
        'disclosure_keys': disclosure_keys_in(keys),
        'request_started_at_utc': payload.get('request_started_at_utc'),
        'response_completed_at_utc': payload.get('response_completed_at_utc'),
        'source_url': payload.get('source_url'),
    }


def nested_latest_flags(path: Path) -> dict:
    text = path.read_text(encoding='utf-8')
    return {
        'path': str(path.relative_to(ROOT)),
        'contains_latest_token': '最新' in text,
        'trade_date_latest': '交易日期\\":\\"最新' in text or '"交易日期":"最新"' in text or '交易日期":"最新' in text,
        'cutoff_latest': '截止日期\\":\\"最新' in text or '"截止日期":"最新"' in text or '截止日期":"最新' in text,
    }


def file_has_sentence(path: Path, sentence: str) -> bool:
    return sentence in path.read_text(encoding='utf-8')


def python_mentions(token: str) -> list[str]:
    hits = []
    for path in ROOT.rglob('*.py'):
        if '.git' in path.parts or '__pycache__' in path.parts:
            continue
        if HERE in path.parents or path.parent == HERE:
            continue
        if token in path.read_text(encoding='utf-8-sig'):
            hits.append(str(path.relative_to(ROOT)))
    return sorted(hits)


def filename_hits(patterns: tuple[str, ...]) -> list[str]:
    found = []
    for pattern in patterns:
        for path in ROOT.rglob(pattern):
            if '.git' in path.parts or '__pycache__' in path.parts:
                continue
            if HERE in path.parents or path.parent == HERE:
                continue
            found.append(str(path.relative_to(ROOT)))
    return sorted(set(found))


def v92_exchange_capture() -> dict:
    base = ROOT / 'A-share-top-monitor-history' / 'research' / 'v92_margin_recovery'
    records = []
    pit_values = Counter()
    formal_values = Counter()
    clock_fields = Counter()
    capture_times = []
    for path in sorted((base / 'records').glob('*/*.json')):
        payload = load_json(path)
        keys = list(payload.keys())
        pit = payload.get('PIT_certified')
        pit_values[str(pit)] += 1
        formal_values[str(payload.get('formal_signal_allowed'))] += 1
        if payload.get('first_captured_at_utc'):
            clock_field = 'first_captured_at_utc'
        elif payload.get('source_run_started_at_utc'):
            clock_field = 'source_run_started_at_utc'
        else:
            clock_field = ''
        captured = payload.get(clock_field) if clock_field else None
        clock_fields[clock_field or 'none'] += 1
        if captured:
            capture_times.append(captured)
        records.append({
            'path': str(path.relative_to(ROOT)),
            'sha256': sha256_file(path),
            'date': payload.get('date'),
            'exchange': payload.get('exchange'),
            'keys': keys,
            'disclosure_keys': disclosure_keys_in(keys),
            'PIT_certified': pit,
            'formal_signal_allowed': payload.get('formal_signal_allowed'),
            'capture_clock_field': clock_field or None,
            'capture_clock': captured,
            'date_provenance': payload.get('date_provenance'),
            'jin10_status': (payload.get('Jin10_comparison') or {}).get('status'),
        })
    raw_headers = {}
    raw_counts = Counter()
    for path in sorted((base / 'raw').glob('*/*.csv')):
        exchange = path.parent.name
        raw_counts[exchange] += 1
        with path.open(encoding='utf-8-sig', newline='') as handle:
            header = handle.readline().strip()
        raw_headers.setdefault(exchange, set()).add(header)
    return {
        'record_files': len(records),
        'unique_dates': sorted({item['date'] for item in records}),
        'pit_certified_values': dict(pit_values),
        'formal_signal_allowed_values': dict(formal_values),
        'capture_clock_fields': dict(clock_fields),
        'disclosure_key_hits': sorted({key for item in records for key in item['disclosure_keys']}),
        'capture_time_min': min(capture_times) if capture_times else None,
        'capture_time_max': max(capture_times) if capture_times else None,
        'capture_before_preopen': 0,
        'raw_csv_counts': dict(raw_counts),
        'raw_headers': {exchange: sorted(headers) for exchange, headers in raw_headers.items()},
        'records': records,
    }


def mark_capture_against_calendar(v92: dict, nxt: dict[date, date]) -> None:
    before = 0
    for item in v92['records']:
        observed = date.fromisoformat(item['date'])
        captured_text = item['capture_clock']
        captured = datetime.fromisoformat(captured_text.replace('Z', '+00:00')) if captured_text else None
        decision = nxt.get(observed)
        item['capture_is_disclosure'] = False
        item['capture_before_next_preopen'] = bool(captured and decision and disclosure_visible(observed, captured, decision))
        before += int(item['capture_before_next_preopen'])
    v92['capture_before_preopen'] = before


def ifind_financing_keys() -> dict:
    directory = ROOT / 'A-share-top-monitor-history' / 'ifind_financing'
    files = sorted(directory.glob('*_raw.json'))
    keys: set[str] = set()
    disclosure_hits = []
    for path in files:
        found: set[str] = set()
        walk_keys(load_json(path), found)
        keys.update(found)
        hit = disclosure_keys_in(found)
        if hit:
            disclosure_hits.append({'path': str(path.relative_to(ROOT)), 'keys': hit})
    return {
        'files': len(files),
        'keys': sorted(keys),
        'disclosure_key_hits': disclosure_hits,
        'source_name_key_present': '数据来源' in keys,
        'coverage_bound_keys_present': sorted(key for key in ('起始日期', '终止日期') if key in keys),
    }


def cite_rank_metrics(path: Path) -> list[dict]:
    wanted = {'price__past_rank90', 'price_amount_style__past_rank90'}
    rows = []
    with path.open(encoding='utf-8-sig', newline='') as handle:
        for row in csv.DictReader(handle):
            if row['label'] == 'close' and row['group'] in wanted and row['task'] in TASKS:
                rows.append({
                    'task': row['task'],
                    'group': row['group'],
                    'precision': float(row['precision']),
                    'recall': float(row['recall']),
                    'TP': int(row['TP']),
                    'FP': int(row['FP']),
                    'FN': int(row['FN']),
                    'alerts': int(row['alerts']),
                    'targets': int(row['targets']),
                    'dual80': row['dual80'] == 'True',
                })
    order = {task: index for index, task in enumerate(TASKS)}
    rows.sort(key=lambda item: (order[item['task']], item['group']))
    if len(rows) != 8 or any(item['dual80'] for item in rows):
        raise SystemExit('close past_rank90 citation rows are not the frozen eight, or one of them claims dual-80')
    return rows


def prior_decision_codes() -> dict[str, str]:
    paths = {
        'P1': 'dual80-research/p1_score_alignment/decision.json',
        'P1b': 'dual80-research/p1b_feature_timing/decision.json',
        'P1c': 'dual80-research/p1c_slow_feature_score/decision.json',
        'P1d': 'dual80-research/p1d_fire_timing/decision.json',
    }
    return {name: load_json(ROOT / rel)['decision'] for name, rel in paths.items()}


def gap(family_id: str, block: str, path: str, found: str, detail: str) -> dict:
    return {'family_id': family_id, 'block': block, 'path': path, 'found': found, 'detail': detail}


def measure(plan: dict) -> dict:
    contract = load_json(ROOT / 'ACTIVE_RESEARCH_CONTRACT.json')
    if contract.get('production_updated') is not False:
        raise SystemExit('contract production_updated is not false')
    primary = str(contract.get('primary_index', ''))
    if not primary.startswith('000985.CSI') or '000300/000852' not in primary:
        raise SystemExit('contract primary index changed')
    if contract['user_confirmed_window']['minimum_lead_sessions'] != 0 or contract['user_confirmed_window']['maximum_lead_sessions'] != 6:
        raise SystemExit('contract window changed')
    priors = prior_decision_codes()
    if priors != plan['freeze']['prior_decisions_unchanged']:
        raise SystemExit(f'prior decisions changed: {priors}')

    calendar_info = research_calendar(ROOT / 'turning-research-canonical/tables/research_inputs.csv')
    dates: list[date] = calendar_info.pop('dates')
    nxt = {dates[index]: dates[index + 1] for index in range(len(dates) - 1)}
    canonical_lineage = lineage_counts(ROOT / 'turning-research-canonical/tables/field_lineage.csv')
    reacquired_lineage = lineage_counts(ROOT / 'turning-raw-reacquired/tables/field_lineage.csv')
    financing_table = csv_header_and_dates(ROOT / 'turning-raw-reacquired/tables/financing_sh_sz.csv', 'date')
    policy = load_json(ROOT / 'turning-research-canonical/source_policy.json')
    turnover_audit = load_json(ROOT / 'turning-research-canonical/turnover_selection_audit.json')
    receipts = {
        code: official_receipt(ROOT / f'turning-research-canonical/raw/official/{code}_20110802_20260825.receipt.json')
        for code in ('000985', '000300', '000852')
    }
    responses = {
        code: official_response_schema(ROOT / f'turning-research-canonical/raw/official/{code}_20110802_20260825.response.json')
        for code in ('000985', '000300', '000852')
    }
    latest_flags = {
        'ifind_definition_request': nested_latest_flags(ROOT / 'turning-research-canonical/raw/turnover/ifind_definition_request.json'),
        'float_a_repair_2020_03_17': nested_latest_flags(ROOT / 'turning-research-canonical/raw/turnover/float_a_history/repair_2020-03-17_2020-03-17.json'),
    }
    sentences = {
        'turnover_readme_uncertified': file_has_sentence(
            ROOT / 'turning-research-canonical/README.md',
            '没有认证历史发布时点或数据修订版本',
        ),
        'reacquired_readme_uncertified': file_has_sentence(
            ROOT / 'turning-raw-reacquired/README.md',
            '历史实际发布时间、官方日历以及供应商修订版本尚未完整认证',
        ),
        'financing_note_uncertified': file_has_sentence(
            ROOT / 'A-share-top-monitor-history/补数验收说明.md',
            '历史实际发布时间、历史修订版本和官方交易日历尚未认证',
        ),
        'requirements_name_breadth_gap': file_has_sentence(
            ROOT / 'A-share-top-monitor-history/完整数据需求清单.md',
            '其余分组尚未完成全区间验收',
        ),
        'breadth_named_as_future_work': file_has_sentence(
            ROOT / 'dual80-research/broad_experiments_v2/失败原因与优化建议_20261102.md',
            '必须先认证当时成分、退市、停牌及开盘前发布时点',
        ),
        'zz1000_backcast_note': file_has_sentence(
            ROOT / 'turning-raw-reacquired/data_dictionary.json',
            '发布前追溯序列不证明当时已知',
        ),
    }
    if not all(sentences.values()):
        missing = [name for name, found in sentences.items() if not found]
        raise SystemExit(f'documented limit sentences missing: {missing}')
    v92 = v92_exchange_capture()
    mark_capture_against_calendar(v92, nxt)
    ifind_keys = ifind_financing_keys()
    disclosure_table = ROOT / 'turning-research-canonical/tables/disclosure_timestamps.csv'
    breadth_paths = filename_hits((
        '*constituent*', '*breadth*', '*c50*', '*C50*', '*advance*decline*',
        '*new_high*', '*new_low*', '*newhigh*', '*newlow*',
        '*涨跌*', '*广度*', '*成分*', '*停牌*', '*停复牌*',
    ))
    outside_paths = filename_hits(('*northbound*', '*fund_flow*', '*资金流*', '*宏观*', '*level2*', '*minute*bar*'))
    derived_header = []
    with (ROOT / 'turning-rebuild/sources/a_share_5_9_daily_reconstruction.csv').open(encoding='utf-8-sig') as handle:
        derived_header = handle.readline().strip().split(',')
    derived_clock = file_has_sentence(ROOT / 'turning-rebuild/prepare_data.py', 'NOT D-day preopen') and file_has_sentence(
        ROOT / 'turning-rebuild/prepare_data.py', 'AFTER_CLOSE'
    )
    if not derived_clock:
        raise SystemExit('prepare_data.py no longer states the AFTER_CLOSE clock')
    cited = cite_rank_metrics(ROOT / 'dual80-research/label_clock_v4/rank_metrics.csv')
    peg_mentions = python_mentions('peg')
    cons_mentions = python_mentions('consNumber')

    gaps = []
    amount_status = canonical_lineage['by_field'].get('turnover', {})
    financing_status = canonical_lineage['by_field'].get('financing_balance', {})
    reacquired_financing = reacquired_lineage['by_field'].get('financing_balance', {})
    style_status = {
        'hs300_close': canonical_lineage['by_field'].get('hs300_close', {}),
        'zz1000_close': canonical_lineage['by_field'].get('zz1000_close', {}),
    }

    def add_common_official_blocks(family_id: str, fields: tuple[str, ...]) -> None:
        for field in fields:
            status = canonical_lineage['by_field'].get(field, {})
            gaps.append(gap(
                family_id, 'LINEAGE_NOT_PIT', canonical_lineage['path'], str(status),
                f'{field} lineage status counts are {status}',
            ))
        relevant = ('000985',) if family_id == 'index_trading_amount' else ('000300', '000852')
        for code in relevant:
            receipt = receipts[code]
            response = responses[code]
            gaps.append(gap(
                family_id, 'CAPTURE_TIME_NOT_DISCLOSURE', receipt['path'],
                f"{receipt['request_started_at_utc']} -> {receipt['response_completed_at_utc']}",
                'Receipt clocks are the 2026 download, not a historical disclosure time.',
            ))
            gaps.append(gap(
                family_id, 'NO_DISCLOSURE_COLUMN', response['path'],
                'none' if not response['disclosure_keys'] else ','.join(response['disclosure_keys']),
                f"Row keys are {', '.join(response['row_keys'])}. tradeDate is the session date.",
            ))

    add_common_official_blocks('index_trading_amount', ('turnover',))
    add_common_official_blocks('style_index_controls', ('hs300_close', 'zz1000_close'))
    gaps.append(gap(
        'index_trading_amount', 'ALREADY_COMPARED', 'dual80-research/label_clock_v4/rank_metrics.csv',
        'cited',
        'price_amount_style was already compared and did not replace the displayed price baseline. Not re-run.',
    ))
    gaps.append(gap(
        'style_index_controls', 'CONTROL_NOT_TARGET', 'ACTIVE_RESEARCH_CONTRACT.json',
        contract['primary_index'],
        '000300 and 000852 stay style controls. They are not a new official target.',
    ))
    gaps.append(gap(
        'style_index_controls', 'BACKCAST_NOT_THEN_KNOWN', 'turning-raw-reacquired/data_dictionary.json',
        f"000852 null consNumber {responses['000852']['null_consNumber']} of {responses['000852']['rows']}",
        'The dictionary says pre-publication backcast values do not prove the level was known then.',
    ))

    gaps.append(gap(
        'financing_balance', 'NO_DISCLOSURE_COLUMN', calendar_info['path'],
        'none' if not calendar_info['disclosure_columns'] else ','.join(calendar_info['disclosure_columns']),
        'Main-table columns are date, closes, turnover (amount), turnover_rate, financing_balance.',
    ))
    gaps.append(gap(
        'financing_balance', 'NO_DISCLOSURE_COLUMN', financing_table['path'],
        'none' if not financing_table['disclosure_columns'] else ','.join(financing_table['disclosure_columns']),
        f"Columns are {', '.join(financing_table['columns'])}. Date coverage is {financing_table['start']} to {financing_table['end']}, {financing_table['rows']} rows.",
    ))
    gaps.append(gap(
        'financing_balance', 'LINEAGE_NOT_PIT', canonical_lineage['path'], str(financing_status),
        'Canonical financing lineage is not a disclosure clock.',
    ))
    gaps.append(gap(
        'financing_balance', 'LINEAGE_NOT_PIT', reacquired_lineage['path'], str(reacquired_financing),
        'Reacquired financing lineage is not a disclosure clock.',
    ))
    gaps.append(gap(
        'financing_balance', 'POLICY_PIT_FALSE', 'turning-research-canonical/source_policy.json',
        str(policy.get('pit_certified')),
        'The source policy says the adopted fields are not PIT-certified.',
    ))
    gaps.append(gap(
        'financing_balance', 'VENDOR_REPRINT_NOT_A_CLOCK', 'A-share-top-monitor-history/ifind_financing',
        f"{ifind_keys['files']} raw files; disclosure hits {len(ifind_keys['disclosure_key_hits'])}",
        'Keys include 数据来源 plus 起始日期 and 终止日期. Those name a source and a coverage bound.',
    ))
    gaps.append(gap(
        'financing_balance', 'PARTIAL_COVERAGE', 'A-share-top-monitor-history/research/v92_margin_recovery/records',
        f"{len(v92['unique_dates'])} of {CALENDAR_ROWS} sessions",
        f"PIT_certified values are {v92['pit_certified_values']}. Capture-clock fields are {v92['capture_clock_fields']}. Those clocks span {v92['capture_time_min']} to {v92['capture_time_max']}. Capture times before the next pre-open: {v92['capture_before_preopen']}.",
    ))
    raw_header_text = '; '.join(f'{exchange}: {headers}' for exchange, headers in sorted(v92['raw_headers'].items()))
    gaps.append(gap(
        'financing_balance', 'NO_DISCLOSURE_COLUMN', 'A-share-top-monitor-history/research/v92_margin_recovery/raw',
        raw_header_text,
        f"CSV counts {v92['raw_csv_counts']}. The SSE header starts with 信用交易日期, which is the observation date. The SZSE header has no date column; the date is the filename. Neither header has a disclosure timestamp. Same-day flow columns on this short window are not a separate family.",
    ))
    gaps.append(gap(
        'financing_balance', 'MISSING_FILE', 'turning-research-canonical/tables/disclosure_timestamps.csv',
        'present' if disclosure_table.is_file() else 'absent',
        'Need one Shanghai row and one Shenzhen row per research date, with a timezone-aware disclosure timestamp before the next 09:15 Asia/Shanghai pre-open.',
    ))

    gaps.append(gap(
        'turnover_rate', 'POLICY_PIT_FALSE', 'turning-research-canonical/turnover_selection_audit.json',
        str(turnover_audit.get('historical_publication_times_certified')),
        'historical_publication_times_certified is false.',
    ))
    gaps.append(gap(
        'turnover_rate', 'CONSTITUENT_SCOPE_UNCERTIFIED', 'turning-research-canonical/turnover_selection_audit.json',
        str(turnover_audit.get('historical_constituents_independently_verified')),
        'The float-A denominator was not rebuilt from a certified constituent list. Timestamps alone would not admit this family.',
    ))
    gaps.append(gap(
        'turnover_rate', 'LATEST_PARAMETER', latest_flags['ifind_definition_request']['path'],
        str(latest_flags['ifind_definition_request']['trade_date_latest']),
        'The native-rate definition request still carries 交易日期 = 最新.',
    ))
    gaps.append(gap(
        'turnover_rate', 'LATEST_PARAMETER', latest_flags['float_a_repair_2020_03_17']['path'],
        str(latest_flags['float_a_repair_2020_03_17']['cutoff_latest']),
        'A float-A repair receipt still carries 截止日期 = 最新.',
    ))
    gaps.append(gap(
        'turnover_rate', 'NO_DISCLOSURE_COLUMN', calendar_info['path'], 'none',
        'turnover_rate is populated on the main table. Population is not a disclosure clock. The official tradingVol numerator is on the same 2026 official receipt as tradingValue.',
    ))
    gaps.append(gap(
        'turnover_rate', 'VENDOR_FORMULA_UNRESOLVED', 'turning-research-canonical/README.md',
        'sentence present',
        'The project-selected rate is not the vendor native formula, and that native formula is unresolved. The README says publication time and revision history were not certified.',
    ))

    gaps.append(gap(
        'market_breadth', 'MISSING_FILE', '(filename search)',
        'none' if not breadth_paths else '; '.join(breadth_paths),
        'No constituent, breadth, C50, advance/decline, new-high, new-low, or halt file is in the repository.',
    ))
    gaps.append(gap(
        'market_breadth', 'CONSTITUENT_SCOPE_UNCERTIFIED', 'A-share-top-monitor-history/完整数据需求清单.md',
        'sentence present',
        'Stock-level bars, the security master, and halt status are documented as not fully accepted. Today’s survivors must not be backfilled.',
    ))
    gaps.append(gap(
        'market_breadth', 'NOT_THE_DOCUMENTED_BREADTH', responses['000985']['path'],
        f"consNumber nulls {responses['000985']['null_consNumber']}",
        'consNumber is a constituent count on the official row, not an advance share or a new-low share.',
    ))

    gaps.append(gap(
        'official_peg', 'RAW_FIELD_UNUSED', responses['000985']['path'],
        f"python mentions excluding this audit: {peg_mentions or 'none'}",
        f"peg is a row key. Disclosure keys: {responses['000985']['disclosure_keys'] or 'none'}. Null peg rows: 000985 {responses['000985']['null_peg']}, 000300 {responses['000300']['null_peg']}, 000852 {responses['000852']['null_peg']}.",
    ))
    gaps.append(gap(
        'official_constituent_count', 'RAW_FIELD_UNUSED', responses['000985']['path'],
        f"python mentions excluding this audit: {cons_mentions or 'none'}",
        'consNumber is unused as a feature and has no disclosure key. It does not stand in for market breadth.',
    ))
    gaps.append(gap(
        'price_transforms', 'EXCLUDED_PRICE_FAMILY', 'dual80-research/p1d_fire_timing/decision.json',
        priors['P1d'],
        'Price transforms stay inside the frozen price family. This phase does not refit them and does not add the two fast features back.',
    ))
    gaps.append(gap(
        'named_outside_minimum_set', 'OUT_OF_SCOPE', 'A-share-top-monitor-history/完整数据需求清单.md',
        'none' if not outside_paths else '; '.join(outside_paths),
        'News, financial statements, macro, fund flow, level-2, and minute bars are named as outside the current minimum set.',
    ))
    gaps.append(gap(
        'financing_balance', 'AFTER_CLOSE_DERIVED', 'turning-rebuild/sources/a_share_5_9_daily_reconstruction.csv',
        'header only',
        'finance_63d_growth_p756_pct, turnover_amt_p252_pct, turnover_rate_p252_pct, and style_dd20_pct are transforms of families already inventoried. prepare_data.py marks that construction AFTER_CLOSE and not D-day pre-open.',
    ))

    required_header = {
        'turnover_amt_p252_pct', 'turnover_rate_p252_pct', 'style_dd20_pct',
        'finance_63d_growth_p756_pct', 'rv_p756_pct',
    }
    if not required_header <= set(derived_header):
        raise SystemExit('reconstruction header is missing a derived column this audit cites')
    if disclosure_table.is_file():
        raise SystemExit('A disclosure table appeared after the plan was frozen. This phase does not create one, and a new file is not admitted without being part of the pre-registered sources.')

    families = []
    admitted = []
    for spec in plan['families']:
        family_id = spec['family_id']
        role = spec['role']
        family_gaps = [item for item in gaps if item['family_id'] == family_id]
        blocking = []
        for item in family_gaps:
            if item['block'] != 'ALREADY_COMPARED' and item['block'] not in blocking:
                blocking.append(item['block'])
        if role == 'candidate':
            passed = not family_gaps
            status = 'ADMITTED' if passed else 'RESEARCH_ONLY'
        elif role == 'control_not_a_target':
            passed = False
            status = 'CONTROL_NOT_A_TARGET'
        elif role == 'cited_already_compared':
            passed = False
            status = 'CITED_NOT_RERUN'
        else:
            passed = False
            status = 'NOT_A_CANDIDATE'
        if status not in STATUS_ENUM:
            raise SystemExit(f'unexpected status {status}')
        if passed:
            admitted.append(family_id)
        families.append({
            'family_id': family_id,
            'name': spec['name'],
            'role': role,
            'eligible_if_evidence_passes': role == 'candidate',
            'gate_passed': passed,
            'status': status,
            'blocks': blocking,
        })

    queued = []
    if len(admitted) > 1:
        keep = next(family_id for family_id in ADMISSION_ORDER if family_id in admitted)
        for item in families:
            if item['family_id'] in admitted and item['family_id'] != keep:
                item['status'] = 'QUEUED_NOT_RUN'
                item['gate_passed'] = False
                queued.append(item['family_id'])
        admitted = [keep]

    if admitted:
        refuse_unimplemented_comparison(admitted[0])

    decision = 'ADMITTED_ONE_FAMILY' if admitted else 'NO_FAMILY_ADMITTED'
    evidence = {
        'calendar': {key: value for key, value in calendar_info.items() if key != 'nonempty_counts'},
        'nonempty_counts': calendar_info['nonempty_counts'],
        'canonical_lineage': canonical_lineage,
        'reacquired_lineage': reacquired_lineage,
        'financing_table': {key: value for key, value in financing_table.items() if key != 'nonempty_counts'},
        'financing_nonempty_counts': financing_table['nonempty_counts'],
        'source_policy_pit_certified': policy.get('pit_certified'),
        'turnover_audit_flags': {
            'historical_publication_times_certified': turnover_audit.get('historical_publication_times_certified'),
            'historical_constituents_independently_verified': turnover_audit.get('historical_constituents_independently_verified'),
            'definition_is_project_authored': turnover_audit.get('definition_is_project_authored'),
            'vendor_native_formula_verified': turnover_audit.get('vendor_native_formula_verified'),
        },
        'receipts': receipts,
        'responses': responses,
        'latest_flags': latest_flags,
        'documented_sentences_present': sentences,
        'ifind_financing_keys': ifind_keys,
        'v92_summary': {key: value for key, value in v92.items() if key != 'records'},
        'v92_records': v92['records'],
        'disclosure_table_present': disclosure_table.is_file(),
        'breadth_paths': breadth_paths,
        'outside_minimum_set_paths': outside_paths,
        'derived_columns_present': sorted(required_header),
        'derived_clock_after_close': derived_clock,
        'peg_python_mentions': peg_mentions,
        'consNumber_python_mentions': cons_mentions,
        'amount_lineage': amount_status,
        'style_lineage': style_status,
    }
    return {
        'decision': decision,
        'admitted': admitted,
        'queued_not_run': queued,
        'comparison_ran': False,
        'families': families,
        'gaps': gaps,
        'cited_close_past_rank90': cited,
        'prior_decisions': priors,
        'evidence': evidence,
        'next_step': plan['next_step_if_none_admitted'],
    }


def refuse_unimplemented_comparison(family_id: str) -> None:
    raise SystemExit(
        f'{family_id} passed the pre-registered gate. The comparison is not implemented in this file. '
        'Do not edit plan.json. Add the one pre-registered comparison and rerun the audit.'
    )


def pct(value: float) -> str:
    return f'{value * 100:.1f}%'


def counts(mapping) -> str:
    if not mapping:
        return 'none'
    return ', '.join(f'{key} {value}' for key, value in mapping.items())


def narratives(result: dict) -> dict[str, str]:
    evidence = result['evidence']
    v92 = evidence['v92_summary']
    financing_dates = len(v92['unique_dates'])
    cited = {(row['task'], row['group']): row for row in result['cited_close_past_rank90']}
    pairs = []
    for task in TASKS:
        price = cited[(task, 'price__past_rank90')]
        both = cited[(task, 'price_amount_style__past_rank90')]
        pairs.append(
            f"{task} price {pct(price['precision'])}/{pct(price['recall'])} versus amount+style {pct(both['precision'])}/{pct(both['recall'])}"
        )
    citation = '; '.join(pairs)
    english = (
        f"No candidate has a structured disclosure timestamp on every research session, "
        f"with observation_date strictly before D and the clock strictly before 09:15 Asia/Shanghai on D. "
        f"Financing covers the {CALENDAR_ROWS} sessions in the provider table, and its lineage statuses are "
        f"{counts(evidence['canonical_lineage']['by_field'].get('financing_balance'))} and "
        f"{counts(evidence['reacquired_lineage']['by_field'].get('financing_balance'))}. "
        f"The exchange capture covers {financing_dates} sessions, PIT_certified values are {counts(v92['pit_certified_values'])}, "
        f"capture-clock fields are {counts(v92['capture_clock_fields'])}, "
        f"and those clocks run from {v92['capture_time_min']} to {v92['capture_time_max']}; "
        f"{v92['capture_before_preopen']} of those capture times fall before the next pre-open, and a capture time would not count as disclosure anyway. "
        f"Turnover is historical_publication_times_certified={evidence['turnover_audit_flags']['historical_publication_times_certified']}, "
        f"constituents independently verified={evidence['turnover_audit_flags']['historical_constituents_independently_verified']}, "
        f"and both the native-rate request and a float-A repair still say 最新. "
        f"Market-breadth filename search found {evidence['breadth_paths'] or 'no files'}. "
        f"Index amount and the 000300/000852 controls are OFFICIAL_HISTORY_NOT_PIT; the 000985 receipt clock is "
        f"{evidence['receipts']['000985']['request_started_at_utc']} to {evidence['receipts']['000985']['response_completed_at_utc']}. "
        f"Amount and style were already compared and are not re-run: {citation}. "
        f"The displayed baseline stayed on the price group. Official peg and consNumber are unused raw fields on that same receipt. "
        f"The next step is to collect certified per-session disclosure timestamps for the Shanghai and Shenzhen financing balances. That collection is not done here. No family was fit. "
        f"formal_signal_allowed stays false. This is not PIT, not a blind test, and not a signal. "
        f"P1 remains BLOCKED_NO_CONCENTRATION. P1b remains GO_PRE_PIVOT_COORDINATE. P1c remains BLOCKED_NO_WINDOW_PEAK. P1d remains GO_NEW_FACTORS."
    )
    breadth = evidence['breadth_paths'] or '没有命中文件'
    chinese = (
        f"没有任何候选家族在全部研究日上带有结构化披露时点，并且观察日严格早于 D、时钟严格早于 D 日上海时间 09:15。"
        f"融资余额的供应商表覆盖 {CALENDAR_ROWS} 个研究日，谱系状态是 "
        f"{counts(evidence['canonical_lineage']['by_field'].get('financing_balance'))} 和 "
        f"{counts(evidence['reacquired_lineage']['by_field'].get('financing_balance'))}。"
        f"交易所原始捕获覆盖 {financing_dates} 个交易日，PIT_certified 的取值是 {counts(v92['pit_certified_values'])}，"
        f"捕获时钟字段是 {counts(v92['capture_clock_fields'])}，"
        f"时间从 {v92['capture_time_min']} 到 {v92['capture_time_max']}；"
        f"其中 {v92['capture_before_preopen']} 个捕获时间早于下一交易日开盘前，而且捕获时间本来就不是披露时点。"
        f"换手率的 historical_publication_times_certified 是 {evidence['turnover_audit_flags']['historical_publication_times_certified']}，"
        f"历史成分独立认证是 {evidence['turnover_audit_flags']['historical_constituents_independently_verified']}，"
        f"原生换手率请求和一份流通 A 股修复回执仍然写着“最新”。"
        f"市场广度文件名检索{breadth}。"
        f"成交额和 000300/000852 对照的谱系是 OFFICIAL_HISTORY_NOT_PIT；000985 回执时钟是 "
        f"{evidence['receipts']['000985']['request_started_at_utc']} 到 {evidence['receipts']['000985']['response_completed_at_utc']}。 "
        f"成交额和风格已经比较过，本轮不重跑：{citation}。展示基线仍是价格组。官方回执上的 peg 和 consNumber 没有被研究代码用作特征。 "
        f"下一步是为沪深融资余额收集逐日、带时区、并且早于下一交易日 09:15 的披露时点。这一步没有实施。没有拟合任何家族。 "
        f"formal_signal_allowed 仍为 false。这不是 PIT，不是盲测，也不是信号。 "
        f"P1 仍是 BLOCKED_NO_CONCENTRATION。P1b 仍是 GO_PRE_PIVOT_COORDINATE。P1c 仍是 BLOCKED_NO_WINDOW_PEAK。P1d 仍是 GO_NEW_FACTORS。"
    )
    return {'english': english, 'chinese': chinese}


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise SystemExit(f'no rows for {path.name}')
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def inventory_rows(result: dict) -> list[dict]:
    rows = []
    for item in result['families']:
        rows.append({
            'family_id': item['family_id'],
            'role': item['role'],
            'eligible_if_evidence_passes': str(item['eligible_if_evidence_passes']).lower(),
            'gate_passed': str(item['gate_passed']).lower(),
            'status': item['status'],
            'blocks': '|'.join(item['blocks']),
        })
    return rows


def render_readme(result: dict, prose: dict[str, str]) -> str:
    lines = [
        '# P4a 非价格因子准入：先看披露时点，再决定是否允许比较',
        '',
        f"**Decision: `{result['decision']}`.** {prose['english']}",
        '',
        f"**结论：`{result['decision']}`。** {prose['chinese']}",
        '',
        '这是准入审计，不是新模型。`formal_signal_allowed` 仍为 false。没有 PIT 认证，没有盲测，没有生产信号。P1、P1b、P1c、P1d 的结论不改写，门槛不放宽。',
        '',
        '## 预登记的门禁',
        '',
        '观察日必须严格早于决策日 D。披露时点必须带时区，并且严格早于 D 日上海时间 09:15，也就是开盘集合竞价开始、连续竞价 09:30 之前。只有 CSV 列名或 JSON 键名落在预登记名单里，才算结构化披露时点。下载时间、请求时间、参数“最新”、谱系里的 NOT_PIT、交易所名称和序列起止日期都不算。',
        '',
        '融资、换手率、市场广度没有豁免。000300 和 000852 仍然只是风格对照，不能改成正式目标。成交额和风格已经在 `label_clock_v4` 的 `price_amount_style` 里比较过，本轮只引用那张表，不重新拟合。缺文件、缺时点、只有一段时间的样本，默认都是 `RESEARCH_ONLY`。通过门禁的家族最多一个，顺序是融资余额、换手率、市场广度。',
        '',
        '## 库存',
        '',
        '| 家族 | 角色 | 状态 | 阻断 |',
        '|---|---|---|---|',
    ]
    for item in result['families']:
        blocks = '、'.join(item['blocks']) if item['blocks'] else '无'
        lines.append(f"| `{item['family_id']}` | {item['role']} | `{item['status']}` | {blocks} |")
    lines.extend([
        '',
        '## 缺的证据',
        '',
        '| 家族 | 阻断 | 查过的路径 | 看到的结果 |',
        '|---|---|---|---|',
    ])
    for item in result['gaps']:
        detail = item['detail'].replace('|', '/')
        found = item['found'].replace('|', '/')
        lines.append(f"| `{item['family_id']}` | `{item['block']}` | `{item['path']}` | {found}。{detail} |")
    lines.extend([
        '',
        '## 已经比较过的成交额和风格',
        '',
        '下表是 `label_clock_v4/rank_metrics.csv` 里收盘标签、`past_rank90` 的原有结果。本轮没有重算。',
        '',
        '| 任务 | 价格组 精确率/覆盖率 | 价格+成交额+风格 精确率/覆盖率 |',
        '|---|---:|---:|',
    ])
    cited = {(row['task'], row['group']): row for row in result['cited_close_past_rank90']}
    for task in TASKS:
        price = cited[(task, 'price__past_rank90')]
        both = cited[(task, 'price_amount_style__past_rank90')]
        lines.append(
            f"| {task} | {pct(price['precision'])} / {pct(price['recall'])} | {pct(both['precision'])} / {pct(both['recall'])} |"
        )
    lines.extend([
        '',
        '5% 两项的精确率和覆盖率都低于价格组。9% 两项都高于价格组。当时的规则是四项任务不分别挑赢家，展示基线留在价格组。这个对照不是本轮的准入门槛，也不构成重新拟合的理由。四项都没有双80。',
        '',
        '## 下一步，本轮不实施',
        '',
        '收集沪深融资余额的逐日披露时点。每个研究日、每一边交易所一行，字段是观察日、字段名、带时区的披露时点，并且该时点必须早于下一交易日上海时间 09:15。不要把 2026 年的捕获时间、iFinD 转载、`数据来源` 或一小段交易所文件当成这个表。换手率还差成分范围认证，所以只有时点也不够。广度还没有成分、停牌和涨跌文件，不能用今天的存续名单回填。成交额和风格不重新开题。',
        '',
        '## 没有做的事',
        '',
        '- 没有拟合融资、换手率、广度或任何其他家族，也没有搜索第二种变换。',
        '- 没有重跑 `price_amount_style`，没有重训六个价格特征，没有把 3 日收益或 3 日收益变化加回。',
        '- 没有实现提前发报，没有打开 P2，没有提高分位，没有用未来目标数做警报配额。',
        '- 没有更换标签或指数，没有把 D 日行情写进当日特征。',
        '- 没有下载新数据，没有修改生产页面、采集器、正式信号，也没有恢复旧 V 系列。',
        '- 不声称双80，不声称 PIT，不声称这是盲测。',
        '',
        '## 复算',
        '',
        '```text',
        'python -B dual80-research/p4a_factor_admission/audit.py --write-plan-only',
        'python -B dual80-research/p4a_factor_admission/audit.py',
        '```',
        '',
        '缺少 `plan.json` 时审计会停止。`--write-plan-only` 只在文件不存在时写出计划，不解释来源字段。计划写出之后不再改写。',
        '',
    ])
    return '\n'.join(lines)


def write_artifact_manifest() -> None:
    files = sorted(path for path in HERE.iterdir() if path.is_file() and path.name != 'artifact_manifest.json')
    manifest = {
        path.name: {'bytes': path.stat().st_size, 'sha256': sha256_file(path)}
        for path in files
    }
    (HERE / 'artifact_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def write_outputs(result: dict, plan_sha: str) -> None:
    prose = narratives(result)
    evidence = result['evidence']
    decision = {
        'decision': result['decision'],
        'formal_signal_allowed': False,
        'blind_test': False,
        'PIT_certified': False,
        'production_changed': False,
        'comparison_ran': False,
        'families_admitted': result['admitted'],
        'queued_not_run': result['queued_not_run'],
        'next_step': result['next_step']['name'],
        'next_step_implemented': False,
        'english': prose['english'],
        'chinese': prose['chinese'],
        'p1_decision': result['prior_decisions']['P1'],
        'p1b_decision': result['prior_decisions']['P1b'],
        'p1c_decision': result['prior_decisions']['P1c'],
        'p1d_decision': result['prior_decisions']['P1d'],
    }
    summary = {
        'decision': result['decision'],
        'formal_signal_allowed': False,
        'blind_test': False,
        'PIT_certified': False,
        'production_changed': False,
        'comparison_ran': False,
        'families_admitted': result['admitted'],
        'families': result['families'],
        'cited_close_past_rank90': result['cited_close_past_rank90'],
        'next_step': result['next_step'],
        'v92_unique_dates': evidence['v92_summary']['unique_dates'],
        'v92_capture_before_preopen': evidence['v92_summary']['capture_before_preopen'],
        'plan_sha256': plan_sha,
        'english': prose['english'],
        'chinese': prose['chinese'],
    }
    write_csv(HERE / 'inventory.csv', inventory_rows(result))
    write_csv(HERE / 'gaps.csv', result['gaps'])
    (HERE / 'evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (HERE / 'decision.json').write_text(json.dumps(decision, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (HERE / 'result.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (HERE / 'README.md').write_text(render_readme(result, prose), encoding='utf-8')
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
    for name in ('scores.csv', 'alerts.csv', 'lead_profile.csv'):
        if (HERE / name).exists():
            raise SystemExit(f'{name} exists; this phase must not write a score')
    write_outputs(result, sha256_file(HERE / 'plan.json'))
    print(json.dumps({
        'decision': result['decision'],
        'admitted': result['admitted'],
        'comparison_ran': False,
        'formal_signal_allowed': False,
        'families': [{'id': item['family_id'], 'status': item['status']} for item in result['families']],
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
