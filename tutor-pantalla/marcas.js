/* Marcas · kit de anotaciones sobre la pantalla.
   Funciones puras: reciben números y texto, devuelven SVG como texto. Sin DOM obligatorio, sin fuentes externas.
   Cada pieza devuelve { svg, g, w, h, m }:
     svg → documento SVG listo para pasar a PNG, de (w + 2m) × (h + 2m); colócalo en (x - m, y - m).
     g   → el mismo dibujo como fragmento, en coordenadas de la pieza (0,0)-(w,h).
     m   → margen para el halo, la sombra y el latido.
   flecha devuelve { svg, g, x, y, w, h }: g ya va en coordenadas de la ventana; svg se coloca en (x, y). */
(function (raiz) {
  'use strict';
  var FUENTE = "'Segoe UI', system-ui, sans-serif";
  var n2 = function (x) { return Math.round(x * 100) / 100; };
  var lim = function (x, a, b) { a = a == null ? 0 : a; b = b == null ? 1 : b; return Math.max(a, Math.min(b, x)); };
  var sal = function (t) { return 1 - Math.pow(1 - lim(t), 3); };
  var esc = function (s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); };
  var corto = function (s) { s = String(s == null ? '' : s).trim(); return s.length > 40 ? s.slice(0, 39).trim() + '…' : s; };

  function oklch(L, C, H) {
    var h = H * Math.PI / 180, A = C * Math.cos(h), B = C * Math.sin(h);
    var l = Math.pow(L + 0.3963377774 * A + 0.2158037573 * B, 3);
    var m = Math.pow(L - 0.1055613458 * A - 0.0638541728 * B, 3);
    var s = Math.pow(L - 0.0894841775 * A - 1.291485548 * B, 3);
    var rgb = [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
      -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
      -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s];
    return '#' + rgb.map(function (x) {
      x = lim(x); x = x <= 0.0031308 ? 12.92 * x : 1.055 * Math.pow(x, 1 / 2.4) - 0.055;
      return ('0' + Math.round(x * 255).toString(16)).slice(-2);
    }).join('');
  }

  // [L, C] por tema; tono h. Claro: tinta oscura con texto blanco. Oscuro: tinta clara con texto oscuro.
  var TONOS = {
    azul:     { h: 258, claro: [0.50, 0.17], oscuro: [0.77, 0.12] },
    verde:    { h: 150, claro: [0.50, 0.13], oscuro: [0.80, 0.15] },
    rojo:     { h: 25,  claro: [0.52, 0.19], oscuro: [0.73, 0.16] },
    naranja:  { h: 50,  claro: [0.57, 0.17], oscuro: [0.79, 0.14] },
    amarillo: { h: 85,  claro: [0.66, 0.14], oscuro: [0.87, 0.15] },
    morado:   { h: 300, claro: [0.50, 0.19], oscuro: [0.76, 0.14] }
  };
  var COLORES = Object.keys(TONOS);

  function paleta(color, tema) {
    var T = TONOS[color] || TONOS.azul, osc = tema === 'oscuro', h = T.h, LC = osc ? T.oscuro : T.claro;
    var tinta = oklch(LC[0], LC[1], h);
    var P = {
      tinta: tinta, fondo: tinta, texto: osc ? oklch(0.22, 0.05, h) : '#ffffff', borde: null,
      halo: osc ? oklch(0.17, 0.01, 265) : '#ffffff', haloA: osc ? 0.8 : 0.9,
      sombra: osc ? '#000000' : oklch(0.3, 0.04, h), sombraA: osc ? 0.5 : 0.2,
      tinteA: osc ? 0.12 : 0.07,
      marcador: osc ? oklch(0.8, 0.14, color === 'amarillo' ? 95 : h) : oklch(0.86, 0.15, color === 'amarillo' ? 95 : h),
      marcadorA: osc ? 0.4 : 0.5
    };
    if (!osc && (TONOS[color] ? color : 'azul') === 'amarillo') {
      P.fondo = oklch(0.9, 0.14, 95); P.texto = oklch(0.32, 0.07, 70); P.borde = tinta;
    }
    var claroAmarillo = P.borde != null;
    P.circulo = claroAmarillo ? P.texto : (osc ? P.texto : '#ffffff');
    P.circuloTexto = claroAmarillo ? P.fondo : P.tinta;
    return P;
  }

  var ctx = null;
  function medir(texto, px, peso) {
    try {
      if (!ctx) {
        var c = typeof OffscreenCanvas !== 'undefined' ? new OffscreenCanvas(1, 1) : document.createElement('canvas');
        ctx = c.getContext('2d');
      }
      ctx.font = peso + ' ' + px + 'px ' + FUENTE;
      return ctx.measureText(texto).width;
    } catch (e) { return texto.length * px * 0.56; }
  }

  // Latido: p de 0 a 1 (1.2 s). Dos pulsos, el segundo más suave.
  function latido(p) {
    if (p == null || p < 0 || p >= 1) return { a: 0, f: 0, o: 0 };
    var k = Math.floor(p * 2), f = (p * 2) % 1, g = k ? 0.6 : 1;
    return { a: (f < 0.5 ? Math.sin(Math.PI * f / 0.5) : 0) * g, f: f, o: (1 - f) * 0.55 * g };
  }

  function rr(x, y, w, h, r) {
    var c = Array.isArray(r) ? r : [r, r, r, r]; // arriba-izq, arriba-der, abajo-der, abajo-izq
    var A = function (q, X, Y) { return q ? 'A' + n2(q) + ',' + n2(q) + ' 0 0 1 ' + n2(X) + ',' + n2(Y) : ''; };
    return 'M' + n2(x + c[0]) + ',' + n2(y) + 'H' + n2(x + w - c[1]) + A(c[1], x + w, y + c[1]) +
      'V' + n2(y + h - c[2]) + A(c[2], x + w - c[2], y + h) +
      'H' + n2(x + c[3]) + A(c[3], x, y + h - c[3]) +
      'V' + n2(y + c[0]) + A(c[0], x + c[0], y) + 'Z';
  }
  function trazo(e) {
    if (e >= 0.999) return '';
    if (e <= 0.005) return ' visibility="hidden"';
    return ' pathLength="1" stroke-dasharray="' + n2(e) + ' 1"';
  }
  function doc(g, x, y, w, h) {
    return '<svg xmlns="http://www.w3.org/2000/svg" width="' + n2(w) + '" height="' + n2(h) + '" viewBox="' +
      n2(x) + ' ' + n2(y) + ' ' + n2(w) + ' ' + n2(h) + '">' + g + '</svg>';
  }
  function txt(s, x, y, px, peso, color, extra) {
    return '<text x="' + n2(x) + '" y="' + n2(y) + '" font-family="' + FUENTE + '" font-size="' + n2(px) +
      '" font-weight="' + peso + '" fill="' + color + '"' + (extra || '') + '>' + esc(s) + '</text>';
  }
  function base(o) { return { s: o.escala || 1, P: paleta(o.color, o.tema), L: latido(o.latido), t: o.t == null ? 1 : o.t }; }
  function entra(g, e, w, h, dx, dy, sc) {
    if (e >= 0.999) return g;
    return '<g opacity="' + n2(e) + '" transform="translate(' + n2(w / 2 + dx) + ',' + n2(h / 2 + dy) + ') scale(' + n2(sc) +
      ') translate(' + n2(-w / 2) + ',' + n2(-h / 2) + ')">' + g + '</g>';
  }
  function cuerpo(P, s, d, w, h) { // sombra suave + halo + relleno
    return '<path d="' + rr(0, 2 * s, w, h, d) + '" fill="' + P.sombra + '" fill-opacity="' + n2(P.sombraA * 0.45) + '"/>' +
      '<path d="' + rr(0, 1 * s, w, h, d) + '" fill="' + P.sombra + '" fill-opacity="' + n2(P.sombraA) + '"/>' +
      '<path d="' + rr(0, 0, w, h, d) + '" fill="none" stroke="' + P.halo + '" stroke-opacity="' + P.haloA + '" stroke-width="' + n2(3 * s) + '"/>' +
      '<path d="' + rr(0, 0, w, h, d) + '" fill="' + P.fondo + '"' + (P.borde ? ' stroke="' + P.borde + '" stroke-width="' + n2(1.25 * s) + '"' : '') + '/>';
  }
  function anillo(P, s, L, w, h, r) {
    if (L.o <= 0) return '';
    var k = 1.5 * s + 4 * s * L.f;
    return '<path d="' + rr(-k, -k, w + 2 * k, h + 2 * k, Array.isArray(r) ? r.map(function (q) { return q + k; }) : r + k) +
      '" fill="none" stroke="' + P.tinta + '" stroke-opacity="' + n2(L.o) + '" stroke-width="' + n2(1.5 * s) + '"/>';
  }

  /* 1 · Marco. El trazo va centrado sobre el borde de la caja (0,0)-(w,h). */
  function marco(o) {
    var b = base(o), s = b.s, P = b.P, L = b.L, e = sal(b.t), w = o.w, h = o.h;
    var sw = (Math.min(w, h) < 40 * s ? 2 : 2.5) * s * (1 + 0.5 * L.a);
    var r = Math.min(8 * s, Math.min(w, h) / 3), d = rr(0, 0, w, h, r), da = trazo(e), m = 10 * s;
    var g = '<path d="' + d + '" fill="' + P.tinta + '" fill-opacity="' + n2((P.tinteA + 0.12 * L.a) * e) + '"/>' +
      '<path d="' + d + '" fill="none" stroke="' + P.halo + '" stroke-opacity="' + P.haloA + '" stroke-width="' + n2(sw + 3 * s) + '" stroke-linecap="round"' + da + '/>' +
      '<path d="' + d + '" fill="none" stroke="' + P.tinta + '" stroke-width="' + n2(sw) + '" stroke-linecap="round"' + da + '/>';
    if (L.o > 0) {
      var k = 3 * s + 5 * s * L.f;
      g += '<path d="' + rr(-k, -k, w + 2 * k, h + 2 * k, r + k) + '" fill="none" stroke="' + P.tinta + '" stroke-opacity="' + n2(L.o) + '" stroke-width="' + n2(1.5 * s) + '"/>';
    }
    return { svg: doc(g, -m, -m, w + 2 * m, h + 2 * m), g: g, w: w, h: h, m: m };
  }

  /* 2 · Nota. Etiqueta sólida; n opcional en círculo. */
  function nota(o) {
    var b = base(o), s = b.s, P = b.P, L = b.L, e = sal(b.t), texto = corto(o.texto);
    var fs = 13 * s, h = Math.round(26 * s), r = 7 * s, d = 18 * s, conN = o.n != null && o.n !== '';
    var x0 = conN ? 4 * s + d + 6 * s : 10 * s, w = Math.round(x0 + medir(texto, fs, 600) + 10 * s), m = 7 * s;
    var g = cuerpo(P, s, r, w, h);
    if (conN) {
      var cx = 4 * s + d / 2;
      g += '<circle cx="' + n2(cx) + '" cy="' + n2(h / 2) + '" r="' + n2(d / 2) + '" fill="' + P.circulo + '"/>' +
        txt(String(o.n), cx, h / 2 + 11.5 * s * 0.36, 11.5 * s, 700, P.circuloTexto, ' text-anchor="middle"');
    }
    g += txt(texto, x0, h / 2 + fs * 0.35, fs, 600, P.texto) + anillo(P, s, L, w, h, r);
    if (e < 0.999) g = entra(g, e, w, h, 0, (1 - e) * 5 * s, 0.92 + 0.08 * e);
    else if (L.a > 0) g = '<g transform="translate(' + n2(w / 2) + ',' + n2(h / 2) + ') scale(' + n2(1 + 0.04 * L.a) + ') translate(' + n2(-w / 2) + ',' + n2(-h / 2) + ')">' + g + '</g>';
    return { svg: doc(g, -m, -m, w + 2 * m, h + 2 * m), g: g, w: w, h: h, m: m };
  }

  /* 3 · Flecha de la nota (x1,y1) a la punta (x2,y2). curva: 0 recta; ±0.1…0.35 arqueada (signo = lado). */
  function flecha(o) {
    var b = base(o), s = b.s, P = b.P, L = b.L, e = sal(b.t);
    var x1 = o.x1, y1 = o.y1, x2 = o.x2, y2 = o.y2, dx = x2 - x1, dy = y2 - y1, len = Math.hypot(dx, dy) || 1;
    var c = o.curva != null ? o.curva : (len > 90 * s ? 0.15 : 0), k = lim(c * len, -70 * s, 70 * s);
    var cx = (x1 + x2) / 2 - dy / len * k, cy = (y1 + y2) / 2 + dx / len * k;
    var u = e, tx = (1 - u) * (1 - u) * x1 + 2 * (1 - u) * u * cx + u * u * x2, ty = (1 - u) * (1 - u) * y1 + 2 * (1 - u) * u * cy + u * u * y2;
    var qx = x1 + (cx - x1) * u, qy = y1 + (cy - y1) * u, ux = tx - qx, uy = ty - qy, ul = Math.hypot(ux, uy);
    if (ul < 1e-6) { ux = dx / len; uy = dy / len; } else { ux /= ul; uy /= ul; }
    var nx = -uy, ny = ux, hs = lim(e / 0.3), hl = Math.min(10 * s, len * 0.4) * hs, hw = 9 * s * hs;
    var sw = 2.25 * s * (1 + 0.5 * L.a), ex = tx - ux * hl * 0.7, ey = ty - uy * hl * 0.7;
    var p = function (X, Y) { return n2(X) + ',' + n2(Y); };
    var shaft = 'M' + p(x1, y1) + 'Q' + p(qx, qy) + ' ' + p(ex, ey);
    var head = 'M' + p(tx, ty) + 'L' + p(tx - ux * hl + nx * hw / 2, ty - uy * hl + ny * hw / 2) + 'L' + p(tx - ux * hl * 0.72, ty - uy * hl * 0.72) +
      'L' + p(tx - ux * hl - nx * hw / 2, ty - uy * hl - ny * hw / 2) + 'Z';
    var g = e <= 0.005 ? '' :
      '<path d="' + shaft + '" fill="none" stroke="' + P.halo + '" stroke-opacity="' + P.haloA + '" stroke-width="' + n2(sw + 3.5 * s) + '" stroke-linecap="round"/>' +
      '<path d="' + head + '" fill="' + P.halo + '" fill-opacity="' + P.haloA + '" stroke="' + P.halo + '" stroke-opacity="' + P.haloA + '" stroke-width="' + n2(3.5 * s) + '" stroke-linejoin="round"/>' +
      '<path d="' + shaft + '" fill="none" stroke="' + P.tinta + '" stroke-width="' + n2(sw) + '" stroke-linecap="round"/>' +
      '<path d="' + head + '" fill="' + P.tinta + '" stroke="' + P.tinta + '" stroke-width="' + n2(1 * s) + '" stroke-linejoin="round"/>';
    var pad = 12 * s, X = Math.min(x1, x2, cx) - pad, Y = Math.min(y1, y2, cy) - pad;
    var W = Math.max(x1, x2, cx) + pad - X, H = Math.max(y1, y2, cy) + pad - Y;
    return { svg: doc(g, X, Y, W, H), g: g, x: n2(X), y: n2(Y), w: n2(W), h: n2(H) };
  }

  /* 4 · Marca al borde. Pastilla con el lado plano pegado al borde de la ventana. */
  var DIR = { arriba: [0, -1], abajo: [0, 1], izquierda: [-1, 0], derecha: [1, 0] };
  function borde(o) {
    var b = base(o), s = b.s, P = b.P, L = b.L, e = sal(b.t), lado = DIR[o.lado] ? o.lado : 'abajo', v = DIR[lado];
    var texto = corto(String(o.texto || '').replace(/^\s*[↑↓←→⬆⬇⬅➡]\s*/, ''));
    var fs = 13 * s, h = Math.round(28 * s), ic = 12 * s, gap = 6 * s, px = 12 * s, R = h / 2, m = 7 * s;
    var w = Math.round(px + ic + gap + medir(texto, fs, 600) + px);
    var rad = { arriba: [0, 0, R, R], abajo: [R, R, 0, 0], izquierda: [0, R, R, 0], derecha: [R, 0, 0, R] }[lado];
    var izq = lado !== 'derecha', ax = izq ? px : w - px - ic, tx = izq ? px + ic + gap : px;
    var cx = ax + ic / 2, cy = h / 2, a = ic * 0.42, q = a * 0.62, nx = -v[1], ny = v[0];
    var p = function (X, Y) { return n2(X) + ',' + n2(Y); };
    var fx = cx + v[0] * a, fy = cy + v[1] * a;
    var arrow = 'M' + p(cx - v[0] * a, cy - v[1] * a) + 'L' + p(fx, fy) + 'M' + p(fx - v[0] * q + nx * q, fy - v[1] * q + ny * q) + 'L' + p(fx, fy) + 'L' + p(fx - v[0] * q - nx * q, fy - v[1] * q - ny * q);
    var g = cuerpo(P, s, rad, w, h) +
      '<path d="' + arrow + '" fill="none" stroke="' + P.texto + '" stroke-width="' + n2(1.75 * s) + '" stroke-linecap="round" stroke-linejoin="round"/>' +
      txt(texto, tx, h / 2 + fs * 0.35, fs, 600, P.texto) + anillo(P, s, L, w, h, rad);
    if (e < 0.999) g = entra(g, e, w, h, v[0] * (1 - e) * h * 0.8, v[1] * (1 - e) * h * 0.8, 1);
    return { svg: doc(g, -m, -m, w + 2 * m, h + 2 * m), g: g, w: w, h: h, m: m };
  }

  /* 5 · Resaltador. Banda de marcador con cantos en bisel; crece de izquierda a derecha con t. */
  function resaltador(o) {
    var b = base({ escala: o.escala, color: o.color || 'amarillo', tema: o.tema, latido: o.latido, t: o.t });
    var s = b.s, P = b.P, w = o.w, h = o.h, ww = Math.max(0.01, w * sal(b.t)), k = Math.min(5 * s, h * 0.3), m = 2 * s;
    var d = 'M' + n2(k * 0.7) + ',' + n2(h * 0.1) + 'Q' + n2(ww / 2) + ',' + n2(-h * 0.03) + ' ' + n2(ww) + ',' + n2(h * 0.05) +
      'L' + n2(ww - k * 0.7) + ',' + n2(h * 0.93) + 'Q' + n2(ww / 2) + ',' + n2(h * 1.03) + ' 0,' + n2(h * 0.9) + 'Z';
    var g = '<path d="' + d + '" fill="' + P.marcador + '" fill-opacity="' + n2(Math.min(0.85, P.marcadorA + 0.2 * b.L.a)) + '"/>';
    return { svg: doc(g, -m, -m, w + 2 * m, h + 2 * m), g: g, w: w, h: h, m: m };
  }

  /* 6 · Corchete. largo = lo que abarca; lado = dónde queda respecto a lo señalado; tipo: llave | corchete.
     ancla = punto de la pieza que va en el inicio del tramo abarcado (lado del contenido). */
  function corchete(o) {
    var b = base(o), s = b.s, P = b.P, L = b.L, lado = DIR[o.lado] ? o.lado : 'derecha', Lg = o.largo || 100;
    var eB = sal(lim(b.t / 0.6)), tN = lim((b.t - 0.4) / 0.6), d = 12 * s, m = 8 * s;
    var nt = o.texto ? nota({ texto: o.texto, n: o.n, color: o.color, tema: o.tema, escala: s, t: tN, latido: o.latido }) : null;
    var nw = nt ? nt.w : 0, nh = nt ? nt.h : 0, G = nt ? 8 * s : 0, W, H, map, nx, ny, an;
    if (lado === 'derecha' || lado === 'izquierda') {
      H = Math.max(Lg, nh); W = d + G + nw; var y0 = (H - Lg) / 2;
      map = lado === 'derecha' ? function (a, q) { return [q, y0 + a]; } : function (a, q) { return [W - q, y0 + a]; };
      nx = lado === 'derecha' ? d + G : 0; ny = (H - nh) / 2; an = { x: lado === 'derecha' ? 0 : W, y: y0 };
    } else {
      W = Math.max(Lg, nw); H = d + G + nh; var x0 = (W - Lg) / 2;
      map = lado === 'abajo' ? function (a, q) { return [x0 + a, q]; } : function (a, q) { return [x0 + a, H - q]; };
      nx = (W - nw) / 2; ny = lado === 'abajo' ? d + G : 0; an = { x: x0, y: lado === 'abajo' ? 0 : H };
    }
    var p = function (a, q) { var r = map(a, q); return n2(r[0]) + ',' + n2(r[1]); };
    var q = Math.min(8 * s, Lg / 4), hd = d / 2, M2 = Lg / 2;
    var path = o.tipo === 'corchete'
      ? 'M' + p(0, 0) + 'L' + p(0, hd) + 'L' + p(Lg, hd) + 'L' + p(Lg, 0) + 'M' + p(M2, hd) + 'L' + p(M2, d)
      : 'M' + p(0, 0) + 'Q' + p(0, hd) + ' ' + p(q, hd) + 'L' + p(M2 - q, hd) + 'Q' + p(M2, hd) + ' ' + p(M2, d) +
        'Q' + p(M2, hd) + ' ' + p(M2 + q, hd) + 'L' + p(Lg - q, hd) + 'Q' + p(Lg, hd) + ' ' + p(Lg, 0);
    var sw = 2.25 * s * (1 + 0.5 * L.a), da = trazo(eB);
    var g = '<path d="' + path + '" fill="none" stroke="' + P.halo + '" stroke-opacity="' + P.haloA + '" stroke-width="' + n2(sw + 3 * s) + '" stroke-linecap="round" stroke-linejoin="round"' + da + '/>' +
      '<path d="' + path + '" fill="none" stroke="' + P.tinta + '" stroke-width="' + n2(sw) + '" stroke-linecap="round" stroke-linejoin="round"' + da + '/>';
    if (nt) g += '<g transform="translate(' + n2(nx) + ',' + n2(ny) + ')">' + nt.g + '</g>';
    return { svg: doc(g, -m, -m, W + 2 * m, H + 2 * m), g: g, w: n2(W), h: n2(H), m: m, ancla: { x: n2(an.x), y: n2(an.y) } };
  }

  /* 7 · «Mira aquí». Punto con dos ondas. fase 0→1 en bucle (sugerido: 1.6 s). Centro en (w/2, h/2). */
  function mira(o) {
    var b = base(o), s = b.s, P = b.P, e = sal(b.t), S = 48 * s, c = S / 2, r0 = 4.5 * s * (1 + 0.3 * b.L.a);
    var fase = o.fase == null ? 0.35 : o.fase, g = '';
    [0, 0.5].forEach(function (k) {
      var f = (fase + k) % 1, r = r0 + 2 * s + 15 * s * f, op = Math.min(1, (1 - f) * 1.1) * e, sw = 2 * s * (1 - 0.4 * f);
      g += '<circle cx="' + n2(c) + '" cy="' + n2(c) + '" r="' + n2(r) + '" fill="none" stroke="' + P.halo + '" stroke-opacity="' + n2(op * P.haloA * 0.8) + '" stroke-width="' + n2(sw + 2.5 * s) + '"/>' +
        '<circle cx="' + n2(c) + '" cy="' + n2(c) + '" r="' + n2(r) + '" fill="none" stroke="' + P.tinta + '" stroke-opacity="' + n2(op) + '" stroke-width="' + n2(sw) + '"/>';
    });
    g += '<circle cx="' + n2(c) + '" cy="' + n2(c) + '" r="' + n2(r0 * e) + '" fill="' + P.tinta + '" stroke="' + P.halo + '" stroke-opacity="' + P.haloA + '" stroke-width="' + n2(2.5 * s) + '" paint-order="stroke"/>';
    return { svg: doc(g, 0, 0, S, S), g: g, w: S, h: S, m: 0, centro: { x: c, y: c } };
  }

  /* Movimiento */
  var tiempo = {
    ENTRADA: 350, LATIDO: 1200, DESLIZAR: 250, MIRA: 1600,
    // ms desde que aparece la marca → t local de cada pieza (cada pieza aplica su propia curva ease-out)
    entrada: function (ms) { return { nota: lim(ms / 140), flecha: lim((ms - 80) / 180), marco: lim((ms - 170) / 180) }; },
    // ms desde que el ratón entra en la palabra → p para { latido: p }; null fuera de rango
    latido: function (ms) { return ms >= 0 && ms < 1200 ? ms / 1200 : null; },
    // ms desde «Reajustar» → k (0→1, ease-out) para interpolar posiciones
    deslizar: function (ms) { return sal(ms / 250); }
  };
  function interpolar(a, b, k) {
    if (typeof a === 'number') return a + (b - a) * k;
    var r = {}; Object.keys(a).forEach(function (x) { r[x] = typeof a[x] === 'number' ? a[x] + (b[x] - a[x]) * k : b[x]; }); return r;
  }
  function temaPara(r, g, b) { // color medio del fondo bajo la marca, 0-255
    var li = function (x) { x /= 255; return x <= 0.04045 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); };
    return 0.2126 * li(r) + 0.7152 * li(g) + 0.0722 * li(b) > 0.18 ? 'claro' : 'oscuro';
  }
  function documento(w, h, fragmentos) {
    return doc([].concat(fragmentos).join(''), 0, 0, w, h);
  }

  /* Íconos de panel · línea 1.5 px a cualquier tamaño, currentColor por defecto. */
  var TRAZOS = {
    reajustar: '<path d="M4 9V6.5A2.5 2.5 0 0 1 6.5 4H9"/><path d="M15 4h2.5A2.5 2.5 0 0 1 20 6.5V9"/><path d="M20 15v2.5a2.5 2.5 0 0 1-2.5 2.5H15"/><path d="M9 20H6.5A2.5 2.5 0 0 1 4 17.5V15"/><circle cx="12" cy="12" r="2.6"/>',
    senalar: '<path d="M10 4H6a2 2 0 0 0-2 2v4"/><path d="M4 13.5v.5a2 2 0 0 0 2 2h2.5"/><path d="M13.5 4h.5a2 2 0 0 1 2 2v2.5"/><path d="M12.5 12.5l8 2.8-3.4 1.4-1.4 3.4z"/>',
    borrar: '<path d="M13 20h7"/><path d="M5.3 15.7a2 2 0 0 1 0-2.8l7.6-7.6a2 2 0 0 1 2.8 0l3 3a2 2 0 0 1 0 2.8L12.4 17.4a2 2 0 0 1-1.4.6H8.6a2 2 0 0 1-1.4-.6z"/><path d="M9.6 8.6l5.8 5.8"/>',
    voz: '<path d="M4 9.6v4.8h3.4L12 18.5v-13L7.4 9.6z"/><path d="M15.5 9a4.2 4.2 0 0 1 0 6"/><path d="M18.4 6.2a8.2 8.2 0 0 1 0 11.6"/>',
    vozApagada: '<path d="M4 9.6v4.8h3.4L12 18.5v-13L7.4 9.6z"/><path d="M16 9.5l5 5"/><path d="M21 9.5l-5 5"/>',
    practicar: '<rect x="3.5" y="7.5" width="13" height="13" rx="2"/><path d="M7.5 4.5h10a2 2 0 0 1 2 2v10"/><path d="M8.2 12a1.9 1.9 0 1 1 2.6 1.8c-.5.2-.8.6-.8 1.1v.3"/><path d="M10 17.6v.01"/>',
    celular: '<rect x="3.5" y="2.5" width="10" height="19" rx="2.2"/><path d="M7.5 18.5h2"/><path d="M16.5 12h5"/><path d="M19 9.5l2.5 2.5-2.5 2.5"/>'
  };
  var iconos = {};
  Object.keys(TRAZOS).forEach(function (k) {
    iconos[k] = function (tam, color) {
      tam = tam || 16;
      return '<svg xmlns="http://www.w3.org/2000/svg" width="' + tam + '" height="' + tam + '" viewBox="0 0 24 24" fill="none" stroke="' + (color || 'currentColor') +
        '" stroke-width="' + n2(1.5 * 24 / tam) + '" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + TRAZOS[k] + '</svg>';
    };
  });

  var Marcas = {
    piezas: { marco: marco, nota: nota, flecha: flecha, borde: borde, resaltador: resaltador, corchete: corchete, mira: mira },
    iconos: iconos, tiempo: tiempo, paleta: paleta, colores: COLORES, temaPara: temaPara,
    documento: documento, interpolar: interpolar, oklch: oklch, fuente: FUENTE
  };
  raiz.Marcas = Marcas;
  if (typeof module !== 'undefined' && module.exports) module.exports = Marcas;
})(typeof window !== 'undefined' ? window : globalThis);
