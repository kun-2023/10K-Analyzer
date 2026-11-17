import os
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from backend.app.services.filing_extraction import extract_filing
from backend.app.services.financial_metrics import calculate_financial_metrics
from backend.app.services.financial_comparison import build_financial_comparison
from backend.app.services.report_generation import generate_financial_overview
from backend.app.services.report_generation import generate_company_development
from backend.app.services.filing_validation import validate_pdf_uploads
from backend.app.services.analysis_service import analyze_filings


current_pdf = Path("samples/sample_10k.pdf")
previous_pdf = Path("samples/adobe_2024.pdf")

for pdf in (current_pdf, previous_pdf):
    if not pdf.is_file():
        raise SystemExit(f"Missing PDF: {pdf}")

load_dotenv(".env", override=True)
api_key = os.getenv("OPENAI_API_KEY", "").strip()
if not api_key:
    raise SystemExit("Set OPENAI_API_KEY in .env before running the test.")

client = OpenAI(api_key=api_key)

pdf_paths = [current_pdf, previous_pdf, Path("samples/adbe_2023.pdf")]

for path in pdf_paths:
    if not path.is_file():
        raise SystemExit(f"Missing PDF: {path}")

uploads = [(path.name, path.read_bytes()) for path in pdf_paths]
result = analyze_filings(uploads, client=client)

comparison = result["comparison"]
assert [period[:4] for period in comparison] == ["2023", "2024", "2025"]

latest_period = max(comparison)
roic = comparison[latest_period]["roic_pct"]
assert roic is not None, "FY2025 ROIC is missing"
assert round(roic, 2) == Decimal("61.74"), f"Unexpected FY2025 ROIC: {roic}"

assert result["financial_overview"].strip(), "Financial Overview is empty"
assert result["company_development"].strip(), "Company Development is empty"

print("PASS: Adobe analysis returned all three years, FY2025 ROIC, and both report sections.")
print("\nFinancial Overview")
print(result["financial_overview"])
print("\nCompany Development")
print(result["company_development"])