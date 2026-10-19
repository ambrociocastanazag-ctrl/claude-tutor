/* Pestaña «Escribir» de la Tarjeta SVG (contrato §2).
 * Campo de ecuación (MathLive, con los atajos de MathStudio de atajos.js) arriba y debajo la
 * ecuación dibujada grande con MathJax. figura() devuelve el SVG con la misma holgura que
 * conHolgura() de MathStudio (nunca la tinta pegada al borde), en px, con tinta según el tema
 * y fondo transparente.
 *
 * Todo lo que necesita lo carga ella sola, con rutas calculadas desde su propio <script src>
 * (así no importa desde dónde se sirva la página):
 *   - MathLive:  <esta carpeta>/vendor/mathlive/mathlive.min.js  (+ mathlive-fonts.css y fonts/)
 *   - MathJax:   <raíz>/tutor-pantalla/vendor/tex-svg.js   (si la página no trae ya MathJax)
 * Se puede forzar con window.TARJETA_RUTAS = {mathlive: '/ruta/mathlive/', mathjax: '/ruta/tex-svg.js'}.
 * Clases CSS con prefijo te- (el diseño las reestilizará); el CSS provisional va en un <style id="te-estilo">.
 */
(function () {
  'use strict';

  var ACTUAL = document.currentScript && document.currentScript.src;
  var RUTAS = window.TARJETA_RUTAS || {};
  var BASE_ML = RUTAS.mathlive || (ACTUAL ? new URL('vendor/mathlive/', ACTUAL).href : 'vendor/mathlive/');
  var URL_MJ = RUTAS.mathjax || (ACTUAL ? new URL('../tutor-pantalla/vendor/tex-svg.js', ACTUAL).href : '../tutor-pantalla/vendor/tex-svg.js');

  // ---- La holgura de MathStudio (js/exportar.js, entrada del 2026-08-31) ----
  // MathJax deja la tinta pegada al borde del viewBox y mide en `ex`. Se añade margen al viewBox y
  // se fijan width/height en px (el viewBox está en milésimas de em; 1ex = 0.442em).
  var HOLGURA_EX = 0.15;
  var EM_PX = 16;
  var TINTA = { claro: '#1b1f24', oscuro: '#e8eaed' };

  function neat(n) { return Math.abs(n) < 1e-9 ? '0' : String(+n.toFixed(8)); }

  function conHolgura(svg) {
    var caja = (svg.getAttribute('viewBox') || '').trim().split(/[\s,]+/).map(Number);
    var altoEx = parseFloat(svg.getAttribute('height'));
    if (caja.length !== 4 || caja.some(function (n) { return !isFinite(n); })) return svg;
    if (!(caja[3] > 0) || !(altoEx > 0)) return svg;
    var porEx = caja[3] / altoEx;
    var m = HOLGURA_EX * porEx;
    var nueva = [caja[0] - m, caja[1] - m, caja[2] + 2 * m, caja[3] + 2 * m];
    var px = function (u) { return neat(u * EM_PX / 1000); };
    svg.setAttribute('viewBox', nueva.map(neat).join(' '));
    svg.setAttribute('width', px(nueva[2]) + 'px');
    svg.setAttribute('height', px(nueva[3]) + 'px');
    return svg;
  }

  function limpiar(latex) { return String(latex || '').replace(/\\placeholder\{\}/g, '').replace(/#\?/g, '').trim(); }

  // ---- carga perezosa de las librerías ----
  function cargarScript(src) {
    return new Promise(function (ok, mal) {
      var s = document.createElement('script');
      s.src = src; s.onload = ok; s.onerror = function () { mal(new Error('No se pudo cargar ' + src)); };
      document.head.appendChild(s);
    });
  }
  function cargarMathLive() {
    if (customElements.get('math-field')) return Promise.resolve();
    if (!document.getElementById('te-fuentes')) {            // @font-face estáticos: MathLive los ve en document.fonts
      var l = document.createElement('link');
      l.id = 'te-fuentes'; l.rel = 'stylesheet'; l.href = BASE_ML + 'mathlive-fonts.css';
      document.head.appendChild(l);
    }
    return cargarScript(BASE_ML + 'mathlive.min.js').then(function () { return customElements.whenDefined('math-field'); });
  }
  function mjListo() { return window.MathJax && window.MathJax.tex2svg && window.MathJax.startup && window.MathJax.startup.document; }
  function cargarMathJax() {
    if (mjListo()) return Promise.resolve();
    if (!window.MathJax) {
      window.MathJax = { tex: { packages: { '[+]': ['ams'] } }, svg: { fontCache: 'none' }, options: { enableMenu: false },
                         startup: { typeset: false }, loader: { load: [] } };
    }
    var p = window.MathJax.tex2svg ? Promise.resolve() : cargarScript(URL_MJ);
    return p.then(function () {
      return new Promise(function (ok) { (function esperar() { if (mjListo()) ok(); else setTimeout(esperar, 30); })(); });
    });
  }

  // ---- CSS (diseño de Claude Design; los colores salen de los tokens de la cáscara) ----
  var CSS = [
    '.te-raiz{display:flex;flex-direction:column;gap:6px;min-width:0}',
    '.te-campo{display:block;width:100%;min-height:60px;padding:8px 10px;font-size:22px;border:1px solid var(--borde);border-radius:8px;background:var(--sup);color:var(--tinta);outline:none;--caret-color:var(--acento);--selection-background-color:var(--acento-suave);--primary:var(--acento)}',
    '.te-campo:focus-within{border-color:var(--acento);box-shadow:0 0 0 2px var(--acento-suave)}',
    '.te-campo::part(virtual-keyboard-toggle),.te-campo::part(menu-toggle){display:none}',   // sin teclado ni menú: pocos botones
    '.te-campo:not(:defined){font:500 14px var(--mono);color:var(--tenue);display:flex;align-items:center}',
    '.te-pie{display:flex;align-items:center;gap:6px;min-height:22px}',
    '.te-aviso{flex:1;min-width:0;font-size:12px;color:var(--error);overflow-wrap:anywhere}',
    '.te-boton{flex:none;height:22px;padding:0 8px;border:0;border-radius:5px;background:none;font-size:12px;font-weight:600;color:var(--tenue)}',
    '.te-boton:hover{background:var(--sup-2);color:var(--tinta)}'
  ].join('');
  function ponerCss() {
    if (document.getElementById('te-estilo')) return;
    var s = document.createElement('style'); s.id = 'te-estilo'; s.textContent = CSS; document.head.appendChild(s);
  }

  // ---- la pestaña ----
  var cont, mf, aviso;
  var listo = false, temporizador = 0, valorPendiente = null;

  function tema() { return (window.Tarjeta && window.Tarjeta.tema) === 'oscuro' ? 'oscuro' : 'claro'; }
  function tinta(t) {
    t = t || tema();
    var e = window.Figuras && window.Figuras.estilo && window.Figuras.estilo[t];
    return (e && (e.tinta || e.texto)) || TINTA[t];
  }

  // LaTeX → {svg} | {error} | null (vacío). Síncrono una vez cargado MathJax. paraCopiar: con la tinta del tema claro
  // (Tarjeta.temaFigura: sobre un fondo blanco una tinta clara no se vería) o, si es 'claro'|'oscuro', con la de ese tema.
  function dibujar(latex, paraCopiar) {
    var tex = limpiar(latex);
    if (!tex) return null;
    var nodo = window.MathJax.tex2svg(tex, { display: true });
    var s = nodo.querySelector('svg');
    if (!s) return { error: 'No se pudo dibujar la ecuación.' };
    var err = nodo.querySelector('[data-mjx-error]');
    if (err) return { error: err.getAttribute('data-mjx-error') };
    s = s.cloneNode(true);
    s.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    s.removeAttribute('role'); s.removeAttribute('focusable');
    s.removeAttribute('style');                                 // vertical-align solo sirve en línea dentro de HTML
    conHolgura(s);
    var t = paraCopiar === 'claro' || paraCopiar === 'oscuro' ? paraCopiar : paraCopiar ? ((window.Tarjeta && window.Tarjeta.temaFigura) || 'claro') : tema();
    return { svg: new XMLSerializer().serializeToString(s).replace(/currentColor/g, tinta(t)) };
  }

  // la ecuación dibujada la enseña la cáscara en su figura central; aquí solo se avisa si no vale
  function actualizar() {
    if (!listo) return;
    var r = dibujar(mf.getValue('latex-without-placeholders'));
    aviso.textContent = r && r.error ? 'La ecuación no es válida todavía: ' + r.error : '';
    if (window.Tarjeta && window.Tarjeta.cambio) window.Tarjeta.cambio();
  }

  function programar() { clearTimeout(temporizador); temporizador = setTimeout(actualizar, 90); }

  function copiarTexto(t) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(t);
    return new Promise(function (ok, mal) {
      var a = document.createElement('textarea');
      a.value = t; a.setAttribute('readonly', ''); a.style.cssText = 'position:fixed;opacity:0;pointer-events:none';
      document.body.appendChild(a); a.select();
      var bien = document.execCommand('copy'); a.remove();
      bien ? ok() : mal(new Error('El portapapeles está bloqueado'));
    });
  }

  function montar(contenedor) {
    ponerCss();
    cont = contenedor;
    cont.classList.add('te-raiz');
    cont.setAttribute('data-tema', tema());
    cont.innerHTML =
      '<math-field class="te-campo" aria-label="Campo de ecuación"></math-field>' +
      '<div class="te-pie"><div class="te-aviso" role="status"></div>' +
      '<button type="button" class="te-boton te-latex" title="Copiar el código LaTeX ($$…$$)">Copiar LaTeX</button></div>';
    mf = cont.querySelector('math-field'); aviso = cont.querySelector('.te-aviso');
    cont.querySelector('.te-latex').onclick = function () {
      var t = listo ? limpiar(mf.getValue('latex-without-placeholders')) : '';
      var T = window.Tarjeta;
      if (!t) return T && T.aviso('Escribe una ecuación primero');
      copiarTexto('$$' + t + '$$').then(function () { T && T.aviso('LaTeX copiado'); },
                                         function () { T && T.aviso('No se pudo copiar'); });
    };

    Promise.all([cargarMathLive(), cargarMathJax()]).then(function () {
      var M = window.MathfieldElement;
      if (M) { M.fontsDirectory = BASE_ML + 'fonts'; M.soundsDirectory = null; M.plonkSound = null; }
      mf.mathVirtualKeyboardPolicy = 'manual';                  // sin teclado en pantalla
      window.Atajos.configurar(mf);
      mf.addEventListener('input', programar);
      listo = true;
      if (valorPendiente != null) { mf.setValue(valorPendiente, { silenceNotifications: true }); valorPendiente = null; }
      actualizar();
    }).catch(function (e) {
      aviso.textContent = String((e && e.message) || e);
    });

    // cambio de tema: se vuelve a pintar con la otra tinta
    new MutationObserver(function () { cont.setAttribute('data-tema', tema()); actualizar(); })
      .observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'data-tema'] });
  }

  function poner(latex) {
    if (listo) { mf.setValue(latex, { silenceNotifications: true }); actualizar(); }
    else valorPendiente = latex;
  }

  window.Tarjeta.registrar('escribir', {
    titulo: 'Escribir',
    icono: 'ecuacion',
    montar: montar,
    figura: function (tema) {                                   // tema ('claro'|'oscuro'): para enseñarla en la ventana; sin él, la que se copia
      if (!listo) return null;
      var r = dibujar(mf.getValue('latex-without-placeholders'), tema || true);
      return r && r.svg ? { svg: r.svg, nombre: 'ecuacion' } : null;
    },
    cargar: function (c) { if (c && c.tipo === 'latex') poner(String(c.latex || '')); },
    estado: function () { return { latex: listo ? mf.getValue('latex') : (valorPendiente || '') }; },
    restaurar: function (e) { if (e && typeof e.latex === 'string') poner(e.latex); },
    // la cáscara puede llamarlo al cambiar el tema o al mostrar la pestaña
    tema: function () { if (cont) { cont.setAttribute('data-tema', tema()); actualizar(); } }
  });
})();
