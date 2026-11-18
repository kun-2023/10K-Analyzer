import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv


load_dotenv(".env")
st.set_page_config(page_title="Financial Dashboard", layout="wide")

repo_url = os.getenv("ANALYZER_REPO_URL", "")
if repo_url:
    st.sidebar.link_button("View GitHub repo", repo_url)

st.title("Financial Dashboard")

analysis = st.session_state.get("analysis")
if not analysis or not analysis.get("comparison"):
    st.info("Generate a report on the Report page first.")
    st.stop()

comparison = analysis["comparison"]
currency = analysis["currency"]
periods = sorted(comparison)
latest_period = periods[-1]
latest = comparison[latest_period]
card_values = {**latest, **analysis.get("valuation", {})}


def format_value(value, unit):
    if value is None:
        return "N/A"

    number = float(value)
    if unit == "money":
        return f"{number / 1_000_000:,.2f}"
    return f"{number:,.2f}{unit}"


st.header(analysis["company_name"])
st.caption(f"KPIs for the fiscal year ended {latest_period}")


quote = analysis.get("market_quote")
if quote:
    if quote["price_type"] == "regular_session_quote":
        timestamp = pd.Timestamp(quote["as_of"]).tz_convert("America/Toronto")
        label = f"Latest quote · {timestamp:%Y-%m-%d %I:%M:%S %p %Z}"
    else:
        label = f"Last close · {quote['trading_date']}"

    price = float(quote["price"])
    st.caption(
        f"{quote['symbol']} {quote['currency']} {price:,.2f} · {label} · "
        f"{quote['source']} · Financials ended {latest_period}"
    )

kpis = [
    ("ROIC", "roic_pct", "%"),
    ("WACC", "wacc_pct", "%"),
    ("ROIC − WACC", "roic_spread_pct_points", " pp"),
    ("P/E", "pe_ratio", "×"),
    ("EV/EBITDA", "ev_to_ebitda", "×"),
    ("EV/Free Cash Flow", "ev_to_fcf", "×"),
]

for start in (0, 3):
    for column, (label, key, unit) in zip(st.columns(3), kpis[start:start + 3]):
        column.metric(label, format_value(card_values.get(key), unit))

st.subheader("Fiscal-Year Comparison")
st.caption(f"Monetary figures are in {currency} millions. Column dates are fiscal year-ends.")

rows = [
    ("Revenue", "revenue", "money"),
    ("Revenue growth", "revenue_growth_pct", "%"),
    ("Operating income", "operating_income", "money"),
    ("Net income", "net_income", "money"),
    ("Gross margin", "gross_margin_pct", "%"),
    ("Operating margin", "operating_margin_pct", "%"),
    ("Net profit margin", "net_profit_margin_pct", "%"),
    ("Free cash flow", "free_cash_flow", "money"),
    ("Free cash flow margin", "free_cash_flow_margin_pct", "%"),
    ("Working capital", "working_capital", "money"),
    ("Current ratio", "current_ratio", "×"),
    ("Quick ratio", "quick_ratio", "×"),
    ("Cash ratio", "cash_ratio", "×"),
    ("Debt-to-assets", "debt_to_assets_pct", "%"),
    ("Inventory turnover", "inventory_turnover", "×"),
    ("Total debt", "total_debt", "money"),
    ("Noncurrent debt", "long_term_debt", "money"),
    ("Book equity", "shareholders_equity", "money"),
    ("Cash and cash equivalents", "cash_and_cash_equivalents", "money"),
    ("Ending invested capital", "ending_invested_capital", "money"),
    ("Average invested capital", "average_invested_capital", "money"),
    ("After-tax operating income", "after_tax_operating_income", "money"),
    ("FCF return on invested capital", "fcf_return_on_invested_capital_pct", "%"),
    ("ROIC", "roic_pct", "%"),
]

table = pd.DataFrame(
    [
        {
            "Metric": label,
            **{
                period: format_value(comparison[period].get(key), unit)
                for period in periods
            },
        }
        for label, key, unit in rows
    ]
)

st.dataframe(table, width="stretch", height="content", hide_index=True)