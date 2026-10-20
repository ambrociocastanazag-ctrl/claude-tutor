/* Profe · figuras del tutor sobre la clase.
   Funciones puras: números y texto → SVG como texto. Sin React, sin CSS, sin fuentes externas.
   Todas devuelven { svg, g, x, y, w, h }:
     g   → fragmento en coordenadas de la ventana de la clase (px de pantalla).
     svg → el mismo dibujo recortado a su caja; colócalo en (x, y) o pásalo a PNG.
   Opciones comunes: tema 'claro'|'oscuro' · escala 1|1.25|1.5 · color (azul por defecto) · t 0→1 (entrada) · variante.
   Las coordenadas ya vienen multiplicadas por la escala; la escala solo agranda trazos, radios y letra.
   Gráficas: ejes = { x0, x1, y0, y1, q:[min,max], p:[min,max] } → px de los extremos de cada eje. */
(function (raiz) {
  'use strict';
  var SANS = "'Segoe UI', system-ui, sans-serif";
  var LETRAS = { print: "'Segoe Print', 'Ink Free', 'Comic Sans MS', cursive", ink: "'Ink Free', 'Segoe Print', 'Comic Sans MS', cursive", ui: "'Segoe UI', system-ui, sans-serif" };
  var n2 = function (x) { return Math.round(x * 100) / 100; };
  var lim = function (x, a, b) { a = a == null ? 0 : a; b = b == null ? 1 : b; return Math.max(a, Math.min(b, x)); };
  var sal = function (t) { return 1 - Math.pow(1 - lim(t), 3); };
  var suave = function (t) { t = lim(t); return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
  var tramo = function (t, a, b) { return lim((t - a) / (b - a)); };
  var esc = function (s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); };
  var P2 = function (x, y) { return n2(x) + ',' + n2(y); };
  var cuenta = 0; function uid(p) { cuenta += 1; return 'pf' + (p || '') + cuenta.toString(36); }
  function fmt(v) { var r = Math.round(v * 100) / 100; return String(r).replace('.', ',').replace('-', '−'); }

  function oklch(L, C, H) {
    var h = H * Math.PI / 180, A = C * Math.cos(h), B = C * Math.sin(h);
    var l = Math.pow(L + 0.3963377774 * A + 0.2158037573 * B, 3);
    var m = Math.pow(L - 0.1055613458 * A - 0.0638541728 * B, 3);
    var s = Math.pow(L - 0.0894841775 * A - 1.291485548 * B, 3);
    var rgb = [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s, -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s];
    return '#' + rgb.map(function (x) { x = lim(x); x = x <= 0.0031308 ? 12.92 * x : 1.055 * Math.pow(x, 1 / 2.4) - 0.055; return ('0' + Math.round(x * 255).toString(16)).slice(-2); }).join('');
  }

  /* Seis colores con significado. [L, C] por tema. Claro: tinta oscura (≥4.5:1 con texto blanco salvo amarillo). Oscuro: tinta clara con texto oscuro. */
  var TONOS = {
    azul:     { h: 258, claro: [0.50, 0.17], oscuro: [0.77, 0.12] },
    verde:    { h: 150, claro: [0.50, 0.13], oscuro: [0.80, 0.15] },
    rojo:     { h: 25,  claro: [0.52, 0.19], oscuro: [0.73, 0.16] },
    naranja:  { h: 50,  claro: [0.55, 0.16], oscuro: [0.79, 0.14] },
    amarillo: { h: 85,  claro: [0.66, 0.14], oscuro: [0.87, 0.15] },
    morado:   { h: 300, claro: [0.50, 0.19], oscuro: [0.76, 0.14] }
  };
  var NEUTRO = {
    claro:  { fondo: '#ffffff', papel: '#ffffff', borde: oklch(0.86, 0.008, 265), texto: oklch(0.24, 0.01, 265), suave: oklch(0.48, 0.01, 265) },
    oscuro: { fondo: oklch(0.205, 0.008, 265), papel: oklch(0.265, 0.01, 265), borde: oklch(0.4, 0.012, 265), texto: oklch(0.94, 0.005, 265), suave: oklch(0.75, 0.01, 265) }
  };
  function paleta(color, tema, fondo) {
    var nom = TONOS[color] ? color : 'azul', T = TONOS[nom], osc = tema === 'oscuro', LC = osc ? T.oscuro : T.claro, h = T.h, N = NEUTRO[osc ? 'oscuro' : 'claro'];
    var amC = !osc && nom === 'amarillo';
    return {
      nombre: nom, osc: osc, tinta: oklch(LC[0], LC[1], h),
      sobre: osc ? oklch(0.22, 0.05, h) : (amC ? oklch(0.27, 0.06, 75) : '#ffffff'),
      fuerte: osc ? oklch(Math.min(0.9, LC[0] + 0.05), LC[1], h) : (amC ? oklch(0.47, 0.1, 75) : oklch(LC[0] - 0.07, LC[1], h)),
      tenue: osc ? oklch(0.33, 0.06, h) : oklch(0.95, 0.035, h),
      fondo: fondo || N.fondo, papel: N.papel, borde: N.borde, texto: N.texto, suave: N.suave,
      relleno: osc ? 0.24 : 0.15, sombra: osc ? '#000000' : oklch(0.3, 0.03, 265), sombraA: osc ? 0.42 : 0.14
    };
  }

  var ctx = null;
  function medir(texto, px, peso, fuente) {
    texto = String(texto == null ? '' : texto);
    try {
      if (!ctx) { var c = typeof OffscreenCanvas !== 'undefined' ? new OffscreenCanvas(1, 1) : document.createElement('canvas'); ctx = c.getContext('2d'); }
      ctx.font = (peso || 400) + ' ' + px + 'px ' + (fuente || SANS); return ctx.measureText(texto).width;
    } catch (e) { return texto.length * px * 0.55; }
  }
  function envolver(texto, px, peso, ancho, fuente) {
    var out = [], l = '';
    String(texto || '').split(/\s+/).filter(Boolean).forEach(function (w) {
      var p = l ? l + ' ' + w : w;
      if (l && medir(p, px, peso, fuente) > ancho) { out.push(l); l = w; } else l = p;
    });
    if (l) out.push(l);
    return out;
  }
  function txt(s, x, y, px, peso, color, extra, fuente) {
    return '<text x="' + n2(x) + '" y="' + n2(y) + '" font-family="' + esc(fuente || SANS) + '" font-size="' + n2(px) + '" font-weight="' + (peso || 400) + '" fill="' + color + '"' + (extra || '') + '>' + esc(s) + '</text>';
  }
  function txtHalo(s, x, y, px, peso, color, halo, hg, extra, fuente) {
    return txt(s, x, y, px, peso, halo, ' stroke="' + halo + '" stroke-width="' + n2(hg) + '" stroke-linejoin="round"' + (extra || ''), fuente) + txt(s, x, y, px, peso, color, extra, fuente);
  }
  function rr(x, y, w, h, r) {
    var c = Array.isArray(r) ? r : [r, r, r, r];
    var A = function (q, X, Y) { return q ? 'A' + n2(q) + ',' + n2(q) + ' 0 0 1 ' + P2(X, Y) : ''; };
    return 'M' + P2(x + c[0], y) + 'H' + n2(x + w - c[1]) + A(c[1], x + w, y + c[1]) + 'V' + n2(y + h - c[2]) + A(c[2], x + w - c[2], y + h) +
      'H' + n2(x + c[3]) + A(c[3], x, y + h - c[3]) + 'V' + n2(y + c[0]) + A(c[0], x + c[0], y) + 'Z';
  }
  function revela(e) { if (e >= 0.999) return ''; if (e <= 0.005) return ' visibility="hidden"'; return ' pathLength="1" stroke-dasharray="' + n2(e) + ' 1"'; }
  function linea(d, color, sw, extra) { return '<path d="' + d + '" fill="none" stroke="' + color + '" stroke-width="' + n2(sw) + '" stroke-linecap="round" stroke-linejoin="round"' + (extra || '') + '/>'; }
  function conHalo(d, P, sw, s, extra, op) {
    return linea(d, P.fondo, sw + 3 * s, ' stroke-opacity="0.85"' + (extra || '')) + linea(d, P.tinta, sw, (op != null && op < 1 ? ' stroke-opacity="' + n2(op) + '"' : '') + (extra || ''));
  }
  function sombraRR(x, y, w, h, r, P, s, k) {
    k = k == null ? 1 : k; var g = '';
    [[3, 5, 0.05], [1.5, 2.5, 0.08], [0, 1, 0.12]].forEach(function (a) {
      var e = a[0] * s * k;
      g += '<path d="' + rr(x - e, y - e + a[1] * s * k, w + 2 * e, h + 2 * e, (Array.isArray(r) ? Math.max.apply(null, r) : r) + e) + '" fill="' + P.sombra + '" fill-opacity="' + n2(a[2] * (P.osc ? 2.6 : 1)) + '"/>';
    });
    return g;
  }
  function punto(x, y, r, P, s, color) {
    return '<circle cx="' + n2(x) + '" cy="' + n2(y) + '" r="' + n2(r + 2 * s) + '" fill="' + P.fondo + '" fill-opacity="0.9"/><circle cx="' + n2(x) + '" cy="' + n2(y) + '" r="' + n2(r) + '" fill="' + (color || P.tinta) + '"/>';
  }
  function punta(x, y, ux, uy, l, w, color) {
    var nx = -uy, ny = ux;
    return '<path d="M' + P2(x, y) + 'L' + P2(x - ux * l + nx * w / 2, y - uy * l + ny * w / 2) + 'L' + P2(x - ux * l * 0.72, y - uy * l * 0.72) +
      'L' + P2(x - ux * l - nx * w / 2, y - uy * l - ny * w / 2) + 'Z" fill="' + color + '" stroke="' + color + '" stroke-width="0.75" stroke-linejoin="round"/>';
  }
  function Caja() { this.a = Infinity; this.b = Infinity; this.c = -Infinity; this.d = -Infinity; }
  Caja.prototype.p = function (x, y, m) { m = m || 0; this.a = Math.min(this.a, x - m); this.b = Math.min(this.b, y - m); this.c = Math.max(this.c, x + m); this.d = Math.max(this.d, y + m); return this; };
  Caja.prototype.r = function (x, y, w, h, m) { return this.p(x, y, m).p(x + w, y + h, m); };
  function fin(g, B, extra) {
    if (!isFinite(B.a)) B.p(0, 0);
    var x = Math.floor(B.a), y = Math.floor(B.b), w = Math.ceil(B.c) - x, h = Math.ceil(B.d) - y;
    var r = { svg: '<svg xmlns="http://www.w3.org/2000/svg" width="' + w + '" height="' + h + '" viewBox="' + x + ' ' + y + ' ' + w + ' ' + h + '">' + g + '</svg>', g: g, x: x, y: y, w: w, h: h };
    if (extra) Object.keys(extra).forEach(function (k) { r[k] = extra[k]; });
    return r;
  }
  function aparece(g, e, cx, cy, dx, dy, sc) {
    if (e >= 0.999) return g; if (e <= 0.001) return '';
    sc = sc == null ? 0.96 : sc; var k = sc + (1 - sc) * e;
    return '<g opacity="' + n2(e) + '" transform="translate(' + P2(cx + (dx || 0) * (1 - e), cy + (dy || 0) * (1 - e)) + ') scale(' + n2(k) + ') translate(' + P2(-cx, -cy) + ')">' + g + '</g>';
  }
  function ejes(E) {
    if (!E) return null; if (E.px) return E;
    var f = function (q, p) { return [E.x0 + (q - E.q[0]) / (E.q[1] - E.q[0]) * (E.x1 - E.x0), E.y0 + (p - E.p[0]) / (E.p[1] - E.p[0]) * (E.y1 - E.y0)]; };
    var inv = function (x, y) { return [E.q[0] + (x - E.x0) / (E.x1 - E.x0) * (E.q[1] - E.q[0]), E.p[0] + (y - E.y0) / (E.y1 - E.y0) * (E.p[1] - E.p[0])]; };
    return { px: f, valor: inv, x0: E.x0, x1: E.x1, y0: E.y0, y1: E.y1, q: E.q, p: E.p };
  }
  function base(o) { o = o || {}; var s = o.escala || 1; return { o: o, s: s, P: paleta(o.color, o.tema, o.fondo), t: o.t == null ? 1 : o.t }; }

  /* Ficha: etiqueta compacta. partes [[texto, peso, color?]]. estilo solido | papel | tenue. ancla i | c | d (x), y = centro. */
  function ficha(o) {
    var s = o.s, P = o.P, px = (o.px || 12.5) * s, h = (o.alto || 24) * s, pad = (o.pad || 8) * s, gap = 5 * s, r = Math.min((o.r != null ? o.r : 6) * s, h / 2);
    var partes = o.partes || [[o.texto, 600]], anchos = partes.map(function (p) { return medir(p[0], px, p[1]); });
    var w = pad * 2 + anchos.reduce(function (a, b) { return a + b; }, 0) + gap * (partes.length - 1);
    var x = o.x - (o.ancla === 'd' ? w : o.ancla === 'c' ? w / 2 : 0), y = o.y - h / 2, est = o.estilo || 'solido';
    var fill = est === 'solido' ? P.tinta : est === 'tenue' ? P.tenue : P.papel, col = est === 'solido' ? P.sobre : P.fuerte, d = rr(x, y, w, h, r);
    var g = '<path d="' + d + '" fill="none" stroke="' + P.fondo + '" stroke-opacity="0.9" stroke-width="' + n2(3 * s) + '"/>' + (o.sombra === false ? '' : sombraRR(x, y, w, h, r, P, s, 0.5)) +
      '<path d="' + d + '" fill="' + fill + '"' + (est === 'papel' ? ' stroke="' + P.tinta + '" stroke-width="' + n2(1.25 * s) + '"' : '') + '/>';
    var cx = x + pad;
    partes.forEach(function (p, i) { g += txt(p[0], cx, y + h / 2 + px * 0.36, px, p[1], p[2] || col); cx += anchos[i] + gap; });
    return { g: g, x: x, y: y, w: w, h: h };
  }

  /* Burbuja de papel con pico opcional. pico = { tip:[x,y], lado:'izq'|'der'|'arr'|'aba' } (lado del globo donde nace) */
  function burbuja(o) {
    var P = o.P, s = o.s, x = o.x, y = o.y, w = o.w, h = o.h, r = o.r || 10 * s, bw = o.bw || 1.5 * s, col = o.borde || P.tinta, fill = o.relleno || P.papel;
    var g = (o.sombra === false ? '' : sombraRR(x, y, w, h, r, P, s, 1)) + '<path d="' + rr(x, y, w, h, r) + '" fill="' + fill + '" stroke="' + col + '" stroke-width="' + n2(bw) + '"/>';
    if (o.pico) {
      var t = o.pico.tip, L = o.pico.lado, hb = 7 * s, a, b1, b2, i1, i2;
      if (L === 'izq' || L === 'der') {
        a = lim(t[1], y + r + hb, y + h - r - hb); var ex = L === 'izq' ? x : x + w, dx = L === 'izq' ? bw * 1.5 : -bw * 1.5;
        b1 = [ex, a - hb]; b2 = [ex, a + hb]; i1 = [ex + dx, a - hb]; i2 = [ex + dx, a + hb];
      } else {
        a = lim(t[0], x + r + hb, x + w - r - hb); var ey = L === 'arr' ? y : y + h, dy = L === 'arr' ? bw * 1.5 : -bw * 1.5;
        b1 = [a - hb, ey]; b2 = [a + hb, ey]; i1 = [a - hb, ey + dy]; i2 = [a + hb, ey + dy];
      }
      g += '<path d="M' + P2(i1[0], i1[1]) + 'L' + P2(b1[0], b1[1]) + 'L' + P2(t[0], t[1]) + 'L' + P2(b2[0], b2[1]) + 'L' + P2(i2[0], i2[1]) + 'Z" fill="' + fill + '"/>' +
        linea('M' + P2(b1[0], b1[1]) + 'L' + P2(t[0], t[1]) + 'L' + P2(b2[0], b2[1]), col, bw);
    }
    return g;
  }
  var LADOS = { derecha: ['izq', 1, 0], izquierda: ['der', -1, 0], arriba: ['aba', 0, -1], abajo: ['arr', 0, 1] };
  function colocar(A, w, h, lado, dist, caja) {
    var L = LADOS[lado] || LADOS.derecha, gx, gy;
    if (caja) { gx = caja.x; gy = caja.y; }
    else if (L[1] > 0) { gx = A.x + dist; gy = A.y - h / 2; }
    else if (L[1] < 0) { gx = A.x - dist - w; gy = A.y - h / 2; }
    else if (L[2] < 0) { gx = A.x - w / 2; gy = A.y - dist - h; }
    else { gx = A.x - w / 2; gy = A.y + dist; }
    return { x: gx, y: gy, cola: L[0], dx: L[1], dy: L[2] };
  }
  function borde(cx, cy, w, h, ax, ay) { // punto del borde de la caja centrada en (cx,cy) hacia (ax,ay)
    var dx = ax - cx, dy = ay - cy, k = Math.min(Math.abs(dx) > 1e-6 ? (w / 2) / Math.abs(dx) : Infinity, Math.abs(dy) > 1e-6 ? (h / 2) / Math.abs(dy) : Infinity);
    return [cx + dx * k, cy + dy * k];
  }
  var ICONO = {
    visto: function (x, y, t, c, sw) { return linea('M' + P2(x - t * 0.42, y + t * 0.02) + 'L' + P2(x - t * 0.12, y + t * 0.32) + 'L' + P2(x + t * 0.45, y - t * 0.3), c, sw); },
    equis: function (x, y, t, c, sw) { var k = t * 0.32; return linea('M' + P2(x - k, y - k) + 'L' + P2(x + k, y + k) + 'M' + P2(x + k, y - k) + 'L' + P2(x - k, y + k), c, sw); },
    devolver: function (x, y, t, c, sw) { var k = t / 24, o = function (a, b) { return P2(x + (a - 12) * k, y + (b - 12) * k); };
      return linea('M' + o(4, 12) + 'A' + n2(8 * k) + ',' + n2(8 * k) + ' 0 1 0 ' + o(12, 4) + 'C' + o(9.6, 4) + ' ' + o(7.4, 5) + ' ' + o(5.8, 6.6) + 'L' + o(4, 8.4) + 'M' + o(4, 4) + 'V' + n2(y + (8.4 - 12) * k) + 'H' + n2(x + (8.4 - 12) * k), c, sw); },
    chispa: function (x, y, t, c) { var k = t / 24, o = function (a, b) { return P2(x + (a - 12) * k, y + (b - 12) * k); };
      return '<path d="M' + o(12, 3) + 'Q' + o(12.9, 11.1) + ' ' + o(21, 12) + 'Q' + o(12.9, 12.9) + ' ' + o(12, 21) + 'Q' + o(11.1, 12.9) + ' ' + o(3, 12) + 'Q' + o(11.1, 11.1) + ' ' + o(12, 3) + 'Z" fill="' + c + '"/>'; },
    enviar: function (x, y, t, c, sw) { return linea('M' + P2(x, y + t * 0.32) + 'V' + n2(y - t * 0.3) + 'M' + P2(x - t * 0.28, y - t * 0.04) + 'L' + P2(x, y - t * 0.32) + 'L' + P2(x + t * 0.28, y - t * 0.04), c, sw); }
  };

  /* Cursor del tutor: punta en (x,y), con rótulo. k = pulsación (1 normal, 0.88 apretando). */
  function cursor(x, y, P, s, nombre, k) {
    k = k == null ? 1 : k; var c = s * k;
    var g = '<g transform="translate(' + P2(x, y) + ') scale(' + n2(c) + ')"><path d="M0,0 L0,16.5 L4.3,12.6 L7.2,19 L10,17.8 L7.3,11.5 L13,11.5 Z" fill="' + P.tinta + '" stroke="' + P.fondo + '" stroke-width="1.6" stroke-linejoin="round"/></g>';
    if (nombre !== false) {
      var px = 11 * s, tw = medir(nombre || 'Tutor', px, 600), w = tw + 12 * s, h = 18 * s, X = x + 11 * s, Y = y + 18 * s;
      g += '<path d="' + rr(X, Y, w, h, [2 * s, 7 * s, 7 * s, 7 * s]) + '" fill="' + P.tinta + '" stroke="' + P.fondo + '" stroke-width="' + n2(1.5 * s) + '"/>' + txt(nombre || 'Tutor', X + 6 * s, Y + h / 2 + px * 0.36, px, 600, P.sobre);
    }
    return g;
  }

  /* ───────── A1 · Globo de explicación ─────────
     { ancla:{x,y}, texto (1–3 frases, string o array), formula, lado 'derecha'|'izquierda'|'arriba'|'abajo', caja:{x,y}, distancia,
       ancho (máx., 260), pieza:{x,y,w,h} (pestaña), variante 'hilo' (recomendada) | 'pico' | 'pestana', enlace (texto de acción al pie) } */
  function globo(o) {
    var b = base(o), s = b.s, P = b.P, t = b.t, v = o.variante || 'hilo', A = o.ancla || { x: 0, y: 0 };
    var maxW = (o.ancho || 260) * s, pad = 12 * s, fs = 14 * s, lh = 20 * s, ff = 15 * s;
    var lineas = envolver([].concat(o.texto || []).join(' '), fs, 400, maxW - 2 * pad);
    var tw = Math.max.apply(null, lineas.map(function (l) { return medir(l, fs, 400); }).concat([0]));
    var fw = o.formula ? medir(o.formula, ff, 600) + 20 * s : 0, pie = o._pie || null;
    var enl = o.enlace ? { w: medir(o.enlace, 12.5 * s, 600) + 20 * s, h: 16 * s } : null;
    var w = Math.ceil(Math.max(tw, fw, pie ? pie.w : 0, enl ? enl.w : 0) + 2 * pad);
    if (pie && pie.lleno) w = Math.max(w, Math.min(maxW, 220 * s));
    var h = Math.ceil(10 * s + lineas.length * lh + (o.formula ? 38 * s : 0) + (pie ? 10 * s + pie.h : 0) + (enl ? 10 * s + enl.h : 0) + 12 * s);
    var B = new Caja(), g = '', sol = v === 'pestana';
    function contenido(gx, gy) {
      var c = '', yy = gy + 10 * s, colT = sol ? P.sobre : P.texto;
      lineas.forEach(function (l, i) { c += txt(l, gx + pad, yy + lh * i + 14.5 * s, fs, 400, colT); });
      yy += lineas.length * lh;
      if (o.formula) {
        yy += 8 * s;
        c += '<path d="' + rr(gx + pad, yy, fw, 30 * s, 6 * s) + '" fill="' + (sol ? P.sobre : P.tenue) + '"' + (sol ? ' fill-opacity="0.16"' : '') + '/>' + txt(o.formula, gx + pad + 10 * s, yy + 15 * s + ff * 0.36, ff, 600, sol ? P.sobre : P.fuerte);
        yy += 30 * s;
      }
      if (pie) { yy += 10 * s; c += pie.dibujar(gx + pad, yy, w - 2 * pad); yy += pie.h; }
      if (enl) { yy += 10 * s; c += ICONO.devolver(gx + pad + 6 * s, yy + 8 * s, 13 * s, sol ? P.sobre : P.fuerte, 1.6 * s) + txt(o.enlace, gx + pad + 17 * s, yy + 12.5 * s, 12.5 * s, 600, sol ? P.sobre : P.fuerte); }
      return c;
    }
    if (v === 'pestana' && o.pieza) {
      var Z = o.pieza, m = 5 * s, abajo = o.lado === 'abajo', mx = Z.x - m, my = Z.y - m, mw = Z.w + 2 * m, mh = Z.h + 2 * m;
      var gx = mx, gy = abajo ? my + mh : my - h, R = 10 * s, e1 = sal(tramo(t, 0, 0.6)), e2 = sal(tramo(t, 0.3, 1));
      var dm = rr(mx, my, mw, mh, abajo ? [8 * s, 8 * s, 8 * s, 0] : [0, 8 * s, 8 * s, 8 * s]);
      g += linea(dm, P.fondo, 5 * s, ' stroke-opacity="0.85"' + revela(e1)) + linea(dm, P.tinta, 2 * s, revela(e1));
      var gg = sombraRR(gx, gy, w, h, R, P, s, 0.6) + '<path d="' + rr(gx, gy, w, h, abajo ? [0, R, R, R] : [R, R, R, 0]) + '" fill="' + P.tinta + '"/>' + contenido(gx, gy);
      g += aparece(gg, e2, gx, abajo ? gy : gy + h, 0, 0, 0.92);
      B.r(mx, my, mw, mh, 4 * s).r(gx, gy, w, h, 8 * s);
      return fin(g, B);
    }
    var C = colocar(A, w, h, o.lado || 'derecha', (o.distancia != null ? o.distancia : (v === 'hilo' ? 56 : 18)) * s, o.caja);
    B.r(C.x, C.y, w, h, 8 * s).p(A.x, A.y, 8 * s);
    if (v === 'pico') {
      var gap = (o.hueco != null ? o.hueco : 6) * s, tip = [A.x + C.dx * gap, A.y + C.dy * gap];
      if (o.caja) { var dd = Math.hypot(C.x + w / 2 - A.x, C.y + h / 2 - A.y) || 1; tip = [A.x + (C.x + w / 2 - A.x) / dd * gap, A.y + (C.y + h / 2 - A.y) / dd * gap]; }
      var gp = (o.punto ? punto(A.x, A.y, 3.5 * s, P, s) : '') + burbuja({ P: P, s: s, x: C.x, y: C.y, w: w, h: h, pico: { tip: tip, lado: C.cola } }) + contenido(C.x, C.y);
      g += aparece(gp, sal(t), A.x, A.y, 0, 0, 0.9);
    } else {
      var e1h = sal(tramo(t, 0, 0.55)), e2h = sal(tramo(t, 0.3, 1)), Bp = borde(C.x + w / 2, C.y + h / 2, w, h, A.x, A.y);
      var dl = Math.hypot(Bp[0] - A.x, Bp[1] - A.y) || 1, ux = (Bp[0] - A.x) / dl, uy = (Bp[1] - A.y) / dl, r0 = 3.5 * s;
      if (e1h > 0) g += conHalo('M' + P2(A.x + ux * (r0 + 1.5 * s), A.y + uy * (r0 + 1.5 * s)) + 'L' + P2(Bp[0], Bp[1]), P, 1.5 * s, s, revela(e1h)) + aparece(punto(A.x, A.y, r0, P, s), sal(tramo(t, 0, 0.3)), A.x, A.y, 0, 0, 0.3);
      g += aparece(burbuja({ P: P, s: s, x: C.x, y: C.y, w: w, h: h }) + contenido(C.x, C.y), e2h, Bp[0], Bp[1], 0, 0, 0.94);
    }
    return fin(g, B, { caja: { x: C.x, y: C.y, w: w, h: h } });
  }

  /* ───────── A2 · Explicación en pasos ─────────
     { pasos:[{ insignia:[x,y], pieza:{x,y,w,h}, texto, formula, lado, caja }], actual (0…n-1), progreso 0→1 (voz), riel:{x,y,w}, variante 'numeros' (rec.) | 'riel' | 'rastro' } */
  function pasos(o) {
    var b = base(o), s = b.s, P = b.P, t = b.t, v = o.variante || 'numeros', L = o.pasos || [], k = o.actual || 0, n = L.length, pr = lim(o.progreso || 0);
    var g = '', B = new Caja();
    function insignia(x, y, i, est) {
      B.p(x, y, 14 * s);
      if (est === 'actual') return '<circle cx="' + n2(x) + '" cy="' + n2(y) + '" r="' + n2(14 * s) + '" fill="' + P.fondo + '" fill-opacity="0.9"/><circle cx="' + n2(x) + '" cy="' + n2(y) + '" r="' + n2(12 * s) + '" fill="' + P.tinta + '"/>' + txt(String(i + 1), x, y + 12.5 * s * 0.36, 12.5 * s, 700, P.sobre, ' text-anchor="middle"');
      if (est === 'visto') return '<circle cx="' + n2(x) + '" cy="' + n2(y) + '" r="' + n2(9 * s) + '" fill="' + P.papel + '" stroke="' + P.tinta + '" stroke-width="' + n2(1.5 * s) + '"/>' + ICONO.visto(x, y, 10 * s, P.tinta, 1.75 * s);
      return '<circle cx="' + n2(x) + '" cy="' + n2(y) + '" r="' + n2(9 * s) + '" fill="' + P.papel + '" stroke="' + P.suave + '" stroke-width="' + n2(1.25 * s) + '" stroke-dasharray="' + n2(2.5 * s) + ' ' + n2(2.2 * s) + '"/>' + txt(String(i + 1), x, y + 11 * s * 0.36, 11 * s, 600, P.suave, ' text-anchor="middle"');
    }
    function marco(Z, e) { var d = rr(Z.x - 4 * s, Z.y - 4 * s, Z.w + 8 * s, Z.h + 8 * s, 8 * s); B.r(Z.x, Z.y, Z.w, Z.h, 8 * s); return linea(d, P.fondo, 5 * s, ' stroke-opacity="0.85"' + revela(e)) + linea(d, P.tinta, 2 * s, revela(e)); }
    var pie = {
      w: 0, h: 12 * s, lleno: true, dibujar: function (x, y, w) {
        var cy = y + 6 * s, bw = w - 44 * s, q = '';
        q += linea('M' + P2(x, cy) + 'H' + n2(x + bw), P.borde, 3 * s) + (pr > 0.01 ? linea('M' + P2(x, cy) + 'H' + n2(x + bw * pr), P.tinta, 3 * s) : '');
        return q + txt((k + 1) + ' de ' + n, x + w - 8 * s, cy + 4 * s, 11.5 * s, 600, P.suave, ' text-anchor="end"') + linea('M' + P2(x + w - 3 * s, cy - 3.5 * s) + 'L' + P2(x + w, cy) + 'L' + P2(x + w - 3 * s, cy + 3.5 * s), P.suave, 1.5 * s);
      }
    };
    var cur = L[k];
    if (v === 'rastro') {
      for (var i = 0; i < n - 1; i++) {
        var a = L[i].insignia, c = L[i + 1].insignia, mx = (a[0] + c[0]) / 2, my = (a[1] + c[1]) / 2, dx = c[0] - a[0], dy = c[1] - a[1], dl = Math.hypot(dx, dy) || 1;
        var d = 'M' + P2(a[0], a[1]) + 'Q' + P2(mx - dy / dl * dl * 0.12, my + dx / dl * dl * 0.12) + ' ' + P2(c[0], c[1]);
        g += i < k ? linea(d, P.tinta, 2 * s, ' stroke-opacity="0.55"') : linea(d, P.suave, 1.5 * s, ' stroke-opacity="0.7" stroke-dasharray="' + n2(3 * s) + ' ' + n2(4 * s) + '"');
      }
    }
    if (cur && cur.pieza) g += marco(cur.pieza, sal(t));
    L.forEach(function (p, i) { g += insignia(p.insignia[0], p.insignia[1], i, i < k ? 'visto' : i === k ? 'actual' : 'pendiente'); });
    if (v === 'riel' && o.riel) {
      var R = o.riel, fs = 14 * s, tl = envolver(cur ? cur.texto : '', fs, 400, R.w - 70 * s), bh = Math.max(46 * s, 22 * s + tl.length * 20 * s), y0 = R.y;
      var rg = sombraRR(R.x, y0, R.w, bh, 12 * s, P, s, 1) + '<path d="' + rr(R.x, y0, R.w, bh, 12 * s) + '" fill="' + P.papel + '" stroke="' + P.borde + '" stroke-width="' + n2(1 * s) + '"/>';
      rg += '<circle cx="' + n2(R.x + 22 * s) + '" cy="' + n2(y0 + bh / 2) + '" r="' + n2(11 * s) + '" fill="' + P.tinta + '"/>' + txt(String(k + 1), R.x + 22 * s, y0 + bh / 2 + 12 * s * 0.36, 12 * s, 700, P.sobre, ' text-anchor="middle"');
      tl.forEach(function (l, i) { rg += txt(l, R.x + 42 * s, y0 + bh / 2 - (tl.length - 1) * 10 * s + i * 20 * s + 5 * s, fs, 400, P.texto); });
      var sw = (R.w - 24 * s) / n;
      for (var j = 0; j < n; j++) {
        var x1 = R.x + 12 * s + j * sw + 2 * s, x2 = x1 + sw - 4 * s, yb = y0 + bh - 5 * s;
        rg += linea('M' + P2(x1, yb) + 'H' + n2(x2), P.borde, 3 * s);
        var f = j < k ? 1 : j === k ? pr : 0; if (f > 0.01) rg += linea('M' + P2(x1, yb) + 'H' + n2(x1 + (x2 - x1) * f), P.tinta, 3 * s, j < k ? ' stroke-opacity="0.5"' : '');
      }
      rg += txt((k + 1) + '/' + n, R.x + R.w - 12 * s, y0 + 16 * s, 11 * s, 600, P.suave, ' text-anchor="end"');
      g += aparece(rg, sal(t), R.x + R.w / 2, y0 + bh, 0, 8 * s, 1);
      B.r(R.x, y0, R.w, bh, 8 * s);
    } else if (cur) {
      var gl = globo({ ancla: { x: cur.insignia[0], y: cur.insignia[1] }, texto: cur.texto, formula: cur.formula, lado: cur.lado, caja: cur.caja, ancho: cur.ancho || 230,
        variante: 'pico', distancia: 22, hueco: 16, _pie: pie, tema: o.tema, escala: s, color: o.color, fondo: o.fondo, t: t });
      g += gl.g; B.r(gl.x, gl.y, gl.w, gl.h);
    }
    return fin(g, B);
  }

  /* ───────── A3 · Pregunta rápida ─────────
     { ancla, lado, caja, pregunta, opciones[], correcta, elegida, estado 'pregunta'|'acierto'|'fallo', mensajes:{acierto, fallo},
       variante 'chips' (rec.) | 'tarjeta' | 'grafica' (puntos:[{x,y,letra}]) } */
  function pregunta(o) {
    var b = base(o), s = b.s, P = b.P, t = b.t, v = o.variante || 'chips', est = o.estado || 'pregunta';
    var V = paleta('verde', o.tema, o.fondo), R = paleta('rojo', o.tema, o.fondo), A = o.ancla || { x: 0, y: 0 };
    var maxW = (o.ancho || 280) * s, pad = 12 * s, fq = 14 * s, fo = 13.5 * s, ql = envolver(o.pregunta, fq, 600, maxW - 2 * pad);
    var ops = o.opciones || [], msg = est === 'acierto' ? (o.mensajes || {}).acierto : est === 'fallo' ? (o.mensajes || {}).fallo : null;
    var qw = Math.max.apply(null, ql.map(function (l) { return medir(l, fq, 600); }).concat([0])), lay = [], y = 0, x = 0, rowH, w, cw = maxW - 2 * pad;
    function estOp(i) { return est !== 'pregunta' && i === o.elegida ? est : (est === 'acierto' ? 'apagada' : 'normal'); }
    function boton(bx, by, bw, bh, i, letra) {
      var e = estOp(i), fill = P.papel, stroke = P.borde, col = P.texto, peso = 500, op = e === 'apagada' ? ' opacity="0.42"' : '', ic = '';
      if (e === 'acierto') { fill = V.tinta; stroke = V.tinta; col = V.sobre; peso = 600; }
      if (e === 'fallo') { fill = R.tenue; stroke = R.tinta; col = R.fuerte; peso = 600; }
      var r = v === 'chips' ? bh / 2 : 8 * s, gg = '<path d="' + rr(bx, by, bw, bh, r) + '" fill="' + fill + '" stroke="' + stroke + '" stroke-width="' + n2((e === 'fallo' ? 1.5 : 1.25) * s) + '"/>', tx = bx + 12 * s;
      if (letra) { gg += '<circle cx="' + n2(bx + 18 * s) + '" cy="' + n2(by + bh / 2) + '" r="' + n2(10 * s) + '" fill="none" stroke="' + (e === 'normal' || e === 'apagada' ? P.borde : col) + '" stroke-width="' + n2(1.25 * s) + '"/>' + txt(letra, bx + 18 * s, by + bh / 2 + 11 * s * 0.36, 11 * s, 700, e === 'normal' || e === 'apagada' ? P.suave : col, ' text-anchor="middle"'); tx = bx + 36 * s; }
      if (e === 'acierto') { ic = ICONO.visto(bx + bw - 15 * s, by + bh / 2, 11 * s, col, 1.9 * s); }
      if (e === 'fallo') { ic = ICONO.equis(bx + bw - 15 * s, by + bh / 2, 11 * s, col, 1.9 * s); }
      return '<g' + op + '>' + gg + txt(ops[i], tx, by + bh / 2 + fo * 0.36, fo, peso, col) + ic + '</g>';
    }
    var g = '', B = new Caja();
    if (v === 'grafica') {
      (o.puntos || []).forEach(function (p, i) {
        var e = estOp(i), fill = P.papel, st = P.tinta, col = P.tinta;
        if (e === 'acierto') { fill = V.tinta; st = V.tinta; col = V.sobre; g += '<circle cx="' + n2(p.x) + '" cy="' + n2(p.y) + '" r="' + n2(17 * s) + '" fill="' + V.tinta + '" fill-opacity="0.2"/>'; }
        if (e === 'fallo') { fill = R.tenue; st = R.tinta; col = R.fuerte; }
        g += '<g' + (e === 'apagada' ? ' opacity="0.42"' : '') + '><circle cx="' + n2(p.x) + '" cy="' + n2(p.y) + '" r="' + n2(13.5 * s) + '" fill="' + P.fondo + '" fill-opacity="0.9"/><circle cx="' + n2(p.x) + '" cy="' + n2(p.y) + '" r="' + n2(11 * s) + '" fill="' + fill + '" stroke="' + st + '" stroke-width="' + n2(2 * s) + '"/>' +
          (e === 'acierto' ? ICONO.visto(p.x, p.y, 12 * s, col, 2 * s) : e === 'fallo' ? ICONO.equis(p.x, p.y, 11 * s, col, 2 * s) : txt(p.letra || String.fromCharCode(65 + i), p.x, p.y + 12 * s * 0.36, 12 * s, 700, col, ' text-anchor="middle"')) + '</g>';
        B.p(p.x, p.y, 18 * s);
      });
      var hint = est === 'pregunta' ? 'Toca un punto' : msg, hw = medir(hint || '', 12.5 * s, 600);
      w = Math.ceil(Math.max(qw, hw) + 2 * pad); var h0 = Math.ceil(10 * s + ql.length * 20 * s + 22 * s + 10 * s);
      var C0 = colocar(A, w, h0, o.lado || 'derecha', 18 * s, o.caja), gq = burbuja({ P: P, s: s, x: C0.x, y: C0.y, w: w, h: h0 });
      ql.forEach(function (l, i) { gq += txt(l, C0.x + pad, C0.y + 10 * s + i * 20 * s + 14.5 * s, fq, 600, P.texto); });
      gq += txt(hint || '', C0.x + pad, C0.y + 10 * s + ql.length * 20 * s + 16 * s, 12.5 * s, 600, est === 'acierto' ? V.fuerte : est === 'fallo' ? R.fuerte : P.suave);
      g = aparece(gq, sal(t), C0.x, C0.y, 0, 6 * s, 1) + g; B.r(C0.x, C0.y, w, h0, 8 * s);
      return fin(g, B);
    }
    if (v === 'chips') {
      rowH = 30 * s; var gap = 6 * s, rows = 1;
      ops.forEach(function (op, i) { var bw = medir(op, fo, 600) + 24 * s + (estOp(i) === 'acierto' || estOp(i) === 'fallo' ? 18 * s : 0); if (x > 0 && x + bw > cw) { x = 0; y += rowH + gap; rows++; } lay.push([x, y, bw]); x += bw + gap; });
      w = Math.ceil(Math.max(qw, Math.max.apply(null, lay.map(function (l) { return l[0] + l[2]; }).concat([0]))) + 2 * pad); y += rowH;
    } else {
      rowH = 34 * s; w = Math.ceil(Math.max(qw, (o.ancho || 240) * s - 2 * pad, Math.max.apply(null, ops.map(function (op) { return medir(op, fo, 600) + 68 * s; }))) + 2 * pad);
      ops.forEach(function (op, i) { lay.push([0, i * (rowH + 6 * s), w - 2 * pad]); }); y = ops.length * (rowH + 6 * s) - 6 * s;
    }
    var mh = msg ? 26 * s : 0, h = Math.ceil(10 * s + ql.length * 20 * s + 8 * s + y + mh + 12 * s);
    var C = colocar(A, w, h, o.lado || 'derecha', 18 * s, o.caja), dd = Math.hypot(C.x + w / 2 - A.x, C.y + h / 2 - A.y) || 1;
    var tip = o.caja ? [A.x + (C.x + w / 2 - A.x) / dd * 6 * s, A.y + (C.y + h / 2 - A.y) / dd * 6 * s] : [A.x + C.dx * 6 * s, A.y + C.dy * 6 * s];
    var gb = burbuja({ P: P, s: s, x: C.x, y: C.y, w: w, h: h, pico: { tip: tip, lado: C.cola } }), y0 = C.y + 10 * s;
    ql.forEach(function (l, i) { gb += txt(l, C.x + pad, y0 + i * 20 * s + 14.5 * s, fq, 600, P.texto); });
    var oy = y0 + ql.length * 20 * s + 8 * s;
    lay.forEach(function (l, i) { gb += boton(C.x + pad + l[0], oy + l[1], l[2], rowH, i, v === 'tarjeta' ? String.fromCharCode(65 + i) : null); });
    if (msg) gb += txt(msg, C.x + pad, oy + y + 19 * s, 13 * s, 600, est === 'acierto' ? V.fuerte : R.fuerte);
    g += aparece(gb, sal(t), A.x, A.y, 0, 0, 0.92); B.r(C.x, C.y, w, h, 8 * s).p(A.x, A.y);
    return fin(g, B, { caja: { x: C.x, y: C.y, w: w, h: h } });
  }

  /* ───────── A4 · Pastilla y cajita ─────────
     pastilla { x: borde derecho, y: centro, estado 'reposo'|'nuevo'|'abierta', variante 'marca' (rec.) | 'rotulo' | 'asoma', aviso (texto de 'asoma') }
     cajita   { x: borde derecho, y: centro, ancho, estado 'vacia'|'escribiendo'|'pensando', texto, fase 0→1 (bucle 1,6 s) } */
  function pastilla(o) {
    var b = base(o), s = b.s, P = b.P, v = o.variante || 'marca', est = o.estado || 'reposo', X = o.x, Y = o.y, g = '', B = new Caja();
    var abierta = est === 'abierta', nuevo = est === 'nuevo';
    function tab(w, h) { var x = X - w, y = Y - h / 2, R = 10 * s, d = rr(x, y, w, h, [R, 0, 0, R]); B.r(x, y, w, h, 6 * s);
      return sombraRR(x, y, w, h, R, P, s, 0.7) + '<path d="' + d + '" fill="' + (abierta ? P.tinta : P.papel) + '" stroke="' + (abierta ? P.tinta : P.borde) + '" stroke-width="' + n2(1 * s) + '"/>'; }
    function aviso(x, y) { return '<circle cx="' + n2(x) + '" cy="' + n2(y) + '" r="' + n2(9 * s) + '" fill="' + P.tinta + '" fill-opacity="0.18"/><circle cx="' + n2(x) + '" cy="' + n2(y) + '" r="' + n2(5.5 * s) + '" fill="' + P.tinta + '" stroke="' + P.fondo + '" stroke-width="' + n2(2 * s) + '"/>'; }
    if (v === 'rotulo') {
      var w = 26 * s, h = 82 * s; g += tab(w, h);
      g += '<g transform="translate(' + P2(X - w / 2 + 4.3 * s, Y) + ') rotate(-90)">' + txt('Tutor', 0, 0, 12.5 * s, 600, abierta ? P.sobre : nuevo ? P.fuerte : P.suave, ' text-anchor="middle"') + '</g>';
      if (nuevo) g += aviso(X - w + 3 * s, Y - h / 2 + 3 * s);
    } else if (v === 'asoma' && !abierta) {
      if (nuevo) {
        var tx = o.aviso || 'Te dejé una nota', tw = medir(tx, 12.5 * s, 600), w2 = tw + 46 * s, h2 = 34 * s; g += tab(w2, h2);
        g += ICONO.chispa(X - w2 + 16 * s, Y, 15 * s, P.tinta) + txt(tx, X - w2 + 30 * s, Y + 12.5 * s * 0.36, 12.5 * s, 600, P.texto);
      } else {
        var w1 = 12 * s, h1 = 48 * s; g += tab(w1, h1);
        [-7, 0, 7].forEach(function (d) { g += '<circle cx="' + n2(X - w1 / 2 - 0.5 * s) + '" cy="' + n2(Y + d * s) + '" r="' + n2(1.4 * s) + '" fill="' + P.suave + '"/>'; });
      }
    } else {
      var w3 = 30 * s, h3 = 56 * s; g += tab(w3, h3);
      g += ICONO.chispa(X - w3 / 2 + 1 * s, Y, 17 * s, abierta ? P.sobre : nuevo ? P.tinta : P.suave);
      if (nuevo) g += aviso(X - w3 + 4 * s, Y - h3 / 2 + 4 * s);
    }
    return fin(g, B);
  }
  function garabato(x, y, w, f, P, s) { // el profe «escribe»: lazos que se dibujan y se borran
    var d = '', n = 28, a = 4.2 * s;
    for (var i = 0; i <= n; i++) { var u = i / n, th = u * Math.PI * 2 * 3.2, X = x + u * (w - 2 * a) + a - a * 0.9 * Math.sin(th), Y = y - a * Math.cos(th) * 0.95 + a * 0.2; d += (i ? 'L' : 'M') + P2(X, Y); }
    var e = f < 0.62 ? f / 0.62 : 1, op = f < 0.62 ? 1 : 1 - (f - 0.62) / 0.38;
    return linea(d, P.tinta, 1.75 * s, ' opacity="' + n2(op) + '"' + revela(e));
  }
  function cajita(o) {
    var b = base(o), s = b.s, P = b.P, est = o.estado || 'vacia', w = (o.ancho || 300) * s, h = 44 * s, x = o.x - w, y = o.y - h / 2, f = o.fase || 0, g = '', B = new Caja();
    var foco = est === 'escribiendo', fs = 14 * s, tx = x + 14 * s, ty = y + h / 2 + fs * 0.36, max = w - 64 * s;
    g += sombraRR(x, y, w, h, 12 * s, P, s, 1.6) + '<path d="' + rr(x, y, w, h, 12 * s) + '" fill="' + P.papel + '" stroke="' + (foco ? P.tinta : P.borde) + '" stroke-width="' + n2((foco ? 1.75 : 1) * s) + '"/>';
    var texto = o.texto || '';
    if (est === 'vacia') g += txt('Pregúntale algo de la clase', tx, ty, fs, 400, P.suave);
    else {
      var vis = texto; while (vis.length > 1 && medir(vis + (est === 'pensando' ? '…' : ''), fs, 400) > max) vis = vis.slice(1);
      if (vis !== texto) vis = '…' + vis.slice(1);
      g += txt(vis, tx, ty, fs, 400, est === 'pensando' ? P.suave : P.texto);
      if (foco && (f % 1) < 0.55) { var cx = tx + medir(vis, fs, 400) + 2 * s; g += linea('M' + P2(cx, y + 13 * s) + 'V' + n2(y + h - 13 * s), P.tinta, 1.5 * s); }
    }
    var bx = x + w - 22 * s, by = y + h / 2;
    if (est === 'pensando') g += garabato(x + w - 44 * s, by, 32 * s, f % 1, P, s);
    else g += '<circle cx="' + n2(bx) + '" cy="' + n2(by) + '" r="' + n2(14 * s) + '" fill="' + (foco ? P.tinta : P.borde) + '"' + (foco ? '' : ' fill-opacity="0.6"') + '/>' + ICONO.enviar(bx, by, 14 * s, foco ? P.sobre : P.papel, 1.9 * s);
    B.r(x, y, w, h, 10 * s);
    return fin(g, B);
  }

  /* ───────── B5 · Punto con su valor ─────────
     { ejes, q, p, letra:'E', texto (por defecto «Q = 60 · P = 20»; '' = solo letra), lado 'ne'|'no'|'se'|'so'|'e'|'o', variante 'ficha' (rec.) | 'halo' | 'mira' } */
  var DIRS = { ne: [1, -1], no: [-1, -1], se: [1, 1], so: [-1, 1], e: [1, 0], o: [-1, 0], n: [0, -1], s: [0, 1] };
  function puntoValor(o) {
    var b = base(o), s = b.s, P = b.P, e = sal(b.t), E = ejes(o.ejes), xy = E ? E.px(o.q, o.p) : [o.x, o.y], X = xy[0], Y = xy[1], v = o.variante || 'ficha';
    var D = DIRS[o.lado] || DIRS.ne, dl = Math.hypot(D[0], D[1]), ux = D[0] / dl, uy = D[1] / dl, letra = o.letra == null ? '' : o.letra;
    var valor = o.texto != null ? o.texto : 'Q = ' + fmt(o.q) + ' · P = ' + fmt(o.p), g = '', B = new Caja();
    B.p(X, Y, 10 * s);
    if (v === 'mira') {
      var r = 10 * s; for (var i = 0; i < 4; i++) { var a0 = i * Math.PI / 2 + 0.32, a1 = a0 + Math.PI / 2 - 0.64;
        var d = 'M' + P2(X + r * Math.cos(a0), Y + r * Math.sin(a0)) + 'A' + n2(r) + ',' + n2(r) + ' 0 0 1 ' + P2(X + r * Math.cos(a1), Y + r * Math.sin(a1)); g += conHalo(d, P, 2 * s, s); }
      g += punto(X, Y, 2.75 * s, P, s);
      var tx = (letra ? letra + ' ' : '') + (valor ? '(' + fmt(o.q) + ', ' + fmt(o.p) + ')' : ''), ch = ficha({ s: s, P: P, partes: [[tx, 700]], x: X, y: Y - r - 20 * s, ancla: 'c', estilo: 'papel' });
      g += ch.g; B.r(ch.x, ch.y, ch.w, ch.h, 4 * s);
      return fin(aparece(g, e, X, Y, 0, 0, 0.6), B);
    }
    g += punto(X, Y, 5 * s, P, s);
    if (v === 'halo') {
      var lx = X + ux * (Math.abs(uy) < 0.1 ? 14 : 10) * s, ly = Y + uy * 10 * s, anc = ux < -0.1 ? ' text-anchor="end"' : ux > 0.1 ? '' : ' text-anchor="middle"', fl = 16 * s;
      var by = Math.abs(uy) < 0.1 ? Y - 1 * s : uy < 0 ? ly - (valor ? 15 * s : 0) : ly + fl;
      if (letra) g += txtHalo(letra, lx, by, fl, 700, P.fuerte, P.fondo, 4 * s, anc);
      if (valor) g += txtHalo(valor, lx, by + 15 * s, 12.5 * s, 600, P.fuerte, P.fondo, 3.5 * s, anc);
      var ww = Math.max(medir(letra, fl, 700), medir(valor, 12.5 * s, 600)); B.r(ux < 0 ? lx - ww : lx - (ux > 0.1 ? 0 : ww / 2), by - fl, ww, 34 * s, 4 * s);
      return fin(aparece(g, e, X, Y, 0, 0, 0.6), B);
    }
    var L0 = 7 * s, L1 = 16 * s, ex = X + ux * L1, ey = Y + uy * L1;
    g += conHalo('M' + P2(X + ux * L0, Y + uy * L0) + 'L' + P2(ex, ey), P, 1.75 * s, s);
    var partes = []; if (letra) partes.push([letra, 700]); if (valor) partes.push([valor, 500]);
    if (partes.length) {
      var anc2 = ux < -0.1 ? 'd' : ux > 0.1 ? 'i' : 'c', cyy = ey + (Math.abs(uy) > 0.1 ? uy * 12 * s : 0);
      var c2 = ficha({ s: s, P: P, partes: partes, x: ex + (anc2 === 'i' ? -2 * s : anc2 === 'd' ? 2 * s : 0), y: cyy, ancla: anc2 }); g += c2.g; B.r(c2.x, c2.y, c2.w, c2.h, 4 * s);
    }
    return fin(aparece(g, e, X, Y, 0, 0, 0.6), B);
  }

  /* ───────── B6 · Medida entre dos puntos ─────────
     { ejes, p, q1, q2, texto ('sobran 72'), lado 'arriba'|'abajo', variante 'cota' (rec.) | 'llave' | 'banda' } */
  function medida(o) {
    var b = base(o), s = b.s, P = b.P, t = b.t, E = ejes(o.ejes), A = E.px(o.q1, o.p), C = E.px(o.q2, o.p), y = A[1], x1 = Math.min(A[0], C[0]), x2 = Math.max(A[0], C[0]);
    var v = o.variante || 'cota', sg = o.lado === 'abajo' ? 1 : -1, g = '', B = new Caja(), e1 = sal(tramo(t, 0, 0.6)), e2 = sal(tramo(t, 0.4, 1)), mx = (x1 + x2) / 2;
    var texto = o.texto || fmt(Math.abs(o.q2 - o.q1)), hx = (x2 - x1) / 2 * e1;
    B.p(x1, y, 8 * s).p(x2, y, 8 * s);
    g += punto(x1, y, 3.5 * s, P, s) + punto(x2, y, 3.5 * s, P, s);
    var ly;
    if (v === 'llave') {
      var yb = y + sg * 7 * s, d = 12 * s, q = Math.min(9 * s, (x2 - x1) / 5), a = mx - hx, c = mx + hx, yy = yb + sg * d / 2, yt = yb + sg * d;
      var path = 'M' + P2(a, yb) + 'Q' + P2(a, yy) + ' ' + P2(a + q, yy) + 'L' + P2(mx - q, yy) + 'Q' + P2(mx, yy) + ' ' + P2(mx, yt) + 'Q' + P2(mx, yy) + ' ' + P2(mx + q, yy) + 'L' + P2(c - q, yy) + 'Q' + P2(c, yy) + ' ' + P2(c, yb);
      if (e1 > 0.02) g += conHalo(path, P, 2 * s, s);
      ly = yt + sg * 15 * s;
    } else if (v === 'banda') {
      var bh = 10 * s; g = '<path d="' + rr(mx - hx, y - bh / 2, hx * 2, bh, bh / 2) + '" fill="' + P.tinta + '" fill-opacity="' + n2(P.osc ? 0.4 : 0.28) + '"/>' + g;
      ly = y + sg * 22 * s;
    } else {
      var off = 22 * s, yd = y + sg * off;
      g += linea('M' + P2(x1, y + sg * 6 * s) + 'L' + P2(x1, yd + sg * 6 * s) + 'M' + P2(x2, y + sg * 6 * s) + 'L' + P2(x2, yd + sg * 6 * s), P.tinta, 1.25 * s, ' stroke-opacity="' + n2(0.75 * e1) + '"');
      if (e1 > 0.02) {
        g += conHalo('M' + P2(mx - hx + 3 * s, yd) + 'L' + P2(mx + hx - 3 * s, yd), P, 1.75 * s, s);
        g += punta(mx - hx, yd, -1, 0, 8 * s * e1, 7 * s * e1, P.tinta) + punta(mx + hx, yd, 1, 0, 8 * s * e1, 7 * s * e1, P.tinta);
      }
      ly = yd;
    }
    var ch = ficha({ s: s, P: P, partes: [[texto, 700]], x: mx, y: ly, ancla: 'c' });
    g += aparece(ch.g, e2, mx, ly, 0, sg * -4 * s, 0.9); B.r(ch.x, ch.y, ch.w, ch.h, 4 * s).p(mx, ly, 14 * s);
    return fin(g, B);
  }

  /* ───────── B7 · Guías a los ejes ─────────
     { ejes, q, p, textoQ, textoP, punto (true), variante 'fichas' (rec.) | 'texto' | 'escuadra' } */
  function guias(o) {
    var b = base(o), s = b.s, P = b.P, t = b.t, E = ejes(o.ejes), xy = E.px(o.q, o.p), X = xy[0], Y = xy[1], v = o.variante || 'fichas';
    var tq = o.textoQ != null ? o.textoQ : fmt(o.q), tp = o.textoP != null ? o.textoP : fmt(o.p), e1 = sal(tramo(t, 0, 0.6)), e2 = sal(tramo(t, 0.45, 1));
    var g = '', B = new Caja(), yA = E.y0, xA = E.x0, vy = Y + (yA - Y) * e1, hx = X + (xA - X) * e1;
    B.p(X, Y, 8 * s).p(X, yA, 14 * s).p(xA, Y, 14 * s);
    if (v === 'escuadra') {
      g += linea('M' + P2(X, Y) + 'L' + P2(X, vy) + 'M' + P2(X, Y) + 'L' + P2(hx, Y), P.tinta, 1.25 * s, ' stroke-opacity="0.55"');
      g += linea('M' + P2(xA, yA) + 'L' + P2(xA + (X - xA) * e1, yA) + 'M' + P2(xA, yA) + 'L' + P2(xA, yA + (Y - yA) * e1), P.tinta, 4 * s, ' stroke-opacity="0.85"');
    } else {
      var da = ' stroke-dasharray="' + n2(4 * s) + ' ' + n2(3.5 * s) + '"';
      g += linea('M' + P2(X, Y) + 'L' + P2(X, vy) + 'M' + P2(X, Y) + 'L' + P2(hx, Y), P.fondo, 4.5 * s, ' stroke-opacity="0.7"') + linea('M' + P2(X, Y) + 'L' + P2(X, vy) + 'M' + P2(X, Y) + 'L' + P2(hx, Y), P.tinta, 1.5 * s, da);
    }
    if (o.punto !== false) g += punto(X, Y, 4.5 * s, P, s);
    var lab = '';
    if (v === 'fichas') {
      var c1 = ficha({ s: s, P: P, partes: [[tq, 700]], x: X, y: yA + 13 * s, ancla: 'c', alto: 20, px: 12, pad: 6, r: 5, sombra: false });
      var c2 = ficha({ s: s, P: P, partes: [[tp, 700]], x: xA - 4 * s, y: Y, ancla: 'd', alto: 20, px: 12, pad: 6, r: 5, sombra: false });
      lab = c1.g + c2.g; B.r(c1.x, c1.y, c1.w, c1.h, 3 * s).r(c2.x, c2.y, c2.w, c2.h, 3 * s);
    } else {
      lab = linea('M' + P2(X, yA - 4 * s) + 'V' + n2(yA + 4 * s) + 'M' + P2(xA - 4 * s, Y) + 'H' + n2(xA + 4 * s), P.tinta, 2 * s) +
        txtHalo(tq, X, yA + 18 * s, 13 * s, 700, P.fuerte, P.fondo, 4 * s, ' text-anchor="middle"') + txtHalo(tp, xA - 8 * s, Y + 4.5 * s, 13 * s, 700, P.fuerte, P.fondo, 4 * s, ' text-anchor="end"');
      B.p(X, yA + 22 * s, 16 * s).p(xA - 30 * s, Y, 10 * s);
    }
    g += aparece(lab, e2, X, Y, 0, 0, 1);
    return fin(g, B);
  }

  /* ───────── B8 · Área sombreada ─────────
     { ejes, rect:{q:[a,b], p:[a,b]} | poli:[[q,p],…], texto, detalle, en:[q,p] (centro de la etiqueta), variante 'tenue' (rec.) | 'rayado' | 'contorno' } */
  function area(o) {
    var b = base(o), s = b.s, P = b.P, t = b.t, E = ejes(o.ejes), v = o.variante || 'tenue', pts;
    if (o.rect) pts = [[o.rect.q[0], o.rect.p[0]], [o.rect.q[1], o.rect.p[0]], [o.rect.q[1], o.rect.p[1]], [o.rect.q[0], o.rect.p[1]]];
    else pts = o.poli || [];
    var px = pts.map(function (p) { return E.px(p[0], p[1]); }), B = new Caja(), g = '', e1 = sal(tramo(t, 0, 0.6)), e2 = sal(tramo(t, 0.4, 1));
    px.forEach(function (p) { B.p(p[0], p[1], 3 * s); });
    var d = 'M' + px.map(function (p) { return P2(p[0], p[1]); }).join('L') + 'Z';
    var cx = 0, cy = 0; px.forEach(function (p) { cx += p[0]; cy += p[1]; }); cx /= px.length || 1; cy /= px.length || 1;
    if (o.en) { var q = E.px(o.en[0], o.en[1]); cx = q[0]; cy = q[1]; }
    if (v === 'rayado') {
      var id = o.id || uid('r'), x0 = B.a, x1 = B.c, y0 = B.b, y1 = B.d, sp = 7 * s, hl = '';
      for (var k = x0 - (y1 - y0); k < x1; k += sp) hl += 'M' + P2(k, y1) + 'L' + P2(k + (y1 - y0), y0);
      g += '<defs><clipPath id="' + id + '"><path d="' + d + '"/></clipPath></defs><g clip-path="url(#' + id + ')" opacity="' + n2(e1) + '">' + linea(hl, P.tinta, 1.25 * s, ' stroke-opacity="0.6"') + '</g>' + linea(d, P.tinta, 1.5 * s, revela(e1));
    } else if (v === 'contorno') {
      g += linea(d, P.fondo, 5 * s, ' stroke-opacity="0.8"' + (e1 < 1 ? ' opacity="' + n2(e1) + '"' : '')) + linea(d, P.tinta, 2 * s, ' stroke-dasharray="' + n2(6 * s) + ' ' + n2(4 * s) + '"' + (e1 < 1 ? ' opacity="' + n2(e1) + '"' : ''));
    } else {
      g += '<path d="' + d + '" fill="' + P.tinta + '" fill-opacity="' + n2(P.relleno * e1) + '"/>' + linea(d, P.tinta, 1.5 * s, ' stroke-opacity="0.75"' + revela(e1));
    }
    var lab = '';
    if (v === 'tenue') {
      lab = txt(o.texto || '', cx, cy - (o.detalle ? 3 * s : -5 * s), 13.5 * s, 700, P.fuerte, ' text-anchor="middle"') + (o.detalle ? txt(o.detalle, cx, cy + 15 * s, 12.5 * s, 600, P.texto, ' text-anchor="middle"') : '');
    } else {
      var partes = [[o.texto || '', 700]]; if (o.detalle) partes.push([o.detalle, 500]);
      var ch = ficha({ s: s, P: P, partes: partes, x: cx, y: cy, ancla: 'c', estilo: v === 'contorno' ? 'papel' : 'solido' }); lab = ch.g;
    }
    g += aparece(lab, e2, cx, cy, 0, 4 * s, 0.94);
    return fin(g, B);
  }

  /* ───────── B9 · Desplazamiento de una curva ─────────
     { ejes, de:[[q,p],[q,p]], a:[[q,p],[q,p]], nombre:'D′', nota ('sube la demanda'), variante 'flechas' (rec.) | 'fantasma' | 'barrido', t 0→1 (1,4 s) } */
  function recortar(a, c, R) { // Liang–Barsky
    var x0 = a[0], y0 = a[1], dx = c[0] - x0, dy = c[1] - y0, u0 = 0, u1 = 1, p = [-dx, dx, -dy, dy], q = [x0 - R.x0, R.x1 - x0, y0 - R.y0, R.y1 - y0];
    for (var i = 0; i < 4; i++) { if (p[i] === 0) { if (q[i] < 0) return null; } else { var r = q[i] / p[i]; if (p[i] < 0) { if (r > u1) return null; if (r > u0) u0 = r; } else { if (r < u0) return null; if (r < u1) u1 = r; } } }
    return [[x0 + dx * u0, y0 + dy * u0], [x0 + dx * u1, y0 + dy * u1], u0, u1];
  }
  function desplazar(o) {
    var b = base(o), s = b.s, P = b.P, t = b.t, E = ejes(o.ejes), v = o.variante || 'flechas', g = '', B = new Caja();
    var R = { x0: Math.min(E.x0, E.x1), x1: Math.max(E.x0, E.x1), y0: Math.min(E.y0, E.y1), y1: Math.max(E.y0, E.y1) };
    var de = o.de.map(function (p) { return E.px(p[0], p[1]); }), a = o.a.map(function (p) { return E.px(p[0], p[1]); });
    var e0 = sal(tramo(t, 0, 0.25)), k = suave(tramo(t, 0.2, 0.75)), e3 = sal(tramo(t, 0.7, 1));
    var mid = function (k2) { return [[de[0][0] + (a[0][0] - de[0][0]) * k2, de[0][1] + (a[0][1] - de[0][1]) * k2], [de[1][0] + (a[1][0] - de[1][0]) * k2, de[1][1] + (a[1][1] - de[1][1]) * k2]]; };
    var seg = function (L) { var c = recortar(L[0], L[1], R); return c ? 'M' + P2(c[0][0], c[0][1]) + 'L' + P2(c[1][0], c[1][1]) : ''; };
    var dOld = seg(de);
    B.r(R.x0, R.y0, R.x1 - R.x0, R.y1 - R.y0);
    if (v === 'fantasma') g += linea(dOld, P.tinta, 9 * s, ' stroke-opacity="' + n2(0.16 * e0) + '"');
    else if (v === 'barrido') { [0.25, 0.5, 0.75].forEach(function (q, i) { if (k > q) g += linea(seg(mid(q)), P.tinta, 2 * s, ' stroke-opacity="' + n2(0.12 + 0.08 * i) + '"'); }); g += linea(dOld, P.tinta, 2 * s, ' stroke-opacity="' + n2(0.4 * e0) + '" stroke-dasharray="' + n2(6 * s) + ' ' + n2(5 * s) + '"'); }
    else g += linea(dOld, P.tinta, 2 * s, ' stroke-opacity="' + n2(0.45 * e0) + '" stroke-dasharray="' + n2(6 * s) + ' ' + n2(5 * s) + '"');
    if (t > 0.2) { var dNew = seg(mid(k)); g += conHalo(dNew, P, 3 * s, s); }
    if (e3 > 0) {
      var nw = recortar(a[0], a[1], R), sx = a[0][0] - de[0][0], sy = a[0][1] - de[0][1], sl = Math.hypot(sx, sy) || 1, ux = sx / sl, uy = sy / sl;
      if (v === 'flechas') {
        [0.32, 0.58].forEach(function (u) {
          var c = recortar(de[0], de[1], R); if (!c) return; var uu = c[2] + (c[3] - c[2]) * u, p0 = [de[0][0] + (de[1][0] - de[0][0]) * uu, de[0][1] + (de[1][1] - de[0][1]) * uu];
          var L = (sl - 14 * s) * e3; if (L < 4 * s) return; var a0 = [p0[0] + ux * 6 * s, p0[1] + uy * 6 * s], a1 = [a0[0] + ux * L, a0[1] + uy * L];
          g += conHalo('M' + P2(a0[0], a0[1]) + 'L' + P2(a1[0] - ux * 5 * s, a1[1] - uy * 5 * s), P, 2 * s, s) + punta(a1[0], a1[1], ux, uy, 8 * s, 7.5 * s, P.tinta);
        });
      } else if (v === 'fantasma') {
        var c2 = recortar(de[0], de[1], R); if (c2) {
          var m0 = [(c2[0][0] + c2[1][0]) / 2, (c2[0][1] + c2[1][1]) / 2], m1 = [m0[0] + sx, m0[1] + sy];
          var ha = mano.flecha({ x1: m0[0] - uy * 20 * s + ux * 6 * s, y1: m0[1] + ux * 20 * s + uy * 6 * s, x2: m1[0] - uy * 14 * s - ux * 8 * s, y2: m1[1] + ux * 14 * s - uy * 8 * s, curva: -0.35, tema: o.tema, escala: s, color: o.color, fondo: o.fondo, t: e3 });
          g += ha.g;
          var top = recortar(a[0], a[1], R); if (o.nota && top) g += mano.nota({ x: top[0][0] + 26 * s, y: top[0][1] + 14 * s, texto: o.nota, tam: 15, tema: o.tema, escala: s, color: o.color, fondo: o.fondo, t: e3 }).g;
        }
      }
      if (nw && o.nombre) { var ex = nw[1]; g += aparece(txtHalo(o.nombre, ex[0] + 6 * s, ex[1] + 4 * s, 14 * s, 700, P.fuerte, P.fondo, 4 * s), e3, ex[0], ex[1], 0, 0, 0.8); B.p(ex[0] + 26 * s, ex[1], 10 * s); }
    }
    return fin(g, B);
  }

  /* ───────── B10 · Recorrido animado ─────────
     { ejes, camino:[[q,p],…], fase 0→1 (ciclo de 4 s), variante 'guias' (rec.) | 'estela' | 'saltos', etiqueta: fn(q,p)→texto } */
  var RECORRIDO = { aparece: [0, 0.1], viaja: [0.1, 0.7], quieto: [0.7, 0.9], sale: [0.9, 1] };
  function recorrido(o) {
    var b = base(o), s = b.s, P = b.P, E = ejes(o.ejes), v = o.variante || 'guias', f = ((o.fase || 0) % 1 + 1) % 1, g = '', B = new Caja();
    var u = suave(tramo(f, 0.1, 0.7)), op = f < 0.1 ? f / 0.1 : f > 0.9 ? 1 - (f - 0.9) / 0.1 : 1;
    var cam = (o.camino || []).map(function (p) { return E.px(p[0], p[1]); }), seg = [], L = 0;
    if (v === 'saltos' && cam.length >= 2) {
      var A = cam[0], C = cam[cam.length - 1], mx = (A[0] + C[0]) / 2, my = (A[1] + C[1]) / 2, dx = C[0] - A[0], dy = C[1] - A[1], dl = Math.hypot(dx, dy) || 1, k = 0.28 * dl;
      var Q = [mx + dy / dl * k * (dx > 0 ? -1 : 1), my - Math.abs(dx / dl) * k], bz = function (w) { return [(1 - w) * (1 - w) * A[0] + 2 * (1 - w) * w * Q[0] + w * w * C[0], (1 - w) * (1 - w) * A[1] + 2 * (1 - w) * w * Q[1] + w * w * C[1]]; };
      g += '<circle cx="' + n2(A[0]) + '" cy="' + n2(A[1]) + '" r="' + n2(5 * s) + '" fill="none" stroke="' + P.tinta + '" stroke-width="' + n2(1.5 * s) + '" stroke-dasharray="' + n2(2.5 * s) + ' ' + n2(2 * s) + '"/>';
      g += linea('M' + P2(A[0], A[1]) + 'Q' + P2(Q[0], Q[1]) + ' ' + P2(C[0], C[1]), P.tinta, 1.5 * s, ' stroke-opacity="0.5" stroke-dasharray="' + n2(3 * s) + ' ' + n2(4 * s) + '"');
      var pos = bz(u); g += '<g opacity="' + n2(op) + '">' + punto(pos[0], pos[1], 6 * s, P, s) + '</g>';
      B.p(A[0], A[1], 10 * s).p(C[0], C[1], 10 * s).p(Q[0], Q[1], 10 * s);
      return fin(g, B);
    }
    for (var i = 0; i < cam.length - 1; i++) { var l = Math.hypot(cam[i + 1][0] - cam[i][0], cam[i + 1][1] - cam[i][1]); seg.push([L, l]); L += l; }
    var en = function (w) { var d = lim(w) * L; for (var j = 0; j < seg.length; j++) if (d <= seg[j][0] + seg[j][1] + 1e-6 || j === seg.length - 1) { var ff = seg[j][1] ? (d - seg[j][0]) / seg[j][1] : 0; return [cam[j][0] + (cam[j + 1][0] - cam[j][0]) * ff, cam[j][1] + (cam[j + 1][1] - cam[j][1]) * ff]; } return cam[0] || [0, 0]; };
    cam.forEach(function (p) { B.p(p[0], p[1], 12 * s); });
    var p = en(u), val = E.valor(p[0], p[1]), gg = '';
    if (v === 'estela') {
      for (var k2 = 0; k2 < 8; k2++) { var w0 = u - 0.16 * (k2 + 1) / 8, w1 = u - 0.16 * k2 / 8; if (w1 <= 0) break; var a0 = en(Math.max(0, w0)), a1 = en(w1);
        gg += linea('M' + P2(a0[0], a0[1]) + 'L' + P2(a1[0], a1[1]), P.tinta, (5 - k2 * 0.45) * s, ' stroke-opacity="' + n2(0.5 * (1 - k2 / 8)) + '"'); }
      gg += punto(p[0], p[1], 6 * s, P, s);
      var et = o.etiqueta ? o.etiqueta(val[0], val[1]) : 'P = ' + Math.round(val[1]), ch = ficha({ s: s, P: P, partes: [[et, 700]], x: p[0] + 12 * s, y: p[1] - 16 * s, ancla: 'i' }); gg += ch.g;
    } else {
      gg += guias({ ejes: E, q: val[0], p: val[1], textoQ: String(Math.round(val[0])), textoP: String(Math.round(val[1])), tema: o.tema, escala: s, color: o.color, fondo: o.fondo, punto: false }).g + punto(p[0], p[1], 6 * s, P, s);
      B.p(E.x0 - 30 * s, E.y0 + 24 * s);
    }
    g += '<g opacity="' + n2(op) + '">' + gg + '</g>';
    return fin(g, B);
  }

  /* ───────── C11–12 · Trazo a mano alzada ───────── */
  function azar(sem) { var a = (sem || 7) * 9301 + 49297; return function () { a = (a * 9301 + 49297) % 233280; return a / 233280; }; }
  function curvaSuave(pts) {
    if (pts.length < 2) return '';
    var d = 'M' + P2(pts[0][0], pts[0][1]);
    for (var i = 0; i < pts.length - 1; i++) {
      var p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
      d += 'C' + P2(p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6) + ' ' + P2(p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6) + ' ' + P2(p2[0], p2[1]);
    }
    return d;
  }
  function ondula(R) { var f1 = R() * 6.28, f2 = R() * 6.28; return function (u) { return Math.sin(6.28 * u * 2.3 + f1) * 0.6 + Math.sin(6.28 * u * 5.1 + f2) * 0.4; }; }
  function trazoMano(d, P, s, e, sw) { sw = (sw || 2.75) * s; return linea(d, P.fondo, sw + 3 * s, ' stroke-opacity="0.85"' + revela(e)) + linea(d, P.tinta, sw, revela(e)); }
  function lineaMano(x1, y1, x2, y2, R, s, amp, comba) {
    var W = ondula(R), pts = [], n = Math.max(5, Math.round(Math.hypot(x2 - x1, y2 - y1) / (28 * s))), dx = x2 - x1, dy = y2 - y1, dl = Math.hypot(dx, dy) || 1, nx = -dy / dl, ny = dx / dl;
    for (var i = 0; i <= n; i++) { var u = i / n, o = W(u) * amp * s + Math.sin(Math.PI * u) * (comba || 0) * s; pts.push([x1 + dx * u + nx * o, y1 + dy * u + ny * o]); }
    return curvaSuave(pts);
  }
  var mano = {
    /* rodear { x,y,w,h, forma 'auto' (rec.) | 'elipse' | 'lazo' | 'corchetes' | 'doble', semilla, t } · auto: w/h ≤ 2,2 → elipse; si no → lazo */
    rodear: function (o) {
      var b = base(o), s = b.s, P = b.P, t = b.t, R = azar(o.semilla), x = o.x, y = o.y, w = o.w, h = o.h, forma = o.forma || 'auto', g = '', B = new Caja();
      if (forma === 'auto') forma = w / h <= 2.2 ? 'elipse' : 'lazo';
      if (forma === 'elipse') {
        var cx = x + w / 2, cy = y + h / 2, rx = w / 2 * 1.32 + 6 * s, ry = h / 2 * 1.32 + 6 * s, pts = [], a0 = -Math.PI * 0.68 + (R() - 0.5) * 0.3, tot = Math.PI * 2 + 0.5, W = ondula(R), rot = (R() - 0.5) * 0.08;
        for (var i = 0; i <= 56; i++) { var u = i / 56, a = a0 + tot * u, k = 1 + 0.03 * W(u) + 0.07 * u, X = rx * k * Math.cos(a), Y = ry * k * Math.sin(a); pts.push([cx + X * Math.cos(rot) - Y * Math.sin(rot), cy + X * Math.sin(rot) + Y * Math.cos(rot)]); }
        g = trazoMano(curvaSuave(pts), P, s, sal(t)); B.p(cx - rx * 1.1, cy - ry * 1.1).p(cx + rx * 1.1, cy + ry * 1.1);
      } else if (forma === 'lazo') {
        var X0 = x - 8 * s, Y0 = y - 6 * s, W0 = w + 16 * s, H0 = h + 12 * s, r = Math.min(H0 / 2, 16 * s), segs = [], Lt = 0;
        var add = function (q) { q.L0 = Lt; Lt += q.len; segs.push(q); };
        var lin = function (a, b2, c, d, nx, ny) { add({ l: 1, a: a, b: b2, c: c, d: d, nx: nx, ny: ny, len: Math.hypot(c - a, d - b2) }); };
        var arc = function (cx2, cy2, a1) { add({ l: 0, cx: cx2, cy: cy2, a1: a1, len: Math.PI * r / 2 }); };
        lin(X0 + r, Y0, X0 + W0 - r, Y0, 0, -1); arc(X0 + W0 - r, Y0 + r, -Math.PI / 2); lin(X0 + W0, Y0 + r, X0 + W0, Y0 + H0 - r, 1, 0); arc(X0 + W0 - r, Y0 + H0 - r, 0);
        lin(X0 + W0 - r, Y0 + H0, X0 + r, Y0 + H0, 0, 1); arc(X0 + r, Y0 + H0 - r, Math.PI / 2); lin(X0, Y0 + H0 - r, X0, Y0 + r, -1, 0); arc(X0 + r, Y0 + r, Math.PI);
        var en = function (d) { d = ((d % Lt) + Lt) % Lt; for (var j = 0; j < segs.length; j++) { var q = segs[j]; if (d <= q.L0 + q.len + 1e-6) { var f = (d - q.L0) / (q.len || 1);
          if (q.l) return [q.a + (q.c - q.a) * f, q.b + (q.d - q.b) * f, q.nx, q.ny]; var an = q.a1 + f * Math.PI / 2; return [q.cx + r * Math.cos(an), q.cy + r * Math.sin(an), Math.cos(an), Math.sin(an)]; } } return en(0); };
        var d0 = (W0 - 2 * r) * (0.1 + R() * 0.08), tot2 = Lt * 1.1, n = Math.max(48, Math.round(tot2 / (10 * s))), Wv = ondula(R), pl = [];
        for (var i2 = 0; i2 <= n; i2++) { var u2 = i2 / n, p = en(d0 + tot2 * u2), off = Wv(u2) * 1.3 * s + u2 * 3 * s; pl.push([p[0] + p[2] * off, p[1] + p[3] * off]); }
        g = trazoMano(curvaSuave(pl), P, s, sal(t)); B.r(X0, Y0, W0, H0, 10 * s);
      } else if (forma === 'corchetes') {
        var pp = 5 * s, tk = Math.min(12 * s, w * 0.2), j = function () { return (R() - 0.5) * 1.6 * s; }, a = x - 7 * s, c = x + w + 7 * s, y0 = y - pp, y1 = y + h + pp;
        var izq = 'M' + P2(a + tk + j(), y0 + j()) + 'C' + P2(a + 3 * s, y0) + ' ' + P2(a, y0 + 2 * s) + ' ' + P2(a + j() * 0.5, y0 + 7 * s) + 'L' + P2(a + j() * 0.5, y1 - 7 * s) + 'C' + P2(a, y1 - 2 * s) + ' ' + P2(a + 3 * s, y1) + ' ' + P2(a + tk + j(), y1 + j());
        var der = 'M' + P2(c - tk + j(), y0 + j()) + 'C' + P2(c - 3 * s, y0) + ' ' + P2(c, y0 + 2 * s) + ' ' + P2(c + j() * 0.5, y0 + 7 * s) + 'L' + P2(c + j() * 0.5, y1 - 7 * s) + 'C' + P2(c, y1 - 2 * s) + ' ' + P2(c - 3 * s, y1) + ' ' + P2(c - tk + j(), y1 + j());
        g = trazoMano(izq, P, s, sal(tramo(t, 0, 0.55))) + trazoMano(der, P, s, sal(tramo(t, 0.45, 1))); B.r(a, y0, c - a, y1 - y0, 8 * s);
      } else {
        var yA = y + h + 5 * s, yB = yA + 5.5 * s;
        g = trazoMano(lineaMano(x - 3 * s, yA, x + w + 4 * s, yA - 1.5 * s, R, s, 1.1, -1.5), P, s, sal(tramo(t, 0, 0.6))) + trazoMano(lineaMano(x + w * 0.06, yB, x + w * 0.95, yB + 0.5 * s, R, s, 1.1, -1), P, s, sal(tramo(t, 0.5, 1)));
        B.r(x - 6 * s, yA - 6 * s, w + 14 * s, 18 * s);
      }
      return fin(g, B, { forma: forma });
    },
    subrayar: function (o) { var b = base(o), s = b.s, R = azar(o.semilla), y = o.y + 3 * s, d = lineaMano(o.x1 - 2 * s, y, o.x2 + 3 * s, y - 1.5 * s, R, s, 1, -1.5); return fin(trazoMano(d, b.P, s, sal(b.t)), new Caja().p(o.x1, y, 8 * s).p(o.x2, y, 8 * s)); },
    tachar: function (o) {
      var b = base(o), s = b.s, R = azar(o.semilla), g;
      if (o.tipo === 'x') g = trazoMano(lineaMano(o.x, o.y, o.x + o.w, o.y + o.h, R, s, 0.8), b.P, s, sal(tramo(b.t, 0, 0.55))) + trazoMano(lineaMano(o.x + o.w, o.y, o.x, o.y + o.h, R, s, 0.8), b.P, s, sal(tramo(b.t, 0.45, 1)));
      else g = trazoMano(lineaMano(o.x - 4 * s, o.y + o.h * 0.6, o.x + o.w + 4 * s, o.y + o.h * 0.42, R, s, 0.9), b.P, s, sal(b.t));
      return fin(g, new Caja().r(o.x, o.y, o.w, o.h, 8 * s));
    },
    visto: function (o) { var b = base(o), s = b.s, T = (o.tam || 22) * s, x = o.x, y = o.y; var d = 'M' + P2(x, y + T * 0.52) + 'Q' + P2(x + T * 0.2, y + T * 0.66) + ' ' + P2(x + T * 0.36, y + T) + 'Q' + P2(x + T * 0.52, y + T * 0.4) + ' ' + P2(x + T * 1.05, y - T * 0.05); return fin(trazoMano(d, b.P, s, sal(b.t), 3), new Caja().r(x, y - T * 0.1, T * 1.1, T * 1.1, 6 * s)); },
    /* flecha { x1,y1 → x2,y2, curva (±0,1…0,4) } — punta abierta de dos trazos */
    flecha: function (o) {
      var b = base(o), s = b.s, P = b.P, t = b.t, R = azar(o.semilla), dx = o.x2 - o.x1, dy = o.y2 - o.y1, dl = Math.hypot(dx, dy) || 1, k = (o.curva == null ? 0.2 : o.curva) * dl;
      var cx = (o.x1 + o.x2) / 2 - dy / dl * k, cy = (o.y1 + o.y2) / 2 + dx / dl * k, pts = [], W = ondula(R);
      for (var i = 0; i <= 10; i++) { var u = i / 10, X = (1 - u) * (1 - u) * o.x1 + 2 * (1 - u) * u * cx + u * u * o.x2, Y = (1 - u) * (1 - u) * o.y1 + 2 * (1 - u) * u * cy + u * u * o.y2, w = W(u) * 0.9 * s * Math.sin(Math.PI * u); pts.push([X - dy / dl * w, Y + dx / dl * w]); }
      var tx = o.x2 - cx, ty = o.y2 - cy, tl = Math.hypot(tx, ty) || 1, ux = tx / tl, uy = ty / tl, hl = 12 * s, an = 0.5;
      var h1 = [o.x2 - hl * (ux * Math.cos(an) - uy * Math.sin(an)), o.y2 - hl * (uy * Math.cos(an) + ux * Math.sin(an))], h2 = [o.x2 - hl * (ux * Math.cos(-an) - uy * Math.sin(-an)), o.y2 - hl * (uy * Math.cos(-an) + ux * Math.sin(-an))];
      var g = trazoMano(curvaSuave(pts), P, s, sal(tramo(t, 0, 0.75)), 2.5) + trazoMano('M' + P2(h1[0], h1[1]) + 'L' + P2(o.x2, o.y2) + 'L' + P2(h2[0], h2[1]), P, s, sal(tramo(t, 0.7, 1)), 2.5);
      return fin(g, new Caja().p(o.x1, o.y1, 8 * s).p(o.x2, o.y2, 14 * s).p(cx, cy, 8 * s));
    },
    /* nota { x, y (línea base), texto (1–5 palabras), tam 16 (14–18), letra 'print' (rec.) | 'ink' | 'ui', ancla 'i'|'c'|'d', giro (−2°) } */
    nota: function (o) {
      var b = base(o), s = b.s, P = b.P, e = sal(b.t), fam = LETRAS[o.letra || 'print'] || LETRAS.print, px = (o.tam || 16) * s, peso = o.letra === 'ui' ? 600 : 400;
      var w = medir(o.texto, px, peso, fam), x = o.x - (o.ancla === 'd' ? w : o.ancla === 'c' ? w / 2 : 0), giro = o.giro == null ? -2 : o.giro, id = o.id || uid('n');
      var tg = txtHalo(o.texto, x, o.y, px, peso, P.fuerte, P.fondo, 4 * s, o.letra === 'ui' ? '' : ' letter-spacing="0.2"', fam);
      var g = '<g transform="rotate(' + giro + ' ' + P2(x, o.y) + ')">' + (e < 0.999 ? '<defs><clipPath id="' + id + '"><rect x="' + n2(x - 6 * s) + '" y="' + n2(o.y - px * 1.6) + '" width="' + n2((w + 12 * s) * e) + '" height="' + n2(px * 2.4) + '"/></clipPath></defs><g clip-path="url(#' + id + ')">' + tg + '</g>' : tg) + '</g>';
      return fin(g, new Caja().r(x, o.y - px * 1.2, w, px * 1.6, 6 * s));
    }
  };

  /* ───────── D13 · Notita del deslizador ─────────
     { riel:{x1,x2,y}, min, max, valor, paradas:[…], parada (índice de la actual), moviendo, etiqueta 'P', variante 'cursor' (rec.) | 'rotulo' | 'riel' } */
  function deslizador(o) {
    var b = base(o), s = b.s, P = b.P, Rl = o.riel, v = o.variante || 'cursor', g = '', B = new Caja();
    var xv = function (val) { return Rl.x1 + (val - o.min) / (o.max - o.min) * (Rl.x2 - Rl.x1); }, X = xv(o.valor), Y = Rl.y, k = o.parada == null ? -1 : o.parada;
    B.p(Rl.x1, Y, 10 * s).p(Rl.x2, Y, 10 * s);
    if (v === 'riel') g += linea('M' + P2(Rl.x1, Y) + 'H' + n2(X), P.tinta, 5 * s, ' stroke-opacity="0.9"');
    (o.paradas || []).forEach(function (pv, i) {
      var x = xv(pv), hecha = i < k || (i === k && !o.moviendo);
      if (v === 'riel') {
        var yb = Y - 20 * s; g += '<circle cx="' + n2(x) + '" cy="' + n2(yb) + '" r="' + n2(9 * s) + '" fill="' + (hecha ? P.tinta : P.papel) + '" stroke="' + P.tinta + '" stroke-width="' + n2(1.5 * s) + '"/>' + txt(String(i + 1), x, yb + 11 * s * 0.36, 11 * s, 700, hecha ? P.sobre : P.fuerte, ' text-anchor="middle"');
        g += linea('M' + P2(x, yb + 9 * s) + 'V' + n2(Y - 5 * s), P.tinta, 1.25 * s, ' stroke-opacity="0.6"'); B.p(x, yb, 12 * s);
      } else {
        g += '<circle cx="' + n2(x) + '" cy="' + n2(Y) + '" r="' + n2(4 * s) + '" fill="' + (hecha ? P.tinta : P.papel) + '" stroke="' + P.tinta + '" stroke-width="' + n2(1.5 * s) + '"/>';
      }
      g += txtHalo(fmt(pv), x, Y + 23 * s, 11.5 * s, 700, P.fuerte, P.fondo, 3 * s, ' text-anchor="middle"'); B.p(x, Y + 26 * s, 10 * s);
    });
    g += '<circle cx="' + n2(X) + '" cy="' + n2(Y) + '" r="' + n2(13 * s) + '" fill="none" stroke="' + P.tinta + '" stroke-width="' + n2(2.5 * s) + '"/>';
    if (v !== 'riel') {
      var vt = (o.etiqueta || 'P') + ' = ' + fmt(Math.round(o.valor)), ch = ficha({ s: s, P: P, partes: v === 'rotulo' ? [['✦ Tutor', 500], [vt, 700]] : [[vt, 700]], x: X, y: Y - 34 * s, ancla: 'c', alto: 24 });
      g += ch.g + '<path d="M' + P2(X - 5 * s, ch.y + ch.h - 0.5) + 'L' + P2(X, ch.y + ch.h + 5 * s) + 'L' + P2(X + 5 * s, ch.y + ch.h - 0.5) + 'Z" fill="' + P.tinta + '"/>';
      B.r(ch.x, ch.y, ch.w, ch.h, 4 * s);
    }
    if (v === 'cursor') { g += cursor(X + 8 * s, Y - 2 * s, P, s, 'Tutor'); B.p(X + 64 * s, Y + 40 * s); }
    return fin(g, B);
  }

  /* ───────── D14 · Botón pulsado por el tutor ─────────
     { boton:{x,y,w,h,r}, t 0→1 (900 ms), variante 'onda' (rec.) | 'contorno' | 'sello' } */
  function pulsado(o) {
    var b = base(o), s = b.s, P = b.P, t = b.t, Bt = o.boton, v = o.variante || 'onda', g = '', B = new Caja(), r = (Bt.r != null ? Bt.r : 8) * s;
    var cx = Bt.x + Bt.w * 0.62, cy = Bt.y + Bt.h * 0.58;
    B.r(Bt.x, Bt.y, Bt.w, Bt.h, 10 * s);
    if (v === 'contorno') {
      var a = t < 1 ? Math.max(0, Math.sin(Math.PI * ((t * 2) % 1))) * (t < 0.5 ? 1 : 0.6) : 0, k = 3 * s;
      g += '<path d="' + rr(Bt.x - k, Bt.y - k, Bt.w + 2 * k, Bt.h + 2 * k, r + k) + '" fill="none" stroke="' + P.tinta + '" stroke-width="' + n2(2.5 * s) + '" stroke-opacity="' + n2(t >= 1 ? 0.9 : 0.35 + 0.65 * a) + '"/>';
      var ch = ficha({ s: s, P: P, partes: [['Tutor', 700]], x: Bt.x + Bt.w + 4 * s, y: Bt.y - 6 * s, ancla: 'c', alto: 18, px: 11, pad: 6 }); g += ch.g; B.r(ch.x, ch.y, ch.w, ch.h);
    } else if (v === 'sello') {
      var e = sal(tramo(t, 0.3, 1));
      g += '<path d="' + rr(Bt.x - 3 * s, Bt.y - 3 * s, Bt.w + 6 * s, Bt.h + 6 * s, r + 3 * s) + '" fill="none" stroke="' + P.tinta + '" stroke-width="' + n2(2 * s) + '" stroke-opacity="' + n2(0.9 * e) + '"/>';
      g += mano.flecha({ x1: Bt.x + Bt.w + 52 * s, y1: Bt.y - 16 * s, x2: Bt.x + Bt.w + 6 * s, y2: Bt.y + 6 * s, curva: 0.3, tema: o.tema, escala: s, color: o.color, fondo: o.fondo, t: e }).g;
      g += mano.nota({ x: Bt.x + Bt.w + 30 * s, y: Bt.y - 22 * s, texto: 'lo pulsé yo', tam: 15, tema: o.tema, escala: s, color: o.color, fondo: o.fondo, t: e }).g; B.p(Bt.x + Bt.w + 130 * s, Bt.y - 40 * s);
    } else {
      var e1 = sal(tramo(t, 0, 0.4)), pr = t > 0.38 && t < 0.52 ? 0.88 : 1, kr = tramo(t, 0.42, 1), fl = t < 0.42 ? 0 : Math.max(0, 1 - (t - 0.42) / 0.58);
      if (fl > 0) g += '<path d="' + rr(Bt.x - 2 * s, Bt.y - 2 * s, Bt.w + 4 * s, Bt.h + 4 * s, r + 2 * s) + '" fill="none" stroke="' + P.tinta + '" stroke-width="' + n2(2 * s) + '" stroke-opacity="' + n2(fl) + '"/>';
      if (kr > 0 && kr < 1) g += '<circle cx="' + n2(cx) + '" cy="' + n2(cy) + '" r="' + n2(5 * s + 30 * s * sal(kr)) + '" fill="' + P.tinta + '" fill-opacity="' + n2(0.12 * (1 - kr)) + '" stroke="' + P.tinta + '" stroke-width="' + n2(2 * s) + '" stroke-opacity="' + n2(0.6 * (1 - kr)) + '"/>';
      var px = cx - 46 * s * (1 - e1), py = cy + 34 * s * (1 - e1);
      g += '<g opacity="' + n2(Math.min(1, e1 * 1.5)) + '">' + cursor(px, py, P, s, 'Tutor', pr) + '</g>'; B.p(cx - 50 * s, cy + 60 * s).p(cx + 70 * s, cy + 44 * s).p(cx + 36 * s, cy - 36 * s);
    }
    return fin(g, B);
  }

  /* ───────── D15 · «↺ Devolver» ─────────
     { x, y (centro), ancla 'i'|'c'|'d', variante 'ficha' (rec.) | 'esquina', texto } — la variante 'enlace' es globo({ enlace:'Devolver' }) */
  function devolver(o) {
    var b = base(o), s = b.s, P = b.P, v = o.variante || 'ficha', e = sal(b.t), tx = o.texto || (v === 'esquina' ? 'Dejar todo como estaba' : 'Devolver');
    var px = 12.5 * s, h = (v === 'esquina' ? 32 : 28) * s, tw = medir(tx, px, 600), w = 12 * s + 14 * s + 6 * s + tw + 12 * s + (v === 'esquina' ? 30 * s : 0);
    var x = o.x - (o.ancla === 'd' ? w : o.ancla === 'c' ? w / 2 : 0), y = o.y - h / 2, g = '';
    g += sombraRR(x, y, w, h, h / 2, P, s, 0.5) + '<path d="' + rr(x, y, w, h, h / 2) + '" fill="' + P.papel + '" stroke="' + P.borde + '" stroke-width="' + n2(1 * s) + '"/>';
    g += ICONO.devolver(x + 19 * s, y + h / 2, 14 * s, P.texto, 1.6 * s) + txt(tx, x + 32 * s, y + h / 2 + px * 0.36, px, 600, P.texto);
    if (v === 'esquina') { var ex = x + w - 18 * s; g += linea('M' + P2(ex - 12 * s, y + 8 * s) + 'V' + n2(y + h - 8 * s), P.borde, 1 * s) + ICONO.equis(ex, y + h / 2, 12 * s, P.suave, 1.6 * s); }
    return fin(aparece(g, e, x + w / 2, y + h / 2, 0, 4 * s, 0.94), new Caja().r(x, y, w, h, 6 * s));
  }

  /* ───────── E16 · Foco ─────────
     { area:{x,y,w,h} (ventana), pieza:{x,y,w,h}, variante 'velo' (rec.) | 'vineta' | 'halo', t 0→1 (350 ms) } — no captura clics: la clase sigue usable */
  function foco(o) {
    var b = base(o), s = b.s, P = b.P, e = sal(b.t), A = o.area, Z = o.pieza, v = o.variante || 'velo', pad = 8 * s, id = o.id || uid('f'), g = '';
    var hx = Z.x - pad, hy = Z.y - pad, hw = Z.w + 2 * pad, hh = Z.h + 2 * pad, hole = rr(hx, hy, hw, hh, 12 * s);
    var outer = 'M' + P2(A.x - 40 * s, A.y - 40 * s) + 'H' + n2(A.x + A.w + 40 * s) + 'V' + n2(A.y + A.h + 40 * s) + 'H' + n2(A.x - 40 * s) + 'Z';
    if (v === 'vineta') {
      var cx = Z.x + Z.w / 2, cy = Z.y + Z.h / 2, R = Math.max(A.w, A.h) * 0.8, r0 = Math.max(Z.w, Z.h) / 2 / R;
      g += '<defs><radialGradient id="' + id + '" gradientUnits="userSpaceOnUse" cx="' + n2(cx) + '" cy="' + n2(cy) + '" r="' + n2(R) + '"><stop offset="' + n2(r0 * 0.9) + '" stop-color="' + P.fondo + '" stop-opacity="0"/><stop offset="' + n2(Math.min(0.95, r0 * 1.7)) + '" stop-color="' + P.fondo + '" stop-opacity="0.55"/><stop offset="1" stop-color="' + P.fondo + '" stop-opacity="0.8"/></radialGradient></defs>' +
        '<rect x="' + n2(A.x) + '" y="' + n2(A.y) + '" width="' + n2(A.w) + '" height="' + n2(A.h) + '" fill="url(#' + id + ')" opacity="' + n2(e) + '"/>';
    } else if (v === 'halo') {
      g += '<path d="' + outer + hole + '" fill-rule="evenodd" fill="' + P.fondo + '" fill-opacity="' + n2(0.3 * e) + '"/>';
      [[3, 0.3], [8, 0.14], [14, 0.06]].forEach(function (q) { var k = q[0] * s; g += '<path d="' + rr(hx - k, hy - k, hw + 2 * k, hh + 2 * k, 12 * s + k) + '" fill="none" stroke="' + P.tinta + '" stroke-width="' + n2(5 * s) + '" stroke-opacity="' + n2(q[1] * e) + '"/>'; });
    } else {
      g += '<defs><filter id="' + id + '" x="-5%" y="-5%" width="110%" height="110%"><feGaussianBlur stdDeviation="' + n2(5 * s) + '"/></filter></defs>' +
        '<path d="' + outer + hole + '" fill-rule="evenodd" fill="' + P.fondo + '" fill-opacity="' + n2((P.osc ? 0.66 : 0.7) * e) + '" filter="url(#' + id + ')"/>' +
        '<path d="' + hole + '" fill="none" stroke="' + P.tinta + '" stroke-width="' + n2(1.5 * s) + '" stroke-opacity="' + n2(0.45 * e) + '"/>';
    }
    return fin(g, new Caja().r(A.x, A.y, A.w, A.h));
  }

  /* Movimiento · todo en ms → t (0→1). Cada pieza aplica su propia curva (ease-out cúbica). */
  var tiempo = {
    ENTRADA: 350, MANO: 450, PULSADO: 900, DESPLAZAR: 1400, RECORRIDO: 4000, PENSANDO: 1600, FOCO: 350, CURSOR_PARPADEO: 1060,
    t: function (ms, dur) { return lim(ms / (dur || 350)); },
    fase: function (ms, ciclo) { ciclo = ciclo || 4000; return ((ms % ciclo) + ciclo) % ciclo / ciclo; },
    recorrido: RECORRIDO,
    // recorrido del deslizador: desde → cada parada (mover 600 ms, quieto 1200 ms). Devuelve { valor, parada, moviendo, fin }
    deslizador: function (ms, desde, paradas, mover, quieto) {
      mover = mover || 600; quieto = quieto || 1200; var prev = desde, T = 0;
      for (var i = 0; i < paradas.length; i++) {
        if (ms < T + mover) return { valor: prev + (paradas[i] - prev) * suave((ms - T) / mover), parada: i, moviendo: true, fin: false };
        T += mover; if (ms < T + quieto) return { valor: paradas[i], parada: i, moviendo: false, fin: false };
        T += quieto; prev = paradas[i];
      }
      return { valor: prev, parada: paradas.length - 1, moviendo: false, fin: true };
    },
    duracionDeslizador: function (n, mover, quieto) { return n * ((mover || 600) + (quieto || 1200)); }
  };

  raiz.Profe = {
    globo: globo, pasos: pasos, pregunta: pregunta, pastilla: pastilla, cajita: cajita,
    punto: puntoValor, medida: medida, guias: guias, area: area, desplazar: desplazar, recorrido: recorrido,
    mano: mano, deslizador: deslizador, pulsado: pulsado, devolver: devolver, foco: foco,
    tiempo: tiempo, paleta: paleta, colores: Object.keys(TONOS), ejes: ejes, letras: LETRAS, fuente: SANS,
    util: { txt: txt, txtHalo: txtHalo, rr: rr, medir: medir, envolver: envolver, oklch: oklch, linea: linea, n2: n2, P2: P2, fmt: fmt, cursor: cursor, ficha: ficha, icono: ICONO, sal: sal, suave: suave, tramo: tramo }
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = raiz.Profe;
})(typeof window !== 'undefined' ? window : globalThis);
