FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITTENBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY frontend/streamlit-requirements.txt ./streamlit-requirements.txt
RUN python -m pip install --no-cache-dir -r streamlit-requirements.txt

COPY frontend/ ./frontend/

EXPOSE 8502

CMD ["python", "-m", "streamlit", "run", "frontend/app.py", "--server.address=0.0.0.0", "--server.port=8502", "--server.headless=true"]
