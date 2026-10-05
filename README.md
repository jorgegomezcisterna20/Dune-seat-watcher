# Monitor de fechas: Dune: Part Three en AMC Lincoln Square 13

Este programa revisa automáticamente, cada 15 minutos, si AMC abrió la venta
de entradas para fechas posteriores al **13 de enero de 2027** (que es el
límite actual). Si detecta una fecha nueva, te manda un mensaje de Telegram
al instante para que tú entres a comprar la butaca.

No necesitas dejar tu celular ni tu computador prendidos: todo corre gratis
en los servidores de GitHub.

No revisa butacas específicas (eso está bloqueado por el sitio, como ya
conversamos) — te avisa apenas se abra una fecha nueva, y ahí entras tú a
elegir la butaca entre fila G-J y columna 10-22.

## Mensajes que te pueden llegar por Telegram

- 🎬 **Fechas nuevas**: AMC abrió la venta después del 13 de enero. ¡A comprar!
- 🤖 **Mensaje semanal**: "Sigo vigilando...". Llega una vez por semana. Si
  pasa más de una semana sin recibirlo, algo le pasó al robot.
- ⚠️ **Falla**: el robot no pudo revisar la página varias veces seguidas
  (máximo un aviso cada 12 horas). Incluye el error, para que pidas ayuda.
- ✅ **Recuperado**: el robot volvió a funcionar después de una falla.

---

## Paso 1: Crear tu bot de Telegram (5 minutos)

1. Abre Telegram y busca el usuario **@BotFather** (es el bot oficial para
   crear bots).
2. Escríbele el comando `/newbot`.
3. Te pedirá un nombre (cualquier cosa, ej. "Dune Seat Watcher") y un
   usuario que termine en "bot" (ej. `dune_seat_watcher_bot`).
4. Al terminar, @BotFather te va a entregar un **token**, algo como:
   `123456789:AAExampleTokenNoEsReal`
   Guárdalo, lo vas a necesitar en el Paso 3.

## Paso 2: Obtener tu "chat_id" (2 minutos)

1. Busca en Telegram al usuario **@userinfobot** y escríbele cualquier
   mensaje (ej. "hola").
2. Te va a responder con tu información, incluyendo un número llamado
   **Id**. Ese número es tu `chat_id`. Guárdalo también.
3. Importante: además, busca el bot que TÚ creaste en el Paso 1 y
   apriétale "Iniciar" o mándale un mensaje cualquiera. Si no le escribes
   primero, el bot no puede mandarte mensajes a ti.

## Paso 3: Subir este proyecto a GitHub (10 minutos)

1. Si no tienes cuenta, crea una gratis en [github.com](https://github.com).
2. Crea un repositorio nuevo (puede ser privado), por ejemplo llamado
   `dune-seat-watcher`.
3. Sube todos los archivos de esta carpeta a ese repositorio (puedes
   arrastrar los archivos directamente desde la web de GitHub con el botón
   "Add file" → "Upload files", no necesitas usar la línea de comandos).

## Paso 4: Configurar tus datos secretos en GitHub (3 minutos)

Esto es para que el token de Telegram no quede visible públicamente en el
código.

1. Dentro de tu repositorio en GitHub, ve a **Settings** →
   **Secrets and variables** → **Actions**.
2. Click en **New repository secret**.
   - Nombre: `TELEGRAM_BOT_TOKEN` — Valor: el token del Paso 1.
3. Click en **New repository secret** de nuevo.
   - Nombre: `TELEGRAM_CHAT_ID` — Valor: el número del Paso 2.

## Paso 5: Probarlo

1. Ve a la pestaña **Actions** de tu repositorio.
2. Debería aparecer el workflow "Monitor Dune Part Three - AMC Lincoln
   Square 13".
3. Click en él, y luego en el botón **Run workflow** para probarlo
   manualmente (no hace falta esperar los 15 minutos).
4. Si todo quedó bien configurado, te llega por Telegram el mensaje 🤖
   "Sigo vigilando..." y la ejecución queda con un ✓ verde. En el log
   debería decir algo como `Ultima fecha a la venta hoy: 13-01-2027`.

A partir de ahí, el robot queda revisando solo cada 15 minutos. El día que
AMC abra fechas después del 13 de enero, te va a llegar un mensaje de
Telegram al instante.

---

## Los 60 días de GitHub (ya resuelto solo)

GitHub **desactiva automáticamente** los workflows programados de los
repositorios públicos si pasan **60 días seguidos** sin ningún cambio
("commit").

Para que eso no pase, el mismo robot hace un cambio vacío cada 45 días.
Vas a ver en el historial commits llamados
`Mantener activo el monitor (automatico)`: son normales, no los borres.

Si aun así algún día aparece en la pestaña **Actions** un aviso de que el
workflow fue deshabilitado, hay un botón para reactivarlo con un clic.

## Historial de arreglos

- **05-10-2026**: desde el 15-09-2026 el robot fallaba en cada revisión.
  Ese día salió una versión nueva de Playwright y el robot seguía usando un
  navegador guardado de la versión anterior. Ahora el navegador guardado
  queda marcado con su versión, Playwright quedó fijo en una versión, y el
  robot avisa por Telegram si vuelve a fallar.

## Si en algún momento quieres cambiar el criterio

- Para cambiar la fecha límite, edita la variable `CUTOFF_DATE` en
  `check_dune.py`.
- Para cambiar cada cuánto revisa, edita la línea `cron` en
  `.github/workflows/check.yml` (ej. `*/30 * * * *` para cada 30 minutos).
