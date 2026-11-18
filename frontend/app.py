import os
from time import perf_counter
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv(".env")

API_URL=os.getenv("ANALYZER_API_URL", "http://127.0.0.1:8000").rstrip("/")
REPO_URL=os.getenv("ANALYZER_REPO_URL","")

st.set_page_config(page_title="10K Analyzer", layout="wide")

if REPO_URL:
    st.sidebar.link_button("View GitHub repo", REPO_URL)

st.title("10-K Analyzer")    
st.write("""
10-K analyzer is designed to generate a financial report based on
key informations from one company's 10K files uploaded. The report 
includes Company's business model, customer, competitors, competitve 
advantages, risks and key metrics and KPIs.
10-K analyzer accepts up to three 10K files of the same company.
It will give user a deep insights of the company's financials instantneously. 
It takes around 50s to generate the report.

""")
uploaded_files=st.file_uploader(
    "Upload annual 10-K PDFs",
    type=["pdf"],
    accept_multiple_files=True,
    help="Upload 1-3 filings for the same company. Three consecutive years are recommended."
)

valid_count=1<=len(uploaded_files)<=3
if len(uploaded_files)>3:
    st.warning("Upload at most three PDFs.")

if st.button("Generate report", type="primary", disabled=not valid_count):
    files=[
        ("files", (upload.name, upload.getvalue(), "application/pdf"))
        for upload in uploaded_files
    ]

    started_at=perf_counter()

    try:
        with st.spinner("Generating report...", show_time=True):
            response=requests.post(
                f"{API_URL}/analysis",
                files=files,
                timeout=(5,300)
            )
            response.raise_for_status()
            analysis=response.json()
    except requests.HTTPError as exc:
        st.error(f"Analysis failed (HTTP {exc.response.status_code}).")
    except requests.RequestException:
        st.error("Could not complete the request. Check that FastAPI is running.")
    else:
        st.session_state["analysis"] = analysis
        st.session_state["report_elapsed"] = perf_counter() - started_at
        st.session_state.pop("analysis_pdf", None)

analysis=st.session_state.get("analysis")
if analysis is not None:
    st.header(analysis["company_name"])
    st.caption(
        f"Report generated in {st.session_state["report_elapsed"]:.1f} seconds."
    )

    st.subheader("Financial Overview")
    st.markdown(analysis["financial_overview"])

    #st.subheader("Company Development")
    st.markdown(analysis["company_development"])

    if "analysis_pdf" not in st.session_state:
        with st.spinner("Preparing PDF…"):
            try:
                response = requests.post(
                    f"{API_URL}/analysis/pdf",
                    json=analysis,
                    timeout=(5, 30),
                )
                response.raise_for_status()
            except requests.RequestException:
                st.warning("The report is ready, but PDF export failed.")
                st.button("Retry PDF export")
            else:
                st.session_state["analysis_pdf"] = response.content

    if "analysis_pdf" in st.session_state:
        st.download_button(
            "Download PDF",
            data=st.session_state["analysis_pdf"],
            file_name="10k_report.pdf",
            mime="application/pdf",
            on_click="ignore",
        )