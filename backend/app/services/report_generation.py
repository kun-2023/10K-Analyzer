import json
import os
import inspect
import tempfile
import hashlib
from decimal import Decimal
from openai import OpenAI
from functools import wraps
from pathlib import Path
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
Write the business analysis for a 10-K report. Review Item 1 (Business),
Item 7 (MD&A), Item 1A (Risk Factors), and relevant financial statement
notes in the supplied filings.

Use these seven plain-text subsection labels in this order:

Business Model
Operating Infrastructure
Competitive Advantages
Competitors
Key Risks
Developments by Fiscal Year
Stock Buybacks by Fiscal Year

Put each label on its own line, followed by a blank line.
Use the latest supplied filing for the first five subsections.
For the last two, cover only fiscal years listed in
metrics_by_fiscal_year_end.

Business Model
Write two short paragraphs, up to 160 words total. Explain what the
company sells, who pays, and how it earns revenue. Describe the main
business segments and what drives each one. Include reported revenue
mix when it helps explain the business. Cite the relevant filing sections.

Operating Infrastructure
Using the latest supplied filing, describe the physical and technology
infrastructure that supports the company’s operations. Where relevant,
cover facilities, distribution networks, data centers, software
platforms, and reliance on leased assets or third-party providers.

Explain which business segments this infrastructure supports. Mention
disclosed capacity, expansion plans, or infrastructure spending when
material. Distinguish existing facilities from planned investments.
Cite the relevant filing sections. Keep this subsection under 120 words.

Competitive Advantages
Give up to three bullets. For each advantage, explain how it helps the
company win or retain customers and cite the supporting filing section.
Attribute management claims and label your own inferences. If evidence
is limited, say so.

Competitors
Identify up to five named competitors and explain where they compete
with the company, if disclosed. If the filing describes only categories
of competitors or substitutes, summarize those categories. Cite the
relevant filing section.

Key Risks
Use Item 1A to identify up to three risks particularly relevant to the
company. Explain how each could affect the business and cite the filing.
Distinguish possible future effects from events already disclosed.

Developments by Fiscal Year
Cover the fiscal years listed in metrics_by_fiscal_year_end, oldest
first. Write two to three bullets per year, up to 50 words each.
Use fewer bullets when the filing discloses fewer material developments.

Prioritize product launches, strategic initiatives, partnerships,
market expansion, acquisitions, divestitures, and terminated deals.
State what happened, whether it was announced or completed, and why it
mattered. Connect it to financial results when the filing supports the
link. Distinguish management's explanation from your inference. Use the
supplied operating-margin changes verbatim when quantifying them, and
attribute a specific expense only to the portion the evidence supports.
Cite the filing year and section for each bullet.

Stock Buybacks by Fiscal Year
After the development bullets, add one short buyback line per supplied
year with disclosed repurchases. Report full-year shares delivered and
cash paid, where available. Distinguish completed repurchases from
authorizations. Include a reported average price only when it matches
the shares and period described. For tranche or shorter-period prices,
label the tranche or dates and pair the price with its share count.
Omit the price if no matching average is reported. Cite the filing
year and section for each buyback line.

Earlier years may appear as context within a supplied year's bullet.
"""


def _serialize_cache_value(value):
    if isinstance(value, bytes):
        return {"pdf_sha256": hashlib.sha256(value).hexdigest()}
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Unsupported cache value: {type(value).__name__}")


def cache_report(prompt_name):
    def decorate(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            arguments = inspect.signature(function).bind(*args, **kwargs)
            arguments.apply_defaults()

            # The client contains credentials and is excluded from the cache.
            inputs = {
                key: value
                for key, value in arguments.arguments.items()
                if key != "client"
            }

            cache_input = {
                "function": function.__name__,
                "prompt": function.__globals__[prompt_name],
                "inputs": inputs,
            }
            serialized = json.dumps(
                cache_input,
                sort_keys=True,
                default=_serialize_cache_value,
            )
            cache_key = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

            cache_dir = Path(__file__).resolve().parents[3] / ".cache" / "reports"
            cache_path = cache_dir / f"{cache_key}.json"

            if cache_path.exists():
                print(f"Report cache hit: {function.__name__}")
                return json.loads(cache_path.read_text(encoding="utf-8"))

            result = function(*args, **kwargs)

            cache_dir.mkdir(parents=True, exist_ok=True)
            temporary_path = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=cache_dir,
                    delete=False,
                ) as temporary_file:
                    temporary_path = Path(temporary_file.name)
                    json.dump(result, temporary_file)

                os.replace(temporary_path, cache_path)
            finally:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)

            print(f"Report saved: {function.__name__}")
            return result

        return wrapper

    return decorate


@cache_report("FINANCIAL_OVERVIEW_PROMPT")
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

@cache_report("COMPANY_DEVELOPMENT_PROMPT")
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