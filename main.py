import os
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlmodel import Session, select, SQLModel, create_engine, Field, Relationship
from sqlalchemy import CheckConstraint
from sqlalchemy.exc import IntegrityError
from contextlib import asynccontextmanager

load_dotenv()

postgres_url = os.getenv("postgres_url")

if postgres_url is None:
    raise ValueError("Postgres URL not found in environment variables.")

engine = create_engine(postgres_url)


class Author(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    books: list["Book"] = Relationship(back_populates="author", cascade_delete=True)


class Publisher(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    books: list["Book"] = Relationship(back_populates="publisher", cascade_delete=True)


class Member(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    contact: str
    books: list["Book"] = Relationship(back_populates="member")


class Book(SQLModel, table=True):
    __table_args__ = (CheckConstraint("year >= 0", name="check_year_positive"),)
    id: int | None = Field(default=None, primary_key=True)
    title: str
    available: bool = Field(default=True)
    year: int = Field(ge=0)
    author_id: int = Field(foreign_key="author.id", ondelete="CASCADE")
    publisher_id: int = Field(foreign_key="publisher.id", ondelete="CASCADE")
    author: Author = Relationship(back_populates="books")
    publisher: Publisher = Relationship(back_populates="books")
    member_id: int | None = Field(
        default=None, foreign_key="member.id", ondelete="SET NULL"
    )
    member: Member | None = Relationship(back_populates="books")


class BookCreate(SQLModel):
    title: str
    year: int = Field(ge=0)
    author_id: int
    publisher_id: int


class MemberCreate(SQLModel):
    name: str
    contact: str


class AuthorCreate(SQLModel):
    name: str


class PublisherCreate(SQLModel):
    name: str


class BookUpdate(SQLModel):
    title: str | None = None
    year: int | None = Field(default=None, ge=0)
    author_id: int | None = None
    publisher_id: int | None = None


class MemberUpdate(SQLModel):
    name: str | None = None
    contact: str | None = None


class BookPublic(SQLModel):
    id: int
    title: str
    available: bool
    year: int
    author_id: int
    publisher_id: int
    member_id: int | None = None


class MemberPublic(SQLModel):
    id: int
    name: str
    contact: str


class AuthorPublic(SQLModel):
    id: int
    name: str


class PublisherPublic(SQLModel):
    id: int
    name: str


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


async def get_session():
    with Session(engine) as session:
        yield session


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/library/add_book", response_model=BookPublic)
async def add_book(*, session: Session = Depends(get_session), book: BookCreate):
    try:
        book_db = Book.model_validate(book)
        session.add(book_db)
        session.commit()
        session.refresh(book_db)
        return book_db
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Invalid Author or Publisher ID")


@app.post("/library/add_member", response_model=MemberPublic)
async def add_member(*, session: Session = Depends(get_session), member: MemberCreate):
    member_db = Member.model_validate(member)
    session.add(member_db)
    session.commit()
    session.refresh(member_db)
    return member_db


@app.post("/library/add_author", response_model=AuthorPublic)
async def add_author(*, session: Session = Depends(get_session), author: AuthorCreate):
    author_db = Author.model_validate(author)
    session.add(author_db)
    session.commit()
    session.refresh(author_db)
    return author_db


@app.post("/library/add_publisher", response_model=PublisherPublic)
async def add_publisher(
    *, session: Session = Depends(get_session), publisher: PublisherCreate
):
    publisher_db = Publisher.model_validate(publisher)
    session.add(publisher_db)
    session.commit()
    session.refresh(publisher_db)
    return publisher_db


@app.post("/library/borrow/{book_id}/{member_id}")
async def borrow_book(
    *, session: Session = Depends(get_session), book_id: int, member_id: int
):
    book_db = session.get(Book, book_id)
    if book_db is None:
        raise HTTPException(status_code=404, detail="Book Not Found")
    if not book_db.available:
        raise HTTPException(status_code=409, detail="Book already borrowed")
    member_db = session.get(Member, member_id)
    if member_db is None:
        raise HTTPException(status_code=404, detail="Member Not Found")
    book_db.available = False
    book_db.member_id = member_id
    session.add(book_db)
    session.commit()
    session.refresh(book_db)
    return {"Congratulations": "Book Borrowed"}


@app.post("/library/return/{book_id}")
async def return_book(*, session: Session = Depends(get_session), book_id: int):
    book_db = session.get(Book, book_id)
    if book_db is None:
        raise HTTPException(status_code=404, detail="Book Not Found")
    if book_db.available:
        raise HTTPException(status_code=409, detail="Book is not borrowed")
    book_db.available = True
    book_db.member_id = None
    session.add(book_db)
    session.commit()
    session.refresh(book_db)
    return {"Congratulations": "Book Returned"}


@app.get("/library/books/search/", response_model=list[BookPublic])
async def search_books(
    *,
    session: Session = Depends(get_session),
    name: str | None = None,
    author: str | None = None,
    available: bool | None = None
):
    if name is None and author is None and available is None:
        raise HTTPException(
            status_code=400, detail="At least one search parameter must be provided"
        )
    query = select(Book)
    if name:
        query = query.where(Book.title.contains(name))  # type: ignore
    if author:
        query = query.join(Author).where(Author.name.contains(author))  # type: ignore
    if available is not None:
        query = query.where(Book.available == available)  # type: ignore
    results = session.exec(query).all()
    return results


@app.get("/library/books/", response_model=list[BookPublic])
async def get_all_books(
    *,
    session: Session = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, le=100, ge=1)
):
    books = session.exec(select(Book).offset(offset).limit(limit)).all()
    return books


@app.get("/library/members/", response_model=list[MemberPublic])
async def get_all_members(
    *,
    session: Session = Depends(get_session),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=10, le=100, ge=1)
):
    members = session.exec(select(Member).offset(offset).limit(limit)).all()
    return members


@app.patch("/library/update_book/{book_id}", response_model=BookPublic)
async def update_book(
    *, session: Session = Depends(get_session), book_id: int, book_update: BookUpdate
):
    book_db = session.get(Book, book_id)
    if book_db is None:
        raise HTTPException(status_code=404, detail="Book Not Found")
    book_data = book_update.model_dump(exclude_unset=True)
    book_db.sqlmodel_update(book_data)
    try:
        session.add(book_db)
        session.commit()
        session.refresh(book_db)
        return book_db
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Invalid Author or Publisher ID")


@app.patch("/library/update_member/{member_id}", response_model=MemberPublic)
async def update_member(
    *,
    session: Session = Depends(get_session),
    member_id: int,
    member_update: MemberUpdate
):
    member_db = session.get(Member, member_id)
    if member_db is None:
        raise HTTPException(status_code=404, detail="Member Not Found")
    member_data = member_update.model_dump(exclude_unset=True)
    member_db.sqlmodel_update(member_data)
    try:
        session.add(member_db)
        session.commit()
        session.refresh(member_db)
        return member_db
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=400, detail="Invalid Member Data")


@app.delete("/library/delete_book/{book_id}")
async def delete_book(*, session: Session = Depends(get_session), book_id: int):
    book_db = session.get(Book, book_id)
    if book_db is None:
        raise HTTPException(status_code=404, detail="Book Not Found")
    session.delete(book_db)
    session.commit()
    return {"Congratulations": "Book Deleted"}


@app.get("/library/books/{book_id}", response_model=BookPublic)
async def get_book_by_id(*, session: Session = Depends(get_session), book_id: int):
    book_db = session.get(Book, book_id)
    if book_db is None:
        raise HTTPException(status_code=404, detail="Book Not Found")
    return book_db


@app.get("/library/members/{member_id}", response_model=MemberPublic)
async def get_member_by_id(*, session: Session = Depends(get_session), member_id: int):
    member_db = session.get(Member, member_id)
    if member_db is None:
        raise HTTPException(status_code=404, detail="Member Not Found")
    return member_db


@app.delete("/library/delete_member/{member_id}")
async def delete_member(*, session: Session = Depends(get_session), member_id: int):
    member_db = session.get(Member, member_id)
    if member_db is None:
        raise HTTPException(status_code=404, detail="Member Not Found")
    session.delete(member_db)
    session.commit()
    return {"Congratulations": "Member Deleted"}
