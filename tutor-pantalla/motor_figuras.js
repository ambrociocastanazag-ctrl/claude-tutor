/* Motor de figuras matemáticas en SVG: JS puro, sin DOM, sirve en el navegador (window.Figuras) y en node (require).
   Lo comparten el chat de los tutores (ilustraciones_ui.js) y la Tarjeta SVG (tarjeta-svg/). Contrato: tarjeta-svg/CONTRATO.md §1.
     Figuras.estilo                          tokens por tema {claro, oscuro}: TODO lo visual sale de aquí (el diseño los reemplazará)
     Figuras.compilar(expr)                  → f(x): intérprete seguro de expresiones («2x+1», «sin(x)/x»); nunca eval
     Figuras.grafica(spec, opts)             → {svg, w, h} | lanza Error en español.  spec = el JSON de ```grafica
     Figuras.geometria(guion, opts)          → {svg, w, h, errores:[{linea, mensaje}], objetos:[…]}  (con errores dibuja lo válido)
     Figuras.plano(spec, opts)               → {svg, w, h}: solo el plano cartesiano (ejes, rejilla, números)
   opts: {tema:'claro'|'oscuro', tam:'S'|'M'|'L' (320 / 480 / 720 px), ancho:px (manda sobre tam), fondo:'transparente'|'blanco'|'tema'|'#rrggbb',
          paleta:{tinta,suave,fondo,acento,azul…} (colores del panel, para el chat), x:[a,b], y:[c,d] (vista manual de geometría),
          ejes:bool, rejilla:bool (geometría)}.
   El lenguaje de geometría es el de MathStudio (su DOCUMENTACION_PROYECTO.md §8):
   mismos nombres, alias, anidación, atajo AB, nombre obligatorio y orden que importa; el mismo guion se pega allí.  Todo se calcula
   analíticamente; lo que no sabe hacer da un error en su línea, nunca un dibujo equivocado. */
(function(RAIZ){
  'use strict';

  var FUENTE = "'Segoe UI', system-ui, sans-serif";
  var TAM = {S: 320, M: 480, L: 720};
  function tiene(o, k){ return Object.prototype.hasOwnProperty.call(o, k); }

  // =====================================================================================================
  // 0. Estilo (provisional: lo reemplazará el diseño de Claude Design)
  // =====================================================================================================
  var ACENTOS = {
    claro: {azul: '#2a5fd0', verde: '#1d8a4a', rojo: '#d23a3a', naranja: '#d9741a', morado: '#7b45c9', amarillo: '#c9980a'},
    oscuro: {azul: '#6ea1ff', verde: '#4cc47f', rojo: '#ff7f7c', naranja: '#ffa650', morado: '#b68cff', amarillo: '#f2cf50'}
  };
  var BASE = {
    claro: {modo: 'claro', tinta: '#2a2d3a', suave: '#d9d6cc', fondo: '#ffffff', acento: '#4a54c9',
            trazo: '#24344a', derivado: '#2a5fd0', punto: '#c0392b', notacion: '#24344a', relleno: 0.11},
    oscuro: {modo: 'oscuro', tinta: '#ece9e1', suave: '#454a5a', fondo: '#1f2230', acento: '#8fa0ff',
             trazo: '#dfe6f2', derivado: '#6ea1ff', punto: '#ff8a80', notacion: '#dfe6f2', relleno: 0.16}
  };
  var ESTILO = {claro: {}, oscuro: {}};
  ['claro', 'oscuro'].forEach(function(t){ var k; for (k in BASE[t]) ESTILO[t][k] = BASE[t][k]; for (k in ACENTOS[t]) ESTILO[t][k] = ACENTOS[t][k]; });

  function estiloDe(o){                                     // los tokens del tema, con los colores del panel encima si vienen
    o = o || {};
    var P = {}, base = ESTILO[o.tema === 'oscuro' ? 'oscuro' : 'claro'], k, q = o.paleta;
    for (k in base) P[k] = base[k];
    if (q){
      for (k in q) P[k] = q[k];
      if (!q.trazo) P.trazo = q.tinta || P.trazo;
      if (!q.derivado) P.derivado = q.azul || q.acento || P.derivado;
      if (!q.punto) P.punto = q.tinta || P.punto;
      if (!q.notacion) P.notacion = q.tinta || P.notacion;
    }
    return P;
  }
  function anchoDe(o){
    o = o || {};
    if (typeof o.ancho === 'number' && o.ancho >= 160 && o.ancho <= 2400) return Math.round(o.ancho);
    return TAM[String(o.tam || 'M').toUpperCase()] || TAM.M;
  }
  function colorFondo(o, P){
    var f = o && o.fondo;
    if (f === 'blanco') return '#ffffff';
    if (f === 'tema') return P.fondo;
    if (typeof f === 'string' && /^#[0-9a-f]{3,8}$/i.test(f)) return f;
    return '';
  }
  function colorDe(P, nombre, def){
    var n = String(nombre == null ? '' : nombre).trim().toLowerCase();
    if (tiene(P, n) && n !== 'modo' && typeof P[n] === 'string') return P[n];
    if (/^#[0-9a-f]{3,8}$/i.test(n)) return n;
    return def;
  }
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }
  function redondo(v){ return Math.round(v * 10) / 10; }
  function r2(v){ return Math.round(v * 100) / 100; }

  // =====================================================================================================
  // 1. Intérprete de expresiones (tokenizador + parser recursivo → funciones). Nunca eval ni Function.
  // =====================================================================================================
  var FUN = {sqrt: Math.sqrt, cbrt: Math.cbrt, sin: Math.sin, cos: Math.cos, tan: Math.tan, asin: Math.asin, acos: Math.acos, atan: Math.atan,
             exp: Math.exp, ln: Math.log, log: Math.log10, log10: Math.log10, log2: Math.log2, abs: Math.abs, sinh: Math.sinh, cosh: Math.cosh,
             tanh: Math.tanh, floor: Math.floor, ceil: Math.ceil, sign: Math.sign};
  var ALIAS = {sen: 'sin', tg: 'tan', arcsin: 'asin', arccos: 'acos', arctan: 'atan', raiz: 'sqrt', lg: 'log10'};
  var CONST = {pi: Math.PI, e: Math.E, tau: 2 * Math.PI};
  var NOMBRES = Object.keys(FUN).concat(Object.keys(ALIAS), Object.keys(CONST), ['x']).sort(function(a, b){ return b.length - a.length; });

  function normalizar(s){
    return String(s).replace(/[−–—]/g, '-').replace(/[×·]/g, '*').replace(/÷/g, '/').replace(/π/g, ' pi ')
      .replace(/√/g, ' sqrt ').replace(/²/g, '^2').replace(/³/g, '^3').replace(/ /g, ' ')
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
  function conocido(n){ return tiene(FUN, n) || tiene(ALIAS, n) || tiene(CONST, n) || n === 'x'; }
  function tokens(s){
    var t = [], i = 0, m;
    while (i < s.length){
      var rest = s.slice(i), c = s.charAt(i);
      if (/\s/.test(c)){ i++; continue; }
      if ((m = /^(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?/i.exec(rest))){ t.push({k: 'num', v: parseFloat(m[0])}); i += m[0].length; continue; }
      if ((m = /^[A-Za-z_]+\d*/.exec(rest))){
        var id = m[0].toLowerCase();
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
  function compilar(texto, opciones){
    var constante = !!(opciones && opciones.constante);     // constante: «x» es una variable libre y no se acepta (coordenadas)
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
        if (t.v === 'x'){ if (constante) throw new Error('contiene una variable libre (x)'); return function(x){ return x; }; }
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
  // 2. Piezas comunes de dibujo: texto, ticks, recorte
  // =====================================================================================================
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
  function textoSvg(P, x, y, txt, o){                       // <text> con halo del color de fondo (se lee sobre líneas y rejilla)
    o = o || {};
    return '<text x="' + redondo(x) + '" y="' + redondo(y) + '" font-size="' + (o.tam || 11) + '" text-anchor="' + (o.anc || 'middle') + '"' +
      (o.peso ? ' font-weight="' + o.peso + '"' : '') + (o.cur ? ' font-style="italic"' : '') + ' fill="' + (o.col || P.tinta) + '"' +
      (o.halo === false ? '' : ' stroke="' + P.fondo + '" stroke-width="3" stroke-linejoin="round" paint-order="stroke"') + '>' + esc(txt) + '</text>';
  }
  function cabecera(w, h, vb, titulo){
    return '<svg xmlns="http://www.w3.org/2000/svg" width="' + redondo(w) + '" height="' + redondo(h) + '" viewBox="' + vb.map(redondo).join(' ') +
      '" font-family="' + FUENTE + '" role="img"' + (titulo ? ' aria-label="' + esc(titulo) + '"' : '') + '>';
  }
  // Liang–Barsky: parte [u0,u1] del segmento (x0,y0)-(x1,y1) que cae dentro de la caja, o null
  function recortarSegmento(x0, y0, x1, y1, xa, ya, xb, yb){
    var dx = x1 - x0, dy = y1 - y0, p = [-dx, dx, -dy, dy], q = [x0 - xa, xb - x0, y0 - ya, yb - y0], u0 = 0, u1 = 1;
    for (var i = 0; i < 4; i++){
      if (p[i] === 0){ if (q[i] < 0) return null; }
      else {
        var r = q[i] / p[i];
        if (p[i] < 0){ if (r > u1) return null; if (r > u0) u0 = r; }
        else { if (r < u0) return null; if (r < u1) u1 = r; }
      }
    }
    return u0 <= u1 ? [u0, u1] : null;
  }
  function tope(v){ return Math.max(-1e7, Math.min(1e7, v)); }
  function trazoRecortado(pts, caja){                       // polilínea [[x,y],…] en px → «d» de path recortado a la caja [xa,ya,xb,yb]
    var d = '', ult = null;
    for (var i = 1; i < pts.length; i++){
      var a = pts[i - 1], b = pts[i], s = recortarSegmento(tope(a[0]), tope(a[1]), tope(b[0]), tope(b[1]), caja[0], caja[1], caja[2], caja[3]);
      if (!s){ ult = null; continue; }
      var ax = tope(a[0]) + (tope(b[0]) - tope(a[0])) * s[0], ay = tope(a[1]) + (tope(b[1]) - tope(a[1])) * s[0];
      var bx = tope(a[0]) + (tope(b[0]) - tope(a[0])) * s[1], by = tope(a[1]) + (tope(b[1]) - tope(a[1])) * s[1];
      if (!ult || Math.abs(ult[0] - ax) > 1e-6 || Math.abs(ult[1] - ay) > 1e-6) d += 'M' + redondo(ax) + ' ' + redondo(ay);
      d += 'L' + redondo(bx) + ' ' + redondo(by);
      ult = [bx, by];
    }
    return d;
  }

  // =====================================================================================================
  // 3. Gráficas de funciones (y plano cartesiano suelto)
  // =====================================================================================================
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

  function grafica(spec, opts, soloPlano){
    opts = opts || {};
    var P = estiloDe(opts);
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
    if (!soloPlano && !fns.length && !area && !pts.length) throw new Error('falta «funciones»');

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
    var W = anchoDe(opts), titulo = spec.titulo == null ? '' : String(spec.titulo).slice(0, 90), leyenda = fns.filter(function(o){ return o.nombre; });
    var filas = [], fila = [], ancho = 0, maxAncho = W - 30;
    leyenda.forEach(function(o){
      var w = 24 + o.nombre.length * 6.6 + 18;
      if (ancho + w > maxAncho && fila.length){ filas.push(fila); fila = []; ancho = 0; }
      fila.push({o: o, x: ancho, w: w}); ancho += w;
    });
    if (fila.length) filas.push(fila);
    var cab = (titulo ? 26 : 0) + (filas.length ? filas.length * 18 + 4 : 0);
    var px0 = 46, py0 = 14 + cab, pw = W - px0 - 20, ph = Math.round(W * 0.48), H = py0 + ph + 32;
    var caja = [px0, py0, px0 + pw, py0 + ph];
    function sx(x){ return px0 + (x - xa) / (xb - xa) * pw; }
    function sy(y){ return py0 + ph - (y - ya) / (yb - ya) * ph; }
    function cl(v){ return Math.max(py0, Math.min(py0 + ph, v)); }
    var rangoY = yb - ya, S = [];
    var fondo = colorFondo(opts, P);
    S.push(cabecera(W, H, [0, 0, W, H], titulo || (soloPlano ? 'Plano cartesiano' : 'Gráfica')));
    if (titulo) S.push('<title>' + esc(titulo) + '</title>');
    if (fondo) S.push('<rect x="0" y="0" width="' + W + '" height="' + H + '" fill="' + fondo + '"/>');
    if (titulo) S.push(textoSvg(P, px0 - 36, 21, titulo, {anc: 'start', tam: 14, peso: 700, halo: false}));
    filas.forEach(function(f, r){
      var yy = (titulo ? 26 : 0) + 14 + r * 18;
      f.forEach(function(it){
        var x0 = 14 + it.x;
        S.push('<line x1="' + x0 + '" y1="' + (yy - 4) + '" x2="' + (x0 + 16) + '" y2="' + (yy - 4) + '" stroke="' + it.o.color + '" stroke-width="3" stroke-linecap="round"/>', textoSvg(P, x0 + 22, yy, it.o.nombre, {anc: 'start', tam: 12.5, halo: false}));
      });
    });
    // ejes y rejilla
    var piX = esMultiploPi(xa) && esMultiploPi(xb) && (xb - xa) >= Math.PI - 1e-9;
    var tx = piX ? ticksPi(xa, xb) : ticksNum(xa, xb, W < 400 ? 5 : 7), ty = ticksNum(ya, yb, W < 400 ? 4 : 6);
    var ejeY = ya <= 0 && yb >= 0 ? sy(0) : py0 + ph, ejeX = xa <= 0 && xb >= 0 ? sx(0) : px0;
    var rej = [];
    tx.forEach(function(v){ var x = sx(v); rej.push('M' + redondo(x) + ' ' + py0 + 'V' + (py0 + ph)); });
    ty.forEach(function(v){ var y = sy(v); rej.push('M' + px0 + ' ' + redondo(y) + 'H' + (px0 + pw)); });
    S.push('<path d="' + rej.join('') + '" stroke="' + P.suave + '" stroke-width="0.9" fill="none" opacity="0.85"/>',
           '<rect x="' + px0 + '" y="' + py0 + '" width="' + pw + '" height="' + ph + '" fill="none" stroke="' + P.suave + '" stroke-width="1"/>');
    // área sombreada (los y se llevan a los bordes del recuadro: es el recorte exacto de una región entre dos curvas)
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
      if (d) S.push('<path d="' + d + '" fill="' + area.color + '" fill-opacity="0.24" stroke="none"/>');
    }
    // ejes (encima del área, debajo de las curvas)
    S.push('<path d="M' + px0 + ' ' + redondo(ejeY) + 'H' + (px0 + pw) + 'M' + redondo(ejeX) + ' ' + py0 + 'V' + (py0 + ph) + '" stroke="' + P.tinta + '" stroke-width="1.3" fill="none"/>');
    if (soloPlano && spec.flechas !== false){
      S.push('<path d="M' + (px0 + pw) + ' ' + redondo(ejeY) + 'l-9 -4.5v9z" fill="' + P.tinta + '"/><path d="M' + redondo(ejeX) + ' ' + py0 + 'l-4.5 9h9z" fill="' + P.tinta + '"/>');
    }
    var marcas = [];
    tx.forEach(function(v){ var x = sx(v); marcas.push('M' + redondo(x) + ' ' + redondo(ejeY - 3.5) + 'V' + redondo(ejeY + 3.5)); });
    ty.forEach(function(v){ var y = sy(v); marcas.push('M' + redondo(ejeX - 3.5) + ' ' + redondo(y) + 'H' + redondo(ejeX + 3.5)); });
    S.push('<path d="' + marcas.join('') + '" stroke="' + P.tinta + '" stroke-width="1.2" fill="none"/>');
    var ETQ = [];                                           // los números y los nombres de los ejes van encima de las curvas
    var etY = Math.min(ejeY + 15, py0 + ph + 15);
    tx.forEach(function(v){
      var lab = piX ? etiquetaPi(v) : etiquetaNum(v), x = sx(v);
      if (Math.abs(v) < 1e-12 && ejeX > px0 + 1) { ETQ.push(textoSvg(P, x - 6, etY, '0', {anc: 'end'})); return; }
      ETQ.push(textoSvg(P, x, etY, lab));
    });
    ty.forEach(function(v){
      if (Math.abs(v) < 1e-12 && ejeY < py0 + ph - 1 && ejeX > px0 + 1) return;           // el 0 ya está en el eje x
      ETQ.push(textoSvg(P, ejeX - 7, sy(v) + 3.8, etiquetaNum(v), {anc: 'end'}));
    });
    ETQ.push(textoSvg(P, px0 + pw - 4, ejeY - 7, spec.etiquetaX == null ? 'x' : String(spec.etiquetaX).slice(0, 12), {anc: 'end', cur: true, tam: 12.5}),
             textoSvg(P, ejeX + 8, py0 + 12, spec.etiquetaY == null ? 'y' : String(spec.etiquetaY).slice(0, 12), {anc: 'start', cur: true, tam: 12.5}));
    // curvas (recortadas al recuadro a mano: sin clipPath, para que el SVG se vea igual en cualquier sitio)
    var nMuestras = Math.min(1200, Math.round(pw * 1.6));
    fns.forEach(function(o){
      var d2 = corridas(o.fn, xa, xb, nMuestras, rangoY).map(function(r){
        return trazoRecortado(r.map(function(q){ return [sx(q[0]), sy(q[1])]; }), caja);
      }).join('');
      if (d2) S.push('<path d="' + d2 + '" fill="none" stroke="' + o.color + '" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>');
    });
    S.push(ETQ.join(''));
    // puntos
    pts.forEach(function(q){
      if (q.x < xa || q.x > xb || q.y < ya || q.y > yb) return;
      var x = sx(q.x), y = sy(q.y);
      S.push('<circle cx="' + redondo(x) + '" cy="' + redondo(y) + '" r="4.4" fill="' + q.color + '" stroke="' + P.fondo + '" stroke-width="1.6"/>');
      if (q.et){
        var anc = x + 8 + q.et.length * 6.4 > px0 + pw ? 'end' : 'start', ly = y - 9 < py0 + 12 ? y + 17 : y - 9;
        S.push(textoSvg(P, anc === 'end' ? x - 7 : x + 7, ly, q.et, {anc: anc, tam: 12, peso: 600}));
      }
    });
    S.push('</svg>');
    return {svg: S.join(''), w: W, h: H};
  }
  function plano(spec, opts){
    spec = spec || {};
    var s = {}, k;
    for (k in spec) s[k] = spec[k];
    if (s.x == null) s.x = [-5, 5];
    if (s.y == null) s.y = [-5, 5];
    s.funciones = []; delete s.funcion; delete s.area; delete s.puntos;
    return grafica(s, opts, true);
  }

  // =====================================================================================================
  // 4. Geometría: el lenguaje de MathStudio, calculado analíticamente
  // =====================================================================================================
  var EPS = 1e-9;
  function normaV(a){ return Math.hypot(a.x, a.y); }
  function resta(a, b){ return {x: a.x - b.x, y: a.y - b.y}; }
  function suma2(a, b){ return {x: a.x + b.x, y: a.y + b.y}; }
  function mult(a, k){ return {x: a.x * k, y: a.y * k}; }
  function punto2(a, b){ return a.x * b.x + a.y * b.y; }
  function cruz(a, b){ return a.x * b.y - a.y * b.x; }
  function unitario(a){ var n = normaV(a); return {x: a.x / n, y: a.y / n}; }
  function medio(a, b){ return {x: (a.x + b.x) / 2, y: (a.y + b.y) / 2}; }
  function perp(a){ return {x: -a.y, y: a.x}; }
  function P2(v){ return {x: v.x, y: v.y}; }
  function angDe(c, p){ return Math.atan2(p.y - c.y, p.x - c.x); }
  function mod2pi(a){ var t = 2 * Math.PI; a = a % t; return a < 0 ? a + t : a; }
  function cerca(a, b){ return Math.abs(a - b) < 1e-7 * Math.max(1, Math.abs(a), Math.abs(b)); }

  function claveNorm(v){ return v.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase(); }
  var NOMBRE_OK = /^\p{L}[\p{L}\p{N}_]*$/u;
  var DERIVADOS = {mediatriz: 1, bisectriz: 1, altura: 1, mediana: 1, tan: 1, paralela: 1, perpendicular: 1};

  // ---- el catálogo: cada firma dice sus tipos, sus ramas y cómo se calcula (misma tabla que GEO_COMMANDS de MathStudio) ----
  var CMD = {}, INDICE = {};
  function def(clave, alias, firmas, extra){
    var e = {clave: clave, alias: alias, firmas: firmas, fase: 1, clase: 'constructor'}, k;
    if (extra) for (k in extra) e[k] = extra[k];
    CMD[clave] = e;
    [clave].concat(alias).forEach(function(a){ INDICE[claveNorm(a)] = e; });
  }
  function dosDistintos(a, b, que){ if (Math.hypot(a.x - b.x, a.y - b.y) < EPS) throw new Error('Los dos puntos coinciden: no definen ' + que + '.'); }
  function segDe(v){                                        // segmento | par → {a, b}
    return v.tipo === 'par' ? {a: P2(v.a), b: P2(v.b)} : {a: P2(v.a), b: P2(v.b)};
  }
  function linDe(v){                                        // recta | semirrecta | segmento | par → p + t·d con t en [t0, t1]
    if (v.tipo === 'recta') return {p: v.p, d: v.d, t0: -Infinity, t1: Infinity};
    if (v.tipo === 'semirrecta') return {p: v.p, d: v.d, t0: 0, t1: Infinity};
    return {p: v.a, d: resta(v.b, v.a), t0: 0, t1: 1};
  }
  function recta(p, d, ancla){ return {tipo: 'recta', p: P2(p), d: unitario(d), ancla: ancla || [P2(p)]}; }
  function pie(p, lin){                                     // pie de la perpendicular desde p a la recta de lin
    var d = unitario(lin.d), t = punto2(resta(p, lin.p), d);
    return suma2(lin.p, mult(d, t));
  }
  function cortarLineas(l1, l2){
    var den = cruz(l1.d, l2.d);
    if (Math.abs(den) < 1e-12 * normaV(l1.d) * normaV(l2.d)) throw new Error('Las rectas son paralelas: no se cortan en un punto.');
    var w = resta(l2.p, l1.p), t = cruz(w, l2.d) / den, s = cruz(w, l1.d) / den, tol = 1e-9;
    if (t < l1.t0 - tol || t > l1.t1 + tol || s < l2.t0 - tol || s > l2.t1 + tol) throw new Error('Los objetos no se cortan (la intersección cae fuera del segmento o de la semirrecta).');
    return suma2(l1.p, mult(l1.d, t));
  }
  function cortarLineaCirculo(l, c, i){                     // el punto 1 es el de menor t (a lo largo de A→B); en segmentos y semirrectas solo cuentan los que caen dentro
    var f = resta(l.p, c.c), a = punto2(l.d, l.d), b = 2 * punto2(f, l.d), cc = punto2(f, f) - c.r * c.r;
    var disc = b * b - 4 * a * cc, escala = Math.max(b * b, 4 * a * Math.abs(cc), 1e-300);
    if (disc < -1e-9 * escala) throw new Error('No hay intersección: la recta no toca la circunferencia.');
    var raiz = Math.sqrt(Math.max(0, disc)), ts = [(-b - raiz) / (2 * a), (-b + raiz) / (2 * a)];
    if (raiz < 1e-7 * Math.sqrt(escala)) ts = [ts[0], ts[0]];
    var validos = ts.filter(function(t){ return t >= l.t0 - 1e-9 && t <= l.t1 + 1e-9; });
    if (!validos.length) throw new Error('La intersección cae fuera del segmento o de la semirrecta.');
    if (i > validos.length) throw new Error('Solo hay ' + validos.length + ' punto' + (validos.length === 1 ? '' : 's') + ' de intersección dentro del segmento o de la semirrecta (índice ' + validos.length + ' como máximo).');
    return suma2(l.p, mult(l.d, validos[i - 1]));
  }
  function cortarCirculos(c1, c2, i){
    if ((c2.orden || 0) < (c1.orden || 0)){ var t = c1; c1 = c2; c2 = t; }       // GeoGebra no mira el orden de los argumentos sino el de creación
    var d = normaV(resta(c2.c, c1.c));
    if (d < EPS) throw new Error('Las circunferencias son concéntricas: no se cortan.');
    if (d > c1.r + c2.r + 1e-9 || d < Math.abs(c1.r - c2.r) - 1e-9) throw new Error('No hay intersección: las circunferencias no se cortan.');
    var a = (c1.r * c1.r - c2.r * c2.r + d * d) / (2 * d), h = Math.sqrt(Math.max(0, c1.r * c1.r - a * a)), u = unitario(resta(c2.c, c1.c));
    var base = suma2(c1.c, mult(u, a)), n = perp(u);
    if (h < 1e-7) return base;
    return suma2(base, mult(n, (i === 1 ? 1 : -1) * h));    // comprobado contra GeoGebra: el 1 queda a la izquierda de (circunferencia creada antes → creada después)
  }
  function circuncentro(a, b, c){
    var d = 2 * (a.x * (b.y - c.y) + b.x * (c.y - a.y) + c.x * (a.y - b.y));
    if (Math.abs(d) < 1e-9 * Math.max(1, normaV(resta(a, b)) * normaV(resta(a, c)))) throw new Error('Los tres puntos son colineales: no hay circunferencia que pase por ellos.');
    var a2 = a.x * a.x + a.y * a.y, b2 = b.x * b.x + b.y * b.y, c2 = c.x * c.x + c.y * c.y;
    var ux = (a2 * (b.y - c.y) + b2 * (c.y - a.y) + c2 * (a.y - b.y)) / d, uy = (a2 * (c.x - b.x) + b2 * (a.x - c.x) + c2 * (b.x - a.x)) / d;
    return {x: ux, y: uy};
  }
  function tangentesPunto(p, c, i){
    var v = resta(p, c.c), d = normaV(v), tol = 1e-7 * Math.max(1, c.r);
    if (d < c.r - tol) throw new Error('El punto está dentro de la circunferencia: no tiene tangentes.');
    if (Math.abs(d - c.r) <= tol){
      if (i === 2) throw new Error('El punto está sobre la circunferencia: solo hay una tangente (índice 1).');
      var dir = perp(unitario(v));
      return {tipo: 'recta', p: P2(p), d: dir, ancla: [P2(p)]};
    }
    var th = Math.atan2(v.y, v.x), al = Math.acos(c.r / d), sig = i === 1 ? 1 : -1;   // comprobado contra GeoGebra: el 1 toca en th+α (antihorario desde P)
    var T = {x: c.c.x + c.r * Math.cos(th + sig * al), y: c.c.y + c.r * Math.sin(th + sig * al)};
    return {tipo: 'recta', p: P2(T), d: unitario(resta(p, T)), ancla: [P2(T), P2(p)]};
  }
  function tangentesComunes(c1, c2, i){                     // orden comprobado contra GeoGebra (120 casos al azar): exteriores y luego interiores; en cada grupo,
    var dv = resta(c2.c, c1.c), d = normaV(dv);              // primero la que toca c1 a la derecha del eje de centros orientado hacia +x, luego la de la izquierda
    if (d < EPS) throw new Error('Las circunferencias son concéntricas: no tienen tangentes comunes.');
    var u = unitario(dv), n = perp(u), lista = [];
    var ue = (dv.x > 1e-12 || (Math.abs(dv.x) <= 1e-12 && dv.y > 0)) ? u : mult(u, -1);
    [[1, 1], [1, -1]].forEach(function(sg){                 // [σ1, σ2]: iguales = exterior, opuestas = interior
      var a = (sg[1] * c2.r - sg[0] * c1.r) / d;
      if (Math.abs(a) > 1 + 1e-9) return;
      var b = Math.sqrt(Math.max(0, 1 - a * a)), par = [];
      [1, -1].forEach(function(lado){
        var m = suma2(mult(u, a), mult(n, lado * b)), T1 = suma2(c1.c, mult(m, -sg[0] * c1.r));
        par.push({lado: cruz(ue, resta(T1, c1.c)), t: {tipo: 'recta', p: P2(T1), d: unitario(perp(m)), ancla: [P2(T1), suma2(c2.c, mult(m, -sg[1] * c2.r))]}});
      });
      if (b < 1e-9) par.pop();                              // tangente doble
      par.sort(function(p, q){ return p.lado - q.lado; });
      par.forEach(function(q){ lista.push(q.t); });
    });
    if (i > lista.length) throw new Error('Esas circunferencias solo tienen ' + lista.length + ' tangente' + (lista.length === 1 ? '' : 's') + ' en común.');
    return lista[i - 1];
  }

  function pol_area(pts){ var s = 0; for (var i = 0; i < pts.length; i++){ var a = pts[i], b = pts[(i + 1) % pts.length]; s += a.x * b.y - b.x * a.y; } return Math.abs(s) / 2; }
  function pol_perim(pts){ var s = 0; for (var i = 0; i < pts.length; i++) s += normaV(resta(pts[(i + 1) % pts.length], pts[i])); return s; }
  function barrido(c, A, B){ var a0 = angDe(c.c, A), a1 = angDe(c.c, B), sw = mod2pi(a1 - a0); return {a0: a0, sw: sw < 1e-9 ? 2 * Math.PI : sw}; }
  function arcoDe(tipo){
    return function(a){
      var b = barrido(a[0], a[1], a[2]);
      return {tipo: tipo, c: P2(a[0].c), r: a[0].r, a0: b.a0, sw: b.sw};
    };
  }
  function anguloGeoGebra(A, B, C){                         // Angle(A,B,C): de BA a BC en sentido antihorario, en grados (0–360)
    var u = resta(A, B), v = resta(C, B);
    if (normaV(u) < EPS || normaV(v) < EPS) throw new Error('El ángulo no está definido: un extremo coincide con el vértice.');
    return mod2pi(Math.atan2(v.y, v.x) - Math.atan2(u.y, u.x)) * 180 / Math.PI;
  }

  def('segmento', ['segment'], [{params: ['punto', 'punto'], hacer: function(a){ dosDistintos(a[0], a[1], 'un segmento'); return {tipo: 'segmento', a: P2(a[0]), b: P2(a[1])}; }}]);
  def('recta', ['line'], [{params: ['punto', 'punto'], hacer: function(a){ dosDistintos(a[0], a[1], 'una recta'); return recta(a[0], resta(a[1], a[0]), [P2(a[0]), P2(a[1])]); }}]);
  def('semirrecta', ['ray'], [{params: ['punto', 'punto'], hacer: function(a){ dosDistintos(a[0], a[1], 'una semirrecta'); return {tipo: 'semirrecta', p: P2(a[0]), d: unitario(resta(a[1], a[0])), ancla: [P2(a[0]), P2(a[1])]}; }}]);
  def('circunferencia', ['circle'], [
    {params: ['punto', 'numero'], hacer: function(a){ if (!(a[1].v > 0)) throw new Error('El radio tiene que ser positivo.'); return {tipo: 'conica', c: P2(a[0]), r: a[1].v}; }},
    {params: ['punto', 'punto'], hacer: function(a){ dosDistintos(a[0], a[1], 'una circunferencia'); return {tipo: 'conica', c: P2(a[0]), r: normaV(resta(a[1], a[0]))}; }},
    {params: ['punto', 'punto', 'punto'], hacer: function(a){ var c = circuncentro(a[0], a[1], a[2]); return {tipo: 'conica', c: c, r: normaV(resta(a[0], c))}; }}]);
  def('poligono', ['polígono', 'polygon'], [{params: [], rest: 'punto', minimo: 3, hacer: function(a){ return {tipo: 'poligono', pts: a.map(P2)}; }}]);
  def('triangulo', ['triángulo', 'triangle'], [{params: ['punto', 'punto', 'punto'], hacer: function(a){
    if (Math.abs(cruz(resta(a[1], a[0]), resta(a[2], a[0]))) < 1e-9) throw new Error('Los tres puntos son colineales: no forman un triángulo.');
    return {tipo: 'poligono', pts: a.map(P2)}; }}]);
  def('arco', ['arc'], [{params: ['conica', 'punto', 'punto'], hacer: arcoDe('arco')}]);
  def('sector', [], [{params: ['conica', 'punto', 'punto'], hacer: arcoDe('sector')}]);
  def('puntomedio', ['midpoint'], [{params: ['punto', 'punto'], hacer: function(a){ var m = medio(a[0], a[1]); return {tipo: 'punto', x: m.x, y: m.y}; }}]);
  var LIN3 = 'recta|semirrecta|segmento';
  def('interseccion', ['intersección', 'intersect'], [
    {params: [LIN3, LIN3], hacer: function(a){ var p = cortarLineas(linDe(a[0]), linDe(a[1])); return {tipo: 'punto', x: p.x, y: p.y}; }},
    {params: [LIN3 + '|conica', 'conica'], salidas: 'rama', ramas: 2, hacer: function(a, i){
      var p = a[0].tipo === 'conica' ? cortarCirculos(a[0], a[1], i) : cortarLineaCirculo(linDe(a[0]), a[1], i); return {tipo: 'punto', x: p.x, y: p.y}; }},
    {params: ['conica', LIN3 + '|conica'], salidas: 'rama', ramas: 2, hacer: function(a, i){
      var p = a[1].tipo === 'conica' ? cortarCirculos(a[0], a[1], i) : cortarLineaCirculo(linDe(a[1]), a[0], i); return {tipo: 'punto', x: p.x, y: p.y}; }}]);
  def('paralela', ['parallel'], [{params: ['punto', LIN3], hacer: function(a){ var l = linDe(a[1]); return recta(a[0], l.d, [P2(a[0])]); }}]);
  def('perpendicular', [], [{params: ['punto', LIN3], hacer: function(a){ var l = linDe(a[1]); return recta(a[0], perp(l.d), [P2(a[0]), pie(a[0], l)]); }}]);
  def('mediatriz', ['perpendicularbisector'], [{params: ['punto', 'punto'], hacer: function(a){
    dosDistintos(a[0], a[1], 'una mediatriz'); var m = medio(a[0], a[1]); return recta(m, perp(resta(a[1], a[0])), [m]); }}]);
  def('bisectriz', ['anglebisector'], [{params: ['punto', 'punto', 'punto'], hacer: function(a){
    var u = resta(a[0], a[1]), v = resta(a[2], a[1]);
    if (normaV(u) < EPS || normaV(v) < EPS) throw new Error('El ángulo no está definido: un extremo coincide con el vértice.');
    var d = suma2(unitario(u), unitario(v));
    if (normaV(d) < 1e-9) d = perp(u);
    return recta(a[1], d, [P2(a[1])]); }}]);
  def('altura', ['altitude'], [{params: ['punto', 'segmento|par'], hacer: function(a){
    var l = linDe(a[1]); if (normaV(l.d) < EPS) throw new Error('La base de la altura es un solo punto.');
    var f = pie(a[0], l); return recta(f, perp(l.d), [P2(a[0]), f]); }}]);
  def('mediana', ['median'], [{params: ['punto', 'segmento|par'], hacer: function(a){
    var s = segDe(a[1]); return {tipo: 'segmento', a: P2(a[0]), b: medio(s.a, s.b)}; }}]);
  def('tan', ['tangente', 'tangent'], [
    {params: ['punto', 'conica'], salidas: 'rama', ramas: 2, hacer: function(a, i){ return tangentesPunto(a[0], a[1], i); }},
    {params: ['conica', 'conica'], salidas: 'rama', ramas: 4, hacer: function(a, i){ return tangentesComunes(a[0], a[1], i); }}]);
  def('punto', ['point'], [{params: ['recta|semirrecta|segmento|conica|poligono|arco'], hacer: function(){
    throw new Error('«punto(o)» (un punto cualquiera sobre un objeto) no se dibuja aquí: hazlo en MathStudio.'); }}]);
  def('distancia', ['distance'], [{params: ['punto', 'punto'], hacer: function(a){ return {tipo: 'numero', v: normaV(resta(a[0], a[1])), medida: 'distancia', a: P2(a[0]), b: P2(a[1])}; }}]);
  def('angulo', ['ángulo', 'angle'], [{params: ['punto', 'punto', 'punto'], hacer: function(a){
    return {tipo: 'numero', v: anguloGeoGebra(a[0], a[1], a[2]), medida: 'angulo', a: P2(a[0]), b: P2(a[1]), c: P2(a[2])}; }}]);
  def('area', ['área'], [{params: ['poligono|conica|sector'], hacer: function(a){
    var o = a[0], v = o.tipo === 'poligono' ? pol_area(o.pts) : o.tipo === 'conica' ? Math.PI * o.r * o.r : 0.5 * o.r * o.r * o.sw;
    return {tipo: 'numero', v: v, medida: 'area', sobre: o}; }}]);
  def('perimetro', ['perímetro', 'perimeter'], [{params: ['poligono|conica'], hacer: function(a){
    var o = a[0], v = o.tipo === 'poligono' ? pol_perim(o.pts) : 2 * Math.PI * o.r;
    return {tipo: 'numero', v: v, medida: 'perimetro', sobre: o}; }}]);
  var NOT = {clase: 'notacion'};
  def('marcaigual', [], [{params: ['segmento|par', 'numero']}], NOT);
  def('marcaangulo', [], [{params: ['punto', 'punto', 'punto', 'numero']}], NOT);
  def('angulorecto', [], [{params: ['punto', 'punto', 'punto']}], NOT);
  def('marcaparalela', [], [{params: ['segmento|par', 'numero']}], NOT);
  def('etiqueta', [], [{params: ['segmento|par|recta|semirrecta|conica|poligono|arco|sector', 'texto']}], NOT);
  ['baricentro', 'circuncentro', 'incentro', 'ortocentro', 'circunscrita', 'inscrita', 'poligonoregular'].forEach(function(c){ def(c, [], [], {fase: 2}); });

  // ---- análisis de una línea ----
  function partirTop(texto, sep){
    var res = [], ini = 0, prof = 0, cita = false, esc2 = false, i, c;
    for (i = 0; i < texto.length; i++){
      c = texto.charAt(i);
      if (cita){ if (esc2) esc2 = false; else if (c === '\\') esc2 = true; else if (c === '"') cita = false; continue; }
      if (c === '"'){ cita = true; continue; }
      if (c === '(' || c === '{' || c === '[') prof++;
      if (c === ')' || c === '}' || c === ']') prof--;
      if (prof < 0) throw new Error('Delimitadores desequilibrados.');
      if (c === sep && prof === 0){ res.push(texto.slice(ini, i)); ini = i + 1; }
    }
    if (cita) throw new Error('Literal de texto sin comillas de cierre.');
    if (prof !== 0) throw new Error('Delimitadores desequilibrados.');
    res.push(texto.slice(ini));
    return res;
  }
  function literal(src){
    if (src.charAt(0) !== '"') return null;
    if (src.length < 2 || src.charAt(src.length - 1) !== '"') throw new Error('Literal de texto sin comillas de cierre.');
    var v = '';
    for (var i = 1; i < src.length - 1; i++){
      var c = src.charAt(i);
      if (c === '\\'){ var n = src.charAt(i + 1); if (n !== '"' && n !== '\\') throw new Error('Escape no válido en literal de texto.'); v += n; i++; }
      else if (c === '"') throw new Error('Comilla sin escapar dentro del literal de texto.');
      else v += c;
    }
    return {tipo: 'texto', texto: v};
  }
  function coordenada(txt){
    var t = txt.trim();
    try { var v = compilar(t, {constante: true})(0); if (typeof v === 'number' && isFinite(v)) return v; }
    catch (e) { if (/variable libre|no entiendo/.test(e.message)) throw new Error('La coordenada «' + t + '» contiene una variable libre.'); throw new Error('La coordenada «' + t + '» no es válida (' + e.message + ').'); }
    throw new Error('La coordenada «' + t + '» no es un número.');
  }
  function compatible(real, esperado){ return esperado.split('|').indexOf(real) >= 0; }
  function nombresDe(v){ return v.refs || []; }

  function creado(o, E){ o.orden = ++E.n; return o; }
  function evaluar(texto, E, top){
    var src = texto.trim(), s = literal(src);
    if (s) return s;
    if (src.charAt(0) === '('){
      if (src.charAt(src.length - 1) !== ')') throw new Error('Delimitadores desequilibrados.');
      var cs = partirTop(src.slice(1, -1), ',');
      if (cs.length !== 2) throw new Error('Un punto necesita dos coordenadas.');
      return creado({tipo: 'punto', x: coordenada(cs[0]), y: coordenada(cs[1]), refs: []}, E);
    }
    var m = /^([\p{L}_][\p{L}\p{N}_]*)\s*\(([\s\S]*)\)$/u.exec(src);
    if (m) return llamar(m[1], m[2], E, top);
    if (/^[\p{L}\p{N}_]+$/u.test(src)){
      if (tiene(E.simbolos, src)){ var v = E.simbolos[src], c = {}, k; for (k in v) c[k] = v[k]; c.refs = [src]; return c; }
      if (tiene(E.fallidos, src)) throw new Error('«' + src + '» no se pudo construir (error en la línea ' + E.fallidos[src] + ').');
      var chars = Array.from(src);
      if (chars.length === 2 && chars.every(function(x){ return tiene(E.simbolos, x) && E.simbolos[x].tipo === 'punto'; }))
        return {tipo: 'par', a: E.simbolos[chars[0]], b: E.simbolos[chars[1]], refs: chars};
      if (/^\d+(?:\.\d+)?$/.test(src)) return {tipo: 'numero', v: parseFloat(src), refs: []};
      try { var n = compilar(src, {constante: true})(0); if (typeof n === 'number' && isFinite(n)) return {tipo: 'numero', v: n, refs: []}; } catch (e) { /* cae al error de abajo */ }
      throw new Error('Referencia adelantada o desconocida: «' + src + '».');
    }
    try { var n2 = compilar(src, {constante: true})(0); if (typeof n2 === 'number' && isFinite(n2)) return {tipo: 'numero', v: n2, refs: []}; } catch (e2) { /* error de abajo */ }
    throw new Error('Expresión no válida o delimitadores desequilibrados.');
  }
  function llamar(nombre, crudo, E, top){
    var cmd = INDICE[claveNorm(nombre)];
    if (!cmd) throw new Error('El comando «' + nombre + '» no está en GEO_COMMANDS (no existe en MathStudio ni aquí).');
    if (cmd.clase !== 'notacion' && (cmd.fase !== 1 || !cmd.firmas.length)) throw new Error('«' + cmd.clave + '» está reservado para la Fase 2: esto, en MathStudio todavía no existe.');
    var rawArgs = crudo.trim() ? partirTop(crudo, ',') : [], elegida = null, args = null, idx = null, fallos = [];
    for (var f = 0; f < cmd.firmas.length; f++){
      var fi = cmd.firmas[f], cand = rawArgs.slice(), indice = null;
      if (fi.salidas === 'rama' && cand.length && /^\d+$/.test(cand[cand.length - 1].trim())){ indice = +cand[cand.length - 1].trim(); cand = cand.slice(0, -1); }
      var minimo = fi.rest ? fi.minimo : fi.params.length;
      if ((!fi.rest && cand.length !== fi.params.length) || (fi.rest && cand.length < minimo)){ fallos.push('aridad'); continue; }
      try {
        var parsed = cand.map(function(a){ return evaluar(a, E, false); }), bad = -1, esp;
        for (var j = 0; j < parsed.length; j++){ esp = fi.params[j] || fi.rest; if (!compatible(parsed[j].tipo, esp)){ bad = j; break; } }
        if (bad >= 0) throw new Error('El argumento ' + (bad + 1) + ' espera ' + (fi.params[bad] || fi.rest) + '; recibió ' + parsed[bad].tipo + '.');
        if (fi.salidas === 'rama'){
          if (indice == null) throw new Error('«' + cmd.clave + '» tiene ' + fi.ramas + ' ramas; indica un índice.');
          if (indice < 1 || indice > fi.ramas) throw new Error('El índice debe estar entre 1 y ' + fi.ramas + '.');
        }
        elegida = fi; args = parsed; idx = indice; break;
      } catch (e) { fallos.push(e.message); }
    }
    if (!elegida){
      var esp2 = null;
      fallos.forEach(function(x){ if (!esp2 && /ramas.*índice/i.test(x)) esp2 = x; });
      fallos.forEach(function(x){ if (!esp2 && x !== 'aridad') esp2 = x; });
      throw new Error(esp2 || '«' + cmd.clave + '» recibió una aridad incorrecta.');
    }
    var refs = [];
    args.forEach(function(a){ nombresDe(a).forEach(function(n){ if (refs.indexOf(n) < 0) refs.push(n); }); });
    if (cmd.clase === 'notacion') return {tipo: 'notacion', clave: cmd.clave, args: args, refs: refs};
    var obj = creado(elegida.hacer(args, idx), E);
    obj.refs = refs;
    if (DERIVADOS[cmd.clave]) obj.derivado = true;
    return obj;
  }

  function analizar(guion){
    var E = {simbolos: {}, fallidos: {}, n: 0}, errores = [], objetos = [], notaciones = [];
    String(guion == null ? '' : guion).split(/\r?\n/).forEach(function(crudo, k){
      var linea = k + 1, texto = crudo.trim();
      if (!texto) return;
      try {
        var iguales = partirTop(texto, '=');
        if (iguales.length === 1){
          var cab = /^([\p{L}_][\p{L}\p{N}_]*)\s*\(/u.exec(texto), cmd = cab ? INDICE[claveNorm(cab[1])] : null;
          if (!cmd || cmd.clase !== 'notacion') throw new Error('Toda línea necesita un nombre y el signo =.');
          var nt = evaluar(texto, E, true);
          if (nt.tipo !== 'notacion') throw new Error('Toda construcción necesita un nombre y el signo =.');
          validarNotacion(nt);
          nt.linea = linea;
          notaciones.push(nt);
          return;
        }
        if (iguales.length !== 2) throw new Error('La línea contiene más de un signo =.');
        var nombre = iguales[0].trim();
        if (!NOMBRE_OK.test(nombre)) throw new Error('El nombre debe comenzar con una letra y usar letras, números o _.');
        if (tiene(E.simbolos, nombre)) throw new Error('El nombre «' + nombre + '» está repetido.');
        var expr = iguales[1].trim().replace(/\s+fijo$/u, '');
        var v = evaluar(expr, E, true);
        if (v.tipo === 'notacion') throw new Error('Las notaciones no llevan nombre ni signo =.');
        if (v.tipo === 'texto') throw new Error('Un texto solo se usa dentro de etiqueta(…).');
        if (v.tipo === 'par') throw new Error('Un par de puntos (AB) es un atajo de segmento: usa segmento(A,B) para darle nombre.');
        v.nombre = nombre; v.linea = linea;
        E.simbolos[nombre] = v;
        objetos.push(v);
      } catch (e) {
        errores.push({linea: linea, mensaje: e.message});
        var nm = /^\s*([\p{L}_][\p{L}\p{N}_]*)\s*=/u.exec(crudo);
        if (nm && !tiene(E.simbolos, nm[1])) E.fallidos[nm[1]] = linea;
      }
    });
    return {objetos: objetos, notaciones: notaciones, errores: errores};
  }
  function validarNotacion(nt){
    var a = nt.args, g;
    if (nt.clave === 'marcaigual' || nt.clave === 'marcaangulo' || nt.clave === 'marcaparalela'){
      g = a[a.length - 1].v;
      if (!(Number.isInteger(g) && g >= 1)) throw new Error('El índice de grupo debe ser un entero positivo.');
      nt.grupo = g;
    }
    if (nt.clave === 'etiqueta'){
      if (a[0].tipo !== 'segmento' && a[0].tipo !== 'par') throw new Error('La etiqueta solo se coloca sobre un segmento o un par de puntos (por ejemplo AB): en MathStudio tampoco se dibuja sobre otros objetos.');
      nt.texto = a[1].texto;
    }
    if (nt.clave === 'marcaigual' || nt.clave === 'marcaparalela' || nt.clave === 'etiqueta'){
      var s = segDe(a[0]); if (normaV(resta(s.b, s.a)) < EPS) throw new Error('Segmento degenerado: no se puede marcar.');
    } else {
      var p = a.slice(0, 3);
      if (normaV(resta(p[0], p[1])) < EPS || normaV(resta(p[1], p[2])) < EPS) throw new Error('Ángulo degenerado: un extremo coincide con el vértice.');
      if (nt.clave === 'angulorecto'){
        var u = unitario(resta(p[0], p[1])), v = unitario(resta(p[2], p[1])), cosA = punto2(u, v);
        if (Math.abs(cosA) > 0.0175) throw new Error('El ángulo no es recto (mide ' + r2(Math.acos(cosA) * 180 / Math.PI) + '°): no se dibuja el cuadradito.');   // 1° de tolerancia
      }
    }
  }

  // ---- extensión de cada objeto (para encajar la vista) ----
  function puntosDe(o){
    switch (o.tipo){
      case 'punto': return [o];
      case 'segmento': return [o.a, o.b];
      case 'recta': case 'semirrecta': return o.ancla || [o.p];
      case 'poligono': return o.pts;
      case 'conica': return [{x: o.c.x - o.r, y: o.c.y - o.r}, {x: o.c.x + o.r, y: o.c.y + o.r}];
      case 'arco': case 'sector':
        var L = [pEn(o, o.a0), pEn(o, o.a0 + o.sw)], cuartos = [0, 1, 2, 3];
        cuartos.forEach(function(q){ var a = q * Math.PI / 2; if (mod2pi(a - o.a0) <= o.sw) L.push(pEn(o, a)); });
        if (o.tipo === 'sector') L.push(o.c);
        return L;
      default: return [];
    }
  }
  function pEn(o, a){ return {x: o.c.x + o.r * Math.cos(a), y: o.c.y + o.r * Math.sin(a)}; }

  function formatoNum(v){ var s = String(r2(v)); return s; }

  function geometria(guion, opts){
    opts = opts || {};
    var P = estiloDe(opts), an = analizar(guion), objs = an.objetos, nots = an.notaciones;
    var dibujables = objs.filter(function(o){ return o.tipo !== 'numero'; });
    var salidaObjetos = objs.map(function(o){ var c = {}, k; for (k in o) c[k] = o[k]; return c; });
    var vacio = {svg: '', w: 0, h: 0, errores: an.errores, objetos: salidaObjetos};
    if (!dibujables.length && !objs.length) return vacio;

    // ---- vista: la que pide el usuario o la que deja entrar todo con margen ----
    var W = anchoDe(opts), M = 34, xs = [], ys = [];
    dibujables.forEach(function(o){ puntosDe(o).forEach(function(p){ xs.push(p.x); ys.push(p.y); }); });
    objs.forEach(function(o){ if (o.tipo === 'numero' && o.medida === 'angulo'){ [o.a, o.b, o.c].forEach(function(p){ xs.push(p.x); ys.push(p.y); }); } if (o.tipo === 'numero' && o.medida === 'distancia'){ [o.a, o.b].forEach(function(p){ xs.push(p.x); ys.push(p.y); }); } });
    var manual = !!(opts.x || opts.y);
    if (!xs.length){ xs = [-1, 1]; ys = [-1, 1]; }
    var xmin = Math.min.apply(null, xs), xmax = Math.max.apply(null, xs), ymin = Math.min.apply(null, ys), ymax = Math.max.apply(null, ys);
    if (opts.x && opts.x.length === 2 && opts.x[0] < opts.x[1]){ xmin = opts.x[0]; xmax = opts.x[1]; }
    if (opts.y && opts.y.length === 2 && opts.y[0] < opts.y[1]){ ymin = opts.y[0]; ymax = opts.y[1]; }
    var bw = xmax - xmin, bh = ymax - ymin;
    if (bw < 1e-9 && bh < 1e-9){ bw = bh = 2; xmin -= 1; xmax += 1; ymin -= 1; ymax += 1; }
    else {
      if (bw < 1e-9){ bw = bh * 0.5; xmin -= bw / 2; xmax += bw / 2; }
      if (bh < 1e-9){ bh = bw * 0.5; ymin -= bh / 2; ymax += bh / 2; }
    }
    var s = (W - 2 * M) / bw, H = bh * s + 2 * M, Hmax = W * 1.15, Hmin = W * 0.34;
    if (!manual && H > Hmax){ s = (Hmax - 2 * M) / bh; H = Hmax; }
    if (H < Hmin) H = Hmin;
    var ox = (W - bw * s) / 2 - xmin * s, oy = (H - bh * s) / 2 + ymax * s;
    function sx(x){ return ox + x * s; }
    function sy(y){ return oy - y * s; }
    function pp(p){ return [sx(p.x), sy(p.y)]; }
    var caja = [10, 10, W - 10, H - 10];                    // las rectas se recortan aquí
    var cajaVista = [sx(xmin), sy(ymax), sx(xmax), sy(ymin)];

    var capaRelleno = [], capaTrazo = [], capaDeriv = [], capaMarca = [], capaPuntos = [], capaTexto = [], capaFondo = [];
    var obst = [], cajasTxt = [], dots = [], extra = {x0: 0, y0: 0, x1: W, y1: H};
    function muestrear(pts){                                // puntos cada ~5 px a lo largo de una polilínea
      for (var i = 1; i < pts.length; i++){
        var a = pts[i - 1], b = pts[i], n = Math.max(1, Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1]) / 5));
        for (var k = 0; k <= n; k++) obst.push([a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n]);
      }
    }
    function estiloTrazo(o, grueso){ return ' fill="none" stroke="' + (o.derivado ? P.derivado : P.trazo) + '" stroke-width="' + (grueso || (o.derivado ? 1.7 : 2.1)) + '" stroke-linecap="round" stroke-linejoin="round"'; }
    function arcoPx(c, r, a0, sw, mover){                   // arco del círculo (centro/radio en math) como tramo de path en px
      var p0 = pEn({c: c, r: r}, a0), p1 = pEn({c: c, r: r}, a0 + sw), q0 = pp(p0), q1 = pp(p1), R = r * s;
      return (mover ? 'M' : 'L') + redondo(q0[0]) + ' ' + redondo(q0[1]) + 'A' + redondo(R) + ' ' + redondo(R) + ' 0 ' + (sw > Math.PI ? 1 : 0) + ' 0 ' + redondo(q1[0]) + ' ' + redondo(q1[1]);
    }
    function muestrearArco(c, r, a0, sw){
      var n = Math.max(8, Math.ceil(sw * r * s / 5)), L = [];
      for (var i = 0; i <= n; i++) L.push(pp(pEn({c: c, r: r}, a0 + sw * i / n)));
      muestrear(L);
    }

    // ---- ejes y rejilla opcionales ----
    if (opts.ejes || opts.rejilla){
      var gx = ticksNum(xmin, xmax, 7), gy = ticksNum(ymin, ymax, 6), gd = [];
      if (opts.rejilla){
        gx.forEach(function(v){ gd.push('M' + redondo(sx(v)) + ' ' + redondo(cajaVista[1]) + 'V' + redondo(cajaVista[3])); });
        gy.forEach(function(v){ gd.push('M' + redondo(cajaVista[0]) + ' ' + redondo(sy(v)) + 'H' + redondo(cajaVista[2])); });
        capaFondo.push('<path d="' + gd.join('') + '" stroke="' + P.suave + '" stroke-width="0.9" fill="none" opacity="0.85"/>');
      }
      if (opts.ejes){
        var ey = ymin <= 0 && ymax >= 0 ? sy(0) : cajaVista[3], ex = xmin <= 0 && xmax >= 0 ? sx(0) : cajaVista[0];
        capaFondo.push('<path d="M' + redondo(cajaVista[0]) + ' ' + redondo(ey) + 'H' + redondo(cajaVista[2]) + 'M' + redondo(ex) + ' ' + redondo(cajaVista[1]) + 'V' + redondo(cajaVista[3]) + '" stroke="' + P.tinta + '" stroke-width="1.2" fill="none"/>');
        gx.forEach(function(v){ if (Math.abs(v) > 1e-12) capaFondo.push(textoSvg(P, sx(v), Math.min(ey + 15, cajaVista[3] + 15), etiquetaNum(v), {tam: 10.5})); });
        gy.forEach(function(v){ if (Math.abs(v) > 1e-12) capaFondo.push(textoSvg(P, ex - 6, sy(v) + 3.6, etiquetaNum(v), {tam: 10.5, anc: 'end'})); });
      }
    }

    // ---- trazos ----
    dibujables.forEach(function(o){
      var L = o.derivado ? capaDeriv : capaTrazo, d, q;
      switch (o.tipo){
        case 'segmento': {
          var a = pp(o.a), b = pp(o.b);
          L.push('<path d="M' + redondo(a[0]) + ' ' + redondo(a[1]) + 'L' + redondo(b[0]) + ' ' + redondo(b[1]) + '"' + estiloTrazo(o) + '/>');
          muestrear([a, b]); break;
        }
        case 'recta': case 'semirrecta': {
          var p0 = pp(o.p), dd = [o.d.x, -o.d.y], LL = 1e5, a2 = o.tipo === 'recta' ? [p0[0] - dd[0] * LL, p0[1] - dd[1] * LL] : p0, b2 = [p0[0] + dd[0] * LL, p0[1] + dd[1] * LL];
          d = trazoRecortado([a2, b2], caja);
          if (d){ L.push('<path d="' + d + '"' + estiloTrazo(o) + '/>');
            var sg = recortarSegmento(a2[0], a2[1], b2[0], b2[1], caja[0], caja[1], caja[2], caja[3]);
            if (sg) muestrear([[a2[0] + (b2[0] - a2[0]) * sg[0], a2[1] + (b2[1] - a2[1]) * sg[0]], [a2[0] + (b2[0] - a2[0]) * sg[1], a2[1] + (b2[1] - a2[1]) * sg[1]]]); }
          break;
        }
        case 'poligono': {
          q = o.pts.map(pp);
          d = 'M' + q.map(function(v){ return redondo(v[0]) + ' ' + redondo(v[1]); }).join('L') + 'Z';
          capaRelleno.push('<path d="' + d + '" fill="' + P.derivado + '" fill-opacity="' + P.relleno + '" stroke="none"/>');
          L.push('<path d="' + d + '"' + estiloTrazo(o) + '/>');
          muestrear(q.concat([q[0]])); break;
        }
        case 'conica': {
          var c = pp(o.c);
          L.push('<circle cx="' + redondo(c[0]) + '" cy="' + redondo(c[1]) + '" r="' + redondo(o.r * s) + '"' + estiloTrazo(o) + '/>');
          muestrearArco(o.c, o.r, 0, 2 * Math.PI); break;
        }
        case 'arco': {
          L.push('<path d="' + arcoPx(o.c, o.r, o.a0, o.sw, true) + '"' + estiloTrazo(o) + '/>');
          muestrearArco(o.c, o.r, o.a0, o.sw); break;
        }
        case 'sector': {
          var cc = pp(o.c);
          d = 'M' + redondo(cc[0]) + ' ' + redondo(cc[1]) + arcoPx(o.c, o.r, o.a0, o.sw, false) + 'Z';
          capaRelleno.push('<path d="' + d + '" fill="' + P.derivado + '" fill-opacity="' + (P.relleno * 1.3) + '" stroke="none"/>');
          L.push('<path d="' + d + '"' + estiloTrazo(o) + '/>');
          muestrear([cc, pp(pEn(o, o.a0))]); muestrear([cc, pp(pEn(o, o.a0 + o.sw))]); muestrearArco(o.c, o.r, o.a0, o.sw); break;
        }
      }
    });

    // ---- colocación de rótulos sin pisar trazos, puntos ni otros rótulos ----
    function chocaCajas(c, w, h, infl){
      var n = 0;
      cajasTxt.forEach(function(b){ if (c[0] - w / 2 - infl < b.x1 && c[0] + w / 2 + infl > b.x0 && c[1] - h / 2 - infl < b.y1 && c[1] + h / 2 + infl > b.y0) n++; });
      return n;
    }
    function ubicar(anc, w, h, pref, sep, centro){
      var mejor = null, k, cand = [];
      if (centro) cand.push({dx: 0, dy: 0, k: 0});
      for (k = 0; k < 16; k++){
        var ang = pref + (k % 2 ? 1 : -1) * Math.ceil(k / 2) * (Math.PI / 8), dir = [Math.cos(ang), Math.sin(ang)];
        var sup = (w / 2) * Math.abs(dir[0]) + (h / 2) * Math.abs(dir[1]);
        cand.push({dx: dir[0] * (sep + sup), dy: dir[1] * (sep + sup), k: k + 1});
      }
      cand.forEach(function(q){
        var c = [anc[0] + q.dx, anc[1] + q.dy], pena = q.k * 0.35, i;
        for (i = 0; i < obst.length; i++) if (Math.abs(obst[i][0] - c[0]) < w / 2 + 3 && Math.abs(obst[i][1] - c[1]) < h / 2 + 3) pena += 4;
        for (i = 0; i < dots.length; i++) if (Math.abs(dots[i][0] - c[0]) < w / 2 + 5 && Math.abs(dots[i][1] - c[1]) < h / 2 + 5) pena += 30;
        pena += chocaCajas(c, w, h, 2) * 60;
        if (c[0] - w / 2 < 2 || c[0] + w / 2 > W - 2 || c[1] - h / 2 < 2 || c[1] + h / 2 > H - 2) pena += 6;
        if (!mejor || pena < mejor.pena) mejor = {pena: pena, c: c};
      });
      cajasTxt.push({x0: mejor.c[0] - w / 2, x1: mejor.c[0] + w / 2, y0: mejor.c[1] - h / 2, y1: mejor.c[1] + h / 2});
      extra.x0 = Math.min(extra.x0, mejor.c[0] - w / 2 - 6); extra.x1 = Math.max(extra.x1, mejor.c[0] + w / 2 + 6);
      extra.y0 = Math.min(extra.y0, mejor.c[1] - h / 2 - 6); extra.y1 = Math.max(extra.y1, mejor.c[1] + h / 2 + 6);
      return mejor.c;
    }
    function ancho(txt, tam){ return Array.from(txt).length * tam * 0.58 + 2; }

    // ---- notaciones (marcas de MathStudio: geo-notacion.js, en píxeles) ----
    var colN = P.notacion, estN = ' fill="none" stroke="' + colN + '" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"';
    nots.forEach(function(nt){
      var a = nt.args;
      if (nt.clave === 'marcaigual' || nt.clave === 'marcaparalela' || nt.clave === 'etiqueta'){
        var sg = segDe(a[0]), A = pp(sg.a), B = pp(sg.b), dx = B[0] - A[0], dy = B[1] - A[1], tam = Math.hypot(dx, dy), ux = dx / tam, uy = dy / tam, nx = -uy, ny = ux, mx = (A[0] + B[0]) / 2, my = (A[1] + B[1]) / 2;
        if (nt.clave === 'marcaigual'){
          var cu = Math.max(1, Math.min(3, nt.grupo));
          for (var i = 0; i < cu; i++){ var off = (i - (cu - 1) / 2) * 6, cx = mx + ux * off, cy = my + uy * off;
            capaMarca.push('<path d="M' + redondo(cx - nx * 6) + ' ' + redondo(cy - ny * 6) + 'L' + redondo(cx + nx * 6) + ' ' + redondo(cy + ny * 6) + '"' + estN + '/>'); }
        } else if (nt.clave === 'marcaparalela'){
          var cp = Math.max(1, Math.min(3, nt.grupo));
          for (var j = 0; j < cp; j++){ var of2 = (j - (cp - 1) / 2) * 9, cx2 = mx + ux * of2, cy2 = my + uy * of2;
            capaMarca.push('<path d="M' + redondo(cx2 - ux * 7 - nx * 5) + ' ' + redondo(cy2 - uy * 7 - ny * 5) + 'L' + redondo(cx2) + ' ' + redondo(cy2) + 'L' + redondo(cx2 - ux * 7 + nx * 5) + ' ' + redondo(cy2 - uy * 7 + ny * 5) + '"' + estN + '/>'); }
        } else {
          var tx = nt.texto == null ? '' : nt.texto, w = ancho(tx, 13.5), cT = [mx - uy * 12, my + ux * 12];
          // lado del trazo: el que menos choca con otros rótulos (se prueba el otro si el primero está ocupado)
          var alt = [mx + uy * 12, my - ux * 12];
          if (chocaCajas(cT, w, 16, 2) && !chocaCajas(alt, w, 16, 2)) cT = alt;
          cajasTxt.push({x0: cT[0] - w / 2, x1: cT[0] + w / 2, y0: cT[1] - 8, y1: cT[1] + 8});
          extra.x0 = Math.min(extra.x0, cT[0] - w / 2 - 6); extra.x1 = Math.max(extra.x1, cT[0] + w / 2 + 6); extra.y0 = Math.min(extra.y0, cT[1] - 14); extra.y1 = Math.max(extra.y1, cT[1] + 14);
          capaTexto.push(textoSvg(P, cT[0], cT[1] + 5, tx, {tam: 13.5, peso: 600, col: colN}));
        }
      } else {
        var V = pp(a[1]), A2 = pp(a[0]), C2 = pp(a[2]);
        if (nt.clave === 'marcaangulo'){
          var st = Math.atan2(A2[1] - V[1], A2[0] - V[0]), en = Math.atan2(C2[1] - V[1], C2[0] - V[0]), dl = en - st;
          while (dl <= -Math.PI) dl += 2 * Math.PI; while (dl > Math.PI) dl -= 2 * Math.PI;
          var cn = Math.max(1, Math.min(3, nt.grupo));
          for (var m = 0; m < cn; m++){ var rad = 18 + m * 6, q1 = [V[0] + Math.cos(st) * rad, V[1] + Math.sin(st) * rad], q2 = [V[0] + Math.cos(st + dl) * rad, V[1] + Math.sin(st + dl) * rad];
            capaMarca.push('<path d="M' + redondo(q1[0]) + ' ' + redondo(q1[1]) + 'A' + rad + ' ' + rad + ' 0 0 ' + (dl > 0 ? 1 : 0) + ' ' + redondo(q2[0]) + ' ' + redondo(q2[1]) + '"' + estN + '/>'); }
        } else {                                            // angulorecto: el cuadradito en el vértice (el segundo punto)
          var nu = function(F){ var ddx = F[0] - V[0], ddy = F[1] - V[1], zz = Math.hypot(ddx, ddy); return [ddx / zz, ddy / zz]; }, u1 = nu(A2), v1 = nu(C2), z = 15;
          var r1 = [V[0] + u1[0] * z, V[1] + u1[1] * z], r2p = [r1[0] + v1[0] * z, r1[1] + v1[1] * z], r3 = [V[0] + v1[0] * z, V[1] + v1[1] * z];
          capaMarca.push('<path d="M' + redondo(r1[0]) + ' ' + redondo(r1[1]) + 'L' + redondo(r2p[0]) + ' ' + redondo(r2p[1]) + 'L' + redondo(r3[0]) + ' ' + redondo(r3[1]) + '"' + estN + '/>');
        }
      }
    });

    // ---- puntos y sus nombres ----
    var puntos = dibujables.filter(function(o){ return o.tipo === 'punto'; });
    puntos.forEach(function(o){ dots.push(pp(o)); });
    var cen = [0, 0];
    if (puntos.length){ puntos.forEach(function(o){ var q = pp(o); cen[0] += q[0] / puntos.length; cen[1] += q[1] / puntos.length; }); }
    else { cen = [W / 2, H / 2]; }
    puntos.forEach(function(o){
      var q = pp(o);
      capaPuntos.push('<circle cx="' + redondo(q[0]) + '" cy="' + redondo(q[1]) + '" r="3.8" fill="' + P.punto + '" stroke="' + P.fondo + '" stroke-width="1.4"/>');
    });
    puntos.forEach(function(o){
      var q = pp(o), pref = Math.atan2(q[1] - cen[1], q[0] - cen[0]);
      if (Math.hypot(q[0] - cen[0], q[1] - cen[1]) < 1) pref = -Math.PI / 4;
      var w = ancho(o.nombre, 15), c = ubicar(q, w, 17, pref, 6);
      capaTexto.push(textoSvg(P, c[0], c[1] + 5, o.nombre, {tam: 15, peso: 600, cur: false}));
    });

    // ---- medidas: «nombre = valor» junto a lo que miden ----
    var pilaCentro = {};
    objs.forEach(function(o){
      if (o.tipo !== 'numero' || !o.medida) return;
      var etq, anc, pref = 0, w, c;
      if (o.medida === 'distancia'){
        etq = o.nombre + ' = ' + formatoNum(o.v); var A = pp(o.a), B = pp(o.b), mx = (A[0] + B[0]) / 2, my = (A[1] + B[1]) / 2, nx = -(B[1] - A[1]), ny = B[0] - A[0], zz = Math.hypot(nx, ny) || 1;
        nx /= zz; ny /= zz; if ((mx - cen[0]) * nx + (my - cen[1]) * ny < 0){ nx = -nx; ny = -ny; }
        pref = Math.atan2(ny, nx); w = ancho(etq, 13.5); c = ubicar([mx, my], w, 16, pref, 6);
      } else if (o.medida === 'angulo'){
        etq = o.nombre + ' = ' + formatoNum(o.v) + '°';
        var V = pp(o.b), a0 = angDe(o.b, o.a), sw = o.v * Math.PI / 180, rad = 24, p0 = pp({x: o.b.x + rad / s * Math.cos(a0), y: o.b.y + rad / s * Math.sin(a0)}), p1 = pp({x: o.b.x + rad / s * Math.cos(a0 + sw), y: o.b.y + rad / s * Math.sin(a0 + sw)});
        capaMarca.push('<path d="M' + redondo(p0[0]) + ' ' + redondo(p0[1]) + 'A' + rad + ' ' + rad + ' 0 ' + (sw > Math.PI ? 1 : 0) + ' 0 ' + redondo(p1[0]) + ' ' + redondo(p1[1]) + '" fill="none" stroke="' + P.punto + '" stroke-width="1.8" stroke-linecap="round"/>');
        var mid = a0 + sw / 2; w = ancho(etq, 13.5);
        c = ubicar([V[0] + Math.cos(mid) * (rad + 2), V[1] - Math.sin(mid) * (rad + 2)], w, 16, Math.atan2(-Math.sin(mid), Math.cos(mid)), 4);
      } else {
        var base = o.sobre, cx0, cy0;
        etq = o.nombre + ' = ' + formatoNum(o.v);
        if (base.tipo === 'poligono'){ var qs = base.pts.map(pp); cx0 = qs.reduce(function(t, v){ return t + v[0]; }, 0) / qs.length; cy0 = qs.reduce(function(t, v){ return t + v[1]; }, 0) / qs.length; }
        else { var cq = pp(base.c); cx0 = cq[0]; cy0 = cq[1]; if (base.tipo === 'sector'){ var mm = base.a0 + base.sw / 2; cx0 += Math.cos(mm) * base.r * s * 0.5; cy0 -= Math.sin(mm) * base.r * s * 0.5; } }
        var key = Math.round(cx0) + ',' + Math.round(cy0), n = pilaCentro[key] || 0; pilaCentro[key] = n + 1;
        w = ancho(etq, 13.5); c = ubicar([cx0, cy0 + n * 18], w, 16, Math.PI / 2, 4, true);
      }
      capaTexto.push(textoSvg(P, c[0], c[1] + 5, etq, {tam: 13.5, peso: 600, col: P.punto}));
    });

    // ---- ensamblado: el viewBox crece lo que haga falta para que nada quede pegado al borde ----
    var vb = [Math.min(0, extra.x0), Math.min(0, extra.y0), 0, 0];
    vb[2] = Math.max(W, extra.x1) - vb[0]; vb[3] = Math.max(H, extra.y1) - vb[1];
    var fondo = colorFondo(opts, P), S = [cabecera(vb[2], vb[3], vb, 'Figura de geometría')];
    if (fondo) S.push('<rect x="' + redondo(vb[0]) + '" y="' + redondo(vb[1]) + '" width="' + redondo(vb[2]) + '" height="' + redondo(vb[3]) + '" fill="' + fondo + '"/>');
    var cuerpo = capaFondo.concat(capaRelleno, capaTrazo, capaDeriv, capaMarca, capaPuntos, capaTexto).join('');
    if (manual){
      var idc = 'rec' + Math.random().toString(36).slice(2, 7);
      S.push('<clipPath id="' + idc + '"><rect x="' + redondo(cajaVista[0]) + '" y="' + redondo(cajaVista[1]) + '" width="' + redondo(cajaVista[2] - cajaVista[0]) + '" height="' + redondo(cajaVista[3] - cajaVista[1]) + '"/></clipPath><g clip-path="url(#' + idc + ')">' + capaFondo.concat(capaRelleno, capaTrazo, capaDeriv, capaMarca).join('') + '</g>' + capaPuntos.concat(capaTexto).join(''));
    } else S.push(cuerpo);
    S.push('</svg>');
    return {svg: S.join(''), w: redondo(vb[2]), h: redondo(vb[3]), errores: an.errores, objetos: salidaObjetos, vista: {escala: s, ox: ox, oy: oy, viewBox: vb}};
  }

  var API = {estilo: ESTILO, compilar: compilar, grafica: function(spec, opts){ return grafica(spec, opts, false); }, geometria: geometria, plano: plano,
             _etiquetaPi: etiquetaPi, _estiloDe: estiloDe, _colorDe: colorDe};
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  if (RAIZ) RAIZ.Figuras = API;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
