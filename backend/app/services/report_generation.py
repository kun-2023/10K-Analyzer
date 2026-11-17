import json
from decimal import Decimal
from openai import OpenAI
from base64 import b64encode

FINANCIAL_OVERVIEW_PROMPT="""
Write the Financial Overview section of a 10-K analysis report.
Use only the supplied data. Write one paragraph of at most 100 words.
Focus on the two or three most important trends. Describe dips and
rebounds in chronological order. Refer to ROIC as a calculated metric.

- For one fiscal year, summarize the available results.
- For two or three fiscal years, compare the results chronologically.
- Focus on revenue, profitability, margins, free cash flow, and ROIC.
- Monetary figures are in full units of the supplied reporting currency.
  Display large amounts in millions or billions and label the units.
- Values ending in _pct are already percentages. Express changes between
  percentages in percentage points.
- Treat null values as unavailable. Never treat them as zero.
- Leave explanations about company events or causes to Company Development.
- Start directly with the overview text. Omit the section heading.
"""

COMPANY_DEVELOPMENT_PROMPT = """
Write the Company Development section of a 10-K analysis report.
Review Item 1 (Business), Item 7 (MD&A), and relevant notes in
the supplied filings. Return the section without a heading.

Write one development bullet per supplied fiscal year, oldest first,
with at most 40 words per bullet. Prioritize material product launches,
strategic initiatives, partnerships, market expansion, acquisitions,
divestitures, and terminated deals. Distinguish announcements from
completed actions. Include material events whose impact is undisclosed.

Connect developments to financial results when the filing supports the
link. Distinguish management's explanation from your inference. Use the
supplied operating-margin changes verbatim when quantifying them.
Describe a specific expense as one contributor to a margin change
unless the filing attributes the entire change to it. Cite the fiscal
year and relevant filing section for each bullet.

After the development bullets, add one short buyback line for each fiscal
year with disclosed repurchases. These lines are outside the 40-word cap.
Report full-year shares delivered and cash paid, where disclosed.
Distinguish actual activity from repurchase authorizations.

Include an average price only when the filing reports it for the same
shares and period. If prices are reported by tranche or for a shorter
period, pair each price with the corresponding share count and label
the tranche or period. Omit the price if no matching average is reported.
Cite the fiscal year and filing section for each buyback line.

Create development bullets and buyback lines only for fiscal years listed
in metrics_by_fiscal_year_end. Earlier years may appear as context inside
a supplied year's bullet.
"""

def generate_financial_overview(
        comparison: dict[str, dict[str, Decimal|None]],
        *,
        company_name: str,
        currency:str,
        client: OpenAI,
        model: str="gpt-5.4-mini"
)->str:
    if not comparison:
        raise ValueError("Provide at least one fiscal year for the overview.")
    payload={
        "company_name":company_name,
        "reporting_currency": currency,
        "metrics_by_fiscal_year_end":comparison,
    }

    response=client.responses.create(
        model=model,
        instructions=FINANCIAL_OVERVIEW_PROMPT,
        input=json.dumps(payload, default=str),
        store=False,
    )

    overview=response.output_text.strip()
    if response.status!="completed" or not overview:
        raise RuntimeError(
            f"Financial overview genration didn't complete "
            f"(status: {response.status})"
        )
    return overview

def generate_company_development(
        comparison: dict[str, dict[str, Decimal|None]],
        *,
        company_name: str,
        pdfs_by_period: dict[str, bytes],
        client: OpenAI,
        model: str="gpt-5.4-mini",
)->str:
    if not comparison or comparison.keys()!=pdfs_by_period.keys():
        raise ValueError("Provide one PDF foor each fiscal year in the comparison.")
    
    periods = sorted(comparison)
    operating_margin_changes = {}

    for earlier, later in zip(periods, periods[1:]):
        earlier_margin = comparison[earlier]["operating_margin_pct"]
        later_margin = comparison[later]["operating_margin_pct"]

        if earlier_margin is not None and later_margin is not None:
            change = later_margin - earlier_margin
            operating_margin_changes[f"{earlier} to {later}"] = (
                f"{change:+.2f} percentage points"
            )
    
    payload={
        "company_name": company_name,
        "metrics_by_fiscal_year_end":comparison,
        "operating_margin_changes": operating_margin_changes,
    }

    content=[
        {"type":"input_text", "text":json.dumps(payload, default=str)}
    ]

    for period_end, pdf_bytes in sorted(pdfs_by_period.items()):
        encoded_pdf=b64encode(pdf_bytes).decode("ascii")
        content.append({
            "type": "input_file",
            "filename":f"10k-{period_end}.pdf",
            "file_data":f"data:application/pdf;base64,{encoded_pdf}",
        })

    response=client.responses.create(
        model=model,
        instructions=COMPANY_DEVELOPMENT_PROMPT,
        input=[{"role":"user", "content":content}],
        store=False
    )

    development=response.output_text.strip()
    if response.status!="completed" or not development:
        raise RuntimeError(
        f"Company Development generation did not complete "
        f"(status: {response.status}).")
    return development