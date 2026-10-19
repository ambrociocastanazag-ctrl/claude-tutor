/* Pestaña «Geometría» de la Tarjeta SVG (CONTRATO.md §2), con el diseño de Claude Design.
 * Un editor de guion (el lenguaje de MathStudio, una instrucción por línea): números de línea al lado (el de un error, en rojo), colores para
 * comandos, puntos y números, la palabra con error subrayada y el mensaje al final de su línea. La figura la enseña la cáscara en su lienzo
 * central; si hay errores se dibuja igual lo válido. Todo el dibujo lo hace Figuras.geometria.
 * Clases CSS con prefijo tgeo- (el CSS va en <style id="tgeo-estilo">).
 *
 * cargar({tipo:'geometria', guion})  ·  estado() → {guion}  ·  restaurar({guion})
 * figura(tema?) → {svg, nombre}: sin tema, SIEMPRE con Tarjeta.temaFigura (claro), fondo transparente y el tamaño S/M/L de Tarjeta.opciones;
 *            con tema ('claro'|'oscuro'), el de la ventana (solo para enseñarla). null si no hay nada que dibujar.
 *            (Lo que la cáscara pase a MathStudio es estado().guion.) */
(function () {
  'use strict';

  var CSS = [
    '.tgeo{display:flex;flex-direction:column;gap:5px;min-width:0}',
    '.tgeo-ed{display:flex;height:138px;border:1px solid var(--borde);border-radius:8px;background:var(--sup);overflow:hidden;font:500 12.5px/16px var(--mono)}',
    '.tgeo-ed:focus-within{border-color:var(--acento);box-shadow:0 0 0 2px var(--acento-suave)}',
    '.tgeo-canal{flex:none;width:28px;padding:5px 6px 0 0;text-align:right;color:var(--tenue);background:var(--hundido);border-right:1px solid var(--borde);overflow:hidden;font-size:11px;user-select:none}',
    '.tgeo-canal div{height:16px;white-space:nowrap}',
    '.tgeo-canal .mal{color:var(--error);font-weight:600}',
    '.tgeo-cod{position:relative;flex:1;min-width:0;overflow:hidden}',
    '.tgeo-cod pre,.tgeo-cod textarea{position:absolute;inset:0;margin:0;padding:5px 8px;font:inherit;white-space:pre;tab-size:2;border:0;border-radius:0}',
    '.tgeo-cod pre{pointer-events:none;overflow:visible}',
    '.tgeo-cod pre span.l{display:block;min-height:16px;margin:0 -8px;padding:0 8px}',
    '.tgeo-cod pre span.l.mal{background:var(--error-suave)}',
    '.tgeo-cod textarea{width:100%;height:100%;background:none;color:transparent;caret-color:var(--tinta);resize:none;outline:none;overflow:auto;user-select:text}',
    '.tgeo-cod textarea::selection{background:var(--acento-suave)}',
    '.k-cmd{color:var(--acento-texto);font-weight:600}',
    '.k-pt{font-weight:600}',
    '.k-num{color:var(--tenue)}',
    '.k-txt{color:var(--ok)}',
    '.k-com{color:var(--tenue);font-style:italic}',
    '.k-mal{text-decoration:wavy underline var(--error);text-decoration-thickness:1.25px;text-underline-offset:3px;color:var(--error)}',
    '.tgeo-aviso{position:absolute;right:6px;display:flex;align-items:center;height:16px;padding:0 6px;border-radius:4px;background:var(--error);color:var(--sobre-error);font:700 11px/1 var(--f);white-space:nowrap;pointer-events:none;overflow:hidden;text-overflow:ellipsis}',
    '.tgeo-errores{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:2px;font-size:11.5px;color:var(--error);user-select:text}',
    '.tgeo-errores li{overflow-wrap:anywhere;min-width:0}',
    '.tgeo-errores b{font-family:var(--mono);margin-right:6px}'
  ].join('\n');

  var area, canal, resalte, avisos, lista, temporizador = null, errActuales = [];

  function F() { return window.Figuras; }
  function tema() { return (window.Tarjeta && window.Tarjeta.tema) === 'oscuro' ? 'oscuro' : 'claro'; }
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  function cambio() { if (window.Tarjeta && window.Tarjeta.cambio) window.Tarjeta.cambio(); }
  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

  // ---- colores: lo que va seguido de «(» es un comando; el resto de letras, un punto o un nombre ----
  function colorear(t) {
    return t.replace(/("[^"]*")|(#.*$)|(-?\d*\.?\d+)|([A-Za-zñÑáéíóúÁÉÍÓÚüÜ][A-Za-z0-9ñÑáéíóúÁÉÍÓÚüÜ_']*)(\s*\()?/g, function (m, s, c, n, id, par) {
      if (s) return '<span class="k-txt">' + esc(s) + '</span>';
      if (c) return '<span class="k-com">' + esc(c) + '</span>';
      if (n) return '<span class="k-num">' + n + '</span>';
      return (par ? '<span class="k-cmd">' + esc(id) + '</span>' + esc(par) : '<span class="k-pt">' + esc(id) + '</span>');
    });
  }
  // la palabra con error: la que cita el mensaje entre «», si está en la línea; si no, toda la línea
  function tramo(linea, mensaje) {
    var q = /«([^»]+)»/.exec(mensaje || ''), i = q ? linea.indexOf(q[1]) : -1;
    if (i >= 0) return [i, i + q[1].length];
    var ini = linea.length - linea.replace(/^\s+/, '').length;
    return [ini, linea.replace(/\s+$/, '').length];
  }

  function pintar(errores) {
    var lineas = area.value.split('\n'), por = {};
    errores.forEach(function (e) { if (!por[e.linea]) por[e.linea] = e; });
    resalte.innerHTML = lineas.map(function (l, i) {
      var e = por[i + 1], h;
      if (e && l.trim()) { var t = tramo(l, e.mensaje); h = colorear(l.slice(0, t[0])) + '<span class="k-mal">' + esc(l.slice(t[0], t[1])) + '</span>' + colorear(l.slice(t[1])); }
      else h = colorear(l);
      return '<span class="l' + (e ? ' mal' : '') + '">' + (h || ' ') + '</span>';
    }).join('');
    canal.innerHTML = lineas.map(function (l, i) { return '<div' + (por[i + 1] ? ' class="mal"' : '') + '>' + (i + 1) + '</div>'; }).join('');
    colocar();
    var top = area.scrollTop, ancho = ancharCar(), libre = area.clientWidth;
    avisos.innerHTML = Object.keys(por).map(function (n) {         // el aviso usa el hueco que deja el texto de su línea (mínimo 90 px)
      var hueco = Math.max(90, libre - 8 - (lineas[n - 1] || '').length * ancho - 14 + area.scrollLeft);
      return '<div class="tgeo-aviso" style="top:' + (5 + (n - 1) * 16 - top) + 'px;max-width:' + Math.round(hueco) + 'px" title="' + esc(por[n].mensaje) + '">' + esc(por[n].mensaje) + '</div>';
    }).join('');
    // si un mensaje no cabe en su línea, la lista de abajo lo trae completo
    var corto = [].some.call(avisos.children, function (a) { return a.scrollWidth > a.clientWidth + 1; });
    lista.innerHTML = corto ? errores.map(function (e) { return '<li><b>L' + esc(e.linea) + '</b>' + esc(e.mensaje) + '</li>'; }).join('') : '';
    lista.hidden = !corto;
  }
  var anchoCar = 0;
  function ancharCar() {                     // lo que mide un carácter del editor (es monoespaciado)
    if (anchoCar > 0) return anchoCar;
    var t = el('span', '', 'MMMMMMMMMM'); t.style.cssText = 'position:absolute;visibility:hidden;white-space:pre;font:inherit';
    resalte.appendChild(t); var w = t.getBoundingClientRect().width / 10; t.remove();
    if (w > 0) anchoCar = w; return w || 7.5;
  }
  function colocar() {                       // el resalte y los números siguen al desplazamiento del texto
    resalte.style.transform = 'translate(' + -area.scrollLeft + 'px,' + -area.scrollTop + 'px)';
    canal.style.transform = 'translateY(' + -area.scrollTop + 'px)';
  }

  function montar(caja) {
    if (!document.getElementById('tgeo-estilo')) { var st = el('style'); st.id = 'tgeo-estilo'; st.textContent = CSS; document.head.appendChild(st); }
    var raiz = el('div', 'tgeo'); caja.appendChild(raiz);
    var ed = el('div', 'tgeo-ed');
    var cn = el('div', 'tgeo-canal'); canal = el('div'); cn.appendChild(canal);
    var cod = el('div', 'tgeo-cod'); resalte = el('pre'); resalte.setAttribute('aria-hidden', 'true'); avisos = el('div');
    area = el('textarea');
    area.spellcheck = false; area.setAttribute('wrap', 'off'); area.autocapitalize = 'off'; area.autocomplete = 'off'; area.setAttribute('aria-label', 'Guion de geometría');
    area.placeholder = 'Un objeto por línea:\nA=(0,0)\nB=(6,0)\nC=(2,5)\nt=triangulo(A,B,C)';
    area.addEventListener('input', programar);
    area.addEventListener('scroll', function () { colocar(); pintar(errActuales); });
    area.addEventListener('keydown', function (e) { if (e.key === 'Tab') { e.preventDefault(); document.execCommand('insertText', false, '  '); } });
    cod.appendChild(resalte); cod.appendChild(area); cod.appendChild(avisos);
    ed.appendChild(cn); ed.appendChild(cod);
    lista = el('ul', 'tgeo-errores'); lista.hidden = true;
    raiz.appendChild(ed); raiz.appendChild(lista);
    if (window.ResizeObserver) new ResizeObserver(function () { if (area.offsetParent) pintar(errActuales); }).observe(ed);   // al mostrarse la pestaña, se mide si los mensajes caben
    dibujar();
  }
  function programar() { clearTimeout(temporizador); temporizador = setTimeout(dibujar, 200); }

  // la figura la enseña la cáscara; aquí se marcan los errores del guion
  function dibujar() {
    var guion = area.value, r = null, falla = '';
    if (guion.trim()) { try { r = F().geometria(guion, { tema: tema(), tam: 'M' }); } catch (e) { falla = e.message; } }
    errActuales = r ? r.errores.slice() : [];
    if (falla) errActuales.push({ linea: 1, mensaje: falla });
    pintar(errActuales);
    cambio();
  }

  function figura(t) {
    if (!area || !area.value.trim()) return null;
    try {
      var tam = (window.Tarjeta && window.Tarjeta.opciones && window.Tarjeta.opciones.tam) || 'M';
      var r = F().geometria(area.value, { tema: t || (window.Tarjeta && window.Tarjeta.temaFigura) || 'claro', tam: tam, fondo: 'transparente' });
      return r.svg ? { svg: r.svg, nombre: 'geometria' } : null;
    } catch (e) { return null; }
  }
  function cargar(c) {
    var g = c && (c.guion != null ? c.guion : c.script);
    if (g == null) return;
    area.value = String(g).replace(/\r\n/g, '\n');
    clearTimeout(temporizador); dibujar();
  }
  function estado() { return { guion: area ? area.value : '' }; }
  function restaurar(s) { if (s && typeof s.guion === 'string'){ area.value = s.guion; clearTimeout(temporizador); dibujar(); } }

  window.Tarjeta.registrar('geometria', { titulo: 'Geometría', icono: 'geometria', montar: montar, figura: figura, cargar: cargar, estado: estado, restaurar: restaurar });
})();
