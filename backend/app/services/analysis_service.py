from openai import OpenAI
from .filing_extraction import extract_filing
from .filing_validation import validate_pdf_uploads,validate_extracted_filings
from .financial_comparison import build_financial_comparison
from .report_generation import (
    generate_company_development,
    generate_financial_overview
)
import logging
from decimal import Decimal
from .financial_metrics import calculate_valuation, weighted_debt_rate_pct
from .market_data import get_valuation_price

def analyze_filings(uploads: list[tuple[str, bytes]], *, client: OpenAI)->dict:
    validate_pdf_uploads(uploads)

    filings=[]
    pdfs_by_period={}
    for filename, pdf_bytes in uploads:
        filing=extract_filing(pdf_bytes, filename=filename, client=client)
        filings.append(filing)
        pdfs_by_period[filing.fiscal_year_end]=pdf_bytes
    validate_extracted_filings(filings)
    currencies={
        figure.currency for filing in filings 
        for figure in (filing.revenue, filing.net_income, filing.total_assets)
        if figure is not None
    }
    if len(currencies)!=1:
        raise ValueError("The filings must have one identifiable reporting currency.")
    currency=currencies.pop()
    company_name=filings[0].company_name
    comparison=build_financial_comparison(filings)

    latest_filing = max(filings, key=lambda filing: filing.fiscal_year_end)
    print("Weighted debt rate (%):", weighted_debt_rate_pct(latest_filing))
    print("Debt tranches:", latest_filing.long_term_debt_tranches)
    
    latest_metrics = comparison[latest_filing.fiscal_year_end]
    print(
    "ROIC check:",
    latest_filing.fiscal_year_end,
    "after-tax operating income =", latest_metrics["after_tax_operating_income"],
    "average invested capital =", latest_metrics["average_invested_capital"],
    "ROIC % =", latest_metrics["roic_pct"],
)

    quote = None
    valuation = {}

    if latest_filing.trading_symbol:
        try:
            quote = get_valuation_price(latest_filing.trading_symbol)
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "Market data unavailable: %s", type(exc).__name__
            )

    if quote and quote["currency"] == currency:
        valuation = calculate_valuation(
            latest_filing,
            latest_metrics,
            Decimal(quote["price"]),
        )

    return {
        "company_name": company_name,
        "currency": currency,
        "comparison": comparison,
        "financial_overview": generate_financial_overview(
            comparison,
            company_name=company_name,
            currency=currency,
            client=client,
        ),
        "company_development": generate_company_development(
            comparison,
            company_name=company_name,
            pdfs_by_period=pdfs_by_period,
            client=client,
        ),
        "market_quote": quote,
        "valuation":valuation
    }