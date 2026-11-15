import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from fastapi.testclient import TestClient

from backend.main import create_app


class BookingTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.db = Path(temporary.name) / "demo.sqlite3"
        self.client = self.enterContext(TestClient(create_app(self.db)))
        self.vessel = {"vessel": "Horizon Test", "length": 110, "beam": 19, "draft": 5}

    def search(self, **overrides):
        criteria = {"port": "Marseille", "length": 110, "beam": 19, "draft": 5}
        result = self.client.get("/api/search", params={**criteria, **overrides})
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def request(self, slot_id=1, **overrides):
        return self.client.post("/api/bookings", json={**self.vessel, "slot_id": slot_id, **overrides})

    def decide(self, booking, new_status, yard=1):
        return self.client.patch(f"/api/yards/{yard}/bookings/{booking}", json={"status": new_status})

    def test_filters_and_exact_capacity(self):
        self.assertEqual([yard["id"] for yard in self.search()], [1, 2, 3])
        self.assertEqual([yard["id"] for yard in self.search(port=" toulon ")], [4])
        self.assertEqual([yard["id"] for yard in self.search(length=155, beam=26, draft=8)], [1, 3])
        for field, value in [("length", 121), ("beam", 22), ("draft", 6.1)]:
            self.assertEqual([yard["id"] for yard in self.search(**{field: value})], [1, 3])
        self.assertEqual(self.search(length=999), [])

    def test_invalid_inputs_and_unknown_slot(self):
        for key, value in [("length", 0), ("beam", -2), ("draft", "nan"), ("vessel", "   "), ("length", 156)]:
            with self.subTest(key=key, value=value):
                self.assertEqual(self.request(**{key: value}).status_code, 422)
        self.assertEqual(self.request(999).status_code, 404)
        self.assertEqual(self.client.get("/api/search?port=Marseille&length=nan&beam=19&draft=5").status_code, 422)
        self.assertEqual(self.client.get("/api/bookings").json(), [])

    def test_confirm_and_persist(self):
        response = self.request()
        self.assertEqual(response.status_code, 201, response.text)
        booking = response.json()
        self.assertEqual(booking["status"], "pending")
        self.assertIn(1, [slot["id"] for slot in self.search()[0]["slots"]])
        self.assertEqual(self.decide(booking["id"], "accepted", yard=2).status_code, 404)
        self.assertEqual(self.decide(booking["id"], "pending").status_code, 422)
        response = self.decide(booking["id"], "accepted")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "accepted")
        self.assertNotIn(1, [slot["id"] for slot in self.search()[0]["slots"]])
        self.assertEqual(self.request().status_code, 409)
        self.assertEqual(self.decide(booking["id"], "rejected").status_code, 409)
        with TestClient(create_app(self.db)) as restarted:
            self.assertEqual(restarted.get("/api/bookings").json()[0]["status"], "accepted")
            self.assertEqual(restarted.get("/api/bookings?yard_id=2").json(), [])

    def test_reject_preserves_availability(self):
        first = self.request().json()
        response = self.decide(first["id"], "rejected")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "rejected")
        self.assertEqual(self.decide(first["id"], "accepted").status_code, 409)
        self.assertEqual(self.request().status_code, 201)

    def test_simultaneous_confirmation(self):
        booking_ids = [self.request(vessel=name).json()["id"] for name in ("Premier", "Second")]
        barrier = Barrier(2, timeout=5)

        def confirm(booking_id):
            barrier.wait()
            return self.decide(booking_id, "accepted").status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(confirm, booking_ids)), [200, 409])
        bookings = self.client.get("/api/bookings").json()
        self.assertCountEqual([booking["status"] for booking in bookings], ["accepted", "pending"])

    def test_overlapping_slots_and_adjacent_boundary(self):
        with sqlite3.connect(self.db) as db:
            db.execute("INSERT INTO slots SELECT 91, yard_id, date(start_date, '+1 day'), date(end_date, '+1 day') FROM slots WHERE id = 1")
            db.execute("INSERT INTO slots SELECT 92, yard_id, end_date, date(end_date, '+1 day') FROM slots WHERE id = 1")
            db.execute("INSERT INTO slots SELECT 93, yard_id, date(start_date, '-2 months'), date(end_date, '-2 months') FROM slots WHERE id = 1")
        first = self.request().json()
        overlapping = self.request(91).json()
        self.assertEqual(self.decide(first["id"], "accepted").status_code, 200)
        self.assertEqual(self.decide(overlapping["id"], "accepted").status_code, 409)
        self.assertEqual(self.decide(overlapping["id"], "rejected").status_code, 200)
        self.assertEqual(self.request(93).status_code, 409)
        self.assertEqual(self.request(92).status_code, 201)

    def test_openapi_documents_api(self):
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue({"/api/search", "/api/bookings", "/api/yards/{yard_id}/bookings/{booking_id}"} <= response.json()["paths"].keys())


if __name__ == "__main__":
    unittest.main()
