/* La forma «marca» del dibujante: la flecha de siempre (marco redondeado alrededor del objetivo + nota que no tapa
   botones + flecha de la nota al marco), ahora en SVG y con entrada animada. Contrato: CONTRATO-MARCAS.md, sección 2.

   Una capa por marca (id = d.id), para que «deslizar» y «latir» de capa.py funcionen por marca.

   Dos mitades, para poder cambiar el diseño sin tocar la colocación:
     · Marcas.piezas.{nota, marco, numero, flecha, borde}({color, tema, escala, texto, ...}) → {svg, w, h}
       Solo dibujan. nota/numero/borde devuelven el SVG en coordenadas locales (0..w, 0..h); marco también (w, h = su tamaño);
       flecha devuelve el SVG ya en coordenadas de cliente (x1, y1, x2, y2) y su caja en w, h.
       Parámetros comunes: color (nombre o #rrggbb), tema ('claro' | 'oscuro'), escala. Con `progreso` (0..1) marco y flecha
       se dibujan a medias (la entrada animada).
     · La forma «marca» (abajo) decide dónde va cada cosa y arma los fotogramas de entrada. */
(function(){
  if (!window.Dibujante) return;
  var D = window.Dibujante;
  var FUENTE = "'Segoe UI', 'Segoe UI Variable Text', system-ui, sans-serif";
  var med = document.createElement('canvas').getContext('2d');
  function medir(t, px){ med.font = '600 ' + px + 'px ' + FUENTE; return med.measureText(String(t)).width; }
  function esc(s){ return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){ return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]; }); }
  function acota(v){ return Math.max(0, Math.min(1, v)); }

  // ---- el color según el tema de la app que hay detrás ----
  function pal(o){
    var Q = D.U.paleta(o.color, o.tema === 'oscuro' ? 'oscuro' : 'claro');           // la paleta plana: la tinta ya viene aclarada en el tema oscuro
    return {col: Q.tinta, texto: Q.fuerte, borde: Q.tinta, fondo: Q.papel, fondoOp: 1, halo: Q.fondo, sombra: Q.sombra,
            numFondo: Q.tinta, numTexto: Q.sobre, osc: Q.osc};
  }
  function sombra(id, s, osc, color){
    return '<filter id="' + id + '" x="-20%" y="-30%" width="140%" height="170%"><feDropShadow dx="0" dy="' + 1.5 * s + '" stdDeviation="' + 2.2 * s +
      '" flood-color="' + (color || '#000000') + '" flood-opacity="' + (osc ? 0.5 : 0.2) + '"/></filter>';
  }
  // rectángulo con las cuatro esquinas redondeadas por separado (las de la pastilla pegada al borde son rectas por fuera)
  function rr(x, y, w, h, r){
    var a = r[0], b = r[1], c = r[2], d = r[3];
    return 'M' + (x + a) + ' ' + y + 'H' + (x + w - b) + (b ? 'A' + b + ' ' + b + ' 0 0 1 ' + (x + w) + ' ' + (y + b) : '') +
      'V' + (y + h - c) + (c ? 'A' + c + ' ' + c + ' 0 0 1 ' + (x + w - c) + ' ' + (y + h) : '') +
      'H' + (x + d) + (d ? 'A' + d + ' ' + d + ' 0 0 1 ' + x + ' ' + (y + h - d) : '') +
      'V' + (y + a) + (a ? 'A' + a + ' ' + a + ' 0 0 1 ' + (x + a) + ' ' + y : '') + 'Z';
  }

  // =====================================================================================================
  // Las piezas visuales
  // =====================================================================================================
  var Marcas = {piezas: {}};
  var P = Marcas.piezas;

  // El número de orden: un círculo con el número dentro.
  P.numero = function(o){
    var s = o.escala || 1, c = pal(o), px = 15 * s, dc = Math.round(px * 1.4), t = String(o.n);
    var fs = px * (t.length > 1 ? 0.72 : 0.86);
    return {w: dc, h: dc, svg: '<circle cx="' + dc / 2 + '" cy="' + dc / 2 + '" r="' + dc / 2 + '" fill="' + c.numFondo + '"/>' +
      '<text x="' + dc / 2 + '" y="' + (dc / 2 + 0.5 * s) + '" text-anchor="middle" dominant-baseline="central" font-size="' + fs + '" font-weight="700" fill="' + c.numTexto + '">' + esc(t) + '</text>'};
  };

  // La nota: [número] texto, en una tarjeta con borde del color.
  P.nota = function(o){
    var s = o.escala || 1, c = pal(o), px = 15 * s, pad = 9 * s, h = px * 1.3 + 1.3 * pad;
    var num = o.n ? P.numero(o) : null, x = pad, texto = o.texto ? String(o.texto) : '';
    var w = pad + (num ? num.w + (texto ? 6 * s : 0) : 0) + (texto ? medir(texto, px) : 0) + pad;
    var out = '<defs>' + sombra('ns', s, c.osc, c.sombra) + '</defs>' +
      '<rect x="' + 1.2 * s + '" y="' + 1.2 * s + '" width="' + (w - 2.4 * s) + '" height="' + (h - 2.4 * s) + '" rx="' + 7 * s + '" fill="' + c.fondo + '" fill-opacity="' + c.fondoOp +
      '" stroke="' + c.borde + '" stroke-width="' + 1.5 * s + '" filter="url(#ns)"/>';
    if (num){ out += '<g transform="translate(' + x + ' ' + (h - num.h) / 2 + ')">' + num.svg + '</g>'; x += num.w + (texto ? 6 * s : 0); }
    if (texto) out += '<text x="' + x + '" y="' + h / 2 + '" dominant-baseline="central" font-size="' + px + '" font-weight="600" fill="' + c.texto + '">' + esc(texto) + '</text>';
    return {svg: out, w: w, h: h};
  };

  // El marco redondeado alrededor del objetivo (w × h es su tamaño total). progreso < 1: se va dibujando.
  P.marco = function(o){
    var s = o.escala || 1, c = pal(o), sw = 3.2 * s, p = o.progreso == null ? 1 : acota(o.progreso), w = o.w, h = o.h;
    if (p <= 0) return {svg: '', w: w, h: h};
    var da = p >= 1 ? '' : ' pathLength="1" stroke-dasharray="' + p + ' 2"';
    var halo = '<rect x="' + sw / 2 + '" y="' + sw / 2 + '" width="' + (w - sw) + '" height="' + (h - sw) + '" rx="' + 6 * s + '" fill="none" stroke="' + c.halo + '" stroke-opacity="0.55" stroke-width="' + (sw + 2.4 * s) + '"' + da + '/>';
    return {w: w, h: h, svg: halo + '<rect x="' + sw / 2 + '" y="' + sw / 2 + '" width="' + (w - sw) + '" height="' + (h - sw) + '" rx="' + 6 * s + '" fill="none" stroke="' + c.col +
      '" stroke-width="' + sw + '" stroke-linejoin="round"' + da + '/>'};
  };

  // La flecha de la nota al marco, en coordenadas de cliente. progreso < 1: crece desde la nota.
  P.flecha = function(o){
    var s = o.escala || 1, c = pal(o), p = o.progreso == null ? 1 : acota(o.progreso);
    var w = Math.abs(o.x2 - o.x1), h = Math.abs(o.y2 - o.y1);
    if (p < 0.08) return {svg: '', w: w, h: h};
    var x2 = o.x1 + (o.x2 - o.x1) * p, y2 = o.y1 + (o.y2 - o.y1) * p;
    if (p < 0.8)       // creciendo: solo el trazo; la punta aparece al final (así no flota una punta suelta)
      return {svg: '<path d="M' + o.x1 + ' ' + o.y1 + 'L' + x2 + ' ' + y2 + '" stroke="' + c.col + '" stroke-width="' + 3.2 * s + '" stroke-linecap="round" fill="none"/>', w: w, h: h};
    return {svg: D.U.flecha(o.x1, o.y1, x2, y2, {color: c.col, grosor: 3.2 * s}), w: w, h: h};
  };

  // La pastilla pegada al borde cuando lo señalado quedó fuera de la vista: «↓ Negrita, más abajo».
  var FUERA = {abajo: ['↓', 'más abajo'], arriba: ['↑', 'más arriba'], izquierda: ['←', 'más a la izquierda'], derecha: ['→', 'más a la derecha']};
  P.borde = function(o){
    var s = o.escala || 1, c = pal(o), px = 15 * s, pad = 9 * s, h = px * 1.3 + 1.3 * pad, dir = FUERA[o.dir] ? o.dir : 'abajo', f = FUERA[dir];
    var texto = f[0] + ' ' + (o.texto ? o.texto + ', ' : '') + f[1];
    var num = o.n ? P.numero(o) : null, x = pad;
    var w = pad + (num ? num.w + 6 * s : 0) + medir(texto, px) + pad, R = 9 * s;
    var r = {abajo: [R, R, 0, 0], arriba: [0, 0, R, R], izquierda: [0, R, R, 0], derecha: [R, 0, 0, R]}[dir];     // el lado del borde, recto
    var out = '<defs>' + sombra('bs', s, c.osc, c.sombra) + '</defs>' +
      '<path d="' + rr(1.2 * s, 1.2 * s, w - 2.4 * s, h - 2.4 * s, r.map(function(v){ return Math.max(0, v - 1.2 * s); })) + '" fill="' + c.fondo + '" fill-opacity="' + c.fondoOp +
      '" stroke="' + c.borde + '" stroke-width="' + 2.4 * s + '" filter="url(#bs)"/>';
    if (num){ out += '<g transform="translate(' + x + ' ' + (h - num.h) / 2 + ')">' + num.svg + '</g>'; x += num.w + 6 * s; }
    out += '<text x="' + x + '" y="' + h / 2 + '" dominant-baseline="central" font-size="' + px + '" font-weight="600" fill="' + c.texto + '">' + esc(texto) + '</text>';
    return {svg: out, w: w, h: h};
  };

  // ---- el diseño de Claude Design («Kit de anotaciones», marcas.js): si está cargado, sus piezas sustituyen a las de
  //      arriba. Devuelven {g, w, h}: g ya en las coordenadas que usa la colocación (nota y borde locales, flecha de cliente).
  var KIT = window.Marcas && window.Marcas.tiempo && window.Marcas.piezas ? window.Marcas : null;
  if (KIT){
    var K = KIT.piezas;
    var kp = function(o){ return {color: KIT.colores.indexOf(o.color) >= 0 ? o.color : 'azul', tema: o.tema === 'oscuro' ? 'oscuro' : 'claro', escala: o.escala || 1}; };
    P.nota = function(o){
      var q = kp(o); q.texto = o.texto || ''; if (o.n) q.n = o.n;          // la entrada de la nota la anima la forma «marca»
      var r = K.nota(q); return {svg: r.g, w: r.w, h: r.h};
    };
    P.marco = function(o){
      var q = kp(o), t = o.progreso == null ? 1 : acota(o.progreso);
      if (t <= 0) return {svg: '', w: o.w, h: o.h};
      q.w = o.w; q.h = o.h; q.t = t; return {svg: K.marco(q).g, w: o.w, h: o.h};
    };
    P.flecha = function(o){
      var q = kp(o), t = o.progreso == null ? 1 : acota(o.progreso), w = Math.abs(o.x2 - o.x1), h = Math.abs(o.y2 - o.y1);
      if (t <= 0.01) return {svg: '', w: w, h: h};
      q.x1 = o.x1; q.y1 = o.y1; q.x2 = o.x2; q.y2 = o.y2; q.t = t; return {svg: K.flecha(q).g, w: w, h: h};
    };
    P.borde = function(o){
      var q = kp(o), dir = FUERA[o.dir] ? o.dir : 'abajo';                  // el kit dibuja su propia flecha: el texto va sin «↓»
      q.lado = dir; q.texto = (o.n ? o.n + ' · ' : '') + (o.texto ? o.texto + ', ' : '') + FUERA[dir][1];
      var r = K.borde(q); return {svg: r.g, w: r.w, h: r.h};
    };
  }

  // =====================================================================================================
  // La forma «marca»
  // =====================================================================================================
  var N_ENTRADA = 11, MS_ENTRADA = 350;            // fotogramas de la entrada (~26 por segundo)
  function suave(g){ return 0.5 - 0.5 * Math.cos(Math.PI * acota(g)); }

  function colocarFuera(d, U, pieza, c, s){
    // pegada a su borde; si ya hay algo ahí (otra pastilla, un botón), se corre a lo largo del borde al sitio con menos solape
    var dir = d.fuera, w = pieza.w, h = pieza.h, horiz = dir === 'abajo' || dir === 'arriba', cands = [], paso = (horiz ? w : h) + 8 * s;
    var sep = 2 * s;                                   // un pelín hacia dentro: así se ve entero su borde
    var fijo = dir === 'abajo' ? c[1] - h - sep : dir === 'arriba' ? sep : dir === 'derecha' ? c[0] - w - sep : sep;
    var largo = horiz ? c[0] : c[1], tam = horiz ? w : h, centro = (largo - tam) / 2;
    for (var k = 0; k < 12; k++){
      [k, -k].forEach(function(j, i){
        if (k === 0 && i) return;
        var v = centro + j * paso * (k ? 1 : 0);
        if (v < 2 || v + tam > largo - 2) return;
        cands.push(horiz ? [v, fijo, w, h] : [fijo, v, w, h]);
      });
    }
    if (!cands.length) cands.push(horiz ? [Math.max(0, centro), fijo, w, h] : [fijo, Math.max(0, centro), w, h]);
    var mejor = null, bp = Infinity;
    cands.forEach(function(k){
      var p = 0;
      (d.evitar || []).forEach(function(o){
        var a = Math.min(k[0] + k[2], o[0] + o[2]) - Math.max(k[0], o[0]), b = Math.min(k[1] + k[3], o[1] + o[3]) - Math.max(k[1], o[1]);
        if (a > 0 && b > 0) p += a * b * (o.fuerte ? 50 : 4);
      });
      if (p < bp - 1e-6){ bp = p; mejor = k; }
    });
    return mejor;
  }

  D.registrar('marca', async function(d, U){
    var s = d.escala || 1, c = d.cliente || [1600, 900], tema = d.tema === 'oscuro' ? 'oscuro' : 'claro';
    var par = {color: d.color, tema: tema, escala: s};
    var texto = d.texto || '', caja, ocupa, dibujar;      // dibujar(g): el SVG (coordenadas de cliente) con la entrada al avance g (0..1)

    if (d.fuera){
      var pz = P.borde({color: d.color, tema: tema, escala: s, texto: texto, n: d.n, dir: d.fuera});
      var pb = colocarFuera(d, U, pz, c, s);
      var corre = {abajo: [0, 14 * s], arriba: [0, -14 * s], izquierda: [-14 * s, 0], derecha: [14 * s, 0]}[d.fuera] || [0, 0];
      caja = [pb[0] - 16 * s, pb[1] - 16 * s, pb[2] + 32 * s, pb[3] + 32 * s];
      ocupa = [pb];
      dibujar = function(g){
        var e = 1 - suave(acota(g / 0.6)), op = acota(g / 0.5);        // entra desde fuera del borde, deslizándose un poco
        if (op <= 0) return '';
        return '<g opacity="' + op + '" transform="translate(' + (pb[0] + corre[0] * e) + ' ' + (pb[1] + corre[1] * e) + ')">' + pz.svg + '</g>';
      };
    } else {
      if (!d.r) throw new Error('marca necesita un objetivo (r) o «fuera»');
      var r = d.r, g4 = 4 * s, mb = [r[0] - g4, r[1] - g4, r[2] + 2 * g4, r[3] + 2 * g4];
      var nota = texto || d.n ? P.nota({color: d.color, tema: tema, escala: s, texto: texto, n: d.n}) : null;
      var col = nota ? U.nota(d, texto || ' ', {tam: [nota.w, nota.h], solo: true, color: d.color}) : null;     // la colocación de siempre: hueco sin tapar nada
      var cajas = [mb];
      if (col){ cajas.push(col.caja); if (col.flecha) cajas.push([Math.min(col.flecha[0], col.flecha[2]), Math.min(col.flecha[1], col.flecha[3]),
                                                                 Math.abs(col.flecha[2] - col.flecha[0]) || 1, Math.abs(col.flecha[3] - col.flecha[1]) || 1]); }
      var x0 = Math.min.apply(null, cajas.map(function(k){ return k[0]; })), y0 = Math.min.apply(null, cajas.map(function(k){ return k[1]; }));
      var x1 = Math.max.apply(null, cajas.map(function(k){ return k[0] + k[2]; })), y1 = Math.max.apply(null, cajas.map(function(k){ return k[1] + k[3]; }));
      var m = 16 * s;
      caja = [x0 - m, y0 - m, x1 - x0 + 2 * m, y1 - y0 + 2 * m];
      ocupa = col ? [col.caja] : [];
      dibujar = function(g){
        var o = '', pm = P.marco({color: d.color, tema: tema, escala: s, w: mb[2], h: mb[3], progreso: g / 0.45});
        if (pm.svg) o += '<g opacity="' + acota(g * 5) + '" transform="translate(' + mb[0] + ' ' + mb[1] + ')">' + pm.svg + '</g>';
        if (col && col.flecha){
          o += P.flecha({color: d.color, tema: tema, escala: s, x1: col.flecha[0], y1: col.flecha[1], x2: col.flecha[2], y2: col.flecha[3], progreso: (g - 0.25) / 0.5}).svg;
        }
        if (nota){
          var op = acota((g - 0.55) / 0.45), sube = (1 - suave(op)) * 6 * s;
          if (op > 0) o += '<g opacity="' + op + '" transform="translate(' + col.caja[0] + ' ' + (col.caja[1] + sube) + ')">' + nota.svg + '</g>';
        }
        return o;
      };
    }
    if (!caja || !U.recorte(d, caja)) return null;
    var cap;
    if (d.entrada){
      var fotos = await U.fotos(d, caja, N_ENTRADA, function(i, n){ return dibujar(suave(i / (n - 1))); });
      cap = await U.capa(d, caja, '', {fotos: fotos, fps: N_ENTRADA * 1000 / MS_ENTRADA, duracion: MS_ENTRADA, repetir: false});
    } else cap = await U.capa(d, caja, dibujar(1), {});
    if (cap) cap.ocupa = ocupa;
    return cap;
  });

  if (KIT) KIT.adaptadas = P;                       // el kit sigue siendo window.Marcas (con sus íconos y tiempos)
  else window.Marcas = Marcas;
})();
