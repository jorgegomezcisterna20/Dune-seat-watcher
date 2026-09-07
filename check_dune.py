"""
Monitor de fechas disponibles para "Dune: Part Three" en AMC Lincoln Square 13.

Que hace:
1. Revisa la pagina publica de horarios del teatro en Atom Tickets.
2. Busca todas las fechas que aparecen para la funcion de Dune: Part Three.
3. Si aparece una fecha posterior al 13 de enero de 2027 (que es el limite
   actual de venta), manda un aviso por Telegram.
4. Guarda la ultima fecha maxima vista en un archivo de estado (state.json)
   para no avisar dos veces de lo mismo.

No entra a la pagina de compra ni al mapa de butacas: solo lee la pagina
publica de horarios, que es la parte del sitio que permite ser consultada
por un programa.
"""

import os
import re
import json
import sys
from datetime import datetime

import requests

# --- Configuracion ---
MOVIE_ID = "359230"   # Identificador de "Dune: Part Three" en Atom Tickets
VENUE_ID = "164"      # Identificador de AMC Lincoln Square 13 en Atom Tickets
THEATER_URL = "https://www.atomtickets.com/theaters/amc-lincoln-square-13/164"

# Ultima fecha que hoy (6 de septiembre 2026) se puede comprar.
# Si el programa encuentra una fecha MAS ALLA de esta, te avisa.
CUTOFF_DATE = datetime(2027, 1, 13)

STATE_FILE = "state.json"


def send_telegram(message: str) -> None:
    """Envia un mensaje al chat de Telegram configurado."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Faltan las variables TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID.")
        sys.exit(1)

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    response = requests.post(
        url,
        data={"chat_id": chat_id, "text": message},
        timeout=30,
    )
    response.raise_for_status()


def load_known_max_date() -> datetime:
    """Lee la ultima fecha maxima que se conocia de una ejecucion anterior."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return datetime.fromisoformat(data["max_date_seen"])
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
    return CUTOFF_DATE


def save_known_max_date(max_date: datetime) -> None:
    """Guarda la nueva fecha maxima vista para la proxima ejecucion."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"max_date_seen": max_date.isoformat()}, f)


def get_available_dates() -> list[datetime]:
    """
    Descarga la pagina del teatro y extrae todas las fechas disponibles
    para la funcion de Dune: Part Three, buscando enlaces con este patron:

        /movies/359230/showtimes?localDate=2027-01-13T...&venueId=164

    La pagina arma su contenido con JavaScript, asi que en vez de pedirla
    con 'requests' (que solo trae el HTML inicial vacio), usamos Playwright
    para abrirla en un navegador real (invisible) y esperar a que cargue
    antes de leer el contenido.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(
            user_agent="Mozilla/5.0 (compatible; DuneSeatWatcher/1.0; "
            "personal use, low frequency)"
        )
        page.goto(THEATER_URL, wait_until="networkidle", timeout=60000)
        html = page.content()
        browser.close()

    pattern = (
        rf"/movies/{MOVIE_ID}/showtimes\?localDate="
        rf"(\d{{4}}-\d{{2}}-\d{{2}})T[^&\"]*&venueId={VENUE_ID}"
    )
    matches = re.findall(pattern, html)
    return [datetime.strptime(d, "%Y-%m-%d") for d in matches]


def main() -> None:
    dates = get_available_dates()

    if not dates:
        print(
            "No se encontraron fechas para Dune: Part Three en esta revision. "
            "Puede que la estructura de la pagina haya cambiado, o que la "
            "funcion ya no
