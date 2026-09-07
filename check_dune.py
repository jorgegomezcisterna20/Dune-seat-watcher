"""
Monitor de fechas disponibles para "Dune: Part Three" en AMC Lincoln Square 13,
mas busqueda automatica de vuelos SCL-NYC para esas fechas.

Que hace, cada 15 minutos:
1. Revisa la pagina publica de horarios del teatro en Atom Tickets.
2. Busca todas las fechas que aparecen para la funcion de Dune: Part Three.
3. Si aparece una fecha CONFIRMADA posterior al 13 de enero de 2027:
   a) Calcula la ventana de vuelo: ida un dia antes, vuelta 1 o 2 dias
      despues (el que salga mas barato).
   b) Busca vuelos SCL-NYC en Amadeus para esas fechas.
   c) Manda un aviso por Telegram con la fecha confirmada y el mejor vuelo.
4. Ademas, cada 4 horas (no cada 15 minutos, para no gastar de mas la cuota
   gratis de Amadeus), busca vuelos para una fecha ESTIMADA: el dia
   siguiente a la ultima fecha confirmada (hoy, 14 de enero de 2027). Si
   aparece un precio bueno, avisa de inmediato, sin esperar a que la
   funcion se confirme oficialmente.

No entra a la pagina de compra ni al mapa de butacas: solo lee la pagina
publica de horarios, que es la parte del sitio que permite ser consultada
por un programa. La busqueda de vuelos usa la API oficial de Amadeus para
desarrolladores, no scraping.
"""

import os
import re
import json
import sys
from datetime import datetime, timedelta

import requests

MOVIE_ID = "359230"
VENUE_ID = "164"
THEATER_URL = "https://www.atomtickets.com/theaters/amc-lincoln-square-13/164"
CUTOFF_DATE = datetime(2027, 1, 13)
STATE_FILE = "state.json"

FLIGHT_ORIGIN = "SCL"
FLIGHT_DESTINATION = "NYC"
FLIGHT_BUDGET_IDEAL_USD = 600
FLIGHT_BUDGET_SOFT_USD = 650
FLIGHT_CHECK_INTERVAL_HOURS = 4
AMADEUS_BASE_URL = "https://test.api.amadeus.com"


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
    default_state = {
        "max_date_seen": CUTOFF_DATE.isoformat(),
        "last_flight_check": None,
        "best_flight_price_alerted": None,
    }
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


def get_available_dates() -> list[datetime]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(user_agent="Mozilla/5.0 (compatible; DuneSeatWatcher/1.0; personal use, low frequency)")
        page.goto(THEATER_URL, wait_until="networkidle", timeout=60000)
        html = page.content()
        browser.close()

    pattern = rf"/movies/{MOVIE_ID}/showtimes\?localDate=(\d{{4}}-\d{{2}}-\d{{2}})"
    matches = re.findall(pattern, html)

    if not matches:
        print(f"[Diagnostico] Largo del HTML recibido: {len(html)} caracteres")
        print(f"[Diagnostico] Contiene 'Dune'?: {'Dune' in html}")
        print(f"[Diagnostico] Contiene el ID de pelicula {MOVIE_ID}?: {MOVIE_ID in html}")
        print(f"[Diagnostico] Contiene 'Pre-order'?: {'Pre-order' in html}")

    return [datetime.strptime(d, "%Y-%m-%d") for d in matches]


def get_amadeus_token() -> str:
    client_id = os.environ.get("AMADEUS_API_KEY")
    client_secret = os.environ.get("AMADEUS_API_SECRET")

    if not client_id or not client_secret:
        print("Faltan las variables AMADEUS_API_KEY o AMADEUS_API_SECRET.")
        return ""

    response = requests.post(
        f"{AMADEUS_BASE_URL}/v1/security/oauth2/token",
        data={"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def search_flights(token: str, departure_date: datetime, return_date: datetime, nonstop: bool) -> list:
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "originLocationCode": FLIGHT_ORIGIN,
        "destinationLocationCode": FLIGHT_DESTINATION,
        "departureDate": departure_date.strftime("%Y-%m-%d"),
        "returnDate": return_date.strftime("%Y-%m-%d"),
        "adults": 1,
        "currencyCode": "USD",
        "max": 5,
        "nonStop": "true" if nonstop else "false",
    }
    response = requests.get(f"{AMADEUS_BASE_URL}/v2/shopping/flight-offers", headers=headers, params=params, timeout=30)
    if response.status_code != 200:
        print(f"[Diagnostico vuelos] Amadeus respondio {response.status_code} para {params}")
        return []
    return response.json().get("data", [])


def describe_offer(offer: dict) -> str:
    price = offer["price"]["total"]
    currency = offer["price"]["currency"]
    segments = offer["itineraries"][0]["segments"]
    carriers = sorted({seg["carrierCode"] for it in offer["itineraries"] for seg in it["segments"]})
    stops = len(segments) - 1
    tipo = "directo" if stops == 0 else f"{stops} escala(s)"
    return f"{currency} {price} ({tipo}, aerolinea(s): {', '.join(carriers)})"


def budget_label(precio: float) -> str:
    if precio <= FLIGHT_BUDGET_IDEAL_USD:
        return "dentro de tu presupuesto ideal"
    if precio <= FLIGHT_BUDGET_SOFT_USD:
        return "un poco mas alto que tu ideal, pero podria valer la pena (revisa aerolinea y horario)"
    return f"bastante sobre tu presupuesto (tope blando: USD {FLIGHT_BUDGET_SOFT_USD})"


def find_best_flight(movie_date: datetime):
    token = get_amadeus_token()
    if not token:
        return None, "No se pudo consultar vuelos (faltan credenciales de Amadeus)."

    departure_date = movie_date - timedelta(days=1)
    return_options = [movie_date + timedelta(days=1), movie_date + timedelta(days=2)]

    best_offer = None
    best_return = None

    for return_date in return_options:
        offers = search_flights(token, departure_date, return_date, nonstop=True)
        if not offers:
            offers = search_flights(token, departure_date, return_date, nonstop=False)
        if not offers:
            continue
        cheapest = min(offers, key=lambda o: float(o["price"]["total"]))
        if best_offer is None or float(cheapest["price"]["total"]) < float(best_offer["price"]["total"]):
            best_offer = cheapest
            best_return = return_date

    if not best_offer:
        texto = f"No se encontraron vuelos SCL-NYC para el {departure_date.strftime('%d-%m-%Y')} (ida) por ahora."
        return None, texto

    detalle = describe_offer(best_offer)
    precio = float(best_offer["price"]["total"])
    etiqueta = budget_label(precio)
    texto = f"Vuelo SCL-NYC ida {departure_date.strftime('%d-%m-%Y')} / vuelta {best_return.strftime('%d-%m-%Y')}: {detalle} -- {etiqueta}."
    return precio, texto


def check_confirmed_date(state: dict) -> bool:
    """Revisa si AMC confirmo una fecha nueva. Devuelve True si mando aviso."""
    dates = get_available_dates()

    if not dates:
        print("""No se encontraron fechas para Dune: Part Three en esta revision. Puede que la estructura de la pagina haya cambiado, o que la funcion ya no aparezca listada con 'Pre-order'.""")
        return False

    current_max = max(dates)
    known_max = datetime.fromisoformat(state["max_date_seen"])

    print(f"Fecha maxima conocida hasta ahora: {known_max.strftime('%d-%m-%Y')}")
    print(f"Fecha maxima encontrada hoy:       {current_max.strftime('%d-%m-%Y')}")

    if current_max > known_max:
        _, vuelo_info = find_best_flight(current_max)
        mensaje = f"""AMC Lincoln Square 13 abrio nuevas fechas para Dune: Part Three! Ahora se puede comprar hasta el {current_max.strftime('%d-%m-%Y')}. Entra a comprar aqui: {THEATER_URL}

{vuelo_info}"""
        send_telegram(mensaje)
        state["max_date_seen"] = current_max.isoformat()
        state["best_flight_price_alerted"] = None
        print("Aviso de fecha CONFIRMADA enviado por Telegram.")
        print(vuelo_info)
        return True

    print("Sin novedades en la fecha de la funcion.")
    return False


def check_estimated_flight(state: dict) -> None:
    """Revisa vuelos para la fecha estimada (dia siguiente al ultimo confirmado)."""
    last_check_raw = state.get("last_flight_check")
    if last_check_raw:
        last_check = datetime.fromisoformat(last_check_raw)
        horas_pasadas = (datetime.utcnow() - last_check).total_seconds() / 3600
        if horas_pasadas < FLIGHT_CHECK_INTERVAL_HOURS:
            print(f"Chequeo de vuelo estimado se salta (ultimo hace {horas_pasadas:.1f}h, se revisa cada {FLIGHT_CHECK_INTERVAL_HOURS}h).")
            return

    known_max = datetime.fromisoformat(state["max_date_seen"])
    fecha_estimada = known_max + timedelta(days=1)

    print(f"Revisando vuelos para fecha ESTIMADA: {fecha_estimada.strftime('%d-%m-%Y')}")
    precio, vuelo_info = find_best_flight(fecha_estimada)
    state["last_flight_check"] = datetime.utcnow().isoformat()

    if precio is None:
        print(vuelo_info)
        return

    mejor_previo = state.get("best_flight_price_alerted")
    ya_avisado_mejor = mejor_previo is not None and precio >= mejor_previo

    if precio <= FLIGHT_BUDGET_SOFT_USD and not ya_avisado_mejor:
        mensaje = f"""Vuelo estimado para tu viaje a ver Dune: Part Three (fecha de funcion aun no confirmada, se estima {fecha_estimada.strftime('%d-%m-%Y')} o cercana):

{vuelo_info}"""
        send_telegram(mensaje)
        state["best_flight_price_alerted"] = precio
        print("Aviso de vuelo ESTIMADO enviado por Telegram.")
    else:
        print(vuelo_info)


def main() -> None:
    state = load_state()
    hubo_fecha_confirmada = check_confirmed_date(state)
    if not hubo_fecha_confirmada:
        check_estimated_flight(state)
    save_state(state)


if __name__ == "__main__":
    main()
