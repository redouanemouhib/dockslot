"""Run with: python tests/test_browser.py (after building frontend/dist)."""
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def wait_for_server(server, url):
    for _ in range(100):
        if server.poll() is not None:
            raise RuntimeError("Le serveur Uvicorn s’est arrêté.")
        try:
            with urlopen(url + "/api/yards", timeout=1) as response:
                if response.status == 200:
                    return
        except URLError:
            time.sleep(0.1)
    raise RuntimeError("Le serveur Uvicorn ne répond pas.")


def run():
    if not (ROOT / "frontend/dist/index.html").is_file():
        raise RuntimeError("Exécutez npm run build dans frontend avant ce test.")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "browser.sqlite3"
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app", "--port", str(port), "--log-level", "warning"],
            cwd=ROOT,
            env={**os.environ, "DOCKSLOT_DB": str(database)},
        )
        try:
            wait_for_server(server, url)
            browser_checks(url)
            with sqlite3.connect(database) as db:
                rows = db.execute("SELECT vessel, status FROM bookings ORDER BY id").fetchall()
                assert rows == [("Horizon Atlantique", "accepted"), ("Cap Boréal", "rejected")], rows
                print("SQLite : demandes et décisions enregistrées.")
        finally:
            server.terminate()
            server.wait(timeout=10)


def browser_checks(url):
    with sync_playwright() as playwright:
        chromium = os.environ.get("DOCKSLOT_CHROMIUM")
        browser = playwright.chromium.launch(executable_path=chromium)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url)
        expect(page.locator(".yard-card")).to_have_count(3)
        assert page.request.get(url + "/port.webp").ok, "Image de couverture indisponible"
        if os.environ.get("DOCKSLOT_SCREENSHOTS"):
            page.screenshot(path="/tmp/dockslot-desktop.png", full_page=True)
        page.get_by_label("Longueur").fill("0")
        page.get_by_role("button", name="Rechercher", exact=True).last.click()
        assert page.locator("#length").evaluate("(input) => !input.validity.valid")
        page.get_by_label("Longueur").fill("160")
        page.get_by_role("button", name="Rechercher", exact=True).last.click()
        expect(page.locator(".yard-card")).to_have_count(1)
        expect(page.locator(".yard-card")).to_contain_text("Digue Horizon")
        page.get_by_label("Longueur").fill("110")
        page.get_by_role("button", name="Rechercher", exact=True).last.click()
        expect(page.locator(".yard-card")).to_have_count(3)

        def submit(vessel):
            first_yard = page.locator(".yard-card").filter(has_text="Forme du Cap")
            button = first_yard.get_by_role("button").first
            label = button.get_attribute("aria-label")
            button.click()
            expect(page.get_by_role("dialog")).to_be_visible()
            page.get_by_label("Nom du navire").fill(vessel)
            page.get_by_role("button", name="Envoyer la demande").click()
            expect(page.get_by_role("row").filter(has_text=vessel)).to_contain_text("En attente")
            return label

        occupied_label = submit("Horizon Atlantique")
        page.get_by_role("navigation").get_by_role("button", name="Rechercher").click()
        submit("Cap Boréal")
        page.get_by_role("button", name="Espace chantier").click()
        page.get_by_label("Chantier naval").select_option("2")
        expect(page.get_by_text("Aucune demande pour le moment.")).to_be_visible()
        page.get_by_label("Chantier naval").select_option("1")
        first = page.get_by_role("row").filter(has_text="Horizon Atlantique")
        second = page.get_by_role("row").filter(has_text="Cap Boréal")
        first.get_by_role("button", name="Accepter").click()
        expect(first).to_contain_text("Confirmée")
        second.get_by_role("button", name="Accepter").click()
        expect(page.get_by_role("alert")).to_contain_text("Ce créneau n’est plus disponible")
        second.get_by_role("button", name="Refuser").click()
        expect(second).to_contain_text("Refusée")
        page.get_by_role("button", name="Mes réservations").click()
        expect(first).to_contain_text("Confirmée")
        expect(second).to_contain_text("Refusée")
        if os.environ.get("DOCKSLOT_SCREENSHOTS"):
            page.screenshot(path="/tmp/dockslot-bookings.png", full_page=True)
        page.get_by_role("navigation").get_by_role("button", name="Rechercher").click()
        expect(page.get_by_role("button", name=occupied_label, exact=True)).to_have_count(0)
        assert page.request.get(url + "/docs").ok
        print("Chromium : recherche, validation, demandes, confirmation, conflit, refus et suivi.")

        mobile = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        mobile.goto(url)
        expect(mobile.locator(".yard-card")).to_have_count(3)
        assert mobile.evaluate("document.documentElement.scrollWidth === innerWidth")
        if os.environ.get("DOCKSLOT_SCREENSHOTS"):
            mobile.screenshot(path="/tmp/dockslot-mobile.png", full_page=True)
        mobile.get_by_role("button", name="Mes réservations").click()
        expect(mobile.get_by_role("row").filter(has_text="Horizon Atlantique")).to_contain_text("Confirmée")
        assert mobile.evaluate("document.documentElement.scrollWidth === innerWidth")
        assert mobile.locator(".table-scroll").evaluate("(table) => table.scrollWidth > table.clientWidth")
        assert not errors, errors
        print("Chromium 390 px : recherche et suivi sans débordement de page, tableau défilable.")
        browser.close()


if __name__ == "__main__":
    run()
