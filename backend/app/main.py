from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import Base, engine

# ==========================
# Import Models
# ==========================
from app.models.user import User
from app.models.chat import Chat
from app.models.message import Message
from app.models.upload_session import UploadSession
from app.models.report import Report
from app.models.medical_image import MedicalImage
from app.models.summary import Summary
from app.models.chat_history import ChatHistory
from app.models.quick_response import QuickResponse

# ==========================
# Import Routes
# ==========================
from app.api.routes.auth import router as auth_router
from app.api.routes.upload import router as upload_router
from app.api.routes.profile import router as profile_router
from app.api.routes.analysis import router as analysis_router
from app.api.routes.chat import router as chat_router

app = FastAPI(
    title="Oncology AI API",
    description="AI-powered Clinical Decision Support System",
    version="1.0.0",
)

# ==========================
# Create Database Tables
# ==========================
Base.metadata.create_all(bind=engine)

# ==========================
# CORS Configuration
# ==========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================
# Register Routes
# ==========================
app.include_router(auth_router)
app.include_router(upload_router)
app.include_router(profile_router)
app.include_router(analysis_router)
app.include_router(chat_router)

# ==========================
# Root Endpoint
# ==========================
@app.get("/")
def root():
    return {
        "status": "Running",
        "application": "Oncology AI",
        "version": "1.0.0",
        "message": "Backend is running successfully."
    }


# ==========================
# Health Check
# ==========================
@app.get("/health")
def health():
    return {
        "status": "healthy"
    }
