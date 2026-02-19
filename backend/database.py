from sqlmodel import SQLModel, Field, create_engine, Session, select
from datetime import datetime
from typing import Optional, List
from passlib.context import CryptContext

DATABASE_URL = "sqlite:///docspace.db"
engine = create_engine(DATABASE_URL, echo=False)


pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    if len(password) < 6:
        raise ValueError("Password too short (min 6 characters)")
    if len(password) > 256:
        raise ValueError("Password too long (max 256 characters)")
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    file_path: str
    department: str
    role: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    full_name: str
    email: str = Field(index=True, unique=True)  # company email
    hashed_password: str
    department: str
    role: str = Field(default="employee")  # auto-set for now
    created_at: datetime = Field(default_factory=datetime.utcnow)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def add_document(filename: str, department: str, role: str) -> Document:
    doc = Document(filename=filename, department=department, role=role, file_path="")
    with Session(engine) as session:
        session.add(doc)
        session.commit()
        session.refresh(doc)
    return doc


def add_uploaded_document(filename: str, file_path: str, department: str, role: str) -> Document:
    doc = Document(filename=filename, file_path=file_path, department=department, role=role)
    with Session(engine) as session:
        session.add(doc)
        session.commit()
        session.refresh(doc)
    return doc


def list_documents() -> List[Document]:
    with Session(engine) as session:
        docs = session.exec(select(Document).order_by(Document.id)).all()
    return docs


def get_document_by_id(doc_id: int) -> Optional[Document]:
    with Session(engine) as session:
        doc = session.get(Document, doc_id)
    return doc


def delete_document_by_id(doc_id: int) -> bool:
    with Session(engine) as session:
        doc = session.get(Document, doc_id)
        if doc is None:
            return False
        session.delete(doc)
        session.commit()
    return True


def create_user(session: Session, full_name: str, email: str, password: str, department: str) -> User:
    hashed = hash_password(password)
    user = User(
        full_name=full_name,
        email=email,
        hashed_password=hashed,
        department=department,
        role="employee",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_user_by_email(session: Session, email: str) -> Optional[User]:
    statement = select(User).where(User.email == email)
    results = session.exec(statement)
    return results.first()