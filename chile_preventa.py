"""
Monitor de preventa de Dune: Parte Tres en Cinemark Chile y Cinepolis Chile.

Que hace:
1. Revisa la portada de www.cinemark.cl buscando un link a una pelicula
   cuyo nombre/slug contenga "dune".
2. Revisa la portada de cinepolischile.cl buscando la palabra "DUNE" en el
   listado de peliculas (incluye preventas y estrenos).
3. Si encuentra a Dune en cualquiera de los dos donde antes no estaba,
   manda un aviso por Telegram de inmediato.
4. Guarda en un archivo de estado (chile_state.json) cual de los dos ya
   avisamos, para no repetir el mismo aviso.

Ambas paginas se leen tal cual estan publicadas (no requieren JavaScript
para mostrar el listado), asi que no hace falta un navegador simulado.
"""

import os
import re
import json
import sys

import requests

CINEMARK_URL = "https://www.cinemark.cl"
CINEPOLIS_URL = "https://cinepolischile.cl"
STATE_FILE = "chile_state.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; DunePreventaWatcher/1.0; personal use, low frequency)"
}


def send_telegram(message: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Faltan las variables TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID.")
        sys.exit(1)

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    response = requests.post(url, data={"chat_id": chat_id, "text": message}, timeout=30)
    response.raise_for_status()


def load_state() -> dict:
    default_state = {"cinemark_avisado": False, "cinepolis_avisado": False}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            default_state.update(data)
        except (json.JSONDecodeError, ValueError):
            pass
    return default_state


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)


def check_cinemark() -> bool:
    response = requests.get(CINEMARK_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    html = response.text
    return bool(re.search(r"/pelicula/[a-z0-9\-]*dune[a-z0-9\-]*", html, re.IGNORECASE))


def check_cinepolis() -> bool:
    response = requests.get(CINEPOLIS_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    html = response.text
    return "dune" in html.lower()


def main() -> None:
    state = load_state()

    encontrado_cinemark = check_cinemark()
    encontrado_cinepolis = check_cinepolis()

    print(f"Cinemark: {'ENCONTRADO' if encontrado_cinemark else 'todavia no aparece'}")
    print(f"Cinepolis: {'ENCONTRADO' if encontrado_cinepolis else 'todavia no aparece'}")

    if encontrado_cinemark and not state["cinemark_avisado"]:
        send_telegram(f"Dune: Parte Tres ya aparece en Cinemark Chile! Entra a comprar: {CINEMARK_URL}")
        state["cinemark_avisado"] = True
        print("Aviso de Cinemark enviado por Telegram.")

    if encontrado_cinepolis and not state["cinepolis_avisado"]:
        send_telegram(f"Dune: Parte Tres ya aparece en Cinepolis Chile! Entra a comprar: {CINEPOLIS_URL}")
        state["cinepolis_avisado"] = True
        print("Aviso de Cinepolis enviado por Telegram.")

    save_state(state)


if __name__ == "__main__":
    main()
