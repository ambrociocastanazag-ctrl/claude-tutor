/* Pestaña «Gráfica» de la Tarjeta SVG (CONTRATO.md §2). con el diseño de Claude Design.
 * Hasta 3 funciones (un renglón cada una: color, expresión y ojo), rango x/y, interruptor «Área» con función y desde/hasta. La figura
 * la enseña la cáscara en su lienzo central (diseño de Claude Design); aquí solo se arman los campos y se avisa de lo que no vale.
 * Todo el dibujo lo hace Figuras.grafica (tutor-pantalla/motor_figuras.js).
 * Clases CSS con prefijo tg- (el CSS provisional va en <style id="tg-estilo">).
 *
 * cargar({tipo:'grafica', spec})  →  pone el JSON de ```grafica en los campos (lo que no cabe en ellos, como el título o los puntos,
 *                                    se conserva y se vuelve a mandar al motor).
 * estado() / restaurar(obj)       →  lo escrito, para recordarlo entre sesiones.
 * figura()                        →  {svg, nombre}: SIEMPRE con el tema Tarjeta.temaFigura (claro: se pega sobre blanco), fondo transparente
 *                                    (la cáscara pone el blanco si se pide) y el tamaño S/M/L de Tarjeta.opciones. null si no hay nada que copiar. */
(function () {
  'use strict';

  var COLORES = ['azul', 'rojo', 'verde', 'naranja', 'morado', 'amarillo'];
  var N = 3;
  var CSS = [
    '.tg{display:flex;flex-direction:column;gap:4px;min-width:0}',
    '.tg-fila{display:flex;align-items:center;gap:5px;height:28px;min-width:0}',
    '.tg-fila.oculta .tg-f,.tg-fila.oculta .tg-col{opacity:.5}',
    '.tg-col{flex:none;width:24px;height:24px;border:1px solid var(--borde);border-radius:6px;background:var(--sup);display:grid;place-items:center;padding:0}',
    '.tg-col i{display:block;width:10px;height:10px;border-radius:50%}',
    '.tg-etq{flex:none;width:22px;font:italic 500 13px var(--f);color:var(--tenue);text-align:right}',
    '.tg-f,.tg-num,.tg-sel{border:1px solid var(--borde);border-radius:7px;background:var(--sup);outline:none}',
    '.tg-f{flex:1;min-width:0;height:28px;padding:0 8px;font:500 13px var(--mono)}',
    '.tg-f::placeholder,.tg-num::placeholder{color:var(--tenue)}',
    '.tg-f:focus,.tg-num:focus,.tg-sel:focus{border-color:var(--acento);box-shadow:0 0 0 2px var(--acento-suave)}',
    '.tg-ojo{flex:none;width:28px;height:28px;border:0;border-radius:6px;background:none;color:var(--tenue);display:grid;place-items:center;padding:0}',
    '.tg-ojo:hover{background:var(--sup-2);color:var(--tinta)}',
    '.tg-msg{color:var(--error);font-size:11.5px;margin:-1px 0 1px 54px;overflow-wrap:anywhere}',
    '.tg-linea{display:flex;align-items:center;gap:5px;min-height:30px;margin-top:2px;font-size:12.5px;font-weight:600;color:var(--tenue);white-space:nowrap}',
    '.tg-linea em{font-style:italic;font-weight:500;color:var(--tinta)}',
    '.tg-esp{flex:1}',
    '.tg-num{width:46px;height:26px;padding:0 3px;text-align:center;font:500 12.5px var(--mono);color:var(--tinta);min-width:0}',
    '.tg-num:disabled{opacity:.45}',
    '.tg-sel{height:26px;padding:0 4px;font:600 12px var(--f);color:var(--tinta)}',
    '.tg-sw{display:inline-flex;align-items:center;gap:6px;height:26px;padding:0 4px;border:0;background:none;font-weight:700;font-size:12.5px;color:var(--tinta)}',
    '.tg-sw b{position:relative;width:28px;height:16px;border-radius:8px;background:var(--borde)}',
    '.tg-sw b::after{content:"";position:absolute;top:2px;left:2px;width:12px;height:12px;border-radius:50%;background:var(--sup);transition:transform .15s}',
    '.tg-sw[aria-checked="true"] b{background:var(--acento)}',
    '.tg-sw[aria-checked="true"] b::after{transform:translateX(12px)}',
    '.tg-area[data-on="0"] .tg-ac{opacity:.4;pointer-events:none}',
    '.tg-ac{display:flex;align-items:center;gap:5px}',
    '.tg-error{color:var(--error);font-size:12px;overflow-wrap:anywhere;user-select:text}'
  ].join('\n');

  var raiz, filas = [], campos = {}, extra = {}, temporizador = null, ultimo = null, cajaError;

  function F() { return window.Figuras; }
  function tema() { return (window.Tarjeta && window.Tarjeta.tema) === 'oscuro' ? 'oscuro' : 'claro'; }
  function hexDe(color, t) { var P = F()._estiloDe({ tema: t }); return F()._colorDe(P, color, '#888888'); }
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  function icono(n, t) { return window.Tarjeta && Tarjeta.icono ? Tarjeta.icono(n, t) : ''; }
  function cambio() { if (window.Tarjeta && window.Tarjeta.cambio) window.Tarjeta.cambio(); }

  function montar(caja) {
    if (!document.getElementById('tg-estilo')) { var st = el('style'); st.id = 'tg-estilo'; st.textContent = CSS; document.head.appendChild(st); }
    raiz = el('div', 'tg'); caja.appendChild(raiz);
    for (var i = 0; i < N; i++) (function (i) {
      var fila = el('div', 'tg-fila'), msg = el('div', 'tg-msg'); msg.hidden = true;
      var col = el('button', 'tg-col'); col.type = 'button'; col.title = 'Cambiar de color';
      var ojo = el('button', 'tg-ojo', icono('ojo', 16)); ojo.type = 'button'; ojo.title = 'Ocultar'; ojo.setAttribute('aria-pressed', 'true');
      var etq = el('span', 'tg-etq', 'y ='), inp = el('input', 'tg-f'); inp.type = 'text'; inp.spellcheck = false; inp.autocomplete = 'off';
      inp.placeholder = ['sqrt(x)', 'otra función', 'otra función'][i]; inp.setAttribute('aria-label', 'Función ' + (i + 1));
      var f = { color: COLORES[i % COLORES.length], ver: true, inp: inp, col: col, ojo: ojo, msg: msg, fila: fila };
      col.onclick = function () { f.color = COLORES[(COLORES.indexOf(f.color) + 1) % COLORES.length] || COLORES[0]; pintarColor(f); programar(); };
      ojo.onclick = function () { f.ver = !f.ver; pintarOjo(f); programar(); };
      inp.addEventListener('input', programar);
      fila.appendChild(col); fila.appendChild(etq); fila.appendChild(inp); fila.appendChild(ojo);
      raiz.appendChild(fila); raiz.appendChild(msg);
      filas.push(f); pintarColor(f);
    })(i);

    // «x [a] a [b]   y [a] a [b]» y, debajo, «Área [y1] [desde] a [hasta]»
    var rg = el('div', 'tg-linea');
    [['x', 'xa', '-5'], ['', 'xb', '5'], ['y', 'ya', 'auto'], ['', 'yb', 'auto']].forEach(function (d, k) {
      if (d[0]) rg.appendChild(el('em', '', d[0]));
      else rg.appendChild(el('span', '', 'a'));
      var i = el('input', 'tg-num'); i.type = 'text'; i.placeholder = d[2]; i.spellcheck = false; i.autocomplete = 'off'; i.setAttribute('aria-label', d[1]); i.addEventListener('input', programar);
      campos[d[1]] = i; rg.appendChild(i);
      if (k === 1) rg.appendChild(el('span', 'tg-esp'));
    });
    raiz.appendChild(rg);

    var ar = el('div', 'tg-linea tg-area'); ar.setAttribute('data-on', '0');
    var ck = el('button', 'tg-sw', '<b></b>Área'); ck.type = 'button'; ck.setAttribute('role', 'switch'); ck.setAttribute('aria-checked', 'false');
    var cc = el('div', 'tg-ac'), sel = el('select', 'tg-sel'); sel.setAttribute('aria-label', 'Función del área');
    for (var k = 0; k < N; k++) { var o = el('option', '', 'y' + (k + 1)); o.value = String(k); o.title = 'de la función ' + (k + 1); sel.appendChild(o); }
    var d1 = el('input', 'tg-num'), d2 = el('input', 'tg-num'); d1.type = d2.type = 'text'; d1.placeholder = 'desde'; d2.placeholder = 'hasta'; d1.spellcheck = d2.spellcheck = false;
    d1.autocomplete = d2.autocomplete = 'off'; d1.setAttribute('aria-label', 'Área desde'); d2.setAttribute('aria-label', 'Área hasta');
    cc.appendChild(sel); cc.appendChild(d1); cc.appendChild(el('span', '', 'a')); cc.appendChild(d2);
    ar.appendChild(ck); ar.appendChild(el('span', 'tg-esp')); ar.appendChild(cc); raiz.appendChild(ar);
    campos.areaOn = ck; campos.areaFn = sel; campos.areaA = d1; campos.areaB = d2; campos.areaCaja = ar;
    ck.checked = false;
    ck.onclick = function () { ponerArea(!ck.checked); programar(); };
    [sel, d1, d2].forEach(function (e) { e.addEventListener('input', programar); e.addEventListener('change', programar); });

    cajaError = el('div', 'tg-error'); cajaError.hidden = true;
    raiz.appendChild(cajaError);
    dibujar();
  }
  // el interruptor del área (no es un checkbox, pero se lee igual: campos.areaOn.checked)
  function ponerArea(on) { campos.areaOn.checked = !!on; campos.areaOn.setAttribute('aria-checked', String(!!on)); campos.areaCaja.setAttribute('data-on', on ? '1' : '0'); }
  function pintarOjo(f) {
    f.ojo.setAttribute('aria-pressed', String(f.ver)); f.ojo.innerHTML = icono(f.ver ? 'ojo' : 'ojoCerrado', 16);
    f.ojo.title = f.ver ? 'Ocultar' : 'Mostrar'; f.fila.classList.toggle('oculta', !f.ver);
  }
  function pintarColor(f) { f.col.innerHTML = '<i style="background:' + hexDe(f.color, tema()) + '"></i>'; f.col.setAttribute('aria-label', 'Color ' + f.color); }

  function programar() { clearTimeout(temporizador); temporizador = setTimeout(dibujar, 180); }

  // ---- de los campos a la spec del motor (y los errores junto a su campo) ----
  function numero(txt) {                                    // «-2*pi» → número, o undefined si está vacío; lanza si no vale
    var t = String(txt || '').trim();
    if (!t || t === 'auto') return undefined;
    var v = F().compilar(t, { constante: true })(0);
    if (typeof v !== 'number' || !isFinite(v)) throw new Error('no es un número');
    return v;
  }
  function rango(a, b, que) {
    var va, vb;
    try { va = numero(a); vb = numero(b); } catch (e) { throw new Error('El rango de ' + que + ' no es válido (' + e.message + ').'); }
    if (va === undefined && vb === undefined) return null;
    if (va === undefined || vb === undefined) throw new Error('El rango de ' + que + ' necesita los dos extremos.');
    if (!(va < vb)) throw new Error('En el rango de ' + que + ' el primero tiene que ser menor que el segundo.');
    return [va, vb];
  }
  function armar() {
    var spec = {}, fallos = [], hay = false;
    var xr = null, yr = null;
    try { xr = rango(campos.xa.value, campos.xb.value, 'x'); } catch (e) { fallos.push(e.message); }
    try { yr = rango(campos.ya.value, campos.yb.value, 'y'); } catch (e2) { fallos.push(e2.message); }
    if (xr) spec.x = xr; if (yr) spec.y = yr;
    spec.funciones = [];
    filas.forEach(function (f, i) {
      f.msg.hidden = true; f.inp.style.borderColor = '';
      var t = f.inp.value.trim();
      if (!t) return;
      try { F().compilar(t); } catch (e) { f.msg.textContent = e.message; f.msg.hidden = false; f.inp.style.borderColor = 'var(--bad,#b00)'; return; }
      if (f.ver) { spec.funciones.push({ f: t, color: f.color }); hay = true; }
    });
    if (campos.areaOn.checked) {
      var g = filas[+campos.areaFn.value], tf = g && g.inp.value.trim();
      if (!tf) fallos.push('El área necesita que la función ' + (+campos.areaFn.value + 1) + ' esté escrita.');
      else {
        var ar = { f: tf, color: g.color }, rx = null;
        try { rx = rango(campos.areaA.value, campos.areaB.value, 'el área'); } catch (e3) { fallos.push(e3.message); }
        if (rx) ar.x = rx;
        if (extra.areaG) ar.g = extra.areaG;
        spec.area = ar; hay = true;
      }
    }
    ['titulo', 'puntos', 'pie'].forEach(function (k) { if (extra[k] != null) spec[k] = extra[k]; });
    if (extra.puntos && extra.puntos.length) hay = true;
    return { spec: spec, hay: hay, fallos: fallos };
  }

  // la figura la enseña la cáscara en su lienzo; aquí solo se comprueba que se pueda dibujar y se dice por qué no
  function dibujar() {
    var a = armar(), r = null, msg = a.fallos.join(' ');
    if (a.hay && !a.fallos.length || (a.hay && a.spec.funciones && a.spec.funciones.length)) {
      try { r = F().grafica(a.spec, { tema: tema(), tam: 'M' }); } catch (e) { msg = (msg ? msg + ' ' : '') + e.message; }
    }
    ultimo = r ? a.spec : null;
    if (!r && a.hay && !msg) msg = 'No se puede dibujar todavía.';
    cajaError.textContent = msg; cajaError.hidden = !msg;
    cambio();
  }

  function figura(t) {                                     // t ('claro'|'oscuro'): para enseñarla en la ventana; sin él, la que se copia
    var a = armar();
    if (!a.hay || (a.fallos.length && !(a.spec.funciones && a.spec.funciones.length))) return null;
    try {
      var tam = (window.Tarjeta && window.Tarjeta.opciones && window.Tarjeta.opciones.tam) || 'M';
      var r = F().grafica(a.spec, { tema: t || (window.Tarjeta && window.Tarjeta.temaFigura) || 'claro', tam: tam, fondo: 'transparente' });
      return { svg: r.svg, nombre: 'grafica' };
    } catch (e) { return null; }
  }

  // ---- de la spec a los campos ----
  function ponerRango(v, ia, ib) {
    ia.value = ib.value = '';
    if (Array.isArray(v) && v.length === 2) { ia.value = String(v[0]); ib.value = String(v[1]); }
  }
  function cargar(c) {
    var spec = c && c.spec;
    if (typeof spec === 'string') { try { spec = JSON.parse(spec); } catch (e) { spec = null; } }
    if (!spec || typeof spec !== 'object') return;
    var lista = spec.funciones != null ? spec.funciones : spec.funcion != null ? [spec.funcion] : [];
    if (!Array.isArray(lista)) lista = [lista];
    extra = {};
    ['titulo', 'puntos', 'pie'].forEach(function (k) { if (spec[k] != null) extra[k] = spec[k]; });
    filas.forEach(function (f, i) {
      var it = lista[i];
      if (typeof it === 'string' || typeof it === 'number') it = { f: it };
      f.inp.value = it && it.f != null ? String(it.f) : '';
      f.color = it && it.color && COLORES.indexOf(String(it.color).toLowerCase()) >= 0 ? String(it.color).toLowerCase() : COLORES[i % COLORES.length];
      f.ver = true; pintarOjo(f); f.msg.hidden = true; pintarColor(f);
    });
    if (lista.length > N && window.Tarjeta && Tarjeta.aviso) Tarjeta.aviso('Aquí caben ' + N + ' funciones; el resto se dejó fuera');
    ponerRango(spec.x, campos.xa, campos.xb); ponerRango(spec.y, campos.ya, campos.yb);
    ponerArea(!!spec.area);
    campos.areaA.value = campos.areaB.value = ''; campos.areaFn.value = '0';
    if (spec.area) {
      var af = String(spec.area.f), k = -1;
      filas.forEach(function (f, i) { if (k < 0 && f.inp.value.trim() === af.trim()) k = i; });
      if (k < 0) {                                           // el área es de una función que no se dibuja: va a un renglón libre con el ojo cerrado
        k = filas.map(function (f) { return f.inp.value.trim(); }).indexOf('');
        if (k < 0) k = N - 1;
        filas[k].inp.value = af; filas[k].ver = false; pintarOjo(filas[k]);
      }
      campos.areaFn.value = String(k);
      if (Array.isArray(spec.area.x)) { campos.areaA.value = String(spec.area.x[0]); campos.areaB.value = String(spec.area.x[1]); }
      if (spec.area.color) filas[k].color = COLORES.indexOf(String(spec.area.color).toLowerCase()) >= 0 ? String(spec.area.color).toLowerCase() : filas[k].color;
      pintarColor(filas[k]);
      if (spec.area.g != null && String(spec.area.g) !== '0') extra.areaG = spec.area.g;
    }
    clearTimeout(temporizador); dibujar();
  }

  function estado() {
    return {
      f: filas.map(function (f) { return { t: f.inp.value, color: f.color, ver: f.ver }; }),
      x: [campos.xa.value, campos.xb.value], y: [campos.ya.value, campos.yb.value],
      area: { on: campos.areaOn.checked, fn: campos.areaFn.value, a: campos.areaA.value, b: campos.areaB.value }, extra: extra
    };
  }
  function restaurar(s) {
    if (!s || typeof s !== 'object') return;
    (s.f || []).forEach(function (d, i) {
      var f = filas[i]; if (!f || !d) return;
      f.inp.value = d.t || ''; f.color = COLORES.indexOf(d.color) >= 0 ? d.color : f.color; f.ver = d.ver !== false;
      pintarOjo(f); pintarColor(f);
    });
    if (s.x) { campos.xa.value = s.x[0] || ''; campos.xb.value = s.x[1] || ''; }
    if (s.y) { campos.ya.value = s.y[0] || ''; campos.yb.value = s.y[1] || ''; }
    if (s.area) { ponerArea(!!s.area.on); campos.areaFn.value = s.area.fn || '0'; campos.areaA.value = s.area.a || ''; campos.areaB.value = s.area.b || ''; }
    extra = s.extra && typeof s.extra === 'object' ? s.extra : {};
    clearTimeout(temporizador); dibujar();
  }

  window.Tarjeta.registrar('grafica', { titulo: 'Gráfica', icono: 'grafica', montar: montar, figura: figura, cargar: cargar, estado: estado, restaurar: restaurar });
})();
