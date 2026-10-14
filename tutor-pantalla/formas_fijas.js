/* Formas «fijas» del dibujante: foco, teclas, mano, lupa y svg. Se registran en Dibujante (dibujante.js);
   el contrato está en DIBUJOS.md. Todo en píxeles de cliente; los tamaños se multiplican por d.escala. */
(function(){
  if (!window.Dibujante) return;
  var D = window.Dibujante;

  // ---------- ayudas comunes ----------
  function clientes(d){ var c = d.cliente || [1600, 900]; return [c[0], c[1]]; }
  function relevantes(d){                     // controles que no deben taparse (menos los que están dentro del objetivo)
    return (d.evitar || []).filter(function(e){ return !d.r || !choca(e, d.r); });
  }
  function choca(a, b, m){ m = m || 0; return !(a[0] + a[2] + m <= b[0] || b[0] + b[2] + m <= a[0] || a[1] + a[3] + m <= b[1] || b[1] + b[3] + m <= a[1]); }
  function solape(a, b){ var w = Math.min(a[0] + a[2], b[0] + b[2]) - Math.max(a[0], b[0]), h = Math.min(a[1] + a[3], b[1] + b[3]) - Math.max(a[1], b[1]); return w > 0 && h > 0 ? w * h : 0; }
  // Penalización de una caja candidata: lo que se sale del cliente y lo que tapa (0 = sitio perfecto).
  function puntuar(d, caja, prohibidas, margen){
    var c = clientes(d), m = margen == null ? 2 : margen, p = 0;
    var dentro = Math.max(0, Math.min(caja[0] + caja[2], c[0] - m) - Math.max(caja[0], m)) * Math.max(0, Math.min(caja[1] + caja[3], c[1] - m) - Math.max(caja[1], m));
    p += (caja[2] * caja[3] - dentro) * 10;
    (prohibidas || []).forEach(function(o){ p += solape(caja, o) * (o.fuerte ? 50 : 4); });
    return p;
  }
  function mejor(d, cands, prohibidas){        // la candidata de menor penalización (la primera si empatan)
    var b = null, bp = Infinity;
    cands.forEach(function(c){ var p = puntuar(d, c, prohibidas); if (p < bp - 1e-6){ bp = p; b = c; } });
    return b;
  }
  function fuerte(caja){ var c = caja.slice(); c.fuerte = true; return c; }
  function union(cajas, pad){
    var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    cajas.forEach(function(c){ x0 = Math.min(x0, c[0]); y0 = Math.min(y0, c[1]); x1 = Math.max(x1, c[0] + c[2]); y1 = Math.max(y1, c[1] + c[3]); });
    return [x0 - pad, y0 - pad, x1 - x0 + 2 * pad, y1 - y0 + 2 * pad];
  }
  function sombra(id, dy, desv, op){
    return '<filter id="' + id + '" x="-30%" y="-30%" width="160%" height="170%"><feDropShadow dx="0" dy="' + dy + '" stdDeviation="' + desv + '" flood-color="#0b1020" flood-opacity="' + op + '"/></filter>';
  }
  var med = document.createElement('canvas').getContext('2d');
  function medirFuente(texto, px, fuente){ med.font = px + 'px ' + fuente; return med.measureText(String(texto)).width; }

  // =====================================================================================================
  // 1. foco: oscurece todo menos el objetivo; un anillo late alrededor
  // =====================================================================================================
  D.registrar('foco', async function(d, U){
    if (!d.r) throw new Error('foco necesita un objetivo');
    var s = d.escala || 1, c = clientes(d), col = U.color(d.color);
    var osc = d.oscuro == null ? 0.55 : Math.max(0, Math.min(1, d.oscuro));
    var m = 6 * s, hx = d.r[0] - m, hy = d.r[1] - m, hw = d.r[2] + 2 * m, hh = d.r[3] + 2 * m, rx = 9 * s;
    var desv = 3.2 * s;
    var cont =
      '<defs><filter id="bl" filterUnits="userSpaceOnUse" x="-50" y="-50" width="' + (c[0] + 100) + '" height="' + (c[1] + 100) + '"><feGaussianBlur stdDeviation="' + desv + '"/></filter>' +
      '<mask id="mk" maskUnits="userSpaceOnUse" x="0" y="0" width="' + c[0] + '" height="' + c[1] + '"><rect width="' + c[0] + '" height="' + c[1] + '" fill="#fff"/>' +
      '<rect x="' + hx + '" y="' + hy + '" width="' + hw + '" height="' + hh + '" rx="' + rx + '" fill="#000" filter="url(#bl)"/></mask></defs>' +
      '<rect width="' + c[0] + '" height="' + c[1] + '" fill="#080d1c" fill-opacity="' + osc + '" mask="url(#mk)"/>' +
      '<rect x="' + hx + '" y="' + hy + '" width="' + hw + '" height="' + hh + '" rx="' + rx + '" fill="none" stroke="' + col + '" stroke-opacity="0.9" stroke-width="' + 2 * s + '"/>';
    var nota = d.texto ? U.nota(d, d.texto, {color: d.color}) : null;
    // anillo que late: una pieza centrada en el hueco
    var g = 14 * s, pw = hw + 2 * g, ph = hh + 2 * g;
    var anillo = await U.pieza('<defs>' + sombra('gl', 0, 4 * s, 0.0) + '</defs>' +
      '<rect x="' + (g + 1.5 * s) + '" y="' + (g + 1.5 * s) + '" width="' + (hw - 3 * s) + '" height="' + (hh - 3 * s) + '" rx="' + rx + '" fill="none" stroke="' + col + '" stroke-opacity="0.35" stroke-width="' + 9 * s + '"/>' +
      '<rect x="' + g + '" y="' + g + '" width="' + hw + '" height="' + hh + '" rx="' + rx + '" fill="none" stroke="' + col + '" stroke-width="' + 3 * s + '"/>', pw, ph);
    var cx = hx + hw / 2, cy = hy + hh / 2;
    return U.capa(d, [0, 0, c[0], c[1]], cont + (nota ? nota.svg : ''), {
      piezas: [{png: anillo.png, ax: pw / 2, ay: ph / 2, ruta: [[0, cx, cy, 0.95, 1], [800, cx, cy, 0.4, 1.06], [1600, cx, cy, 0.95, 1]]}],
      duracion: 1600, repetir: true, pausa: 0
    });
  });

  // =====================================================================================================
  // 2. teclas: se pulsan una tras otra, quedan pulsadas y se sueltan
  // =====================================================================================================
  var SIMBOLOS = {enter: 'Enter ↵', intro: 'Enter ↵', win: '⊞ Win', windows: '⊞ Windows', shift: '⇧ Shift', izquierda: '←', derecha: '→', arriba: '↑', abajo: '↓',
                  left: '←', right: '→', up: '↑', down: '↓', flechaizquierda: '←', flechaderecha: '→', flecha_arriba: '↑', flecha_abajo: '↓',
                  tab: 'Tab ⇥', backspace: '⌫ Backspace', retroceso: '⌫ Retroceso'};
  function etiqueta(t){ t = String(t); var k = SIMBOLOS[t.toLowerCase().replace(/\s+/g, '')]; return k || t; }
  var FUENTE_TECLA = "'Segoe UI', 'Segoe UI Symbol', 'Segoe UI Emoji', sans-serif";

  D.registrar('teclas', async function(d, U){
    var lista = (d.teclas || []).slice(0, 5).map(etiqueta);
    if (!lista.length) throw new Error('teclas: falta la lista «teclas»');
    var s = d.escala || 1, c = clientes(d), col = U.color(d.color);
    var px = 17 * s, alto = 40 * s, dep = 4 * s, baja = 3 * s, pad = 7 * s, hueco = 28 * s;
    var anchos;
    // se mide con U.medir (semibold) y con la fuente de símbolos; vale el mayor
    anchos = lista.map(function(t){ return Math.max(alto, Math.max(U.medir(t, px), medirFuente(t, px, FUENTE_TECLA)) + 26 * s); });
    var total = anchos.reduce(function(a, b){ return a + b; }, 0) + hueco * (lista.length - 1);
    var tw = total + 2 * 12 * s, th = alto + dep + 2 * 12 * s;     // placa de fondo
    var cands, r = d.r, gap = 14 * s;
    if (r){
      var cx = r[0] + r[2] / 2, cy = r[1] + r[3] / 2;
      cands = [[cx - tw / 2, r[1] + r[3] + gap], [cx - tw / 2, r[1] - gap - th], [r[0] + r[2] + gap, cy - th / 2], [r[0] - gap - tw, cy - th / 2],
               [cx - tw / 2, r[1] + r[3] + 3 * gap], [cx - tw / 2, r[1] - 3 * gap - th]];
      cands = cands.map(function(k){ return [Math.min(Math.max(2, k[0]), c[0] - tw - 2), Math.min(Math.max(2, k[1]), c[1] - th - 2), tw, th]; });
    } else cands = [[(c[0] - tw) / 2, c[1] - th - 28 * s, tw, th]];
    var pl = mejor(d, cands, relevantes(d).concat(r ? [fuerte(r)] : []));
    var x0 = pl[0] + 12 * s, y0 = pl[1] + 12 * s;
    var cont = '<defs>' + sombra('pl', 3 * s, 6 * s, 0.28) + '</defs>' +
      '<rect x="' + pl[0] + '" y="' + pl[1] + '" width="' + tw + '" height="' + th + '" rx="' + 14 * s + '" fill="#fff" fill-opacity="0.86" stroke="' + col + '" stroke-opacity="0.55" stroke-width="' + 1.6 * s + '" filter="url(#pl)"/>';
    var pos = [], x = x0;
    lista.forEach(function(t, i){
      pos.push(x);
      if (i < lista.length - 1) cont += '<text x="' + (x + anchos[i] + hueco / 2) + '" y="' + (y0 + alto / 2) + '" text-anchor="middle" dominant-baseline="central" font-size="' + 22 * s + '" font-weight="600" fill="#596072">+</text>';
      x += anchos[i] + hueco;
    });
    var nota = d.texto ? U.nota(d, d.texto, {color: d.color, cerca: pl}) : null;
    if (nota) cont += nota.svg;
    // dibujo de una tecla: arriba (levantada) o abajo (pulsada)
    function tecla(t, w, abajo){
      var ty = pad + (abajo ? baja : 0), g = abajo ? ['#dfe3ec', '#cdd2df'] : ['#ffffff', '#eceff6'];
      return '<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="' + g[0] + '"/><stop offset="1" stop-color="' + g[1] + '"/></linearGradient>' +
        '<filter id="s" x="-20%" y="-20%" width="140%" height="160%"><feGaussianBlur stdDeviation="' + 2.2 * s + '"/></filter></defs>' +
        '<rect x="' + (pad + 1) + '" y="' + (pad + dep + 3 * s) + '" width="' + (w - 2) + '" height="' + alto + '" rx="' + 8 * s + '" fill="#0b1020" fill-opacity="' + (abajo ? 0.12 : 0.3) + '" filter="url(#s)"/>' +
        '<rect x="' + pad + '" y="' + (pad + dep) + '" width="' + w + '" height="' + alto + '" rx="' + 8 * s + '" fill="#9aa1b2"/>' +
        '<rect x="' + pad + '" y="' + ty + '" width="' + w + '" height="' + alto + '" rx="' + 8 * s + '" fill="url(#g)" stroke="#aab0c0" stroke-width="' + 1.3 * s + '"/>' +
        '<text x="' + (pad + w / 2) + '" y="' + (ty + alto / 2 + 1 * s) + '" text-anchor="middle" dominant-baseline="central" font-family="' + FUENTE_TECLA + '" font-size="' + px + '" font-weight="600" fill="' + (abajo ? '#1a1e2a' : '#2b3040') + '">' + U.esc(t) + '</text>';
    }
    var piezas = [], t0 = 350, paso = 380;
    var pulsa = lista.map(function(_, i){ return t0 + i * paso; });
    var suelta = pulsa[pulsa.length - 1] + 750, fin = suelta + 350;
    for (var i = 0; i < lista.length; i++){
      var pw = anchos[i] + 2 * pad, ph = alto + dep + 2 * pad;
      var a = await U.pieza(tecla(lista[i], anchos[i], false), pw, ph), b = await U.pieza(tecla(lista[i], anchos[i], true), pw, ph);
      var px0 = pos[i] - pad, py0 = y0 - pad, p = pulsa[i];
      piezas.push({png: a.png, ax: 0, ay: 0, ruta: [[0, px0, py0, 1, 1], [p - 1, px0, py0, 1, 1], [p, px0, py0, 0, 1], [suelta - 1, px0, py0, 0, 1], [suelta, px0, py0, 1, 1], [fin, px0, py0, 1, 1]]});
      piezas.push({png: b.png, ax: 0, ay: 0, ruta: [[0, px0, py0, 0, 1], [p - 1, px0, py0, 0, 1], [p, px0, py0, 1, 1], [suelta - 1, px0, py0, 1, 1], [suelta, px0, py0, 0, 1], [fin, px0, py0, 0, 1]]});
    }
    var caja = union([[pl[0], pl[1], tw, th]].concat(nota ? [nota.caja] : []), 14 * s);
    return U.capa(d, caja, cont, {piezas: piezas, duracion: fin, repetir: true, pausa: 1200});
  });

  // =====================================================================================================
  // 3. mano: trazo a mano alzada (rough.js) que se va dibujando
  // =====================================================================================================
  var MANO = "'Ink Free', 'Segoe Print', cursive";
  function atan2d(y, x){ return Math.atan2(y, x); }

  D.registrar('mano', async function(d, U){
    if (!d.r) throw new Error('mano necesita un objetivo');
    await U.cargar('rough');
    var s = d.escala || 1, c = clientes(d), col = U.color(d.color), r = d.r, trazo = d.trazo || 'circulo';
    var gen = rough.generator();
    var sw = 3.4 * s;
    function opc(sem){ return {seed: sem, roughness: 1.1, bowing: 1.2, strokeWidth: sw, stroke: col, fill: 'none'}; }
    var cx = r[0] + r[2] / 2, cy = r[1] + r[3] / 2, m = 11 * s;
    var trozos = [];                 // cada trozo es una lista de paths (d) que se dibujan seguidos
    function paths(drawable){ return gen.toPaths(drawable).map(function(p){ return p.d; }); }
    var pts = [], pad = 8 * s;
    var cajaTrazo, inicio = null, tipo = trazo;
    if (tipo === 'circulo'){
      var a = Math.max(r[2] / 2 + m, 22 * s), b = Math.max(r[3] / 2 + m, 22 * s);
      if (r[2] > 3 * r[3]) b = r[3] / 2 + m * 0.9;
      var ang0 = -2.0, vuelta = Math.PI * 2 + 0.55, n = 15, tilt = -0.07;
      for (var i = 0; i <= n; i++){
        var u = i / n, th = ang0 + u * vuelta, k = 1 + 0.02 + 0.075 * u;
        var ex = Math.cos(th) * a * k, ey = Math.sin(th) * b * k;
        pts.push([cx + ex * Math.cos(tilt) - ey * Math.sin(tilt), cy + ex * Math.sin(tilt) + ey * Math.cos(tilt)]);
      }
      trozos.push(paths(gen.curve(pts, opc(11))));
      cajaTrazo = [cx - a * 1.12, cy - b * 1.12, a * 2.24, b * 2.24];
    } else if (tipo === 'subrayado'){
      var y = r[1] + r[3] + 7 * s, x0 = r[0] - 4 * s, x1 = r[0] + r[2] + 6 * s, w = x1 - x0, q = [];
      for (var j = 0; j <= 5; j++) q.push([x0 + w * j / 5, y + Math.sin(j * 1.3) * 2.2 * s + j * 0.6 * s]);
      trozos.push(paths(gen.curve(q, opc(5))));
      cajaTrazo = [x0, y - 6 * s, w, 14 * s];
    } else if (tipo === 'tache'){
      var tw = Math.max(r[2], 22 * s) + 8 * s, th2 = Math.max(r[3], 22 * s) + 8 * s;
      var X0 = cx - tw / 2, X1 = cx + tw / 2, Y0 = cy - th2 / 2, Y1 = cy + th2 / 2;
      trozos.push(paths(gen.line(X0, Y0, X1, Y1, opc(3))));
      trozos.push(paths(gen.line(X1, Y0 + 2 * s, X0 + 2 * s, Y1, opc(8))));
      cajaTrazo = [X0, Y0, tw, th2];
    } else if (tipo === 'check'){
      var W = 26 * s, H = 28 * s, gp = 10 * s, rel = relevantes(d).concat([fuerte(r)]);
      var cs = [[r[0] + r[2] + gp, cy - H * 0.55, W, H], [r[0] - gp - W, cy - H * 0.55, W, H], [cx - W / 2, r[1] - gp - H, W, H], [cx - W / 2, r[1] + r[3] + gp, W, H]];
      var cb = mejor(d, cs, rel);
      trozos.push(paths(gen.linearPath([[cb[0], cb[1] + H * 0.55], [cb[0] + W * 0.34, cb[1] + H], [cb[0] + W, cb[1]]], opc(6))));
      cajaTrazo = cb;
    } else if (tipo === 'flecha'){
      var L = 85 * s, rel2 = relevantes(d).concat([fuerte(r)]);
      var dirs = [[-1, -0.75], [1, -0.75], [-1, 0.75], [1, 0.75], [0, -1], [0, 1], [-1, 0], [1, 0]];
      var tx = d.texto ? medirFuente(d.texto, 26 * s, MANO) : 0, th3 = 30 * s, mejorC = null, mejorP = Infinity;
      dirs.forEach(function(v){
        var nv = Math.hypot(v[0], v[1]), ux = v[0] / nv, uy = v[1] / nv;
        // salida del rectángulo (con margen) por esa dirección
        var hx = r[2] / 2 + 6 * s, hy = r[3] / 2 + 6 * s, tt = Math.min(ux ? hx / Math.abs(ux) : 1e9, uy ? hy / Math.abs(uy) : 1e9);
        var sx = cx + ux * (tt + L), sy = cy + uy * (tt + L);
        var tb = null, pen;
        if (d.texto){
          var cand = [[sx - tx / 2, sy - th3 - 6 * s, tx, th3], [sx - tx / 2, sy + 6 * s, tx, th3], [sx + 6 * s, sy - th3 / 2, tx, th3], [sx - tx - 6 * s, sy - th3 / 2, tx, th3]];
          tb = mejor(d, cand, rel2);
          var pref = ux > 0.3 ? 2 : ux < -0.3 ? 3 : (uy < 0 ? 0 : 1);
          if (puntuar(d, cand[pref], rel2) <= puntuar(d, tb, rel2) + 1e-6) tb = cand[pref];
        } else tb = [sx - 8 * s, sy - 8 * s, 16 * s, 16 * s];
        pen = puntuar(d, tb, rel2) + puntuar(d, [sx - 4, sy - 4, 8, 8], rel2) * 3 + (uy > 0 ? 1 : 0);
        if (pen < mejorP - 1e-6){ mejorP = pen; mejorC = {sx: sx, sy: sy, ux: ux, uy: uy, tt: tt, tb: tb}; }
      });
      var M = mejorC, tipX = cx + M.ux * (M.tt + 5 * s), tipY = cy + M.uy * (M.tt + 5 * s);
      var dx = tipX - M.sx, dy = tipY - M.sy, lg = Math.hypot(dx, dy), curv = 0.14 * lg;
      var mx = (M.sx + tipX) / 2 - dy / lg * curv, my = (M.sy + tipY) / 2 + dx / lg * curv;
      var tdx = tipX - mx, tdy = tipY - my, tl = Math.hypot(tdx, tdy), ex2 = tdx / tl, ey2 = tdy / tl, hl = 15 * s;
      var h1 = [tipX - ex2 * hl - ey2 * hl * 0.55, tipY - ey2 * hl + ex2 * hl * 0.55], h2 = [tipX - ex2 * hl + ey2 * hl * 0.55, tipY - ey2 * hl - ex2 * hl * 0.55];
      trozos.push(paths(gen.curve([[M.sx, M.sy], [mx, my], [tipX, tipY]], opc(4))));
      trozos.push(paths(gen.linearPath([h1, [tipX, tipY], h2], opc(9))));
      cajaTrazo = union([[Math.min(M.sx, tipX, mx), Math.min(M.sy, tipY, my), Math.abs(tipX - M.sx) || 1, Math.abs(tipY - M.sy) || 1]], 0);
      inicio = M.tb;
    } else throw new Error('mano: trazo desconocido «' + tipo + '»');

    // texto a mano junto al trazo
    var caja = cajaTrazo, textoSVG = '', tcaja = null, pxm = 26 * s;
    if (d.texto){
      var tw2 = medirFuente(d.texto, pxm, MANO), th4 = 31 * s;
      if (inicio) tcaja = inicio;
      else {
        var g2 = 8 * s, o = cajaTrazo, rel3 = relevantes(d).concat([fuerte(r)]);
        var cc = tipo === 'subrayado' ? [[o[0], o[1] + o[3] + g2 / 2, tw2, th4], [o[0] + o[2] - tw2, o[1] + o[3] + g2 / 2, tw2, th4], [o[0] + o[2] + g2, o[1] + o[3] / 2 - th4 / 2, tw2, th4], [o[0], r[1] - th4 - 6 * s, tw2, th4]]
          : [[o[0] + o[2] + g2, o[1] + o[3] / 2 - th4 / 2, tw2, th4], [o[0] + o[2] / 2 - tw2 / 2, o[1] + o[3] + g2 / 2, tw2, th4], [o[0] + o[2] / 2 - tw2 / 2, o[1] - th4 - g2 / 2, tw2, th4], [o[0] - g2 - tw2, o[1] + o[3] / 2 - th4 / 2, tw2, th4]];
        tcaja = mejor(d, cc, rel3.concat([fuerte(cajaTrazo)]));
      }
      caja = union([cajaTrazo, tcaja], 0);
      textoSVG = function(op){
        return '<text x="' + (tcaja[0] + tcaja[2] / 2) + '" y="' + (tcaja[1] + tcaja[3] / 2) + '" text-anchor="middle" dominant-baseline="central" font-family="' + MANO + '" font-size="' + pxm + '" fill="' + col + '" fill-opacity="' + op + '" stroke="#fff" stroke-opacity="' + op * 0.7 + '" stroke-width="' + 4 * s + '" stroke-linejoin="round" paint-order="stroke" transform="rotate(-2 ' + (tcaja[0] + tcaja[2] / 2) + ' ' + (tcaja[1] + tcaja[3] / 2) + ')">' + U.esc(d.texto) + '</text>';
      };
    }
    caja = union([caja], pad + 6 * s);

    // longitudes (para repartir el tiempo entre trozos y paths)
    var todos = [];
    trozos.forEach(function(lista, ti){ lista.forEach(function(dd){ todos.push({d: dd, ti: ti, len: 1}); }); });
    todos.forEach(function(p){
      try { var e = document.createElementNS('http://www.w3.org/2000/svg', 'path'); e.setAttribute('d', p.d); p.len = Math.max(1, e.getTotalLength()); } catch (e2){}
    });
    var suma = todos.reduce(function(a, p){ return a + p.len; }, 0), acum = 0;
    todos.forEach(function(p){ p.a = acum / suma; acum += p.len; p.b = acum / suma; });
    var N = 16, TR = 12, FPS = 24;
    function frame(k){
      var g = Math.min(1, (k + 1) / TR); g = 0.5 - 0.5 * Math.cos(Math.PI * g);
      if (k + 1 >= TR) g = 1;
      var o = '';
      todos.forEach(function(p){
        var q = Math.max(0, Math.min(1, (g - p.a) / (p.b - p.a)));
        if (q <= 0) return;
        var da = q >= 1 ? '' : ' stroke-dasharray="1 2" stroke-dashoffset="' + (1 - q) + '"';
        o += '<path d="' + p.d + '" pathLength="1" fill="none" stroke="#fff" stroke-opacity="0.6" stroke-width="' + (sw + 3.2 * s) + '" stroke-linecap="round" stroke-linejoin="round"' + da + '/>';
      });
      todos.forEach(function(p){
        var q = Math.max(0, Math.min(1, (g - p.a) / (p.b - p.a)));
        if (q <= 0) return;
        var da = q >= 1 ? '' : ' stroke-dasharray="1 2" stroke-dashoffset="' + (1 - q) + '"';
        o += '<path d="' + p.d + '" pathLength="1" fill="none" stroke="' + col + '" stroke-width="' + sw + '" stroke-linecap="round" stroke-linejoin="round"' + da + '/>';
      });
      if (textoSVG){ var op = Math.max(0, Math.min(1, (k + 1 - (TR - 2)) / 4)); if (op > 0) o += textoSVG(op); }
      return o;
    }
    var fotos = await U.fotos(d, caja, N, function(k){ return frame(k); });
    if (!fotos.length) return null;
    return U.capa(d, caja, '', {fotos: fotos, fps: FPS, duracion: Math.ceil(N * 1000 / FPS), repetir: false});
  });

  // =====================================================================================================
  // 4. lupa: la zona aumentada en una lente cercana (los píxeles los pone capa.py en vivo)
  // =====================================================================================================
  D.registrar('lupa', async function(d, U){
    if (!d.r) throw new Error('lupa necesita una zona');
    var s = d.escala || 1, c = clientes(d), col = U.color(d.color), aum = d.aumento > 0 ? d.aumento : 2.5;
    var mz = 3, z = [Math.max(0, d.r[0] - mz), Math.max(0, d.r[1] - mz), d.r[2] + 2 * mz, d.r[3] + 2 * mz];
    z = [z[0], z[1], Math.min(z[2], c[0] - z[0]), Math.min(z[3], c[1] - z[1])];
    var lw = z[2] * aum, lh = z[3] * aum;
    var tope = Math.min(0.4 * c[0] / lw, 0.4 * c[1] / lh, 1); lw *= tope; lh *= tope;     // tope: 40 % del cliente
    var minimo = 140 * s, sm = Math.min(lw, lh);
    if (sm < minimo){ var f = minimo / sm; lw *= f; lh *= f; if (lw > 0.4 * c[0] || lh > 0.4 * c[1]){ var f2 = Math.min(0.4 * c[0] / lw, 0.4 * c[1] / lh); lw *= f2; lh *= f2; } }
    lw = Math.round(lw); lh = Math.round(lh);
    var real = lw / z[2], radio = Math.round(10 * s);
    // sitio de la lente: cerca, sin tapar la zona ni (si se puede) los controles
    var rel = relevantes(d), zc = [z[0] + z[2] / 2, z[1] + z[3] / 2], cands = [];
    [26, 55, 100, 170, 260].forEach(function(g){
      g *= s;
      cands.push([z[0] + z[2] + g, zc[1] - lh / 2], [zc[0] - lw / 2, z[1] + z[3] + g], [z[0] - g - lw, zc[1] - lh / 2], [zc[0] - lw / 2, z[1] - g - lh],
                 [z[0] + z[2] + g, z[1] + z[3] + g * 0.6], [z[0] - g - lw, z[1] + z[3] + g * 0.6], [z[0] + z[2] + g, z[1] - g * 0.6 - lh], [z[0] - g - lw, z[1] - g * 0.6 - lh]);
    });
    cands = cands.map(function(k){ return [Math.min(Math.max(4 * s, k[0]), c[0] - lw - 4 * s), Math.min(Math.max(4 * s, k[1]), c[1] - lh - 4 * s), lw, lh]; });
    var lejos = cands.filter(function(k){ return !choca(k, z, 10 * s); });
    var lente = mejor(d, lejos.length ? lejos : cands, rel.concat([fuerte(z)]));
    var lc = [lente[0] + lw / 2, lente[1] + lh / 2];
    // líneas de conexión: las dos esquinas de la silueta
    var dx = lc[0] - zc[0], dy = lc[1] - zc[1], esq = [[-1, -1], [1, -1], [1, 1], [-1, 1]];
    function info(e){ return {e: e, cross: dx * e[1] - dy * e[0], dot: dx * e[0] + dy * e[1]}; }
    var ls = esq.map(info);
    var pa = ls.slice().sort(function(a, b){ return b.cross - a.cross || b.dot - a.dot; })[0];
    var pb = ls.slice().sort(function(a, b){ return a.cross - b.cross || b.dot - a.dot; })[0];
    function ec(cj, e){ return [cj[0] + (e[0] > 0 ? cj[2] : 0), cj[1] + (e[1] > 0 ? cj[3] : 0)]; }
    var cont = '<defs>' + sombra('zs', 1 * s, 1.4 * s, 0.25) + '</defs>';
    [pa, pb].forEach(function(p, i){
      if (i && pa.e === pb.e) return;
      var A = ec(z, p.e), B = ec(lente, p.e);
      cont += '<line x1="' + A[0] + '" y1="' + A[1] + '" x2="' + B[0] + '" y2="' + B[1] + '" stroke="' + col + '" stroke-opacity="0.75" stroke-width="' + 1.5 * s + '" stroke-dasharray="' + 5 * s + ' ' + 4 * s + '"/>';
    });
    cont += '<rect x="' + (z[0] - 1) + '" y="' + (z[1] - 1) + '" width="' + (z[2] + 2) + '" height="' + (z[3] + 2) + '" rx="' + 3 * s + '" fill="none" stroke="#fff" stroke-opacity="0.8" stroke-width="' + 3.4 * s + '"/>' +
      '<rect x="' + (z[0] - 1) + '" y="' + (z[1] - 1) + '" width="' + (z[2] + 2) + '" height="' + (z[3] + 2) + '" rx="' + 3 * s + '" fill="none" stroke="' + col + '" stroke-width="' + 1.8 * s + '"/>';
    var nota = d.texto ? U.nota(d, d.texto, {color: d.color, cerca: lente}) : null;
    if (nota) cont += nota.svg;
    // marco de la lente (va encima de la imagen aumentada, por eso es una pieza fija)
    var g = 12 * s, pw = lw + 2 * g, ph = lh + 2 * g, et = '×' + (Math.round(real * 10) / 10).toString().replace(/\.0$/, ''), px = 13 * s;
    var ew = U.medir(et, px) + 14 * s, eh = 21 * s;
    var marco = await U.pieza('<defs>' + sombra('ms', 2 * s, 3.5 * s, 0.4) + '</defs>' +
      '<g filter="url(#ms)"><rect x="' + (g + 1.5 * s) + '" y="' + (g + 1.5 * s) + '" width="' + (lw - 3 * s) + '" height="' + (lh - 3 * s) + '" rx="' + radio + '" fill="none" stroke="' + col + '" stroke-width="' + 3 * s + '"/></g>' +
      '<rect x="' + (g + 7 * s) + '" y="' + (g + 7 * s) + '" width="' + ew + '" height="' + eh + '" rx="' + eh / 2 + '" fill="' + col + '"/>' +
      '<text x="' + (g + 7 * s + ew / 2) + '" y="' + (g + 7 * s + eh / 2 + 0.5) + '" text-anchor="middle" dominant-baseline="central" font-size="' + px + '" font-weight="700" fill="#fff">' + U.esc(et) + '</text>', pw, ph);
    var caja = union([z, lente].concat(nota ? [nota.caja] : []), 16 * s);
    return U.capa(d, caja, cont, {
      lupa: {zona: z, en: lente, radio: radio, fps: 8},
      piezas: [{png: marco.png, ax: g, ay: g, ruta: [[0, lente[0], lente[1], 1, 1]]}]
    });
  });

  // =====================================================================================================
  // 5. svg: el dibujo propio del tutor, filtrado y encajado en el objetivo. Puede ir animado (SMIL: animate,
  //    animateTransform, animateMotion, set; o CSS con @keyframes): se toman fotogramas y capa.py los repite
  // =====================================================================================================
  var ELEM = {svg: 1, g: 1, path: 1, rect: 1, circle: 1, ellipse: 1, line: 1, polyline: 1, polygon: 1, text: 1, tspan: 1, defs: 1, marker: 1,
              lineargradient: 1, radialgradient: 1, stop: 1, clippath: 1, mask: 1,
              animate: 1, animatetransform: 1, animatemotion: 1, set: 1, mpath: 1, style: 1};
  var ANIMA = {animate: 1, animatetransform: 1, animatemotion: 1, set: 1};
  var ATTR = {};
  ('x y x1 y1 x2 y2 cx cy r rx ry width height d points transform viewBox preserveAspectRatio fill fill-opacity fill-rule stroke stroke-width stroke-opacity ' +
   'stroke-linecap stroke-linejoin stroke-dasharray stroke-dashoffset stroke-miterlimit opacity font-family font-size font-weight font-style text-anchor ' +
   'dominant-baseline letter-spacing dx dy rotate textLength lengthAdjust marker-start marker-mid marker-end markerWidth markerHeight refX refY orient markerUnits ' +
   'id offset stop-color stop-opacity gradientUnits gradientTransform spreadMethod fx fy clip-path clipPathUnits mask maskUnits maskContentUnits paint-order ' +
   'vector-effect style class ' +
   'attributeName attributeType from to by values dur begin end repeatCount repeatDur keyTimes keySplines keyPoints calcMode type additive accumulate path').split(' ').forEach(function(a){ ATTR[a.toLowerCase()] = a; });
  var CON_URL = {fill: 1, stroke: 1, 'clip-path': 1, mask: 1, 'marker-start': 1, 'marker-mid': 1, 'marker-end': 1};
  var NS = 'http://www.w3.org/2000/svg';

  function valorSeguro(nombre, v){
    var l = v.toLowerCase();
    if (/javascript:|expression\(|@import|<\s*script|data:text\/html/.test(l)) return false;
    if (l.indexOf('url(') >= 0){
      if (!CON_URL[nombre]) return false;
      var re = /url\(\s*(['"]?)([^)'"]*)\1\s*\)/gi, m, n = 0;
      while ((m = re.exec(v))){ n++; if (m[2].charAt(0) !== '#') return false; }
      if (!n) return false;
    }
    return true;
  }
  function estiloSeguro(v){
    var l = v.toLowerCase();
    return !/url\(|expression|@import|javascript:|behavior|binding/.test(l);
  }
  function limpiar(origen, cuenta){
    var nombre = origen.localName.toLowerCase();
    if (!ELEM[nombre]) return null;
    if (++cuenta.n > 500) throw new Error('svg: demasiados elementos (máximo 500)');
    var nuevo = document.createElementNS(NS, origen.localName);
    for (var i = 0; i < origen.attributes.length; i++){
      var a = origen.attributes[i], an = a.name.toLowerCase();
      if (an.indexOf('on') === 0 || an.indexOf('xmlns') === 0) continue;
      if (an === 'href' || an === 'xlink:href'){            // solo referencias internas (degradados que se encadenan, mpath)
        if (/^(lineargradient|radialgradient|mpath)$/.test(nombre) && /^#[\w\-.:]+$/.test(a.value.trim())) nuevo.setAttribute(an === 'href' ? 'href' : 'xlink:href', a.value.trim());
        continue;
      }
      if (an === 'attributename' && /^(on|href|xlink:href|style$)/i.test(a.value.trim())) return null;   // no se animan enlaces ni eventos
      if (!ATTR[an]) continue;
      if (an === 'style'){ if (estiloSeguro(a.value)) nuevo.setAttribute('style', a.value); continue; }
      if (an === 'class'){ if (/^[\w\- ]{1,200}$/.test(a.value)) nuevo.setAttribute('class', a.value); continue; }   // para el CSS propio
      if (!valorSeguro(an, a.value)) continue;
      nuevo.setAttribute(ATTR[an], a.value);
    }
    if (nombre === 'style'){                                   // CSS propio (animaciones con @keyframes), sin nada externo
      var css = origen.textContent || '';
      if (css.length > 8000 || !estiloSeguro(css)) return null;
      nuevo.appendChild(document.createTextNode(css));
      return nuevo;
    }
    var conTexto = nombre === 'text' || nombre === 'tspan';
    for (var n = origen.firstChild; n; n = n.nextSibling){
      if (n.nodeType === 1){ var h = limpiar(n, cuenta); if (h) nuevo.appendChild(h); }
      else if (n.nodeType === 3 && conTexto) nuevo.appendChild(document.createTextNode(n.nodeValue));
    }
    return nuevo;
  }
  function numero(v){ var m = /^\s*([0-9.]+)/.exec(v || ''); return m ? parseFloat(m[1]) : NaN; }
  var DIBUJA = {path: 1, rect: 1, circle: 1, ellipse: 1, line: 1, polyline: 1, polygon: 1, text: 1};
  function cuentaDibujo(el){ var n = DIBUJA[el.localName.toLowerCase()] ? 1 : 0; for (var c = el.firstChild; c; c = c.nextSibling) if (c.nodeType === 1 && c.localName !== 'defs') n += cuentaDibujo(c); return n; }

  // ---- animación: duración y fotogramas ----
  function segundos(v){                                      // "2s", "1500ms", "0.5" → segundos (NaN si no es un reloj simple)
    var m = /^\s*(-?[0-9.]+)\s*(ms|s|min)?\s*$/.exec(v || '');
    if (!m) return NaN;
    var n = parseFloat(m[1]); return m[2] === 'ms' ? n / 1000 : m[2] === 'min' ? n * 60 : n;
  }
  // {dur, desde, repetir} de las animaciones del SVG limpio, o null si es fijo. Lo que se repite se graba un ciclo
  // (mínimo común múltiplo de sus duraciones) a partir de que ya empezaron todas: así el bucle no salta. Tope: 6 s.
  function animacion(el){
    var anims = Array.prototype.slice.call(el.querySelectorAll('animate,animateTransform,animateMotion,set'));
    var css = Array.prototype.map.call(el.querySelectorAll('style'), function(x){ return x.textContent; }).join(' ') +
              Array.prototype.map.call(el.querySelectorAll('[style]'), function(x){ return x.getAttribute('style'); }).join(' ');
    var conCss = /animation/i.test(css) && /@keyframes/i.test(css);
    if (!anims.length && !conCss) return null;
    var fin = 0, durs = [], desde = 0;
    anims.forEach(function(a){
      var dur = segundos(a.getAttribute('dur')), b = segundos(a.getAttribute('begin') || '0s');
      var rc = a.getAttribute('repeatCount') || '';
      if (!(dur > 0)) dur = a.localName === 'set' ? 0 : 1;
      if (isNaN(b)) b = 0;
      if (rc === 'indefinite' || a.getAttribute('repeatDur') === 'indefinite'){ durs.push(dur); desde = Math.max(desde, b); }
      else fin = Math.max(fin, b + dur * Math.min(10, parseFloat(rc) || 1));
    });
    if (conCss){
      var cd = (css.match(/([0-9.]+)\s*(ms|s)\b/g) || []).map(segundos).filter(function(n){ return n > 0 && n <= 30; });
      if (/infinite/i.test(css)) durs = durs.concat(cd.length ? [Math.max.apply(null, cd)] : [2]);
      else cd.forEach(function(n){ fin = Math.max(fin, n); });
    }
    if (!durs.length) return {dur: Math.min(6, Math.max(0.3, fin || 2)), desde: 0, repetir: false};
    var dec = function(x){ return Math.max(1, Math.round(x * 10)); }, mcd = function(a, b){ return b ? mcd(b, a % b) : a; };
    var ciclo = durs.map(dec).reduce(function(a, b){ return a / mcd(a, b) * b; }) / 10;
    if (ciclo > 6) ciclo = Math.min(6, Math.max.apply(null, durs));
    return {dur: Math.max(0.3, ciclo), desde: desde, repetir: true};
  }
  // El SVG en el instante t (s). SMIL: cada animación empieza t segundos antes (el SVG pasado a imagen se pinta en su
  // instante 0). CSS: Chrome no anima el CSS de un SVG pasado a imagen, así que se mete escondido en la página, se
  // lleva cada animación a t (Web Animations) y sus valores quedan fijos en el estilo antes de pasarlo a imagen.
  function enInstante(el, t){
    var c = el.cloneNode(true);
    Array.prototype.forEach.call(c.querySelectorAll('animate,animateTransform,animateMotion,set'), function(a){
      var b = segundos(a.getAttribute('begin') || '0s');
      if (!isNaN(b)) a.setAttribute('begin', (b - t).toFixed(3) + 's');
    });
    if (!/@keyframes/i.test(Array.prototype.map.call(c.querySelectorAll('style'), function(x){ return x.textContent; }).join(' ')))
      return new XMLSerializer().serializeToString(c);
    var caja = document.createElement('div');
    caja.style.cssText = 'position:fixed;left:-20000px;top:0;width:10px;height:10px;overflow:hidden;pointer-events:none';
    document.body.appendChild(caja); caja.attachShadow({mode: 'open'}).appendChild(c);     // su CSS no toca el panel
    try {
      c.getAnimations({subtree: true}).forEach(function(an){
        an.pause(); an.currentTime = t * 1000;
        var obj = an.effect && an.effect.target, props = {};
        if (!obj) return;
        an.effect.getKeyframes().forEach(function(k){
          Object.keys(k).forEach(function(n){ if (!/^(offset|computedOffset|easing|composite)$/.test(n)) props[n] = 1; });
        });
        var cs = getComputedStyle(obj);
        Object.keys(props).forEach(function(n){
          var css = n.replace(/[A-Z]/g, function(m){ return '-' + m.toLowerCase(); });
          obj.style.setProperty(css, cs.getPropertyValue(css));
        });
      });
      c.getAnimations({subtree: true}).forEach(function(an){ var obj = an.effect && an.effect.target; if (obj) obj.style.setProperty('animation', 'none'); });
      return new XMLSerializer().serializeToString(c);
    } finally { caja.remove(); }
  }

  D.registrar('svg', async function(d, U){
    if (!d.r) throw new Error('svg necesita un objetivo donde encajarse');
    var texto = String(d.svg || '');
    if (!texto.trim()) throw new Error('svg: falta el dibujo');
    if (texto.length > 30000) throw new Error('svg: demasiado grande (' + Math.round(texto.length / 1000) + ' KB, máximo 30 KB)');
    var doc = new DOMParser().parseFromString(texto, 'image/svg+xml');
    if (doc.getElementsByTagName('parsererror').length || !doc.documentElement || doc.documentElement.localName.toLowerCase() !== 'svg') throw new Error('svg: no es un SVG válido');
    var raiz = doc.documentElement, cuenta = {n: 0};
    var limpio = limpiar(raiz, cuenta);
    if (!limpio || !cuentaDibujo(limpio)) throw new Error('svg: no queda nada que dibujar después de filtrarlo');
    var vb = (raiz.getAttribute('viewBox') || '').trim().split(/[\s,]+/).map(Number);
    if (vb.length !== 4 || vb.some(isNaN) || vb[2] <= 0 || vb[3] <= 0){
      var w0 = numero(raiz.getAttribute('width')), h0 = numero(raiz.getAttribute('height'));
      if (!(w0 > 0 && h0 > 0)) throw new Error('svg: sin viewBox ni width/height');
      vb = [0, 0, w0, h0];
    }
    var par = (raiz.getAttribute('preserveAspectRatio') || 'xMidYMid meet').trim();
    if (!/^(none|x(Min|Mid|Max)Y(Min|Mid|Max)(\s+(meet|slice))?)$/.test(par)) par = 'xMidYMid meet';
    var slice = /slice$/.test(par);
    ['width', 'height', 'x', 'y', 'viewBox', 'preserveAspectRatio'].forEach(function(a){ limpio.removeAttribute(a); });
    limpio.setAttribute('x', d.r[0]); limpio.setAttribute('y', d.r[1]); limpio.setAttribute('width', d.r[2]); limpio.setAttribute('height', d.r[3]);
    limpio.setAttribute('viewBox', vb.join(' ')); limpio.setAttribute('preserveAspectRatio', par);
    limpio.setAttribute('overflow', slice ? 'hidden' : 'visible');
    var s = d.escala || 1;
    var nota = d.texto ? U.nota(d, d.texto, {color: d.color}) : null;
    var caja = union([d.r].concat(nota ? [nota.caja] : []), (slice ? 4 : 28) * s);
    var an = animacion(limpio);
    if (!an) return U.capa(d, caja, new XMLSerializer().serializeToString(limpio) + (nota ? nota.svg : ''), {});
    // animado: la nota va fija en el fondo y el dibujo en fotogramas (≤ 60; menos si la capa es grande)
    var k = U.recorte(d, caja), area = k ? k[2] * k[3] : 1;
    var fps = Math.max(6, Math.min(15, Math.floor(14e6 / (area * an.dur)))), n = Math.max(2, Math.min(60, Math.round(an.dur * fps)));
    fps = n / an.dur;
    var fotos = await U.fotos(d, caja, n, function(i){ return enInstante(limpio, an.desde + Math.min(an.dur, i / fps)); });
    return U.capa(d, caja, nota ? nota.svg : '', {fotos: fotos, fps: fps, duracion: Math.round(an.dur * 1000), repetir: an.repetir, pausa: 0});
  });
})();
