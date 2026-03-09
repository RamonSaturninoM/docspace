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


class Department(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    file_path: str

    # who uploaded it
    owner_id: int = Field(index=True)

    department: str
    role: str
    pinned: bool = Field(default=False)

    # file size
    size_bytes: int = Field(default=0)

    uploaded_at: datetime = Field(default_factory=datetime.utcnow)

    # last opened timestamp (None until opened)
    last_opened_at: Optional[datetime] = Field(default=None)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    full_name: str
    email: str = Field(index=True, unique=True)
    hashed_password: str
    department: str
    role: str = Field(default="employee")
    created_at: datetime = Field(default_factory=datetime.utcnow)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def create_department(session: Session, name: str, description: str = "") -> Department:
    cleaned_name = name.strip()
    if not cleaned_name:
        raise ValueError("Department name is required")

    existing = get_department_by_name(session, cleaned_name)
    if existing:
        raise ValueError("Department already exists")

    department = Department(
        name=cleaned_name,
        description=description.strip(),
    )
    session.add(department)
    session.commit()
    session.refresh(department)
    return department


def list_departments(session: Session) -> List[Department]:
    statement = select(Department).order_by(Department.name)
    return session.exec(statement).all()


def get_department_by_name(session: Session, name: str) -> Optional[Department]:
    cleaned_name = name.strip()
    if not cleaned_name:
        return None

    statement = select(Department).where(Department.name == cleaned_name)
    return session.exec(statement).first()


def seed_departments(session: Session) -> None:
    default_departments = [
        {
            "name": "Engineering",
            "description": "Architecture, builds, development docs",
        },
        {
            "name": "Human Resources",
            "description": "Policies, onboarding, employee benefits",
        },
        {
            "name": "Finance",
            "description": "Budgets, reports, financial planning",
        },
        {
            "name": "Marketing",
            "description": "Campaigns, branding, strategies",
        },
    ]

    for dept in default_departments:
        existing = get_department_by_name(session, dept["name"])
        if not existing:
            department = Department(
                name=dept["name"],
                description=dept["description"],
            )
            session.add(department)

    session.commit()


def seed_admin_user(session: Session) -> None:
    admin_email = "admin@docspace.com"

    existing_admin = get_user_by_email(session, admin_email)
    if existing_admin:
        return

    admin_user = User(
        full_name="Docspace Admin",
        email=admin_email,
        hashed_password=hash_password("admin123"),
        department="Engineering",
        role="admin",
    )
    session.add(admin_user)
    session.commit()


def seed_defaults() -> None:
    with Session(engine) as session:
        seed_departments(session)
        seed_admin_user(session)


def add_document(filename: str, department: str, role: str, owner_id: int) -> Document:
    doc = Document(
        filename=filename,
        department=department,
        role=role,
        file_path="",
        owner_id=owner_id,
        size_bytes=0,
        last_opened_at=None,
    )
    with Session(engine) as session:
        session.add(doc)
        session.commit()
        session.refresh(doc)
    return doc


def add_uploaded_document(
    filename: str,
    file_path: str,
    department: str,
    role: str,
    owner_id: int,
    size_bytes: int,
) -> Document:
    doc = Document(
        filename=filename,
        file_path=file_path,
        department=department,
        role=role,
        owner_id=owner_id,
        pinned=False,
        size_bytes=size_bytes,
        last_opened_at=None,
    )
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


def touch_document_opened(doc_id: int) -> None:
    """Update last_opened_at to now."""
    with Session(engine) as session:
        doc = session.get(Document, doc_id)
        if doc is None:
            return
        doc.last_opened_at = datetime.utcnow()
        session.add(doc)
        session.commit()


def set_document_pinned(doc_id: int, pinned: bool) -> Optional[Document]:
    with Session(engine) as session:
        doc = session.get(Document, doc_id)
        if doc is None:
            return None
        doc.pinned = pinned
        session.add(doc)
        session.commit()
        session.refresh(doc)
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


def get_user_by_id(session: Session, user_id: int) -> Optional[User]:
    return session.get(User, user_id)