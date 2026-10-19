/* Pestaña «Geometría» de la Tarjeta SVG (CONTRATO.md §2). INTERFAZ PROVISIONAL: el diseño de Claude Design la reestilizará.
 * Un área de texto monoespaciada para el guion (el lenguaje de MathStudio, una instrucción por línea), con los números de línea al lado
 * (la de un error sale en rojo, con su mensaje al pasar el ratón y completo en la lista de debajo) y la figura debajo, que se redibuja
 * al escribir (con un pequeño retraso). Si hay errores se dibuja igual lo válido. Todo el dibujo lo hace Figuras.geometria.
 * Clases CSS con prefijo tgeo- (el CSS provisional va en <style id="tgeo-estilo">).
 *
 * cargar({tipo:'geometria', guion})  ·  estado() → {guion}  ·  restaurar({guion})
 * figura() → {svg, nombre}: SIEMPRE con el tema Tarjeta.temaFigura (claro), fondo transparente y el tamaño S/M/L de Tarjeta.opciones.
 *            null si no hay nada que dibujar. (Lo que la cáscara pase a MathStudio es estado().guion.) */
(function () {
  'use strict';

  var EJEMPLO = 'A=(0,0)\nB=(6,0)\nC=(2,5)\nt=triangulo(A,B,C)\nc=circunferencia(A,B,C)\nh=altura(A,BC)';
  var CSS = [
    '.tgeo{display:flex;flex-direction:column;gap:9px;min-width:0}',
    '.tgeo-ed{display:flex;border:1px solid var(--line,#ccc);border-radius:9px;background:var(--bg,#fff);overflow:hidden;min-width:0}',
    '.tgeo-num{flex:none;min-width:30px;padding:7px 5px 7px 6px;text-align:right;color:var(--muted,#777);background:var(--sunk,#eee);overflow:hidden;font:12.5px/18px var(--mono,Consolas,monospace);user-select:none}',
    '.tgeo-num div{height:18px;white-space:nowrap}',
    '.tgeo-num .mal{color:var(--on-acc,#fff);background:var(--bad,#b00);border-radius:4px;font-weight:700;cursor:help}',
    '.tgeo-txt{flex:1;min-width:0;height:104px;resize:vertical;border:0;border-radius:0;background:transparent;padding:7px 8px;font:12.5px/18px var(--mono,Consolas,monospace);white-space:pre;overflow:auto;user-select:text;outline:none}',
    '.tgeo-errores{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:3px;font-size:12px;user-select:text}',
    '.tgeo-errores li{display:flex;gap:7px;align-items:baseline;color:var(--bad,#b00);overflow-wrap:anywhere;min-width:0}',
    '.tgeo-errores b{flex:none;font-family:var(--mono,Consolas,monospace)}',
    '.tgeo-errores i{font-style:normal;color:var(--muted,#666);font-family:var(--mono,Consolas,monospace);flex:none;max-width:40%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
    '.tgeo-fig{min-height:96px;border:1px solid var(--line,#ccc);border-radius:9px;background:var(--bg,#fff);display:grid;place-items:center;padding:6px;overflow:hidden}',
    '.tgeo-fig svg{display:block;width:100%;height:auto;max-width:100%}',
    '.tgeo-vacio{color:var(--muted,#666);font-size:12.5px;text-align:center;padding:14px}'
  ].join('\n');

  var area, num, lista, cajaFig, temporizador = null;

  function F() { return window.Figuras; }
  function tema() { return (window.Tarjeta && window.Tarjeta.tema) === 'oscuro' ? 'oscuro' : 'claro'; }
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  function cambio() { if (window.Tarjeta && window.Tarjeta.cambio) window.Tarjeta.cambio(); }

  function montar(caja) {
    if (!document.getElementById('tgeo-estilo')) { var st = el('style'); st.id = 'tgeo-estilo'; st.textContent = CSS; document.head.appendChild(st); }
    var raiz = el('div', 'tgeo'); caja.appendChild(raiz);
    var ed = el('div', 'tgeo-ed');
    num = el('div', 'tgeo-num'); area = el('textarea', 'tgeo-txt');
    area.spellcheck = false; area.setAttribute('wrap', 'off'); area.autocapitalize = 'off'; area.setAttribute('aria-label', 'Guion de geometría');
    area.placeholder = 'Un objeto por línea:\nA=(0,0)\nB=(6,0)\nC=(2,5)\nt=triangulo(A,B,C)';
    area.addEventListener('input', programar);
    area.addEventListener('scroll', function () { num.scrollTop = area.scrollTop; });
    ed.appendChild(num); ed.appendChild(area);
    lista = el('ul', 'tgeo-errores'); lista.hidden = true;
    cajaFig = el('div', 'tgeo-fig');
    raiz.appendChild(ed); raiz.appendChild(lista); raiz.appendChild(cajaFig);
    dibujar();
  }
  function programar() { clearTimeout(temporizador); temporizador = setTimeout(dibujar, 200); }

  function pintarNumeros(errores) {
    var n = Math.max(area.value.split('\n').length, 1), porLinea = {};
    errores.forEach(function (e) { (porLinea[e.linea] = porLinea[e.linea] || []).push(e.mensaje); });
    num.innerHTML = '';
    for (var i = 1; i <= n; i++) {
      var d = el('div', porLinea[i] ? 'mal' : '', String(i));
      if (porLinea[i]) d.title = porLinea[i].join('\n');
      num.appendChild(d);
    }
    area.style.height = Math.min(Math.max(n + 1, 5), 13) * 18 + 14 + 'px';     // crece con el guion (de 5 a 13 líneas); más allá, se desplaza
    num.scrollTop = area.scrollTop;
  }

  function dibujar() {
    var guion = area.value, r = null, falla = '';
    cajaFig.innerHTML = ''; lista.innerHTML = '';
    if (guion.trim()) { try { r = F().geometria(guion, { tema: tema(), tam: 'M' }); } catch (e) { falla = e.message; } }
    var errores = r ? r.errores : [];
    pintarNumeros(errores);
    var lineas = guion.split(/\r?\n/);
    errores.forEach(function (e) {
      var li = el('li'), b = el('b', '', 'L' + e.linea), q = el('i', '', (lineas[e.linea - 1] || '').trim()), t = el('span', '', e.mensaje);
      li.appendChild(b); li.appendChild(q); li.appendChild(t); lista.appendChild(li);
    });
    if (falla) { var lf = el('li', '', ''); lf.textContent = falla; lista.appendChild(lf); }
    lista.hidden = !lista.childNodes.length;
    if (r && r.svg) cajaFig.innerHTML = r.svg;
    else cajaFig.appendChild(el('div', 'tgeo-vacio', guion.trim() ? 'No hay nada que dibujar todavía: revisa las líneas marcadas.' : 'Escribe el guion: un objeto por línea.'));
    cambio();
  }

  function figura() {
    if (!area || !area.value.trim()) return null;
    try {
      var tam = (window.Tarjeta && window.Tarjeta.opciones && window.Tarjeta.opciones.tam) || 'M';
      var r = F().geometria(area.value, { tema: (window.Tarjeta && window.Tarjeta.temaFigura) || 'claro', tam: tam, fondo: 'transparente' });
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
