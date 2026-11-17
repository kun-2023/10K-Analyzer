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
validate_pdf_uploads([(path.name, path.read_bytes()) for path in pdf_paths])
print("PASS: All three Adobe PDFs are readable.")

current = extract_filing(
    current_pdf.read_bytes(), filename=current_pdf.name, client=client
)
previous = extract_filing(
    previous_pdf.read_bytes(), filename=previous_pdf.name, client=client
)

if not current.fiscal_year_end.startswith("2025-"):
    raise SystemExit(f"Expected FY2025, got {current.fiscal_year_end}")

if not previous.fiscal_year_end.startswith("2024-"):
    raise SystemExit(f"Expected FY2024, got {previous.fiscal_year_end}")

metrics = calculate_financial_metrics(current, previous=previous)

for name, value in metrics.items():
    display = f"{value:,.2f}" if value is not None else "N/A"
    print(f"{name}: {display}")

expected_metrics = {
    "operating_margin_pct": Decimal("36.63"),
    "net_profit_margin_pct": Decimal("30.00"),
    "roic_pct": Decimal("61.74"),
}

for name, expected in expected_metrics.items():
    actual = metrics[name]
    if actual is None or round(actual, 2) != expected:
        raise SystemExit(f"FAIL: {name}: expected {expected}, got {actual}")

print("\nPASS: Adobe FY2025 operating margin, net profit margin, and ROIC.")

comparison=build_financial_comparison([current, previous])

assert list(comparison) == [previous.fiscal_year_end, current.fiscal_year_end]
assert comparison[previous.fiscal_year_end]["roic_pct"] is None
#assert round(comparison[current.fiscal_year_end]["roic_pct"], 2) == Decimal("61.74")
current_roic = comparison[current.fiscal_year_end]["roic_pct"]
assert current_roic is not None, "FY2025 comparison ROIC is missing"
assert round(current_roic, 2) == Decimal("61.74")

print("PASS: Financial comparison sorted both years and used FY2024 for FY2025 ROIC.")

oldest_pdf = Path("samples/adbe_2023.pdf")
if not oldest_pdf.is_file():
    raise SystemExit(f"Missing PDF: {oldest_pdf}")

oldest = extract_filing(
    oldest_pdf.read_bytes(), filename=oldest_pdf.name, client=client
)
assert oldest.fiscal_year_end.startswith("2023-"), oldest.fiscal_year_end

three_years = build_financial_comparison([current, oldest, previous])

assert list(three_years) == [
    oldest.fiscal_year_end,
    previous.fiscal_year_end,
    current.fiscal_year_end,
]
assert three_years[oldest.fiscal_year_end]["roic_pct"] is None
assert three_years[previous.fiscal_year_end]["roic_pct"] is not None, (
    "FY2024 ROIC is missing. Check the FY2023 balances and FY2024 inputs."
)

print("PASS: Three-year comparison sorted FY2023–FY2025 and calculated FY2024 ROIC.")

periods = list(three_years)

rows = [
    ("Revenue (USD millions)", "revenue", False),
    ("Operating margin", "operating_margin_pct", True),
    ("Net profit margin", "net_profit_margin_pct", True),
    ("Free cash flow (USD millions)", "free_cash_flow", False),
    ("ROIC", "roic_pct", True),
]

print("\nAdobe three-year comparison")
print(f"{'Metric':<32}" + "".join(f"{'FY' + period[:4]:>14}" for period in periods))
print("-" * (32 + 14 * len(periods)))

for label, key, is_percent in rows:
    cells = []
    for period in periods:
        value = three_years[period][key]

        if value is None:
            cell = "N/A"
        elif is_percent:
            cell = f"{value:.2f}%"
        else:
            cell = f"{value / 1_000_000:,.0f}"

        cells.append(f"{cell:>14}")

    print(f"{label:<32}" + "".join(cells))

overview=generate_financial_overview(
    three_years,
    company_name=current.company_name,
    currency="USD",
    client=client
)

print("\nFinancial Overview")
print(overview)

development = generate_company_development(
    three_years,
    company_name=current.company_name,
    pdfs_by_period={
        oldest.fiscal_year_end: oldest_pdf.read_bytes(),
        previous.fiscal_year_end: previous_pdf.read_bytes(),
        current.fiscal_year_end: current_pdf.read_bytes(),
    },
    client=client,
)

print("\nCompany Development")
print(development)