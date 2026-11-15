import json
import os
import sqlite3
from contextlib import asynccontextmanager, closing
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ROOT = Path(__file__).resolve().parent
DIMS = ("length", "beam", "draft")
Metres = Annotated[float, Field(gt=0, le=1000, allow_inf_nan=False)]
QueryMetres = Annotated[float, Query(gt=0, le=1000, allow_inf_nan=False)]
BookingStatus = Literal["pending", "accepted", "rejected"]


class VesselDimensions(BaseModel):
    length: Metres
    beam: Metres
    draft: Metres


class BookingInput(VesselDimensions):
    model_config = ConfigDict(extra="forbid")
    slot_id: Annotated[int, Field(gt=0)]
    vessel: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]


class Decision(BaseModel):
    status: Literal["accepted", "rejected"]


class Slot(BaseModel):
    id: int
    start_date: date
    end_date: date


class Yard(VesselDimensions):
    id: int
    name: str
    port: str
    description: str
    type: str


class YardAvailability(Yard):
    slots: list[Slot]


class Booking(BookingInput):
    id: int
    yard_id: int
    yard_name: str
    port: str
    start_date: date
    end_date: date
    status: BookingStatus
    created_at: str


BOOKINGS = """
    SELECT b.*, s.start_date, s.end_date, y.id AS yard_id, y.name AS yard_name, y.port
    FROM bookings b JOIN slots s ON s.id = b.slot_id JOIN yards y ON y.id = s.yard_id
"""
SLOT_IS_FREE = """
    NOT EXISTS (
        SELECT 1 FROM bookings b JOIN slots occupied ON occupied.id = b.slot_id
        WHERE b.status = 'accepted' AND occupied.yard_id = s.yard_id
          AND occupied.start_date < s.end_date AND occupied.end_date > s.start_date
    )
"""


def connect(path):
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def initialize(path):
    seed = json.loads((ROOT / "seed.json").read_text(encoding="utf-8"))
    with closing(connect(path)) as db, db:
        db.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT 1 FROM yards LIMIT 1").fetchone():
            return
        db.executemany(
            """INSERT INTO yards VALUES (:id,:name,:port,:description,:length,:beam,:draft,:type)""",
            seed["yards"],
        )
        today = date.today()
        slots = [
            (slot["id"], slot["yard_id"], (today + timedelta(days=slot["offset"])).isoformat(),
             (today + timedelta(days=slot["offset"] + slot["days"])).isoformat())
            for slot in seed["slots"]
        ]
        db.executemany("INSERT INTO slots VALUES (?,?,?,?)", slots)


def slot_available(db, slot_id):
    return db.execute(
        f"SELECT 1 FROM slots s WHERE id = ? AND start_date >= ? AND {SLOT_IS_FREE}",
        (slot_id, date.today().isoformat()),
    ).fetchone() is not None


def create_app(db_path=None):
    path = db_path or os.getenv("DOCKSLOT_DB", ROOT / "dockslot.sqlite3")

    @asynccontextmanager
    async def lifespan(_app):
        initialize(path)
        yield

    app = FastAPI(
        title="DockSlot API",
        version="1.0.0",
        description="Prototype de réservation de carénage. Rôles simulés et données fictives.",
        lifespan=lifespan,
    )

    @app.get("/api/yards", response_model=list[Yard])
    def list_yards():
        with closing(connect(path)) as db:
            return [dict(row) for row in db.execute("SELECT * FROM yards ORDER BY port, name")]

    @app.get("/api/search", response_model=list[YardAvailability])
    def search(port: Annotated[str, Query(min_length=1, max_length=80)],
               length: QueryMetres, beam: QueryMetres, draft: QueryMetres):
        with closing(connect(path)) as db, db:
            db.execute("BEGIN")
            yards = db.execute(
                """SELECT * FROM yards WHERE port = ? COLLATE NOCASE
                   AND length >= ? AND beam >= ? AND draft >= ? ORDER BY id""",
                (port.strip(), length, beam, draft),
            ).fetchall()
            return [
                {**dict(yard), "slots": [dict(slot) for slot in db.execute(
                    f"""SELECT s.id, s.start_date, s.end_date FROM slots s
                        WHERE s.yard_id = ? AND s.start_date >= ? AND {SLOT_IS_FREE}
                        ORDER BY s.start_date""",
                    (yard["id"], date.today().isoformat()),
                )]}
                for yard in yards
            ]

    @app.get("/api/bookings", response_model=list[Booking])
    def list_bookings(yard_id: Annotated[int | None, Query(gt=0)] = None):
        with closing(connect(path)) as db:
            query = BOOKINGS + " WHERE (? IS NULL OR y.id = ?) ORDER BY b.id DESC"
            return [dict(row) for row in db.execute(query, (yard_id, yard_id))]

    @app.post("/api/bookings", status_code=status.HTTP_201_CREATED, response_model=Booking,
              responses={404: {"description": "Créneau inconnu"}, 409: {"description": "Créneau indisponible"}})
    def request_booking(payload: BookingInput):
        with closing(connect(path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            yard = db.execute(
                "SELECT y.* FROM yards y JOIN slots s ON s.yard_id = y.id WHERE s.id = ?",
                (payload.slot_id,),
            ).fetchone()
            if yard is None:
                raise HTTPException(404, "Créneau introuvable.")
            if any(getattr(payload, dimension) > yard[dimension] for dimension in DIMS):
                raise HTTPException(422, "Les dimensions du navire dépassent la capacité du chantier.")
            if not slot_available(db, payload.slot_id):
                raise HTTPException(409, "Ce créneau n’est plus disponible.")
            booking_id = db.execute(
                """INSERT INTO bookings(slot_id,vessel,length,beam,draft)
                   VALUES (:slot_id,:vessel,:length,:beam,:draft)""",
                payload.model_dump(),
            ).lastrowid
            return dict(db.execute(BOOKINGS + " WHERE b.id = ?", (booking_id,)).fetchone())

    @app.patch("/api/yards/{yard_id}/bookings/{booking_id}", response_model=Booking,
               responses={404: {"description": "Demande introuvable"}, 409: {"description": "Conflit de réservation"}})
    def decide(yard_id: int, booking_id: int, decision: Decision):
        with closing(connect(path)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            booking = db.execute(
                BOOKINGS + " WHERE b.id = ? AND y.id = ?", (booking_id, yard_id),
            ).fetchone()
            if booking is None:
                raise HTTPException(404, "Demande introuvable pour ce chantier.")
            if booking["status"] != "pending":
                raise HTTPException(409, "Cette demande a déjà reçu une décision.")
            if decision.status == "accepted" and not slot_available(db, booking["slot_id"]):
                raise HTTPException(409, "Ce créneau n’est plus disponible. Vous pouvez refuser la demande.")
            db.execute("UPDATE bookings SET status = ? WHERE id = ?", (decision.status, booking_id))
            return {**dict(booking), "status": decision.status}

    dist = ROOT.parent / "frontend" / "dist"
    if (dist / "index.html").is_file():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")

    return app


app = create_app()
