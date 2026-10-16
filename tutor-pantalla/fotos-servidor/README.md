# Fotos del celular (servicio)

Servicio pequeño (Node, sin framework) para el botón **«Foto del celular»** de los tutores: el panel abre una sesión y muestra un QR y un código de 6 dígitos; en el celular se abre la página, se toma la foto y se sube; el panel la recoge en 1–2 s y el servicio **la borra al entregarla**. Al cerrar el panel se borra la sesión, y todo lo que lleve más de 10 min sin uso se borra solo. La foto llega al chat como adjunto pendiente (miniatura y ✕): solo le llega al tutor si la persona envía el mensaje.

## Archivos

| Archivo | Qué es |
|---|---|
| `server.js` | El servicio: página del celular, subir (solo con un código vivo), y para el panel (con `TUTOR_CLAVE`): abrir sesión (código + QR en SVG), recoger y borrar, cerrar. Límite de intentos por IP, solo JPG/PNG/WebP, máx. 8 MB y 6 fotos esperando. |
| `celular.html` | La página del celular (código, «Tomar foto», «Elegir de la galería»; reduce la foto a 2000 px antes de subirla). |
| `package.json`, `package-lock.json` | Dependencias: `pg` y `qrcode`. `node_modules/` no se versiona. |

## Variables

- `TUTOR_CLAVE` (obligatoria, ≥ 24 caracteres): la misma `FOTOS_CLAVE` de `tutor-pantalla/.env`.
- `DATABASE_URL` (opcional): Postgres. Sin ella guarda en memoria (pruebas).
- `PORT` (Railway la pone) y `URL_PUBLICA` (opcional; si no, se deduce de la petición).

## Cómo cambiarlo

1. Edita `server.js` o `celular.html`.
2. Prueba en local: `npm install` y `TUTOR_CLAVE=<clave de prueba> node server.js`; luego `python tutor-pantalla/celular.py --probar http://localhost:8787 <clave>` hasta «Celular: todo bien».
3. Haz commit y push: el servicio de Railway conectado a este repo se vuelve a desplegar solo.
4. Vuelve a correr `python tutor-pantalla/celular.py --probar` (usa `tutor-pantalla/.env`).

## Desplegar por primera vez en Railway

1. En Railway: **New → GitHub Repo →** este repo (en el proyecto que elijas). Detecta Node y arranca con `npm start`.
2. Variables del servicio: `TUTOR_CLAVE` (la misma `FOTOS_CLAVE` de `tutor-pantalla/.env`) y, si quieres Postgres, `DATABASE_URL=${{<tu Postgres de pruebas>.DATABASE_URL}}` (referencia a ese servicio).
3. **Settings → Networking → Generate Domain** y pon esa dirección en `tutor-pantalla/.env` como `FOTOS_URL`.
4. Comprueba con `python tutor-pantalla/celular.py --probar` hasta «Celular: todo bien».
