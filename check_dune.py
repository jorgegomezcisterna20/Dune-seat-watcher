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

MOVIE_ID = "359230"
VENUE_ID = "164"
THEATER_URL = "https://www.atomtickets.com/theaters/amc-lincoln-square-13/164"
CUTOFF_DATE = datetime(2027, 1, 13)
STATE_FILE = "state.json"


def send_telegram(message: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Faltan las variables TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID.")
        sys.exit(1)

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    response = requests.post(url, data={"chat_id": chat_id, "text": message}, timeout=30)
    response.raise_for_status()


def load_known_max_date() -> datetime:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return datetime.fromisoformat(data["max_date_seen"])
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
    return CUTOFF_DATE


def save_known_max_date(max_date: datetime) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"max_date_seen": max_date.isoformat()}, f)


def get_available_dates() -> list[datetime]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(user_agent="Mozilla/5.0 (compatible; DuneSeatWatcher/1.0; personal use, low frequency)")
        page.goto(THEATER_URL, wait_until="networkidle", timeout=60000)
        html = page.content()
        browser.close()

    pattern = rf"/movies/{MOVIE_ID}/showtimes\?localDate=(\d{{4}}-\d{{2}}-\d{{2}})T[^&\"]*&venueId={VENUE_ID}"
    matches = re.findall(pattern, html)
    return [datetime.strptime(d, "%Y-%m-%d") for d in matches]


def main() -> None:
    dates = get_available_dates()

    if not dates:
        print("""No se encontraron fechas para Dune: Part Three en esta revision. Puede que la estructura de la pagina haya cambiado, o que la funcion ya no aparezca listada con 'Pre-order'.""")
        return

    current_max = max(dates)
    known_max = load_known_max_date()

    print(f"Fecha maxima conocida hasta ahora: {known_max.strftime('%d-%m-%Y')}")
    print(f"Fecha maxima encontrada hoy:       {current_max.strftime('%d-%m-%Y')}")

    if current_max > known_max:
        mensaje = f"""AMC Lincoln Square 13 abrio nuevas fechas para Dune: Part Three! Ahora se puede comprar hasta el {current_max.strftime('%d-%m-%Y')}. Entra a comprar aqui: {THEATER_URL}"""
        send_telegram(mensaje)
        save_known_max_date(current_max)
        print("Aviso enviado por Telegram.")
    else:
        print("Sin novedades. No se envia aviso.")


if __name__ == "__main__":
    main()
