# -*- coding: utf-8 -*-
from jqdata import *
import datetime
import numpy as np
import pandas as pd


def initialize(context):
    g.index_code = '000300.XSHG'
    g.stock_count = 30
    g.position_ratio = 0.95

    g.min_list_days = 120
    g.liquidity_window = 20
    g.min_avg_money = 20000000

    g.momentum_window = 60
    g.skip_recent_days = 5
    g.vol_window = 20

    set_benchmark(g.index_code)
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    log.set_level('order', 'error')

    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.0005,
            open_commission=0.0003,
            close_commission=0.0003,
            close_today_commission=0,
            min_commission=5
        ),
        type='stock'
    )
    set_slippage(PriceRelatedSlippage(0.002))

    run_monthly(rebalance, 1, time='open', reference_security=g.index_code)


def rebalance(context):
    universe = get_index_stocks(g.index_code)
    universe = filter_universe(context, universe)
    if len(universe) < g.stock_count:
        log.info('Not enough tradable stocks: {}'.format(len(universe)))
        return

    factor_df = build_factor_table(context, universe)
    if factor_df.empty:
        log.info('No valid factor data.')
        return

    factor_z = pd.DataFrame(index=factor_df.index)
    for column in factor_df.columns:
        factor_z[column] = standardize(winsorize(factor_df[column]))

    factor_z = factor_z.dropna()
    if factor_z.empty:
        log.info('No valid standardized factor data.')
        return

    value_score = 0.5 * factor_z['ep'] + 0.5 * factor_z['bp']
    score = (
        0.30 * factor_z['momentum']
        + 0.25 * value_score
        + 0.25 * factor_z['roe']
        + 0.20 * factor_z['low_vol']
    )

    target_stocks = list(score.sort_values(ascending=False).head(g.stock_count).index)
    adjust_position(context, target_stocks)


def filter_universe(context, stocks):
    current_data = get_current_data()
    today = context.current_dt.date()
    result = []

    for stock in stocks:
        data = current_data[stock]
        if data.paused or data.is_st:
            continue

        security_info = get_security_info(stock)
        if security_info is None:
            continue
        if today - security_info.start_date < datetime.timedelta(days=g.min_list_days):
            continue

        # Do not open new positions in stocks already locked at limit prices.
        if data.last_price >= data.high_limit or data.last_price <= data.low_limit:
            continue

        result.append(stock)

    return result


def build_factor_table(context, stocks):
    price_count = max(
        g.momentum_window + g.skip_recent_days + 1,
        g.vol_window + 1,
        g.liquidity_window
    )
    price = get_price(
        stocks,
        end_date=context.previous_date,
        count=price_count,
        frequency='daily',
        fields=['close', 'money'],
        skip_paused=False,
        fq='pre',
        panel=False
    )
    if price is None or len(price) == 0:
        return pd.DataFrame()

    if 'time' not in price.columns or 'code' not in price.columns:
        price = price.reset_index()

    close = price.pivot(index='time', columns='code', values='close').sort_index()
    money = price.pivot(index='time', columns='code', values='money').sort_index()

    avg_money = money.iloc[-g.liquidity_window:].mean()
    liquid_stocks = list(avg_money[avg_money >= g.min_avg_money].index)
    if len(liquid_stocks) == 0:
        return pd.DataFrame()

    close = close[liquid_stocks]

    momentum_end = close.iloc[-g.skip_recent_days - 1]
    momentum_start = close.iloc[-g.momentum_window - g.skip_recent_days - 1]
    momentum = momentum_end / momentum_start - 1

    returns = close.pct_change()
    low_vol = -returns.iloc[-g.vol_window:].std()

    fundamentals = get_fundamentals(
        query(
            valuation.code,
            valuation.market_cap,
            valuation.pe_ratio,
            valuation.pb_ratio,
            indicator.roe
        ).filter(valuation.code.in_(liquid_stocks)),
        date=context.previous_date
    )
    if fundamentals is None or len(fundamentals) == 0:
        return pd.DataFrame()

    fundamentals = fundamentals.set_index('code')
    fundamentals = fundamentals.replace([np.inf, -np.inf], np.nan)
    fundamentals = fundamentals[(fundamentals['pe_ratio'] > 0) & (fundamentals['pb_ratio'] > 0)]

    factor_df = pd.DataFrame(index=fundamentals.index)
    factor_df['momentum'] = momentum
    factor_df['ep'] = 1.0 / fundamentals['pe_ratio']
    factor_df['bp'] = 1.0 / fundamentals['pb_ratio']
    factor_df['roe'] = fundamentals['roe']
    factor_df['low_vol'] = low_vol

    return factor_df.replace([np.inf, -np.inf], np.nan).dropna()


def winsorize(series, n=3.0):
    series = series.dropna()
    if series.empty:
        return series

    median = series.median()
    mad = (series - median).abs().median()
    if mad == 0 or np.isnan(mad):
        lower = series.quantile(0.01)
        upper = series.quantile(0.99)
    else:
        width = n * 1.4826 * mad
        lower = median - width
        upper = median + width

    return series.clip(lower=lower, upper=upper)


def standardize(series):
    series = series.dropna()
    std = series.std(ddof=0)
    if std == 0 or np.isnan(std):
        return pd.Series(index=series.index, data=np.nan)

    return (series - series.mean()) / std


def adjust_position(context, target_stocks):
    current_data = get_current_data()
    current_holding = list(context.portfolio.positions.keys())

    for stock in current_holding:
        if stock not in target_stocks:
            data = current_data[stock]
            if data.paused or data.last_price <= data.low_limit:
                continue
            order_target_value(stock, 0)

    buy_list = []
    for stock in target_stocks:
        data = current_data[stock]
        if data.paused or data.last_price >= data.high_limit:
            continue
        buy_list.append(stock)

    if len(buy_list) == 0:
        return

    target_value = context.portfolio.total_value * g.position_ratio / len(buy_list)
    for stock in buy_list:
        order_target_value(stock, target_value)
