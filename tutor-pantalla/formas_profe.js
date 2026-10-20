/* Las figuras de Claude Design («Figuras del tutor», profe.js) como formas del dibujante. Contrato:
   clase-viva/CONTRATO-FIGURAS.md; formato de cada una en DIBUJOS.md.
     globo · pasos · punto · medida · guias · area · desplazar · recorrido   (nuevas)
     mano · foco                                                           (reemplazan a las de formas_fijas.js)
   En una gráfica, Python pone d.ejes = {q: [q0, q1], p: [p0, p1]} y d.r = su área de datos: el tutor da valores (q, p)
   y aquí pasan a píxeles. Profe dibuja en coordenadas de cliente, que es justo lo que pide U.capa. Las entradas van en
   fotogramas (sin repetir: capa.py se queda en el último). Va después de formas_fijas.js, así mano y foco son estas. */
(function(){
  var D = window.Dibujante, P = window.Profe;
  if (!D || !P) return;

  function base(d, mas){
    var o = {tema: d.tema === 'oscuro' ? 'oscuro' : 'claro', escala: d.escala || 1, color: d.color || 'azul'};
    for (var k in mas || {}) o[k] = mas[k];
    return o;
  }
  function caja(r, s){ var m = 4 * s; return [r.x - m, r.y - m, r.w + 2 * m, r.h + 2 * m]; }
  function rect(r){ return r ? {x: r[0], y: r[1], w: r[2], h: r[3]} : null; }
  function ejes(d){
    if (!d.ejes || !d.r) throw new Error(d.forma + ': su objetivo tiene que ser una «gráfica» del mapa');
    var r = d.r;
    return P.ejes({x0: r[0], x1: r[0] + r[2], y0: r[1] + r[3], y1: r[1], q: d.ejes.q, p: d.ejes.p});
  }
  function num(v, que, forma){ var n = parseFloat(v); if (!isFinite(n)) throw new Error(forma + ': falta «' + que + '» (un número de los ejes)'); return n; }

  // f(t) → resultado de Profe. Con ms > 0, la entrada en n fotogramas; si no, la figura quieta.
  function figura(d, U, f, ms, n, extra){
    var fin = f(1), s = d.escala || 1, k = caja(fin, s);
    var ocupa = {ocupa: [[fin.x, fin.y, fin.w, fin.h]]};
    if (!ms || n < 2) return U.capa(d, k, fin.g, Object.assign(ocupa, extra || {}));
    return U.fotos(d, k, n, function(i){ return f((i + 1) / n).g; }).then(function(fotos){
      return U.capa(d, k, '', Object.assign({fotos: fotos, fps: n * 1000 / ms, duracion: ms, repetir: false, pausa: 0}, ocupa, extra || {}));
    });
  }
  function choca(a, b){ return !(a.x + a.w <= b[0] || b[0] + b[2] <= a.x || a.y + a.h <= b[1] || b[1] + b[3] <= a.y); }
  function cabe(res, d){
    var c = d.cliente || [1e9, 1e9];
    if (res.x < 2 || res.y < 2 || res.x + res.w > c[0] - 2 || res.y + res.h > c[1] - 2) return false;
    return !(d.evitar || []).some(function(e){ return e.fuerte && choca(res, e); });
  }

  // 1a · globo con hilo (en piezas de texto o fórmulas, 1c pestaña). Ancla: el dato (q, p) de una gráfica, o la pieza.
  D.registrar('globo', function(d, U){
    var texto = d.texto || d.decir || '';
    if (!texto) throw new Error('globo: falta el texto');
    var r = rect(d.r), o = {texto: texto, formula: d.formula || undefined, ancho: d.ancho || 260};
    if (d.pieza_texto && r){
      o.variante = 'pestana'; o.pieza = r;
      var lado = r.y + r.h + 140 * (d.escala || 1) < (d.cliente || [0, 1e9])[1] ? 'abajo' : 'arriba';
      return figura(d, U, function(t){ return P.globo(base(d, Object.assign({lado: lado, t: t}, o))); }, 400, 8);
    }
    var A;
    if (d.ejes && d.q != null && d.p != null){ var px = ejes(d).px(num(d.q, 'q', 'globo'), num(d.p, 'p', 'globo')); A = {x: px[0], y: px[1]}; }
    else if (r) A = {x: r.x + r.w / 2, y: r.y + r.h / 2};
    else { var c = d.cliente || [1200, 800]; A = {x: c[0] / 2, y: c[1] / 3}; }
    o.variante = 'hilo'; o.ancla = A;
    var ancha = r && !d.ejes && r.w > (d.cliente || [1e9])[0] * 0.45;      // pieza ancha (un deslizador, un párrafo): encima, que debajo suelen ir los cálculos
    var lados = ancha ? ['arriba', 'abajo', 'derecha', 'izquierda'] : ['derecha', 'izquierda', 'abajo', 'arriba'], elegido = lados[0];
    for (var i = 0; i < lados.length; i++){ if (cabe(P.globo(base(d, Object.assign({lado: lados[i]}, o))), d)){ elegido = lados[i]; break; } }
    return figura(d, U, function(t){ return P.globo(base(d, Object.assign({lado: elegido, t: t}, o))); }, 400, 8);
  });

  // 2a · explicación en pasos: un paso cada ≈ 4 s (el número, su globo y la barra que avanza); al final quedan todos.
  D.registrar('pasos', function(d, U){
    var ps = (d.pasos || []).filter(function(p){ return p && p.r; });
    if (!ps.length) throw new Error('pasos: ningún paso tiene objetivo a la vista');
    var s = d.escala || 1, c = d.cliente || [1200, 800];
    var L = ps.slice(0, 6).map(function(p){
      var r = rect(p.r), ins = [Math.max(16 * s, r.x - 4 * s), Math.max(16 * s, r.y - 4 * s)];
      var lado = r.x + r.w + 280 * s < c[0] ? 'derecha' : r.w > c[0] * 0.45 ? (r.y + r.h + 150 * s < c[1] ? 'abajo' : 'arriba') : 'izquierda';
      return {insignia: ins, pieza: r, texto: p.texto || p.decir || '', formula: p.formula || undefined, lado: lado};
    });
    var POR = 8, n = L.length, fps = 2;                 // 8 cuadros de 500 ms por paso = 4 s
    var dib = function(k, j){ return P.pasos(base(d, {variante: 'numeros', pasos: L, actual: k, progreso: j / (POR - 1), t: j === 0 ? 0.6 : 1})); };
    var fin = dib(n - 1, POR - 1), k0 = caja(fin, s);
    var todos = []; for (var k = 0; k < n; k++) for (var j = 0; j < POR; j++) todos.push([k, j]);
    var cajas = todos.map(function(kj){ return dib(kj[0], kj[1]); });
    var u = cajas.reduce(function(a, b){ return {x: Math.min(a.x, b.x), y: Math.min(a.y, b.y), x2: Math.max(a.x2, b.x + b.w), y2: Math.max(a.y2, b.y + b.h)}; },
                         {x: fin.x, y: fin.y, x2: fin.x + fin.w, y2: fin.y + fin.h});
    k0 = caja({x: u.x, y: u.y, w: u.x2 - u.x, h: u.y2 - u.y}, s);
    return U.fotos(d, k0, todos.length, function(i){ return cajas[i].g; }).then(function(fotos){
      return U.capa(d, k0, '', {fotos: fotos, fps: fps, duracion: todos.length * 1000 / fps, repetir: false, pausa: 0, ocupa: [[u.x, u.y, u.x2 - u.x, u.y2 - u.y]]});
    });
  });

  // ---- B · sobre una gráfica (valores de los ejes, no píxeles) ----
  D.registrar('punto', function(d, U){
    var E = ejes(d), q = num(d.q, 'q', 'punto'), p = num(d.p, 'p', 'punto');
    return figura(d, U, function(t){ return P.punto(base(d, {ejes: E, q: q, p: p, letra: d.letra || '', texto: d.texto, lado: d.lado || 'ne', t: t})); }, 350, 8);
  });
  D.registrar('medida', function(d, U){
    var E = ejes(d), p = num(d.p, 'p', 'medida'), q1 = num(d.q1, 'q1', 'medida'), q2 = num(d.q2, 'q2', 'medida');
    return figura(d, U, function(t){ return P.medida(base(d, {ejes: E, p: p, q1: q1, q2: q2, texto: d.texto || '', lado: d.lado || 'arriba', t: t})); }, 600, 10);
  });
  D.registrar('guias', function(d, U){
    var E = ejes(d), q = num(d.q, 'q', 'guias'), p = num(d.p, 'p', 'guias');
    return figura(d, U, function(t){ return P.guias(base(d, {ejes: E, q: q, p: p, textoQ: d.textoQ, textoP: d.textoP, punto: d.punto !== false, t: t})); }, 500, 8);
  });
  D.registrar('area', function(d, U){
    var E = ejes(d);
    if (!d.rect && !d.poli) throw new Error('area: falta «rect» ({q: [a, b], p: [a, b]}) o «poli» ([[q, p], …])');
    return figura(d, U, function(t){ return P.area(base(d, {ejes: E, rect: d.rect, poli: d.poli, texto: d.texto || '', detalle: d.detalle, en: d.en, t: t})); }, 400, 8);
  });
  D.registrar('desplazar', function(d, U){
    var E = ejes(d);
    if (!Array.isArray(d.de) || !Array.isArray(d.a)) throw new Error('desplazar: faltan «de» y «a» ([[q, p], [q, p]] cada una)');
    return figura(d, U, function(t){ return P.desplazar(base(d, {ejes: E, de: d.de, a: d.a, nombre: d.nombre || '', nota: d.nota || d.texto, t: t})); }, 1400, 14);
  });
  D.registrar('recorrido', function(d, U){
    var E = ejes(d), cam = (d.camino || []).filter(function(x){ return Array.isArray(x) && x.length === 2; });
    if (cam.length < 2) throw new Error('recorrido: «camino» necesita al menos dos puntos [q, p]');
    var n = 48, ms = 4000, s = d.escala || 1;
    var cuadros = []; for (var i = 0; i < n; i++) cuadros.push(P.recorrido(base(d, {ejes: E, camino: cam, fase: i / n})));
    var r = d.r, k = [r[0] - 60 * s, r[1] - 30 * s, r[2] + 120 * s, r[3] + 60 * s];      // el área de datos y lo que sale a los ejes
    return U.fotos(d, k, n, function(i){ return cuadros[i].g; }).then(function(fotos){
      return U.capa(d, k, '', {fotos: fotos, fps: n * 1000 / ms, duracion: ms, repetir: true, pausa: 0, ocupa: [r]});
    });
  });

  // ---- C · a mano alzada (11a: rodear en «auto» = elipse si es casi cuadrado, lazo si es ancho) y 12a la nota ----
  D.registrar('mano', function(d, U){
    if (!d.r) throw new Error('mano necesita un objetivo');
    var r = rect(d.r), s = d.escala || 1, trazo = d.trazo || 'circulo', sem = d.semilla || 7;
    var forma = function(t){
      if (trazo === 'subrayado') return P.mano.subrayar(base(d, {x1: r.x, x2: r.x + r.w, y: r.y + r.h, semilla: sem, t: t}));
      if (trazo === 'tache') return P.mano.tachar(base(d, {x: r.x, y: r.y, w: r.w, h: r.h, tipo: 'x', semilla: sem, t: t}));
      if (trazo === 'check') return P.mano.visto(base(d, {x: r.x + r.w + 6 * s, y: r.y + r.h / 2 - 12 * s, tam: 22, t: t}));
      if (trazo === 'flecha'){
        var x2 = r.x - 4 * s, y2 = r.y + r.h / 2, x1 = Math.max(10 * s, x2 - 90 * s), y1 = Math.max(10 * s, y2 - 60 * s);
        return P.mano.flecha(base(d, {x1: x1, y1: y1, x2: x2, y2: y2, curva: 0.25, semilla: sem, t: t}));
      }
      return P.mano.rodear(base(d, {x: r.x, y: r.y, w: r.w, h: r.h, forma: d.figura || 'auto', semilla: sem, t: t}));
    };
    var f = function(t){
      var a = forma(t);
      if (!d.texto) return a;
      var c = d.cliente || [1e9, 1e9], x = a.x + a.w + 10 * s, y = a.y + Math.min(a.h, 30 * s), ancla = 'i';
      if (x + 160 * s > c[0]) { x = a.x + a.w - 10 * s; ancla = 'd'; y = a.y > 34 * s ? a.y - 8 * s : a.y + a.h + 24 * s; }   // arriba, si cabe
      var nt = P.mano.nota(base(d, {x: x, y: y, texto: d.texto, ancla: ancla, t: Math.max(0, (t - 0.6) / 0.4)}));
      var x0 = Math.min(a.x, nt.x), y0 = Math.min(a.y, nt.y);
      return {g: a.g + nt.g, x: x0, y: y0, w: Math.max(a.x + a.w, nt.x + nt.w) - x0, h: Math.max(a.y + a.h, nt.y + nt.h) - y0};
    };
    return figura(d, U, f, 600, 10);
  });

  // ---- E · foco: velo de papel (el fondo de la app, no negro); quieto, sin capturar clics ----
  D.registrar('foco', function(d, U){
    if (!d.r) throw new Error('foco necesita un objetivo');
    var c = d.cliente || [1600, 900], s = d.escala || 1, m = 6 * s, r = rect(d.r);
    var res = P.foco(base(d, {area: {x: 0, y: 0, w: c[0], h: c[1]}, pieza: {x: r.x - m, y: r.y - m, w: r.w + 2 * m, h: r.h + 2 * m}, variante: 'velo', t: 1}));
    return U.capa(d, [0, 0, c[0], c[1]], res.g, {ocupa: []});
  });
})();
