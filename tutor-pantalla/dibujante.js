/* El dibujante: convierte los dibujos del tutor (el «lote» que manda Python) en capas PNG para capa.py, que las
   pega encima de la app. Todo se dibuja en SVG (bordes suaves, texto con las fuentes de Windows) y se pasa a PNG
   aquí mismo, en la página del panel: no hace falta otra ventana. Contrato completo en DIBUJOS.md.

   Dibujante.registrar(forma, fn)   fn(d, U) → capa | [capas] | Promise (lo usan formas_*.js)
   Dibujante.renderizar(lote)       → Promise<{capas, narracion, errores}> (sin tocar nada: banco de pruebas)
   Dibujante.mostrar(lote, texto)   renderiza, pone las capas encima de la app y, con la voz encendida, narra
   Dibujante.borrar()               quita las capas */
(function(){
  if (window.Dibujante) return;
  var FORMAS = {};
  var COLORES = {azul: '#1e5ac8', verde: '#1e8c46', rojo: '#c02828', naranja: '#e66e00', amarillo: '#d79100', morado: '#783cbe'};
  var FUENTE = "'Segoe UI', 'Segoe UI Variable Text', system-ui, sans-serif";
  var lienzo = document.createElement('canvas').getContext('2d');
  var ocupado = {};                       // hwnd → cajas que las notas no deben tapar (en el lote que se está dibujando)

  function api(){ return window.pywebview && window.pywebview.api; }
  function color(n){ return COLORES[n] || (/^#[0-9a-f]{6}$/i.test(n || '') ? n : COLORES.azul); }
  function esc(s){ return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){ return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]; }); }
  function medir(t, px, negrita){ lienzo.font = (negrita === false ? '400 ' : '600 ') + px + 'px ' + FUENTE; return lienzo.measureText(String(t)).width; }
  function svg(w, h, contenido){
    return '<svg xmlns="http://www.w3.org/2000/svg" width="' + w + '" height="' + h + '" viewBox="0 0 ' + w + ' ' + h +
      '" font-family="' + FUENTE.replace(/"/g, "'") + '">' + contenido + '</svg>';
  }
  function png(s, w, h){
    return new Promise(function(ok, mal){
      var img = new Image();
      img.onload = function(){
        var c = document.createElement('canvas'); c.width = Math.max(1, w); c.height = Math.max(1, h);
        c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
        try { ok(c.toDataURL('image/png')); } catch (e){ mal(e); }
      };
      img.onerror = function(){ mal(new Error('El SVG no se pudo dibujar')); };
      img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(s);
    });
  }

  // La caja [x, y, w, h] de cliente, en enteros y recortada al área de cliente (null si queda fuera).
  function recorte(d, caja){
    var cw = (d.cliente || [99999, 99999])[0], ch = (d.cliente || [99999, 99999])[1];
    var x0 = Math.max(0, Math.floor(caja[0])), y0 = Math.max(0, Math.floor(caja[1]));
    var x1 = Math.min(cw, Math.ceil(caja[0] + caja[2])), y1 = Math.min(ch, Math.ceil(caja[1] + caja[3]));
    return x1 - x0 >= 1 && y1 - y0 >= 1 ? [x0, y0, x1 - x0, y1 - y0] : null;
  }
  function enCaja(k, contenido){ return svg(k[2], k[3], '<g transform="translate(' + (-k[0]) + ' ' + (-k[1]) + ')">' + contenido + '</g>'); }

  // Rasteriza `contenido` (SVG en coordenadas de cliente) dentro de `caja` y devuelve la capa. Las rutas de las
  // piezas y lupa.en vienen en coordenadas de cliente y aquí pasan a las de la capa.
  function capa(d, caja, contenido, extra){
    var k = recorte(d, caja);
    if (!k) return Promise.resolve(null);
    return (contenido ? png(enCaja(k, contenido), k[2], k[3]) : Promise.resolve(null)).then(function(fondo){
      var c = {id: d.id, hwnd: d.hwnd, x: k[0], y: k[1], w: k[2], h: k[3], fondo: fondo, duracion: 0};
      for (var n in extra || {}) c[n] = extra[n];
      (c.piezas || []).forEach(function(p){ p.ruta = (p.ruta || []).map(function(r){ return [r[0], r[1] - k[0], r[2] - k[1], r[3] == null ? 1 : r[3], r[4] == null ? 1 : r[4]]; }); });
      if (c.lupa && c.lupa.en) c.lupa.en = [c.lupa.en[0] - k[0], c.lupa.en[1] - k[1], c.lupa.en[2], c.lupa.en[3]];
      return c;
    });
  }
  // Los fotogramas de una capa con la misma `caja` (mismo recorte que capa()). f(i, n) → SVG en coordenadas de cliente.
  function fotos(d, caja, n, f){
    var k = recorte(d, caja);
    if (!k) return Promise.resolve([]);
    var ps = [];
    for (var i = 0; i < n; i++) ps.push(png(enCaja(k, f(i, n)), k[2], k[3]));
    return Promise.all(ps);
  }
  function pieza(contenido, w, h){
    w = Math.ceil(w); h = Math.ceil(h);
    return png(svg(w, h, contenido), w, h).then(function(p){ return {png: p, w: w, h: h}; });
  }

  // ---- notas con flecha que no tapan nada (la misma idea que las flechas de siempre) ----
  function choca(a, b, m){ m = m || 0; return !(a[0] + a[2] + m <= b[0] || b[0] + b[2] + m <= a[0] || a[1] + a[3] + m <= b[1] || b[1] + b[3] + m <= a[1]); }
  function nota(d, texto, opc){
    opc = opc || {};
    var s = d.escala || 1, col = color(opc.color || d.color), px = Math.round(15 * s), pad = 9 * s;
    var r = opc.cerca || d.r;
    var cw = (d.cliente || [1600, 900])[0], ch = (d.cliente || [1600, 900])[1];
    var w = medir(texto, px) + 2 * pad, h = px * 1.3 + 1.3 * pad;
    var occ = ocupado[d.hwnd] = ocupado[d.hwnd] || [];
    var caja = null;
    if (r){
      var x0 = r[0], y0 = r[1], x1 = r[0] + r[2], y1 = r[1] + r[3], cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
      var cands = [];
      [46, 110, 190, 300].forEach(function(k){
        k *= s;
        cands.push([x1 + k, cy - h / 2], [cx - w / 2, y1 + k * 0.8], [x0 - k - w, cy - h / 2], [cx - w / 2, y0 - k * 0.8 - h],
                   [x1 + k, y1 + 20 * s], [x1 + k, y0 - 20 * s - h], [x0 - k - w, y1 + 20 * s], [x0 - k - w, y0 - 20 * s - h]);
      });
      for (var i = 0; i < cands.length && !caja; i++){
        var c = [cands[i][0], cands[i][1], w, h];
        if (c[0] >= 2 && c[1] >= 2 && c[0] + w <= cw - 2 && c[1] + h <= ch - 2 && !choca(c, r, 4 * s) && !occ.some(function(o){ return choca(c, o, 6 * s); })) caja = c;
      }
      if (!caja) caja = [Math.min(Math.max(2, x1 + 46 * s), cw - w - 2), Math.min(Math.max(2, cy - h / 2), ch - h - 2), w, h];
    } else caja = [(cw - w) / 2, 24 * s, w, h];
    occ.push(caja);
    var out = '';
    if (r && opc.flecha !== false){      // flecha: del borde de la nota más cercano al objetivo hasta el objetivo
      var g = 4 * s, tx0 = r[0] - g, ty0 = r[1] - g, tx1 = r[0] + r[2] + g, ty1 = r[1] + r[3] + g, ocx = (tx0 + tx1) / 2, ocy = (ty0 + ty1) / 2;
      var pxn = Math.min(Math.max(ocx, caja[0]), caja[0] + w), pyn = Math.min(Math.max(ocy, caja[1]), caja[1] + h);
      var tx = Math.min(Math.max(pxn, tx0), tx1), ty = Math.min(Math.max(pyn, ty0), ty1);
      if (Math.hypot(tx - pxn, ty - pyn) > 8 * s) out += flecha(pxn, pyn, tx, ty, {color: col, grosor: 3.2 * s});
    }
    var fondo = mezclar(col, 0.10);
    out += '<rect x="' + caja[0] + '" y="' + caja[1] + '" width="' + w + '" height="' + h + '" rx="' + 7 * s + '" fill="' + fondo +
      '" fill-opacity="0.965" stroke="' + col + '" stroke-width="' + 2.4 * s + '"/>' +
      '<text x="' + (caja[0] + pad) + '" y="' + (caja[1] + h / 2) + '" dominant-baseline="central" font-size="' + px +
      '" font-weight="600" fill="' + col + '">' + esc(texto) + '</text>';
    return {svg: out, caja: caja};
  }
  function ocupar(d, caja){ (ocupado[d.hwnd] = ocupado[d.hwnd] || []).push(caja); }
  function mezclar(hex, k){                 // el color, aclarado hacia blanco (k = cuánto color queda)
    var n = parseInt(hex.slice(1), 16), c = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map(function(v){ return Math.round(255 - (255 - v) * k); });
    return '#' + c.map(function(v){ return ('0' + v.toString(16)).slice(-2); }).join('');
  }

  // Flecha de (x1, y1) a (x2, y2); curva > 0 la dobla (fracción del largo, hacia la izquierda del trayecto).
  function flecha(x1, y1, x2, y2, o){
    o = o || {};
    var col = color(o.color), gr = o.grosor || 3, L = Math.max(1e-6, Math.hypot(x2 - x1, y2 - y1)), cu = o.curva || 0;
    var qx = (x1 + x2) / 2 - (y2 - y1) / L * cu * L, qy = (y1 + y2) / 2 + (x2 - x1) / L * cu * L;
    var tx = x2 - qx, ty = y2 - qy, tl = Math.max(1e-6, Math.hypot(tx, ty)), ux = tx / tl, uy = ty / tl;
    var p = Math.max(9, gr * 4), ex = x2 - ux * p * 0.8, ey = y2 - uy * p * 0.8;
    var izq = [x2 - ux * p - uy * p * 0.55, y2 - uy * p + ux * p * 0.55], der = [x2 - ux * p + uy * p * 0.55, y2 - uy * p - ux * p * 0.55];
    return '<path d="M' + x1 + ' ' + y1 + ' Q' + qx + ' ' + qy + ' ' + ex + ' ' + ey + '" fill="none" stroke="' + col + '" stroke-width="' + gr +
      '" stroke-linecap="round"' + (o.punteada ? ' stroke-dasharray="' + gr * 3 + ' ' + gr * 2.2 + '"' : '') + '/>' +
      '<polygon points="' + x2 + ',' + y2 + ' ' + izq.join(',') + ' ' + der.join(',') + '" fill="' + col + '"/>';
  }

  // ---- librerías de vendor/ (rough.js, MathJax): se cargan la primera vez que hacen falta ----
  var LIBS = {
    rough: {archivo: 'rough.js', listo: function(){ return window.rough; }},
    mathjax: {archivo: 'tex-svg.js', listo: function(){ return window.MathJax && window.MathJax.tex2svgPromise && window.MathJax.startup && window.MathJax.startup.promise; },
              antes: function(){
                window.MathJax = {tex: {packages: {'[+]': []}}, svg: {fontCache: 'local'}, options: {enableMenu: false},
                                  startup: {typeset: false}, loader: {load: []}};
              }}
  };
  var cargando = {};
  function cargar(nombre){
    var L = LIBS[nombre];
    if (!L) return Promise.reject(new Error('librería desconocida: ' + nombre));
    if (L.listo()) return Promise.resolve(nombre === 'mathjax' ? window.MathJax.startup.promise : window.rough);
    if (cargando[nombre]) return cargando[nombre];
    if (L.antes) L.antes();
    var p = new Promise(function(ok, mal){
      var s = document.createElement('script');
      function poner(texto){ if (texto) s.textContent = texto; else s.src = (window.DIB_VENDOR || 'vendor/') + L.archivo; document.head.appendChild(s); }
      s.onload = function(){ ok(); }; s.onerror = function(){ mal(new Error('No se pudo cargar ' + L.archivo)); };
      var a = api();
      if (a && a.dib_recurso) a.dib_recurso(nombre).then(function(t){
        if (!t) return mal(new Error('No encuentro ' + L.archivo));
        poner(t); ok();                       // un script en línea corre al añadirlo: no hay onload
      }, mal);
      else poner(null);
    }).then(function(){
      if (nombre !== 'mathjax') return window.rough;
      return new Promise(function(ok){ (function esperar(){ if (L.listo()) ok(window.MathJax.startup.promise); else setTimeout(esperar, 30); })(); });
    });
    cargando[nombre] = p;
    p.catch(function(){ delete cargando[nombre]; });
    return p;
  }

  // LaTeX → SVG de MathJax, con tamaño en píxeles (las unidades del viewBox son milésimas de em).
  function tex(latex, o){
    o = o || {};
    var px = o.px || 20;
    return cargar('mathjax').then(function(){ return window.MathJax.tex2svgPromise(String(latex), {display: true}); }).then(function(nodo){
      if (nodo.querySelector('[data-mml-node="merror"]')) throw new Error('LaTeX con errores: ' + latex);
      var s = nodo.querySelector('svg'), vb = s.getAttribute('viewBox').split(/[ ,]+/).map(Number);
      var w = vb[2] / 1000 * px, h = vb[3] / 1000 * px;
      s.setAttribute('width', w); s.setAttribute('height', h);
      s.setAttribute('style', 'color:' + color(o.color || 'azul'));
      s.removeAttribute('role'); s.removeAttribute('focusable');
      return {svg: new XMLSerializer().serializeToString(s), w: w, h: h};
    });
  }

  var U = {color: color, esc: esc, medir: medir, svg: svg, png: png, capa: capa, fotos: fotos, pieza: pieza, nota: nota,
           flecha: flecha, mezclar: mezclar, choca: choca, ocupar: ocupar, recorte: recorte, cargar: cargar, tex: tex, FUENTE: FUENTE};

  function renderizar(lote){
    var dibujos = (lote && lote.dibujos) || lote || [];
    ocupado = {};
    dibujos.forEach(function(d){                 // las notas no tapan ningún objetivo del lote
      var o = ocupado[d.hwnd] = ocupado[d.hwnd] || [];
      if (d.r) o.push(d.r);
      (d.pasos || []).forEach(function(p){ if (p.r) o.push(p.r); if (p.hasta_r) o.push(p.hasta_r); });
      (d.evitar || []).forEach(function(e){ if (!d.r || !choca(e, d.r)) o.push(e); });
    });
    var capas = [], narracion = [], errores = [];
    return dibujos.reduce(function(cadena, d){
      return cadena.then(function(){
        var f = FORMAS[d.forma];
        if (!f){ errores.push((d.forma || '?') + ': forma desconocida'); return; }
        // lo que ya ocupan los dibujos anteriores entra en su «evitar» (salvo lo que cubre su propio objetivo)
        var dd = {}; for (var k in d) dd[k] = d[k];
        var cen = d.r ? [d.r[0] + d.r[2] / 2, d.r[1] + d.r[3] / 2] : null;
        dd.evitar = (d.evitar || []).concat((ocupado[d.hwnd] || []).filter(function(o){
          return !cen || !(cen[0] >= o[0] && cen[0] <= o[0] + o[2] && cen[1] >= o[1] && cen[1] <= o[1] + o[3]);
        }).map(function(o){ var c = o.slice(); c.fuerte = true; return c; }));     // «fuerte»: pisar otro dibujo pesa más que tapar un botón
        return Promise.resolve().then(function(){ return f(dd, U); }).then(function(r){
          var lista = (Array.isArray(r) ? r : [r]).filter(Boolean);
          lista.forEach(function(c, i){ if (!c.id || (i && c.id === d.id)) c.id = d.id + (i ? '_' + i : ''); c.hwnd = c.hwnd || d.hwnd; capas.push(c); });
          var cl = d.cliente || [1e9, 1e9];        // las notas de los dibujos siguientes no caen encima de este (salvo el foco, que lo cubre todo)
          lista.forEach(function(c){
            if (c.ocupa) c.ocupa.forEach(function(o){ ocupar(d, o); });          // las cajas exactas que declara la forma
            else if (c.w * c.h < 0.3 * cl[0] * cl[1]) ocupar(d, [c.x, c.y, c.w, c.h]);
            delete c.ocupa;
          });
          if (!lista.length) return;
          var ids = lista.map(function(c){ return c.id; }), con = lista.filter(function(c){ return c.tramos; })[0];
          var pasos = d.pasos || (d.partes && d.partes.map(function(p){ return {decir: p.decir || p.nota}; }));    // desarmar: una parte por tramo
          if (con && pasos) con.tramos.forEach(function(t, k){
            var p = pasos[k] || {};
            narracion.push({ids: ids, desde: t[0], hasta: t[1], texto: p.decir || p.texto || ''});
          });
          else narracion.push({ids: ids, desde: 0, hasta: Math.max.apply(null, lista.map(function(c){ return c.duracion || 0; })), texto: d.decir || d.texto || ''});
        }, function(e){ errores.push(d.forma + ': ' + (e && e.message || e) + (e && e.stack ? ' @ ' + (String(e.stack).split('\n')[1] || '').trim() : '')); });
      });
    }, Promise.resolve()).then(function(){ return {capas: capas, narracion: narracion, errores: errores}; });
  }

  var turno = 0;                               // cada mostrar() nuevo corta la narración del anterior
  function mostrar(lote, texto){
    var mio = ++turno, a = api(), voz = window.Voz && window.Voz.activa && window.Voz.activa();
    if (voz) window.Voz.callar();
    return renderizar(lote || []).then(function(r){
      if (r.errores.length) console.warn('Dibujante:', r.errores.join(' | '));
      var narrar = voz ? r.narracion.filter(function(t){ return t.texto; }) : [];
      var pausadas = {};
      narrar.forEach(function(t){ t.ids.forEach(function(id){ pausadas[id] = true; }); });
      r.capas.forEach(function(c){ if (pausadas[c.id]) c.auto = false; });
      var puesto = r.capas.length && a && a.capa_poner ? a.capa_poner({capas: r.capas}) : Promise.resolve();
      return Promise.resolve(puesto).then(function(){
        if (!voz) return r;
        if (!narrar.length) return texto ? window.Voz.decir(limpiar(texto)).then(function(){ return r; }) : r;
        return narrar.reduce(function(cadena, t){
          return cadena.then(function(){
            if (mio !== turno) return;
            t.ids.forEach(function(id){ if (a && a.capa_reproducir) a.capa_reproducir(id, t.desde, t.hasta); });
            return window.Voz.decir(t.texto);
          });
        }, Promise.resolve()).then(function(){
          if (mio === turno && a && a.capa_reproducir) Object.keys(pausadas).forEach(function(id){ a.capa_reproducir(id, null, null); });   // tras la voz, vuelven a andar solas
          return r;
        });
      });
    });
  }
  function limpiar(t){                         // el texto de la respuesta, sin enlaces ni marcas de formato, para la voz
    return String(t).replace(/```[\s\S]*?```/g, ' ').replace(/https?:\/\/\S+/g, ' ').replace(/[*_`#>|]/g, '').replace(/\s+/g, ' ').trim();
  }
  function borrar(){
    turno++;
    if (window.Voz && window.Voz.callar) window.Voz.callar();
    var a = api(); if (a && a.capa_borrar) return a.capa_borrar();
  }

  window.Dibujante = {
    registrar: function(forma, fn){ FORMAS[forma] = fn; },
    formas: function(){ return Object.keys(FORMAS); },
    renderizar: renderizar, probar: renderizar, mostrar: mostrar, borrar: borrar, U: U
  };
})();
