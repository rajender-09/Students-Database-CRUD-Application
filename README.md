# Students Database CRUD Application

A small REST API for managing student records with FastAPI and SQLite. It uses dummy data in examples and starts with an empty database.

## Requirements

- Python 3.10 or newer
- `pip`

## Setup

```powershell
cd students-database-crud
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, run the virtual environment interpreter directly: `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`.

## Run

```powershell
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`; interactive documentation is at `http://127.0.0.1:8000/docs`. SQLite creates `students.db` beside the application package on first startup. Set `STUDENTS_DB_PATH` to use another database file.

## Endpoints

- `POST /students` creates a record (`201`); duplicate IDs return `409`.
- `GET /students` lists students. Optional `name`, `email`, and `course` parameters perform case-insensitive substring filters. `limit` (1-100) and `offset` support pagination.
- `GET /students/{student_id}` returns one record (`404` if missing).
- `PUT /students/{student_id}` replaces the editable fields; the body ID must match the URL.
- `DELETE /students/{student_id}` removes a record (`204`, or `404` if missing).

Each record needs a unique `student_id`, `name`, `date_of_birth` in `YYYY-MM-DD` format, and at least one of `email` or `phone`. Course and address are optional. Invalid payloads receive FastAPI's structured `422` validation response.

## Example

Create a dummy student:

```powershell
$student = @{
  student_id = "DUMMY-001"
  name = "Alex Example"
  date_of_birth = "2002-04-12"
  email = "alex@example.test"
  course = "Computer Science"
  address = "Example Street"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/students -ContentType 'application/json' -Body $student
```

Example response (`201 Created`):

```json
{
  "student_id": "DUMMY-001",
  "name": "Alex Example",
  "date_of_birth": "2002-04-12",
  "email": "alex@example.test",
  "phone": null,
  "course": "Computer Science",
  "address": "Example Street",
  "created_at": "2026-10-24T00:00:00Z"
}
```

List or filter:

```text
GET /students?course=Computer
```

Update and delete use the same ID:

```text
PUT /students/DUMMY-001
DELETE /students/DUMMY-001
```

## Tests

```powershell
python -m unittest discover -s tests -v
```

The tests use temporary SQLite files and dummy records; they do not change the runtime database.
