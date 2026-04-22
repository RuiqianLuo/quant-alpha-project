from pathlib import Path
import os
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MPL_CONFIG_DIR = PROJECT_ROOT / "reports" / "mpl_config"
MPL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ["MPLCONFIGDIR"] = str(MPL_CONFIG_DIR)

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


SRC_DIR = PROJECT_ROOT / "src"
REPORTS_DIR = PROJECT_ROOT / "reports"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester import run_cross_sectional_backtest
from factor_library import compute_factor_set
from metrics import build_research_summary


def _save_plot(series: pd.Series, title: str, ylabel: str, output_path: Path) -> None:
    """
    Save a simple line chart for interview-friendly reporting.
    """

    fig, ax = plt.subplots(figsize=(10, 5))
    series.plot(ax=ax, linewidth=2)
    ax.set_title(title)
    ax.set_xlabel("Date")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> None:
    data_file = PROJECT_ROOT / "data" / "processed" / "real_daily_prices.csv"
    price_col = "adjusted_close"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    if not data_file.exists():
        raise FileNotFoundError(f"Real dataset not found: {data_file}. Run notebooks\\download_real_data.py first.")

    real_data = pd.read_csv(data_file, parse_dates=["date"])
    factor_data = compute_factor_set(real_data, factors=["momentum_1m", "rolling_volatility"], price_col=price_col)

    daily_results, backtest_metrics, rebalance_history = run_cross_sectional_backtest(
        price_data=real_data,
        factor_data=factor_data,
        factor_name="momentum_1m",
        top_n=1,
        transaction_cost_bps=10.0,
        price_col=price_col,
    )

    research_summary = build_research_summary(
        daily_results=daily_results,
        factor_data=factor_data,
        factor_name="momentum_1m",
        rebalance_history=rebalance_history,
    )

    cumulative_plot_path = REPORTS_DIR / "cumulative_returns.png"
    drawdown_plot_path = REPORTS_DIR / "drawdowns.png"

    _save_plot(
        research_summary["cumulative_returns"],
        title="Cumulative Portfolio Returns",
        ylabel="Cumulative Return",
        output_path=cumulative_plot_path,
    )
    _save_plot(
        research_summary["drawdowns"],
        title="Portfolio Drawdown",
        ylabel="Drawdown",
        output_path=drawdown_plot_path,
    )

    print("# Research Demo")
    print()
    print("## Pipeline")
    print(f"Loaded real data from: {data_file}")
    print(f"Research price column: {price_col}")
    print("Computed factors: momentum_1m, rolling_volatility")
    print("Backtest style: monthly rebalance, long-only, equal weight, top 1 name")
    print()
    print("## Backtest Metrics")
    for key, value in backtest_metrics.items():
        print(f"{key}: {value:.6f}")
    print()
    print("## Yearly Summary")
    print(research_summary["yearly_summary"].to_string(index=False))
    print()
    print("## Factor Diagnostics")
    for key, value in research_summary["factor_diagnostics"].items():
        print(f"{key}: {value:.6f}")
    print()
    print("## Portfolio Diagnostics")
    for key, value in research_summary["portfolio_diagnostics"].items():
        print(f"{key}: {value:.6f}")
    print()
    print("## Plot Outputs")
    print(f"Cumulative return plot: {cumulative_plot_path}")
    print(f"Drawdown plot: {drawdown_plot_path}")
    print()
    print("## Interpretation")
    print("This demo shows the mechanics of the research pipeline on downloaded daily data rather than evidence of a robust alpha signal.")
    print("The current real-data path still uses a fixed ticker universe and simple assumptions, so the reported metrics should be treated as exploratory only.")
    print("In an interview, the useful discussion is how the pipeline avoids lookahead bias, tracks turnover and costs, and keeps each research layer modular.")


if __name__ == "__main__":
    main()
