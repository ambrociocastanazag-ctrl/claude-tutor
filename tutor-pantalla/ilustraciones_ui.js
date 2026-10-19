/* Ilustraciones dentro del chat de los tutores (contrato: CONTRATO-MARCAS.md §7; lo que escriben los tutores:
   REGLAS_ILUSTRACIONES en ojos_panel.py).  window.Ilustraciones:
     antes(texto)      → el texto del tutor con las fórmulas $…$ / $$…$$ y los bloques ```svg / ```grafica cambiados por
                         marcas (\u0002id\u0003); la página lo llama al principio de bloques(), antes de escapar el texto.
                         Un bloque a medias (respuesta que llega a trozos) queda como «dibujando…»; un $$ sin cerrar, como texto.
     procesar(nodo)    → cambia esas marcas, dentro de nodo, por la fórmula, la figura o la gráfica (también lo hace solo un
                         MutationObserver, así que basta con pintar el HTML).
     compilar(expr)    → función x → número de una expresión («2x+1», «sin(x)/x», «sqrt(4-x^2)»); intérprete propio, sin eval.
     grafica(spec, P)  → texto SVG de una gráfica de funciones (spec = el JSON de ```grafica).
   Los bloques ```svg, ```grafica y ```geometria (un guion con el lenguaje de MathStudio) se dibujan con Figuras (motor_figuras.js, que
   tiene que estar inyectado ANTES que este archivo). Cada figura lleva «Editar en la tarjeta» si el panel ofrece api.tarjeta_abrir.
   Las figuras se muestran como <img> de un SVG ya filtrado (Dibujante.U.limpiarSvg): lo que traiga no puede ejecutar nada
   ni tocar los estilos de la página. Los colores por NOMBRE (tinta, suave, fondo, acento, azul…) se resuelven con el tema
   actual y se rehacen al cambiar de tema. */
(function(){
  'use strict';
  var NAV = typeof document !== 'undefined';
  var RAIZ = NAV ? window : {};

  // =====================================================================================================
  // 1. El motor de figuras (intérprete de expresiones, gráficas y geometría) vive en motor_figuras.js, común con la Tarjeta SVG.
  //    En el panel se inyecta ANTES que este archivo (SCRIPTS_UI de ojos_panel.py); en node se carga con require.
  // =====================================================================================================
  var F = (typeof Figuras !== 'undefined') ? Figuras : (typeof require === 'function' ? require('./motor_figuras.js') : null);
  var compilar = F ? F.compilar : function(){ throw new Error('falta motor_figuras.js'); };
  var ANCHO_CHAT = 520;
  var ACENTOS = {
    claro: {azul: '#2a5fd0', verde: '#1d8a4a', rojo: '#d23a3a', naranja: '#d9741a', morado: '#7b45c9', amarillo: '#c9980a'},
    oscuro: {azul: '#6ea1ff', verde: '#4cc47f', rojo: '#ff7f7c', naranja: '#ffa650', morado: '#b68cff', amarillo: '#f2cf50'}
  };
  var P_CLARA = {modo: 'claro', tinta: '#2a2d3a', suave: '#d9d6cc', fondo: '#fcfbf8', acento: '#4a54c9'};
  var FUENTE = "'Segoe UI', system-ui, sans-serif";
  function tiene(o, k){ return Object.prototype.hasOwnProperty.call(o, k); }
  function paletaPor(base){                                 // {tinta, suave, fondo, acento} + los acentos por nombre del modo
    var P = {}, a = ACENTOS[base.modo] || ACENTOS.claro, k;
    for (k in base) P[k] = base[k];
    for (k in a) P[k] = a[k];
    return P;
  }
  function redondo(v){ return Math.round(v * 10) / 10; }
  function grafica(spec, P){                                // texto SVG de una gráfica (la API de siempre)
    if (!F) throw new Error('falta motor_figuras.js');
    return F.grafica(spec, {paleta: P || paletaPor(P_CLARA), tema: (P && P.modo) || 'claro', ancho: ANCHO_CHAT}).svg;
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
    var m = /^[ \t]*(svg|grafica|gráfica|geometria|geometría)(?=[ \t\r\n]|$)([^\n]*)(?:\n([\s\S]*))?$/i.exec(p);
    if (!m){
      var w = p.trim().toLowerCase();
      if (!cerrado && w && p.indexOf('\n') < 0 && ('svg'.indexOf(w) === 0 || 'grafica'.indexOf(w) === 0 || 'gráfica'.indexOf(w) === 0 || 'geometria'.indexOf(w) === 0 || 'geometría'.indexOf(w) === 0))
        return marca({tipo: 'hueco', texto: 'dibujando…'}, 'hueco');
      return null;
    }
    var esSvg = m[1].toLowerCase() === 'svg', esGeo = /^geometr/i.test(m[1]);
    if (!cerrado) return marca({tipo: 'hueco', texto: esSvg || esGeo ? 'dibujando la figura…' : 'dibujando la gráfica…'}, 'hueco' + (esSvg ? 's' : esGeo ? 'm' : 'g'));
    if (esSvg){
      var pie = m[2].trim(), cuerpo = (m[3] || '').trim();
      if (!cuerpo && /^<svg/i.test(pie)){ cuerpo = pie; pie = ''; }
      return marca({tipo: 'svg', cuerpo: cuerpo, pie: pie}, 's' + pie + '\n' + cuerpo);
    }
    var json = (m[2] + '\n' + (m[3] || '')).trim();
    if (esGeo) return marca({tipo: 'geometria', guion: json}, 'm' + json);
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
  var API = {antes: antes, compilar: compilar, grafica: grafica, paletaPor: paletaPor, etiquetaPi: F && F._etiquetaPi, _reg: REG};
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
    '.ilu-latex.ilu-editar{right:92px;width:26px;padding:0;display:grid;place-items:center}',
    '.ilu-latex.ilu-editar svg{width:14px;height:14px}',
    '.ilu-bloque.con-editar{padding-right:124px}',
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
    app: icono('<path d="M5 4l14 7-6 2-2 6z"/>'),
    tarjeta: icono('<path d="M4 20l1-4L16.5 4.5a2.1 2.1 0 0 1 3 3L8 19l-4 1zM14 7l3 3"/>')
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
    var ap = RAIZ.pywebview && RAIZ.pywebview.api;
    if (ap && ap.tarjeta_abrir){                            // «Editar en la tarjeta»: la fórmula pasa a la pestaña Escribir
      var e = document.createElement('button'); e.type = 'button'; e.className = 'ilu-latex ilu-editar'; e.title = 'Editar en la tarjeta'; e.setAttribute('aria-label', 'Editar en la tarjeta'); e.innerHTML = IC.tarjeta;
      e.addEventListener('click', function(){ Promise.resolve(ap.tarjeta_abrir({tipo: 'latex', latex: tex})).then(function(res){ if (res && res.ok === false) avisar(e, res.error || 'No pude abrir la tarjeta', true); }); });
      cont.appendChild(e); cont.classList.add('con-editar');
    }
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
      if (!F) return {aviso: 'el motor de figuras no está disponible'};
      var g = F.grafica(spec, {paleta: P, tema: P.modo, ancho: ANCHO_CHAT});
      return {svg: g.svg, w: g.w, h: g.h, pie: spec.pie ? String(spec.pie).slice(0, 200) : '', spec: spec};
    } catch (e3) { return {aviso: 'No pude dibujar la gráfica: ' + String(e3.message).slice(0, 140)}; }
  }
  function geometriaTexto(guion, P){                        // guion de MathStudio → figura; los errores salen por línea y lo válido se dibuja igual
    if (!F) return {aviso: 'el motor de figuras no está disponible'};
    var g;
    try { g = F.geometria(guion, {paleta: P, tema: P.modo, ancho: ANCHO_CHAT}); }
    catch (e) { return {aviso: 'No pude dibujar la figura: ' + String(e.message || e).slice(0, 140)}; }
    if (!g.svg){
      var m = g.errores.length ? g.errores.slice(0, 4).map(function(x){ return 'Línea ' + x.linea + ': ' + x.mensaje; }).join(' · ') : 'el guion está vacío';
      return {aviso: 'No pude dibujar la figura. ' + m};
    }
    return {svg: g.svg, w: g.w, h: g.h, errores: g.errores};
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
  function editarEnTarjeta(fig, btn){                       // abre la figura en la Tarjeta SVG para retocarla (api.tarjeta_abrir lo pone el panel)
    var a = RAIZ.pywebview && RAIZ.pywebview.api, reg = fig._reg, r = fig._r, contenido;
    if (!a || !a.tarjeta_abrir){ avisar(btn, 'Este panel no puede abrir la tarjeta', true); return; }
    if (reg.tipo === 'geometria') contenido = {tipo: 'geometria', guion: reg.guion};
    else if (reg.tipo === 'grafica' && r.spec) contenido = {tipo: 'grafica', spec: r.spec};
    else contenido = {tipo: 'svg', svg: fig._svg};
    Promise.resolve(a.tarjeta_abrir(contenido)).then(function(res){
      if (res && res.ok === false) avisar(btn, res.error || 'No pude abrir la tarjeta', true);
    }, function(e){ avisar(btn, String((e && e.message) || e).slice(0, 100), true); });
  }
  function hayTarjeta(){ var a = RAIZ.pywebview && RAIZ.pywebview.api; return !!(a && a.tarjeta_abrir); }
  function rellenarFigura(fig){
    var reg = fig._reg, P = paleta(), r;
    try { r = reg.tipo === 'svg' ? svgTexto(reg.cuerpo, P) : reg.tipo === 'geometria' ? geometriaTexto(reg.guion, P) : graficaTexto(reg.json, P); } catch (e) { r = {aviso: 'No pude dibujar la figura: ' + String(e.message || e).slice(0, 120)}; }
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
    if (r.errores && r.errores.length){                     // geometría: se dibujó lo válido y cada error sale con su línea
      var av2 = document.createElement('div'); av2.className = 'ilu-aviso'; av2.innerHTML = '<b>⚠</b><span></span>';
      av2.lastChild.textContent = r.errores.slice(0, 5).map(function(x){ return 'Línea ' + x.linea + ': ' + x.mensaje; }).join('\n');
      av2.lastChild.style.whiteSpace = 'pre-line';
      lienzo.parentNode.insertBefore(av2, pie); fig._aviso = av2;
    }
    var im = document.createElement('img'); im.alt = reg.pie || (reg.tipo === 'grafica' ? 'Gráfica' : 'Figura'); im.draggable = false;
    im.style.maxWidth = r.w + 'px'; im.setAttribute('width', r.w); im.setAttribute('height', r.h); im.src = urlSvg(r.svg);
    lienzo.appendChild(im);
    [['ampliar', 'Ampliar', function(b){ ampliar(fig); }],
     ['copiar', 'Copiar SVG', function(b){ copiarTexto(fig._svg).then(function(ok){ avisar(b, ok ? 'SVG copiado' : 'No pude copiar', !ok); }); }],
     ['png', 'Guardar PNG', function(b){ guardarPng(fig, b); }],
     ['app', 'Ponlo en la app', function(b){ ponerEnApp(fig, b); }]].concat(hayTarjeta() ? [['tarjeta', 'Editar en la tarjeta', function(b){ editarEnTarjeta(fig, b); }]] : []).forEach(function(d){
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
  if (RAIZ.addEventListener) RAIZ.addEventListener('pywebviewready', function(){          // ahora sí hay api: las figuras ya hechas ganan su botón de la tarjeta
    Array.prototype.forEach.call(document.querySelectorAll('.ilu-fig'), rellenarFigura);
  });
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
