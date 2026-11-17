from base64 import b64encode
from openai import OpenAI
from pydantic import BaseModel



class FinancialValue(BaseModel):
    label: str
    amount: str
    currency: str
    scale: int
    section: str

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
    if result is None:
        raise RuntimeError(
            f"OpenAI returned no parsed filing data (status: {response.status})."
        )
    return result

