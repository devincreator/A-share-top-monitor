import numpy as np
import pandas as pd
from collector.v27_collect import pct_prior, normalize_frame, build_features


def test_history_does_not_use_future_values():
    a = np.arange(760.0)
    p = pct_prior(a, 756)
    b = a.copy()
    b[-1] = 100000.
    q = pct_prior(b, 756)
    assert np.isnan(p[755])
    assert np.array_equal(p[756:759],q[756:759])


def test_index_wrong_anchor_is_rejected():
    days = pd.date_range("2022-01-01", periods=950, freq="B")
    d = pd.DataFrame({"日期":days,"收盘":7000.,"成交额":1e11,"换手率":1.2})
    try:
        normalize_frame(d, "000985")
    except ValueError as e:
        assert "price index mismatch" in str(e)
    else:
        raise AssertionError("must reject wrong index")


def test_percentile_excludes_current():
    arr=[1.,2.,3.,1.]
    x=pct_prior(arr,3)
    assert np.isclose(x[3],100./3.)
