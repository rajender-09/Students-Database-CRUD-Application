import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


class StudentCrudTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.db_path = Path(self.temp_dir.name) / "students.sqlite3"
        self.client = TestClient(create_app(self.db_path))
        self.client.__enter__()
        self.student = {
            "student_id": "DUMMY-001",
            "name": "Alex Example",
            "date_of_birth": "2002-04-12",
            "email": "alex@example.test",
            "phone": None,
            "course": "Computer Science",
            "address": "Example Street",
        }

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.temp_dir.cleanup()

    def test_create_list_filter_get_update_delete(self):
        created = self.client.post("/students", json=self.student)
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["student_id"], "DUMMY-001")
        self.assertIn("created_at", created.json())

        self.assertEqual(len(self.client.get("/students").json()), 1)
        self.assertEqual(len(self.client.get("/students", params={"course": "Science"}).json()), 1)
        self.assertEqual(self.client.get("/students", params={"name": "Nobody"}).json(), [])
        self.assertEqual(self.client.get("/students/DUMMY-001").json()["email"], "alex@example.test")

        updated = {**self.student, "name": "Alex Updated", "course": "Mathematics"}
        response = self.client.put("/students/DUMMY-001", json=updated)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["name"], "Alex Updated")
        self.assertEqual(self.client.delete("/students/DUMMY-001").status_code, 204)
        self.assertEqual(self.client.get("/students/DUMMY-001").status_code, 404)

    def test_duplicate_id_and_missing_records(self):
        self.client.post("/students", json=self.student)
        self.assertEqual(self.client.post("/students", json=self.student).status_code, 409)
        self.assertEqual(self.client.get("/students/UNKNOWN").status_code, 404)
        self.assertEqual(self.client.put("/students/UNKNOWN", json=self.student).status_code, 400)
        unknown_student = {**self.student, "student_id": "UNKNOWN"}
        self.assertEqual(self.client.put("/students/UNKNOWN", json=unknown_student).status_code, 404)
        self.assertEqual(self.client.delete("/students/UNKNOWN").status_code, 404)

    def test_validation_and_url_body_mismatch(self):
        for changes in (
            {"email": None, "phone": None},
            {"email": "not-an-email"},
            {"date_of_birth": (date.today() + timedelta(days=1)).isoformat()},
            {"name": "   "},
        ):
            payload = {**self.student, **changes}
            self.assertEqual(self.client.post("/students", json=payload).status_code, 422)
        self.assertEqual(self.client.post("/students", json={**self.student, "date_of_birth": "not-a-date"}).status_code, 422)
        self.assertEqual(self.client.put("/students/DUMMY-999", json=self.student).status_code, 400)
        self.assertEqual(self.client.get("/students", params={"limit": 0}).status_code, 422)

    def test_database_persistence_across_app_instances(self):
        self.client.post("/students", json=self.student)
        second_client = TestClient(create_app(self.db_path))
        with second_client:
            response = second_client.get("/students/DUMMY-001")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Alex Example")


if __name__ == "__main__":
    unittest.main()
