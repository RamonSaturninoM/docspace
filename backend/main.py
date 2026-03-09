from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse
from pathlib import Path
from pydantic import BaseModel
from sqlmodel import Session, select
from jose import jwt, JWTError
from datetime import datetime, timedelta
import mimetypes
import uuid

from database import (
    engine,
    create_db_and_tables,
    seed_defaults,
    add_uploaded_document,
    list_documents,
    get_document_by_id,
    delete_document_by_id,
    set_document_pinned,
    create_user,
    get_user_by_email,
    verify_password,
    get_user_by_id,
    touch_document_opened,
    create_department,
    list_departments,
    get_department_by_name,
    Department,
    User,
    Document,
)

app = FastAPI()

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

bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRES_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=401, detail="Missing authorization token")

    token = creds.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    email = payload.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    with Session(engine) as session:
        user = get_user_by_email(session, email)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user


def get_current_admin(current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    seed_defaults()


@app.get("/")
def root():
    return {"message": "Backend is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


# DEPARTMENTS
class CreateDepartmentRequest(BaseModel):
    name: str
    description: str = ""


@app.get("/departments")
def get_departments():
    with Session(engine) as session:
        departments = list_departments(session)
        return [
            {
                "id": dept.id,
                "name": dept.name,
                "description": dept.description,
                "created_at": dept.created_at,
            }
            for dept in departments
        ]


@app.post("/departments")
def add_department(
    request: CreateDepartmentRequest,
    current_user=Depends(get_current_admin),
):
    with Session(engine) as session:
        try:
            department = create_department(
                session=session,
                name=request.name,
                description=request.description,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        return {
            "id": department.id,
            "name": department.name,
            "description": department.description,
            "created_at": department.created_at,
        }


@app.delete("/departments/{dept_id}")
def delete_department(
    dept_id: int,
    current_user=Depends(get_current_admin),
):
    with Session(engine) as session:
        department = session.get(Department, dept_id)
        if department is None:
            raise HTTPException(status_code=404, detail="Department not found")

        user_using_department = session.exec(
            select(User).where(User.department == department.name)
        ).first()
        if user_using_department:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete department because it is assigned to users",
            )

        document_using_department = session.exec(
            select(Document).where(Document.department == department.name)
        ).first()
        if document_using_department:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete department because it is used by documents",
            )

        session.delete(department)
        session.commit()

        return {"deleted": True, "id": dept_id, "name": department.name}


# DOCUMENTS
@app.get("/documents")
def get_documents(
    view: str = "all",
    dtype: str = "all",
    sort: str = "modified",
    current_user=Depends(get_current_user),
):
    docs = list_documents()

    view = (view or "all").lower()
    if view == "my":
        docs = [d for d in docs if d.owner_id == current_user.id]
    elif view == "pinned":
        docs = [d for d in docs if d.pinned is True]
    elif view == "shared":
        docs = []

    dtype = (dtype or "all").lower()

    def ext(name: str) -> str:
        name = name or ""
        if "." not in name:
            return ""
        return name.rsplit(".", 1)[-1].lower()

    if dtype != "all":
        if dtype == "pdf":
            docs = [d for d in docs if ext(d.filename) == "pdf"]
        elif dtype == "docs":
            docs = [d for d in docs if ext(d.filename) in {"doc", "docx"}]
        elif dtype == "sheets":
            docs = [d for d in docs if ext(d.filename) in {"xls", "xlsx", "csv"}]
        elif dtype == "slides":
            docs = [d for d in docs if ext(d.filename) in {"ppt", "pptx"}]

    sort = (sort or "modified").lower()
    if sort == "name":
        docs.sort(key=lambda d: (d.filename or "").lower())
    elif sort == "owner":
        docs.sort(key=lambda d: d.owner_id)
    elif sort == "opened":
        docs.sort(key=lambda d: (d.last_opened_at is None, d.last_opened_at), reverse=False)
        docs.reverse()
    else:
        docs.sort(key=lambda d: d.uploaded_at, reverse=True)

    result = []
    with Session(engine) as session:
        for d in docs:
            owner = get_user_by_id(session, d.owner_id)
            result.append(
                {
                    "id": d.id,
                    "filename": d.filename,
                    "file_path": d.file_path,
                    "owner_id": d.owner_id,
                    "owner_name": owner.full_name if owner else "Unknown",
                    "department": d.department,
                    "role": d.role,
                    "pinned": d.pinned,
                    "size_bytes": d.size_bytes,
                    "uploaded_at": d.uploaded_at,
                    "last_opened_at": d.last_opened_at,
                }
            )

    return result


@app.get("/documents/{doc_id}")
def get_document(doc_id: int, current_user=Depends(get_current_user)):
    doc = get_document_by_id(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@app.delete("/documents/{doc_id}")
def delete_document(doc_id: int, current_user=Depends(get_current_user)):
    deleted = delete_document_by_id(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": True, "id": doc_id}


@app.post("/documents/{doc_id}/pin")
def pin_document(doc_id: int, current_user=Depends(get_current_user)):
    doc = set_document_pinned(doc_id, True)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"id": doc.id, "pinned": doc.pinned}


@app.post("/documents/{doc_id}/unpin")
def unpin_document(doc_id: int, current_user=Depends(get_current_user)):
    doc = set_document_pinned(doc_id, False)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"id": doc.id, "pinned": doc.pinned}


@app.post("/documents/upload")
async def upload_document(
    current_user=Depends(get_current_user),
    file: UploadFile = File(...),
    department: str = Form(...),
    role: str = Form(...),
):
    storage_dir = (Path(__file__).parent / "storage").resolve()
    storage_dir.mkdir(exist_ok=True)

    safe_name = file.filename.replace("/", "_").replace("\\", "_")
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    save_path = (storage_dir / stored_name).resolve()

    contents = await file.read()
    with open(save_path, "wb") as f:
        f.write(contents)

    size_bytes = len(contents)

    doc = add_uploaded_document(
        filename=file.filename,
        file_path=str(save_path),
        department=department,
        role=role,
        owner_id=current_user.id,
        size_bytes=size_bytes,
    )

    return doc


@app.get("/documents/{doc_id}/file")
def get_document_file(doc_id: int, current_user=Depends(get_current_user)):
    touch_document_opened(doc_id)

    doc = get_document_by_id(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = Path(doc.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Stored file missing")

    media_type, _ = mimetypes.guess_type(doc.filename)
    if media_type is None:
        media_type = "application/octet-stream"

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{doc.filename}"'},
    )


@app.get("/documents/{doc_id}/download")
def download_document(doc_id: int, current_user=Depends(get_current_user)):
    touch_document_opened(doc_id)

    doc = get_document_by_id(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = Path(doc.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Stored file missing")

    return FileResponse(
        path=str(file_path),
        filename=doc.filename,
        media_type="application/octet-stream",
    )


# AUTH
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

        department = get_department_by_name(session, request.department)
        if not department:
            raise HTTPException(status_code=400, detail="Selected department does not exist")

        user = create_user(
            session=session,
            full_name=request.full_name,
            email=request.email,
            password=request.password,
            department=department.name,
        )

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


@app.get("/auth/me")
def me(current_user=Depends(get_current_user)):
    return {
        "id": current_user.id,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "department": current_user.department,
        "role": current_user.role,
    }