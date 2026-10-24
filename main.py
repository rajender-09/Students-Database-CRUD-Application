from contextlib import asynccontextmanager, closing
from datetime import date
import os
import re
import sqlite3
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


DEFAULT_DB = Path(__file__).resolve().parent.parent / "students.db"


class StudentInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    student_id: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=120)
    date_of_birth: date
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=30)
    course: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=500)

    @field_validator("student_id")
    @classmethod
    def valid_student_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("student_id cannot be blank")
        return value

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name cannot be blank")
        return value

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str | None) -> str | None:
        if value == "":
            return None
        if value is not None and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("email must be a valid email address")
        return value

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        return value or None

    @model_validator(mode="after")
    def valid_record(self):
        if self.date_of_birth >= date.today():
            raise ValueError("date_of_birth must be in the past")
        if not self.email and not self.phone:
            raise ValueError("provide at least an email address or phone number")
        return self


class Student(StudentInput):
    created_at: str


def create_app(database_path: str | Path | None = None) -> FastAPI:
    db_path = Path(database_path or os.getenv("STUDENTS_DB_PATH", DEFAULT_DB))

    def connect() -> sqlite3.Connection:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        with closing(connect()) as connection, connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS students (
                    student_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    date_of_birth TEXT NOT NULL,
                    email TEXT,
                    phone TEXT,
                    course TEXT,
                    address TEXT,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
                    CHECK (email IS NOT NULL OR phone IS NOT NULL)
                )"""
            )
        yield

    app = FastAPI(title="Students Database CRUD Application", version="1.0.0", lifespan=lifespan)

    def as_student(row: sqlite3.Row) -> Student:
        return Student(**dict(row))

    @app.post("/students", response_model=Student, status_code=status.HTTP_201_CREATED)
    def create_student(student: StudentInput):
        try:
            with closing(connect()) as connection, connection:
                cursor = connection.execute(
                    "INSERT INTO students (student_id,name,date_of_birth,email,phone,course,address) VALUES (?,?,?,?,?,?,?)",
                    (student.student_id, student.name, student.date_of_birth.isoformat(), student.email,
                     student.phone, student.course, student.address),
                )
                row = connection.execute("SELECT * FROM students WHERE student_id = ?", (student.student_id,)).fetchone()
        except sqlite3.IntegrityError as exc:
            if "students.student_id" in str(exc):
                raise HTTPException(status_code=409, detail=f"Student '{student.student_id}' already exists") from exc
            raise HTTPException(status_code=400, detail="Student data violates a database constraint") from exc
        return as_student(row)

    @app.get("/students", response_model=list[Student])
    def list_students(
        name: Annotated[str | None, Query(max_length=120)] = None,
        email: Annotated[str | None, Query(max_length=254)] = None,
        course: Annotated[str | None, Query(max_length=120)] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ):
        clauses, params = [], []
        for column, value in (("name", name), ("email", email), ("course", course)):
            if value:
                clauses.append(f"{column} LIKE ?")
                params.append(f"%{value}%")
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with closing(connect()) as connection, connection:
            rows = connection.execute(
                f"SELECT * FROM students{where} ORDER BY student_id LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [as_student(row) for row in rows]

    @app.get("/students/{student_id}", response_model=Student)
    def get_student(student_id: str):
        with closing(connect()) as connection, connection:
            row = connection.execute("SELECT * FROM students WHERE student_id = ?", (student_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Student '{student_id}' not found")
        return as_student(row)

    @app.put("/students/{student_id}", response_model=Student)
    def update_student(student_id: str, student: StudentInput):
        if student.student_id != student_id:
            raise HTTPException(status_code=400, detail="student_id in the body must match the URL")
        with closing(connect()) as connection, connection:
            cursor = connection.execute(
                "UPDATE students SET name=?,date_of_birth=?,email=?,phone=?,course=?,address=? WHERE student_id=?",
                (student.name, student.date_of_birth.isoformat(), student.email, student.phone,
                 student.course, student.address, student_id),
            )
            row = connection.execute("SELECT * FROM students WHERE student_id = ?", (student_id,)).fetchone()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Student '{student_id}' not found")
        return as_student(row)

    @app.delete("/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_student(student_id: str):
        with closing(connect()) as connection, connection:
            cursor = connection.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Student '{student_id}' not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return app


app = create_app()
