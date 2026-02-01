from sqlmodel import SQLModel, Field, create_engine, Session, select, delete
from datetime import datetime
from typing import Optional, List

DATABASE_URL = "sqlite:///docspace.db"
engine = create_engine(DATABASE_URL, echo=False)


# documents table
class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    file_path: str
    department: str
    role: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


# create one document row
def add_document(filename: str, department: str, role: str) -> Document:
    doc = Document(filename=filename, department=department, role=role)
    with Session(engine) as session:
        session.add(doc)
        session.commit()
        session.refresh(doc)
    return doc


# list all document rows
def list_documents() -> List[Document]:
    with Session(engine) as session:
        docs = session.exec(select(Document).order_by(Document.id)).all()
    return docs

# get one document by id
def get_document_by_id(doc_id: int) -> Optional[Document]:
    with Session(engine) as session:
        doc = session.get(Document, doc_id)
    return doc


# delete one document by id (returns True if deleted, False if not found)
def delete_document_by_id(doc_id: int) -> bool:
    with Session(engine) as session:
        doc = session.get(Document, doc_id)
        if doc is None:
            return False
        session.delete(doc)
        session.commit()
    return True

def add_uploaded_document(filename: str, file_path: str, department: str, role: str) -> Document:
    doc = Document(filename=filename, file_path=file_path, department=department, role=role)
    with Session(engine) as session:
        session.add(doc)
        session.commit()
        session.refresh(doc)
    return doc
