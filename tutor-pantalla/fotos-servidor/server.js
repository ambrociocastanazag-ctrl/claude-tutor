// Servicio de fotos del celular para los tutores (tutor-pantalla/celular.py).
//
// El panel abre una sesión (con la clave TUTOR_CLAVE) y recibe un código de 6 dígitos + un QR. En el celular se abre
// https://<servicio>/c/<código>, se toma la foto y se sube. El panel la recoge en 1–2 s y el servidor la BORRA al
// entregarla. Al cerrar el panel se borra la sesión; además, todo lo que lleve más de 10 min sin uso se borra solo.
//
// Almacén: con DATABASE_URL, Postgres (esquema propio «tutor», tablas tutor.sesiones y tutor.fotos; no toca nada más).
// Sin DATABASE_URL, en memoria (pruebas locales).
//
//   TUTOR_CLAVE   la clave compartida con el panel (obligatoria)
//   DATABASE_URL  Postgres (opcional)        PORT  el puerto (Railway lo pone)
//   URL_PUBLICA   la dirección pública (opcional; si no, se deduce de la petición)
'use strict';
const http = require('http');
const crypto = require('crypto');
const QRCode = require('qrcode');

const CLAVE = process.env.TUTOR_CLAVE || '';
if (CLAVE.length < 24) { console.error('Falta TUTOR_CLAVE (mínimo 24 caracteres).'); process.exit(1); }
const PORT = Number(process.env.PORT) || 8787;
const VIDA_MIN = 10;                     // minutos sin uso antes de borrar una sesión o una foto
const MAX_FOTO = 8 * 1024 * 1024;        // bytes por foto (la página ya las reduce a ~0,5–1 MB)
const MAX_PEND = 6;                      // fotos esperando por sesión
const TIPOS = new Set(['image/jpeg', 'image/png', 'image/webp']);

// ---------- almacén ----------
function almacenMemoria() {
  const ses = new Map();                 // código → {vista, fotos: [{id, media_type, datos, creada}]}
  let n = 0;
  return {
    async iniciar() {},
    async crear(c) { if (ses.has(c)) return false; ses.set(c, {vista: Date.now(), fotos: []}); return true; },
    async viva(c) { return ses.has(c); },
    async tocar(c) { const s = ses.get(c); if (s) s.vista = Date.now(); return !!s; },
    async pendientes(c) { const s = ses.get(c); return s ? s.fotos.length : 0; },
    async guardar(c, tipo, datos) { const s = ses.get(c); if (!s) return false; s.fotos.push({id: ++n, media_type: tipo, datos, creada: Date.now()}); return true; },
    async sacar(c) { const s = ses.get(c); if (!s) return null; const f = s.fotos; s.fotos = []; s.vista = Date.now(); return f; },
    async borrar(c) { ses.delete(c); },
    async limpiar() {
      const lim = Date.now() - VIDA_MIN * 60000;
      for (const [c, s] of ses) { if (s.vista < lim) ses.delete(c); else s.fotos = s.fotos.filter(f => f.creada >= lim); }
    },
  };
}

function almacenPostgres(url) {
  const {Pool} = require('pg');
  const pool = new Pool({connectionString: url, max: 4, ssl: /sslmode=require/.test(url) ? {rejectUnauthorized: false} : undefined});
  const q = (t, v) => pool.query(t, v);
  return {
    async iniciar() {
      await q('CREATE SCHEMA IF NOT EXISTS tutor');
      await q('CREATE TABLE IF NOT EXISTS tutor.sesiones (codigo text PRIMARY KEY, vista timestamptz NOT NULL DEFAULT now())');
      await q(`CREATE TABLE IF NOT EXISTS tutor.fotos (id bigserial PRIMARY KEY,
               codigo text NOT NULL REFERENCES tutor.sesiones(codigo) ON DELETE CASCADE,
               media_type text NOT NULL, datos bytea NOT NULL, creada timestamptz NOT NULL DEFAULT now())`);
    },
    async crear(c) { const r = await q('INSERT INTO tutor.sesiones (codigo) VALUES ($1) ON CONFLICT DO NOTHING', [c]); return r.rowCount === 1; },
    async viva(c) { return (await q('SELECT 1 FROM tutor.sesiones WHERE codigo = $1', [c])).rowCount === 1; },
    async tocar(c) { return (await q('UPDATE tutor.sesiones SET vista = now() WHERE codigo = $1', [c])).rowCount === 1; },
    async pendientes(c) { return Number((await q('SELECT count(*) AS n FROM tutor.fotos WHERE codigo = $1', [c])).rows[0].n); },
    async guardar(c, tipo, datos) {
      try { await q('INSERT INTO tutor.fotos (codigo, media_type, datos) VALUES ($1, $2, $3)', [c, tipo, datos]); return true; }
      catch (e) { if (e.code === '23503') return false; throw e; }       // la sesión ya no existe
    },
    async sacar(c) {                    // entrega y BORRA en la misma operación
      await q('UPDATE tutor.sesiones SET vista = now() WHERE codigo = $1', [c]);
      const r = await q('DELETE FROM tutor.fotos WHERE codigo = $1 RETURNING id, media_type, datos, creada', [c]);
      return r.rows.sort((a, b) => Number(a.id) - Number(b.id));
    },
    async borrar(c) { await q('DELETE FROM tutor.sesiones WHERE codigo = $1', [c]); },
    async limpiar() {
      await q(`DELETE FROM tutor.sesiones WHERE vista < now() - interval '${VIDA_MIN} minutes'`);
      await q(`DELETE FROM tutor.fotos WHERE creada < now() - interval '${VIDA_MIN} minutes'`);
    },
  };
}

const db = process.env.DATABASE_URL ? almacenPostgres(process.env.DATABASE_URL) : almacenMemoria();

// ---------- límites contra adivinar códigos ----------
const intentos = new Map();              // ip → {n, desde}
function bloqueado(ip) { const i = intentos.get(ip); return i && Date.now() - i.desde < 600000 && i.n >= 20; }
function fallo(ip) {
  const i = intentos.get(ip);
  if (!i || Date.now() - i.desde >= 600000) intentos.set(ip, {n: 1, desde: Date.now()}); else i.n++;
}

// ---------- utilidades ----------
function ipDe(req) { return (req.headers['x-forwarded-for'] || req.socket.remoteAddress || '').split(',')[0].trim(); }
function autorizado(req) {
  const h = req.headers.authorization || '', esperado = 'Bearer ' + CLAVE;
  return h.length === esperado.length && crypto.timingSafeEqual(Buffer.from(h), Buffer.from(esperado));
}
function json(res, codigo, dato) {
  res.writeHead(codigo, {'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store'});
  res.end(JSON.stringify(dato));
}
function cuerpo(req, max) {
  return new Promise((ok, mal) => {
    const partes = []; let n = 0;
    req.on('data', d => { n += d.length; if (n > max) { mal(new Error('grande')); req.destroy(); } else partes.push(d); });
    req.on('end', () => ok(Buffer.concat(partes))); req.on('error', mal);
  });
}
function base(req) {
  if (process.env.URL_PUBLICA) return process.env.URL_PUBLICA.replace(/\/$/, '');
  const proto = req.headers['x-forwarded-proto'] || 'http';
  return proto + '://' + req.headers.host;
}
const CODIGO = /^\d{6}$/;
function nuevoCodigo() { return String(crypto.randomInt(0, 1000000)).padStart(6, '0'); }

// ---------- la página del celular ----------
const PAGINA = require('fs').readFileSync(require('path').join(__dirname, 'celular.html'), 'utf8');

// ---------- rutas ----------
async function atender(req, res) {
  const url = new URL(req.url, 'http://x'), ruta = url.pathname, ip = ipDe(req);
  res.setHeader('X-Content-Type-Options', 'nosniff');

  if (req.method === 'GET' && (ruta === '/' || /^\/c\/\d{6}$/.test(ruta))) {
    res.writeHead(200, {'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'});
    return res.end(PAGINA);
  }
  if (req.method === 'GET' && ruta === '/salud') return json(res, 200, {ok: true});

  // --- el celular (sin clave: solo con un código vivo) ---
  let m = ruta.match(/^\/api\/codigo\/(\d{6})$/);
  if (req.method === 'GET' && m) {
    if (bloqueado(ip)) return json(res, 429, {ok: false, error: 'Demasiados intentos. Espera unos minutos.'});
    const viva = await db.viva(m[1]);
    if (!viva) fallo(ip);
    return json(res, viva ? 200 : 404, viva ? {ok: true} : {ok: false, error: 'Ese código no existe o ya caducó. Mira el código en tu panel.'});
  }
  m = ruta.match(/^\/api\/subir\/(\d{6})$/);
  if (req.method === 'POST' && m) {
    if (bloqueado(ip)) return json(res, 429, {ok: false, error: 'Demasiados intentos. Espera unos minutos.'});
    const tipo = (req.headers['content-type'] || '').split(';')[0].trim();
    if (!TIPOS.has(tipo)) return json(res, 415, {ok: false, error: 'Solo fotos (JPG, PNG o WebP).'});
    if (!(await db.viva(m[1]))) { fallo(ip); return json(res, 404, {ok: false, error: 'Ese código ya caducó. Abre «Foto del celular» otra vez en tu panel.'}); }
    if ((await db.pendientes(m[1])) >= MAX_PEND) return json(res, 429, {ok: false, error: 'Hay varias fotos esperando: abre tu panel para recogerlas.'});
    let datos;
    try { datos = await cuerpo(req, MAX_FOTO); } catch (e) { return json(res, 413, {ok: false, error: 'La foto pesa demasiado.'}); }
    if (!datos.length) return json(res, 400, {ok: false, error: 'La foto llegó vacía.'});
    const ok = await db.guardar(m[1], tipo, datos);
    return json(res, ok ? 200 : 404, ok ? {ok: true} : {ok: false, error: 'Ese código ya caducó.'});
  }

  // --- el panel (con la clave) ---
  if (ruta.startsWith('/api/')) {
    if (!autorizado(req)) return json(res, 401, {ok: false, error: 'Clave incorrecta.'});
    if (req.method === 'POST' && ruta === '/api/sesion') {
      let c = null;
      for (let i = 0; i < 10 && !c; i++) { const x = nuevoCodigo(); if (await db.crear(x)) c = x; }
      if (!c) return json(res, 503, {ok: false, error: 'No pude crear un código; intenta otra vez.'});
      const enlace = base(req) + '/c/' + c;
      const qr = await QRCode.toString(enlace, {type: 'svg', margin: 1, errorCorrectionLevel: 'M'});
      return json(res, 200, {ok: true, codigo: c, url: enlace, inicio: base(req), qr, vida_min: VIDA_MIN});
    }
    m = ruta.match(/^\/api\/fotos\/(\d{6})$/);
    if (req.method === 'GET' && m) {
      const fotos = await db.sacar(m[1]);
      if (fotos === null || (!fotos.length && !(await db.viva(m[1])))) return json(res, 404, {ok: false, error: 'La sesión caducó.'});
      return json(res, 200, {ok: true, fotos: fotos.map(f => ({media_type: f.media_type, datos: Buffer.from(f.datos).toString('base64')}))});
    }
    m = ruta.match(/^\/api\/sesion\/(\d{6})$/);
    if (req.method === 'DELETE' && m) { await db.borrar(m[1]); return json(res, 200, {ok: true}); }
  }
  json(res, 404, {ok: false, error: 'No existe.'});
}

db.iniciar().then(() => {
  http.createServer((req, res) => atender(req, res).catch(e => { console.error(e); json(res, 500, {ok: false, error: 'Error del servidor.'}); }))
    .listen(PORT, () => console.log(`Fotos del tutor en el puerto ${PORT} (${process.env.DATABASE_URL ? 'Postgres, esquema tutor' : 'memoria'})`));
  setInterval(() => db.limpiar().catch(e => console.error('limpiar:', e.message)), 60000);
}).catch(e => { console.error('No pude preparar el almacén:', e.message); process.exit(1); });
