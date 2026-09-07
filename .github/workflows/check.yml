"""
Monitor de fechas disponibles para "Dune: Part Three" en AMC Lincoln Square 13.

Qué hace:
1. Revisa la página pública de horarios del teatro en Atom Tickets.
2. Busca todas las fechas que aparecen para la función de Dune: Part Three.
3. Si aparece una fecha posterior al 13 de enero de 2027 (que es el límite
   actual de venta), manda un aviso por Telegram.
4. Guarda la última fecha máxima vista en un archivo de estado (state.json)
   para no avisar dos veces de lo mismo.

No entra a la página de compra ni al mapa de butacas: solo lee la página
pública de horarios, que es la parte del sitio que permite ser consultada
por un programa.
"""

import os
import re
import json
import sys
from datetime import datetime

import requests

# --- Configuración ---
MOVIE_ID = "359230"   # Identificador de "Dune: Part Three" en Atom Tickets
VENUE_ID = "164"      # Identificador de AMC Lincoln Square 13 en Atom Tickets
THEATER_URL = "https://www.atomtickets.com/theaters/amc-lincoln-square-13/164"

# Última fecha que hoy (6 de septiembre 2026) se puede comprar.
# Si el programa encuentra una fecha MÁS ALLÁ de esta, te avisa.
CUTOFF_DATE = datetime(2027, 1, 13)

STATE_FILE = "state.json"


def send_telegram(message: str) -> None:
    """Envía un mensaje al chat de Telegram configurado."""
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
    """Lee la última fecha máxima que se conocía de una ejecución anterior."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return datetime.fromisoformat(data["max_date_seen"])
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
    return CUTOFF_DATE


def save_known_max_date(max_date: datetime) -> None:
    """Guarda la nueva fecha máxima vista para la próxima ejecución."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"max_date_seen": max_date.isoformat()}, f)


def get_available_dates() -> list[datetime]:
    """
    Descarga la página del teatro y extrae todas las fechas disponibles
    para la función de Dune: Part Three, buscando enlaces con este patrón:

        /movies/359230/showtimes?localDate=2027-01-13T...&venueId=164
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; DuneSeatWatcher/1.0; "
        "personal use, low frequency)"
    }
    response = requests.get(THEATER_URL, headers=headers, timeout=30)
    response.raise_for_status()
    html = response.text

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
            "No se encontraron fechas para Dune: Part Three en esta revisión. "
            "Puede que la estructura de la página haya cambiado, o que la "
            "función ya no aparezca listada con 'Pre-order'."
        )
        return

    current_max = max(dates)
    known_max = load_known_max_date()

    print(f"Fecha máxima conocida hasta ahora: {known_max.strftime('%d-%m-%Y')}")
    print(f"Fecha máxima encontrada hoy:       {current_max.strftime('%d-%m-%Y')}")

    if current_max > known_max:
        send_telegram(
            "🎬 ¡AMC Lincoln Square 13 abrió nuevas fechas para "
            "Dune: Part Three!\n"
            f"Ahora se puede comprar hasta el {current_max.strftime('%d-%m-%Y')}.\n"
            f"Entra a comprar aquí: {THEATER_URL}"
        )
        save_known_max_date(current_max)
        print("Aviso enviado por Telegram.")
    else:
        print("Sin novedades. No se envía aviso.")


if __name__ == "__main__":
    main()
