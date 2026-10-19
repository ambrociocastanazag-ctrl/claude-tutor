/* Pestaña «Geometría» de la Tarjeta SVG (CONTRATO.md §2), con el diseño de Claude Design.
 * Un editor de guion (el lenguaje de MathStudio, una instrucción por línea): números de línea al lado (el de un error, en rojo), colores para
 * comandos, puntos y números, la palabra con error subrayada y el mensaje al final de su línea. La figura la enseña la cáscara en su lienzo
 * central; si hay errores se dibuja igual lo válido. Todo el dibujo lo hace Figuras.geometria.
 * Clases CSS con prefijo tgeo- (el CSS va en <style id="tgeo-estilo">).
 *
 * cargar({tipo:'geometria', guion})  ·  estado() → {guion, vista}  ·  restaurar({guion, vista})
 * 3D (tutor-pantalla/CONTRATO-3D.md §5): si Figuras3D.es3d(guion) (un punto (x,y,z) o un comando solo 3D), la figura es 3D y girable. La
 *            cáscara le pide el lienzo con figura(tema).vivo(elemento); la vista se recuerda mientras se edita el guion y en estado().
 *            cargar({tipo:'3d', spec, vista}) enseña una figura del chat sin guion (también girable).
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
    '.k-opc{color:var(--ok)}',
    '.tgeo-nota{margin:0;font-size:11.5px;color:var(--tenue)}',
    '.k-mal{text-decoration:wavy underline var(--error);text-decoration-thickness:1.25px;text-underline-offset:3px;color:var(--error)}',
    '.tgeo-aviso{position:absolute;right:6px;display:flex;align-items:center;height:16px;padding:0 6px;border-radius:4px;background:var(--error);color:var(--sobre-error);font:700 11px/1 var(--f);white-space:nowrap;pointer-events:none;overflow:hidden;text-overflow:ellipsis}',
    '.tgeo-errores{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:2px;font-size:11.5px;color:var(--error);user-select:text}',
    '.tgeo-errores li{overflow-wrap:anywhere;min-width:0}',
    '.tgeo-errores b{font-family:var(--mono);margin-right:6px}'
  ].join('\n');

  var PH = 'Un objeto por línea:\nA=(0,0)\nB=(6,0)\nC=(2,5)\nt=triangulo(A,B,C)\n# 3D (se gira con el ratón):\n# e=esfera((0,0,0),1)';
  var area, canal, resalte, avisos, lista, nota, temporizador = null, errActuales = [];
  // 3D: la figura girable (gir) vive en el lienzo de la cáscara; la vista que giró la persona (null: la de la spec) sobrevive a reescribir el guion
  var gir = null, girClave = '', es3 = false, hay3 = false, spec3 = null, externa = null, vistaUsuario = null, vistaGuion = null;
  var copiaEsc = null, copiaClave = '', tNotif = null, girExtra = '';
  var OPC3D = /^(color|opacidad|eje|angulo|angulos|corte|capa|malla|n|ecuador|flecha)$/, PAL3D = /^(no|igual|cubo|opaco|transparente)$/;

  function F() { return window.Figuras; }
  function F3() { return window.Figuras3D; }
  function tema() { return (window.Tarjeta && window.Tarjeta.tema) === 'oscuro' ? 'oscuro' : 'claro'; }
  function el(tag, cls, html) { var e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; }
  function cambio() { if (window.Tarjeta && window.Tarjeta.cambio) window.Tarjeta.cambio(); }
  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

  // ---- colores: lo que va seguido de «(» es un comando; el resto de letras, un punto o un nombre ----
  function colorear(t) {
    return t.replace(/("[^"]*")|(#.*$)|(-?\d*\.?\d+)|([A-Za-zñÑáéíóúÁÉÍÓÚüÜ][A-Za-z0-9ñÑáéíóúÁÉÍÓÚüÜ_']*)(\s*\()?/g, function (m, s, c, n, id, par, pos, todo) {
      if (s) return '<span class="k-txt">' + esc(s) + '</span>';
      if (c) return '<span class="k-com">' + esc(c) + '</span>';
      if (n) return '<span class="k-num">' + n + '</span>';
      if (!par) {                                       // 3D: «color=azul», «eje=y»… dentro del paréntesis, y «no», «igual», «cubo» de ejes(no) / proporcion(igual)
        var antes = todo.slice(0, pos), dentro = (antes.match(/\(/g) || []).length > (antes.match(/\)/g) || []).length;
        if (dentro && OPC3D.test(id) && /^\s*=/.test(todo.slice(pos + m.length))) return '<span class="k-opc">' + esc(id) + '</span>';
        if (dentro && PAL3D.test(id) && /(ejes|numeros|nombres|medidas|relleno|proporcion)\s*\([^)]*$/i.test(antes)) return '<span class="k-opc">' + esc(id) + '</span>';
      }
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
    area.placeholder = PH;
    area.addEventListener('input', function () { externa = null; programar(); });
    area.addEventListener('scroll', function () { colocar(); pintar(errActuales); });
    area.addEventListener('keydown', function (e) { if (e.key === 'Tab') { e.preventDefault(); document.execCommand('insertText', false, '  '); } });
    cod.appendChild(resalte); cod.appendChild(area); cod.appendChild(avisos);
    ed.appendChild(cn); ed.appendChild(cod);
    lista = el('ul', 'tgeo-errores'); lista.hidden = true;
    nota = el('p', 'tgeo-nota'); nota.hidden = true;
    raiz.appendChild(ed); raiz.appendChild(lista); raiz.appendChild(nota);
    if (window.ResizeObserver) new ResizeObserver(function () { if (area.offsetParent) pintar(errActuales); }).observe(ed);   // al mostrarse la pestaña, se mide si los mensajes caben
    dibujar();
  }
  function programar() { clearTimeout(temporizador); temporizador = setTimeout(dibujar, 200); }

  // la figura la enseña la cáscara; aquí se marcan los errores del guion
  function dibujar() {
    var guion = area.value, r = null, falla = '';
    es3 = false; hay3 = false; spec3 = null;
    if (externa) {                                       // una figura 3D del chat, sin guion
      es3 = true; spec3 = externa.spec;
      try { hay3 = !!F3().figura(spec3, { tam: 'S' }).svg; } catch (e) { hay3 = false; }
    } else if (guion.trim()) {
      try {
        if (F3() && F3().es3d(guion)) { r = F3().guion(guion, { tema: tema(), tam: 'S' }); es3 = true; spec3 = r.spec; hay3 = !!r.svg; }
        else r = F().geometria(guion, { tema: tema(), tam: 'M' });
      } catch (e) { falla = e.message; }
    }
    errActuales = r ? r.errores.slice() : [];
    if (falla) errActuales.push({ linea: 1, mensaje: falla });
    if (es3) {                                           // si el guion cambia su vista(…), manda el guion; si no, la que giró la persona
      var vg = JSON.stringify((spec3 && spec3.vista) || null);
      if (vistaGuion !== null && vg !== vistaGuion) vistaUsuario = null;
      vistaGuion = vg;
    }
    pintar(errActuales);
    area.placeholder = externa ? '' : PH;
    nota.hidden = !es3 || !hay3;
    nota.textContent = externa ? 'Viene del chat; puedes girarla y copiarla.' : 'Figura 3D: arrastra para girarla; doble clic vuelve a la vista inicial.';
    cambio();
  }

  function igual(a, b) { return !!a && !!b && Math.abs(a[0] - b[0]) < 1e-6 && Math.abs(a[1] - b[1]) < 1e-6; }
  function clave3(extra) { try { return JSON.stringify(spec3) + '|' + extra; } catch (e) { return String(Math.random()); } }

  // anotaciones y relleno que eligió la persona (Tarjeta.opciones): solo lo que apaga o fuerza; lo demás lo decide la spec
  function extra() {
    var o = (window.Tarjeta && window.Tarjeta.opciones) || {}, an = o.anot || {}, a = {}, r = {};
    ['ejes', 'numeros', 'nombres', 'medidas'].forEach(function (k) { if (an[k] === false) a[k] = false; });
    if (Object.keys(a).length) r.anotaciones = a;
    if (o.relleno === 'opaco' || o.relleno === 'transparente') r.relleno = o.relleno;
    return r;
  }
  function conExtra(base) { var e = extra(); for (var k in e) base[k] = e[k]; return base; }

  // la escena de lo que se copia: siempre en estilo claro, con el tamaño S/M/L; se rearma solo si cambia la spec o el tamaño
  function copia() {
    var tam = (window.Tarjeta && window.Tarjeta.opciones && window.Tarjeta.opciones.tam) || 'M', k = clave3(tam + JSON.stringify(extra()));
    if (copiaEsc && copiaClave === k) return copiaEsc;
    try { copiaEsc = F3().escena(spec3, conExtra({ tema: (window.Tarjeta && window.Tarjeta.temaFigura) || 'claro', tam: tam, fondo: 'transparente' })); } catch (e) { copiaEsc = null; }
    copiaClave = k; return copiaEsc;
  }
  function vistaActual() { return gir ? gir.vista() : (vistaUsuario || (copia() && copia().vista) || null); }

  // la cáscara pide el lienzo: aquí vive la figura girable (se rehace solo si cambia la spec o el tema)
  function vivo(caja, t) {
    var k = clave3(t), ex = JSON.stringify(extra());
    if (gir && girClave === k && caja.firstChild) {        // mismas figura y tema: si solo cambian anotaciones o relleno, se rehace en la misma vista
      if (girExtra !== ex) { girExtra = ex; var o = { anotaciones: undefined, relleno: undefined }; gir.cambiar(conExtra(o)); }
      return;
    }
    soltar();
    var enConstruccion = true, base = copia() ? copia().vista : null;
    girExtra = ex;
    gir = F3().girable(caja, spec3, conExtra({
      tema: t, tam: 'M', fondo: 'transparente', vista: vistaUsuario || undefined,
      alGirar: function (v, rapido) {
        if (enConstruccion) return;
        vistaUsuario = igual(v, base) ? null : v;        // la vista inicial no cuenta como «la giró»
        if (!rapido) { clearTimeout(tNotif); tNotif = setTimeout(cambio, 120); }
      }
    }));
    enConstruccion = false; girClave = k;
  }
  function soltar() { if (gir) { try { gir.destruir(); } catch (e) {} } gir = null; girClave = ''; }

  // el GIF: los fotogramas de la vista actual, con el tamaño, el fondo, las anotaciones y el relleno elegidos y en estilo claro
  // (giro: 'vaiven' | 'vuelta') → Promise<{fotos, ms, w, h}>; la cáscara los pasa a Python (tarjeta.py: copiar_gif)
  function fotogramas(giro) {
    var o = (window.Tarjeta && window.Tarjeta.opciones) || {}, e = copia();
    if (!es3 || !hay3 || !e) return Promise.reject(new Error('El GIF es para figuras 3D'));
    return F3().fotogramas(e, conExtra({ tema: (window.Tarjeta && window.Tarjeta.temaFigura) || 'claro', tam: o.tam || 'M',
                                         fondo: o.fondo === 'blanco' ? 'blanco' : 'transparente', vista: vistaActual(), giro: giro, n: 48 }));
  }

  var SVG_VACIO = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 10 10"/>';
  function figura(t) {
    if (!area || (!area.value.trim() && !externa)) return null;
    if (es3) {
      if (!hay3) return null;
      if (t) return { svg: SVG_VACIO, nombre: 'figura3d', vivo: function (caja) { vivo(caja, t); } };   // para enseñarla: la cáscara le pide el lienzo
      try {
        var e = copia(); if (!e) return null;
        var s = e.dibujar(vistaActual(), { encuadre: 'justo', fondo: 'transparente' }).svg;
        return s ? { svg: s, nombre: 'figura3d' } : null;
      } catch (x) { return null; }
    }
    try {
      var tam = (window.Tarjeta && window.Tarjeta.opciones && window.Tarjeta.opciones.tam) || 'M';
      var r = F().geometria(area.value, { tema: t || (window.Tarjeta && window.Tarjeta.temaFigura) || 'claro', tam: tam, fondo: 'transparente' });
      return r.svg ? { svg: r.svg, nombre: 'geometria' } : null;
    } catch (e) { return null; }
  }
  function cargar(c) {
    if (c && c.tipo === '3d' && c.spec) {                 // del chat, sin guion: figura girable + aviso
      var sp = c.spec; if (typeof sp === 'string') { try { sp = JSON.parse(sp); } catch (e) { return; } }
      area.value = ''; externa = { spec: sp };
      vistaUsuario = Array.isArray(c.vista) ? c.vista : null; vistaGuion = JSON.stringify((sp && sp.vista) || null);
      clearTimeout(temporizador); dibujar(); return;
    }
    var g = c && (c.guion != null ? c.guion : c.script);
    if (g == null) return;
    externa = null; vistaUsuario = null;
    area.value = String(g).replace(/\r\n/g, '\n');
    clearTimeout(temporizador); dibujar();
  }
  function estado() { return { guion: area ? area.value : '', vista: vistaUsuario }; }
  function restaurar(s) {
    if (s && typeof s.guion === 'string') {
      area.value = s.guion; externa = null; vistaUsuario = Array.isArray(s.vista) ? s.vista : null;
      clearTimeout(temporizador); dibujar();
    }
  }

  window.Tarjeta.registrar('geometria', { titulo: 'Geometría', icono: 'geometria', montar: montar, figura: figura, fotogramas: fotogramas, soltar: soltar, cargar: cargar, estado: estado, restaurar: restaurar });
})();
