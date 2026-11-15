import os
from tempfile import gettempdir

if os.getenv("VERCEL") == "1":
    os.environ.setdefault(
        "DOCKSLOT_DB",
        os.path.join(gettempdir(), "dockslot.sqlite3"),
    )

from backend.main import app
