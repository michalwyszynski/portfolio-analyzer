# Quantitative Portfolio Tracker & Analyzer

An object-oriented Python framework for portfolio accounting, historical performance analysis, and asset allocation visualization.
This tool is designed to accurately calculate path-dependent financial metrics (like FIFO-based profit and loss) while providing resilient data ingestion for missing market data.

## Key Features

* **Strict FIFO Accounting:** Implements First-In-First-Out (FIFO) logic to accurately track tax lots, basis reduction, and realized vs. unrealized profit across partial liquidations.
* **Vectorized Performance Metrics:** Leverages pandas vectorization to compute cumulative returns, rolling Compound Annual Growth Rate (CAGR), and maximum drawdown without computationally expensive loops.
* **Resilient Data Ingestion:** Handles notoriously unreliable market data by automatically patching missing yfinance time-series data with local CSV fallbacks.
* **Multi-Currency Support:** Automatically converts historical asset pricing into a unified base currency for accurate aggregate portfolio valuation.
* **Automated Reporting & Visualization:** Generates standardized matplotlib grids for cumulative performance, rolling metrics, and dynamic asset allocation drift.

## Tech Stack

* **Core:** Python 3.11+, Object-Oriented Architecture
* **Data Processing:** `pandas`, `numpy`
* **Market Data:** `yfinance`
* **Visualization:** `matplotlib`

## Quick Start

*(Note: Never push real transaction history to this repository. Use `example.py` to run the framework with dummy transactions.)*

```bash
# Clone the repository
git clone https://github.com/michalwyszynski93/portfolio-analyzer.git
cd portfolio-analyzer

# Run the mocked example
python example.py
```

## Roadmap and future work

* **Environment/dependency/tasks management:** add a `pixi.toml` for modern, reproducible env management.
* **Testing:** implement a `pytest` suite to ensure there are no regressions. The existing CSV fallback functionality can be used for mocking the data source. Add the `test` task in `pixi.toml`.
* **Linting/formatting:** add the `format` task using `ruff` in `pixi.toml`.
* **CI/CD pipeline:** set up GitHub actions for checking formatting and running the test suite on every PR.
* **Support for stock splits:** implement the relevant logic and arithmetic, add tests.
* **Data input:** design and implement streamlined data input (could be from a CSV file).
