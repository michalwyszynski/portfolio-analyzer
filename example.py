from portfolio import AssetClass, Portfolio


def generate_transaction_history(portfolio: Portfolio) -> None:
    portfolio.add_purchase("2021-01-27", "GC=F", 1, 1590.74)
    portfolio.add_purchase("2021-12-02", "SXR8.DE", 24, 408.20)
    portfolio.add_purchase("2022-01-10", "EMIM.AS", 25, 31.50)
    portfolio.add_purchase("2022-10-03", "EMIM.AS", 30, 26.00)
    portfolio.add_purchase("2022-10-05", "DBZB.DE", 22, 204.88)
    portfolio.sell("2025-10-08", "DBZB.DE", 22, 210.50)
    portfolio.add_purchase("2025-10-09", "ASML.AS", 8, 851.60)
    portfolio.add_dividend("2025-11-07", "ASML.AS", 1.60)
    portfolio.sell("2025-12-02", "ASML.AS", 8, 951.50)
    portfolio.add_purchase("2025-12-03", "V60A.DE", 70, 34.00)
    portfolio.sell("2026-02-25", "V60A.DE", 10, 35.10)
    portfolio.add_purchase("2026-03-27", "V60A.DE", 70, 33.50)


if __name__ == "__main__":
    portfolio = Portfolio(start_date="2021-01-26", ccy_conv={"GC=F": "EUR=X"})
    generate_transaction_history(portfolio)
    portfolio.calculate()
    print("=" * 50)
    portfolio.print_best_worst_periods()
    print("=" * 50)
    portfolio.print_best_worst_periods(period="month")
    print("=" * 50)
    portfolio.print_best_worst_periods(period="year")
    print("=" * 50)
    portfolio.default_plot()

    portfolio.register_alloc_matrix(
        {
            "GC=F": {AssetClass.GOLD: 1.0},
            "SXR8.DE": {AssetClass.STOCKS: 1.0},
            "EMIM.AS": {AssetClass.STOCKS: 1.0},
            "DBZB.DE": {AssetClass.BONDS: 1.0},
            "ASML.AS": {AssetClass.STOCKS: 1.0},
            "V60A.DE": {AssetClass.STOCKS: 0.6, AssetClass.BONDS: 0.4},
        }
    )

    portfolio.metrics_plot()
    portfolio.show_plots()
