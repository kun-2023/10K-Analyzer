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
st.subheader("Read Before Proceed") 
st.write("""
10-K analyzer is designed to provide deep insights into 10K files uploaded. 
The app only accepts 10K files, and It only accepts 10K files from the same company.
At most, three 10k files will be alllowed to upload.
It's recommended to upload three consecutive years of 10K files of the same company for maximized effects.
A report and A dashboard will be generated. The report 
includes Company's business model, customer, competitors, competitve 
advantages, operating infrastructures and risks. In the next page, the dashboard including key metrics and KPIs will be produced.
10-K analyzer accepts up to three 10K files of the same company.
It takes around 80s to generate the report and the dashboard.
""")
st.write("""
However, the app doesn't give ratings on the given stock. 
Neither will it calculate intrinsic value for the stock. 
10-K analyzer only provides critical information on which users can rely while making buy or sell decisions.
""")
st.write("AI can make mistakes. It's recommended that users get familiar with the company's financials and fundamentals before using the app in case of hallucinations.")
uploaded_files=st.file_uploader(
    "Upload annual 10-K PDFs",
    type=["pdf"],
    accept_multiple_files=True,
    help="Upload 1-3 filings for the same company. Three consecutive years are recommended."
)

st.info("""
If, however, the app failed to process, that's probably because the files are too
large. You can reduce number of files uploaded. Few year would limit 
year-over-year comparisons and ROIC calculations.


""")

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