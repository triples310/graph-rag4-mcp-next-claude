import os
import uuid
import json
import re
import hashlib
import secrets
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from build_graph import build_graph_for_user
from chatbot import get_chatbot_response

# ========================= APP SETUP =========================
app = FastAPI(title="PDF Knowledge Graph Chatbot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# ========================= FILE-BASED USER STORE =========================
USERS_FILE = Path("users.json")
SESSIONS_FILE = Path("sessions.json")
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


def load_users() -> dict:
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text())
    return {}


def save_users(users: dict):
    USERS_FILE.write_text(json.dumps(users, indent=2))


def load_sessions() -> dict:
    if SESSIONS_FILE.exists():
        data = json.loads(SESSIONS_FILE.read_text())
        # Expire old sessions
        now = datetime.utcnow().isoformat()
        active = {k: v for k, v in data.items() if v["expires"] > now}
        if len(active) != len(data):
            SESSIONS_FILE.write_text(json.dumps(active, indent=2))
        return active
    return {}


def save_sessions(sessions: dict):
    SESSIONS_FILE.write_text(json.dumps(sessions, indent=2))


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# ========================= AUTH HELPERS =========================

def create_token(username: str) -> str:
    token = secrets.token_urlsafe(32)
    sessions = load_sessions()
    sessions[token] = {
        "username": username,
        "expires": (datetime.utcnow() + timedelta(hours=24)).isoformat()
    }
    save_sessions(sessions)
    return token


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    token = credentials.credentials
    sessions = load_sessions()
    session = sessions.get(token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please log in again."
        )
    return session["username"]


# ========================= SCHEMAS =========================

class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class ChatRequest(BaseModel):
    question: str


def format_db_name(username: str) -> str:
    # Remove invalid characters (keep only letters and numbers)
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", username)
    # Return "user" + entirely lowercase username
    return f"user{cleaned.lower()}"


# ========================= AUTH ENDPOINTS =========================

@app.post("/register", summary="Register a new user")
def register(req: RegisterRequest):
    # Force username to lowercase right away
    username = req.username.strip().lower()
    
    if len(username.strip()) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters.")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    users = load_users()
    if username in users:
        raise HTTPException(status_code=409, detail="Username already exists.")

    users[username] = {
        "password_hash": hash_password(req.password),
        "created_at": datetime.utcnow().isoformat(),
        "has_graph": False,
        "pdf_name": None,
        "neo4j_database": format_db_name(username),
    }
    save_users(users)
    return {"message": f"User '{username}' registered successfully."}


@app.post("/login", summary="Login and receive an auth token")
def login(req: LoginRequest):
    # Force username to lowercase to match registration
    username = req.username.strip().lower()
    
    users = load_users()
    user = users.get(username)
    if not user or user["password_hash"] != hash_password(req.password):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    token = create_token(username)
    return {
        "token": token,
        "username": username,
        "has_graph": user.get("has_graph", False),
        "pdf_name": user.get("pdf_name"),
        "message": "Login successful. Token valid for 24 hours."
    }


@app.post("/logout", summary="Invalidate the current session token")
def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    sessions = load_sessions()
    if token in sessions:
        del sessions[token]
        save_sessions(sessions)
    return {"message": "Logged out successfully."}


# ========================= PDF UPLOAD ENDPOINT =========================

@app.post("/upload-pdf", summary="Upload a PDF to build/rebuild the knowledge graph")
async def upload_pdf(
    file: UploadFile = File(...),
    username: str = Depends(get_current_user)
):
    # Validate file type
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    # Validate file size (max 20MB)
    MAX_SIZE = 20 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="PDF too large. Max size is 20MB.")

    # Save PDF to uploads folder (per-user filename to avoid collisions)
    safe_username = username.lower().replace(" ", "_")
    pdf_path = UPLOAD_DIR / f"{safe_username}.pdf"
    pdf_path.write_bytes(content)

    users = load_users()
    user_data = users[username]
    db_name = user_data["neo4j_database"]

    # Build the knowledge graph
    try:
        result = build_graph_for_user(str(pdf_path), db_name)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to build knowledge graph: {str(e)}"
        )

    # Update user record
    users[username]["has_graph"] = True
    users[username]["pdf_name"] = file.filename
    users[username]["last_upload"] = datetime.utcnow().isoformat()
    save_users(users)

    return {
        "message": "PDF uploaded and knowledge graph built successfully.",
        "pdf_name": file.filename,
        "neo4j_database": db_name,
        "nodes_created": result.get("nodes_created", "unknown"),
    }


# ========================= STATUS ENDPOINT =========================

@app.get("/status", summary="Check your graph status")
def get_status(username: str = Depends(get_current_user)):
    users = load_users()
    user = users.get(username, {})
    return {
        "username": username,
        "has_graph": user.get("has_graph", False),
        "pdf_name": user.get("pdf_name"),
        "last_upload": user.get("last_upload"),
        "neo4j_database": user.get("neo4j_database"),
    }


# ========================= CHAT ENDPOINT =========================

@app.post("/chat", summary="Ask a question about your uploaded PDF")
def chat(
    req: ChatRequest,
    username: str = Depends(get_current_user)
):
    users = load_users()
    user = users.get(username, {})

    # Guard: no graph yet
    if not user.get("has_graph", False):
        return {
            "answer": (
                "You haven't uploaded a PDF yet. "
                "Please upload a PDF first using the /upload-pdf endpoint, "
                "then I can answer questions about it."
            ),
            "has_graph": False,
        }

    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    db_name = user["neo4j_database"]

    try:
        answer = get_chatbot_response(req.question, db_name)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Chatbot error: {str(e)}"
        )

    return {
        "question": req.question,
        "answer": answer,
        "has_graph": True,
    }


# ========================= HEALTH CHECK =========================

@app.get("/health", summary="Health check")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/", summary="API info")
def root():
    return {
        "name": "PDF Knowledge Graph Chatbot",
        "version": "1.0.0",
        "endpoints": {
            "POST /register": "Create account",
            "POST /login": "Get auth token",
            "POST /logout": "Invalidate token",
            "POST /upload-pdf": "Upload PDF (auth required)",
            "POST /chat": "Chat with your PDF (auth required)",
            "GET /status": "Check graph status (auth required)",
            "GET /health": "Health check",
        }
    }