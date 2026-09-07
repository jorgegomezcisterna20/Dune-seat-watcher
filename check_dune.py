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
