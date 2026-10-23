
from fastapi import FastAPI

app = FastAPI(
    title="DevTrack API",
    description="A backend API for tracking software projects, tasks, and deployments.",
    version="0.1.0",
)


@app.get("/")
def home():
    return {
        "message": "Welcome to DevTrack API!",
        "status": "running",
        "version": "0.1.0",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
    }
