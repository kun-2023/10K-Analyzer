from typing import Annotated
from fastapi import APIRouter, File, HTTPException, UploadFile, Response
from openai import APIError, OpenAI
from ..services.analysis_service import analyze_filings
import logging
import os
from pydantic import BaseModel
from ..services.pdf_export import export_analysis_pdf

router=APIRouter(prefix="/analysis", tags=["analysis"])

@router.post("")
def analyze_uploads(files: Annotated[list[UploadFile], File()])->dict:
    if not 1<=len(files)<=3:
        raise HTTPException(
            status_code=422,
            detail="Upload one to three SEC Form 10-K PDFs."
        )
    uploads=[(upload.filename or "unnamed", upload.file.read()) for upload in files]

    try:
        with OpenAI(api_key=os.environ["OPENAI_API_KEY"].strip()) as client:
            return analyze_filings(uploads, client=client)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except APIError as exc:
        logging.getLogger("uvicorn.error").error(
            "OpenAI request failed: type=%s status=%s code=%s",
            type(exc).__name__,
            getattr(exc, "status_code", None),
            getattr(exc, "code", None),
        )
        logging.getLogger("uvicorn.error").error(
            "Underlying error type: %s", type(exc.__cause__).__name__
        )
        raise HTTPException(
            status_code=502,
            detail="The report provider couldn't complete the request. Try again."
        ) from exc

class PDFExportRequest(BaseModel):
    company_name: str
    financial_overview: str
    company_development: str


@router.post("/pdf")
def download_analysis_pdf(analysis: PDFExportRequest) -> Response:
    pdf_bytes = export_analysis_pdf(analysis.model_dump())
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="10k_report.pdf"'},
    )    