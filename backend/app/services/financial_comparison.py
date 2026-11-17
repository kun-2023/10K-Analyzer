from datetime import date
from decimal import Decimal
from .filing_extraction import FilingExtraction
from .financial_metrics import amount, calculate_financial_metrics

def build_financial_comparison(
        filings: list[FilingExtraction],
)->dict[str, dict[str, Decimal|None]]:
    sorted_filings=sorted(
        filings,
        key=lambda filing: date.fromisoformat(filing.fiscal_year_end),
    )

    comparison: dict[str, dict[str, Decimal|None]]={}
    previous_filing: FilingExtraction|None=None

    for filing in sorted_filings:
        period_end=filing.fiscal_year_end
        if period_end in comparison:
            raise ValueError(f"Duplicare fiscal")
        prior_year=None
        if previous_filing is not None:
            days_between=(
                date.fromisoformat(period_end)
                - date.fromisoformat(previous_filing.fiscal_year_end)
            ).days

            # Match annual filings roughly one year apart
            if 350<=days_between<=380:
                prior_year=previous_filing

        metrics=calculate_financial_metrics(filing, previous=prior_year)
        comparison[period_end]={
            "revenue": amount(filing.revenue),
            "operating_income": amount(filing.operating_income),
            "net_income":amount(filing.net_income),
            **metrics
        }

        previous_filing=filing
    return comparison
