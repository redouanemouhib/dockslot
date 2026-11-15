CREATE TABLE IF NOT EXISTS yards (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, port TEXT NOT NULL,
    description TEXT NOT NULL, length REAL NOT NULL, beam REAL NOT NULL,
    draft REAL NOT NULL, type TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS slots (
    id INTEGER PRIMARY KEY, yard_id INTEGER NOT NULL REFERENCES yards(id),
    start_date TEXT NOT NULL, end_date TEXT NOT NULL,
    CHECK (start_date < end_date)
);
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY, slot_id INTEGER NOT NULL REFERENCES slots(id),
    vessel TEXT NOT NULL, length REAL NOT NULL, beam REAL NOT NULL, draft REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','accepted','rejected')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS one_accepted_per_slot
    ON bookings(slot_id) WHERE status = 'accepted';
