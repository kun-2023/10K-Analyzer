from openai import OpenAI
from .filing_extraction import extract_filing
from .filing_validation import validate_pdf_uploads,validate_extracted_filings
from .financial_comparison import build_financial_comparison
from .report_generation import (
    generate_company_development,
    generate_financial_overview
)

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
    }