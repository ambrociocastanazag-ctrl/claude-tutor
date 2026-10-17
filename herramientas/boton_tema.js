/* Botón de tema claro ↔ oscuro para los artefactos (guías, figuras, fichas).
   Lo mete boton_tema.py dentro de cada HTML; no se carga suelto.

   - Cambia data-theme="light" | "dark" en <html>: el CSS de los artefactos ya
     tiene los dos temas con esa regla, y las guías redibujan sus figuras al
     ver cambiar ese atributo.
   - Recuerda la elección en este artefacto (localStorage). Sin elección, sigue
     el tema de Windows, como antes.
   - Lo pasa también a los <iframe> de la misma página (figuras de anatomy).
   - Si la página tiene un elemento con [data-boton-tema], el botón va ahí;
     si no, flota arriba a la derecha. */
(function () {
  const CLAVE = 'tema-artefacto';
  const raiz = document.documentElement;
  const sistema = matchMedia('(prefers-color-scheme: dark)');
  const actual = () => raiz.dataset.theme || (sistema.matches ? 'dark' : 'light');
  let boton = null;

  const SOL = '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>';
  const LUNA = '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>';

  function aIframes(t) {
    for (const f of document.querySelectorAll('iframe')) {
      try { if (f.contentDocument) f.contentDocument.documentElement.dataset.theme = t; } catch (e) { /* otro origen */ }
    }
  }

  function pintar() {
    if (!boton) return;
    const oscuro = actual() === 'dark';
    // Muestra lo que pasará al pulsar: en oscuro, el sol (pasar a claro).
    boton.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (oscuro ? SOL : LUNA) + '</svg>';
    const txt = oscuro ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro';
    boton.title = txt; boton.setAttribute('aria-label', txt);
  }

  function aplicar(t, guardar) {
    raiz.dataset.theme = t;
    aIframes(t);
    if (guardar) { try { localStorage.setItem(CLAVE, t); } catch (e) { /* sin almacenamiento */ } }
    pintar();
  }

  try { const g = localStorage.getItem(CLAVE); if (g === 'light' || g === 'dark') aplicar(g, false); } catch (e) { /* nada */ }
  sistema.addEventListener('change', () => { if (!raiz.dataset.theme) pintar(); });
  // Los iframes que cargan después también reciben el tema elegido.
  document.addEventListener('load', e => {
    if (e.target.tagName === 'IFRAME' && raiz.dataset.theme) aIframes(raiz.dataset.theme);
  }, true);

  function crear() {
    const estilo = document.createElement('style');
    estilo.textContent =
      '.boton-tema{display:inline-grid;place-items:center;width:36px;height:36px;padding:0;border-radius:10px;cursor:pointer;' +
      'color:inherit;background:rgb(128 128 128 / .14);border:1px solid rgb(128 128 128 / .32);transition:background .15s}' +
      '.boton-tema:hover{background:rgb(128 128 128 / .26)}' +
      '.boton-tema:focus-visible{outline:2px solid currentColor;outline-offset:2px}' +
      '.boton-tema.flota{position:fixed;top:12px;right:12px;z-index:2147483000;color:CanvasText;background:Canvas;' +
      'box-shadow:0 4px 14px rgb(0 0 0 / .18)}';
    document.head.appendChild(estilo);
    boton = document.createElement('button');
    boton.type = 'button';
    boton.className = 'boton-tema';
    boton.addEventListener('click', () => aplicar(actual() === 'dark' ? 'light' : 'dark', true));
    const sitio = document.querySelector('[data-boton-tema]');
    if (sitio) sitio.appendChild(boton);
    else { boton.classList.add('flota'); document.body.appendChild(boton); }
    pintar();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', crear);
  else crear();
})();
