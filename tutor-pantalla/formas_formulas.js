/* Formas de fórmulas del dibujante: `formula` (la fórmula bien escrita, con mini gráfica opcional), `rayos_x` (de las
   celdas que usa la fórmula al resultado, con los valores viajando) y `desarmar` (el texto ampliado con una llave y una
   explicación por parte). Contrato en DIBUJOS.md; los datos de Excel los pone panel-excel/rayos_x.py.
   Todo en píxeles de cliente; los tamaños se multiplican por d.escala. */
(function(){
  if (!window.Dibujante) return;
  var TINTA = '#1a1f2e', MONO = "Consolas, 'Cascadia Mono', 'Courier New', monospace";
  var PALETA = ['azul', 'verde', 'naranja', 'morado', 'rojo', 'amarillo'];
  var lienzo = document.createElement('canvas').getContext('2d');

  function medirMono(t, px){ lienzo.font = '600 ' + px + 'px ' + MONO; return lienzo.measureText(String(t)).width; }
  function num(v){
    if (typeof v !== 'number') return String(v);
    if (Math.round(v) === v) return String(v);
    try { return v.toLocaleString('es', {maximumFractionDigits: 2}); } catch (e){ return String(Math.round(v * 100) / 100); }
  }
  function corto(t, n){ t = String(t == null ? '' : t); return t.length > n ? t.slice(0, n - 1) + '…' : t; }
  function union(cajas){
    var x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    cajas.forEach(function(c){ if (!c) return; x0 = Math.min(x0, c[0]); y0 = Math.min(y0, c[1]); x1 = Math.max(x1, c[0] + c[2]); y1 = Math.max(y1, c[1] + c[3]); });
    return [x0, y0, x1 - x0, y1 - y0];
  }
  function infla(c, m){ return [c[0] - m, c[1] - m, c[2] + 2 * m, c[3] + 2 * m]; }
  function solape(a, b){
    var w = Math.min(a[0] + a[2], b[0] + b[2]) - Math.max(a[0], b[0]), h = Math.min(a[1] + a[3], b[1] + b[3]) - Math.max(a[1], b[1]);
    return w > 0 && h > 0 ? w * h : 0;
  }
  function defsSombra(s){
    return '<defs><filter id="sombra" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="' + 3 * s +
      '" stdDeviation="' + 5 * s + '" flood-color="#0b1020" flood-opacity="0.28"/></filter></defs>';
  }
  // El hueco libre más cercano al objetivo para una caja de w×h: no tapa `cerca`/d.r ni d.evitar (ni `evitar` extra).
  function hueco(d, U, w, h, opc){
    opc = opc || {};
    var s = d.escala || 1, cw = (d.cliente || [1600, 900])[0], ch = (d.cliente || [1600, 900])[1];
    var r = opc.cerca !== undefined ? opc.cerca : d.r;
    var ev = (d.evitar || []).filter(function(e){ return !r || !U.choca(e, r); }).concat(opc.evitar || []);
    var cx0 = r ? r[0] + r[2] / 2 : cw / 2, cy0 = r ? r[1] + r[3] / 2 : h / 2 + 24 * s;
    var paso = 14 * s, m = 6 * s, mej = null, mejv = 1e18;
    for (var y = m; y + h <= ch - m + 0.01; y += paso){
      for (var x = m; x + w <= cw - m + 0.01; x += paso){
        var c = [x, y, w, h];
        if (r && U.choca(c, r, 10 * s)) continue;
        var so = 0; for (var i = 0; i < ev.length; i++) so += solape(c, ev[i]);
        var v = Math.hypot(x + w / 2 - cx0, y + h / 2 - cy0) + so / (40 * s) * 3;
        if (v < mejv){ mejv = v; mej = c; }
      }
    }
    return mej || [Math.max(0, Math.min((cw - w) / 2, cw - w)), Math.max(0, r ? Math.min(r[1] + r[3] + 12 * s, ch - h) : 24 * s), w, h];
  }
  // El punto del borde de `caja` (inflada `gap`) que mira hacia el punto p.
  function borde(caja, p, gap){
    var cx = caja[0] + caja[2] / 2, cy = caja[1] + caja[3] / 2, vx = p[0] - cx, vy = p[1] - cy;
    var t = Math.min((caja[2] / 2 + gap) / Math.max(1e-6, Math.abs(vx)), (caja[3] / 2 + gap) / Math.max(1e-6, Math.abs(vy)));
    return [cx + vx * t, cy + vy * t];
  }
  function flechaA(U, caja, r, col, s){          // flecha fina del borde de la tarjeta al objetivo
    var g = 4 * s, tx0 = r[0] - g, ty0 = r[1] - g, tx1 = r[0] + r[2] + g, ty1 = r[1] + r[3] + g;
    var pxn = Math.min(Math.max((tx0 + tx1) / 2, caja[0]), caja[0] + caja[2]), pyn = Math.min(Math.max((ty0 + ty1) / 2, caja[1]), caja[1] + caja[3]);
    var tx = Math.min(Math.max(pxn, tx0), tx1), ty = Math.min(Math.max(pyn, ty0), ty1);
    return Math.hypot(tx - pxn, ty - pyn) > 8 * s ? U.flecha(pxn, pyn, tx, ty, {color: col, grosor: 2.4 * s}) : '';
  }
  function marcoR(r, col, s, fuerte){             // recuadro de color alrededor de una celda
    var c = infla(r, (fuerte ? 3.5 : 2) * s);
    return '<rect x="' + c[0] + '" y="' + c[1] + '" width="' + c[2] + '" height="' + c[3] + '" rx="' + 4 * s + '" fill="' + col +
      '" fill-opacity="' + (fuerte ? 0.2 : 0.12) + '" stroke="' + col + '" stroke-width="' + (fuerte ? 4 : 2.6) * s + '"/>';
  }
  function anidar(t, x, y){ return t.svg.replace('<svg', '<svg x="' + x + '" y="' + y + '"'); }

  // ---------------------------------------------------------------- formula
  function barras(U, g, x, y, w, h, col, s){
    var vals = g.valores.slice(), etq = (g.etiquetas || []).slice(), n = vals.length, out = '';
    if (n > 20){                                   // agrupa en 20 barras (promedio de cada grupo)
      var G = 20, nv = [], ne = [];
      for (var k = 0; k < G; k++){
        var a = Math.floor(k * n / G), b = Math.max(a + 1, Math.floor((k + 1) * n / G)), sum = 0;
        for (var j = a; j < b; j++) sum += vals[j];
        nv.push(sum / (b - a)); ne.push(etq[a] != null ? etq[a] : '');
      }
      vals = nv; etq = ne; n = G;
    }
    var pxE = 10.5 * s, hEtq = 16 * s, hVal = 15 * s, base = y + h - hEtq, top = y + hVal;
    var mx = Math.max.apply(null, vals.concat([g.linea ? g.linea.valor : -1e18, 0])), mn = Math.min.apply(null, vals.concat([g.linea ? g.linea.valor : 1e18, 0]));
    if (mx === mn) mx = mn + 1;
    function Y(v){ return base - (v - mn) / (mx - mn) * (base - top); }
    var y0 = Y(0), slot = w / n, bw = slot * 0.66, cual = mezclar(col);
    function mezclar(c){ return U.mezclar(c, 0.55); }
    for (var i = 0; i < n; i++){
      var bx = x + i * slot + (slot - bw) / 2, v = vals[i], yv = Y(v);
      out += '<rect x="' + bx + '" y="' + Math.min(yv, y0) + '" width="' + bw + '" height="' + Math.max(1.5, Math.abs(y0 - yv)) + '" rx="' + 2 * s + '" fill="' + cual + '" stroke="' + col + '" stroke-width="' + 1.2 * s + '"/>';
      if (n <= 10) out += '<text x="' + (bx + bw / 2) + '" y="' + (Math.min(yv, y0) - 3 * s) + '" text-anchor="middle" font-size="' + 10 * s + '" font-weight="600" fill="' + TINTA + '">' + U.esc(num(v)) + '</text>';
    }
    var ancho = 0; etq.forEach(function(e){ ancho = Math.max(ancho, U.medir(corto(e, 5), pxE)); });
    var paso = Math.max(1, Math.ceil((ancho + 5 * s) / slot));
    for (i = 0; i < n; i += paso) out += '<text x="' + (x + i * slot + slot / 2) + '" y="' + (base + 12 * s) + '" text-anchor="middle" font-size="' + pxE + '" fill="#4a5163">' + U.esc(corto(etq[i], 5)) + '</text>';
    out += '<line x1="' + x + '" y1="' + y0 + '" x2="' + (x + w) + '" y2="' + y0 + '" stroke="#8a91a3" stroke-width="' + 1.4 * s + '"/>';
    if (g.linea){
      var yl = Y(g.linea.valor), c2 = U.color('rojo'), tx = (g.linea.texto || '') + ' ' + num(g.linea.valor);
      out += '<line x1="' + x + '" y1="' + yl + '" x2="' + (x + w) + '" y2="' + yl + '" stroke="' + c2 + '" stroke-width="' + 2 * s + '" stroke-dasharray="' + 6 * s + ' ' + 4 * s + '"/>' +
        '<text x="' + (x + w) + '" y="' + (yl - 4 * s) + '" text-anchor="end" font-size="' + 12.5 * s + '" font-weight="700" fill="' + c2 +
        '" stroke="#ffffff" stroke-width="' + 3.2 * s + '" paint-order="stroke" stroke-linejoin="round">' + U.esc(tx) + '</text>';
    }
    return out;
  }

  Dibujante.registrar('formula', async function(d, U){
    var s = d.escala || 1, col = U.color(d.color), pad = 16 * s, cw = (d.cliente || [1600, 900])[0];
    var px = 24 * s, t = null;
    try {
      t = await U.tex(d.latex || '', {px: px, color: TINTA});
      var libre = cw - 2 * pad - 24 * s;
      if (t.w > libre) t = await U.tex(d.latex, {px: px * libre / t.w, color: TINTA});
    } catch (e){ t = null; }
    if (!t){                                        // LaTeX inválido: se muestra tal cual, en monoespaciado
      var pm = 17 * s, txt = corto(d.latex || '', 80), wm = medirMono(txt, pm);
      t = {w: wm, h: pm * 1.6, svg: '<text x="0" y="' + pm * 1.2 + '" font-family="' + MONO + '" font-size="' + pm + '" font-weight="600" fill="' + TINTA + '">' + U.esc(txt) + '</text>', plano: true};
    }
    var g = d.grafica && d.grafica.valores && d.grafica.valores.length > 1 ? d.grafica : null;
    var gw = g ? Math.max(270 * s, Math.min(t.w, 440 * s)) : 0, gh = g ? 138 * s : 0, gap = g ? 14 * s : 0;
    var w = Math.max(120 * s, Math.max(t.w, gw) + 2 * pad), h = t.h + gap + gh + 2 * pad;
    var caja = hueco(d, U, w, h);
    var out = defsSombra(s);
    if (d.r) out += marcoR(d.r, col, s) + flechaA(U, caja, d.r, col, s);
    out += '<rect x="' + caja[0] + '" y="' + caja[1] + '" width="' + w + '" height="' + h + '" rx="' + 10 * s + '" fill="#ffffff" fill-opacity="0.97" stroke="' + col +
      '" stroke-width="' + 2 * s + '" filter="url(#sombra)"/>';
    var tx = caja[0] + (w - t.w) / 2, ty = caja[1] + pad;
    out += t.plano ? '<g transform="translate(' + tx + ' ' + ty + ')">' + t.svg + '</g>' : anidar(t, tx, ty);
    if (g) out += barras(U, g, caja[0] + (w - gw) / 2, caja[1] + pad + t.h + gap, gw, gh, col, s);
    return U.capa(d, infla(union([caja, d.r ? infla(d.r, 8 * s) : null]), 26 * s), out).then(function(c){ if (c) c.ocupa = [caja]; return c; });
  });

  // ---------------------------------------------------------------- rayos_x
  function ease(u){ return u < 0.5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2; }
  function cuad(P0, Q, P2, u){ var a = (1 - u) * (1 - u), b = 2 * (1 - u) * u, c = u * u; return [a * P0[0] + b * Q[0] + c * P2[0], a * P0[1] + b * Q[1] + c * P2[1]]; }

  function burbuja(U, texto, px, col, s, relleno){      // pieza: pastilla blanca con borde de color
    var w = U.medir(texto, px) + px * 1.2, h = px * 1.75, m = 4 * s;
    var c = '<rect x="' + m + '" y="' + m + '" width="' + w + '" height="' + h + '" rx="' + h / 2 + '" fill="' + (relleno || '#ffffff') + '" stroke="' + col +
      '" stroke-width="' + 2.6 * s + '"/><text x="' + (m + w / 2) + '" y="' + (m + h / 2) + '" text-anchor="middle" dominant-baseline="central" font-size="' + px +
      '" font-weight="700" fill="' + (relleno ? '#ffffff' : col) + '">' + U.esc(texto) + '</text>';
    return {c: c, w: w + 2 * m, h: h + 2 * m, m: m, bw: w, bh: h};
  }

  Dibujante.registrar('rayos_x', async function(d, U){
    var s = d.escala || 1, cw = d.cliente[0], ch = d.cliente[1];
    if (!d.r) throw new Error('el resultado no se ve en la pantalla');
    var resCol = U.color(d.color || 'azul');
    var paleta = PALETA.map(U.color).filter(function(c){ return c !== resCol; });
    var fu = (d.fuentes || []).slice(0, 7), n = fu.length;
    var rc = [d.r[0] + d.r[2] / 2, d.r[1] + d.r[3] / 2];
    var fuera = 0, nfuera = fu.filter(function(f){ return !f.r; }).length;
    // geometría de cada fuente
    var G = fu.map(function(f, i){
      var col = paleta[i % paleta.length], o = {f: f, col: col, caja: f.r || null, etiqueta: f.ref};
      var sentido = i % 2 ? -1 : 1, P0;
      if (f.r){ P0 = [f.r[0] + f.r[2] / 2, f.r[1] + f.r[3] / 2]; }
      else {                                        // la celda no se ve: entra por el borde más cercano
        var dist = {izq: rc[0], der: cw - rc[0], arr: rc[1], aba: ch - rc[1]}, lado = Object.keys(dist).sort(function(a, b){ return dist[a] - dist[b]; })[0];
        var off = (fuera - (nfuera - 1) / 2) * 80 * s; fuera++;
        var ins = 18 * s;
        P0 = lado === 'izq' ? [ins, rc[1] + off] : lado === 'der' ? [cw - ins, rc[1] + off] : lado === 'arr' ? [rc[0] + off, ins] : [rc[0] + off, ch - ins];
        P0 = [Math.min(Math.max(P0[0], ins), cw - ins), Math.min(Math.max(P0[1], ins), ch - ins)];
      }
      var L = Math.hypot(rc[0] - P0[0], rc[1] - P0[1]), cu = 0.22 * sentido;
      var Q = [(P0[0] + rc[0]) / 2 - (rc[1] - P0[1]) * cu, (P0[1] + rc[1]) / 2 + (rc[0] - P0[0]) * cu];
      o.P0 = f.r ? borde(f.r, Q, 5 * s) : P0; o.P2 = borde(d.r, Q, 6 * s); o.Q = Q; o.L = L;
      return o;
    });
    var slot = 520, T = 3 * slot, N = 3 * n + 2, D = N * slot;
    var pxB = 15 * s;

    function marcaFuente(o){                         // recuadro + etiqueta de la celda
      var out = '';
      if (o.caja){
        out += marcoR(o.caja, o.col, s);
        var tw = U.medir(o.etiqueta, 11.5 * s) + 10 * s, th = 17 * s, c = infla(o.caja, 2 * s);
        var ty = c[1] - th - 1 * s; if (ty < 2) ty = c[1] + c[3] + 1 * s;
        out += '<rect x="' + c[0] + '" y="' + ty + '" width="' + tw + '" height="' + th + '" rx="' + 4 * s + '" fill="' + o.col + '"/><text x="' + (c[0] + tw / 2) + '" y="' + (ty + th / 2) +
          '" text-anchor="middle" dominant-baseline="central" font-size="' + 11.5 * s + '" font-weight="700" fill="#ffffff">' + U.esc(o.etiqueta) + '</text>';
      } else {
        var tw2 = U.medir(o.etiqueta, 11.5 * s) + 10 * s, th2 = 17 * s;
        out += '<circle cx="' + o.P0[0] + '" cy="' + o.P0[1] + '" r="' + 5 * s + '" fill="' + o.col + '"/><rect x="' + (o.P0[0] - tw2 / 2) + '" y="' + (o.P0[1] - th2 - 8 * s) + '" width="' + tw2 +
          '" height="' + th2 + '" rx="' + 4 * s + '" fill="' + o.col + '"/><text x="' + o.P0[0] + '" y="' + (o.P0[1] - th2 / 2 - 8 * s) + '" text-anchor="middle" dominant-baseline="central" font-size="' + 11.5 * s +
          '" font-weight="700" fill="#ffffff">' + U.esc(o.etiqueta) + '</text>';
      }
      return out;
    }
    function curva(o, solida){                       // la flecha curva por el mismo camino que la burbuja
      var x1 = o.P0[0], y1 = o.P0[1], x2 = o.P2[0], y2 = o.P2[1], dx = x2 - x1, dy = y2 - y1, L2 = dx * dx + dy * dy || 1;
      var cu = ((o.Q[0] - (x1 + x2) / 2) * -dy + (o.Q[1] - (y1 + y2) / 2) * dx) / L2;
      var f = U.flecha(x1, y1, x2, y2, {color: o.col, grosor: (solida ? 3.6 : 3) * s, curva: cu, punteada: !solida});
      return solida ? f : '<g opacity="0.5">' + f + '</g>';
    }
    // burbujas (piezas) que viajan
    var piezas = [];
    for (var i = 0; i < n; i++){
      var o = G[i], t0 = i * T;
      var txt = o.caja ? corto(o.f.valor, 16) : corto(o.etiqueta + ' = ' + o.f.valor, 22);
      var b = burbuja(U, txt, pxB, o.col, s);
      var pz = await U.pieza(b.c, b.w, b.h);
      var ruta = [[0, o.P0[0], o.P0[1], 0, 0.6], [t0, o.P0[0], o.P0[1], 0, 0.6], [t0 + 0.12 * T, o.P0[0], o.P0[1], 1, 1]];
      var ta = t0 + 0.2 * T, tb = t0 + 0.66 * T, pasos = 12;
      for (var k = 0; k <= pasos; k++){
        var u = k / pasos, p = cuad(o.P0, o.Q, o.P2, ease(u));
        ruta.push([ta + (tb - ta) * u, p[0], p[1], 1, 1 - 0.15 * u]);
      }
      ruta.push([t0 + 0.78 * T, o.P2[0], o.P2[1], 0, 0.5]);
      piezas.push({png: pz.png, ax: pz.w / 2, ay: pz.h / 2, ruta: ruta});
    }
    // la burbuja final «= valor»
    var final = burbuja(U, '= ' + corto(d.valor, 20), 24 * s, resCol, s, resCol);
    var cajaF = hueco(d, U, final.w, final.h, {evitar: G.filter(function(o){ return o.caja; }).map(function(o){ return infla(o.caja, 22 * s); })});
    function estado(k){
      var out = defsSombra(s), seg = k < 3 * n ? Math.floor(k / 3) : n, sl = k % 3, fin = k >= 3 * n, fs = k - 3 * n;
      out += marcoR(d.r, resCol, s, fin);
      for (var j = 0; j < n; j++){
        if (j > seg) break;
        var o = G[j], hecha = fin || j < seg;
        out += marcaFuente(o) + curva(o, hecha || sl === 2);
      }
      if (fin && fs >= 1) out += '<g filter="url(#sombra)"><g transform="translate(' + (cajaF[0] - final.m) + ' ' + (cajaF[1] - final.m) + ')">' + final.c + '</g></g>';
      return out;
    }
    var todas = [d.r, cajaF];
    G.forEach(function(o){ if (o.caja) todas.push(o.caja); todas.push([o.P0[0], o.P0[1], 1, 1], [o.Q[0], o.Q[1], 1, 1], [o.P0[0] - 60 * s, o.P0[1] - 40 * s, 120 * s, 80 * s]); });
    var area = infla(union(todas), 36 * s);
    var fotos = await U.fotos(d, area, N, estado);
    var tramos = []; for (i = 0; i < n; i++) tramos.push([i * T, (i + 1) * T]); tramos.push([n * T, D]);
    var ocupa = [cajaF];                                     // lo que de verdad ocupa: burbuja final, fuentes y sus etiquetas
    G.forEach(function(o){ if (o.caja) ocupa.push(infla(o.caja, 3 * s), [o.caja[0] - 2 * s, o.caja[1] - 20 * s, U.medir(o.etiqueta, 11.5 * s) + 14 * s, 18 * s]); });
    return U.capa(d, area, '', {fotos: fotos, fps: 1000 / slot, piezas: piezas, duracion: D, repetir: true, pausa: 1800, tramos: tramos, ocupa: ocupa});
  });

  // ---------------------------------------------------------------- desarmar
  function partirLineas(U, texto, px, maxw){            // líneas equilibradas (hasta 3) para una nota
    var ancho = U.medir(texto, px, false);
    if (ancho <= maxw) return [texto];
    var k = Math.min(3, Math.ceil(ancho / maxw)), pal = String(texto).split(/\s+/), obj = ancho / k, lin = [], cur = '';
    pal.forEach(function(p){
      var prueba = cur ? cur + ' ' + p : p;
      if (cur && U.medir(prueba, px, false) > obj && lin.length < k - 1){ lin.push(cur); cur = p; } else cur = prueba;
    });
    if (cur) lin.push(cur);
    return lin;
  }
  function llave(x0, x1, y, h, col, s){                 // llave horizontal que abraza el texto de arriba; la punta mira abajo
    var w = x1 - x0, xm = (x0 + x1) / 2, r = Math.min(h / 2, w / 4), yh = y + h / 2;
    return '<path d="M' + x0 + ' ' + y + ' Q' + x0 + ' ' + yh + ' ' + (x0 + r) + ' ' + yh + ' L' + (xm - r) + ' ' + yh + ' Q' + xm + ' ' + yh + ' ' + xm + ' ' + (y + h) +
      ' M' + xm + ' ' + (y + h) + ' Q' + xm + ' ' + yh + ' ' + (xm + r) + ' ' + yh + ' L' + (x1 - r) + ' ' + yh + ' Q' + x1 + ' ' + yh + ' ' + x1 + ' ' + y +
      '" fill="none" stroke="' + col + '" stroke-width="' + 2.4 * s + '" stroke-linecap="round" stroke-linejoin="round"/>';
  }

  Dibujante.registrar('desarmar', async function(d, U){
    var s = d.escala || 1, cw = d.cliente[0], col = U.color(d.color), pad = 18 * s;
    var orig = String(d.original == null ? '' : d.original), partes = (d.partes || []).filter(function(p){ return p && p.texto; });
    var unaLinea = orig.indexOf('\n') < 0;
    var P = 26 * s, chw = medirMono('0', 100) / 100;
    var libre = cw * 0.86 - 2 * pad;
    if (unaLinea && medirMono(orig, P) > libre) P = Math.max(15 * s, P * libre / medirMono(orig, P));
    var lineas = orig.split('\n');
    if (unaLinea && medirMono(orig, P) > libre){          // aun así no cabe: se parte en líneas de ancho fijo y las partes van en lista
      var por = Math.max(20, Math.floor(libre / (chw * P))); lineas = [];
      for (var q = 0; q < orig.length; q += por) lineas.push(orig.slice(q, q + por));
      unaLinea = false;
    }
    var lineH = P * 1.4, textoW = 0;
    lineas.forEach(function(l){ textoW = Math.max(textoW, medirMono(l, P)); });
    var Np = 14.5 * s, hb = 11 * s, yTexto = pad, yLlave = yTexto + lineH * lineas.length + 3 * s;
    // ubica cada parte en el texto (de izquierda a derecha)
    var desde = 0, ubic = partes.map(function(p, k){
      var col2 = U.color(p.color || PALETA[k % PALETA.length]), t = String(p.texto), idx = -1;
      if (unaLinea){
        idx = orig.indexOf(t, desde); if (idx < 0) idx = orig.indexOf(t);
        if (idx >= 0) desde = idx + t.length;
      }
      return {p: p, k: k, col: col2, idx: idx, t: t};
    });
    ubic.forEach(function(u){
      if (u.idx < 0) return;
      var a = u.idx, b = u.idx + u.t.length;
      while (a < b && /\s/.test(orig[a])) a++; while (b > a && /\s/.test(orig[b - 1])) b--;
      u.xa = pad + medirMono(orig.slice(0, a), P); u.xb = pad + medirMono(orig.slice(0, b), P);
      u.cx = (u.xa + u.xb) / 2;
      u.lin = partirLineas(U, u.p.nota || '', Np, Math.max(140 * s, Math.min(210 * s, (u.xb - u.xa) * 1.1)));
      u.nw = 0; u.lin.forEach(function(l){ u.nw = Math.max(u.nw, U.medir(l, Np, false)); });
      u.nh = u.lin.length * Np * 1.3;
      u.nx = u.cx - u.nw / 2;
    });
    var en = ubic.filter(function(u){ return u.idx >= 0; }).sort(function(a, b){ return a.cx - b.cx; });
    var niveles = [];                                      // para que las notas no choquen: alturas alternas
    en.forEach(function(u){
      var l = 0;
      while (niveles[l] && niveles[l].some(function(v){ return !(u.nx + u.nw + 10 * s <= v.nx || v.nx + v.nw + 10 * s <= u.nx); })) l++;
      (niveles[l] = niveles[l] || []).push(u); u.nivel = l;
    });
    var altN = niveles.map(function(L){ return Math.max.apply(null, L.map(function(u){ return u.nh; })); });
    var yN = [], acc = yLlave + hb + 8 * s;
    altN.forEach(function(a, l){ yN[l] = acc; acc += a + 8 * s; });
    var finNotas = en.length ? acc : yLlave;
    var sueltas = ubic.filter(function(u){ return u.idx < 0; }), ySueltas = finNotas + (sueltas.length ? 4 * s : 0), hS = Np * 1.7;
    var izq = 0, der = pad + textoW + pad;
    en.forEach(function(u){ izq = Math.min(izq, u.nx - 10 * s); der = Math.max(der, u.nx + u.nw + 10 * s); });
    sueltas.forEach(function(u){
      u.linea = u.t + '  —  ' + (u.p.nota || ''); u.lw = 20 * s + medirMono(u.t, Np) + 28 * s + U.medir(u.p.nota || '', Np, false);
      der = Math.max(der, pad + u.lw + pad - izq);
    });
    var cardW = Math.min(der - izq, cw - 8 * s), cardH = ySueltas + sueltas.length * hS + (sueltas.length || en.length ? pad - 2 * s : pad);
    if (!en.length && !sueltas.length) cardH = yLlave + pad;
    var caja = hueco(d, U, cardW, cardH);
    var ox = caja[0] - izq, oy = caja[1];                  // lo local (x desde `izq`, y desde 0) → cliente
    // base: la tarjeta con el texto
    var out = defsSombra(s);
    if (d.r) out += marcoR(d.r, col, s) + flechaA(U, caja, d.r, col, s);
    out += '<rect x="' + caja[0] + '" y="' + caja[1] + '" width="' + cardW + '" height="' + cardH + '" rx="' + 11 * s + '" fill="#ffffff" fill-opacity="0.97" stroke="' + col + '" stroke-width="' + 2 * s + '" filter="url(#sombra)"/>';
    lineas.forEach(function(l, i){
      out += '<text xml:space="preserve" x="' + (ox + pad) + '" y="' + (oy + yTexto + lineH * i + lineH / 2) + '" dominant-baseline="central" font-family="' + MONO + '" font-size="' + P + '" font-weight="600" fill="' + TINTA + '">' + U.esc(l) + '</text>';
    });
    // piezas: cada parte con su resaltado, llave y nota
    var piezas = [], T = 1300, D = partes.length * T + 700;
    for (var k = 0; k < ubic.length; k++){
      var u = ubic[k], c = '', box;
      if (u.idx >= 0){
        var ya = yTexto + 2 * s, yb = yLlave + hb;
        var nx = u.nx, ny = yN[u.nivel];
        var x0 = Math.min(u.xa, nx), x1 = Math.max(u.xb, nx + u.nw);
        box = [x0 - 6 * s, ya - 3 * s, x1 - x0 + 12 * s, ny + u.nh - ya + 8 * s];
        c += '<rect x="' + u.xa + '" y="' + ya + '" width="' + (u.xb - u.xa) + '" height="' + (lineH - 4 * s) + '" rx="' + 4 * s + '" fill="' + u.col + '" fill-opacity="0.2"/>';
        c += llave(u.xa + 1.5 * s, u.xb - 1.5 * s, yLlave, hb, u.col, s);
        if (u.nivel > 0) c += '<line x1="' + u.cx + '" y1="' + (yLlave + hb + 1 * s) + '" x2="' + u.cx + '" y2="' + (ny - 2 * s) + '" stroke="' + u.col + '" stroke-width="' + 1.6 * s + '" stroke-dasharray="' + 3 * s + ' ' + 3 * s + '"/>';
        u.lin.forEach(function(l, i){
          c += '<text x="' + (u.cx) + '" y="' + (ny + Np * 1.3 * i + Np * 0.65) + '" text-anchor="middle" dominant-baseline="central" font-size="' + Np + '" font-weight="600" fill="' + u.col + '" stroke="#ffffff" stroke-width="' + 3 * s + '" paint-order="stroke" stroke-linejoin="round">' + U.esc(l) + '</text>';
        });
      } else {
        var j = sueltas.indexOf(u), yy = ySueltas + j * hS;
        box = [pad - 6 * s, yy, u.lw + 12 * s, hS];
        c += '<rect x="' + pad + '" y="' + (yy + hS / 2 - 6 * s) + '" width="' + 12 * s + '" height="' + 12 * s + '" rx="' + 3 * s + '" fill="' + u.col + '"/>' +
          '<text x="' + (pad + 20 * s) + '" y="' + (yy + hS / 2) + '" dominant-baseline="central" font-family="' + MONO + '" font-size="' + Np + '" font-weight="600" fill="' + u.col + '">' + U.esc(u.t) + '</text>' +
          '<text x="' + (pad + 20 * s + medirMono(u.t, Np) + 28 * s) + '" y="' + (yy + hS / 2) + '" dominant-baseline="central" font-size="' + Np + '" fill="' + TINTA + '">' + U.esc(u.p.nota || '') + '</text>';
        c = '<g>' + c + '</g>';
      }
      var wb = Math.ceil(box[2]), hb2 = Math.ceil(box[3]);
      var pz = await U.pieza('<g transform="translate(' + (-box[0]) + ' ' + (-box[1]) + ')">' + c + '</g>', wb, hb2);
      var px0 = ox + box[0], py0 = oy + box[1], t0 = k * T + 150;
      piezas.push({png: pz.png, ax: 0, ay: 0, ruta: [[0, px0, py0, 0, 1], [t0, px0, py0, 0, 1], [t0 + 350, px0, py0, 1, 1]]});
    }
    var tramos = ubic.map(function(u, k){ return [k * T, (k + 1) * T]; });
    var area = infla(union([caja, d.r ? infla(d.r, 8 * s) : null]), 26 * s);
    return U.capa(d, area, out, {piezas: piezas, duracion: D, repetir: false, tramos: tramos, ocupa: [caja]});
  });
})();
