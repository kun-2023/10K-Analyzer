from base64 import b64encode
from openai import OpenAI
from pydantic import BaseModel
import hashlib
import json
import os
import tempfile
from pathlib import Path



class FinancialValue(BaseModel):
    label: str
    amount: str
    currency: str
    scale: int
    section: str

class DebtTranche(BaseModel):
    principal: FinancialValue
    annual_rate_pct: str | None

class FilingExtraction(BaseModel):
    company_name: str
    fiscal_year_end: str
    # income statement
    revenue: FinancialValue|None
    cost_of_revenue: FinancialValue|None
    gross_profit: FinancialValue|None
    operating_income: FinancialValue|None
    pretax_income: FinancialValue|None
    income_tax_expense: FinancialValue|None
    net_income: FinancialValue|None
    # balance sheet
    cash_and_cash_equivalents: FinancialValue|None
    short_term_investments: FinancialValue|None
    accounts_receivable: FinancialValue|None
    inventory: FinancialValue|None
    current_assets: FinancialValue|None
    total_assets: FinancialValue|None
    current_liabilities: FinancialValue|None
    short_term_debt: FinancialValue|None
    current_portion_of_long_term_debt: FinancialValue|None
    long_term_debt: FinancialValue|None
    total_debt: FinancialValue | None
    shareholders_equity: FinancialValue|None
    # Cash flow statement
    operating_cash_flow: FinancialValue|None
    capital_expenditures: FinancialValue|None
    # real time stock price
    trading_symbol: str|None=None
    diluted_eps: FinancialValue | None = None
    depreciation_and_amortization: FinancialValue | None = None
    fiscal_year_end_shares_outstanding: int | None = None
    long_term_debt_tranches: list[DebtTranche] | None = None


EXTRACTION_PROMPT = """
Extract financial statement data from the supplied 10-K.

Use the consolidated financial statements and their notes. Select the
fiscal year covered by this filing. Use that year's column for income
and cash flow figures and its closing date for balance sheet figures.
Return fiscal_year_end in YYYY-MM-DD format.

For every reported value, return:
- label: the original line-item label.
- amount: the signed number as a string, without commas or currency
  symbols. Convert parentheses around a number to a minus sign.
- currency: the reported currency code, such as USD.
- scale: the statement's unit multiplier, such as 1, 1000, or 1000000.
  Keep the amount in the statement's original units.
- section: the statement or note title.

For total_debt, use the reported carrying amount of total borrowings.
If no total is stated, use the debt note and balance sheet only when
they establish all current and noncurrent borrowings. Treat a dash as
zero only when it clearly means zero for that line item. Return null
if the total cannot be established.

Return null if a value is unavailable, ambiguous, or inapplicable.
Use zero only when the filing explicitly reports zero.

Apply these field definitions:
- Net income and equity should be attributable to the parent company
  where the filing distinguishes parent and noncontrolling interests.
- Accounts receivable means current net trade receivables.
- Short-term investments exclude cash equivalents.
- Short-term debt means borrowings excluding the current portion of
  long-term debt. Populate these two fields separately only when the
  filing identifies their amounts separately.
- Long-term debt means the noncurrent portion of borrowings under
  this schema.
- Capital expenditures means cash purchases of property and equipment.
  Preserve the sign shown on the cash flow statement.
- trading_symbol: Use the common stock ticker on the 10-K cover page.
  If the filing lists multiple common share classes with different
  tickers, return null.
- diluted_eps: Use reported annual diluted earnings per common share.
  This is a per-share value, so use scale 1.
- depreciation_and_amortization: Use the reported consolidated full-year
  amount, preferably from the statement of cash flows.
- fiscal_year_end_shares_outstanding: Use common shares outstanding
  on the fiscal year-end date. Return the full share count as an integer.
  If the filing only gives a later cover-page count or a weighted-average
  count, return null.

- long_term_debt_tranches: Use the debt note for the filing's fiscal
  year-end. Return each outstanding long-term borrowing separately,
  with its reported outstanding principal and annual interest rate.
  Express the rate in percent units, such as "4.25" for 4.25%.
  Include outstanding long-term issues with current maturities.
  Exclude short-term borrowings and undrawn credit facilities.
  For floating-rate debt, use the disclosed fiscal year-end rate when
  available. If a tranche's rate is unavailable, keep the principal
  and return null for the rate. Return null for the list if the
  filing does not disclose a usable tranche breakdown.
  Return one numeric percentage per debt tranche. If the filing reports
  a range for a group of notes, split the group only when the filing
  discloses each tranche's outstanding principal and matching rate.
  Otherwise keep the group principal and return null for the rate.

- fiscal_year_end_shares_outstanding: Return the full number of common
  shares outstanding at fiscal year-end. Apply the statement's unit
  multiplier. For example, 413 reported "in millions" means 413000000.
  Use outstanding shares, excluding treasury shares. Return null if
  only a later cover-page count or weighted-average count is available.
  
Extract reported figures. Leave ratio calculations to Python.
"""

def extract_filing(
        pdf_bytes: bytes,
        *,
        client: OpenAI,
        filename: str="filing.pdf",
        model: str="gpt-5.4-mini",
)-> FilingExtraction:
    if not pdf_bytes:
        raise ValueError("The Uploaded pdf is empty")

    cache_dir = Path(__file__).resolve().parents[3] / ".cache" / "extractions"

    configuration = json.dumps(
        {
            "model": model,
            "prompt": EXTRACTION_PROMPT,
            "schema": FilingExtraction.model_json_schema(),
        },
        sort_keys=True,
    )

    cache_key = hashlib.sha256(
        pdf_bytes + configuration.encode("utf-8")
    ).hexdigest()
    cache_path = cache_dir / f"{cache_key}.json"

    if cache_path.exists():
        cached = FilingExtraction.model_validate_json(
            cache_path.read_text(encoding="utf-8")
        )
        print(f"Extraction cache hit: {filename}")
        return cached

    print(f"Extracting through API: {filename}")

    encoded_pdf=b64encode(pdf_bytes).decode("ascii")

    response=client.responses.parse(
        model=model,
        instructions=EXTRACTION_PROMPT,
        input=[{
            "role":"user",
            "content": [{
                "type": "input_file",
                "filename": filename,
                "file_data": f"data:application/pdf;base64,{encoded_pdf}"
            }],
        }],
        text_format=FilingExtraction,
        store=False
    )
    result=response.output_parsed
    if response.status != "completed" or result is None:
      raise RuntimeError(
            f"Extraction did not complete (status: {response.status})."
        )

    cache_dir.mkdir(parents=True, exist_ok=True)
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=cache_dir,
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(result.model_dump_json(indent=2))

        os.replace(temporary_path, cache_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    print(f"Extraction saved: {filename}")
    return result

