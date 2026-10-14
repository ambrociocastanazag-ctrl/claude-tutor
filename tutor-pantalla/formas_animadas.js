/* Formas animadas del dibujante: fantasma (cursor que hace los pasos), guia («hazlo aquí») y secuencia (1 → 2 → 3).
   Se animan con piezas que siguen una ruta (cursor, ondas, notas, letras) y con pocos fotogramas (solo el trazo de
   la guía). Contrato en DIBUJOS.md; aquí solo se registran las formas.  Depende de dibujante.js. */
(function(){
  if (!window.Dibujante) return;

  // ---- utilidades comunes ----
  function suave(t){ t = Math.max(0, Math.min(1, t)); return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }
  function centro(r){ return [r[0] + r[2] / 2, r[1] + r[3] / 2]; }
  function limitar(v, a, b){ return Math.max(a, Math.min(b, v)); }

  // Cajas que ocupa lo dibujado (para que la capa sea lo más pequeña posible).
  function Caja(){ this.x0 = 1e9; this.y0 = 1e9; this.x1 = -1e9; this.y1 = -1e9; }
  Caja.prototype.mas = function(x, y, w, h){ this.x0 = Math.min(this.x0, x); this.y0 = Math.min(this.y0, y); this.x1 = Math.max(this.x1, x + (w || 0)); this.y1 = Math.max(this.y1, y + (h || 0)); };
  Caja.prototype.rect = function(m){ return [this.x0 - m, this.y0 - m, this.x1 - this.x0 + 2 * m, this.y1 - this.y0 + 2 * m]; };

  // Ruta de una pieza que aparece: antes de su primera clave no se ve (alfa 0).
  function aparece(claves){
    var k = claves[0], r = claves.slice();
    if (k[0] > 1) r.unshift([k[0] - 1, k[1], k[2], 0, k[4]]);
    if (r[0][0] > 0) r.unshift([0, r[0][1], r[0][2], 0, r[0][4]]);
    return r;
  }
  // Pieza con ruta ya normalizada: {png, ax, ay, ruta}.
  function poner(im, ax, ay, claves){ return {png: im.png, ax: ax, ay: ay, ruta: aparece(claves)}; }

  // Una nota (U.nota) como pieza que se ve entre t0 y t1 (fundido de entrada y salida).
  function notaPieza(d, U, texto, cerca, color, t0, t1, caja, final){
    var n = U.nota(d, texto, {cerca: cerca, color: color}), s = d.escala || 1, c = n.caja, m = 12 * s;
    var x0 = Math.min(c[0], cerca[0]) - m, y0 = Math.min(c[1], cerca[1]) - m;
    var x1 = Math.max(c[0] + c[2], cerca[0] + cerca[2]) + m, y1 = Math.max(c[1] + c[3], cerca[1] + cerca[3]) + m;
    caja.mas(x0, y0, x1 - x0, y1 - y0);
    return U.pieza('<g transform="translate(' + (-x0) + ' ' + (-y0) + ')">' + n.svg + '</g>', x1 - x0, y1 - y0).then(function(im){
      var k = [[t0, x0, y0, 0, 1], [t0 + 200, x0, y0, 1, 1]];
      if (!final){ k.push([t1, x0, y0, 1, 1]); k.push([t1 + 250, x0, y0, 0, 1]); }
      return poner(im, 0, 0, k);
    });
  }

  // ======================= FANTASMA =======================
  function cursorSvg(s){
    var k = 1.1 * s, pad = 7 * s, w = Math.ceil(14 * k + 2 * pad), h = Math.ceil(21 * k + 2 * pad);
    var f = 'M0 0 L0 17 L4.2 13.2 L7 19.6 L9.6 18.5 L6.8 12.2 L12.2 12.2 Z';
    return {w: w, h: h, ax: pad, ay: pad, svg:
      '<defs><filter id="sh" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="' + 1.7 * s + '"/></filter></defs>' +
      '<g transform="translate(' + (pad + 1.6 * s) + ' ' + (pad + 2.4 * s) + ') scale(' + k + ')"><path d="' + f + '" fill="#000" fill-opacity=".38" filter="url(#sh)"/></g>' +
      '<g transform="translate(' + pad + ' ' + pad + ') scale(' + k + ')"><path d="' + f + '" fill="#fff" stroke="#111" stroke-width="1.25" stroke-linejoin="round"/></g>'};
  }
  // Camino de a a b con curva suave y aceleración: claves [t, x, y] cada ~35 ms (sin repetir la de salida).
  function viaje(a, b, t0, dur, sesgo){
    var dx = b[0] - a[0], dy = b[1] - a[1], L = Math.max(1, Math.hypot(dx, dy));
    var qx = (a[0] + b[0]) / 2 - dy / L * L * sesgo, qy = (a[1] + b[1]) / 2 + dx / L * L * sesgo;
    var n = Math.max(2, Math.round(dur / 35)), out = [];
    for (var i = 1; i <= n; i++){
      var u = i / n, e = suave(u), v = 1 - e;
      out.push([t0 + dur * u, v * v * a[0] + 2 * v * e * qx + e * e * b[0], v * v * a[1] + 2 * v * e * qy + e * e * b[1]]);
    }
    return out;
  }

  Dibujante.registrar('fantasma', async function(d, U){
    var s = d.escala || 1, col = U.color(d.color), pasos = d.pasos || [];
    var cw = (d.cliente || [1600, 900])[0], ch = (d.cliente || [1600, 900])[1];
    var caja = new Caja(), piezas = [], tramos = [], cache = {};
    var primero = pasos.filter(function(p){ return p.r; })[0];
    if (!primero) return null;
    var c0 = centro(primero.r);
    var pos = [limitar(c0[0] + 150 * s, 20, cw - 20), limitar(c0[1] + 120 * s, 20, ch - 20)];
    var cur = cursorSvg(s), imCur = await U.pieza(cur.svg, cur.w, cur.h);
    var R = 28 * s;
    async function anillo(c){                     // el anillo de las ondas, uno por color
      if (!cache[c]) cache[c] = await U.pieza('<circle cx="' + (R + 3 * s) + '" cy="' + (R + 3 * s) + '" r="' + R + '" fill="' + c + '" fill-opacity=".16" stroke="' + c + '" stroke-width="' + 3 * s + '"/>', 2 * R + 6 * s, 2 * R + 6 * s);
      return cache[c];
    }
    var imPunto = await U.pieza('<circle cx="' + 4 * s + '" cy="' + 4 * s + '" r="' + 3.2 * s + '" fill="' + col + '"/>', 8 * s, 8 * s);
    var ck = [[0, pos[0], pos[1], 0, 1], [300, pos[0], pos[1], 1, 1]], T = 650;
    caja.mas(pos[0] - 30 * s, pos[1] - 30 * s, 60 * s, 60 * s);

    function claveCur(t, x, y, esc){ ck.push([t, x, y, 1, esc == null ? 1 : esc]); }
    function pulsar(t, p){                        // el cursor se «hunde» un instante al hacer clic
      claveCur(t, p[0], p[1], 1); claveCur(t + 70, p[0], p[1], 0.84); claveCur(t + 170, p[0], p[1], 1);
    }
    async function onda(t, p, c){
      var im = await anillo(c || col);
      piezas.push(poner(im, R + 3 * s, R + 3 * s, [[t, p[0], p[1], 0.95, 0.22], [t + 520, p[0], p[1], 0, 1.15]]));
      caja.mas(p[0] - R * 1.2, p[1] - R * 1.2, R * 2.4, R * 2.4);
    }
    function mover(a, b, dur, sesgo, esc){
      var seg = viaje(a, b, T, dur, sesgo);
      seg.forEach(function(k){ claveCur(k[0], k[1], k[2], esc); caja.mas(k[1] - 20 * s, k[2] - 20 * s, 40 * s, 40 * s); });
      T += dur;
    }

    for (var i = 0; i < pasos.length; i++){
      var p = pasos[i], t0 = T, sesgo = (i % 2 ? -1 : 1) * 0.11, acc = p.accion || 'mover';
      if (!p.r){ tramos.push([T, T]); continue; }
      var obj = centro(p.r), dist = Math.hypot(obj[0] - pos[0], obj[1] - pos[1]);
      mover(pos, obj, Math.round(450 + Math.min(900, dist * 0.7)), sesgo);
      pos = obj;
      var llegada = T;
      if (acc === 'clic'){
        pulsar(T, pos); await onda(T + 60, pos); T += 560;
      } else if (acc === 'doble'){
        pulsar(T, pos); await onda(T + 60, pos); pulsar(T + 260, pos); await onda(T + 320, pos); T += 820;
      } else if (acc === 'derecho'){
        var c2 = col === U.color('naranja') ? U.color('morado') : U.color('naranja');
        pulsar(T, pos); await onda(T + 60, pos, c2);
        var etq = 'clic derecho', pxe = Math.round(13 * s), we = U.medir(etq, pxe) + 14 * s, he = pxe * 1.5 + 4 * s;
        var ex = limitar(pos[0] + 16 * s, 2, cw - we - 2), ey = limitar(pos[1] + 30 * s, 2, ch - he - 2);
        var ime = await U.pieza('<rect x="1" y="1" width="' + (we - 2) + '" height="' + (he - 2) + '" rx="' + 6 * s + '" fill="' + c2 + '"/><text x="' + we / 2 + '" y="' + he / 2 +
                                '" text-anchor="middle" dominant-baseline="central" font-size="' + pxe + '" font-weight="600" fill="#fff">' + etq + '</text>', we, he);
        piezas.push(poner(ime, 0, 0, [[T + 90, ex, ey, 0, 1], [T + 260, ex, ey, 1, 1], [T + 950, ex, ey, 1, 1], [T + 1200, ex, ey, 0, 1]]));
        caja.mas(ex, ey, we, he); T += 950;
      } else if (acc === 'arrastrar' && p.hasta_r){
        var fin = centro(p.hasta_r);
        pulsar(T, pos); await onda(T + 60, pos); T += 200;
        claveCur(T, pos[0], pos[1], 0.88);
        var dd = Math.hypot(fin[0] - pos[0], fin[1] - pos[1]), dur = Math.round(650 + Math.min(1000, dd * 0.9));
        var seg = viaje(pos, fin, T, dur, -sesgo * 0.8);
        // estela punteada: un punto cada tanto, que aparece cuando el cursor pasa por él
        var paso = Math.max(14 * s, dd / 46), acum = 0, prev = pos, dots = 0;
        seg.forEach(function(k){
          claveCur(k[0], k[1], k[2], 0.88); caja.mas(k[1] - 20 * s, k[2] - 20 * s, 40 * s, 40 * s);
          acum += Math.hypot(k[1] - prev[0], k[2] - prev[1]); prev = [k[1], k[2]];
          if (acum >= paso){
            acum = 0; dots++;
            piezas.push(poner(imPunto, 4 * s, 4 * s, [[k[0], k[1], k[2], 0, 0.4], [k[0] + 110, k[1], k[2], 0.95, 1], [T + dur + 520, k[1], k[2], 0.95, 1], [T + dur + 900, k[1], k[2], 0, 1]]));
          }
        });
        T += dur; pos = fin;
        claveCur(T + 40, pos[0], pos[1], 0.88); claveCur(T + 140, pos[0], pos[1], 1);
        await onda(T + 30, pos, col); T += 520;
      } else if (acc === 'escribir' && p.texto){
        pulsar(T, pos); await onda(T + 60, pos); T += 420;
        var txt = String(p.texto), px = Math.round(15 * s), pad = 10 * s, bh = px * 1.4 + 1.2 * pad;
        var bw = U.medir(txt, px, false) + 2 * pad + 8 * s, bx = limitar(p.r[0], 2, cw - bw - 2), by, abajo, hallado = false;
        // hueco libre cerca del objetivo: debajo o encima, probando alineaciones y distancias, sin tapar controles ni otros objetivos
        var evi = (d.evitar || []).concat(pasos.map(function(q){ return q.r; }), pasos.map(function(q){ return q.hasta_r; })).filter(function(e){ return e && !U.choca(e, p.r); });
        [14, 30, 60].forEach(function(g){
          if (hallado) return;
          [true, false].forEach(function(dir){
            [p.r[0], p.r[0] + p.r[2] - bw, p.r[0] + p.r[2] / 2 - bw / 2].forEach(function(xc){
              if (hallado) return;
              var xx = xc, yy = dir ? p.r[1] + p.r[3] + g * s + 10 * s : p.r[1] - g * s - bh - 10 * s;
              var rc = [xx, dir ? yy - 10 * s : yy, bw, bh + 10 * s];
              if (rc[0] < 2 || rc[1] < 2 || rc[0] + bw > cw - 2 || rc[1] + rc[3] > ch - 2) return;
              if (evi.some(function(e){ return U.choca(rc, e, 4 * s); })) return;
              hallado = true; bx = xx; by = yy; abajo = dir;
            });
          });
        });
        if (!hallado){
          abajo = p.r[1] + p.r[3] + 14 * s + bh + 10 * s <= ch - 2;
          by = limitar(abajo ? p.r[1] + p.r[3] + 14 * s + 10 * s : p.r[1] - 14 * s - bh - 10 * s, 2, ch - bh - 2);
        }
        var tipx = limitar(p.r[0] + Math.min(p.r[2] / 2, 30 * s), bx + 14 * s, bx + bw - 14 * s);
        var oy = abajo ? 10 * s : 0, hg = bh + 10 * s, tipy = abajo ? 0 : hg;
        var cuerpo = '<rect x="1" y="' + (oy + 1) + '" width="' + (bw - 2) + '" height="' + (bh - 2) + '" rx="' + 8 * s + '" fill="#fff" stroke="' + col + '" stroke-width="' + 2.4 * s + '"/>';
        var cola = abajo ? [[tipx - bx - 7 * s, oy + 1], [tipx - bx, 0], [tipx - bx + 7 * s, oy + 1]] : [[tipx - bx - 7 * s, bh - 1], [tipx - bx, hg], [tipx - bx + 7 * s, bh - 1]];
        cuerpo += '<polygon points="' + cola.map(function(q){ return q.join(','); }).join(' ') + '" fill="#fff" stroke="' + col + '" stroke-width="' + 2.4 * s + '" stroke-linejoin="round"/>' +
                  '<rect x="' + (tipx - bx - 5 * s) + '" y="' + (abajo ? oy - 1 : bh - 4 * s) + '" width="' + 10 * s + '" height="' + 5 * s + '" fill="#fff"/>';
        var imB = await U.pieza(cuerpo, bw, hg);
        var tx = tipx, ty = abajo ? by - 10 * s : by + bh + 10 * s, tb = T;
        var pB = poner(imB, tipx - bx, tipy, [[tb, tx, ty, 0, 0.8], [tb + 180, tx, ty, 1, 1]]), letras = [pB];
        piezas.push(pB);
        caja.mas(bx, abajo ? by - 10 * s : by, bw, hg);
        // letras: una pieza por trozo (máx. 40), cada una aparece a su hora; la barra de texto las sigue
        var g = Math.ceil(txt.length / 40), dt = Math.min(75, 3600 / Math.ceil(txt.length / g)), ts = tb + 300;
        var yc = by + bh / 2, x0 = bx + pad, hl = Math.ceil(px * 1.5), ant = 0;
        var barra = await U.pieza('<rect x="0" y="0" width="' + 2.2 * s + '" height="' + px * 1.2 + '" rx="1" fill="' + col + '"/>', Math.ceil(2.2 * s) + 1, Math.ceil(px * 1.2));
        var bk = [[ts - 1, x0, yc, 0, 1], [ts, x0, yc, 1, 1]], fin_t = ts, trozosN = Math.ceil(txt.length / g);
        for (var j = 1; j <= trozosN; j++){
          var pre = txt.slice(0, Math.min(txt.length, j * g)), ini = txt.slice(0, (j - 1) * g), parte = txt.slice((j - 1) * g, j * g);
          var tj = ts + (j - 1) * dt + 40, xj = x0 + U.medir(ini, px, false), wj = Math.ceil(U.medir(parte, px, false)) + 4;
          if (parte.trim()){
            var iml = await U.pieza('<text x="2" y="' + hl / 2 + '" dominant-baseline="central" font-size="' + px + '" font-weight="400" fill="#1f2430" xml:space="preserve">' + U.esc(parte) + '</text>', wj, hl);
            var pl = poner(iml, 2, hl / 2, [[tj, xj, yc, 0, 1], [tj + 50, xj, yc, 1, 1]]);
            letras.push(pl); piezas.push(pl);
          }
          bk.push([tj - 1, x0 + U.medir(ini, px, false), yc, 1, 1]); bk.push([tj, x0 + U.medir(pre, px, false), yc, 1, 1]);
          fin_t = tj;
        }
        bk.push([fin_t + 250, bk[bk.length - 1][1], yc, 1, 1], [fin_t + 251, bk[bk.length - 1][1], yc, 0, 1], [fin_t + 520, bk[bk.length - 1][1], yc, 0, 1], [fin_t + 521, bk[bk.length - 1][1], yc, 1, 1]);
        T = fin_t + 900;
        bk.push([T, bk[bk.length - 1][1], yc, 1, 1], [T + 250, bk[bk.length - 1][1], yc, 0, 1]);
        piezas.push(poner(barra, Math.ceil(1.1 * s), Math.ceil(px * 0.6), bk));
        // el globo y las letras se van con un fundido al acabar el paso
        letras.forEach(function(q){ var u = q.ruta[q.ruta.length - 1]; q.ruta.push([T, u[1], u[2], 1, 1], [T + 250, u[1], u[2], 0, 1]); });
        caja.mas(bx, by, bw, bh);
      } else {
        T += 300;                                // mover (o pasos sin datos suficientes)
      }
      if (p.texto && acc !== 'escribir'){         // nota del paso mientras dura su tramo
        piezas.push(await notaPieza(d, U, p.texto, p.r, d.color, llegada, T, caja));
      }
      tramos.push([t0, T]);
    }
    var D = T + 700;
    ck.push([T + 300, pos[0], pos[1], 1, 1], [D, pos[0], pos[1], 0, 1]);
    piezas.push(poner(imCur, cur.ax, cur.ay, ck));   // el cursor va encima de todo
    var m = 18 * s;
    return U.capa(d, caja.rect(m), '', {piezas: piezas, duracion: D, repetir: true, pausa: 1500, tramos: tramos});
  });

  // Nota sin flecha pegada a la figura de la guía: debajo, encima, a la derecha o a la izquierda, en un hueco libre.
  function notaLibre(d, U, texto, fig, color, t0, caja){
    var s = d.escala || 1, col = U.color(color || d.color), px = Math.round(15 * s), pad = 9 * s;
    var cw = (d.cliente || [1600, 900])[0], ch = (d.cliente || [1600, 900])[1];
    var w = U.medir(texto, px) + 2 * pad, h = px * 1.3 + 1.3 * pad, g = 9 * s;
    var evi = (d.evitar || []).filter(function(e){ return !U.choca(e, fig); });
    var cands = [[fig[0], fig[1] + fig[3] + g], [fig[0] + fig[2] - w, fig[1] + fig[3] + g], [fig[0], fig[1] - g - h], [fig[0] + fig[2] + g, fig[1]],
                 [fig[0] - g - w, fig[1]], [fig[0] + fig[2] / 2 - w / 2, fig[1] + fig[3] + g * 3], [fig[0] + fig[2] / 2 - w / 2, fig[1] - g * 3 - h]];
    var c = null;
    for (var i = 0; i < cands.length && !c; i++){
      var q = [cands[i][0], cands[i][1], w, h];
      if (q[0] >= 2 && q[1] >= 2 && q[0] + w <= cw - 2 && q[1] + h <= ch - 2 && !U.choca(q, fig, 2 * s) && !evi.some(function(e){ return U.choca(q, e, 4 * s); })) c = q;
    }
    if (!c) c = [limitar(cands[0][0], 2, cw - w - 2), limitar(cands[0][1], 2, ch - h - 2), w, h];
    caja.mas(c[0] - 4 * s, c[1] - 4 * s, w + 8 * s, h + 8 * s);
    var svg = '<rect x="' + (4 * s) + '" y="' + (4 * s) + '" width="' + w + '" height="' + h + '" rx="' + 7 * s + '" fill="' + U.mezclar(col, 0.10) + '" fill-opacity="0.965" stroke="' + col + '" stroke-width="' + 2.4 * s + '"/>' +
      '<text x="' + (4 * s + pad) + '" y="' + (4 * s + h / 2) + '" dominant-baseline="central" font-size="' + px + '" font-weight="600" fill="' + col + '">' + U.esc(texto) + '</text>';
    return U.pieza(svg, w + 8 * s, h + 8 * s).then(function(im){
      var x = c[0] - 4 * s, y = c[1] - 4 * s;
      return poner(im, 0, 0, [[t0, x, y, 0, 1], [t0 + 250, x, y, 1, 1]]);
    });
  }

  // ======================= GUIA =======================
  function trazoGuia(figura, r, s){
    var p = 6 * s, x = r[0] - p, y = r[1] - p, w = r[2] + 2 * p, h = r[3] + 2 * p, cx = x + w / 2, cy = y + h / 2, a = 8 * s;
    if (figura === 'elipse'){
      var rx = w / 2 * 1.06, ry = h / 2 * 1.06;
      return {d: 'M' + (cx - rx) + ' ' + cy + ' A' + rx + ' ' + ry + ' 0 1 1 ' + (cx + rx) + ' ' + cy + ' A' + rx + ' ' + ry + ' 0 1 1 ' + (cx - rx) + ' ' + cy, relleno: true, caja: [cx - rx, cy - ry, 2 * rx, 2 * ry]};
    }
    if (figura === 'linea'){            // subrayado bajo el objetivo; si es muy alto y estrecho, una raya vertical
      if (r[2] >= r[3]) return {d: 'M' + r[0] + ' ' + (r[1] + r[3] + 4 * s) + ' L' + (r[0] + r[2]) + ' ' + (r[1] + r[3] + 4 * s), relleno: false, caja: [r[0], r[1] + r[3], r[2], 8 * s]};
      return {d: 'M' + cx + ' ' + r[1] + ' L' + cx + ' ' + (r[1] + r[3]), relleno: false, caja: [cx - 4 * s, r[1], 8 * s, r[3]]};
    }
    if (figura === 'flecha'){           // a lo largo del lado más largo, con la punta al final
      var hor = r[2] >= r[3], x1 = hor ? r[0] : cx, y1 = hor ? cy : r[1], x2 = hor ? r[0] + r[2] : cx, y2 = hor ? cy : r[1] + r[3];
      return {d: 'M' + x1 + ' ' + y1 + ' L' + x2 + ' ' + y2, relleno: false, flecha: [x1, y1, x2, y2], caja: [r[0] - 10 * s, r[1] - 10 * s, r[2] + 20 * s, r[3] + 20 * s]};
    }
    return {d: 'M' + (x + a) + ' ' + y + ' H' + (x + w - a) + ' A' + a + ' ' + a + ' 0 0 1 ' + (x + w) + ' ' + (y + a) + ' V' + (y + h - a) + ' A' + a + ' ' + a + ' 0 0 1 ' + (x + w - a) + ' ' + (y + h) +
            ' H' + (x + a) + ' A' + a + ' ' + a + ' 0 0 1 ' + x + ' ' + (y + h - a) + ' V' + (y + a) + ' A' + a + ' ' + a + ' 0 0 1 ' + (x + a) + ' ' + y, relleno: true, caja: [x, y, w, h]};
  }
  function cabeza(x1, y1, x2, y2, col, s){      // punta de flecha al final del segmento
    var L = Math.max(1e-6, Math.hypot(x2 - x1, y2 - y1)), ux = (x2 - x1) / L, uy = (y2 - y1) / L, q = 13 * s;
    return '<polygon points="' + x2 + ',' + y2 + ' ' + [x2 - ux * q - uy * q * 0.55, y2 - uy * q + ux * q * 0.55].join(',') + ' ' + [x2 - ux * q + uy * q * 0.55, y2 - uy * q - ux * q * 0.55].join(',') + '" fill="' + col + '"/>';
  }

  Dibujante.registrar('guia', async function(d, U){
    var s = d.escala || 1, col = U.color(d.color), r = d.r;
    if (!r) return null;
    var f = trazoGuia(d.figura || 'rect', r, s), gr = 3 * s, N = 14, FPS = 20, REV = N * 1000 / FPS;
    var caja = new Caja(); caja.mas(f.caja[0], f.caja[1], f.caja[2], f.caja[3]);
    var dash = 'stroke-dasharray="' + 7 * s + ' ' + 6 * s + '" stroke-linecap="round"';
    // El punteado se va revelando con una máscara: el mismo trazo, continuo y ancho, que crece con pathLength=1.
    function cuadro(k, n){
      var u = suave((k + 1) / n), id = 'm' + k;
      var s1 = '<defs><mask id="' + id + '" maskUnits="userSpaceOnUse" x="-2000" y="-2000" width="9000" height="9000">' +
               '<path d="' + f.d + '" pathLength="1" fill="none" stroke="#fff" stroke-width="' + gr * 4 + '" stroke-dasharray="1 2" stroke-dashoffset="' + (1 - u) + '"/></mask></defs>';
      if (f.relleno) s1 += '<path d="' + f.d + '" fill="' + col + '" fill-opacity="' + 0.09 * u + '" stroke="none"/>';
      s1 += '<g mask="url(#' + id + ')"><path d="' + f.d + '" fill="none" stroke="' + col + '" stroke-width="' + gr + '" ' + dash + '/></g>';
      if (f.flecha && u > 0.88) s1 += cabeza(f.flecha[0], f.flecha[1], f.flecha[2], f.flecha[3], col, s);
      return s1;
    }
    var fotos = await U.fotos(d, caja.rect(14 * s), N, cuadro);
    // El latido: un halo suave del mismo contorno que sube y baja (una sola pieza con la alfa en ruta).
    var m = 14 * s, bx = f.caja[0] - m, by = f.caja[1] - m, bw = f.caja[2] + 2 * m, bh = f.caja[3] + 2 * m;
    var halo = await U.pieza('<defs><filter id="b" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="' + 3.2 * s + '"/></filter></defs><g transform="translate(' + (-bx) + ' ' + (-by) + ')">' +
                             '<path d="' + f.d + '" fill="none" stroke="' + col + '" stroke-width="' + gr * 2.4 + '" filter="url(#b)"/></g>', bw, bh);
    var L = 1200, vueltas = 6, claves = [[REV - 1, bx, by, 0, 1]];
    for (var t = REV; t <= REV + L * vueltas; t += 100) claves.push([t, bx, by, 0.12 + 0.5 * (0.5 - 0.5 * Math.cos((t - REV) / L * 2 * Math.PI)), 1]);
    var piezas = [poner(halo, 0, 0, claves)], D = REV + L * vueltas;
    if (d.texto) piezas.push(await notaLibre(d, U, d.texto, f.caja, d.color, REV - 100, caja));
    var extra = {fotos: fotos, fps: FPS, piezas: piezas, duracion: D, repetir: true, pausa: 700};
    var cap = await U.capa(d, caja.rect(14 * s), '', extra);
    return cap;
  });

  // ======================= SECUENCIA =======================
  Dibujante.registrar('secuencia', async function(d, U){
    var s = d.escala || 1, pasos = (d.pasos || []).filter(function(p){ return p.r; });
    if (!pasos.length) return null;
    var cw = (d.cliente || [1600, 900])[0], ch = (d.cliente || [1600, 900])[1];
    var caja = new Caja(), piezas = [], tramos = [], TP = 1500, Rc = 13 * s, SEG = 7;
    for (var i = 0; i < pasos.length; i++){
      var p = pasos[i], t0 = i * TP, col = U.color(p.color || d.color), r = p.r, ultimo = i === pasos.length - 1;
      // contorno suave del objetivo
      var pe = 3 * s, ow = r[2] + 2 * pe, oh = r[3] + 2 * pe, ox = r[0] - pe, oy = r[1] - pe;
      var imo = await U.pieza('<rect x="' + 2 * s + '" y="' + 2 * s + '" width="' + (ow - 4 * s) + '" height="' + (oh - 4 * s) + '" rx="' + 6 * s + '" fill="' + col + '" fill-opacity=".08" stroke="' + col + '" stroke-width="' + 2.4 * s + '"/>', ow, oh);
      piezas.push(poner(imo, 0, 0, [[t0, ox, oy, 0, 0.96], [t0 + 250, ox, oy, 1, 1]]));
      caja.mas(ox, oy, ow, oh);
      // el número: pop 0.6 → 1.1 → 1, en la esquina de arriba a la izquierda (no tapa el objetivo)
      var cx = limitar(r[0] - 4 * s, Rc + 3 * s, cw - Rc - 3 * s), cy = limitar(r[1] - 4 * s, Rc + 3 * s, ch - Rc - 3 * s), W = Math.ceil(2 * Rc + 8 * s);
      var imn = await U.pieza('<defs><filter id="sh" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="' + 1.5 * s + '"/></filter></defs>' +
        '<circle cx="' + (W / 2 + 0.8 * s) + '" cy="' + (W / 2 + 1.8 * s) + '" r="' + Rc + '" fill="#000" fill-opacity=".3" filter="url(#sh)"/>' +
        '<circle cx="' + W / 2 + '" cy="' + W / 2 + '" r="' + Rc + '" fill="' + col + '" stroke="#fff" stroke-width="' + 2 * s + '"/>' +
        '<text x="' + W / 2 + '" y="' + W / 2 + '" text-anchor="middle" dominant-baseline="central" font-size="' + Math.round(15 * s) + '" font-weight="700" fill="#fff">' + U.esc(p.n != null ? p.n : i + 1) + '</text>', W, W);
      piezas.push({png: imn.png, ax: W / 2, ay: W / 2, ruta: aparece([[t0, cx, cy, 0, 0.6], [t0 + 150, cx, cy, 1, 1.1], [t0 + 280, cx, cy, 1, 1]])});
      caja.mas(cx - W / 2, cy - W / 2, W, W);
      // nota con el texto del paso
      if (p.texto) piezas.push(await notaPieza(d, U, p.texto, r, p.color || d.color, t0 + 200, t0 + TP, caja, true));
      // flecha curva hacia el siguiente: el trazo sale en trocitos que aparecen uno tras otro, y al final la punta
      if (!ultimo){
        var r2 = pasos[i + 1].r, a = centro(r);
        var b = [limitar(r2[0] - 4 * s, Rc + 3 * s, cw - Rc - 3 * s), limitar(r2[1] - 4 * s, Rc + 3 * s, ch - Rc - 3 * s)];   // centro del círculo del siguiente
        function borde(r2, c1, c2){            // donde la recta de centro a centro sale del rectángulo ensanchado
          var dx = c2[0] - c1[0], dy = c2[1] - c1[1], hw = r2[2] / 2 + 9 * s, hh = r2[3] / 2 + 9 * s;
          var k = Math.min(dx ? hw / Math.abs(dx) : 1e9, dy ? hh / Math.abs(dy) : 1e9, 0.45);
          return [c1[0] + dx * k, c1[1] + dy * k];
        }
        var p1 = borde(r, a, b), cu = 0.2, gr = 3.2 * s;
        var dl = Math.max(1e-6, Math.hypot(a[0] - b[0], a[1] - b[1])), p2 = [b[0] + (a[0] - b[0]) / dl * (Rc + 5 * s), b[1] + (a[1] - b[1]) / dl * (Rc + 5 * s)];   // hasta el borde del círculo
        var dxx = p2[0] - p1[0], dyy = p2[1] - p1[1], q = [(p1[0] + p2[0]) / 2 - dyy * cu, (p1[1] + p2[1]) / 2 + dxx * cu];
        var punta = 12 * s, tl = Math.max(1e-6, Math.hypot(p2[0] - q[0], p2[1] - q[1])), uxx = (p2[0] - q[0]) / tl, uyy = (p2[1] - q[1]) / tl;
        var fin = [p2[0] - uxx * punta * 0.8, p2[1] - uyy * punta * 0.8];     // el trazo acaba donde empieza la punta
        function B(u){ var v = 1 - u; return [v * v * p1[0] + 2 * v * u * q[0] + u * u * fin[0], v * v * p1[1] + 2 * v * u * q[1] + u * u * fin[1]]; }
        var ta = t0 + 650, dur = 560;
        for (var j = 0; j < SEG; j++){
          var pts = [], mm = 3 * s;
          for (var k = 0; k <= 4; k++) pts.push(B((j + k / 4) / SEG));
          var x0 = Math.min.apply(null, pts.map(function(z){ return z[0]; })) - gr - mm, y0 = Math.min.apply(null, pts.map(function(z){ return z[1]; })) - gr - mm;
          var x1 = Math.max.apply(null, pts.map(function(z){ return z[0]; })) + gr + mm, y1 = Math.max.apply(null, pts.map(function(z){ return z[1]; })) + gr + mm;
          var dd = 'M' + pts.map(function(z){ return (z[0] - x0) + ' ' + (z[1] - y0); }).join(' L');
          var ims = await U.pieza('<path d="' + dd + '" fill="none" stroke="' + col + '" stroke-width="' + gr + '" stroke-linecap="round" stroke-linejoin="round"/>', x1 - x0, y1 - y0);
          var tj = ta + dur * j / SEG;
          piezas.push(poner(ims, 0, 0, [[tj, x0, y0, 0, 1], [tj + 70, x0, y0, 1, 1]]));
          caja.mas(x0, y0, x1 - x0, y1 - y0);
        }
        var hx0 = Math.min(p2[0], fin[0]) - punta, hy0 = Math.min(p2[1], fin[1]) - punta, hw = 2 * punta;
        var imh;
        // la punta se dibuja con su propia dirección (de q hacia p2) dentro de su pieza
        var punt = cabeza(p2[0] - uxx * 20 - hx0, p2[1] - uyy * 20 - hy0, p2[0] - hx0, p2[1] - hy0, col, s);
        imh = await U.pieza(punt, hw, hw);
        var th = ta + dur;
        piezas.push(poner(imh, 0, 0, [[th, hx0, hy0, 0, 1], [th + 90, hx0, hy0, 1, 1]]));
        caja.mas(hx0, hy0, hw, hw);
      }
      tramos.push([t0, ultimo ? t0 + 1000 : t0 + TP]);
    }
    var D = (pasos.length - 1) * TP + 1000;
    return U.capa(d, caja.rect(16 * s), '', {piezas: piezas, duracion: D, repetir: false, tramos: tramos});
  });
})();
