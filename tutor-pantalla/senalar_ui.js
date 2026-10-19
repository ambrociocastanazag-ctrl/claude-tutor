/* Señalar y preguntar (senalar.py): el botón ✏️ «Señalar» junto a la cámara 📷. La persona encierra con el ratón algo de la app y
   le pregunta al tutor «¿qué es esto?». ojos_panel.inyectar_ui() mete este archivo en la página (después de ojos_ui.js).

   Flujo: ✏️ → la ventana que ya enseñó (api.senalar_ventana) o la lista de ojos_ui.js (la misma de 📷) → api.senalar_empezar(hwnd)
   (una capa encima de la app; dibuja con el ratón, Esc cancela) → api.senalar_capturar(hwnd, trazo) → la vista previa de siempre
   (Adjuntar / Recortar / Cancelar) con el trazo pintado → adjunto del mensaje. Nada sale sin «Adjuntar» y sin enviar.
   Usa window.adjuntarExterno(adjunto), que ya tienen los paneles para las fotos del celular. Si cancela en cualquier paso, no pasa nada.

   Senalar.empezar()   hace lo mismo que pulsar el botón. */
(function(){
  if (window.Senalar) return;
  var css = '' +
    '.sn-aviso{position:fixed;left:50%;top:12px;transform:translateX(-50%);z-index:1100;max-width:calc(100vw - 24px);display:flex;align-items:center;gap:9px;' +
      'padding:9px 14px;border-radius:12px;background:var(--bg,#fff);color:var(--ink,#222);border:1px solid var(--acc,#e07b00);' +
      'box-shadow:0 6px 24px rgba(0,0,0,.22);font:600 13px/1.4 var(--sans,system-ui,sans-serif);overflow-wrap:anywhere}' +
    '.sn-aviso svg{flex-shrink:0;color:var(--acc,#e07b00)} .sn-aviso small{display:block;font-weight:500;color:var(--ink2,#666)}' +
    '.sn-aviso button{flex-shrink:0;margin-left:4px;border:1px solid var(--line,#ccc);background:var(--surface,#f4f4f4);color:inherit;border-radius:8px;padding:4px 10px;font:inherit;font-weight:650;cursor:pointer}';
  var st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);

  var PENCIL = 'M4 20l1-4.5L16.5 4a2.1 2.1 0 0 1 3 3L8 18.5zM14.5 6l3.5 3.5';
  function ic(t){
    if (window.Marcas && window.Marcas.iconos) return window.Marcas.iconos.senalar(t || 15);        // ícono del kit de Claude Design
    return '<svg width="' + (t || 15) + '" height="' + (t || 15) + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="' + PENCIL + '"/></svg>'; }
  function api(){ return window.pywebview && window.pywebview.api; }
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }

  var aviso = null, activo = false;
  function quitarAviso(){ if (aviso){ aviso.remove(); aviso = null; } }
  function poner(html, ms){
    quitarAviso();
    aviso = document.createElement('div'); aviso.className = 'sn-aviso'; aviso.setAttribute('role', 'status'); aviso.innerHTML = html;
    document.body.appendChild(aviso);
    if (ms){ var a = aviso; setTimeout(function(){ if (aviso === a) quitarAviso(); }, ms); }
  }

  function tomar(hwnd){
    activo = true;
    poner(ic(18) + '<span>Encierra lo que quieres preguntar, en la app<small>Arrastra con el ratón · Esc o clic derecho para cancelar</small></span>' +
          '<button type="button" class="sn-cancelar">Cancelar</button>');
    aviso.querySelector('.sn-cancelar').onclick = function(){ if (api().senalar_cancelar) api().senalar_cancelar(); };
    api().senalar_empezar(hwnd).then(function(r){
      activo = false; quitarAviso();
      if (!r || !r.ok){
        if (r && r.error && !r.cancelado) poner('<span>' + esc(r.error) + '</span>', 4500);
        return;                                                     // cancelado: no pasa nada
      }
      // La vista previa de siempre, con la captura que trae el trazo pintado. Adjuntar → adjunto pendiente; sale solo al enviar.
      Ojos.mirar(hwnd, function(a){ if (window.adjuntarExterno) window.adjuntarExterno(a); }, null,
                 {captura: function(){ return api().senalar_capturar(hwnd, r.trazo); }});
    }, function(){ activo = false; quitarAviso(); });
  }

  function empezar(){
    var a = api();
    if (activo || !a || !a.senalar_empezar || !window.Ojos) return;
    var elegida = (document.getElementById('ventana') || {dataset: {}}).dataset.hwnd;        // el asistente: la ventana que ya eligió
    if (elegida) return tomar(+elegida);
    a.senalar_ventana().then(function(v){
      if (v && v.ok) return tomar(v.hwnd);
      Ojos.elegir(function(w){ tomar(w.hwnd); });
    }, function(){ Ojos.elegir(function(w){ tomar(w.hwnd); }); });
  }

  // ---- El botón, junto a la cámara (#mirarVentana en los paneles de Excel/Dia/curso, #mirar «Que mire» en el asistente) ----
  function instalar(intento){
    var cam = document.getElementById('mirarVentana') || document.getElementById('mirar');
    var a = api();
    if (!cam || !a || !a.senalar_empezar){ if ((intento || 0) < 40) setTimeout(function(){ instalar((intento || 0) + 1); }, 500); return; }
    if (document.getElementById('senalarBtn')) return;
    var b = document.createElement('button'); b.type = 'button'; b.id = 'senalarBtn';
    var conTexto = cam.id === 'mirar';                              // en el asistente la cámara trae texto; en los otros, solo ícono
    b.className = conTexto ? 'btn' : cam.className;
    b.title = 'Señalar: encierra con el ratón algo de la app y pregúntame qué es (verás la captura antes de adjuntarla)';
    b.setAttribute('aria-label', 'Señalar algo en la app');
    b.innerHTML = ic(conTexto ? 15 : 18) + (conTexto ? 'Señalar' : '');
    b.hidden = cam.hidden;
    b.onclick = empezar;
    cam.parentNode.insertBefore(b, cam.nextSibling);
    new MutationObserver(function(){ b.hidden = cam.hidden; }).observe(cam, {attributes: true, attributeFilter: ['hidden']});
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function(){ instalar(0); });
  else instalar(0);

  window.Senalar = {empezar: empezar};
})();
