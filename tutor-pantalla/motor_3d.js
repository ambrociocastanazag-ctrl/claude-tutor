/* Motor 3D de figuras en SVG: JS puro, sin DOM (salvo girable), sirve en el navegador (window.Figuras3D, después de motor_figuras.js)
   y en node (require). Lo comparten el chat de los tutores (```3d), la Tarjeta SVG (Geometría con guion 3D) y los dibujos en pantalla
   (forma "3d"). Contrato: tutor-pantalla/CONTRATO-3D.md.
     Figuras3D.figura(spec, opts)     → {svg, w, h, vista:[az, el], errores:[{objeto, mensaje}]}   (con errores dibuja lo válido)
     Figuras3D.escena(spec, opts)     → {dibujar(vista, opts2) → igual que figura, vista:[az, el], errores}  (se arma una vez y se gira barato)
     Figuras3D.guion(texto, opts)     → {svg, w, h, vista, errores:[{linea, mensaje}], spec}  (el lenguaje 3D de la pestaña Geometría)
     Figuras3D.aSpec(texto)           → {spec, errores:[{linea, mensaje}]}
     Figuras3D.es3d(texto)            → bool: ¿el guion de Geometría es 3D? (un punto (x,y,z) o un comando que solo existe en 3D)
     Figuras3D.aGuion(spec)           → el guion equivalente a una spec (para «Editar en la tarjeta»), o null si no se puede
     Figuras3D.vistasGiro(vista, 'vaiven' | 'vuelta', n) → n vistas de una animación
     Figuras3D.fotogramas(spec | {guion} | escena, opts) → Promise<{fotos: [dataURL PNG], ms, w, h}>  (GIF: gif3d.py)
     Figuras3D.girable(elemento, spec | {guion}, opts) → {vista(), poner([az, el]), svg(opts2) → la vista actual 'justa', destruir()}
   opts: los de Figuras (tema, tam, ancho, fondo, paleta) y además vista:[az, el] (grados), encuadre:'justo'|'esfera', rapido:bool,
         anotaciones:{ejes, numeros, nombres, medidas} (false apaga; manda sobre la spec) y relleno:'opaco'|'transparente' (manda sobre cada objeto).
   Cómo dibuja: proyección ortográfica; caras ordenadas de atrás hacia adelante (pintor); cada sólido convexo opaco es un grupo que tapa,
   y las líneas que quedan detrás de él (sus aristas ocultas, un eje que lo atraviesa) salen a trazos, como en los libros. */
(function(RAIZ){
  'use strict';
  var F = (RAIZ && RAIZ.Figuras) || (typeof module !== 'undefined' && typeof require === 'function' ? require('./motor_figuras.js') : null);
  if (!F || !F._u) throw new Error('motor_3d.js necesita motor_figuras.js (cárgalo antes)');
  var U = F._u, GR = Math.PI / 180;
  function tiene(o, k){ return Object.prototype.hasOwnProperty.call(o, k); }

  // =====================================================================================================
  // 0. Vectores [x, y, z]
  // =====================================================================================================
  function sum(a, b){ return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]; }
  function dif(a, b){ return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
  function por(a, k){ return [a[0] * k, a[1] * k, a[2] * k]; }
  function pe(a, b){ return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
  function cr(a, b){ return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
  function lon(a){ return Math.hypot(a[0], a[1], a[2]); }
  function uni(a){ var n = lon(a); return n < 1e-15 ? [0, 0, 0] : por(a, 1 / n); }
  function interp(a, b, t){ return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]; }
  function centro(ps){ var c = [0, 0, 0]; ps.forEach(function(p){ c = sum(c, p); }); return por(c, 1 / Math.max(1, ps.length)); }
  function baseDe(n){                                       // dos unitarios perpendiculares a n (y entre sí)
    var a = Math.abs(n[0]) < 0.9 ? [1, 0, 0] : [0, 1, 0], e1 = uni(cr(n, a));
    return [e1, cr(n, e1)];
  }
  function newell(p){                                       // normal de un polígono (sigue el orden de sus vértices)
    var n = [0, 0, 0];
    for (var i = 0; i < p.length; i++){
      var a = p[i], b = p[(i + 1) % p.length];
      n[0] += (a[1] - b[1]) * (a[2] + b[2]); n[1] += (a[2] - b[2]) * (a[0] + b[0]); n[2] += (a[0] - b[0]) * (a[1] + b[1]);
    }
    return uni(n);
  }
  function anillo(c, eje, r, n){                            // n puntos de la circunferencia de centro c, radio r, perpendicular a eje
    var b = baseDe(uni(eje)), out = [];
    for (var i = 0; i < n; i++){ var a = 2 * Math.PI * i / n; out.push(sum(c, sum(por(b[0], r * Math.cos(a)), por(b[1], r * Math.sin(a))))); }
    return out;
  }

  // =====================================================================================================
  // 1. Lectura de la spec
  // =====================================================================================================
  function numero(v, nombre){ return U.numeroDe(v, nombre); }
  function pt(v, nombre){
    if (!Array.isArray(v) || v.length < 2 || v.length > 3) throw new Error('«' + nombre + '» debe ser un punto [x, y, z]');
    return [numero(v[0], nombre), numero(v[1], nombre), v.length > 2 ? numero(v[2], nombre) : 0];
  }
  function rango(v, def, nombre){
    if (v == null) return def;
    if (!Array.isArray(v) || v.length !== 2) throw new Error('«' + nombre + '» debe ser [desde, hasta]');
    var a = numero(v[0], nombre), b = numero(v[1], nombre);
    if (!(b > a)) throw new Error('el rango «' + nombre + '» va de menor a mayor');
    return [a, b];
  }
  function positivo(v, nombre){ var n = numero(v, nombre); if (!(n > 0)) throw new Error('«' + nombre + '» debe ser mayor que 0'); return n; }
  function fun(expr, vars, nombre){
    if (typeof expr === 'number'){ var c = expr; return function(){ return c; }; }
    if (typeof expr !== 'string' || !expr.trim()) throw new Error('falta la expresión «' + nombre + '»');
    try { return F.compilar(expr.replace(/^\s*[a-z]\s*(\(\s*[a-z,\s]*\))?\s*=\s*/i, ''), {vars: vars}); }
    catch (e){ throw new Error('«' + nombre + '»: ' + e.message); }
  }
  function opac(v, def){ var n = Number(v); return v == null || v === '' || !isFinite(n) ? def : Math.max(0.05, Math.min(1, n)); }
  function entero(v, def, lo, hi){ var n = Math.round(Number(v)); return v == null || !isFinite(n) ? def : Math.max(lo, Math.min(hi, n)); }
  var CON_RELLENO = /^\s*(superficie|param[eé]trica|revoluci[oó]n|pol[ií]gono|tri[aá]ngulo|plano|cubo|caja|ortoedro|prisma|pir[aá]mide|tetraedro|cilindro|cono|esfera|malla)\s*$/i;
  var TIPOS = {superficie: 1, parametrica: 1, revolucion: 1, curva: 1, punto: 1, segmento: 1, recta: 1, vector: 1, poligono: 1, plano: 1,
               cubo: 1, caja: 1, prisma: 1, piramide: 1, cilindro: 1, cono: 1, esfera: 1, malla: 1, carga: 1, campo: 1, etiqueta: 1, cota: 1, angulo: 1, marcaangulo: 1, angulorecto: 1, marcaigual: 1};
  var ALIAS_TIPO = {triangulo: 'poligono', tetraedro: 'piramide', ortoedro: 'caja', paralelepipedo: 'caja', superficieparametrica: 'parametrica',
                    surface: 'superficie', sphere: 'esfera', cube: 'cubo', cylinder: 'cilindro', cone: 'cono', plane: 'plano', curve: 'curva',
                    point: 'punto', segment: 'segmento', line: 'recta', polygon: 'poligono', pyramid: 'piramide', prism: 'prisma', label: 'etiqueta'};
  function tipoDe(o){
    var t = U.claveNorm(String(o.tipo || '')).replace(/[\s_-]/g, '');
    if (tiene(ALIAS_TIPO, t)) t = ALIAS_TIPO[t];
    if (!tiene(TIPOS, t)) throw new Error(o.tipo ? 'no conozco el tipo «' + o.tipo + '»' : 'falta «tipo»');
    return t;
  }

  // =====================================================================================================
  // 2. La escena: caras, polilíneas, puntos y textos en el espacio (antes de mirar)
  // =====================================================================================================
  function nueva(P, k, rapido){
    return {P: P, k: k, rapido: !!rapido, caras: [], polis: [], puntos: [], textos: [], solidos: [], diferidos: [], marcas: [], color: 0, rev: null, supZ: false};
  }
  function siguienteColor(sc){ var c = sc.P.colores[sc.color % sc.P.colores.length]; sc.color++; return c; }
  function colorObj(sc, o, def){ return o.color ? U.colorDe(sc.P, o.color, def || siguienteColor(sc)) : (def || siguienteColor(sc)); }
  function claro(sc, c){ return U.mezcla(c, sc.P.fondo, 0.5); }                       // relleno de sólidos (estilo libro)
  function cara(sc, p, o){
    var c = {p: p, color: o.color, op: o.op == null ? 1 : o.op, n: o.n || newell(p), malla: !!o.malla, sol: o.sol == null ? -1 : o.sol, huecos: o.huecos || null, idx: sc.caras.length,
             medida: !!sc.medida};
    sc.caras.push(c);
    return c;
  }
  function poli(sc, pts, o){
    sc.polis.push({pts: pts, color: o.color, ancho: o.ancho || 2, guion: o.guion || null, oculta: o.oculta || 'guion', flecha: !!o.flecha,
                   sol: o.sol == null ? -1 : o.sol, op: o.op == null ? 1 : o.op, eje: !!o.eje, medida: !!(o.medida || sc.medida)});
  }
  function texto(sc, p, t, o){ o = o || {}; sc.textos.push({p: p, texto: String(t).slice(0, 80), tipo: o.tipo || 'nota', dir: o.dir, fin: o.fin, col: o.col, tam: o.tam, peso: o.peso, cur: o.cur}); }
  function solido(sc, o, datos){
    var s = {id: sc.solidos.length, convexo: o.convexo !== false, cerrado: o.cerrado !== false, opaco: (o.op == null ? 1 : o.op) >= 0.999, caras: [], datos: datos || {}};
    sc.solidos.push(s);
    return s;
  }
  // poliedro: V = vértices, C = caras (índices). Orienta cada cara hacia fuera (convexo) y saca las aristas.
  function poliedro(sc, V, C, o, datos){
    var s = solido(sc, o, datos), cc = centro(V), aristas = {};
    C.forEach(function(ix){
      var p = ix.map(function(i){ return V[i]; }), n = newell(p);
      if (lon(n) < 0.5) return;
      if (pe(n, dif(centro(p), cc)) < 0){ p = p.slice().reverse(); n = por(n, -1); }
      cara(sc, p, {color: o.relleno, op: o.op, n: n, sol: s.id});
      s.caras.push(sc.caras.length - 1);
      for (var i = 0; i < ix.length; i++){ var a = ix[i], b = ix[(i + 1) % ix.length], kk = Math.min(a, b) + ',' + Math.max(a, b); aristas[kk] = [a, b]; }
    });
    if (o.aristas !== false) Object.keys(aristas).forEach(function(kk){
      poli(sc, [V[aristas[kk][0]], V[aristas[kk][1]]], {color: o.borde, ancho: 1.6, sol: s.id, oculta: o.ocultas === false ? 'nada' : 'guion'});
    });
    return s;
  }
  function estiloSolido(sc, o){
    var c = colorObj(sc, o), op = opac(o.opacidad, 1);
    return {color: c, relleno: op < 1 ? c : claro(sc, c), op: op, borde: U.mezcla(sc.P.tinta, c, 0.25), ocultas: o.ocultas, aristas: o.aristas};
  }

  // ---- los constructores, uno por tipo ----
  var HAZ = {};
  HAZ.punto = function(sc, o){
    var p = pt(o.en || o.p || o.punto, 'en');
    sc.puntos.push({p: p, color: o.color ? U.colorDe(sc.P, o.color, sc.P.tinta) : sc.P.tinta, nombre: o.nombre ? String(o.nombre).slice(0, 40) : ''});
  };
  HAZ.carga = function(sc, o){
    var p = pt(o.en || o.p, 'en'), q = numero(o.q == null ? 1 : o.q, 'q');
    sc.puntos.push({p: p, q: q, color: q >= 0 ? sc.P.rojo : sc.P.azul, nombre: o.nombre ? String(o.nombre).slice(0, 40) : ''});
    (sc.cargas = sc.cargas || []).push({p: p, q: q});
  };
  HAZ.segmento = function(sc, o){
    var a = pt(o.de || o.desde, 'de'), b = pt(o.a || o.hasta, 'a');
    poli(sc, [a, b], {color: o.color ? U.colorDe(sc.P, o.color, sc.P.tinta) : sc.P.tinta, ancho: 2, guion: o.guion ? [6, 4] : null});
    if (o.nombre) texto(sc, interp(a, b, 0.5), o.nombre, {tipo: 'nombre'});
  };
  HAZ.vector = function(sc, o){
    var a = o.de || o.desde ? pt(o.de || o.desde, 'de') : [0, 0, 0], b;
    if (o.v) b = sum(a, pt(o.v, 'v')); else b = pt(o.a || o.hasta, 'a');
    if (lon(dif(b, a)) < 1e-12) throw new Error('el vector mide 0');
    var c = colorObj(sc, o);
    poli(sc, [a, b], {color: c, ancho: 2.5, flecha: true});
    if (o.nombre) texto(sc, interp(a, b, 0.62), o.nombre, {tipo: 'nombre', col: c});
  };
  HAZ.recta = function(sc, o){
    var por2 = o.por || [o.de, o.a];
    if (!por2 || por2.length !== 2) throw new Error('una recta va «por» dos puntos');
    var a = pt(por2[0], 'por'), b = pt(por2[1], 'por'), d = dif(b, a), c = o.color ? U.colorDe(sc.P, o.color, sc.P.tinta) : sc.P.tinta;
    if (lon(d) < 1e-12) throw new Error('los dos puntos coinciden');
    sc.diferidos.push(function(caja){
      var t = recorteCaja(a, d, caja);
      if (t) poli(sc, [sum(a, por(d, t[0])), sum(a, por(d, t[1]))], {color: c, ancho: 1.75});
    });
    if (o.nombre) texto(sc, b, o.nombre, {tipo: 'nombre'});
  };
  HAZ.poligono = function(sc, o){
    var ps = (o.puntos || []).map(function(p, i){ return pt(p, 'puntos[' + i + ']'); });
    if (ps.length < 3) throw new Error('un polígono necesita 3 puntos o más');
    var c = colorObj(sc, o), op = opac(o.opacidad, 0.3);
    cara(sc, ps, {color: c, op: op});
    poli(sc, ps.concat([ps[0]]), {color: U.mezcla(sc.P.tinta, c, 0.25), ancho: 1.75});
    if (o.nombre) texto(sc, centro(ps), o.nombre, {tipo: 'nombre'});
    if (o.angulos === true || /^(si|sí|true|1)$/i.test(String(o.angulos))) ps.forEach(function(p, i){   // los ángulos de cada vértice, con su valor
      marcaAngulo(sc, ps[(i + ps.length - 1) % ps.length], p, ps[(i + 1) % ps.length], 'valor', {radio: 0.22});
    });
  };
  HAZ.plano = function(sc, o){
    var n, p0;
    if (o.por){
      if (o.por.length !== 3) throw new Error('un plano va «por» tres puntos');
      var A = pt(o.por[0], 'por'), B = pt(o.por[1], 'por'), C = pt(o.por[2], 'por');
      n = cr(dif(B, A), dif(C, A)); p0 = A;
      if (lon(n) < 1e-12) throw new Error('los tres puntos están alineados: no definen un plano');
    } else if (o.ecuacion){
      var lados = String(o.ecuacion).split('=');
      if (lados.length !== 2) throw new Error('la ecuación del plano lleva un signo =, como «2x + y - z = 3»');
      var f = fun('(' + lados[0] + ')-(' + lados[1] + ')', ['x', 'y', 'z'], 'ecuacion'), f0 = f(0, 0, 0);
      n = [f(1, 0, 0) - f0, f(0, 1, 0) - f0, f(0, 0, 1) - f0];
      var prueba = f(1.3, -0.7, 2.1) - (f0 + n[0] * 1.3 - n[1] * 0.7 + n[2] * 2.1);
      if (Math.abs(prueba) > 1e-6 * (1 + Math.abs(f0) + lon(n))) throw new Error('la ecuación no es de un plano (debe ser lineal en x, y, z)');
      if (lon(n) < 1e-12) throw new Error('la ecuación no tiene x, y ni z');
      p0 = por(n, -f0 / pe(n, n));
    } else {
      n = pt(o.normal, 'normal'); p0 = o.punto ? pt(o.punto, 'punto') : [0, 0, 0];
      if (lon(n) < 1e-12) throw new Error('la normal mide 0');
    }
    n = uni(n);
    var c = colorObj(sc, o), op = opac(o.opacidad, 0.35);
    sc.diferidos.push(function(caja){
      var pol = planoEnCaja(n, p0, caja);
      if (pol.length < 3) return;
      var b = baseDe(n), q2 = pol.map(function(p){ return [pe(dif(p, p0), b[0]), pe(dif(p, p0), b[1])]; });
      var xs = q2.map(function(q){ return q[0]; }), ys = q2.map(function(q){ return q[1]; });
      var x0 = Math.min.apply(null, xs), x1 = Math.max.apply(null, xs), y0 = Math.min.apply(null, ys), y1 = Math.max.apply(null, ys), m = sc.rapido ? 3 : 6;
      var reg = {n: n, p0: p0, b: b, celdas: []};
      for (var i = 0; i < m; i++) for (var j = 0; j < m; j++){     // en celdas, para que se ordene bien con lo que lo cruza
        var rect = [x0 + (x1 - x0) * i / m, y0 + (y1 - y0) * j / m, x0 + (x1 - x0) * (i + 1) / m, y0 + (y1 - y0) * (j + 1) / m], celda = recortarConvexo(q2, rect);
        if (celda.length < 3) continue;
        var cf = cara(sc, celda.map(function(q){ return sum(p0, sum(por(b[0], q[0]), por(b[1], q[1]))); }), {color: c, op: op, n: n});
        cf.celda = true; reg.celdas.push({rect: rect, cara: cf});
      }
      (sc.planosCel = sc.planosCel || []).push(reg);
      poli(sc, pol.concat([pol[0]]), {color: U.mezcla(c, sc.P.tinta, 0.3), ancho: 1.25, oculta: 'guion'});
      if (o.nombre) texto(sc, pol[0], o.nombre, {tipo: 'nombre', col: c});
    });
  };
  HAZ.cubo = function(sc, o){
    var l = positivo(o.lado == null ? 1 : o.lado, 'lado'), a;
    if (o.centro) a = sum(pt(o.centro, 'centro'), [-l / 2, -l / 2, -l / 2]); else a = o.en || o.desde ? pt(o.en || o.desde, 'en') : [0, 0, 0];
    HAZ.caja(sc, {de: a, a: sum(a, [l, l, l]), color: o.color, opacidad: o.opacidad, ocultas: o.ocultas, nombre: o.nombre});
  };
  HAZ.caja = function(sc, o){
    var a = pt(o.de || o.desde, 'de'), b = pt(o.a || o.hasta, 'a');
    if (Math.abs(a[0] - b[0]) < 1e-12 || Math.abs(a[1] - b[1]) < 1e-12 || Math.abs(a[2] - b[2]) < 1e-12) throw new Error('la caja es plana: sus esquinas opuestas deben diferir en x, y y z');
    var V = [], i;
    for (i = 0; i < 8; i++) V.push([i & 1 ? b[0] : a[0], i & 2 ? b[1] : a[1], i & 4 ? b[2] : a[2]]);
    poliedro(sc, V, [[0, 1, 3, 2], [4, 5, 7, 6], [0, 1, 5, 4], [2, 3, 7, 6], [0, 2, 6, 4], [1, 3, 7, 5]], estiloSolido(sc, o), {tipo: 'caja'});
    if (o.nombre) texto(sc, b, o.nombre, {tipo: 'nombre'});
  };
  function puntosBase(o){
    var ps = (o.base || []).map(function(p, i){ return pt(p, 'base[' + i + ']'); });
    if (ps.length < 3) throw new Error('la base necesita 3 puntos o más');
    if (lon(cr(dif(ps[1], ps[0]), dif(ps[2], ps[0]))) < 1e-12 && lon(newell(ps)) < 0.5) throw new Error('los puntos de la base están alineados');
    return ps;
  }
  HAZ.prisma = function(sc, o){
    var B = puntosBase(o), n = newell(B), h;
    if (Array.isArray(o.altura)) h = pt(o.altura, 'altura');
    else { if (n[2] < 0 || (n[2] === 0 && n[1] < 0)) n = por(n, -1); h = por(n, numero(o.altura == null ? 1 : o.altura, 'altura')); }
    if (lon(h) < 1e-12) throw new Error('la altura es 0');
    var m = B.length, V = B.concat(B.map(function(p){ return sum(p, h); })), C = [B.map(function(_, i){ return i; }), B.map(function(_, i){ return m + i; })];
    for (var i = 0; i < m; i++) C.push([i, (i + 1) % m, m + (i + 1) % m, m + i]);
    poliedro(sc, V, C, estiloSolido(sc, o), {tipo: 'prisma'});
    if (o.nombre) texto(sc, sum(centro(B), h), o.nombre, {tipo: 'nombre'});
  };
  HAZ.piramide = function(sc, o){
    var B, V0;
    if (o.puntos && !o.base){ var t = o.puntos.map(function(p, i){ return pt(p, 'puntos[' + i + ']'); }); V0 = t.pop(); B = t; if (B.length < 3) throw new Error('la base necesita 3 puntos o más'); }
    else { B = puntosBase(o); V0 = pt(o.apice || o.vertice, 'apice'); }
    if (Math.abs(pe(newell(B), dif(V0, B[0]))) < 1e-12) throw new Error('el ápice está en el plano de la base');
    var m = B.length, V = B.concat([V0]), C = [B.map(function(_, i){ return i; })];
    for (var i = 0; i < m; i++) C.push([i, (i + 1) % m, m]);
    poliedro(sc, V, C, estiloSolido(sc, o), {tipo: 'piramide'});
    if (o.nombre) texto(sc, V0, o.nombre, {tipo: 'nombre'});
  };
  HAZ.cilindro = function(sc, o){
    var A = o.de || o.base ? pt(o.de || o.base, 'de') : [0, 0, 0], B = o.a || o.tope ? pt(o.a || o.tope, 'a') : sum(A, [0, 0, 1]), r = positivo(o.radio == null ? 1 : o.radio, 'radio');
    var eje = dif(B, A); if (lon(eje) < 1e-12) throw new Error('las dos bases coinciden');
    var n = sc.rapido ? 24 : 48, abajo = anillo(A, eje, r, n), arriba = abajo.map(function(p){ return sum(p, eje); }), C = [[], []], i;
    for (i = 0; i < n; i++){ C[0].push(i); C[1].push(n + i); C.push([i, (i + 1) % n, n + (i + 1) % n, n + i]); }
    var e = estiloSolido(sc, o); e.aristas = false;
    var s = poliedro(sc, abajo.concat(arriba), C, e, {tipo: 'cilindro', A: A, B: B, r: r, borde: e.borde});
    poli(sc, abajo.concat([abajo[0]]), {color: e.borde, ancho: 1.6, sol: s.id, oculta: o.ocultas === false ? 'nada' : 'guion'});
    poli(sc, arriba.concat([arriba[0]]), {color: e.borde, ancho: 1.6, sol: s.id, oculta: o.ocultas === false ? 'nada' : 'guion'});
    if (o.nombre) texto(sc, B, o.nombre, {tipo: 'nombre'});
  };
  HAZ.cono = function(sc, o){
    var A = o.base || o.de ? pt(o.base || o.de, 'base') : [0, 0, 0], V0 = o.apice || o.a ? pt(o.apice || o.a, 'apice') : sum(A, [0, 0, 1]), r = positivo(o.radio == null ? 1 : o.radio, 'radio');
    var eje = dif(V0, A); if (lon(eje) < 1e-12) throw new Error('el ápice coincide con el centro de la base');
    var n = sc.rapido ? 24 : 48, abajo = anillo(A, eje, r, n), C = [[]], i;
    for (i = 0; i < n; i++){ C[0].push(i); C.push([i, (i + 1) % n, n]); }
    var e = estiloSolido(sc, o); e.aristas = false;
    var s = poliedro(sc, abajo.concat([V0]), C, e, {tipo: 'cono', A: A, V: V0, r: r, borde: e.borde});
    poli(sc, abajo.concat([abajo[0]]), {color: e.borde, ancho: 1.6, sol: s.id, oculta: o.ocultas === false ? 'nada' : 'guion'});
    if (o.nombre) texto(sc, V0, o.nombre, {tipo: 'nombre'});
  };
  HAZ.esfera = function(sc, o){
    var C0 = o.centro ? pt(o.centro, 'centro') : [0, 0, 0], r = positivo(o.radio == null ? 1 : o.radio, 'radio');
    var nl = sc.rapido ? 10 : 16, nm = sc.rapido ? 20 : 32, V = [], Cs = [], i, j;
    for (i = 0; i <= nl; i++){
      var la = -Math.PI / 2 + Math.PI * i / nl;
      for (j = 0; j < nm; j++){ var lo = 2 * Math.PI * j / nm; V.push(sum(C0, [r * Math.cos(la) * Math.cos(lo), r * Math.cos(la) * Math.sin(lo), r * Math.sin(la)])); }
    }
    for (i = 0; i < nl; i++) for (j = 0; j < nm; j++){
      var a = i * nm + j, b = i * nm + (j + 1) % nm, c = (i + 1) * nm + (j + 1) % nm, d = (i + 1) * nm + j;
      if (i === 0) Cs.push([a, c, d]); else if (i === nl - 1) Cs.push([a, b, d]); else Cs.push([a, b, c, d]);
    }
    var e = estiloSolido(sc, o); e.aristas = false;
    var s = poliedro(sc, V, Cs, e, {tipo: 'esfera', C: C0, r: r, borde: e.borde});
    if (o.ecuador !== false){
      var eq = anillo(C0, [0, 0, 1], r, sc.rapido ? 32 : 64);
      poli(sc, eq.concat([eq[0]]), {color: e.borde, ancho: 1.25, sol: s.id, oculta: 'guion', op: 0.9});
    }
    if (o.nombre) texto(sc, sum(C0, [0, 0, r]), o.nombre, {tipo: 'nombre'});
  };
  HAZ.malla = function(sc, o){
    var V = (o.vertices || []).map(function(p, i){ return pt(p, 'vertices[' + i + ']'); });
    if (V.length < 3 || !Array.isArray(o.caras) || !o.caras.length) throw new Error('una malla necesita «vertices» y «caras»');
    var c = colorObj(sc, o), op = opac(o.opacidad, 0.9), aristas = {};
    o.caras.slice(0, 4000).forEach(function(ix){
      if (!Array.isArray(ix) || ix.length < 3) throw new Error('cada cara es una lista de 3 o más índices');
      ix.forEach(function(i){ if (!(i >= 0 && i < V.length && i === Math.floor(i))) throw new Error('índice de vértice fuera de rango: ' + i); });
      var p = ix.map(function(i){ return V[i]; });
      if (lon(newell(p)) > 0.5) cara(sc, p, {color: claro(sc, c), op: op});
      for (var i = 0; i < ix.length; i++){ var a = ix[i], b = ix[(i + 1) % ix.length]; aristas[Math.min(a, b) + ',' + Math.max(a, b)] = [a, b]; }
    });
    if (o.aristas !== false) Object.keys(aristas).forEach(function(kk){ poli(sc, [V[aristas[kk][0]], V[aristas[kk][1]]], {color: U.mezcla(sc.P.tinta, c, 0.25), ancho: 1.4}); });
  };
  function rampa(sc, t){                                    // color por altura: azul → turquesa → verde → amarillo
    var R = [sc.P.azul, sc.P.turquesa, sc.P.verde, sc.P.amarillo], x = Math.max(0, Math.min(1, t)) * (R.length - 1), i = Math.min(R.length - 2, Math.floor(x));
    return U.mezcla(R[i], R[i + 1], x - i);
  }
  function rejilla(sc, o, f, ur, vr, nombre){               // superficie de una función (u, v) → [x, y, z]; celdas que no existen se saltan
    var n = entero(o.n, sc.rapido ? 14 : 28, 4, 60), G = [], i, j, zs = [];
    for (i = 0; i <= n; i++){
      G.push([]);
      for (j = 0; j <= n; j++){
        var p = f(ur[0] + (ur[1] - ur[0]) * i / n, vr[0] + (vr[1] - vr[0]) * j / n);
        if (!p || !isFinite(p[0]) || !isFinite(p[1]) || !isFinite(p[2]) || Math.abs(p[2]) > 1e6) p = null;
        if (p && o.zr && (p[2] < o.zr[0] - 1e-9 || p[2] > o.zr[1] + 1e-9)) p = null;
        G[i].push(p); if (p) zs.push(p[2]);
      }
    }
    if (!zs.length) throw new Error(nombre + ' no existe en ese rango');
    var z0 = Math.min.apply(null, zs), z1 = Math.max.apply(null, zs), porAltura = !o.color || /^altura$/i.test(String(o.color));
    var base = porAltura ? null : U.colorDe(sc.P, o.color, sc.P.azul), op = opac(o.opacidad, 1), malla = o.malla !== false;
    for (i = 0; i < n; i++) for (j = 0; j < n; j++){
      var q = [G[i][j], G[i + 1][j], G[i + 1][j + 1], G[i][j + 1]];
      if (!q[0] || !q[1] || !q[2] || !q[3]) continue;
      var nn = uni(cr(dif(q[2], q[0]), dif(q[3], q[1])));
      if (lon(nn) < 0.5) continue;
      var zc = (q[0][2] + q[1][2] + q[2][2] + q[3][2]) / 4;
      cara(sc, q, {color: base || rampa(sc, z1 > z0 ? (zc - z0) / (z1 - z0) : 0.5), op: op, n: nn, malla: malla});
    }
  }
  HAZ.superficie = function(sc, o){
    var f = fun(o.f || o.z, ['x', 'y'], 'f'), xr = rango(o.x, [-2, 2], 'x'), yr = rango(o.y, [-2, 2], 'y');
    if (o.z && Array.isArray(o.z)) o.zr = rango(o.z, null, 'z');
    rejilla(sc, o, function(x, y){ return [x, y, f(x, y)]; }, xr, yr, 'la superficie');
    sc.supZ = true;
  };
  HAZ.parametrica = function(sc, o){
    var fx = fun(o.x, ['u', 'v'], 'x'), fy = fun(o.y, ['u', 'v'], 'y'), fz = fun(o.z, ['u', 'v'], 'z');
    var ur = rango(o.u, [0, 2 * Math.PI], 'u'), vr = rango(o.v, [0, 2 * Math.PI], 'v');
    rejilla(sc, o, function(u, v){ return [fx(u, v), fy(u, v), fz(u, v)]; }, ur, vr, 'la superficie');
  };
  HAZ.curva = function(sc, o){
    var fx = fun(o.x, ['t'], 'x'), fy = fun(o.y, ['t'], 'y'), fz = fun(o.z, ['t'], 'z'), tr = rango(o.t, [0, 2 * Math.PI], 't');
    var n = sc.rapido ? 90 : 220, c = colorObj(sc, o), tramo = [], hubo = false;
    for (var i = 0; i <= n; i++){
      var t = tr[0] + (tr[1] - tr[0]) * i / n, p = [fx(t), fy(t), fz(t)];
      if (isFinite(p[0]) && isFinite(p[1]) && isFinite(p[2])) tramo.push(p);
      else { if (tramo.length > 1){ poli(sc, tramo, {color: c, ancho: 2.5}); hubo = true; } tramo = []; }
    }
    if (tramo.length > 1){ poli(sc, tramo, {color: c, ancho: 2.5, flecha: !!o.flecha}); hubo = true; }
    if (!hubo) throw new Error('la curva no existe en ese rango de t');
    if (o.nombre) texto(sc, tramo[tramo.length - 1] || [fx(tr[1]), fy(tr[1]), fz(tr[1])], o.nombre, {tipo: 'nombre', col: c});
  };
  HAZ.campo = function(sc, o){
    var E;
    if (o.E){
      if (!Array.isArray(o.E) || o.E.length !== 3) throw new Error('«E» son tres expresiones en x, y, z');
      var fx = fun(o.E[0], ['x', 'y', 'z'], 'E'), fy = fun(o.E[1], ['x', 'y', 'z'], 'E'), fz = fun(o.E[2], ['x', 'y', 'z'], 'E');
      E = function(p){ return [fx(p[0], p[1], p[2]), fy(p[0], p[1], p[2]), fz(p[0], p[1], p[2])]; };
    }
    var c = colorObj(sc, o, sc.P.naranja), n = entero(o.n, 4, 2, 7), xr = o.x && rango(o.x, null, 'x'), yr = o.y && rango(o.y, null, 'y'), zr = o.z && rango(o.z, null, 'z');
    sc.diferidos.push(function(caja){
      var cargas = sc.cargas || [];
      if (!E){
        if (!cargas.length) throw new Error('el campo necesita «E» o cargas en la figura');
        E = function(p){ var s = [0, 0, 0]; cargas.forEach(function(q){ var d = dif(p, q.p), r = lon(d); if (r > 1e-9) s = sum(s, por(d, q.q / (r * r * r))); }); return s; };
      }
      var lado = Math.max.apply(null, caja.map(function(r){ return r[1] - r[0]; })), cub = caja.map(function(r){ var m = (r[0] + r[1]) / 2; return [m - lado / 2, m + lado / 2]; });
      var R = [xr || cub[0], yr || cub[1], zr || cub[2]], N = [n, n, n], fl = [], mags = [];
      // cargas en un mismo plano (y sin rango propio): el campo en ese plano, como en los libros; si no, rejilla 3D
      var plano = -1, mejor = 0, dv = [0.8, 0.46, 0.37];
      if (!o.E && cargas.length && !(xr || yr || zr) && o.plano !== false) [0, 1, 2].forEach(function(c){
        if (cargas.every(function(q){ return Math.abs(q.p[c] - cargas[0].p[c]) < 1e-9; }) && dv[c] > mejor){ mejor = dv[c]; plano = c; }
      });
      if (plano >= 0){ N = [2 * n - 1, 2 * n - 1, 2 * n - 1]; N[plano] = 1; R[plano] = [cargas[0].p[plano], cargas[0].p[plano]]; }
      var paso = [0, 1, 2].filter(function(c){ return N[c] > 1; }).reduce(function(t, c, ix, arr){ return t + (R[c][1] - R[c][0]) / N[c] / arr.length; }, 0);
      for (var i = 0; i < N[0]; i++) for (var j = 0; j < N[1]; j++) for (var k = 0; k < N[2]; k++){
        var p = [R[0][0] + (R[0][1] - R[0][0]) * (i + 0.5) / N[0], R[1][0] + (R[1][1] - R[1][0]) * (j + 0.5) / N[1], R[2][0] + (R[2][1] - R[2][0]) * (k + 0.5) / N[2]];
        if (cargas.some(function(q){ return lon(dif(p, q.p)) < paso * 0.45; })) continue;
        var v = E(p), m = lon(v);
        if (!isFinite(m) || m < 1e-12) continue;
        fl.push([p, v, m]); mags.push(m);
      }
      if (!fl.length) return;
      mags.sort(function(a, b){ return a - b; });
      var ref = mags[Math.floor(mags.length * 0.7)] || mags[mags.length - 1];
      fl.forEach(function(f){
        var L = paso * 0.75 * Math.max(0.35, Math.min(1, Math.pow(f[2] / ref, 0.35))), u = uni(f[1]);
        poli(sc, [sum(f[0], por(u, -L / 2)), sum(f[0], por(u, L / 2))], {color: c, ancho: 1.6, flecha: true, oculta: 'nada'});
      });
    });
  };
  HAZ.etiqueta = function(sc, o){ texto(sc, pt(o.en || o.p, 'en'), o.texto == null ? '' : o.texto, {tipo: 'nota', col: o.color ? U.colorDe(sc.P, o.color, sc.P.tinta) : null}); };
  HAZ.cota = function(sc, o){
    var a = pt(o.de, 'de'), b = pt(o.a, 'a'), L = lon(dif(b, a));
    poli(sc, [a, b], {color: sc.P.texto.tenue, ancho: 1.1, guion: [4, 3], oculta: 'nada', medida: true});
    texto(sc, interp(a, b, 0.5), o.texto != null ? o.texto : String(U.r2(L)), {tipo: 'medida'});
  };
  // marca de un ángulo en el vértice B (en el plano de A, B, C): modo 'valor' (arco y grados), 'marca' (n arcos, para ángulos iguales)
  // o 'recto' (el cuadradito). Es una medida: se apaga con «medidas».
  function marcaAngulo(sc, A, B, C, modo, o){
    var u = dif(A, B), w = dif(C, B);
    if (lon(u) < 1e-12 || lon(w) < 1e-12) throw new Error('el ángulo es degenerado: un extremo coincide con el vértice');
    var e1 = uni(u), e2 = uni(dif(w, por(e1, pe(w, e1)))), phi = Math.acos(Math.max(-1, Math.min(1, pe(e1, uni(w)))));
    if (lon(e2) < 0.5) throw new Error('los tres puntos están alineados');
    var rho = (o.radio || 0.3) * Math.min(lon(u), lon(w)), c = o.color ? U.colorDe(sc.P, o.color, sc.P.naranja) : sc.P.naranja, i, j;
    var recto = Math.abs(phi - Math.PI / 2) < 0.0175;
    if (modo === 'recto' && !recto) throw new Error('el ángulo no es recto (mide ' + U.r2(phi / GR) + '°)');
    sc.medida = true;
    try {
      if (modo === 'recto' || (modo === 'valor' && recto)){
        var s = rho * 0.6, q = [sum(B, por(e1, s)), sum(B, sum(por(e1, s), por(e2, s))), sum(B, por(e2, s))];
        cara(sc, [B].concat(q), {color: c, op: 0.25}); poli(sc, q, {color: c, ancho: 1.4, oculta: 'nada'});
      } else {
        var n = modo === 'marca' ? Math.max(1, Math.min(3, Math.round(o.n || 1))) : 1;
        for (j = 0; j < n; j++){
          var r = rho * (1 + 0.17 * j), arco = [];
          for (i = 0; i <= 24; i++){ var t = phi * i / 24; arco.push(sum(B, sum(por(e1, r * Math.cos(t)), por(e2, r * Math.sin(t))))); }
          if (!j) cara(sc, [B].concat(arco), {color: c, op: 0.22});
          poli(sc, arco, {color: c, ancho: 1.4, oculta: 'nada'});
        }
      }
      if (modo === 'valor' && !recto){                     // el recto ya lo dice el cuadradito
        var bis = sum(B, por(uni(sum(e1, por(uni(w), 1))), rho * 1.75));
        texto(sc, bis, (o.nombre ? o.nombre + ' = ' : '') + U.r2(phi / GR) + '°', {tipo: 'medida'});
      }
    } finally { sc.medida = false; }
  }
  HAZ.angulo = function(sc, o){ marcaAngulo(sc, pt(o.a, 'a'), pt(o.b || o.vertice, 'b'), pt(o.c, 'c'), 'valor', o); };
  HAZ.marcaangulo = function(sc, o){ marcaAngulo(sc, pt(o.a, 'a'), pt(o.b || o.vertice, 'b'), pt(o.c, 'c'), 'marca', o); };
  HAZ.angulorecto = function(sc, o){ marcaAngulo(sc, pt(o.a, 'a'), pt(o.b || o.vertice, 'b'), pt(o.c, 'c'), 'recto', o); };
  HAZ.marcaigual = function(sc, o){                         // rayitas de lados iguales (1, 2 o 3) en el medio de un segmento
    var a = pt(o.de, 'de'), b = pt(o.a, 'a');
    if (lon(dif(b, a)) < 1e-12) throw new Error('el segmento mide 0');
    sc.marcas.push({a: a, b: b, n: Math.max(1, Math.min(3, Math.round(o.n || 1))), color: o.color ? U.colorDe(sc.P, o.color, sc.P.tinta) : sc.P.tinta});
  };
  // ---- sólido de revolución: la región entre f y g en [a, b] gira alrededor de un eje horizontal (y = k) o vertical (x = k) ----
  // Plano de la región → espacio: la x sigue siendo x, la y de la región sube (z del espacio) y la profundidad es la otra; los ejes se
  // rotulan x, y (arriba) y z (fondo), como en el libro.
  function ejeRev(o){
    var e = String(o.eje == null ? 'x' : o.eje).replace(/\s+/g, '').toLowerCase(), m;
    if (e === 'x') return {h: true, k: o.en != null ? numero(o.en, 'en') : 0};
    if (e === 'y') return {h: false, k: o.en != null ? numero(o.en, 'en') : 0};
    if ((m = /^y=(.+)$/.exec(e))) return {h: true, k: numero(m[1], 'eje')};
    if ((m = /^x=(.+)$/.exec(e))) return {h: false, k: numero(m[1], 'eje')};
    throw new Error('«eje» es "x", "y", "y=2" o "x=-1"');
  }
  HAZ.revolucion = function(sc, o){
    var f = fun(o.f, ['x'], 'f'), E = ejeRev(o), g = o.g != null ? fun(o.g, ['x'], 'g') : (E.h ? function(){ return E.k; } : function(){ return 0; });
    var xr = rango(o.x, null, 'x'); if (!xr) throw new Error('falta el intervalo «x»: [a, b]');
    var ns = sc.rapido ? 12 : 22, nt = sc.rapido ? 20 : 36, arriba = [], abajo = [], i;
    for (i = 0; i <= ns; i++){
      var x = xr[0] + (xr[1] - xr[0]) * i / ns, fy = f(x), gy = g(x);
      if (!isFinite(fy) || !isFinite(gy)) throw new Error('f o g no están definidas en todo [' + U.r2(xr[0]) + ', ' + U.r2(xr[1]) + ']');
      arriba.push([x, fy]); abajo.push([x, gy]);
    }
    var lazo = arriba.concat(abajo.reverse()), L = [];
    lazo.forEach(function(p){ var q = L[L.length - 1]; if (!q || Math.hypot(p[0] - q[0], p[1] - q[1]) > 1e-9) L.push(p); });
    if (L.length > 2 && Math.hypot(L[0][0] - L[L.length - 1][0], L[0][1] - L[L.length - 1][1]) < 1e-9) L.pop();
    var area = 0; for (i = 0; i < L.length; i++){ var p1 = L[i], p2 = L[(i + 1) % L.length]; area += p1[0] * p2[1] - p2[0] * p1[1]; }
    if (Math.abs(area) < 1e-12) throw new Error('la región entre f y g no tiene área');
    if (area < 0) L.reverse();
    function lleva(p, th){ return E.h ? [p[0], (p[1] - E.k) * Math.sin(th), E.k + (p[1] - E.k) * Math.cos(th)] : [E.k + (p[0] - E.k) * Math.cos(th), (p[0] - E.k) * Math.sin(th), p[1]]; }
    function normal(n2, th){ return E.h ? [n2[0], n2[1] * Math.sin(th), n2[1] * Math.cos(th)] : [n2[0] * Math.cos(th), n2[0] * Math.sin(th), n2[1]]; }
    var ang = Math.max(10, Math.min(360, o.angulo == null ? 360 : numero(o.angulo, 'angulo'))) * GR;
    var frente = (E.h ? -67 : -60) * GR, th0 = ang >= 2 * Math.PI - 1e-9 ? 0 : frente + (2 * Math.PI - ang) / 2;
    var hayCorte = o.corte != null || o.capa != null, c = colorObj(sc, o, sc.P.azul), op = opac(o.opacidad, hayCorte ? 0.32 : 1);
    var s = solido(sc, {convexo: false, op: op}, {tipo: 'revolucion'}), m = Math.max(6, Math.round(nt * ang / (2 * Math.PI))), relleno = op < 1 ? c : claro(sc, c);
    for (i = 0; i < L.length; i++){
      var P1 = L[i], P2 = L[(i + 1) % L.length], dx = P2[0] - P1[0], dy = P2[1] - P1[1], ln = Math.hypot(dx, dy);
      if (ln < 1e-12) continue;
      var r1 = E.h ? Math.abs(P1[1] - E.k) : Math.abs(P1[0] - E.k), r2 = E.h ? Math.abs(P2[1] - E.k) : Math.abs(P2[0] - E.k);
      if (r1 < 1e-12 && r2 < 1e-12) continue;                                   // un borde sobre el eje no barre nada
      var n2 = [dy / ln, -dx / ln];
      for (var j = 0; j < m; j++){
        var ta = th0 + ang * j / m, tb = th0 + ang * (j + 1) / m, q = [lleva(P1, ta), lleva(P2, ta), lleva(P2, tb), lleva(P1, tb)];
        var lim = q.filter(function(v, ix){ return ix === 0 || lon(dif(v, q[ix - 1])) > 1e-12; });
        if (lim.length < 3) continue;
        cara(sc, lim, {color: relleno, op: op, n: uni(normal(n2, (ta + tb) / 2)), sol: s.id});
        s.caras.push(sc.caras.length - 1);
      }
    }
    if (ang < 2 * Math.PI - 1e-9){                                              // el corte deja ver la región que gira
      [th0, th0 + ang].forEach(function(th, ix){
        var pts = L.map(function(p){ return lleva(p, th); }), sg = 0;
        L.forEach(function(p){ sg += E.h ? p[1] - E.k : p[0] - E.k; });
        var t = E.h ? [0, Math.cos(th), -Math.sin(th)] : [-Math.sin(th), Math.cos(th), 0];
        var nn = por(t, (ix ? 1 : -1) * (sg >= 0 ? 1 : -1));
        cara(sc, pts, {color: hayCorte ? U.mezcla(c, sc.P.fondo, 0.35) : U.mezcla(sc.P.naranja, sc.P.fondo, 0.4), op: op, n: nn, sol: s.id});
        s.caras.push(sc.caras.length - 1);
        poli(sc, pts.concat([pts[0]]), {color: U.mezcla(sc.P.tinta, c, 0.3), ancho: 1.4, oculta: 'nada'});
      });
    }
    var A0 = E.h ? [xr[0], 0, E.k] : [E.k, 0, Math.min.apply(null, L.map(function(p){ return p[1]; }))];
    var A1 = E.h ? [xr[1], 0, E.k] : [E.k, 0, Math.max.apply(null, L.map(function(p){ return p[1]; }))];
    if (Math.abs(E.k) > 1e-12){                                                  // el eje de giro, si no es un eje de coordenadas
      var ext = por(uni(dif(A1, A0)), 0.15 * lon(dif(A1, A0)));
      poli(sc, [dif(A0, ext), sum(A1, ext)], {color: sc.P.rojo, ancho: 1.5, guion: [7, 4], oculta: 'nada'});
    }
    var D = (xr[1] - xr[0]) / 30, cc = sc.P.naranja;
    function cortes(c0, horizontalLinea){                                     // intervalos de la región sobre una recta (x = c0 o y = c0)
      var vs = [];
      for (var i2 = 0; i2 < L.length; i2++){
        var a2 = L[i2], b2 = L[(i2 + 1) % L.length], ia = horizontalLinea ? 1 : 0, ib = horizontalLinea ? 0 : 1;
        if ((a2[ia] - c0) * (b2[ia] - c0) < 0 || (a2[ia] === c0 && b2[ia] !== c0)){ var tt = (c0 - a2[ia]) / (b2[ia] - a2[ia]); vs.push(a2[ib] + (b2[ib] - a2[ib]) * tt); }
      }
      vs.sort(function(a3, b3){ return a3 - b3; });
      var out = []; for (var i3 = 0; i3 + 1 < vs.length; i3 += 2) if (vs[i3 + 1] - vs[i3] > 1e-9) out.push([vs[i3], vs[i3 + 1]]);
      return out;
    }
    function punto(sEje){ return E.h ? [sEje, 0, E.k] : [E.k, 0, sEje]; }
    if (o.corte != null){                                                       // disco o arandela: perpendicular al eje
      var c0 = numero(o.corte, 'corte'), iv = cortes(c0, !E.h);
      if (!iv.length) throw new Error('el corte en ' + U.r2(c0) + ' no toca la región');
      iv.forEach(function(I){
        var ra = Math.abs(I[0] - E.k), rb = Math.abs(I[1] - E.k), rIn = (I[0] - E.k) * (I[1] - E.k) < 0 ? 0 : Math.min(ra, rb), rOut = Math.max(ra, rb);
        rodaja(sc, punto(c0 - D / 2), punto(c0 + D / 2), rIn, rOut, cc);
      });
    }
    if (o.capa != null){                                                        // casquete cilíndrico: paralelo al eje
      var c1 = numero(o.capa, 'capa'), iv2 = cortes(c1, E.h), rr = Math.abs(c1 - E.k);
      if (!iv2.length) throw new Error('la capa en ' + U.r2(c1) + ' no toca la región');
      iv2.forEach(function(I){ rodaja(sc, punto(I[0]), punto(I[1]), Math.max(0, rr - D / 2), rr + D / 2, cc); });
    }
    sc.rev = sc.rev || E;
  };
  function rodaja(sc, A, B, r1, r2, color){                // anillo grueso (disco si r1 = 0) alrededor del eje A→B
    var eje = dif(B, A), n = sc.rapido ? 24 : 40, ua = uni(eje), fo = anillo([0, 0, 0], eje, 1, n), s = solido(sc, {convexo: r1 < 1e-12}, {tipo: 'rodaja'});
    function ring(c, r){ return fo.map(function(v){ return sum(c, por(v, r)); }); }
    var oa = ring(A, r2), ob = ring(B, r2), ia = r1 > 1e-12 ? ring(A, r1) : null, ib = ia ? ring(B, r1) : null, i, rell = claro(sc, color);
    function add(p, nn){ cara(sc, p, {color: rell, op: 1, n: nn, sol: s.id}); s.caras.push(sc.caras.length - 1); }
    for (i = 0; i < n; i++){
      var j = (i + 1) % n;
      add([oa[i], oa[j], ob[j], ob[i]], uni(sum(fo[i], fo[j])));
      if (ia) add([ia[i], ia[j], ib[j], ib[i]], por(uni(sum(fo[i], fo[j])), -1));
    }
    cara(sc, oa, {color: rell, op: 1, n: por(ua, -1), sol: s.id, huecos: ia ? [ia] : null}); s.caras.push(sc.caras.length - 1);
    cara(sc, ob, {color: rell, op: 1, n: ua, sol: s.id, huecos: ib ? [ib] : null}); s.caras.push(sc.caras.length - 1);
    var b = U.mezcla(sc.P.tinta, color, 0.3);
    [oa, ob].concat(ia ? [ia, ib] : []).forEach(function(r){ poli(sc, r.concat([r[0]]), {color: b, ancho: 1.2, sol: s.id, oculta: 'nada'}); });
  }

  // ---- recortes contra la caja de la escena ----
  function recorteCaja(a, d, caja){                         // t0, t1 de a + t·d dentro de la caja, o null
    var t0 = -Infinity, t1 = Infinity;
    for (var i = 0; i < 3; i++){
      if (Math.abs(d[i]) < 1e-15){ if (a[i] < caja[i][0] || a[i] > caja[i][1]) return null; continue; }
      var ta = (caja[i][0] - a[i]) / d[i], tb = (caja[i][1] - a[i]) / d[i];
      t0 = Math.max(t0, Math.min(ta, tb)); t1 = Math.min(t1, Math.max(ta, tb));
    }
    return t1 > t0 ? [t0, t1] : null;
  }
  function planoEnCaja(n, p0, caja){                        // polígono (convexo, ordenado) del plano dentro de la caja
    var c = pe(n, p0), V = [], E = [], i, pts = [];
    for (i = 0; i < 8; i++) V.push([caja[0][i & 1], caja[1][(i >> 1) & 1], caja[2][(i >> 2) & 1]]);
    [[0, 1], [2, 3], [4, 5], [6, 7], [0, 2], [1, 3], [4, 6], [5, 7], [0, 4], [1, 5], [2, 6], [3, 7]].forEach(function(e){ E.push([V[e[0]], V[e[1]]]); });
    E.forEach(function(e){
      var da = pe(n, e[0]) - c, db = pe(n, e[1]) - c;
      if (Math.abs(da) < 1e-12) pts.push(e[0]);
      if (da * db < 0) pts.push(interp(e[0], e[1], da / (da - db)));
    });
    var uniq = [];
    pts.forEach(function(p){ if (!uniq.some(function(q){ return lon(dif(p, q)) < 1e-9; })) uniq.push(p); });
    if (uniq.length < 3) return [];
    var cc = centro(uniq), b = baseDe(n);
    uniq.sort(function(p, q){ return Math.atan2(pe(dif(p, cc), b[1]), pe(dif(p, cc), b[0])) - Math.atan2(pe(dif(q, cc), b[1]), pe(dif(q, cc), b[0])); });
    return uniq;
  }
  function recortarConvexo(pol, r){                         // Sutherland–Hodgman: polígono 2D ∩ rectángulo [x0, y0, x1, y1]
    var out = pol;
    [[0, r[0], 1], [0, r[2], -1], [1, r[1], 1], [1, r[3], -1]].forEach(function(lim){
      var ent = out; out = [];
      for (var i = 0; i < ent.length; i++){
        var a = ent[i], b = ent[(i + 1) % ent.length], ia = (a[lim[0]] - lim[1]) * lim[2] >= 0, ib = (b[lim[0]] - lim[1]) * lim[2] >= 0;
        if (ia) out.push(a);
        if (ia !== ib){ var t = (lim[1] - a[lim[0]]) / (b[lim[0]] - a[lim[0]]); out.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]); }
      }
    });
    return out;
  }

  // =====================================================================================================
  // 3. Cerrar la escena: caja, proporción, ejes, troceado de líneas y planos de cada sólido
  // =====================================================================================================
  function recorrer(sc, f){
    sc.caras.forEach(function(c){ c.p.forEach(f); if (c.huecos) c.huecos.forEach(function(h){ h.forEach(f); }); });
    sc.polis.forEach(function(l){ l.pts.forEach(f); });
    sc.puntos.forEach(function(p){ f(p.p); });
    sc.textos.forEach(function(t){ f(t.p); });
  }
  function limites(sc){
    var lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity], hay = false;
    recorrer(sc, function(p){ hay = true; for (var i = 0; i < 3; i++){ if (p[i] < lo[i]) lo[i] = p[i]; if (p[i] > hi[i]) hi[i] = p[i]; } });
    return hay ? [lo, hi] : null;
  }
  function cerrar(sc, spec){
    var b = limites(sc), caja = [], i;
    for (i = 0; i < 3; i++){
      var ext = b ? [b[0][i], b[1][i]] : [-2, 2], nom = 'xyz'.charAt(i);
      if (spec[nom] && Array.isArray(spec[nom])) ext = rango(spec[nom], ext, nom);
      caja.push(ext);
    }
    var tam = Math.max(caja[0][1] - caja[0][0], caja[1][1] - caja[1][0], caja[2][1] - caja[2][0], 1e-9);
    for (i = 0; i < 3; i++){                                // la caja de los diferidos (planos, rectas, campos): algo más holgada
      var nom2 = 'xyz'.charAt(i);
      if (spec[nom2] && Array.isArray(spec[nom2])) continue;
      if (!b){ caja[i] = [-2, 2]; continue; }
      var m = Math.max(0.1 * tam, (caja[i][1] - caja[i][0]) < 0.2 * tam ? (0.2 * tam - (caja[i][1] - caja[i][0])) / 2 : 0);
      caja[i] = [caja[i][0] - m, caja[i][1] + m];
    }
    sc.diferidos.forEach(function(fn){ fn(caja); });
    partirEnPlanos(sc, tam);
    b = limites(sc);
    if (!b) return false;
    // proporción: 'igual' (geometría) o 'cubo' (cada eje estirado a la misma longitud: superficies muy altas o muy planas)
    var R = [0, 1, 2].map(function(j){ return b[1][j] - b[0][j]; }), Rmax = Math.max.apply(null, R), S = [1, 1, 1];
    var prop = String(spec.proporcion || 'auto').toLowerCase(), validos = R.filter(function(r){ return r > 1e-6 * Rmax; });
    var cubo = prop === 'cubo' || (prop === 'auto' && sc.supZ && validos.length === 3 && Rmax / Math.min.apply(null, validos) > 3);
    if (cubo){
      for (i = 0; i < 3; i++) S[i] = R[i] > 1e-6 * Rmax ? Rmax / R[i] : 1;
      var esc = function(p){ p[0] *= S[0]; p[1] *= S[1]; p[2] *= S[2]; };
      var vistos = new Set();
      recorrer(sc, function(p){ if (!vistos.has(p)){ vistos.add(p); esc(p); } });
      sc.caras.forEach(function(c){ c.n = uni([c.n[0] / S[0], c.n[1] / S[1], c.n[2] / S[2]]); });
      sc.solidos.forEach(function(s){ s.deformado = true; });
      b = limites(sc);
    }
    sc.S = S;
    ejes(sc, b, S, spec);                                    // siempre: «ejes» y «numeros» se apagan al dibujar
    // centro y radio de todo (para encuadrar y trocear), con ejes y sin ellos
    var todos = [], deEjes = new Set();
    sc.polis.forEach(function(l){ if (l.eje) l.pts.forEach(function(p){ deEjes.add(p); }); });
    sc.textos.forEach(function(t){ if (t.tipo === 'eje' || t.tipo === 'tick') deEjes.add(t.p); });
    recorrer(sc, function(p){ todos.push(p); });
    var nucleo = todos.filter(function(p){ return !sc.textos.some(function(t){ return t.tipo === 'eje' && t.p === p; }); }), E = esferaMin(nucleo);
    var sinEjes = todos.filter(function(p){ return !deEjes.has(p); }), E2 = sinEjes.length ? esferaMin(sinEjes) : E;
    sc.centro = E.c; sc.radio = Math.max(E.r, 1e-9); sc.todos = todos;
    sc.sinEjes = {centro: E2.c, radio: Math.max(E2.r, 1e-9), todos: sinEjes.length ? sinEjes : todos};
    // líneas: cada polilínea en trozos cortos (ordenan bien con las caras y se ocultan por partes)
    var maxL = sc.radio / (sc.rapido ? 10 : 18), g = 0;
    sc.lineas = [];
    sc.polis.forEach(function(l){ g++; trocear(sc.lineas, l, maxL, g); });
    sc.caras.forEach(function(c){ c.pc = pe(c.n, c.p[0]); });
    // planos de cada sólido convexo (para saber qué tapa)
    sc.solidos.forEach(function(s){
      s.planos = s.caras.map(function(ix){ var c = sc.caras[ix]; return {n: c.n, c: pe(c.n, c.p[0])}; });
      var ps = []; s.caras.forEach(function(ix){ ps = ps.concat(sc.caras[ix].p); });
      s.centro = centro(ps); s.radio = 0; ps.forEach(function(p){ var d = lon(dif(p, s.centro)); if (d > s.radio) s.radio = d; });
    });
    return true;
  }
  // lo plano que cae dentro de un plano (un triángulo en su plano) se parte con las celdas del plano y cada trozo se pinta con su celda
  function partirEnPlanos(sc, tam){
    (sc.planosCel || []).forEach(function(R){
      var n0 = sc.caras.length;
      for (var ic = 0; ic < n0; ic++){
        var c = sc.caras[ic];
        if (c.celda || c.quitar || c.sol >= 0 || Math.abs(pe(c.n, R.n)) < 0.9999) continue;
        if (c.p.some(function(p){ return Math.abs(pe(dif(p, R.p0), R.n)) > 1e-7 * (1 + tam); })) continue;
        var q2 = c.p.map(function(p){ return [pe(dif(p, R.p0), R.b[0]), pe(dif(p, R.p0), R.b[1])]; });
        c.quitar = true;
        R.celdas.forEach(function(ce){
          var pz = recortarConvexo(q2, ce.rect);
          if (pz.length < 3) return;
          var f = cara(sc, pz.map(function(q){ return sum(R.p0, sum(por(R.b[0], q[0]), por(R.b[1], q[1]))); }), {color: c.color, op: c.op, n: c.n});
          f.ancla = ce.cara; f.idx = c.idx;
        });
      }
    });
  }
  function esferaMin(ps){                                  // esfera que lo encierra todo, casi mínima (Ritter): girar no cambia el tamaño
    if (!ps.length) return {c: [0, 0, 0], r: 1};
    function lejos(a){ var m = a, dm = -1; ps.forEach(function(p){ var d = lon(dif(p, a)); if (d > dm){ dm = d; m = p; } }); return m; }
    var b = lejos(ps[0]), c2 = lejos(b), c = interp(b, c2, 0.5), r = lon(dif(c2, b)) / 2;
    ps.forEach(function(p){ var d = lon(dif(p, c)); if (d > r){ var nr = (r + d) / 2; c = sum(c, por(dif(p, c), (nr - r) / d)); r = nr; } });
    return {c: c, r: r};
  }
  function trocear(out, l, maxL, g){
    var idx = 0;
    for (var i = 0; i + 1 < l.pts.length; i++){
      var a = l.pts[i], b = l.pts[i + 1], m = Math.max(1, Math.ceil(lon(dif(b, a)) / maxL));
      for (var j = 0; j < m; j++) out.push({a: interp(a, b, j / m), b: interp(a, b, (j + 1) / m), g: g, i: idx++, l: l, flecha: l.flecha && i === l.pts.length - 2 && j === m - 1});
    }
  }
  function ejes(sc, b, S, spec){
    var P = sc.P, nombres = Array.isArray(spec.nombresEjes) && spec.nombresEjes.length === 3 ? spec.nombresEjes.map(String) : (sc.rev ? ['x', 'z', 'y'] : ['x', 'y', 'z']);
    var Lt = Math.max(b[1][0] - b[0][0], b[1][1] - b[0][1], b[1][2] - b[0][2], 1e-9), pad = 0.14 * Lt;
    for (var i = 0; i < 3; i++){
      var d = [0, 0, 0]; d[i] = 1;
      var lo = Math.min(0, b[0][i]), hi = Math.max(0, b[1][i]);
      var a0 = lo - (lo < -1e-9 ? 0.06 * Lt : 0), a1 = Math.max(hi, 0.3 * Lt) + pad;
      poli(sc, [por(d, a0), por(d, a1)], {color: P.ejes.color, ancho: P.ejes.grosor, flecha: true, oculta: 'guion', eje: true});
      texto(sc, por(d, a1 + 0.07 * Lt), nombres[i], {tipo: 'eje'});
      if (spec.numeros === false || (sc.rev && i === 1)) continue;
      var reales = U.ticksNum(lo / S[i], hi / S[i], 4);
      reales.forEach(function(v){
        if (Math.abs(v) < 1e-12 || v * S[i] > a1 - pad * 0.7 || v * S[i] < a0) return;
        texto(sc, por(d, v * S[i]), U.etiquetaNum(v), {tipo: 'tick', dir: d, fin: por(d, a1)});
      });
    }
  }

  // =====================================================================================================
  // 4. Mirar y dibujar: cámara, qué tapa a qué, orden de pintor y SVG
  // =====================================================================================================
  function camara(az, el){
    var A = az * GR, E = el * GR, d = [Math.cos(E) * Math.cos(A), Math.cos(E) * Math.sin(A), Math.sin(E)], r = [-Math.sin(A), Math.cos(A), 0];
    return {d: d, r: r, u: cr(d, r)};
  }
  function tapa(p, d, sol, tol){                            // ¿el rayo de p hacia la cámara entra en el sólido convexo (encogido tol)?
    var oc = dif(p, sol.centro), t = pe(oc, d), q = lon(dif(oc, por(d, t)));
    if (q > sol.radio) return false;
    var t0 = 0, t1 = Infinity, pl = sol.planos;
    for (var i = 0; i < pl.length; i++){
      var nd = pe(pl[i].n, d), np = pe(pl[i].n, p) - (pl[i].c - tol);
      if (Math.abs(nd) < 1e-12){ if (np > 0) return false; continue; }
      var tt = -np / nd;
      if (nd > 0){ if (tt < t1) t1 = tt; } else if (tt > t0) t0 = tt;
      if (t0 >= t1) return false;
    }
    return t1 > t0;
  }
  function siluetas(sc, cam){                               // líneas de contorno de cilindros y conos para esta vista
    var out = [];
    sc.solidos.forEach(function(s){
      var D = s.datos, n;
      if (s.deformado || !(D.tipo === 'cilindro' || D.tipo === 'cono')) return;
      var pts = [];
      if (D.tipo === 'cilindro'){
        var ax = uni(dif(D.B, D.A)), w = cr(ax, cam.d);
        if (lon(w) < 1e-3) return;
        w = uni(w);
        pts = [[sum(D.A, por(w, D.r)), sum(D.B, por(w, D.r))], [sum(D.A, por(w, -D.r)), sum(D.B, por(w, -D.r))]];
      } else {
        var a = dif(D.V, D.A), h = lon(a), ax2 = uni(a), b = baseDe(ax2), e1d = pe(b[0], cam.d), e2d = pe(b[1], cam.d), rho = Math.hypot(e1d, e2d), q = -D.r * pe(ax2, cam.d) / h;
        if (rho < 1e-9 || Math.abs(q) > rho) return;
        var al = Math.atan2(e2d, e1d), dl = Math.acos(q / rho);
        [al + dl, al - dl].forEach(function(f){ pts.push([sum(D.A, sum(por(b[0], D.r * Math.cos(f)), por(b[1], D.r * Math.sin(f)))), D.V]); });
      }
      pts.forEach(function(sg){
        n = {pts: sg, color: D.borde, ancho: 1.6, oculta: 'guion', sol: s.id, op: 1};
        trocear(out, n, sc.radio / 18, 'sil' + s.id + '_' + out.length);
      });
    });
    return out;
  }
  function encuadre(sc, cam, W, k, modo, conEjes){
    var M = Math.round(30 * k), H, s, cx, cy, B = conEjes ? sc : sc.sinEjes;
    if (modo === 'esfera'){
      H = Math.round(W * 0.78); s = (Math.min(W, H) - 2 * M) / (2 * B.radio);
      cx = pe(B.centro, cam.r); cy = pe(B.centro, cam.u);
    } else {
      var x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
      B.todos.forEach(function(p){ var x = pe(p, cam.r), y = pe(p, cam.u); if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; });
      var bw = Math.max(x1 - x0, 1e-9), bh = Math.max(y1 - y0, 1e-9), Hmax = W * 1.1;
      s = (W - 2 * M) / bw;
      if (bh * s > Hmax - 2 * M) s = (Hmax - 2 * M) / bh;
      H = Math.round(Math.max(bh * s + 2 * M, W * 0.42));
      cx = (x0 + x1) / 2; cy = (y0 + y1) / 2;
    }
    return {W: W, H: H, s: s, f: function(p){ return [W / 2 + s * (pe(p, cam.r) - cx), H / 2 - s * (pe(p, cam.u) - cy)]; }};
  }
  function n1(v){ return Math.round(v * 10) / 10; }
  function orden(a, b){                                     // pintor; dos caras en el mismo plano: la que se definió después va encima
    if (a.t === 'c' && b.t === 'c' && a.c.sol !== b.c.sol){
      var ca = pe(a.c.n, b.c.n);
      if (Math.abs(ca) > 0.9999 && Math.abs(a.c.pc * (ca > 0 ? 1 : -1) - b.c.pc) < 1e-7 * (1 + Math.abs(b.c.pc))) return a.c.idx - b.c.idx;
    }
    return a.prof - b.prof;
  }
  function camino(pts){ return pts.map(function(q, i){ return (i ? 'L' : 'M') + n1(q[0]) + ' ' + n1(q[1]); }).join('') + 'Z'; }

  function dibujar(sc, vista, opts){
    opts = opts || {};
    var A = {}, kk;                                          // anotaciones: las de la spec, y encima las de opts.anotaciones (los botones)
    for (kk in sc.anot) A[kk] = sc.anot[kk];
    if (opts.anotaciones) for (kk in A) if (opts.anotaciones[kk] != null) A[kk] = !!opts.anotaciones[kk];
    var P = sc.P, k = sc.k, W = U.anchoDe(opts), cam = camara(vista[0], vista[1]), d = cam.d, Q = encuadre(sc, cam, W, k, opts.encuadre === 'esfera' ? 'esfera' : 'justo', A.ejes);
    var Lz = uni(sum(sum(por(cam.r, -0.4), por(cam.u, 0.65)), por(d, 0.7))), oscuro = P.modo === 'oscuro', tol = 1e-5 * sc.radio, bias = 0.004 * sc.radio;
    var tapan = sc.solidos.filter(function(s){ return s.convexo && s.opaco && s.planos.length >= 4; });
    var grupos = {}, items = [];
    tapan.forEach(function(s){ grupos[s.id] = {prof: pe(s.centro, d), antes: [], caras: [], vis: [], ocu: [], extra: [], s: s}; });
    // caras: las de atrás de un sólido cerrado opaco no se ven
    sc.caras.forEach(function(c){
      if (c.quitar || (c.medida && !A.medidas)) return;
      var nd = pe(c.n, d), sol = c.sol >= 0 ? sc.solidos[c.sol] : null;
      if (sol && sol.cerrado && sol.opaco && nd <= 1e-9) return;
      var cc = centro(c.p), it = {t: 'c', c: c, prof: c.ancla ? pe(centro(c.ancla.p), d) + 1e-6 * sc.radio : pe(cc, d), nd: nd};
      if (sol && grupos[sol.id]){ grupos[sol.id].caras.push(it); return; }
      for (var i = 0; i < tapan.length; i++) if (tapa(cc, d, tapan[i], tol)){ grupos[tapan[i].id].antes.push(it); return; }   // detrás de un sólido: va antes que él
      items.push(it);
    });
    // líneas: si un sólido opaco las tapa, a trazos dentro de su grupo (o nada)
    sc.lineas.concat(siluetas(sc, cam)).forEach(function(l){
      if ((l.l.eje && !A.ejes) || (l.l.medida && !A.medidas)) return;
      var m = interp(l.a, l.b, 0.5), quien = null;
      for (var i = 0; i < tapan.length; i++) if (tapa(m, d, tapan[i], tol)){ quien = tapan[i]; break; }
      if (quien){ if (l.l.oculta === 'guion') grupos[quien.id].ocu.push(l); return; }
      var it = {t: 'l', l: l, prof: pe(m, d) + bias};
      if (l.l.sol >= 0 && grupos[l.l.sol]) grupos[l.l.sol].vis.push(it); else items.push(it);
    });
    sc.solidos.forEach(function(s){                         // contorno de la esfera
      if (s.datos.tipo !== 'esfera' || s.deformado) return;
      var it = {t: 'o', s: s, prof: pe(s.datos.C, d) + s.datos.r};
      if (grupos[s.id]) grupos[s.id].extra.push(it); else items.push(it);
    });
    tapan.forEach(function(s){                              // un sólido dentro de otro (su centro dentro): va antes, y el de fuera lo tapa
      tapan.forEach(function(t){
        if (s !== t && s.radio <= t.radio && t.planos.every(function(pl){ return pe(pl.n, s.centro) <= pl.c + tol; }))
          grupos[s.id].prof = Math.min(grupos[s.id].prof, grupos[t.id].prof - 1e-3 * sc.radio);
      });
    });
    Object.keys(grupos).forEach(function(id){ items.push({t: 'g', g: grupos[id], prof: grupos[id].prof}); });
    sc.textos.forEach(function(t){                          // los números de los ejes se tapan como cualquier cosa
      if (t.tipo !== 'tick' || !A.ejes || !A.numeros || tapan.some(function(s){ return tapa(t.p, d, s, tol); })) return;
      items.push({t: 'k', x: t, prof: pe(t.p, d) + 2 * bias});
    });
    if (A.medidas) sc.marcas.forEach(function(m){ items.push({t: 'm', m: m, prof: pe(interp(m.a, m.b, 0.5), d) + 2 * bias}); });
    items.sort(orden);

    var out = [], ocupados = [];
    function anchoTexto(t, tam, peso){ return String(t).length * tam * (peso >= 600 ? 0.6 : 0.55); }
    function choca(b){ return ocupados.some(function(o){ return b[0] < o[0] + o[2] && o[0] < b[0] + b[2] && b[1] < o[1] + o[3] && o[1] < b[1] + b[3]; }); }
    function luz(c, nd){
      var n = nd >= 0 ? c.n : por(c.n, -1), I = 0.5 + 0.5 * Math.max(0, pe(n, Lz)), col = U.mezcla(c.color, oscuro ? '#000000' : '#101426', (1 - I) * (oscuro ? 0.62 : 0.5));
      return nd < 0 ? U.mezcla(col, P.fondo, 0.2) : col;
    }
    function pintaCara(it){
      var c = it.c, col = luz(c, it.nd), dd = camino(c.p.map(Q.f)), at = '';
      if (c.huecos){ c.huecos.forEach(function(h){ dd += camino(h.map(Q.f)); }); at = ' fill-rule="evenodd"'; }
      if (c.malla) at += ' stroke="' + U.mezcla(col, oscuro ? '#000000' : '#0b0f1e', 0.3) + '" stroke-width="' + n1(0.5 * k) + '"';
      else if (c.op >= 0.999) at += ' stroke="' + col + '" stroke-width="0.6" stroke-linejoin="round"';
      out.push('<path d="' + dd + '" fill="' + col + '"' + (c.op < 0.999 ? ' fill-opacity="' + U.r2(c.op) + '"' : '') + at + '/>');
    }
    function pintaLinea(l, oculta){
      var a = Q.f(l.a), b = Q.f(l.b), L = l.l, w = L.ancho * k * (oculta ? 0.8 : 1);
      var s = '<path d="M' + n1(a[0]) + ' ' + n1(a[1]) + 'L' + n1(b[0]) + ' ' + n1(b[1]) + '" stroke="' + L.color + '" stroke-width="' + n1(w) + '" stroke-linecap="round" fill="none"';
      if (L.guion) s += ' stroke-dasharray="' + L.guion.map(function(v){ return n1(v * k); }).join(' ') + '"';
      if (L.op < 1) s += ' stroke-opacity="' + U.r2(L.op) + '"';
      out.push(s + '/>');
      if (l.flecha){
        var ux = b[0] - a[0], uy = b[1] - a[1], ln = Math.hypot(ux, uy), largo = (L.ancho >= 2 ? 10 : 7) * k;
        var total = Math.hypot.apply(null, [0, 1].map(function(i){ return Q.f(L.pts[L.pts.length - 1])[i] - Q.f(L.pts[0])[i]; }));
        if (ln > 1e-6 && total > largo * 1.2) out.push(U.punta(b[0], b[1], ux / ln, uy / ln, largo, largo * 0.75, L.color));
      }
    }
    function pintaOcultas(ls){                              // a trazos, unidas por polilínea para que el guion no se corte
      ls.sort(function(a, b){ return a.g === b.g ? a.i - b.i : (String(a.g) < String(b.g) ? -1 : 1); });
      var i = 0;
      while (i < ls.length){
        var j = i, pts = [Q.f(ls[i].a), Q.f(ls[i].b)];
        while (j + 1 < ls.length && ls[j + 1].g === ls[i].g && ls[j + 1].i === ls[j].i + 1){ j++; pts.push(Q.f(ls[j].b)); }
        var L = ls[i].l;
        out.push('<path d="' + pts.map(function(q, ix){ return (ix ? 'L' : 'M') + n1(q[0]) + ' ' + n1(q[1]); }).join('') + '" stroke="' + L.color + '" stroke-width="' + n1(L.ancho * k * 0.8) +
                 '" stroke-dasharray="' + n1(4.5 * k) + ' ' + n1(3.5 * k) + '" stroke-opacity="0.55" stroke-linecap="round" fill="none"/>');
        i = j + 1;
      }
    }
    function pintaMarca(t){
      var q = Q.f(t.p), o = Q.f(sum(t.p, t.dir)), ux = o[0] - q[0], uy = o[1] - q[1], ln = Math.hypot(ux, uy);
      if (ln < 1e-6) return;
      if (t.fin){ var f = Q.f(t.fin); if (Math.hypot(f[0] - q[0], f[1] - q[1]) < 22 * k) return; }   // pegado a la punta del eje: se encimaría
      var px = -uy / ln, py = ux / ln;
      if (py < 0 || (Math.abs(py) < 0.2 && px > 0)){ px = -px; py = -py; }
      out.push('<path d="M' + n1(q[0] - px * 3 * k) + ' ' + n1(q[1] - py * 3 * k) + 'L' + n1(q[0] + px * 3 * k) + ' ' + n1(q[1] + py * 3 * k) + '" stroke="' + P.ejes.color + '" stroke-width="' + n1(1.2 * k) + '"/>');
      var tn = P.numeros.tam * k;
      var tx = q[0] + px * (7 * k + tn * 0.5), ty = q[1] + py * (7 * k + tn * 0.5), tw = anchoTexto(t.texto, tn, P.numeros.peso);
      out.push(U.textoSvg(P, tx, ty + tn * 0.35, t.texto, {tam: tn, peso: P.numeros.peso, col: P.numeros.color, hg: 2.5 * k}));
      ocupados.push([tx - tw / 2, ty - tn / 2, tw, tn]);
    }
    function pintaIgual(m){                                 // n rayitas perpendiculares al lado, en su punto medio
      var a = Q.f(m.a), b = Q.f(m.b), ux = b[0] - a[0], uy = b[1] - a[1], ln = Math.hypot(ux, uy);
      if (ln < 4 * k) return;
      ux /= ln; uy /= ln;
      var mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2, px = -uy, py = ux, L = 6 * k, sep = 4 * k, dd = '';
      for (var i = 0; i < m.n; i++){
        var o = (i - (m.n - 1) / 2) * sep, cx = mx + ux * o, cy = my + uy * o;
        dd += 'M' + n1(cx - px * L) + ' ' + n1(cy - py * L) + 'L' + n1(cx + px * L) + ' ' + n1(cy + py * L);
      }
      out.push('<path d="' + dd + '" stroke="' + m.color + '" stroke-width="' + n1(1.6 * k) + '" stroke-linecap="round" fill="none"/>');
    }
    function pintaContorno(it){
      var D = it.s.datos, c = Q.f(D.C);
      out.push('<circle cx="' + n1(c[0]) + '" cy="' + n1(c[1]) + '" r="' + n1(D.r * Q.s) + '" fill="none" stroke="' + D.borde + '" stroke-width="' + n1(1.6 * k) + '"/>');
    }
    items.forEach(function(it){
      if (it.t === 'c') pintaCara(it);
      else if (it.t === 'l') pintaLinea(it.l, false);
      else if (it.t === 'o') pintaContorno(it);
      else if (it.t === 'k') pintaMarca(it.x);
      else if (it.t === 'm') pintaIgual(it.m);
      else {
        var g = it.g;
        g.antes.sort(orden).forEach(pintaCara);
        g.caras.sort(orden).forEach(pintaCara);
        pintaOcultas(g.ocu);
        g.vis.sort(function(a, b){ return a.prof - b.prof; }).forEach(function(v){ pintaLinea(v.l, false); });
        g.extra.forEach(pintaContorno);
      }
    });
    // puntos (los tapados, huecos y tenues) y textos encima de todo
    var cen = Q.f(A.ejes ? sc.centro : sc.sinEjes.centro);
    sc.textos.forEach(function(t){                          // los rótulos de los ejes y los puntos, antes que los nombres que se colocan
      if (t.tipo !== 'eje' || !A.ejes) return;
      var q = Q.f(t.p), te = P.ejes.etiqueta.tam * k, w = anchoTexto(t.texto, te, 500);
      ocupados.push([q[0] - w / 2 - 2, q[1] - te / 2, w + 4, te]);
    });
    sc.puntos.forEach(function(p){ var q = Q.f(p.p), r = 5 * k; ocupados.push([q[0] - r, q[1] - r, 2 * r, 2 * r]); });
    sc.puntos.forEach(function(p){
      var q = Q.f(p.p), oculto = tapan.some(function(s){ return tapa(p.p, d, s, tol); }), r = (p.q != null ? 8 : P.punto.radio) * k;
      if (p.q != null){
        out.push('<circle cx="' + n1(q[0]) + '" cy="' + n1(q[1]) + '" r="' + n1(r) + '" fill="' + p.color + '" stroke="' + P.fondo + '" stroke-width="' + n1(1.5 * k) + '"' + (oculto ? ' opacity="0.5"' : '') + '/>');
        out.push('<path d="M' + n1(q[0] - r * 0.5) + ' ' + n1(q[1]) + 'H' + n1(q[0] + r * 0.5) + (p.q >= 0 ? 'M' + n1(q[0]) + ' ' + n1(q[1] - r * 0.5) + 'V' + n1(q[1] + r * 0.5) : '') +
                 '" stroke="#ffffff" stroke-width="' + n1(1.8 * k) + '" stroke-linecap="round"/>');
      } else if (oculto) out.push('<circle cx="' + n1(q[0]) + '" cy="' + n1(q[1]) + '" r="' + n1(r) + '" fill="' + P.fondo + '" stroke="' + p.color + '" stroke-width="' + n1(1.4 * k) + '" opacity="0.65"/>');
      else out.push('<circle cx="' + n1(q[0]) + '" cy="' + n1(q[1]) + '" r="' + n1(r) + '" fill="' + p.color + '" stroke="' + P.punto.borde + '" stroke-width="' + n1(P.punto.bordeGrosor * k) + '"/>');
      if (p.nombre && A.nombres) etiquetaJunto(q, r, p.nombre, P.etiqueta.tam * k, P.etiqueta.peso, null);
    });
    function etiquetaJunto(q, r, t, tam, peso, col){         // hacia fuera de la figura; si choca con otro texto, prueba las otras 7 direcciones
      var dx = q[0] - cen[0], dy = q[1] - cen[1], ln = Math.hypot(dx, dy), w = anchoTexto(t, tam, peso), elegido = null;
      if (ln < 1){ dx = 0.7; dy = -0.7; ln = 1; }
      var a0 = Math.atan2(dy / ln, dx / ln);
      [0, 1, -1, 2, -2, 3, -3, 4].some(function(paso){
        var a = a0 + paso * Math.PI / 4, ux = Math.cos(a), uy = Math.sin(a), sep = r + 6 * k;
        var anc = ux > 0.35 ? 'start' : ux < -0.35 ? 'end' : 'middle', x = q[0] + ux * sep, yc = q[1] + uy * (sep + tam * 0.35);
        var x0 = anc === 'start' ? x : anc === 'end' ? x - w : x - w / 2, b = [x0, yc - tam / 2, w, tam];
        var cand = {x: x, y: yc + tam * 0.35, anc: anc, b: b};
        if (!elegido) elegido = cand;
        if (!choca(b)){ elegido = cand; return true; }
        return false;
      });
      ocupados.push(elegido.b);
      out.push(U.textoSvg(P, elegido.x, elegido.y, t, {tam: tam, peso: peso, anc: elegido.anc, col: col || P.etiqueta.color, hg: P.etiqueta.haloGrosor * k}));
    }
    sc.textos.forEach(function(t){
      var q = Q.f(t.p);
      if (t.tipo === 'tick' || (t.tipo === 'eje' && !A.ejes) || ((t.tipo === 'nombre' || t.tipo === 'nota') && !A.nombres) || (t.tipo === 'medida' && !A.medidas)) return;
      if (t.tipo === 'eje'){
        var te = P.ejes.etiqueta.tam * k;
        out.push(U.textoSvg(P, q[0], q[1] + te * 0.35, t.texto, {tam: te, peso: P.ejes.etiqueta.peso, cur: true, col: P.ejes.etiqueta.color, hg: 3 * k}));
      } else if (t.tipo === 'nombre') etiquetaJunto(q, 2 * k, t.texto, P.etiqueta.tam * k, P.etiqueta.peso, t.col);
      else if (t.tipo === 'nota') etiquetaJunto(q, 4 * k, t.texto, P.texto.tam * k, P.texto.peso, t.col || P.texto.color);
      else {
        var tm = P.medida.tam * k;
        out.push(U.textoSvg(P, q[0], q[1] + tm * 0.35, t.texto, {tam: tm, peso: P.medida.peso, col: t.col || P.texto.color, hg: 3 * k}));
      }
    });
    var fondo = U.colorFondo(opts, P), cab = U.cabecera(Q.W, Q.H, [0, 0, Q.W, Q.H], sc.titulo || 'Figura 3D');
    return {svg: cab + (fondo ? '<rect width="' + Q.W + '" height="' + Q.H + '" fill="' + fondo + '"/>' : '') + out.join('') + '</svg>',
            w: Q.W, h: Q.H, vista: [U.r2(vista[0]), U.r2(vista[1])]};
  }

  // =====================================================================================================
  // 5. API: escena, figura, guion
  // =====================================================================================================
  function objetosDe(spec){
    if (Array.isArray(spec.objetos)) return spec.objetos;
    var atajo = [];                                         // atajos: {"superficie": "x^2-y^2", "x": [...], "y": [...]} · {"revolucion": "sqrt(x)", "x": [0, 4]}
    if (spec.superficie) atajo.push({tipo: 'superficie', f: spec.superficie, x: spec.x, y: spec.y, color: spec.color});
    if (spec.revolucion) atajo.push({tipo: 'revolucion', f: spec.revolucion, g: spec.g, x: spec.x, eje: spec.eje, angulo: spec.angulo, corte: spec.corte, capa: spec.capa});
    return atajo;
  }
  function vistaDe(v, def){
    if (Array.isArray(v) && v.length === 2 && isFinite(+v[0]) && isFinite(+v[1])) return [+v[0], Math.max(-89, Math.min(89, +v[1]))];
    return def;
  }
  function escena(spec, opts){
    opts = opts || {};
    if (typeof spec === 'string'){ try { spec = JSON.parse(spec); } catch (e){ throw new Error('el JSON de la figura 3D no se entiende: ' + e.message); } }
    if (!spec || typeof spec !== 'object') throw new Error('la figura 3D es un objeto JSON');
    var P = U.estiloDe(opts), k = U.escalaDe(opts), sc = nueva(P, k, opts.rapido), errores = [];
    sc.titulo = spec.titulo ? String(spec.titulo).slice(0, 120) : '';
    sc.anot = {ejes: spec.ejes !== false, numeros: spec.numeros !== false, nombres: spec.nombres !== false, medidas: spec.medidas !== false};
    var objs = objetosDe(spec), relleno = String(opts.relleno || spec.relleno || '').toLowerCase();
    if (relleno === 'opaco' || relleno === 'transparente') objs = objs.map(function(o){   // el interruptor global manda sobre cada objeto
      if (!o || typeof o !== 'object' || !CON_RELLENO.test(String(o.tipo || ''))) return o;
      var c = {}, kk; for (kk in o) c[kk] = o[kk];
      c.opacidad = relleno === 'opaco' ? 1 : Math.min(opac(o.opacidad, 1), 0.35);
      return c;
    });
    if (objs.length > 300) throw new Error('demasiados objetos (máximo 300)');
    // primero las cargas (el campo las usa), luego lo demás en su orden
    var orden = objs.map(function(o, i){ return i; }).sort(function(a, b){ var ca = /^carga$/i.test(objs[a] && objs[a].tipo) ? 0 : 1, cb = /^carga$/i.test(objs[b] && objs[b].tipo) ? 0 : 1; return ca - cb || a - b; });
    orden.forEach(function(i){
      var o = objs[i];
      try {
        if (!o || typeof o !== 'object') throw new Error('cada objeto es un {…}');
        var nD = sc.diferidos.length;
        var t = tipoDe(o);
        HAZ[t](sc, o);
        if (sc.diferidos.length > nD){                      // los diferidos también avisan en su objeto
          var fns = sc.diferidos.splice(nD);
          fns.forEach(function(fn){ sc.diferidos.push(function(caja){ try { fn(caja); } catch (e){ errores.push({objeto: i, mensaje: e.message}); } }); });
        }
      } catch (e){ errores.push({objeto: i, mensaje: e.message}); }
    });
    var hay = cerrar(sc, spec);
    var defecto = sc.rev ? (sc.rev.h ? [-70, 18] : [-60, 22]) : [30, 22];
    var vista0 = vistaDe(spec.vista, defecto);
    errores.sort(function(a, b){ return a.objeto - b.objeto; });
    return {
      vista: vista0, errores: errores, vacia: !hay,
      dibujar: function(vista, o2){
        var o3 = {}, kk;
        for (kk in opts) o3[kk] = opts[kk];
        if (o2) for (kk in o2) o3[kk] = o2[kk];
        if (!hay) return {svg: '', w: 0, h: 0, vista: vista0, errores: errores};
        var r = dibujar(sc, vistaDe(vista, vista0), o3);
        r.errores = errores;
        return r;
      }
    };
  }
  function figura(spec, opts){
    opts = opts || {};
    var e;
    try { e = escena(spec, opts); }
    catch (err){ return {svg: '', w: 0, h: 0, vista: null, errores: [{objeto: -1, mensaje: err.message}]}; }
    return e.dibujar(opts.vista || e.vista, opts);
  }

  // ---- el lenguaje 3D de la pestaña Geometría (como el de MathStudio: nombre = comando(…), una instrucción por línea) ----
  var SOLO3D = {esfera: 1, cubo: 1, caja: 1, ortoedro: 1, paralelepipedo: 1, prisma: 1, piramide: 1, tetraedro: 1, cilindro: 1, cono: 1, plano: 1,
                superficie: 1, curva: 1, revolucion: 1, vista: 1, vector: 1, carga: 1, campo: 1, sphere: 1, cube: 1, cylinder: 1, cone: 1, plane: 1, surface: 1, prism: 1, pyramid: 1};
  var OPCIONES = {color: 1, opacidad: 1, eje: 1, angulo: 1, corte: 1, capa: 1, malla: 1, ocultas: 1, n: 1, en: 1, ecuador: 1, flecha: 1, angulos: 1};
  function sinComentario(s){
    var cita = false;
    for (var i = 0; i < s.length; i++){
      var c = s.charAt(i);
      if (c === '"') cita = !cita;
      if (!cita && (c === '#' || (c === '/' && s.charAt(i + 1) === '/'))) return s.slice(0, i);
    }
    return s;
  }
  function tuplaLiteral(s){                                 // «(1, 2, 3)» → ['1', '2', '3'] o null
    s = s.trim();
    if (s.charAt(0) !== '(' || s.charAt(s.length - 1) !== ')') return null;
    var prof = 0;
    for (var i = 0; i < s.length; i++){ var c = s.charAt(i); if (c === '(') prof++; if (c === ')') prof--; if (prof === 0 && i < s.length - 1) return null; }
    var partes = U.partirTop(s.slice(1, -1), ',');
    return partes.length >= 2 && partes.length <= 3 ? partes.map(function(x){ return x.trim(); }) : null;
  }
  function es3d(texto){
    return String(texto == null ? '' : texto).split(/\r?\n/).some(function(crudo){
      var t = sinComentario(crudo), m, re = /([\p{L}_][\p{L}\p{N}_]*)\s*\(/gu;
      while ((m = re.exec(t))) if (tiene(SOLO3D, U.claveNorm(m[1]))) return true;
      for (var i = 0; i < t.length; i++){                    // un paréntesis que no es de un comando: ¿una terna (x, y, z)?
        if (t.charAt(i) !== '(' || /[\p{L}\p{N}_]/u.test(t.charAt(i - 1) || '')) continue;
        var prof = 0, j;
        for (j = i; j < t.length; j++){ if (t.charAt(j) === '(') prof++; if (t.charAt(j) === ')'){ prof--; if (!prof) break; } }
        var tu = tuplaLiteral(t.slice(i, j + 1));
        if (tu && tu.length === 3) return true;
      }
      return false;
    });
  }
  function aSpec(texto){
    var spec = {objetos: []}, errores = [], S = {}, lineaActual = 0;
    function constante(s, que){ try { var v = F.compilar(s, {constante: true})(0); if (!isFinite(v)) throw 0; return v; } catch (e){ throw new Error('«' + s + '» no es un número' + (que ? ' (' + que + ')' : '')); } }
    function valor(s){                                      // un argumento: punto, vector, número o nombre
      s = s.trim();
      var tu = tuplaLiteral(s);
      if (tu) return {tipo: 'punto', p: tu.map(function(x){ return constante(x, 'coordenada'); }).concat(tu.length === 2 ? [0] : [])};
      if (tiene(S, s)) return S[s];
      var cab = /^([\p{L}_][\p{L}\p{N}_]*)\s*\(([\s\S]*)\)$/u.exec(s);
      if (cab && U.claveNorm(cab[1]) === 'puntomedio') return comando(cab[1], cab[2]);
      return {tipo: 'numero', v: constante(s)};
    }
    function parLado(s){                                    // «AB» → [A, B] si son dos puntos con nombre
      s = String(s || '').trim();
      if (tiene(S, s) || !/^[\p{L}_][\p{L}\p{N}_]*$/u.test(s)) return null;
      for (var i = 1; i < s.length; i++){
        var x = s.slice(0, i), y = s.slice(i);
        if (tiene(S, x) && tiene(S, y) && S[x].tipo === 'punto' && S[y].tipo === 'punto') return [S[x].p, S[y].p];
      }
      return null;
    }
    function P(s){
      var v = valor(s);
      if (v.tipo === 'punto') return v.p;
      if (v.tipo === 'vector') return v.v;
      throw new Error('«' + s.trim() + '» no es un punto');
    }
    function N(s){ var v = valor(s); if (v.tipo !== 'numero') throw new Error('«' + s.trim() + '» no es un número'); return v.v; }
    function partirArgs(cuerpo){
      var args = cuerpo.trim() ? U.partirTop(cuerpo, ',').map(function(a){ return a.trim(); }) : [], ops = {};
      args = args.filter(function(a){
        var m = /^([\p{L}_]+)\s*=\s*([\s\S]+)$/u.exec(a);
        if (m && tiene(OPCIONES, U.claveNorm(m[1]))){ ops[U.claveNorm(m[1])] = m[2].trim().replace(/^"|"$/g, ''); return false; }
        return true;
      });
      return {a: args, o: ops};
    }
    function cuantos(args, n, uso){ if (args.length !== n) throw new Error('se escribe ' + uso); }
    function comando(nombreCmd, cuerpo, nombre){
      var c = U.claveNorm(nombreCmd), x = partirArgs(cuerpo), a = x.a, o = x.o, obj = null;
      if (tiene(ALIAS_TIPO, c) && ['triangulo', 'tetraedro', 'ortoedro', 'paralelepipedo'].indexOf(c) < 0) c = ALIAS_TIPO[c];
      function con(t){ t._linea = lineaActual; for (var kk in o) if (t[kk] == null) t[kk] = o[kk]; if (nombre && t.nombre == null && t.tipo === 'vector') t.nombre = nombre; spec.objetos.push(t); return t; }
      switch (c){
        case 'punto': cuantos(a, 3, 'punto(x, y, z)'); return {tipo: 'punto', p: a.map(function(s){ return N(s); })};
        case 'puntomedio': cuantos(a, 2, 'puntomedio(A, B)'); return {tipo: 'punto', p: interp(P(a[0]), P(a[1]), 0.5)};
        case 'segmento': cuantos(a, 2, 'segmento(A, B)'); con({tipo: 'segmento', de: P(a[0]), a: P(a[1])}); break;
        case 'recta': cuantos(a, 2, 'recta(A, B)'); con({tipo: 'recta', por: [P(a[0]), P(a[1])]}); break;
        case 'vector':
          if (a.length === 1){ var v1 = P(a[0]); con({tipo: 'vector', v: v1}); return {tipo: 'vector', v: v1}; }
          cuantos(a, 2, 'vector(A, B) o vector((x, y, z))');
          var A1 = P(a[0]), B1 = P(a[1]); con({tipo: 'vector', de: A1, a: B1}); return {tipo: 'vector', v: dif(B1, A1)};
        case 'poligono': case 'triangulo':
          if (c === 'triangulo') cuantos(a, 3, 'triangulo(A, B, C)');
          if (a.length < 3) throw new Error('un polígono necesita 3 puntos o más');
          con({tipo: 'poligono', puntos: a.map(P)}); break;
        case 'plano':
          if (a.length === 1 && /=/.test(a[0])) con({tipo: 'plano', ecuacion: a[0]});
          else if (a.length === 3) con({tipo: 'plano', por: a.map(P)});
          else if (a.length === 2) con({tipo: 'plano', punto: P(a[0]), normal: P(a[1])});
          else throw new Error('se escribe plano(A, B, C), plano(A, normal) o plano(2x + y - z = 3)');
          break;
        case 'esfera': cuantos(a, 2, 'esfera(centro, radio)'); con({tipo: 'esfera', centro: P(a[0]), radio: N(a[1])}); break;
        case 'cubo': cuantos(a, 2, 'cubo(A, lado)'); con({tipo: 'cubo', en: P(a[0]), lado: N(a[1])}); break;
        case 'caja': case 'ortoedro': case 'paralelepipedo': cuantos(a, 2, c + '(A, B) con A y B esquinas opuestas'); con({tipo: 'caja', de: P(a[0]), a: P(a[1])}); break;
        case 'prisma':
          if (a.length < 4) throw new Error('se escribe prisma(A, B, C, …, altura)');
          con({tipo: 'prisma', base: a.slice(0, -1).map(P), altura: N(a[a.length - 1])}); break;
        case 'piramide': case 'tetraedro':
          if (c === 'tetraedro') cuantos(a, 4, 'tetraedro(A, B, C, D)');
          if (a.length < 4) throw new Error('se escribe piramide(A, B, C, …, ápice)');
          con({tipo: 'piramide', base: a.slice(0, -1).map(P), apice: P(a[a.length - 1])}); break;
        case 'cilindro': cuantos(a, 3, 'cilindro(A, B, radio): A y B, los centros de las bases'); con({tipo: 'cilindro', de: P(a[0]), a: P(a[1]), radio: N(a[2])}); break;
        case 'cono': cuantos(a, 3, 'cono(centro de la base, ápice, radio)'); con({tipo: 'cono', base: P(a[0]), apice: P(a[1]), radio: N(a[2])}); break;
        case 'superficie':
          if (a.length !== 1 && a.length !== 5) throw new Error('se escribe superficie(x^2 - y^2) o superficie(x^2 - y^2, xmin, xmax, ymin, ymax)');
          con({tipo: 'superficie', f: a[0], x: a.length === 5 ? [N(a[1]), N(a[2])] : undefined, y: a.length === 5 ? [N(a[3]), N(a[4])] : undefined}); break;
        case 'curva': cuantos(a, 5, 'curva(x(t), y(t), z(t), tmin, tmax)'); con({tipo: 'curva', x: a[0], y: a[1], z: a[2], t: [N(a[3]), N(a[4])]}); break;
        case 'revolucion':
          if (a.length === 3) con({tipo: 'revolucion', f: a[0], x: [N(a[1]), N(a[2])]});
          else if (a.length === 4) con({tipo: 'revolucion', f: a[0], g: a[1], x: [N(a[2]), N(a[3])]});
          else throw new Error('se escribe revolucion(f, a, b) o revolucion(f, g, a, b), y si quieres eje=y, angulo=300, corte=2, capa=1');
          var r = spec.objetos[spec.objetos.length - 1];
          ['angulo', 'corte', 'capa'].forEach(function(kk){ if (r[kk] != null) r[kk] = N(String(r[kk])); });
          break;
        case 'carga': cuantos(a, 2, 'carga(A, q)'); con({tipo: 'carga', en: P(a[0]), q: N(a[1])}); break;
        case 'campo': con({tipo: 'campo'}); break;
        case 'distancia':
          cuantos(a, 2, 'distancia(A, B)');
          var dA = P(a[0]), dB = P(a[1]), dv = lon(dif(dB, dA));
          con({tipo: 'cota', de: dA, a: dB, texto: (nombre ? nombre + ' = ' : '') + U.r2(dv)}); return {tipo: 'numero', v: dv};
        case 'angulo':
          cuantos(a, 3, 'angulo(A, B, C), con B el vértice');
          con({tipo: 'angulo', a: P(a[0]), b: P(a[1]), c: P(a[2]), nombre: nombre}); return {tipo: 'objeto'};
        case 'marcaangulo':
          if (a.length !== 3 && a.length !== 4) throw new Error('se escribe marcaangulo(A, B, C) o marcaangulo(A, B, C, n), con B el vértice y n = 1, 2 o 3 arcos');
          con({tipo: 'marcaangulo', a: P(a[0]), b: P(a[1]), c: P(a[2]), n: a[3] ? N(a[3]) : 1}); return {tipo: 'nota'};
        case 'angulorecto': cuantos(a, 3, 'angulorecto(A, B, C), con B el vértice'); con({tipo: 'angulorecto', a: P(a[0]), b: P(a[1]), c: P(a[2])}); return {tipo: 'nota'};
        case 'marcaigual':
          var lado = parLado(a[0]);                         // marcaigual(AB, n) como en geometría plana, o marcaigual(A, B, n)
          if (lado){ if (a.length > 2) throw new Error('se escribe marcaigual(AB, n) o marcaigual(A, B, n)'); con({tipo: 'marcaigual', de: lado[0], a: lado[1], n: a[1] ? N(a[1]) : 1}); }
          else { if (a.length !== 2 && a.length !== 3) throw new Error('se escribe marcaigual(AB, n) o marcaigual(A, B, n)'); con({tipo: 'marcaigual', de: P(a[0]), a: P(a[1]), n: a[2] ? N(a[2]) : 1}); }
          return {tipo: 'nota'};
        case 'nombres': spec.nombres = !/^(no|false|0)$/i.test((a[0] || '').trim()); return {tipo: 'nota'};
        case 'medidas': spec.medidas = !/^(no|false|0)$/i.test((a[0] || '').trim()); return {tipo: 'nota'};
        case 'relleno':
          if (!/^(opaco|transparente)$/i.test((a[0] || '').trim())) throw new Error('se escribe relleno(opaco) o relleno(transparente)');
          spec.relleno = a[0].trim().toLowerCase(); return {tipo: 'nota'};
        case 'etiqueta': cuantos(a, 2, 'etiqueta(A, "texto")'); con({tipo: 'etiqueta', en: P(a[0]), texto: a[1].replace(/^"|"$/g, '')}); return {tipo: 'nota'};
        case 'vista': cuantos(a, 2, 'vista(giro, altura) en grados, por ejemplo vista(30, 20)'); spec.vista = [N(a[0]), N(a[1])]; return {tipo: 'nota'};
        case 'ejes': spec.ejes = !/^(no|false|0|ninguno)$/i.test((a[0] || '').trim()); return {tipo: 'nota'};
        case 'numeros': spec.numeros = !/^(no|false|0)$/i.test((a[0] || '').trim()); return {tipo: 'nota'};
        case 'proporcion': spec.proporcion = /cubo/i.test(a[0] || '') ? 'cubo' : 'igual'; return {tipo: 'nota'};
        default: throw new Error('«' + nombreCmd + '» no existe en 3D' + (c === 'circunferencia' || c === 'arco' || c === 'sector' ? ' (es de geometría plana: usa puntos (x, y) sin z)' : ''));
      }
      return {tipo: 'objeto'};
    }
    String(texto == null ? '' : texto).split(/\r?\n/).forEach(function(crudo, ix){
      var linea = ix + 1, t = sinComentario(crudo).trim();
      if (!t) return;
      lineaActual = linea;
      try {
        var partes = U.partirTop(t, '='), nombre = null, expr = t;
        if (partes.length >= 2 && /^[\p{L}_][\p{L}\p{N}_]*$/u.test(partes[0].trim())){ nombre = partes[0].trim(); expr = partes.slice(1).join('=').trim(); }
        if (nombre && tiene(S, nombre)) throw new Error('El nombre «' + nombre + '» está repetido.');
        var cab = /^([\p{L}_][\p{L}\p{N}_]*)\s*\(([\s\S]*)\)$/u.exec(expr), v;
        if (cab && !tuplaLiteral(expr)) v = comando(cab[1], cab[2], nombre);
        else v = valor(expr);
        if (v.tipo === 'punto'){
          if (!nombre) throw new Error('Un punto necesita nombre: A = (1, 2, 3).');
          spec.objetos.push({tipo: 'punto', en: v.p, nombre: nombre, _linea: linea});
        } else if (!nombre && v.tipo === 'numero') throw new Error('Un número necesita nombre: r = 2.');
        if (nombre) S[nombre] = v;
      } catch (e){ errores.push({linea: linea, mensaje: e.message}); }
    });
    return {spec: spec, errores: errores};
  }
  function guion(texto, opts){
    var a = aSpec(texto), r = figura(a.spec, opts || {}), errs = a.errores.slice();
    (r.errores || []).forEach(function(e){                  // errores de construcción → la línea de su objeto
      var o = a.spec.objetos[e.objeto], ln = o && o._linea;
      errs.push({linea: ln || 0, mensaje: e.mensaje});
    });
    errs.sort(function(x, y){ return x.linea - y.linea; });
    r.errores = errs; r.spec = a.spec;
    return r;
  }

  // ---- de la spec JSON (```3d del chat) al guion de la pestaña Geometría; null si algo no tiene comando en el guion ----
  function aGuion(spec){
    if (typeof spec === 'string'){ try { spec = JSON.parse(spec); } catch (e){ return null; } }
    if (!spec || typeof spec !== 'object') return null;
    var L = [], n = 0;
    function num(v){ return typeof v === 'number' ? String(U.r2(v) === v ? v : parseFloat(v.toPrecision(10))) : String(v); }
    function P(p){ return Array.isArray(p) ? '(' + p.map(num).concat(p.length === 2 ? ['0'] : []).join(', ') + ')' : null; }
    function ops(o, extra){
      var r = [];
      if (o.color) r.push('color=' + o.color);
      if (o.opacidad != null) r.push('opacidad=' + num(o.opacidad));
      (extra || []).forEach(function(k){ if (o[k] != null) r.push(k + '=' + num(o[k])); });
      return r.length ? ', ' + r.join(', ') : '';
    }
    function nom(o, pre){ return o.nombre && /^[\p{L}_][\p{L}\p{N}_]*$/u.test(o.nombre) ? o.nombre : pre + (++n); }
    var ok = objetosDe(spec).every(function(o){
      var t; try { t = tipoDe(o); } catch (e){ return false; }
      switch (t){
        case 'punto': L.push(nom(o, 'P') + ' = ' + P(o.en || o.p)); return !!P(o.en || o.p);
        case 'segmento': L.push(nom(o, 's') + ' = segmento(' + P(o.de || o.desde) + ', ' + P(o.a || o.hasta) + ops(o) + ')'); return true;
        case 'recta': if (!o.por) return false; L.push(nom(o, 'r') + ' = recta(' + P(o.por[0]) + ', ' + P(o.por[1]) + ops(o) + ')'); return true;
        case 'vector':
          if (o.v) L.push(nom(o, 'v') + ' = vector(' + (o.de ? P(o.de) + ', ' + P(sum(pt(o.de, 'de'), pt(o.v, 'v'))) : P(o.v)) + ops(o) + ')');
          else L.push(nom(o, 'v') + ' = vector(' + P(o.de || [0, 0, 0]) + ', ' + P(o.a || o.hasta) + ops(o) + ')');
          return true;
        case 'poligono': L.push(nom(o, 'pol') + ' = poligono(' + (o.puntos || []).map(P).join(', ') + ops(o, ['angulos']) + ')'); return true;
        case 'plano':
          if (o.por) L.push(nom(o, 'pl') + ' = plano(' + o.por.map(P).join(', ') + ops(o) + ')');
          else if (o.ecuacion) L.push(nom(o, 'pl') + ' = plano(' + o.ecuacion + ops(o) + ')');
          else L.push(nom(o, 'pl') + ' = plano(' + P(o.punto || [0, 0, 0]) + ', ' + P(o.normal) + ops(o) + ')');
          return true;
        case 'esfera': L.push(nom(o, 'e') + ' = esfera(' + P(o.centro || [0, 0, 0]) + ', ' + num(o.radio == null ? 1 : o.radio) + ops(o) + ')'); return true;
        case 'cubo':
          var l = o.lado == null ? 1 : o.lado, en = o.centro ? sum(pt(o.centro, 'centro'), [-l / 2, -l / 2, -l / 2]) : (o.en || o.desde || [0, 0, 0]);
          L.push(nom(o, 'c') + ' = cubo(' + P(en) + ', ' + num(l) + ops(o) + ')'); return true;
        case 'caja': L.push(nom(o, 'c') + ' = caja(' + P(o.de || o.desde) + ', ' + P(o.a || o.hasta) + ops(o) + ')'); return true;
        case 'prisma': if (Array.isArray(o.altura)) return false; L.push(nom(o, 'pr') + ' = prisma(' + (o.base || []).map(P).join(', ') + ', ' + num(o.altura == null ? 1 : o.altura) + ops(o) + ')'); return true;
        case 'piramide': if (!o.base) return false; L.push(nom(o, 'pi') + ' = piramide(' + o.base.map(P).join(', ') + ', ' + P(o.apice || o.vertice) + ops(o) + ')'); return true;
        case 'cilindro': L.push(nom(o, 'ci') + ' = cilindro(' + P(o.de || o.base || [0, 0, 0]) + ', ' + P(o.a || o.tope || [0, 0, 1]) + ', ' + num(o.radio == null ? 1 : o.radio) + ops(o) + ')'); return true;
        case 'cono': L.push(nom(o, 'co') + ' = cono(' + P(o.base || o.de || [0, 0, 0]) + ', ' + P(o.apice || o.a || [0, 0, 1]) + ', ' + num(o.radio == null ? 1 : o.radio) + ops(o) + ')'); return true;
        case 'superficie':
          var xr = o.x || [-2, 2], yr = o.y || [-2, 2];
          L.push(nom(o, 'S') + ' = superficie(' + (o.f || o.z) + ', ' + [xr[0], xr[1], yr[0], yr[1]].map(num).join(', ') + ops(o) + ')'); return true;
        case 'curva': var tr = o.t || [0, 2 * Math.PI]; L.push(nom(o, 'C') + ' = curva(' + [o.x, o.y, o.z].join(', ') + ', ' + num(tr[0]) + ', ' + num(tr[1]) + ops(o) + ')'); return true;
        case 'revolucion':
          if (!o.x) return false;
          L.push(nom(o, 'R') + ' = revolucion(' + o.f + (o.g != null ? ', ' + o.g : '') + ', ' + num(o.x[0]) + ', ' + num(o.x[1]) + ops(o, ['eje', 'angulo', 'corte', 'capa']) + ')'); return true;
        case 'carga': L.push(nom(o, 'q') + ' = carga(' + P(o.en || o.p) + ', ' + num(o.q == null ? 1 : o.q) + ')'); return true;
        case 'campo': if (o.E) return false; L.push(nom(o, 'E') + ' = campo()'); return true;
        case 'etiqueta': L.push('etiqueta(' + P(o.en || o.p) + ', "' + String(o.texto == null ? '' : o.texto).replace(/"/g, "'") + '")'); return true;
        case 'cota': L.push(nom(o, 'd') + ' = distancia(' + P(o.de) + ', ' + P(o.a) + ')'); return true;
        case 'angulo': L.push(nom(o, 'ang') + ' = angulo(' + P(o.a) + ', ' + P(o.b || o.vertice) + ', ' + P(o.c) + ')'); return true;
        case 'marcaangulo': L.push('marcaangulo(' + P(o.a) + ', ' + P(o.b || o.vertice) + ', ' + P(o.c) + (o.n ? ', ' + num(o.n) : '') + ')'); return true;
        case 'angulorecto': L.push('angulorecto(' + P(o.a) + ', ' + P(o.b || o.vertice) + ', ' + P(o.c) + ')'); return true;
        case 'marcaigual': L.push('marcaigual(' + P(o.de) + ', ' + P(o.a) + (o.n ? ', ' + num(o.n) : '') + ')'); return true;
        default: return false;
      }
    });
    if (!ok) return null;
    if (Array.isArray(spec.vista)) L.push('vista(' + num(spec.vista[0]) + ', ' + num(spec.vista[1]) + ')');
    if (spec.ejes === false) L.push('ejes(no)');
    if (spec.numeros === false) L.push('numeros(no)');
    if (spec.nombres === false) L.push('nombres(no)');
    if (spec.medidas === false) L.push('medidas(no)');
    if (spec.relleno === 'opaco' || spec.relleno === 'transparente') L.push('relleno(' + spec.relleno + ')');
    if (spec.proporcion === 'cubo' || spec.proporcion === 'igual') L.push('proporcion(' + spec.proporcion + ')');
    return L.join('\n');
  }

  // ---- el giro de una animación (GIF, forma "3d"): n vistas; 'vaiven' = ±30° con suavizado, 'vuelta' = 360° ----
  function vistasGiro(vista, giro, n){
    var v0 = vistaDe(vista, [30, 22]), out = [];
    n = Math.max(2, Math.round(n || 48));
    for (var i = 0; i < n; i++) out.push(giro === 'vuelta' ? [v0[0] + 360 * i / n, v0[1]] : [v0[0] + 30 * Math.sin(2 * Math.PI * i / n), v0[1]]);
    return out;
  }
  // fotogramas PNG de la figura girando (solo navegador): fuente = spec | {guion} | una escena ya hecha.
  // opts: los de la figura (tema, tam/ancho, fondo, anotaciones, relleno…) y vista, giro ('vaiven' | 'vuelta'), n (fotogramas).
  // → Promise<{fotos: [dataURL], ms, w, h}> (tamaño fijo: encuadre 'esfera'). Para el GIF: gif3d.py.
  function fotogramas(fuente, opts){
    opts = opts || {};
    var e = fuente && typeof fuente.dibujar === 'function' ? fuente : escena(fuente && typeof fuente.guion === 'string' ? aSpec(fuente.guion).spec : fuente, opts);
    var giro = opts.giro === 'vuelta' ? 'vuelta' : 'vaiven', n = Math.max(8, Math.min(72, Math.round(opts.n || 48))), dur = giro === 'vuelta' ? 6000 : 4000;
    var o2 = {}, kk; for (kk in opts) o2[kk] = opts[kk];
    o2.encuadre = 'esfera';
    var svgs = vistasGiro(opts.vista || e.vista, giro, n).map(function(v){ return e.dibujar(v, o2); });
    if (!svgs[0].svg) return Promise.reject(new Error('no hay nada que dibujar'));
    var w = svgs[0].w, h = svgs[0].h, lienzo = document.createElement('canvas'), ctx = lienzo.getContext('2d');
    lienzo.width = w; lienzo.height = h;
    return svgs.reduce(function(cadena, r){
      return cadena.then(function(fotos){
        return new Promise(function(listo, falla){
          var im = new Image();
          im.onload = function(){ ctx.clearRect(0, 0, w, h); ctx.drawImage(im, 0, 0, w, h); fotos.push(lienzo.toDataURL('image/png')); listo(fotos); };
          im.onerror = function(){ falla(new Error('no pude pasar un fotograma a imagen')); };
          im.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(r.svg);
        });
      });
    }, Promise.resolve([])).then(function(fotos){ return {fotos: fotos, ms: Math.round(dur / n), w: w, h: h}; });
  }

  // ---- girar con el ratón (solo navegador) ----
  function girable(el, spec, opts){
    opts = opts || {};
    var esGuion = spec && typeof spec === 'object' && typeof spec.guion === 'string', sp = esGuion ? aSpec(spec.guion).spec : spec;
    var o1 = {}, kk; for (kk in opts) o1[kk] = opts[kk];
    var sc = escena(sp, o1), rap = null, vista = (vistaDe(opts.vista, null) || sc.vista).slice(), arr = null, pend = false, ult = null;
    function pintar(rapido){
      var e = rapido ? (rap = rap || escena(sp, Object.assign({}, o1, {rapido: true}))) : sc;
      ult = e.dibujar(vista, {encuadre: 'esfera'});
      el.innerHTML = ult.svg;
      if (opts.alGirar) opts.alGirar(vista.slice(), rapido);
    }
    function mover(ev){
      if (!arr) return;
      vista[0] = arr.v[0] - (ev.clientX - arr.x) * 0.5;
      vista[1] = Math.max(-89, Math.min(89, arr.v[1] + (ev.clientY - arr.y) * 0.4));
      if (!pend){ pend = true; (RAIZ.requestAnimationFrame || setTimeout)(function(){ pend = false; pintar(true); }); }
    }
    function abajo(ev){
      if (ev.button != null && ev.button !== 0) return;
      arr = {x: ev.clientX, y: ev.clientY, v: vista.slice()};
      try { el.setPointerCapture(ev.pointerId); } catch (e){}
      el.style.cursor = 'grabbing'; ev.preventDefault();
    }
    function arriba(){ if (!arr) return; arr = null; el.style.cursor = 'grab'; pintar(false); }
    function doble(){ vista = sc.vista.slice(); pintar(false); }
    el.style.touchAction = 'none'; el.style.cursor = 'grab'; el.style.userSelect = 'none';
    el.addEventListener('pointerdown', abajo); el.addEventListener('pointermove', mover);
    el.addEventListener('pointerup', arriba); el.addEventListener('pointercancel', arriba); el.addEventListener('dblclick', doble);
    pintar(false);
    return {
      vista: function(){ return vista.slice(); },
      poner: function(v){ vista = vistaDe(v, vista); pintar(false); },
      cambiar: function(o2){                                // otras opciones (anotaciones, relleno, tema, paleta…) en la misma vista
        for (var k2 in o2 || {}) o1[k2] = o2[k2];
        sc = escena(sp, o1); rap = null; pintar(false);
      },
      opciones: function(){ var c = {}; for (var k2 in o1) c[k2] = o1[k2]; return c; },
      svg: function(o2){ return sc.dibujar(vista, Object.assign({encuadre: 'justo'}, o2 || {})); },
      errores: sc.errores,
      ultimo: function(){ return ult; },
      destruir: function(){
        el.removeEventListener('pointerdown', abajo); el.removeEventListener('pointermove', mover);
        el.removeEventListener('pointerup', arriba); el.removeEventListener('pointercancel', arriba); el.removeEventListener('dblclick', doble);
      }
    };
  }

  var API = {figura: figura, escena: escena, guion: guion, aSpec: aSpec, aGuion: aGuion, es3d: es3d, girable: girable, vistasGiro: vistasGiro,
             fotogramas: fotogramas, tipos: Object.keys(TIPOS)};
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  if (RAIZ) RAIZ.Figuras3D = API;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
