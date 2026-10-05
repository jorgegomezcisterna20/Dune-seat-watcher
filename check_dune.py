"""
Monitor de fechas para "Dune: Part Three" en AMC Lincoln Square 13.

Que hace cada vez que corre (cada 15 minutos, en los servidores de GitHub):
1. Abre la pagina publica de horarios del teatro en Atom Tickets con un
   navegador invisible (Playwright) y lee hasta que fecha se venden
   entradas para Dune: Part Three.
2. Si aparece una fecha posterior a la ultima conocida (al principio, el
   13 de enero de 2027), te avisa por Telegram para que entres a comprar.
3. Una vez por semana te manda un mensaje corto confirmando que sigue
   funcionando. Si pasa mas de una semana sin ese mensaje, algo paso.
4. Si falla varias veces seguidas, te avisa por Telegram con el error
   (maximo una vez cada 12 horas) y te vuelve a escribir cuando se recupera.

No entra a la pagina de compra ni al mapa de butacas: solo lee la pagina
publica de horarios.
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import requests

# --- Configuracion -----------------------------------------------------------

MOVIE_ID = "359230"  # Dune: Part Three en Atom Tickets
THEATER_URL = "https://www.atomtickets.com/theaters/amc-lincoln-square-13/164"
CUTOFF_DATE = datetime(2027, 1, 13)  # ultima fecha a la venta cuando se armo el robot
STATE_FILE = "state.json"
USER_AGENT = "Mozilla/5.0 (compatible; DuneSeatWatcher/1.0; personal use, low frequency)"
RECORDATORIO_BUTACAS = "Recuerda: fila G a J, butacas 10 a 22."

FALLAS_ANTES_DE_AVISAR = 3  # 3 revisiones fallidas seguidas = unos 45 minutos
HORAS_ENTRE_AVISOS_DE_FALLA = 12
DIAS_ENTRE_MENSAJES_SEMANALES = 7

# Encuentra las fechas en los links de la pagina, que se ven asi:
#   /movies/359230/showtimes?localDate=2027-01-13T02%3A00%3A00-05%3A00&venueId=164
# Tambien acepta los mismos links escritos de forma "escapada" (\/, %2F, etc.).
PATRON_FECHA = re.compile(
    r"movies(?:/|\\/|%2F)" + MOVIE_ID
    + r"(?:/|\\/|%2F)showtimes(?:\?|%3F|\\u003F)localDate(?:=|%3D|\\u003D)"
    + r"(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)


# --- Utilidades ----------------------------------------------------------------

def ahora() -> datetime:
    return datetime.now(timezone.utc)


def ocultar_secretos(texto: str) -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or ""
    return texto.replace(token, "***") if len(token) >= 8 else texto


def primera_linea(texto: str, largo: int = 300) -> str:
    lineas = [l.strip() for l in str(texto).splitlines() if l.strip()]
    return ocultar_secretos(lineas[0] if lineas else "(sin detalle)")[:largo]


def nota_en_github(nivel: str, titulo: str, mensaje: str) -> None:
    """Deja una nota visible en la pagina de la ejecucion (pestana Actions de GitHub)."""
    def limpiar(texto: str) -> str:
        texto = ocultar_secretos(texto)
        return texto.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")

    titulo = limpiar(titulo).replace(":", "%3A").replace(",", "%2C")
    print(f"::{nivel} title={titulo}::{limpiar(mensaje)}")


def send_telegram(message: str, obligatorio: bool = True) -> bool:
    """Manda un mensaje por Telegram.

    Si el mensaje es obligatorio y no se puede mandar, la ejecucion termina con
    error (queda en rojo en GitHub) para que se reintente en la proxima revision.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        nota_en_github(
            "error",
            "Faltan los datos de Telegram",
            "No estan los secretos TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID "
            "(Settings > Secrets and variables > Actions).",
        )
        sys.exit(1)

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": message},
            timeout=30,
        )
        if response.ok:
            return True
        detalle = f"Codigo {response.status_code}: {response.text[:300]}"
    except requests.RequestException as error:
        detalle = str(error)

    nota_en_github("error" if obligatorio else "warning", "Telegram no acepto el mensaje", detalle)
    if obligatorio:
        sys.exit(1)
    return False


# --- Estado (lo que el robot recuerda entre una revision y otra) ---------------

def leer_estado() -> dict:
    estado = {
        "max_date_seen": CUTOFF_DATE.isoformat(),
        "fallas_seguidas": 0,
        "ultimo_aviso_falla": None,
        "ultimo_mensaje_semanal": None,
    }
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                guardado = json.load(f)
            if isinstance(guardado, dict):
                estado.update({k: v for k, v in guardado.items() if k in estado})
        except (OSError, ValueError):
            print("No se pudo leer el estado guardado; se parte de cero.")
    return estado


def guardar_estado(estado: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(estado, f, indent=2)


# --- Revision de la pagina ------------------------------------------------------

def extraer_fechas(html: str) -> list[datetime]:
    return sorted({datetime.strptime(d, "%Y-%m-%d") for d in PATRON_FECHA.findall(html)})


def leer_fechas_disponibles() -> list[datetime]:
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        try:
            page = browser.new_page(user_agent=USER_AGENT)
            respuesta = page.goto(THEATER_URL, wait_until="domcontentloaded", timeout=60000)
            try:
                page.wait_for_selector(
                    f'a[href*="/movies/{MOVIE_ID}/showtimes"]', state="attached", timeout=30000
                )
            except PlaywrightTimeout:
                pass  # se revisa igual lo que alcanzo a cargar
            html = page.content()
            codigo = respuesta.status if respuesta else "sin respuesta"
            titulo = page.title()
        finally:
            browser.close()

    fechas = extraer_fechas(html)
    if not fechas:
        raise RuntimeError(
            "La pagina cargo pero no aparece ninguna fecha de Dune: Part Three "
            f"(codigo {codigo}, titulo '{titulo}', {len(html)} caracteres, "
            f"menciona Dune: {'si' if 'dune' in html.lower() else 'no'}). "
            "Puede que la pagina haya cambiado o que este bloqueando al robot."
        )
    return fechas


# --- Avisos ------------------------------------------------------------------------

def avisar_si_hay_fechas_nuevas(estado: dict, fechas: list[datetime]) -> None:
    fecha_max = fechas[-1]
    fecha_conocida = max(datetime.fromisoformat(estado["max_date_seen"]), CUTOFF_DATE)

    print(f"Ultima fecha conocida:        {fecha_conocida:%d-%m-%Y}")
    print(f"Ultima fecha a la venta hoy:  {fecha_max:%d-%m-%Y}")

    if fecha_max <= fecha_conocida:
        print("Sin novedades.")
        return

    nuevas = ", ".join(f"{f:%d-%m-%Y}" for f in fechas if f > fecha_conocida)
    send_telegram(
        "🎬 ¡AMC Lincoln Square 13 abrió nuevas fechas para Dune: Part Three!\n\n"
        f"Ahora se puede comprar hasta el {fecha_max:%d-%m-%Y}.\n"
        f"Fechas nuevas: {nuevas}\n\n"
        f"Entra a comprar aquí: {THEATER_URL}\n"
        f"{RECORDATORIO_BUTACAS}"
    )
    estado["max_date_seen"] = fecha_max.isoformat()
    print("Aviso de fechas nuevas enviado por Telegram.")
    nota_en_github("notice", "Fechas nuevas", f"Ahora se vende hasta el {fecha_max:%d-%m-%Y}. Aviso enviado.")


def registrar_falla(estado: dict, error: Exception) -> None:
    detalle = primera_linea(f"{type(error).__name__}: {error}")
    estado["fallas_seguidas"] = int(estado.get("fallas_seguidas") or 0) + 1
    n = estado["fallas_seguidas"]

    print(f"No se pudo revisar la pagina (falla {n} seguida). Detalle completo:")
    print(ocultar_secretos(str(error)))
    nota_en_github("warning", "El robot no pudo revisar la pagina", detalle)

    if n < FALLAS_ANTES_DE_AVISAR:
        print(f"Todavia no se avisa por Telegram (se avisa desde la falla {FALLAS_ANTES_DE_AVISAR} seguida).")
        return

    ultimo = estado.get("ultimo_aviso_falla")
    if ultimo and ahora() - datetime.fromisoformat(ultimo) < timedelta(hours=HORAS_ENTRE_AVISOS_DE_FALLA):
        print("Ya se aviso de esta falla hace menos de 12 horas; no se repite el aviso todavia.")
        return

    send_telegram(
        "⚠️ El robot de Dune no está pudiendo revisar la página de AMC "
        f"({n} intentos seguidos fallidos).\n\n"
        f"Error: {detalle}\n\n"
        "Si este aviso se repite, copia este mensaje cuando pidas ayuda. "
        "Te escribo de nuevo cuando vuelva a funcionar."
    )
    estado["ultimo_aviso_falla"] = ahora().isoformat()
    print("Aviso de falla enviado por Telegram.")


def registrar_exito(estado: dict) -> None:
    if estado.get("ultimo_aviso_falla"):
        if send_telegram(
            "✅ El robot de Dune volvió a funcionar. Sigo vigilando AMC cada 15 minutos.",
            obligatorio=False,
        ):
            estado["ultimo_aviso_falla"] = None
            estado["ultimo_mensaje_semanal"] = ahora().isoformat()
    estado["fallas_seguidas"] = 0


def mensaje_semanal(estado: dict, fechas: list[datetime]) -> None:
    ultimo = estado.get("ultimo_mensaje_semanal")
    if ultimo and ahora() - datetime.fromisoformat(ultimo) < timedelta(days=DIAS_ENTRE_MENSAJES_SEMANALES):
        return

    if send_telegram(
        "🤖 Sigo vigilando AMC Lincoln Square 13 cada 15 minutos.\n"
        f"Por ahora Dune: Part Three se vende hasta el {fechas[-1]:%d-%m-%Y}. "
        "Te aviso apenas abran fechas nuevas.\n\n"
        "(Este mensaje llega una vez por semana. Si pasa más de una semana sin "
        "recibirlo, algo le pasó al robot.)",
        obligatorio=False,
    ):
        estado["ultimo_mensaje_semanal"] = ahora().isoformat()
        print("Mensaje semanal enviado por Telegram.")


# --- Programa principal -------------------------------------------------------------

def main() -> None:
    estado = leer_estado()

    try:
        fechas = leer_fechas_disponibles()
    except Exception as error:  # cualquier problema al leer la pagina
        registrar_falla(estado, error)
    else:
        avisar_si_hay_fechas_nuevas(estado, fechas)
        registrar_exito(estado)
        mensaje_semanal(estado, fechas)
        nota_en_github("notice", "Revision OK", f"Dune: Part Three se vende hasta el {fechas[-1]:%d-%m-%Y}")

    guardar_estado(estado)


if __name__ == "__main__":
    main()
