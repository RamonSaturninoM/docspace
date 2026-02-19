from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from pydantic import BaseModel
from sqlmodel import Session
from jose import jwt
from datetime import datetime, timedelta

from database import (
    engine,
    create_db_and_tables,
    add_uploaded_document,
    list_documents,
    get_document_by_id,
    delete_document_by_id,
    create_user,
    get_user_by_email,
    verify_password,
)

app = FastAPI()

# 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


JWT_SECRET = "change-me-later"
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_MINUTES = 60


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRES_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


@app.get("/")
def root():
    return {"message": "Backend is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/documents")
def get_documents():
    return list_documents()


@app.get("/documents/{doc_id}")
def get_document(doc_id: int):
    doc = get_document_by_id(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@app.delete("/documents/{doc_id}")
def delete_document(doc_id: int):
    deleted = delete_document_by_id(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": True, "id": doc_id}


@app.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    department: str = Form(...),
    role: str = Form(...),
):
    storage_dir = Path("storage")
    storage_dir.mkdir(exist_ok=True)

    safe_name = file.filename.replace("/", "_").replace("\\", "_")
    save_path = storage_dir / safe_name

    contents = await file.read()
    with open(save_path, "wb") as f:
        f.write(contents)

    doc = add_uploaded_document(
        filename=file.filename,
        file_path=str(save_path),
        department=department,
        role=role,
    )
    return doc


class SignupRequest(BaseModel):
    full_name: str
    email: str
    password: str
    department: str


class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/auth/signup")
def signup(request: SignupRequest):
    with Session(engine) as session:
        existing_user = get_user_by_email(session, request.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="User already exists")

        try:
            user = create_user(
                session=session,
                full_name=request.full_name,
                email=request.email,
                password=request.password,
                department=request.department,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        return {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "department": user.department,
            "role": user.role,
        }


@app.post("/auth/login")
def login(request: LoginRequest):
    with Session(engine) as session:
        user = get_user_by_email(session, request.email)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        if not verify_password(request.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        token = create_access_token({"sub": str(user.id), "email": user.email})

        return {
            "message": "Login successful",
            "access_token": token,
            "token_type": "bearer",
        }