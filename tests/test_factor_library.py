from pathlib import Path
import sys

import pandas as pd


SRC_DIR = Path(__file__).resolve().parents[1] / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from factor_library import compute_1m_momentum, compute_short_term_reversal


def test_factor_outputs_use_lagged_information() -> None:
    dates = pd.bdate_range("2024-01-01", periods=30)
    frame = pd.DataFrame(
        {
            "date": dates,
            "ticker": ["AAA"] * len(dates),
            "close": list(range(100, 130)),
            "volume": [1000] * len(dates),
        }
    )

    momentum = compute_1m_momentum(frame, window=21)
    reversal = compute_short_term_reversal(frame, window=5)

    target_date = dates[22]

    expected_momentum = (121 / 100) - 1
    expected_reversal = -((121 / 116) - 1)

    assert momentum.index.names == ["date", "ticker"]
    assert abs(momentum.loc[(target_date, "AAA"), "momentum_1m"] - expected_momentum) < 1e-12
    assert abs(reversal.loc[(target_date, "AAA"), "short_term_reversal"] - expected_reversal) < 1e-12
