from .routes.analysis import router as analysis_router
from fastapi import FastAPI

app=FastAPI()
app.include_router(analysis_router)