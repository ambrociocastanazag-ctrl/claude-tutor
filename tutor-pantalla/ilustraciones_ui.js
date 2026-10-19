/* Ilustraciones dentro del chat de los tutores (contrato: CONTRATO-MARCAS.md §7; lo que escriben los tutores:
   REGLAS_ILUSTRACIONES en ojos_panel.py).  window.Ilustraciones:
     antes(texto)      → el texto del tutor con las fórmulas $…$ / $$…$$ y los bloques ```svg / ```grafica cambiados por
                         marcas (\u0002id\u0003); la página lo llama al principio de bloques(), antes de escapar el texto.
                         Un bloque a medias (respuesta que llega a trozos) queda como «dibujando…»; un $$ sin cerrar, como texto.
     procesar(nodo)    → cambia esas marcas, dentro de nodo, por la fórmula, la figura o la gráfica (también lo hace solo un
                         MutationObserver, así que basta con pintar el HTML).
     compilar(expr)    → función x → número de una expresión («2x+1», «sin(x)/x», «sqrt(4-x^2)»); intérprete propio, sin eval.
     grafica(spec, P)  → texto SVG de una gráfica de funciones (spec = el JSON de ```grafica).
   Las figuras se muestran como <img> de un SVG ya filtrado (Dibujante.U.limpiarSvg): lo que traiga no puede ejecutar nada
   ni tocar los estilos de la página. Los colores por NOMBRE (tinta, suave, fondo, acento, azul…) se resuelven con el tema
   actual y se rehacen al cambiar de tema. */
(function(){
  'use strict';
  var NAV = typeof document !== 'undefined';
  var RAIZ = NAV ? window : {};

  // =====================================================================================================
  // 1. Intérprete de expresiones (tokenizador + parser recursivo → funciones). Nunca eval ni Function.
  // =====================================================================================================
  var FUN = {sqrt: Math.sqrt, cbrt: Math.cbrt, sin: Math.sin, cos: Math.cos, tan: Math.tan, asin: Math.asin, acos: Math.acos, atan: Math.atan,
             exp: Math.exp, ln: Math.log, log: Math.log10, log10: Math.log10, log2: Math.log2, abs: Math.abs, sinh: Math.sinh, cosh: Math.cosh,
             tanh: Math.tanh, floor: Math.floor, ceil: Math.ceil, sign: Math.sign};
  var ALIAS = {sen: 'sin', tg: 'tan', arcsin: 'asin', arccos: 'acos', arctan: 'atan', raiz: 'sqrt', lg: 'log10'};
  var CONST = {pi: Math.PI, e: Math.E, tau: 2 * Math.PI};
  function tiene(o, k){ return Object.prototype.hasOwnProperty.call(o, k); }
  var NOMBRES = Object.keys(FUN).concat(Object.keys(ALIAS), Object.keys(CONST), ['x']).sort(function(a, b){ return b.length - a.length; });

  function normalizar(s){
    return String(s).replace(/[−–—]/g, '-').replace(/[×·]/g, '*').replace(/÷/g, '/').replace(/π/g, ' pi ')
      .replace(/√/g, ' sqrt ').replace(/²/g, '^2').replace(/³/g, '^3').replace(/ /g, ' ')
      .replace(/(\d),(\d)/g, '$1.$2').replace(/\*\*/g, '^').replace(/^\s*(y|f\s*\(\s*x\s*\))\s*=\s*/i, '');
  }
  function partir(id){                                      // «sinx» → sin, x · «pix» → pi, x
    var out = [];
    while (id){
      var h = null;
      for (var i = 0; i < NOMBRES.length; i++) if (id.indexOf(NOMBRES[i]) === 0){ h = NOMBRES[i]; break; }
      if (!h) throw new Error('no entiendo «' + id + '»');
      out.push(h); id = id.slice(h.length);
    }
    return out;
  }
  function tokens(s){
    var t = [], i = 0, m;
    while (i < s.length){
      var rest = s.slice(i), c = s.charAt(i);
      if (/\s/.test(c)){ i++; continue; }
      if ((m = /^(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?/i.exec(rest))){ t.push({k: 'num', v: parseFloat(m[0])}); i += m[0].length; continue; }
      if ((m = /^[A-Za-z_]+\d*/.exec(rest))){
        var id = m[0].toLowerCase();
        function conocido(n){ return tiene(FUN, n) || tiene(ALIAS, n) || tiene(CONST, n) || n === 'x'; }
        if (!conocido(id)) id = /^[A-Za-z_]+/.exec(rest)[0].toLowerCase();
        i += id.length;
        (conocido(id) ? [id] : partir(id)).forEach(function(n){ t.push({k: 'id', v: tiene(ALIAS, n) ? ALIAS[n] : n}); });
        continue;
      }
      if ('+-*/^()'.indexOf(c) >= 0){ t.push({k: 'op', v: c}); i++; continue; }
      throw new Error('símbolo no permitido «' + c + '»');
    }
    return t;
  }
  function potencia(a, n){                                  // raíces reales de negativos: (-8)^(1/3) = -2
    if (a < 0 && !Number.isInteger(n)){
      for (var q = 3; q <= 9; q += 2){
        var pp = n * q;
        if (Math.abs(pp - Math.round(pp)) < 1e-9){ var r = Math.pow(-a, n); return Math.round(pp) % 2 === 0 ? r : -r; }
      }
      return NaN;
    }
    return Math.pow(a, n);
  }
  function compilar(texto){
    texto = normalizar(texto);
    if (!texto.trim()) throw new Error('expresión vacía');
    if (texto.length > 300) throw new Error('expresión demasiado larga');
    var tk = tokens(texto), p = 0, prof = 0;
    function es(v){ var t = tk[p]; return !!t && t.k === 'op' && t.v === v; }
    function empiezaPrimario(){ var t = tk[p]; return !!t && (t.k === 'num' || t.k === 'id' || (t.k === 'op' && t.v === '(')); }
    function esperar(v){ if (!es(v)) throw new Error('falta «' + v + '»'); p++; }
    function suma(){
      var a = prod();
      while (es('+') || es('-')){
        var op = tk[p++].v, b = prod();
        a = (function(a, b, mas){ return mas ? function(x){ return a(x) + b(x); } : function(x){ return a(x) - b(x); }; })(a, b, op === '+');
      }
      return a;
    }
    function prod(){
      var a = unario();
      for (;;){
        var b;
        if (es('*')){ p++; b = unario(); a = (function(a, b){ return function(x){ return a(x) * b(x); }; })(a, b); }
        else if (es('/')){ p++; b = unario(); a = (function(a, b){ return function(x){ return a(x) / b(x); }; })(a, b); }
        else if (empiezaPrimario()){ b = unario(); a = (function(a, b){ return function(x){ return a(x) * b(x); }; })(a, b); }   // 2x, 2(x+1)
        else return a;
      }
    }
    function unario(){
      if (es('-')){ p++; var u = unario(); return function(x){ return -u(x); }; }
      if (es('+')){ p++; return unario(); }
      return pot();
    }
    function pot(){
      var b = primario();
      if (es('^')){ p++; var e = unario(); return function(x){ return potencia(b(x), e(x)); }; }
      return b;
    }
    function primario(){
      var t = tk[p++];
      if (!t) throw new Error('la expresión termina antes de tiempo');
      if (t.k === 'num'){ var v = t.v; return function(){ return v; }; }
      if (t.k === 'id'){
        if (t.v === 'x') return function(x){ return x; };
        if (tiene(CONST, t.v)){ var c = CONST[t.v]; return function(){ return c; }; }
        var f = FUN[t.v], a;
        if (es('(')){ p++; a = suma(); esperar(')'); }
        else { if (!empiezaPrimario() && !es('-') && !es('+')) throw new Error('«' + t.v + '» necesita un argumento'); a = unario(); }
        return function(x){ return f(a(x)); };
      }
      if (t.v === '('){
        if (++prof > 60) throw new Error('demasiados paréntesis');
        var r = suma(); esperar(')'); prof--; return r;
      }
      throw new Error('no esperaba «' + t.v + '»');
    }
    var fn = suma();
    if (p < tk.length) throw new Error('sobra «' + (tk[p].v) + '»');
    return fn;
  }
  function numeroDe(v, nombre){                             // un límite del JSON: número o expresión constante («-2*pi»)
    var n = typeof v === 'number' ? v : (typeof v === 'string' ? compilar(v)(0) : NaN);
    if (typeof n !== 'number' || !isFinite(n) || Math.abs(n) > 1e6) throw new Error('«' + nombre + '» no es un número válido');
    return n;
  }

  // =====================================================================================================
  // 2. Gráficas de funciones → texto SVG
  // =====================================================================================================
  var ACENTOS = {
    claro: {azul: '#2a5fd0', verde: '#1d8a4a', rojo: '#d23a3a', naranja: '#d9741a', morado: '#7b45c9', amarillo: '#c9980a'},
    oscuro: {azul: '#6ea1ff', verde: '#4cc47f', rojo: '#ff7f7c', naranja: '#ffa650', morado: '#b68cff', amarillo: '#f2cf50'}
  };
  var P_CLARA = {modo: 'claro', tinta: '#2a2d3a', suave: '#d9d6cc', fondo: '#fcfbf8', acento: '#4a54c9'};
  var FUENTE = "'Segoe UI', system-ui, sans-serif";
  function paletaPor(base){                                 // {tinta, suave, fondo, acento} + los acentos por nombre del modo
    var P = {}, a = ACENTOS[base.modo] || ACENTOS.claro, k;
    for (k in base) P[k] = base[k];
    for (k in a) P[k] = a[k];
    return P;
  }
  function colorDe(P, nombre, def){
    var n = String(nombre == null ? '' : nombre).trim().toLowerCase();
    if (tiene(P, n) && n !== 'modo') return P[n];
    if (/^#[0-9a-f]{3,8}$/i.test(n)) return n;
    return def;
  }
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }
  function redondo(v){ return Math.round(v * 10) / 10; }

  function pasoBonito(rango, objetivo){
    var crudo = rango / objetivo, mag = Math.pow(10, Math.floor(Math.log10(crudo))), f = crudo / mag;
    return (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * mag;
  }
  function limpio(v){ return parseFloat(v.toPrecision(12)); }
  function ticksNum(lo, hi, objetivo){
    var paso = pasoBonito(hi - lo, objetivo), k0 = Math.ceil(lo / paso - 1e-9), k1 = Math.floor(hi / paso + 1e-9), out = [];
    for (var k = k0; k <= k1 && out.length < 60; k++) out.push(limpio(k * paso));
    return out;
  }
  function esMultiploPi(v){ var n = v / (Math.PI / 2); return Math.abs(n - Math.round(n)) < 1e-6; }
  function ticksPi(lo, hi){
    var span = (hi - lo) / Math.PI, paso = (span <= 2 ? 1 : span <= 7 ? 2 : 4) * Math.PI / 2, k0 = Math.ceil(lo / paso - 1e-9), k1 = Math.floor(hi / paso + 1e-9), out = [];
    for (var k = k0; k <= k1 && out.length < 60; k++) out.push(k * paso);
    return out;
  }
  function etiquetaPi(v){
    var n = Math.round(v / (Math.PI / 2)), s;
    if (n === 0) return '0';
    if (n % 2 === 0){ var k = n / 2; s = k === 1 ? 'π' : k === -1 ? '-π' : k + 'π'; }
    else s = n === 1 ? 'π/2' : n === -1 ? '-π/2' : n + 'π/2';
    return s.replace('-', '−');
  }
  function etiquetaNum(v){
    if (Math.abs(v) < 1e-12) return '0';
    var a = Math.abs(v), s;
    if (a >= 1e5 || a < 1e-3) s = v.toExponential(1).replace(/\.0e/, 'e').replace('e+', 'e');
    else s = String(parseFloat(v.toPrecision(6)));
    return s.replace('-', '−');
  }

  function discontinuo(fn, x0, x1, rango){                  // ¿hay un salto o una asíntota entre x0 y x1? (se estrecha hacia donde más cambia)
    var y0 = fn(x0), y1 = fn(x1);
    for (var k = 0; k < 40; k++){
      var m = (x0 + x1) / 2, ym = fn(m);
      if (!isFinite(ym)) return true;
      if (Math.abs(ym - y0) >= Math.abs(y1 - ym)){ x1 = m; y1 = ym; } else { x0 = m; y0 = ym; }
    }
    return Math.abs(y1 - y0) > rango * 0.05;
  }
  function frontera(fn, bueno, malo){                       // el punto con valor más cercano al borde del dominio
    for (var k = 0; k < 40; k++){
      var m = (bueno + malo) / 2;
      if (isFinite(fn(m))) bueno = m; else malo = m;
    }
    var y = fn(bueno);
    return isFinite(y) ? [bueno, y] : null;
  }
  function corridas(fn, a, b, n, rango){                    // tramos continuos [[x, y], …]: se corta en el dominio y en las asíntotas
    var runs = [], run = [], px = 0, py = NaN, i, x, y, e;
    for (i = 0; i <= n; i++){
      x = i === n ? b : a + (b - a) * i / n;
      y = fn(x); if (typeof y !== 'number' || !isFinite(y)) y = NaN;
      if (i > 0){
        if (isNaN(y) && !isNaN(py)){ e = frontera(fn, px, x); if (e) run.push(e); if (run.length > 1) runs.push(run); run = []; }
        else if (!isNaN(y) && isNaN(py)){ run = []; e = frontera(fn, x, px); if (e) run.push(e); }
        else if (!isNaN(y) && !isNaN(py) && Math.abs(y - py) > rango * 0.5 && discontinuo(fn, px, x, rango)){ if (run.length > 1) runs.push(run); run = []; }
      }
      if (!isNaN(y)) run.push([x, y]);
      px = x; py = y;
    }
    if (run.length > 1) runs.push(run);
    return runs;
  }
  function rangoDe(v, def, nombre){
    if (v == null) return def;
    if (!Array.isArray(v) || v.length !== 2) throw new Error('«' + nombre + '» tiene que ser [mínimo, máximo]');
    var a = numeroDe(v[0], nombre), b = numeroDe(v[1], nombre);
    if (!(a < b)) throw new Error('«' + nombre + '»: el mínimo tiene que ser menor que el máximo');
    return [a, b];
  }
  function compilarEn(f, que){
    try { return compilar(typeof f === 'number' ? String(f) : f); }
    catch (e) { throw new Error(que + ' («' + String(f).slice(0, 40) + '»): ' + e.message); }
  }

  function grafica(spec, P){
    P = P || paletaPor(P_CLARA);
    if (!spec || typeof spec !== 'object' || Array.isArray(spec)) throw new Error('el JSON tiene que ser un objeto {…}');
    var xr = rangoDe(spec.x, [-5, 5], 'x'), xa = xr[0], xb = xr[1];
    var lista = spec.funciones != null ? spec.funciones : spec.funcion != null ? [spec.funcion] : [];
    if (!Array.isArray(lista)) lista = [lista];
    if (lista.length > 8) throw new Error('máximo 8 funciones');
    var ORDEN = ['azul', 'rojo', 'verde', 'naranja', 'morado', 'amarillo'];
    var fns = lista.map(function(it, k){
      if (typeof it === 'string' || typeof it === 'number') it = {f: it};
      if (!it || typeof it !== 'object' || it.f == null) throw new Error('función ' + (k + 1) + ': falta «f»');
      return {fn: compilarEn(it.f, 'función ' + (k + 1)), nombre: it.nombre == null ? '' : String(it.nombre).slice(0, 60),
              color: colorDe(P, it.color, P[ORDEN[k % ORDEN.length]])};
    });
    var area = null;
    if (spec.area){
      var A = spec.area, ar = rangoDe(A.x, [xa, xb], 'area.x');
      if (A.f == null) throw new Error('area: falta «f»');
      area = {f: compilarEn(A.f, 'area.f'), g: compilarEn(A.g == null ? '0' : A.g, 'area.g'), a: Math.max(xa, ar[0]), b: Math.min(xb, ar[1]), color: colorDe(P, A.color, P.azul)};
    }
    var pts = (Array.isArray(spec.puntos) ? spec.puntos : []).slice(0, 20).map(function(q, k){
      var x, y, et, col;
      if (Array.isArray(q)){ x = q[0]; y = q[1]; et = q[2]; col = q[3]; } else if (q && typeof q === 'object'){ x = q.x; y = q.y; et = q.etiqueta || q.nombre; col = q.color; }
      else throw new Error('punto ' + (k + 1) + ' mal escrito');
      return {x: numeroDe(x, 'punto ' + (k + 1) + ' x'), y: numeroDe(y, 'punto ' + (k + 1) + ' y'), et: et == null ? '' : String(et).slice(0, 40), color: colorDe(P, col, P.tinta)};
    });
    if (!fns.length && !area && !pts.length) throw new Error('falta «funciones»');

    // ---- rango de y: el dado, o uno que deja ver la parte importante (sin que una asíntota lo estire) ----
    var yr = rangoDe(spec.y, null, 'y');
    if (!yr){
      var vals = [], N0 = 300;
      fns.concat(area ? [{fn: area.f}, {fn: area.g}] : []).forEach(function(o, j){
        var lo = area && j >= fns.length ? area.a : xa, hi = area && j >= fns.length ? area.b : xb;
        for (var i = 0; i <= N0; i++){ var v = o.fn(lo + (hi - lo) * i / N0); if (typeof v === 'number' && isFinite(v)) vals.push(v); }
      });
      pts.forEach(function(q){ vals.push(q.y); });
      vals.sort(function(p, q){ return p - q; });
      if (vals.length < 2) yr = [-5, 5];
      else {
        var lo2 = vals[Math.floor(vals.length * 0.02)], hi2 = vals[Math.min(vals.length - 1, Math.ceil(vals.length * 0.98))];
        if (lo2 > 0 && lo2 < 0.5 * hi2) lo2 = 0;
        if (hi2 < 0 && hi2 > 0.5 * lo2) hi2 = 0;
        var sp = hi2 - lo2; if (!(sp > 1e-12)){ lo2 -= 1; hi2 += 1; sp = 2; }
        yr = [lo2 - sp * 0.08, hi2 + sp * 0.08];
      }
    }
    var ya = yr[0], yb = yr[1];

    // ---- diseño ----
    var W = 520, titulo = spec.titulo == null ? '' : String(spec.titulo).slice(0, 90), leyenda = fns.filter(function(o){ return o.nombre; });
    var filas = [], fila = [], ancho = 0, maxAncho = W - 30;
    leyenda.forEach(function(o){
      var w = 24 + o.nombre.length * 6.6 + 18;
      if (ancho + w > maxAncho && fila.length){ filas.push(fila); fila = []; ancho = 0; }
      fila.push({o: o, x: ancho, w: w}); ancho += w;
    });
    if (fila.length) filas.push(fila);
    var cab = (titulo ? 26 : 0) + (filas.length ? filas.length * 18 + 4 : 0);
    var px0 = 46, py0 = 14 + cab, pw = W - px0 - 20, ph = 250, H = py0 + ph + 32;
    function sx(x){ return px0 + (x - xa) / (xb - xa) * pw; }
    function sy(y){ return py0 + ph - (y - ya) / (yb - ya) * ph; }
    function cl(v){ return Math.max(-5000, Math.min(5000, v)); }
    var rangoY = yb - ya, S = [];
    function t(x, y, txt, o){
      o = o || {};
      return '<text x="' + redondo(x) + '" y="' + redondo(y) + '" font-size="' + (o.tam || 11) + '" text-anchor="' + (o.anc || 'middle') + '"' + (o.peso ? ' font-weight="' + o.peso + '"' : '') +
        (o.cur ? ' font-style="italic"' : '') + ' fill="' + (o.col || P.tinta) + '"' + (o.halo === false ? '' : ' stroke="' + P.fondo + '" stroke-width="3" stroke-linejoin="round" paint-order="stroke"') + '>' + esc(txt) + '</text>';
    }
    S.push('<svg xmlns="http://www.w3.org/2000/svg" width="' + W + '" height="' + H + '" viewBox="0 0 ' + W + ' ' + H + '" font-family="' + FUENTE + '">');
    if (titulo) S.push('<title>' + esc(titulo) + '</title>', t(px0 - 36, 21, titulo, {anc: 'start', tam: 14, peso: 700, halo: false}));
    filas.forEach(function(f, r){
      var yy = (titulo ? 26 : 0) + 14 + r * 18;
      f.forEach(function(it){
        var x0 = 14 + it.x;
        S.push('<line x1="' + x0 + '" y1="' + (yy - 4) + '" x2="' + (x0 + 16) + '" y2="' + (yy - 4) + '" stroke="' + it.o.color + '" stroke-width="3" stroke-linecap="round"/>', t(x0 + 22, yy, it.o.nombre, {anc: 'start', tam: 12.5, halo: false}));
      });
    });
    // ejes y rejilla
    var piX = esMultiploPi(xa) && esMultiploPi(xb) && (xb - xa) >= Math.PI - 1e-9;
    var tx = piX ? ticksPi(xa, xb) : ticksNum(xa, xb, 7), ty = ticksNum(ya, yb, 6);
    var ejeY = ya <= 0 && yb >= 0 ? sy(0) : py0 + ph, ejeX = xa <= 0 && xb >= 0 ? sx(0) : px0;
    var rej = [];
    tx.forEach(function(v){ var x = sx(v); rej.push('M' + redondo(x) + ' ' + py0 + 'V' + (py0 + ph)); });
    ty.forEach(function(v){ var y = sy(v); rej.push('M' + px0 + ' ' + redondo(y) + 'H' + (px0 + pw)); });
    S.push('<path d="' + rej.join('') + '" stroke="' + P.suave + '" stroke-width="0.9" fill="none" opacity="0.85"/>',
           '<rect x="' + px0 + '" y="' + py0 + '" width="' + pw + '" height="' + ph + '" fill="none" stroke="' + P.suave + '" stroke-width="1"/>');
    S.push('<clipPath id="ilu-clip"><rect x="' + px0 + '" y="' + py0 + '" width="' + pw + '" height="' + ph + '"/></clipPath>');
    // área sombreada
    if (area && area.b > area.a){
      var N = 400, ruN = [], cur = null;
      for (var i = 0; i <= N; i++){
        var xv = area.a + (area.b - area.a) * i / N, fv = area.f(xv), gv = area.g(xv);
        if (isFinite(fv) && isFinite(gv)){ if (!cur){ cur = []; ruN.push(cur); } cur.push([xv, fv, gv]); } else cur = null;
      }
      var d = ruN.filter(function(r){ return r.length > 1; }).map(function(r){
        return 'M' + r.map(function(q){ return redondo(sx(q[0])) + ' ' + redondo(cl(sy(q[1]))); }).join('L') + 'L' +
               r.slice().reverse().map(function(q){ return redondo(sx(q[0])) + ' ' + redondo(cl(sy(q[2]))); }).join('L') + 'Z';
      }).join('');
      if (d) S.push('<path d="' + d + '" fill="' + area.color + '" fill-opacity="0.24" stroke="none" clip-path="url(#ilu-clip)"/>');
    }
    // ejes (encima del área, debajo de las curvas)
    S.push('<path d="M' + px0 + ' ' + redondo(ejeY) + 'H' + (px0 + pw) + 'M' + redondo(ejeX) + ' ' + py0 + 'V' + (py0 + ph) + '" stroke="' + P.tinta + '" stroke-width="1.3" fill="none"/>');
    var marcas = [];
    tx.forEach(function(v){ var x = sx(v); marcas.push('M' + redondo(x) + ' ' + redondo(ejeY - 3.5) + 'V' + redondo(ejeY + 3.5)); });
    ty.forEach(function(v){ var y = sy(v); marcas.push('M' + redondo(ejeX - 3.5) + ' ' + redondo(y) + 'H' + redondo(ejeX + 3.5)); });
    S.push('<path d="' + marcas.join('') + '" stroke="' + P.tinta + '" stroke-width="1.2" fill="none"/>');
    var ETQ = [];                                           // los números y los nombres de los ejes van encima de las curvas
    var etY = Math.min(ejeY + 15, py0 + ph + 15);
    tx.forEach(function(v){
      var lab = piX ? etiquetaPi(v) : etiquetaNum(v), x = sx(v);
      if (Math.abs(v) < 1e-12 && ejeX > px0 + 1) { ETQ.push(t(x - 6, etY, '0', {anc: 'end'})); return; }
      ETQ.push(t(x, etY, lab));
    });
    ty.forEach(function(v){
      if (Math.abs(v) < 1e-12 && ejeY < py0 + ph - 1 && ejeX > px0 + 1) return;           // el 0 ya está en el eje x
      ETQ.push(t(ejeX - 7, sy(v) + 3.8, etiquetaNum(v), {anc: 'end'}));
    });
    ETQ.push(t(px0 + pw - 4, ejeY - 7, 'x', {anc: 'end', cur: true, tam: 12.5}), t(ejeX + 8, py0 + 12, 'y', {anc: 'start', cur: true, tam: 12.5}));
    // curvas
    var nMuestras = Math.min(1200, Math.round(pw * 1.6));
    fns.forEach(function(o){
      var d2 = corridas(o.fn, xa, xb, nMuestras, rangoY).map(function(r){
        return 'M' + r.map(function(q){ return redondo(sx(q[0])) + ' ' + redondo(cl(sy(q[1]))); }).join('L');
      }).join('');
      if (d2) S.push('<path d="' + d2 + '" fill="none" stroke="' + o.color + '" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round" clip-path="url(#ilu-clip)"/>');
    });
    S.push(ETQ.join(''));
    // puntos
    pts.forEach(function(q){
      if (q.x < xa || q.x > xb || q.y < ya || q.y > yb) return;
      var x = sx(q.x), y = sy(q.y);
      S.push('<circle cx="' + redondo(x) + '" cy="' + redondo(y) + '" r="4.4" fill="' + q.color + '" stroke="' + P.fondo + '" stroke-width="1.6"/>');
      if (q.et){
        var anc = x + 8 + q.et.length * 6.4 > px0 + pw ? 'end' : 'start', ly = y - 9 < py0 + 12 ? y + 17 : y - 9;
        S.push(t(anc === 'end' ? x - 7 : x + 7, ly, q.et, {anc: anc, tam: 12, peso: 600}));
      }
    });
    S.push('</svg>');
    return S.join('');
  }

  // =====================================================================================================
  // 3. El texto del tutor → marcas (fórmulas y figuras). Funciones puras: se prueban con node.
  // =====================================================================================================
  var REG = {};                                              // id → {tipo: 'mate' | 'svg' | 'grafica' | 'hueco', …}
  function hash(s){ var h = 5381; for (var i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0; return (h >>> 0).toString(36) + s.length.toString(36); }
  function marca(reg, clave){
    var id = reg.tipo.charAt(0) + hash(clave);
    reg.id = id; REG[id] = reg;
    return '\u0002' + id + '\u0003';
  }
  function marcaMate(tex, bloque){ return marca({tipo: 'mate', tex: tex, bloque: bloque}, (bloque ? 'B' : 'I') + tex); }

  function figuraEnBloque(p, cerrado){                      // p = lo que hay entre ``` y ```; devuelve la marca o null si no es svg/gráfica
    var m = /^[ \t]*(svg|grafica|gráfica)(?=[ \t\r\n]|$)([^\n]*)(?:\n([\s\S]*))?$/i.exec(p);
    if (!m){
      var w = p.trim().toLowerCase();
      if (!cerrado && w && p.indexOf('\n') < 0 && ('svg'.indexOf(w) === 0 || 'grafica'.indexOf(w) === 0 || 'gráfica'.indexOf(w) === 0))
        return marca({tipo: 'hueco', texto: 'dibujando…'}, 'hueco');
      return null;
    }
    var esSvg = m[1].toLowerCase() === 'svg';
    if (!cerrado) return marca({tipo: 'hueco', texto: esSvg ? 'dibujando la figura…' : 'dibujando la gráfica…'}, 'hueco' + (esSvg ? 's' : 'g'));
    if (esSvg){
      var pie = m[2].trim(), cuerpo = (m[3] || '').trim();
      if (!cuerpo && /^<svg/i.test(pie)){ cuerpo = pie; pie = ''; }
      return marca({tipo: 'svg', cuerpo: cuerpo, pie: pie}, 's' + pie + '\n' + cuerpo);
    }
    var json = (m[2] + '\n' + (m[3] || '')).trim();
    return marca({tipo: 'grafica', json: json}, 'g' + json);
  }
  function matesEnLinea(seg){                               // $…$ de una línea de texto (no precios como «$5», no celdas como $B$2)
    var out = '', i = 0, n = seg.length;
    while (i < n){
      var c = seg.charAt(i);
      if (c === '\\' && seg.charAt(i + 1) === '$'){ out += '$'; i += 2; continue; }
      if (c === '$'){
        var ant = i > 0 ? seg.charAt(i - 1) : '', sig = seg.charAt(i + 1), ok = false, j = -1;
        if (!/[\w]/.test(ant) && sig && !/[\s$]/.test(sig)){
          j = i + 1;
          while (j < n && !(seg.charAt(j) === '$' && seg.charAt(j - 1) !== '\\')) j++;
          if (j < n){
            var cont = seg.slice(i + 1, j);
            ok = cont.length <= 400 && !/\n\s*\n/.test(cont) && !/\s$/.test(cont) && !/\d/.test(seg.charAt(j + 1) || 'a');
            if (ok && /\d/.test(sig) && !/[A-Za-z\\^_{}=+*\/()\-]/.test(cont)) ok = false;
            if (ok && /\d/.test(sig) && (/;/.test(cont) || /[A-Za-z]{3,}/.test(cont.replace(/\\[A-Za-z]+/g, '')))) ok = false;   // «$10; =SUMA($B…» no es una fórmula
          }
        }
        if (ok){ out += marcaMate(seg.slice(i + 1, j), false); i = j + 1; continue; }
      }
      out += c; i++;
    }
    return out;
  }
  function mates(p){                                         // fuera de los bloques de código: $$…$$ y $…$ (sin tocar el `código`)
    return p.split(/(`[^`\n]*`)/).map(function(seg, k){
      if (k % 2) return seg;
      seg = seg.replace(/\$\$([\s\S]+?)\$\$/g, function(todo, tex){ return tex.trim() ? '\n\n' + marcaMate(tex.trim(), true) + '\n\n' : todo; });
      return matesEnLinea(seg);
    }).join('');
  }
  function antes(texto){
    var piezas = String(texto == null ? '' : texto).split('```'), res = '', quitado = false;
    for (var i = 0; i < piezas.length; i++){
      var p = piezas[i];
      if (i % 2 === 0) res += (i > 0 && !quitado ? '```' : '') + mates(p);
      else {
        var mk = figuraEnBloque(p, i < piezas.length - 1);
        if (mk){ res += '\n\n' + mk + '\n\n'; quitado = true; } else { res += '```' + p; quitado = false; }
      }
    }
    return res;
  }

  // =====================================================================================================
  // 4. En la página: tema, figuras, fórmulas, botones
  // =====================================================================================================
  var API = {antes: antes, compilar: compilar, grafica: grafica, paletaPor: paletaPor, etiquetaPi: etiquetaPi, _reg: REG};
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  if (!NAV){ return; }
  RAIZ.Ilustraciones = API;

  var CSS = [
    '.ilu-fig{position:relative;margin:4px 0;border:1px solid var(--line,#d6d3c8);border-radius:10px;background:var(--surface,#fff);overflow:hidden;max-width:100%;min-width:0;color:var(--ink,#222)}',
    '.ilu-lienzo{padding:8px 10px 4px;display:flex;justify-content:center;min-width:0}',
    '.ilu-lienzo img{display:block;width:100%;height:auto;max-width:100%;-webkit-user-drag:none;user-select:none}',
    '.ilu-fig figcaption{padding:2px 14px 9px;font-size:11.5px;line-height:1.4;color:var(--ink3,#777);text-align:center;overflow-wrap:anywhere}',
    '.ilu-bar{position:absolute;top:6px;right:6px;display:flex;gap:3px;opacity:0;transition:opacity .15s;pointer-events:none}',
    '.ilu-fig:hover .ilu-bar,.ilu-fig:focus-within .ilu-bar{opacity:1;pointer-events:auto}',
    '.ilu-bar button{width:26px;height:26px;padding:0;border:1px solid var(--line,#d6d3c8);border-radius:7px;background:color-mix(in srgb,var(--surface,#fff) 90%,transparent);color:var(--ink2,#555);display:grid;place-items:center;cursor:pointer}',
    '.ilu-bar button:hover{background:var(--acc-soft,#e8eaff);color:var(--acc-text,#3340b8);border-color:var(--acc-mid,#aab)}',
    '.ilu-bar svg{width:15px;height:15px}',
    '.ilu-aviso{display:flex;gap:8px;align-items:flex-start;padding:7px 12px;font-size:12px;line-height:1.4;color:var(--warn,#8a5a00);background:var(--warn-soft,#fff6df);overflow-wrap:anywhere}',
    '.ilu-aviso b{flex-shrink:0}',
    '.ilu-hueco{margin:4px 0;padding:22px 12px;border:1px dashed var(--line,#d6d3c8);border-radius:10px;text-align:center;font-size:12.5px;color:var(--ink3,#777);background:var(--sunk,#f2f0ea)}',
    '.ilu-hueco span{animation:iluPulso 1.3s ease-in-out infinite}',
    '@keyframes iluPulso{0%,100%{opacity:.45}50%{opacity:1}}',
    '.ilu-mat{border-radius:4px;cursor:pointer}',
    '.ilu-mat:hover{background:var(--acc-soft,#e8eaff)}',
    '.ilu-mat svg{max-width:none}',
    '.ilu-mat.pendiente,.ilu-mat.error{font-family:var(--mono,Consolas,monospace);font-size:.92em;color:var(--code-ink,#445);background:var(--code-bg,#eef)}',
    '.ilu-mat.error{color:var(--bad,#b00)}',
    '.ilu-bloque{position:relative;margin:6px 0;padding:10px 78px 10px 12px;border-radius:10px;background:var(--sunk,#f4f2ec);border:1px solid var(--line2,#e6e3da);text-align:center;font-size:1.14em;overflow-x:auto;overflow-y:hidden}',
    '.ilu-bloque .ilu-mat{display:inline-block;max-width:none}',
    '.ilu-latex{position:absolute;top:6px;right:6px;height:23px;padding:0 8px;border:1px solid var(--line,#d6d3c8);border-radius:7px;background:var(--surface,#fff);color:var(--ink2,#555);font:600 11px var(--sans,system-ui);cursor:pointer;opacity:.75;white-space:nowrap}',
    '.ilu-latex:hover{opacity:1;background:var(--acc-soft,#e8eaff);color:var(--acc-text,#3340b8)}',
    '.ilu-toast{position:fixed;z-index:2147483600;padding:4px 10px;border-radius:999px;font:600 12px var(--sans,system-ui);background:var(--ink,#222);color:var(--bg,#fff);box-shadow:0 2px 8px rgba(0,0,0,.25);pointer-events:none;max-width:70vw;overflow-wrap:anywhere}',
    '.ilu-toast.mal{background:var(--bad,#b00);color:#fff}',
    '.ilu-ampliado{position:fixed;inset:0;z-index:2147483000;display:flex;align-items:center;justify-content:center;background:var(--velo,rgba(20,20,30,.6));cursor:zoom-out}',
    '.ilu-ampliado .ilu-caja{background:var(--surface,#fff);border:1px solid var(--line,#ccc);border-radius:14px;padding:14px;box-shadow:0 12px 40px rgba(0,0,0,.35);cursor:default;max-width:96vw;max-height:94vh}',
    '.ilu-ampliado img{display:block;height:auto}',
    '.ilu-ampliado small{display:block;margin-top:8px;text-align:center;font-size:11.5px;color:var(--ink3,#777)}'
  ].join('\n');
  var estilo = document.createElement('style'); estilo.id = 'ilu-css'; estilo.textContent = CSS; document.head.appendChild(estilo);

  // ---- tema: el modo (claro / oscuro) y los colores del panel, como colores concretos (para las imágenes) ----
  var sonda = document.createElement('div'); sonda.setAttribute('aria-hidden', 'true'); sonda.style.cssText = 'position:fixed;left:-9999px;top:0;width:1px;height:1px;visibility:hidden;pointer-events:none';
  document.documentElement.appendChild(sonda);
  var lienzoColor = document.createElement('canvas'); lienzoColor.width = lienzoColor.height = 1;
  var cc = lienzoColor.getContext('2d', {willReadFrequently: true});
  function aHex(css){                                       // cualquier color CSS (oklch incluido) → #rrggbb
    try {
      cc.clearRect(0, 0, 1, 1); cc.fillStyle = '#000'; cc.fillStyle = css; cc.fillRect(0, 0, 1, 1);
      var d = cc.getImageData(0, 0, 1, 1).data;
      return '#' + [d[0], d[1], d[2]].map(function(v){ return ('0' + v.toString(16)).slice(-2); }).join('');
    } catch (e) { return null; }
  }
  function variable(nombre, respaldo){
    var v = getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();
    if (!v) return respaldo;
    sonda.style.color = ''; sonda.style.color = 'var(' + nombre + ')';
    return aHex(getComputedStyle(sonda).color) || respaldo;
  }
  function esOscuro(){
    sonda.style.color = ''; sonda.style.color = 'light-dark(rgb(1, 1, 1), rgb(2, 2, 2))';
    var c = getComputedStyle(sonda).color;
    if (/^rgb\(\s*1,/.test(c)) return false;
    if (/^rgb\(\s*2,/.test(c)) return true;
    return !!(RAIZ.matchMedia && RAIZ.matchMedia('(prefers-color-scheme: dark)').matches);
  }
  var PALETA = null;
  function paleta(){
    if (PALETA) return PALETA;
    var oscuro = esOscuro();
    PALETA = paletaPor({modo: oscuro ? 'oscuro' : 'claro', tinta: variable('--ink', oscuro ? '#ece9e1' : '#2a2d3a'), suave: variable('--line', oscuro ? '#454a5a' : '#d9d6cc'),
                        fondo: variable('--surface', oscuro ? '#2b2e3a' : '#fcfbf8'), acento: variable('--acc', oscuro ? '#8fa0ff' : '#4a54c9')});
    return PALETA;
  }

  // ---- avisos pequeños y copiar ----
  function avisar(ancla, texto, mal){
    var r = ancla && ancla.getBoundingClientRect ? ancla.getBoundingClientRect() : {left: 20, top: 40, width: 0};
    var d = document.createElement('div'); d.className = 'ilu-toast' + (mal ? ' mal' : ''); d.textContent = texto; document.body.appendChild(d);
    var w = d.offsetWidth;
    d.style.left = Math.max(6, Math.min(innerWidth - w - 6, r.left + r.width / 2 - w / 2)) + 'px';
    d.style.top = Math.max(6, r.top - 32) + 'px';
    setTimeout(function(){ d.remove(); }, mal ? 3200 : 1500);
  }
  function copiarTexto(txt){
    function aMano(){                                       // la ventana del panel no siempre deja usar navigator.clipboard
      var ta = document.createElement('textarea'); ta.value = txt; ta.style.cssText = 'position:fixed;left:-9999px;top:0';
      document.body.appendChild(ta); ta.select();
      var ok = false; try { ok = document.execCommand('copy'); } catch (e) {}
      ta.remove(); return ok;
    }
    if (!navigator.clipboard || !navigator.clipboard.writeText) return Promise.resolve(aMano());
    return navigator.clipboard.writeText(txt).then(function(){ return true; }, function(){ return aMano(); });
  }
  function icono(d){ return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">' + d + '</svg>'; }
  var IC = {
    ampliar: icono('<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>'),
    copiar: icono('<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h9"/>'),
    png: icono('<path d="M12 4v11M7 11l5 5 5-5M5 20h14"/>'),
    app: icono('<path d="M5 4l14 7-6 2-2 6z"/>')
  };

  // ---- fórmulas ----
  var MATES = {};                                           // 'I' / 'B' + tex → {html} | {error}
  function pintarMate(cont, tex, bloque){
    var k = (bloque ? 'B' : 'I') + tex, hecho = MATES[k];
    function poner(r){
      if (r.error){ cont.className = 'ilu-mat error'; cont.textContent = (bloque ? '$$' : '$') + tex + (bloque ? '$$' : '$'); cont.title = 'LaTeX con errores: ' + r.error; }
      else { cont.className = 'ilu-mat'; cont.innerHTML = r.html; cont.title = 'Clic para copiar el LaTeX'; }
    }
    if (hecho){ poner(hecho); return; }
    cont.className = 'ilu-mat pendiente'; cont.textContent = tex;
    if (!(RAIZ.Dibujante && Dibujante.U && Dibujante.U.cargar)){ return; }
    Dibujante.U.cargar('mathjax').then(function(){ return RAIZ.MathJax.tex2svgPromise(tex, {display: !!bloque}); }).then(function(nodo){
      var s = nodo.querySelector('svg'), r;
      if (!s || nodo.querySelector('[data-mml-node="merror"]')) r = {error: ((nodo.querySelector('[data-mml-node="merror"]') || {}).getAttribute ? nodo.querySelector('[data-mml-node="merror"]').getAttribute('data-mjx-error') : '') || 'no se pudo escribir'};
      else { s.removeAttribute('role'); s.removeAttribute('focusable'); r = {html: s.outerHTML}; }
      MATES[k] = r; poner(r);
    }, function(){ /* sin MathJax se queda el LaTeX en texto */ });
  }
  function elMate(tex, bloque){
    var dentro = document.createElement('span'); dentro.setAttribute('data-tex', tex); dentro.setAttribute('data-bloque', bloque ? '1' : '0');
    pintarMate(dentro, tex, bloque);
    dentro.addEventListener('click', function(ev){
      if (RAIZ.getSelection && String(getSelection()).length) return;
      copiarTexto(bloque ? '$$\n' + tex + '\n$$' : '$' + tex + '$').then(function(ok){ avisar(dentro, ok ? 'LaTeX copiado' : 'No pude copiar', !ok); });
    });
    if (!bloque) return dentro;
    var cont = document.createElement('div'); cont.className = 'ilu-bloque';
    var b = document.createElement('button'); b.type = 'button'; b.className = 'ilu-latex'; b.textContent = '📋 LaTeX'; b.title = 'Copiar el LaTeX ($$…$$)';
    b.addEventListener('click', function(){ copiarTexto('$$\n' + tex + '\n$$').then(function(ok){ avisar(b, ok ? 'LaTeX copiado' : 'No pude copiar', !ok); }); });
    cont.appendChild(dentro); cont.appendChild(b);
    return cont;
  }

  // ---- figuras ----
  var NOMBRE_COLOR = {tinta: 'tinta', suave: 'suave', fondo: 'fondo', acento: 'acento', azul: 1, verde: 1, rojo: 1, naranja: 1, morado: 1, amarillo: 1};
  var ATRS_COLOR = ['fill', 'stroke', 'stop-color', 'color', 'flood-color'];
  function nombresACss(v, P){                               // «azul» → #…, «currentColor» → tinta; lo demás queda igual
    var l = String(v).trim().toLowerCase();
    if (tiene(NOMBRE_COLOR, l)) return P[l];
    if (l === 'currentcolor') return P.tinta;
    return v;
  }
  function coloresEnCss(css, P){
    return css.replace(/\b(fill|stroke|stop-color|color|flood-color)(\s*:\s*)([A-Za-z]+)/g, function(todo, prop, sep, val){
      return tiene(NOMBRE_COLOR, val.toLowerCase()) ? prop + sep + P[val.toLowerCase()] : todo;
    });
  }
  function svgTexto(cuerpo, P){                             // SVG del tutor → {svg, w, h} con colores del tema, o {aviso}
    var U = RAIZ.Dibujante && Dibujante.U;
    if (!U || !U.limpiarSvg) return {aviso: 'el filtro de figuras no está disponible'};
    var sano = U.limpiarSvg(cuerpo);
    if (!sano) return {aviso: 'No pude dibujar la figura (' + (U.limpiarSvg.error || 'SVG no válido') + ')'};
    var doc = new DOMParser().parseFromString(sano, 'image/svg+xml'), raiz = doc.documentElement;
    Array.prototype.forEach.call(doc.getElementsByTagName('*'), function(el){
      ATRS_COLOR.forEach(function(a){ if (el.hasAttribute(a)) el.setAttribute(a, nombresACss(el.getAttribute(a), P)); });
      if (el.hasAttribute('style')) el.setAttribute('style', coloresEnCss(el.getAttribute('style'), P));
      var n = el.localName.toLowerCase();
      if (n === 'style') el.textContent = coloresEnCss(el.textContent, P);
      if (/^(animate|set|animatetransform)$/.test(n) && ATRS_COLOR.indexOf(el.getAttribute('attributeName')) >= 0)
        ['from', 'to', 'by', 'values'].forEach(function(a){
          if (el.hasAttribute(a)) el.setAttribute(a, el.getAttribute(a).split(';').map(function(s){ return nombresACss(s, P); }).join(';'));
        });
    });
    var vb = (raiz.getAttribute('viewBox') || '').trim().split(/[\s,]+/).map(Number);
    if (vb.length !== 4 || vb.some(isNaN) || vb[2] <= 0 || vb[3] <= 0){
      var w0 = parseFloat(raiz.getAttribute('width')), h0 = parseFloat(raiz.getAttribute('height'));
      if (!(w0 > 0 && h0 > 0)) return {aviso: 'La figura necesita un viewBox (por ejemplo viewBox="0 0 320 180")'};
      vb = [0, 0, w0, h0];
    }
    var w = Math.min(vb[2], 1600), h = w * vb[3] / vb[2];
    raiz.setAttribute('viewBox', vb.join(' ')); raiz.setAttribute('width', redondo(w)); raiz.setAttribute('height', redondo(h));
    raiz.removeAttribute('x'); raiz.removeAttribute('y');
    if (!raiz.hasAttribute('fill')) raiz.setAttribute('fill', P.tinta);                // el texto sin color sigue el tema
    if (!raiz.hasAttribute('font-family')) raiz.setAttribute('font-family', FUENTE);
    return {svg: new XMLSerializer().serializeToString(raiz), w: w, h: h};
  }
  function graficaTexto(json, P){
    var spec;
    try { spec = JSON.parse(json); }
    catch (e) {
      try { spec = JSON.parse(json.replace(/,(\s*[}\]])/g, '$1')); }
      catch (e2) {
        var ln = /line (\d+)/.exec(String(e.message));
        return {aviso: 'No pude dibujar la gráfica: el JSON está mal escrito (revisa comas, comillas y llaves' + (ln ? ', cerca de la línea ' + ln[1] : '') + ').'};
      }
    }
    try {
      var svg = grafica(spec, P), m = /width="(\d+)" height="(\d+)"/.exec(svg);
      return {svg: svg, w: +m[1], h: +m[2], pie: spec.pie ? String(spec.pie).slice(0, 200) : ''};
    } catch (e3) { return {aviso: 'No pude dibujar la gráfica: ' + String(e3.message).slice(0, 140)}; }
  }
  function urlSvg(svg){ return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg); }

  function aPng(fig){                                       // Promise<Blob PNG> de la figura tal como se ve ahora
    var r = fig._r, P = paleta();
    return new Promise(function(ok, mal){
      var im = new Image();
      im.onload = function(){
        var k = Math.min(2, 2400 / Math.max(r.w, r.h)), c = document.createElement('canvas');
        c.width = Math.round(r.w * k); c.height = Math.round(r.h * k);
        var g = c.getContext('2d'); g.fillStyle = P.fondo; g.fillRect(0, 0, c.width, c.height); g.drawImage(im, 0, 0, c.width, c.height);
        c.toBlob(function(b){ b ? ok(b) : mal(new Error('no se pudo crear el PNG')); }, 'image/png');
      };
      im.onerror = function(){ mal(new Error('no se pudo leer la figura')); };
      im.src = urlSvg(fig._svg);
    });
  }
  function guardarPng(fig, btn){
    aPng(fig).then(function(blob){
      var a = RAIZ.pywebview && RAIZ.pywebview.api;
      if (a && a.guardar_imagen){                           // si el panel sabe guardar archivos, mejor
        return new Promise(function(ok){ var fr = new FileReader(); fr.onload = function(){ ok(String(fr.result).split(',')[1]); }; fr.readAsDataURL(blob); })
          .then(function(b64){ return a.guardar_imagen(b64, 'ilustracion.png'); })
          .then(function(r){ avisar(btn, r && r.ok ? 'PNG guardado' + (r.ruta ? ': ' + r.ruta : '') : (r && r.error) || 'No pude guardar', !(r && r.ok)); });
      }
      function descargar(){
        var u = URL.createObjectURL(blob), l = document.createElement('a'); l.href = u; l.download = 'ilustracion.png';
        document.body.appendChild(l); l.click(); l.remove(); setTimeout(function(){ URL.revokeObjectURL(u); }, 4000);
        avisar(btn, a ? 'Descarga pedida; si no aparece el archivo, usa «Copiar SVG»' : 'PNG guardado');
      }
      if (!(a && navigator.clipboard && window.ClipboardItem)) { if (a) avisar(btn, 'No pude guardar el PNG aquí', true); else descargar(); return; }
      return navigator.clipboard.write([new ClipboardItem({'image/png': blob})]).then(
        function(){ avisar(btn, 'Imagen copiada: pégala donde quieras'); },
        function(){ descargar(); });
    }, function(e){ avisar(btn, e.message, true); });
  }
  var abierto = null;
  function cerrarAmpliado(){ if (abierto){ abierto.remove(); abierto = null; document.removeEventListener('keydown', alTeclear, true); } }
  function alTeclear(e){ if (e.key === 'Escape'){ e.stopPropagation(); cerrarAmpliado(); } }
  function ampliar(fig){
    cerrarAmpliado();
    var r = fig._r, ov = document.createElement('div'); ov.className = 'ilu-ampliado';
    var caja = document.createElement('div'); caja.className = 'ilu-caja';
    var im = document.createElement('img'); im.src = urlSvg(fig._svg); im.alt = '';
    im.style.width = 'min(calc(94vw - 30px), calc((94vh - 70px) * ' + (r.w / r.h).toFixed(4) + '))';
    var peq = document.createElement('small'); peq.textContent = (fig._reg.pie || r.pie || '') + (fig._reg.pie || r.pie ? ' · ' : '') + 'Esc o clic fuera para cerrar';
    caja.appendChild(im); caja.appendChild(peq); ov.appendChild(caja);
    ov.addEventListener('click', function(e){ if (!caja.contains(e.target)) cerrarAmpliado(); });
    document.body.appendChild(ov); abierto = ov; document.addEventListener('keydown', alTeclear, true);
  }
  function ponerEnApp(fig, btn){
    var a = RAIZ.pywebview && RAIZ.pywebview.api;
    if (!a || !a.ilustracion_en_app){ avisar(btn, 'Este panel no puede ponerlo en la app', true); return; }
    a.ilustracion_en_app(fig._svg).then(function(r){
      if (r && r.ok){ if (RAIZ.Dibujante) Dibujante.mostrar(r.dibujos, '', {sinVoz: true}); avisar(btn, 'Puesto encima de la app'); }
      else avisar(btn, (r && r.error) || 'No pude ponerlo en la app', true);
    }, function(e){ avisar(btn, String((e && e.message) || e).slice(0, 100), true); });
  }
  function rellenarFigura(fig){
    var reg = fig._reg, P = paleta(), r;
    try { r = reg.tipo === 'svg' ? svgTexto(reg.cuerpo, P) : graficaTexto(reg.json, P); } catch (e) { r = {aviso: 'No pude dibujar la figura: ' + String(e.message || e).slice(0, 120)}; }
    var lienzo = fig.querySelector('.ilu-lienzo'), pie = fig.querySelector('figcaption'), bar = fig.querySelector('.ilu-bar');
    lienzo.textContent = ''; bar.textContent = '';
    fig._r = r; fig._svg = r.svg || null;
    pie.textContent = reg.pie || r.pie || ''; pie.hidden = !pie.textContent;
    if (fig._aviso){ fig._aviso.remove(); fig._aviso = null; }
    if (!r.svg){
      lienzo.hidden = true; bar.hidden = true;
      var av = document.createElement('div'); av.className = 'ilu-aviso'; av.innerHTML = '<b>⚠</b><span></span>'; av.lastChild.textContent = r.aviso;
      lienzo.parentNode.insertBefore(av, lienzo); fig._aviso = av; return;
    }
    lienzo.hidden = false; bar.hidden = false;
    var im = document.createElement('img'); im.alt = reg.pie || (reg.tipo === 'grafica' ? 'Gráfica' : 'Figura'); im.draggable = false;
    im.style.maxWidth = r.w + 'px'; im.setAttribute('width', r.w); im.setAttribute('height', r.h); im.src = urlSvg(r.svg);
    lienzo.appendChild(im);
    [['ampliar', 'Ampliar', function(b){ ampliar(fig); }],
     ['copiar', 'Copiar SVG', function(b){ copiarTexto(fig._svg).then(function(ok){ avisar(b, ok ? 'SVG copiado' : 'No pude copiar', !ok); }); }],
     ['png', 'Guardar PNG', function(b){ guardarPng(fig, b); }],
     ['app', 'Ponlo en la app', function(b){ ponerEnApp(fig, b); }]].forEach(function(d){
      var b = document.createElement('button'); b.type = 'button'; b.title = d[1]; b.setAttribute('aria-label', d[1]); b.innerHTML = IC[d[0]];
      b.addEventListener('click', function(e){ e.stopPropagation(); d[2](b); });
      bar.appendChild(b);
    });
  }
  var FIGURAS = {};                                         // id → figura ya hecha: al llegar más texto no se rehace (ni se reinicia su animación)
  function elFigura(reg){
    var f = FIGURAS[reg.id];
    if (f && !f.isConnected) return f;
    f = document.createElement('figure'); f.className = 'ilu-fig'; f._reg = reg;
    f.innerHTML = '<div class="ilu-lienzo"></div><figcaption hidden></figcaption><div class="ilu-bar"></div>';
    rellenarFigura(f);
    if (!FIGURAS[reg.id]) FIGURAS[reg.id] = f;
    return f;
  }
  function elHueco(reg){
    var d = document.createElement('div'); d.className = 'ilu-hueco'; d.innerHTML = '<span></span>'; d.firstChild.textContent = '✎ ' + reg.texto; return d;
  }

  // ---- cambiar las marcas por lo que representan ----
  function elementoPara(id){
    var reg = REG[id];
    if (!reg) return null;
    if (reg.tipo === 'mate') return elMate(reg.tex, reg.bloque);
    if (reg.tipo === 'hueco') return elHueco(reg);
    return elFigura(reg);
  }
  var MARCA_RE = /\u0002([A-Za-z0-9_-]+)\u0003/;
  function sustituir(tn){
    var partes = tn.nodeValue.split(MARCA_RE);
    if (partes.length === 1) return;
    var frag = document.createDocumentFragment(), bloques = 0, otros = 0;
    partes.forEach(function(s, k){
      if (k % 2 === 0){ if (s.trim()) otros++; if (s) frag.appendChild(document.createTextNode(s)); return; }
      var el = elementoPara(s);
      if (!el) return;
      if (el.nodeName === 'FIGURE' || el.nodeName === 'DIV') bloques++; else otros++;
      frag.appendChild(el);
    });
    var padre = tn.parentNode;
    if (!padre) return;
    if (bloques && !otros && padre.nodeName === 'P' && padre.childNodes.length === 1) padre.parentNode.replaceChild(frag, padre);
    else padre.replaceChild(frag, tn);
  }
  function procesar(nodo){
    if (!nodo) return;
    if (nodo.nodeType === 3){ if (nodo.nodeValue.indexOf('\u0002') >= 0) sustituir(nodo); return; }
    if (nodo.nodeType !== 1 && nodo.nodeType !== 11) return;
    var w = document.createTreeWalker(nodo, NodeFilter.SHOW_TEXT, null), lista = [], n;
    while ((n = w.nextNode())) if (n.nodeValue.indexOf('\u0002') >= 0) lista.push(n);
    lista.forEach(sustituir);
  }
  API.procesar = procesar;
  new MutationObserver(function(ms){
    ms.forEach(function(m){ Array.prototype.forEach.call(m.addedNodes, procesar); });
  }).observe(document.body || document.documentElement, {childList: true, subtree: true});

  // ---- copiar una selección que incluye fórmulas devuelve el LaTeX ----
  function aTexto(nodo){
    var s = '';
    (function ir(n){
      if (n.nodeType === 3){ s += n.nodeValue; return; }
      if (n.nodeType !== 1 && n.nodeType !== 11) return;
      if (n.nodeType === 1){
        if (n.getAttribute('data-tex') != null){ var b = n.getAttribute('data-bloque') === '1', t = n.getAttribute('data-tex'); s += b ? '\n$$\n' + t + '\n$$\n' : '$' + t + '$'; return; }
        if (n.nodeName === 'BUTTON' || n.nodeName === 'STYLE' || n.nodeName === 'SCRIPT' || n.classList.contains('ilu-bar')) return;
        if (n.nodeName === 'BR'){ s += '\n'; return; }
      }
      Array.prototype.forEach.call(n.childNodes, ir);
      if (n.nodeType === 1 && /^(P|DIV|LI|H[1-6]|FIGURE|PRE)$/.test(n.nodeName) && s && !/\n$/.test(s)) s += '\n';
    })(nodo);
    return s.replace(/\n{3,}/g, '\n\n').replace(/^\n+/, '');
  }
  document.addEventListener('copy', function(e){
    var sel = getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount || !e.clipboardData) return;
    var rango = sel.getRangeAt(0), ancla = rango.commonAncestorContainer, base = ancla.nodeType === 1 ? ancla : ancla.parentNode, dentro = base && base.closest ? base.closest('[data-tex]') : null, txt;
    if (dentro){ var b = dentro.getAttribute('data-bloque') === '1', t = dentro.getAttribute('data-tex'); txt = b ? '$$\n' + t + '\n$$' : '$' + t + '$'; }
    else {
      var hay = false, todos = (base && base.querySelectorAll) ? base.querySelectorAll('[data-tex]') : [];
      for (var i = 0; i < todos.length && !hay; i++) hay = sel.containsNode(todos[i], true);
      if (!hay) return;
      txt = aTexto(rango.cloneContents()).trim();
    }
    e.clipboardData.setData('text/plain', txt); e.preventDefault();
  });

  // ---- al cambiar de tema, las figuras se rehacen con los colores nuevos ----
  var firma = '', temporizador = null;
  function revisarTema(){
    PALETA = null;
    var P = paleta(), f = P.modo + P.tinta + P.fondo;
    if (f === firma) return;
    firma = f;
    Array.prototype.forEach.call(document.querySelectorAll('.ilu-fig'), rellenarFigura);
    Object.keys(FIGURAS).forEach(function(k){ if (!FIGURAS[k].isConnected) rellenarFigura(FIGURAS[k]); });
  }
  function vigilar(){ clearTimeout(temporizador); temporizador = setTimeout(revisarTema, 60); }
  new MutationObserver(vigilar).observe(document.documentElement, {attributes: true});
  if (document.body) new MutationObserver(vigilar).observe(document.body, {attributes: true});
  if (RAIZ.matchMedia){ var mq = RAIZ.matchMedia('(prefers-color-scheme: dark)'); if (mq.addEventListener) mq.addEventListener('change', vigilar); }
  firma = (function(){ var P = paleta(); return P.modo + P.tinta + P.fondo; })();
  procesar(document.body);
})();
