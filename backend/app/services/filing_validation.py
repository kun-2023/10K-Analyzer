from datetime import date
from io import BytesIO
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .filing_extraction import FilingExtraction

def validate_pdf_uploads(uploads: list[tuple[str, bytes]])->None:
    if not 1<=len(uploads)<=3:
        raise ValueError("Upload one to three 10k PDFs")

    for filename, pdf_bytes in uploads:
        if not filename.lower().endswith(".pdf"):
            raise ValueError(f"{filename}: only PDF files are accepted.")

        if not pdf_bytes.startswith(b"%PDF-")        :
            raise ValueError(f"{filename}: missing a valid PDF header.")

        try:
            reader=PdfReader(BytesIO(pdf_bytes))
            page_count=len(reader.pages)
        except PdfReadError as exc:
            raise ValueError(f"{filename}: couldn't read PDF.") from exc

        if page_count==0:
            raise ValueError(f"{filename}: the PDF has no pages")

def validate_extracted_filings(filings: list[FilingExtraction])->None:
    company_names=set()
    fiscal_year_ends=set()

    for filing in filings:
        company_name=" ".join(filing.company_name.casefold().split())
        if not company_name:
            raise ValueError("A filing is missing its company name.")
        company_names.add(company_name)

        try:
            period_end=date.fromisoformat(filing.fiscal_year_end)
        except ValueError as exc:
            raise ValueError(
                f"Invalid fiscal year-end: {filing.fiscal_year_end}"
            ) from exc

        if period_end in fiscal_year_ends:
            raise ValueError(f"Duplicated fiscal year-end: {period_end}.")
        fiscal_year_ends.add(period_end)
    if len(company_names)>1:
        raise ValueError("All filings must be for the same company.")


