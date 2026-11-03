# -*- coding: utf-8 -*-
from jqdata import *
import numpy as np


def initialize(context):
    # ===== 标的和基础设置 =====
    g.security = '510300.XSHG'       # 可改成股票，如 '000001.XSHE'
    g.market_index = '000300.XSHG'
    set_benchmark(g.market_index)
    set_option('use_real_price', True)

    # ===== 成本和滑点 =====
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.001,
            open_commission=0.0003,
            close_commission=0.0003,
            close_today_commission=0,
            min_commission=5
        ),
        type='stock'
    )
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=0.0001,
            close_commission=0.0001,
            close_today_commission=0,
            min_commission=5
        ),
        type='fund'
    )
    set_slippage(PriceRelatedSlippage(0.002))

    # ===== 策略参数 =====
    g.rsi_period = 10
    g.rsi_buy_threshold = 40
    g.rsi_take_profit = 55

    g.boll_window = 20
    g.boll_std = 2.0

    g.volume_window = 20
    g.volume_boost = 0.10

    g.atr_period = 14
    g.atr_multiplier = 2.0
    g.stop_loss_atr_multiplier = 2.0
    g.risk_per_trade = 0.01
    g.lot_size = 100

    g.buy_cash_ratio = 0.98
    g.max_position_value_ratio = 0.98
    g.max_order_value_to_avg_amount = 0.02
    g.min_order_value = 10000
    g.round_trip_cost_buffer = 0.006

    g.max_drawdown = 0.25
    g.max_hold_days = 10
    g.market_ma_window = 60
    g.market_recent_return_days = 20
    g.market_ma_buffer = 0.98
    g.market_min_recent_return = -0.08
    g.highest_price = {}
    g.entry_price = {}
    g.hold_days = {}
    g.debug_signal = True

    g.history_count = max(
        g.rsi_period + 1,
        g.boll_window,
        g.volume_window + 2,
        g.atr_period + 1,
        g.market_ma_window + 1
    ) + 5

    run_daily(market_open, time='open', reference_security=g.security)


def market_open(context):
    security = g.security
    current_data = get_current_data()

    if current_data[security].paused:
        log.info('%s 停牌，跳过。' % security)
        return

    hist = attribute_history(
        security,
        g.history_count,
        '1d',
        ['open', 'close', 'high', 'low', 'volume'],
        skip_paused=True,
        df=True,
        fq='pre'
    )

    if hist is None or len(hist) < g.history_count:
        log.info('%s 历史数据不足，跳过。' % security)
        return

    signal = get_signal_from_history(hist)
    if signal is None:
        log.info('%s 指标计算失败，跳过。' % security)
        return

    position = context.portfolio.positions[security]
    trade_price = get_trade_price(current_data[security], hist)
    expected_rebound = signal['boll_mid'] / trade_price - 1.0
    market_ok = is_market_regime_ok()

    if g.debug_signal:
        log.info(
            '信号诊断 %s | buy=%s, 市场=%s, RSI=%.2f<%.2f:%s, 量比=%.3f/%.3f>=%.2f:%s, low=%.3f<=下轨%.3f:%s, close回下轨上方:%s, 到中轨=%.2f%%'
            % (
                security,
                signal['buy_signal'],
                market_ok,
                signal['rsi'],
                g.rsi_buy_threshold,
                signal['rsi_ok'],
                signal['volume_ratio_previous'],
                signal['volume_ratio_latest'],
                1.0 + g.volume_boost,
                signal['volume_ok'],
                signal['yesterday_low'],
                signal['boll_lower'],
                signal['touch_lower'],
                signal['close_back_above_lower'],
                expected_rebound * 100
            )
        )

    # ===== 先检查持仓退出 =====
    if position.total_amount > 0:
        g.hold_days[security] = g.hold_days.get(security, 0) + 1
        update_highest_price(security, trade_price, signal['yesterday_high'])
        highest_price = g.highest_price.get(security, trade_price)
        entry_price = g.entry_price.get(security, trade_price)
        drawdown = trade_price / highest_price - 1.0
        stop_price = entry_price - signal['atr'] * g.stop_loss_atr_multiplier

        exit_reason = None
        if trade_price <= stop_price:
            exit_reason = 'ATR止损'
        elif trade_price >= signal['boll_mid']:
            exit_reason = '回到布林中轨'
        elif signal['rsi'] >= g.rsi_take_profit:
            exit_reason = 'RSI修复'
        elif g.hold_days.get(security, 0) >= g.max_hold_days:
            exit_reason = '持仓超时'
        elif drawdown <= -g.max_drawdown:
            exit_reason = '25%回撤兜底'

        if exit_reason is not None and position.closeable_amount > 0:
            order_target(security, 0)
            g.highest_price[security] = 0
            g.entry_price[security] = 0
            g.hold_days[security] = 0
            log.info(
                '卖出 %s | 原因=%s, 当前价=%.3f, 入场=%.3f, 高点=%.3f, 回撤=%.2f%%'
                % (security, exit_reason, trade_price, entry_price, highest_price, drawdown * 100)
            )
            record(rsi=signal['rsi'], atr=signal['atr'], drawdown=drawdown)
            return
    else:
        g.highest_price[security] = 0
        g.entry_price[security] = 0
        g.hold_days[security] = 0

    # ===== 买入逻辑 =====
    if signal['buy_signal'] and market_ok and position.total_amount == 0 and context.portfolio.cash > 0:
        if expected_rebound <= g.round_trip_cost_buffer:
            log.info(
                '%s 触发买入但空间不足 | 到中轨空间=%.2f%%'
                % (security, expected_rebound * 100)
            )
            record(rsi=signal['rsi'], atr=signal['atr'], expected_rebound=expected_rebound)
            return

        amount, value = calc_atr_position_size(
            context,
            trade_price,
            signal['atr'],
            signal['avg_amount']
        )

        if amount >= g.lot_size:
            order(security, amount)
            g.highest_price[security] = trade_price
            g.entry_price[security] = trade_price
            g.hold_days[security] = 0
            log.info(
                '买入 %s | 手数=%d, 股数=%d, 价值=%.2f, 价格=%.3f, ATR=%.3f, RSI=%.2f, 量比=%.3f/%.3f'
                % (
                    security,
                    amount // g.lot_size,
                    amount,
                    value,
                    trade_price,
                    signal['atr'],
                    signal['rsi'],
                    signal['volume_ratio_previous'],
                    signal['volume_ratio_latest']
                )
            )
        else:
            log.info('%s 触发买入但仓位不足一手或低于最小成交额。' % security)

    record(
        rsi=signal['rsi'],
        atr=signal['atr'],
        volume_ratio_latest=signal['volume_ratio_latest'],
        volume_ratio_previous=signal['volume_ratio_previous'],
        boll_lower=signal['boll_lower']
    )


def get_signal_from_history(hist):
    opens = np.array(hist['open'].values, dtype=float)
    closes = np.array(hist['close'].values, dtype=float)
    highs = np.array(hist['high'].values, dtype=float)
    lows = np.array(hist['low'].values, dtype=float)
    volumes = np.array(hist['volume'].values, dtype=float)

    rsi = calc_rsi(closes, g.rsi_period)
    atr = calc_atr(highs, lows, closes, g.atr_period)
    if rsi is None or atr is None or atr <= 0:
        return None

    boll_closes = closes[-g.boll_window:]
    boll_mid = np.mean(boll_closes)
    boll_std = np.std(boll_closes)
    boll_upper = boll_mid + g.boll_std * boll_std
    boll_lower = boll_mid - g.boll_std * boll_std

    volume_ratio_latest = calc_volume_ratio(volumes, -1, g.volume_window)
    volume_ratio_previous = calc_volume_ratio(volumes, -2, g.volume_window)
    if volume_ratio_latest is None or volume_ratio_previous is None:
        return None

    avg_amount = np.mean(closes[-g.volume_window:] * volumes[-g.volume_window:])
    yesterday_high = highs[-1]
    yesterday_low = lows[-1]
    yesterday_close = closes[-1]

    rsi_ok = rsi < g.rsi_buy_threshold
    volume_ok = (
        volume_ratio_latest >= 1.0 + g.volume_boost
        and volume_ratio_previous >= 1.0 + g.volume_boost
    )
    touch_lower = yesterday_low <= boll_lower
    close_back_above_lower = yesterday_close >= boll_lower
    buy_signal = rsi_ok and volume_ok and touch_lower and close_back_above_lower

    return {
        'rsi': rsi,
        'atr': atr,
        'boll_mid': boll_mid,
        'boll_upper': boll_upper,
        'boll_lower': boll_lower,
        'avg_amount': avg_amount,
        'volume_ratio_latest': volume_ratio_latest,
        'volume_ratio_previous': volume_ratio_previous,
        'yesterday_high': yesterday_high,
        'yesterday_low': yesterday_low,
        'yesterday_close': yesterday_close,
        'rsi_ok': rsi_ok,
        'volume_ok': volume_ok,
        'touch_lower': touch_lower,
        'close_back_above_lower': close_back_above_lower,
        'buy_signal': buy_signal,
    }


def get_trade_price(current_data_item, hist):
    price = getattr(current_data_item, 'day_open', 0)
    if price is None or price <= 0:
        price = getattr(current_data_item, 'last_price', 0)
    if price is None or price <= 0:
        price = float(hist['close'].values[-1])
    return float(price)


def is_market_regime_ok():
    hist = attribute_history(
        g.market_index,
        max(g.market_ma_window, g.market_recent_return_days) + 1,
        '1d',
        ['close'],
        skip_paused=True,
        df=True,
        fq='pre'
    )

    if hist is None or len(hist) < max(g.market_ma_window, g.market_recent_return_days) + 1:
        return False

    closes = np.array(hist['close'].values, dtype=float)
    last_close = closes[-1]
    ma = np.mean(closes[-g.market_ma_window:])
    recent_return = last_close / closes[-g.market_recent_return_days - 1] - 1.0

    above_ma_buffer = last_close >= ma * g.market_ma_buffer
    not_crashing = recent_return >= g.market_min_recent_return
    return above_ma_buffer and not_crashing


def update_highest_price(security, current_price, yesterday_high):
    old_highest = g.highest_price.get(security, 0)
    g.highest_price[security] = max(old_highest, current_price, yesterday_high)


def calc_atr_position_size(context, price, atr, avg_amount):
    if price <= 0 or atr <= 0 or avg_amount <= 0:
        return 0, 0

    risk_budget = context.portfolio.total_value * g.risk_per_trade
    risk_per_share = atr * g.atr_multiplier
    atr_amount = int(risk_budget / risk_per_share) // g.lot_size * g.lot_size

    max_value_by_cash = context.portfolio.cash * g.buy_cash_ratio
    max_value_by_portfolio = context.portfolio.total_value * g.max_position_value_ratio
    max_value_by_liquidity = avg_amount * g.max_order_value_to_avg_amount
    max_value = min(max_value_by_cash, max_value_by_portfolio, max_value_by_liquidity)
    cash_amount = int(max_value / price) // g.lot_size * g.lot_size

    amount = min(atr_amount, cash_amount)
    value = amount * price
    if value < g.min_order_value:
        return 0, value
    return amount, value


def calc_volume_ratio(volumes, signal_index, window):
    signal_pos = len(volumes) + signal_index if signal_index < 0 else signal_index
    start = signal_pos - window
    end = signal_pos

    if start < 0 or end <= start:
        return None

    base = np.mean(volumes[start:end])
    if base <= 0:
        return None

    return volumes[signal_pos] / base


def calc_atr(highs, lows, closes, period):
    if len(closes) < period + 1:
        return None

    true_ranges = []
    start = len(closes) - period
    for i in range(start, len(closes)):
        tr1 = highs[i] - lows[i]
        tr2 = abs(highs[i] - closes[i - 1])
        tr3 = abs(lows[i] - closes[i - 1])
        tr = max(tr1, tr2, tr3)
        true_ranges.append(tr)

    return np.mean(true_ranges)


def calc_rsi(closes, period):
    if len(closes) < period + 1:
        return None

    gains = []
    losses = []
    start = len(closes) - period

    for i in range(start, len(closes)):
        change = closes[i] - closes[i - 1]
        if change > 0:
            gains.append(change)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(change))

    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)

    if avg_loss == 0:
        if avg_gain == 0:
            return 50.0
        return 100.0

    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)
