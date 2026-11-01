from collections.abc import Iterable
import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
from pandas.tseries.offsets import DateOffset
from datetime import datetime
from matplotlib import ticker as mtick
import os
import numpy as np
from enum import StrEnum
from typing import Literal


class AssetClass(StrEnum):
    STOCKS = "stocks"
    BONDS = "bonds"
    GOLD = "gold"


class Portfolio:
    def __init__(self, start_date: str, ccy_conv: dict[str, str]) -> None:
        self.tickers: set[str] = set()
        self._purchases: list = []
        self._sales: list = []
        self._dividends: list = []
        self.end_date = pd.to_datetime("today")

        self.start_date = start_date
        #self.days_to_discard = ["2026-04-01"]
        self.days_to_discard = []

        self.ccy_conv = ccy_conv
        self.alloc_matrix: dict[str, dict[AssetClass, float]] = {}
    
    def _date_conv(self, date_str: str) -> datetime:
        return datetime.strptime(date_str, "%Y-%m-%d")

    def add_purchase(self, date: str, ticker, qty: int, price: float) -> None:
        self._purchases.append([date, ticker, qty, price])
        self.tickers.add(ticker)

    def sell(self, date: str, ticker: str, qty: int, price: float) -> None:
        self._sales.append([date, ticker, qty, price])
    
    def add_dividend(self, date, ticker: str, amount: float) -> None:
        self._dividends.append([date, ticker, amount])
    
    def register_alloc_matrix(self, alloc_matrix: dict[str, dict[AssetClass, float]]) -> None:
        self.alloc_matrix.update(alloc_matrix)
    
    def _get_price_data(self) -> pd.DataFrame:
        tickers = self.tickers


        start, end = self.start_date, self.end_date
        yf_df = yf.Tickers(list(self.tickers)).history(start=start, end=end)['Close']
        yf_df.index = yf_df.index.tz_localize(None)
        
        for ticker in tickers:
            first_valid = yf_df[ticker].first_valid_index()
            target_start = pd.to_datetime(start)
            
            # missing historical data, notorious with yf
            if first_valid is None or first_valid > target_start:
                csv_path = f"data/{ticker}.csv"
                if os.path.exists(csv_path):
                    print(f"Patching {ticker} data...")
                    csv_df = pd.read_csv(csv_path, index_col="Date", parse_dates=True, dayfirst=True)['Close']
                    yf_df[ticker] = csv_df.combine_first(yf_df[ticker])
                else:
                    print(f"Warning: {ticker} data missing. CSV not found at {csv_path}.")
        
            # currency conversion
            if ticker in self.ccy_conv.keys():
                print(f"Converting currency for {ticker}...")
                ccy_df = yf.Ticker(self.ccy_conv[ticker]).history(start=start, end=end)['Close']
                ccy_df.index = ccy_df.index.tz_localize(None)
                yf_df[ticker] *= ccy_df

        yf_df.loc[[self._date_conv(date) for date in self.days_to_discard], :] = None
        yf_df.ffill(inplace=True)
        print(yf_df.iloc[-1, :])
        return yf_df
    

    def calculate(self) -> None:
        self.price_data = self._get_price_data()
        full_idx = self.price_data.index

        self.holdings = pd.DataFrame(0.0, index=full_idx, columns=list(self.tickers))
        self.invested_data = pd.DataFrame(0.0, index=full_idx, columns=list(self.tickers))
        self.realized_profit_data = pd.DataFrame(0.0, index=full_idx, columns=list(self.tickers))
        
        # holdings (vectorized)
        df_buys = pd.DataFrame(self._purchases, columns=['date', 'ticker', 'qty', 'price'])
        df_sells = pd.DataFrame(self._sales, columns=['date', 'ticker', 'qty', 'price'])
        
        df_sells['qty'] = -df_sells['qty']

        df_trades = pd.concat([df_buys, df_sells])
        df_trades['date'] = pd.to_datetime(df_trades['date'])
        
        daily_trades = df_trades.groupby(['date', 'ticker'])['qty'].sum().reset_index()
        qty_ledger = daily_trades.pivot(index='date', columns='ticker', values='qty')
       
        self.holdings = qty_ledger.reindex(full_idx).fillna(0).cumsum()

        # dividends (vectorized) 
        df_divs = pd.DataFrame(self._dividends, columns=['date', 'ticker', 'amount'])
        df_divs['date'] = pd.to_datetime(df_divs['date'])
        
        div_matrix = df_divs.groupby(['date', 'ticker'])['amount'].sum().unstack()
        div_matrix = div_matrix.reindex(full_idx).fillna(0)

        self.realized_profit_data = (self.holdings * div_matrix).cumsum()

        daily_dividends = (self.holdings * div_matrix).sum(axis=1)

        # invested and realized profit (chronogical because path-dependent)
        tax_lots = {ticker: [] for ticker in self.tickers} 
        
        invested_changes = pd.DataFrame(0.0, index=full_idx, columns=list(self.tickers))
        sales_profit_changes = pd.DataFrame(0.0, index=full_idx, columns=list(self.tickers))

        df_trades = df_trades.sort_values('date')
        
        for _, row in df_trades.iterrows():
            date, ticker, qty, price = row['date'], row['ticker'], row['qty'], row['price']

            if qty > 0:  # buy
                cost = qty * price
                tax_lots[ticker].append({'qty': qty, 'price': price, 'cost': cost})
                invested_changes.at[date, ticker] += cost
            
            elif qty < 0:  # sell
                sell_qty = abs(qty)
                realized_gain = 0.0
                basis_reduction = 0.0
                
                # FIFO
                while sell_qty > 0 and tax_lots[ticker]:
                    oldest_lot = tax_lots[ticker][0]
                    
                    if oldest_lot['qty'] <= sell_qty:  # entire lot
                        realized_gain += oldest_lot['qty'] * (price - oldest_lot['price'])
                        basis_reduction += oldest_lot['cost']
                        sell_qty -= oldest_lot['qty']
                        tax_lots[ticker].pop(0)
                    
                    else:  # partial lot
                        realized_gain += sell_qty * (price - oldest_lot['price'])
                        proportional_cost = sell_qty * oldest_lot['price']
                        basis_reduction += proportional_cost
                        
                        oldest_lot['qty'] -= sell_qty
                        oldest_lot['cost'] -= proportional_cost
                        sell_qty = 0
                
                invested_changes.at[date, ticker] -= basis_reduction
                sales_profit_changes.at[date, ticker] += realized_gain
       
        # aggregates
        self.invested_data = invested_changes.cumsum()
        self.realized_profit_data += sales_profit_changes.cumsum()

        self.portfolio_data = self.price_data * self.holdings
        self.unrealized_profit_data = self.portfolio_data - self.invested_data

        # index and drawdown
        df_trades['cash_flow'] = df_trades['qty'] * df_trades['price']
        daily_cash_flow = df_trades.groupby('date')['cash_flow'].sum().reindex(full_idx).fillna(0)

        total_value = self.portfolio_data.sum(axis=1)
        prev_value = total_value.shift(1).fillna(0)

        # (V_t + D_t - CF_t - V_t-1) / V_t-1
        daily_returns = (total_value + daily_dividends - daily_cash_flow - prev_value) / prev_value.replace(0, np.nan)  
        daily_returns = daily_returns.fillna(0)
        self.index_data = (1 + daily_returns).cumprod()

        rolling_max = self.index_data.cummax()
        self.drawdown_data = (self.index_data - rolling_max) / rolling_max

        # simpler and slower, partial liquidations not supported
        
        # for purchase in self._purchases:
        #     date, ticker, qty, price = self._date_conv(purchase[0]), purchase[1], purchase[2], purchase[3]
        #     self.holdings.loc[self.holdings.index >= date, ticker] += qty
        #     self.invested_data.loc[self.holdings.index >= date, ticker] += qty * price
        
        # for sale in self._sales:
        #     date, ticker, price = self._date_conv(sale[0]), sale[1], sale[2]
        #     tpl = date, ticker
        #     qty = self.holdings.loc[tpl]
        #     invested = self.invested_data.loc[tpl]
        #     self.holdings.loc[self.holdings.index >= date, ticker] -= qty
        #     self.invested_data.loc[self.holdings.index >= date, ticker] -= invested
        #     self.realized_profit_data.loc[self.holdings.index >= date, ticker] += qty * price - invested
        
        # for dividend in self._dividends:
        #     date, ticker, amount = self._date_conv(dividend[0]), dividend[1], dividend[2]
        #     tpl = date, ticker
        #     qty = self.holdings.loc[tpl]
        #     self.realized_profit_data.loc[self.holdings.index >= date, ticker] += qty * amount

    def _legend_axes_and_titles(
        self,
        fig: plt.Figure,
        axes: Iterable[plt.Axes],
        titles: Iterable[str],
        formatter: mtick.Formatter | str,
        ylabel: str | None = None,
        reverse_legend: Iterable[int] | None = None,
    ) -> None:
        reverse_legend = [] if reverse_legend is None else reverse_legend
        for idx, (ax, title) in enumerate(zip(axes, titles)):
            if idx in reverse_legend:
                handles, labels = ax.get_legend_handles_labels()
                ax.legend(handles[::-1], labels[::-1], loc="upper left")
            else:
                ax.legend(loc="upper left")
            
            ax.set_xlabel(None)
            ax.set_ylabel(ylabel)
            ax.minorticks_on()
            ax.grid(which="major", linestyle="-", color="black")
            ax.grid(which="minor", linestyle="--", color="grey", axis="y")
            ax.yaxis.set_major_formatter(formatter)
            ax.set_title(title)

            fig.subplots_adjust(top=0.95, bottom=0.05, left=0.10, right=0.95)

    def default_plot(self) -> None:
        fig, ax = plt.subplots(2, 1, sharex="all")

        ax[0].plot(self.portfolio_data, label=self.portfolio_data.columns)
        _, y1 = ax[0].get_ylim()
        ax[0].set_ylim(0, y1)
                
        ax[1].plot(self.portfolio_data.sum(axis=1), label="value")
        ax[1].plot(self.invested_data.sum(axis=1), label="invested")
        unrealized = self.unrealized_profit_data.sum(axis=1)
        realized = self.realized_profit_data.sum(axis=1)
        ax[1].plot(unrealized, label="unrealized profit")
        ax[1].plot(realized, label="realized profit")
        ax[1].plot(unrealized + realized, label="total profit")
             
        self._legend_axes_and_titles(
            fig,
            ax,
            titles=["Portfolio components", "Absolute aggregates"],
            formatter=mtick.StrMethodFormatter("{x:,.0f}"),
            ylabel="EUR",
        )

    def _calculate_rolling_cagr(self, years: int) -> pd.Series:
        target_dates = self.index_data.index - DateOffset(years=years)
        
        df = self.index_data.to_frame(name="price_index")
        targets = pd.DataFrame({"Date": target_dates})

        merged = pd.merge_asof(targets, df.reset_index(), left_on="Date", right_on="Date", direction="backward")

        start_values = merged["price_index"].values
        end_values = self.index_data.values
        cagr = (end_values / start_values) ** (1.0 / years) - 1.0
        return pd.Series(cagr, index=self.index_data.index)
    
    def metrics_plot(self) -> None:        
        fig, ax = plt.subplots(3, 1, sharex="all")
        
        ax[0].plot(self.index_data - 1, label="portfolio index")
        ax[0].plot(self.drawdown_data, label="drawdown")

        for years in [1, 2, 3, 5]:
            rolling = self._calculate_rolling_cagr(years)
            ax[1].plot(rolling, label=f"{years}Y")

        weights_df = pd.DataFrame(self.alloc_matrix).T.fillna(0.0)
        weights_df = weights_df.reindex(self.portfolio_data.columns).fillna(0.0)
        df_asset_alloc = self.portfolio_data.dot(weights_df)
        df_asset_alloc = df_asset_alloc.div(self.portfolio_data.sum(axis=1), axis=0)

        desired_order = [AssetClass.STOCKS, AssetClass.GOLD, AssetClass.BONDS]
        order = [col for col in desired_order if col in df_asset_alloc.columns]
        df_asset_alloc = df_asset_alloc[order]

        df_asset_alloc.plot.area(ax=ax[2], linewidth=0)

        self._legend_axes_and_titles(
            fig,
            ax,
            titles=["Cumulative performance", "Rolling CAGR", "Asset allocation"],
            formatter=mtick.PercentFormatter(xmax=1.0),
            reverse_legend=[2]
        )
    
    def show_plots(self) -> None:
        plt.show()

    def _print_table(self, df_slice: pd.DataFrame, title: str, period: str, label: str, ccy_symbol: str) -> None:
        width = 50
        print(f"\n{'=' * width}")
        print(title)
        print(f"{'=' * width}")
        print(f"{label:<14}{f'Absolute ({ccy_symbol})':>18}{'Return (%)':>18}")
        print(f"{'-' * 14}{'-' * 18}{'-' * 18}")
        for date_val, row in df_slice.iterrows():
            # Format Timestamp for days; PeriodIndex converts cleanly via str()
            date_str = date_val.strftime("%Y-%m-%d") if period == "day" else str(date_val)
            abs_str = f"{row['Absolute']:+,.2f}"
            pct_str = f"{row['Relative']:+.2%}"
            print(f"{date_str:<14}{abs_str:>18}{pct_str:>18}")

    def print_best_worst_periods(
        self, period: Literal["day", "month", "year"] = "day", n: int = 5, ccy_symbol: str = "EUR"
    ) -> None:
        if period not in ("day", "month", "year"):
            raise ValueError("period must be 'day', 'month', or 'year'")

        daily_pct = self.index_data.pct_change().fillna(0.0)
        total_profit = (self.unrealized_profit_data.sum(axis=1) + self.realized_profit_data.sum(axis=1))
        daily_abs = total_profit.diff().fillna(total_profit.iloc[0])

        if period == "day":
            pct_returns = daily_pct
            abs_returns = daily_abs
            label = "Date"
        else:
            freq = "M" if period == "month" else "Y"
            label = "Month" if period == "month" else "Year"

            # Group by calendar PeriodIndex (e.g., '2026-08' or '2026')
            period_idx = daily_pct.index.to_period(freq)

            # Compound daily percentage returns: prod(1 + r) - 1
            pct_returns = (1.0 + daily_pct).groupby(period_idx).prod() - 1.0

            # Telescoping sum of daily absolute PnL changes
            abs_returns = daily_abs.groupby(period_idx).sum()

        df_summary = pd.DataFrame({"Absolute": abs_returns, "Relative": pct_returns}).dropna()

        if period == "year":
            self._print_table(df_summary, "Year by year", period, label, ccy_symbol)
        else:
            self._print_table(
                df_summary.nlargest(n, "Relative"), f"Top {n} best {period}s (relative)", period, label, ccy_symbol
            )
            self._print_table(
                df_summary.nsmallest(n, "Relative"), f"Top {n} worst {period}s (relative)", period, label, ccy_symbol
            )
            self._print_table(
                df_summary.nlargest(n, "Absolute"), f"Top {n} best {period}s (absolute)", period, label, ccy_symbol
            )
            self._print_table(
                df_summary.nsmallest(n, "Absolute"), f"Top {n} worst {period}s (absolute)", period, label, ccy_symbol
            )
