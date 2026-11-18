from decimal import Decimal, InvalidOperation
from .filing_extraction import FilingExtraction, FinancialValue

def amount(figure: FinancialValue|None)->Decimal|None:
    if figure is None:
        return None
    return Decimal(figure.amount)*figure.scale

def sum_amounts(*values: Decimal|None)->Decimal|None:
    if any(value is None for value in values):
        return None
    return sum((value for value in values if value is not None), Decimal(0))

def subtract(left: Decimal|None, right: Decimal|None)->Decimal|None:
    if left is None or right is None:
        return None
    return left-right

def average(left:Decimal|None, right: Decimal|None)->Decimal|None:
    total=sum_amounts(left, right)
    return total/2 if total is not None else None

def ratio(numerator: Decimal|None, denominator: Decimal|None)->Decimal|None:
    if numerator is None or denominator is None or denominator<=0:
        return None
    return numerator/denominator    

def percent(numerator: Decimal|None, denominator: Decimal|None)->Decimal|None:
    result=ratio(numerator, denominator)
    return result*100 if result is not None else None

def invested_capital(filing: FilingExtraction)->Decimal|None:
    debt_and_equity=sum_amounts(
        amount(filing.long_term_debt),
        amount(filing.shareholders_equity)
    )
    return subtract(debt_and_equity, amount(filing.cash_and_cash_equivalents))

def calculate_financial_metrics(
        filing: FilingExtraction,
        previous: FilingExtraction|None=None,
        *,
        wacc_pct: Decimal|None=None,
)->dict[str, Decimal|None]:
    revenue=amount(filing.revenue)
    cost_of_revenue=amount(filing.cost_of_revenue)
    gross_profit=amount(filing.gross_profit)
    operating_income=amount(filing.operating_income)
    net_income=amount(filing.net_income)

    if gross_profit is None:
        gross_profit=subtract(revenue, cost_of_revenue)

    cash=amount(filing.cash_and_cash_equivalents)
    short_term_investments=amount(filing.short_term_investments)
    receivables=amount(filing.accounts_receivable)
    current_assets=amount(filing.current_assets)
    current_liabilities=amount(filing.current_liabilities)
    total_assets=amount(filing.total_assets)

    cash_and_investments=sum_amounts(cash, short_term_investments)
    quick_assets=sum_amounts(cash_and_investments, receivables)
    
    total_debt = amount(filing.total_debt)
    if total_debt is None:
        total_debt = sum_amounts(
            amount(filing.short_term_debt),
            amount(filing.current_portion_of_long_term_debt),
            amount(filing.long_term_debt),
        )

    operating_cash_flow=amount(filing.operating_cash_flow)
    capex=amount(filing.capital_expenditures)
    free_cash_flow=subtract(
        operating_cash_flow,
        abs(capex) if capex is not None else None
    )

    tax_rate=ratio(
        amount(filing.income_tax_expense),
        amount(filing.pretax_income)
    )

    after_tax_operating_income=None
    if operating_income is not None and tax_rate is not None:
        after_tax_operating_income=operating_income*(1-tax_rate)
    revenue_growth_pct=None
    average_inventory=None
    average_invested_capital=None

    if previous is not None:
        previous_revenue=amount(previous.revenue)
        revenue_growth_pct=percent(
            subtract(revenue, previous_revenue),
            previous_revenue
        )
        average_inventory=average(
            amount(filing.inventory),
            amount(previous.inventory)
        )

        average_invested_capital=average(
            invested_capital(filing),
            invested_capital(previous)
        )

    roic_pct=percent(after_tax_operating_income, average_invested_capital)
    
    return {
    "revenue_growth_pct": revenue_growth_pct,
    "gross_margin_pct": percent(gross_profit, revenue),
    "operating_margin_pct": percent(operating_income, revenue),
    "net_profit_margin_pct": percent(net_income, revenue),
    "working_capital": subtract(current_assets, current_liabilities),
    "current_ratio": ratio(current_assets, current_liabilities),
    "quick_ratio": ratio(quick_assets, current_liabilities),
    "cash_ratio": ratio(cash_and_investments, current_liabilities),
    "debt_to_assets_pct": percent(total_debt, total_assets),
    "inventory_turnover": ratio(cost_of_revenue, average_inventory),
    "free_cash_flow": free_cash_flow,
    "free_cash_flow_margin_pct": percent(free_cash_flow, revenue),
    "average_invested_capital": average_invested_capital,
    "roic_pct": roic_pct,
    "fcf_return_on_invested_capital_pct": percent(
        free_cash_flow, average_invested_capital
    ),
    "wacc_pct": wacc_pct,
    "roic_spread_pct_points": subtract(roic_pct, wacc_pct),
    "total_debt": total_debt,
    "long_term_debt": amount(filing.long_term_debt),
    "shareholders_equity": amount(filing.shareholders_equity),
    "cash_and_cash_equivalents": cash,
    "ending_invested_capital": invested_capital(filing),
    "after_tax_operating_income": after_tax_operating_income,
}


def weighted_debt_rate_pct(filing: FilingExtraction) -> Decimal | None:
    tranches = filing.long_term_debt_tranches
    if not tranches:
        return None

    if len({tranche.principal.currency for tranche in tranches}) != 1:
        return None

    total_principal = Decimal("0")
    weighted_rates = Decimal("0")

    for tranche in tranches:
        if tranche.annual_rate_pct is None:
            return None

        try:
            principal = amount(tranche.principal)
            rate_pct = Decimal(tranche.annual_rate_pct)
        except InvalidOperation:
            return None

        if (
            principal is None
            or not principal.is_finite()
            or principal <= 0
            or not rate_pct.is_finite()
        ):
            return None

        total_principal += principal
        weighted_rates += principal * rate_pct

    return ratio(weighted_rates, total_principal)


def calculate_wacc_pct(
    *,
    market_cap: Decimal,
    debt_value: Decimal,
    beta: Decimal,
    risk_free_rate_pct: Decimal,
    equity_risk_premium_pct: Decimal,
    pretax_debt_rate_pct: Decimal | None,
    tax_rate_pct: Decimal | None,
) -> Decimal | None:
    if market_cap <= 0 or debt_value < 0:
        return None

    cost_of_equity_pct = risk_free_rate_pct + beta * equity_risk_premium_pct

    if debt_value == 0:
        return cost_of_equity_pct

    if pretax_debt_rate_pct is None or tax_rate_pct is None:
        return None
    if not 0 <= tax_rate_pct <= 100:
        return None

    total_capital = market_cap + debt_value
    after_tax_debt_rate_pct = pretax_debt_rate_pct * (1 - tax_rate_pct / 100)

    return (
        market_cap / total_capital * cost_of_equity_pct
        + debt_value / total_capital * after_tax_debt_rate_pct
    )


def calculate_valuation(
    filing: FilingExtraction,
    metrics: dict[str, Decimal | None],
    price: Decimal,
) -> dict[str, Decimal | None]:
    shares = filing.fiscal_year_end_shares_outstanding
    market_cap = price * shares if shares is not None and shares > 0 else None

    debt_and_equity = sum_amounts(market_cap, metrics.get("total_debt"))
    cash = metrics.get("cash_and_cash_equivalents")
    enterprise_value = subtract(debt_and_equity, cash)

    ebitda = sum_amounts(
        amount(filing.operating_income),
        amount(filing.depreciation_and_amortization),
    )

    return {
        "pe_ratio": ratio(price, amount(filing.diluted_eps)),
        "ev_to_ebitda": ratio(enterprise_value, ebitda),
        "ev_to_fcf": ratio(enterprise_value, metrics.get("free_cash_flow")),
    }
