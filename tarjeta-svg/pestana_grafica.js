/* Pestaña «Gráfica» de la Tarjeta SVG (CONTRATO.md §2). INTERFAZ PROVISIONAL: el diseño de Claude Design la reestilizará.
 * Hasta 3 funciones (un renglón cada una: color, ojo y la expresión), rango x/y, interruptor «Área» con desde/hasta, y la figura
 * debajo, que se redibuja al escribir (con un pequeño retraso). Todo el dibujo lo hace Figuras.grafica (tutor-pantalla/motor_figuras.js).
 * Clases CSS con prefijo tg- (el CSS provisional va en <style id="tg-estilo">).
 *
 * cargar({tipo:'grafica', spec})  →  pone el JSON de ```grafica en los campos (lo que no cabe en ellos, como el título o los puntos,
 *                                    se conserva y se vuelve a mandar al motor).
 * estado() / restaurar(obj)       →  lo escrito, para recordarlo entre sesiones.
 * figura()                        →  {svg, nombre}: SIEMPRE con el tema Tarjeta.temaFigura (claro: Miro es blanco), fondo transparente
 *                                    (la cáscara pone el blanco si se pide) y el tamaño S/M/L de Tarjeta.opciones. null si no hay nada que copiar. */
(function () {
  'use strict';

  var COLORES = ['azul', 'rojo', 'verde', 'naranja', 'morado', 'amarillo'];
  var N = 3;
  var CSS = [
    '.tg{display:flex;flex-direction:column;gap:9px;min-width:0}',
    '.tg-fila{display:flex;align-items:center;gap:5px;min-width:0}',
    '.tg-col,.tg-ojo{flex:none;width:28px;height:28px;border:1px solid var(--line,#ccc);border-radius:7px;background:var(--surface,#fff);display:grid;place-items:center;padding:0;color:var(--muted,#666)}',
    '.tg-col i{display:block;width:14px;height:14px;border-radius:50%}',
    '.tg-ojo[aria-pressed="false"]{opacity:.45}',
    '.tg-ojo svg{width:16px;height:16px}',
    '.tg-f{flex:1;min-width:0;height:28px;padding:0 8px;font-family:var(--mono,Consolas,monospace);user-select:text}',
    '.tg-etq{flex:none;color:var(--muted,#666);font-family:var(--mono,Consolas,monospace);font-size:12px}',
    '.tg-msg{color:var(--bad,#b00);font-size:11.5px;margin:-4px 0 0 66px;overflow-wrap:anywhere}',
    '.tg-rangos{display:grid;grid-template-columns:auto 1fr auto 1fr;gap:5px 6px;align-items:center}',
    '.tg-rangos input,.tg-area input[type=text]{width:100%;min-width:0;height:26px;padding:0 6px;text-align:center;user-select:text}',
    '.tg-rangos span,.tg-area span{color:var(--muted,#666);font-size:12px}',
    '.tg-area{display:flex;flex-wrap:wrap;align-items:center;gap:6px}',
    '.tg-area label{display:flex;align-items:center;gap:5px;font-weight:600}',
    '.tg-area select{height:26px;border:1px solid var(--line,#ccc);border-radius:7px;background:var(--bg,#fff);color:var(--ink,#222);font:inherit}',
    '.tg-area input[type=text]{width:58px}',
    '.tg-area[data-on="0"] .tg-area-campos{opacity:.4;pointer-events:none}',
    '.tg-area-campos{display:flex;align-items:center;gap:6px;flex-wrap:wrap}',
    '.tg-fig{min-height:96px;border:1px solid var(--line,#ccc);border-radius:9px;background:var(--bg,#fff);display:grid;place-items:center;padding:6px;overflow:hidden}',
    '.tg-fig svg{display:block;width:100%;height:auto;max-width:100%}',
    '.tg-vacio{color:var(--muted,#666);font-size:12.5px;text-align:center;padding:14px}',
    '.tg-error{color:var(--bad,#b00);font-size:12px;overflow-wrap:anywhere;user-select:text}'
  ].join('\n');

  var OJO = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>';

  var raiz, filas = [], campos = {}, extra = {}, temporizador = null, ultimo = null, cajaFig, cajaError;

  function F() { return window.Figuras; }
  function tema() { return (window.Tarjeta && window.Tarjeta.tema) === 'oscuro' ? 'oscuro' : 'claro'; }
  function hexDe(color, t) { var P = F()._estiloDe({ tema: t }); return F()._colorDe(P, color, '#888888'); }
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  function cambio() { if (window.Tarjeta && window.Tarjeta.cambio) window.Tarjeta.cambio(); }

  function montar(caja) {
    if (!document.getElementById('tg-estilo')) { var st = el('style'); st.id = 'tg-estilo'; st.textContent = CSS; document.head.appendChild(st); }
    raiz = el('div', 'tg'); caja.appendChild(raiz);
    for (var i = 0; i < N; i++) (function (i) {
      var fila = el('div', 'tg-fila'), msg = el('div', 'tg-msg'); msg.hidden = true;
      var col = el('button', 'tg-col'); col.type = 'button'; col.title = 'Cambiar de color';
      var ojo = el('button', 'tg-ojo', OJO); ojo.type = 'button'; ojo.title = 'Mostrar u ocultar'; ojo.setAttribute('aria-pressed', 'true');
      var etq = el('span', 'tg-etq', 'y ='), inp = el('input', 'tg-f'); inp.type = 'text'; inp.spellcheck = false; inp.autocomplete = 'off';
      inp.placeholder = ['ej. sqrt(x)', 'ej. sin(x)', 'ej. x^2 - 1'][i];
      var f = { color: COLORES[i % COLORES.length], ver: true, inp: inp, col: col, ojo: ojo, msg: msg };
      col.onclick = function () { f.color = COLORES[(COLORES.indexOf(f.color) + 1) % COLORES.length] || COLORES[0]; pintarColor(f); programar(); };
      ojo.onclick = function () { f.ver = !f.ver; ojo.setAttribute('aria-pressed', String(f.ver)); programar(); };
      inp.addEventListener('input', programar);
      fila.appendChild(col); fila.appendChild(ojo); fila.appendChild(etq); fila.appendChild(inp);
      raiz.appendChild(fila); raiz.appendChild(msg);
      filas.push(f); pintarColor(f);
    })(i);

    var rg = el('div', 'tg-rangos');
    [['x', 'xa', '-5'], ['', 'xb', '5'], ['y', 'ya', 'auto'], ['', 'yb', 'auto']].forEach(function (d) {
      if (d[0]) rg.appendChild(el('span', '', d[0] + ' de'));
      else rg.appendChild(el('span', '', 'a'));
      var i = el('input'); i.type = 'text'; i.placeholder = d[2]; i.spellcheck = false; i.setAttribute('aria-label', d[1]); i.addEventListener('input', programar);
      campos[d[1]] = i; rg.appendChild(i);
    });
    // en la rejilla: «x de [a] a [b]» y «y de [a] a [b]»
    raiz.appendChild(rg);

    var ar = el('div', 'tg-area'); ar.setAttribute('data-on', '0');
    var lb = el('label'), ck = el('input'); ck.type = 'checkbox'; lb.appendChild(ck); lb.appendChild(document.createTextNode('Área'));
    var cc = el('div', 'tg-area-campos'), sel = el('select');
    for (var k = 0; k < N; k++) { var o = el('option', '', 'de la función ' + (k + 1)); o.value = String(k); sel.appendChild(o); }
    var d1 = el('input'), d2 = el('input'); d1.type = d2.type = 'text'; d1.placeholder = 'desde'; d2.placeholder = 'hasta'; d1.spellcheck = d2.spellcheck = false;
    cc.appendChild(sel); cc.appendChild(el('span', '', 'desde')); cc.appendChild(d1); cc.appendChild(el('span', '', 'hasta')); cc.appendChild(d2);
    ar.appendChild(lb); ar.appendChild(cc); raiz.appendChild(ar);
    campos.areaOn = ck; campos.areaFn = sel; campos.areaA = d1; campos.areaB = d2; campos.areaCaja = ar;
    ck.addEventListener('change', function () { ar.setAttribute('data-on', ck.checked ? '1' : '0'); programar(); });
    [sel, d1, d2].forEach(function (e) { e.addEventListener('input', programar); e.addEventListener('change', programar); });

    cajaFig = el('div', 'tg-fig'); cajaError = el('div', 'tg-error'); cajaError.hidden = true;
    raiz.appendChild(cajaFig); raiz.appendChild(cajaError);
    dibujar();
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

  function dibujar() {
    var a = armar(), r = null, msg = a.fallos.join(' ');
    cajaFig.innerHTML = '';
    if (a.hay && !a.fallos.length || (a.hay && a.spec.funciones && a.spec.funciones.length)) {
      try { r = F().grafica(a.spec, { tema: tema(), tam: 'M' }); } catch (e) { msg = (msg ? msg + ' ' : '') + e.message; }
    }
    if (r) { cajaFig.innerHTML = r.svg; ultimo = a.spec; }
    else { ultimo = null; cajaFig.appendChild(el('div', 'tg-vacio', a.hay ? 'No se puede dibujar todavía.' : 'Escribe una función, por ejemplo sqrt(x).')); }
    cajaError.textContent = msg; cajaError.hidden = !msg;
    cambio();
  }

  function figura() {
    var a = armar();
    if (!a.hay || (a.fallos.length && !(a.spec.funciones && a.spec.funciones.length))) return null;
    try {
      var tam = (window.Tarjeta && window.Tarjeta.opciones && window.Tarjeta.opciones.tam) || 'M';
      var r = F().grafica(a.spec, { tema: (window.Tarjeta && window.Tarjeta.temaFigura) || 'claro', tam: tam, fondo: 'transparente' });
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
      f.ver = true; f.ojo.setAttribute('aria-pressed', 'true'); f.msg.hidden = true; pintarColor(f);
    });
    if (lista.length > N && window.Tarjeta && Tarjeta.aviso) Tarjeta.aviso('Aquí caben ' + N + ' funciones; el resto se dejó fuera');
    ponerRango(spec.x, campos.xa, campos.xb); ponerRango(spec.y, campos.ya, campos.yb);
    campos.areaOn.checked = !!spec.area; campos.areaCaja.setAttribute('data-on', spec.area ? '1' : '0');
    campos.areaA.value = campos.areaB.value = ''; campos.areaFn.value = '0';
    if (spec.area) {
      var af = String(spec.area.f), k = -1;
      filas.forEach(function (f, i) { if (k < 0 && f.inp.value.trim() === af.trim()) k = i; });
      if (k < 0) {                                           // el área es de una función que no se dibuja: va a un renglón libre con el ojo cerrado
        k = filas.map(function (f) { return f.inp.value.trim(); }).indexOf('');
        if (k < 0) k = N - 1;
        filas[k].inp.value = af; filas[k].ver = false; filas[k].ojo.setAttribute('aria-pressed', 'false');
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
      f.ojo.setAttribute('aria-pressed', String(f.ver)); pintarColor(f);
    });
    if (s.x) { campos.xa.value = s.x[0] || ''; campos.xb.value = s.x[1] || ''; }
    if (s.y) { campos.ya.value = s.y[0] || ''; campos.yb.value = s.y[1] || ''; }
    if (s.area) { campos.areaOn.checked = !!s.area.on; campos.areaCaja.setAttribute('data-on', s.area.on ? '1' : '0'); campos.areaFn.value = s.area.fn || '0'; campos.areaA.value = s.area.a || ''; campos.areaB.value = s.area.b || ''; }
    extra = s.extra && typeof s.extra === 'object' ? s.extra : {};
    clearTimeout(temporizador); dibujar();
  }

  window.Tarjeta.registrar('grafica', { titulo: 'Gráfica', icono: 'grafica', montar: montar, figura: figura, cargar: cargar, estado: estado, restaurar: restaurar });
})();
