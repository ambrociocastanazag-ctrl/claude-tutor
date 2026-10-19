/* Botón 🎯 Reajustar y texto enlazado con las marcas, en la página de cualquier panel (asistente, Excel, Dia, curso).
   ojos_panel.inyectar_ui() mete este archivo (SCRIPTS_UI). Contrato: tutor-pantalla/CONTRATO-MARCAS.md, sección 5.

   MarcasUI.enlazar(nodo)   tras pintar una respuesta: envuelve la primera aparición del texto de cada marca puesta
                            (Dibujante.marcasPuestas()) en <span class="ancla-marca" data-capa="ID">; al pasar el ratón,
                            esa marca late en la ventana (api.capa_latir). Se puede llamar las veces que haga falta.
   MarcasUI.reajustar()     lo mismo que pulsar el botón: api.reajustar() → dibujos con deslizar → nota → tarjeta «¿Vuelvo a mirar?»
   MarcasUI.estado()        pone el botón gris si no hay marcas ni dibujos puestos (sigue pulsable: Python sabe más que la página)

   La página que lo use define window.MARCAS_PAGINA = {nota(texto), tarjeta(pregunta)}: cómo se pone una nota corta en su
   chat y cómo se pinta la tarjeta (Preguntas.tarjeta con el «enviar» de esa página). El botón va donde esté
   <span data-reajustar></span> o, si no, justo después de «Borrar marcas» (#borrar). */
(function(){
  if (window.MarcasUI) return;
  var css = '' +
    '.reaj-gris{opacity:.5}' +
    '.ancla-marca{text-decoration:underline dotted;text-decoration-color:var(--acc,#4a5fd0);text-decoration-thickness:2px;text-underline-offset:3px;border-radius:3px;cursor:help;transition:background .15s}' +
    '.ancla-marca:hover{background:var(--acc-soft,rgba(74,95,208,.14))}';
  var st = document.createElement('style'); st.textContent = css; (document.head || document.documentElement).appendChild(st);

  var boton = null, ocupado = false, ultimoLatido = {};
  function api(){ return window.pywebview && window.pywebview.api; }

  // ---- texto enlazado ----
  function norm(s){            // sin mayúsculas ni acentos; mapa[i] = posición en el texto original del carácter i
    var t = '', mapa = [];
    for (var i = 0; i < s.length; i++){
      var n = s.charAt(i).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
      for (var k = 0; k < n.length; k++){ t += n.charAt(k); mapa.push(i); }
    }
    return {t: t, m: mapa};
  }
  var LETRA = /[\p{L}\p{N}]/u;
  function textos(raiz){
    var w = document.createTreeWalker(raiz, NodeFilter.SHOW_TEXT, {acceptNode: function(n){
      var p = n.parentNode;
      if (!n.nodeValue.trim() || (p && p.closest && p.closest('a,code,pre,button,script,style,textarea,.ancla-marca,.pq,.oj-vol'))) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    }});
    var out = [], n; while ((n = w.nextNode())) out.push(n);
    return out;
  }
  function envolver(raiz, id, texto){
    var aguja = norm(String(texto || '').replace(/\s+/g, ' ').trim()).t;
    if (aguja.length < 2) return false;
    var nodos = textos(raiz);
    for (var j = 0; j < nodos.length; j++){
      var nodo = nodos[j], h = norm(nodo.nodeValue), desde = 0, i;
      while ((i = h.t.indexOf(aguja, desde)) >= 0){
        var antes = i > 0 ? h.t.charAt(i - 1) : '', despues = i + aguja.length < h.t.length ? h.t.charAt(i + aguja.length) : '';
        if ((antes && LETRA.test(antes)) || (despues && LETRA.test(despues))){ desde = i + 1; continue; }
        var ini = h.m[i], fin = h.m[i + aguja.length - 1] + 1;
        var medio = nodo.splitText(ini); medio.splitText(fin - ini);
        var sp = document.createElement('span'); sp.className = 'ancla-marca'; sp.setAttribute('data-capa', id);
        sp.title = 'Mira dónde está en la ventana';
        medio.parentNode.replaceChild(sp, medio); sp.appendChild(medio);
        return true;
      }
    }
    return false;
  }
  function desenlazar(excepto){       // las anclas de respuestas viejas ya no apuntan a marcas vivas
    Array.prototype.forEach.call(document.querySelectorAll('.ancla-marca'), function(sp){
      if (excepto && excepto.contains(sp)) return;
      var p = sp.parentNode; if (!p) return;
      while (sp.firstChild) p.insertBefore(sp.firstChild, sp);
      p.removeChild(sp); p.normalize();
    });
  }
  function puestas(){
    try { return (window.Dibujante && Dibujante.marcasPuestas && Dibujante.marcasPuestas()) || []; } catch (e) { return []; }
  }
  function enlazarYa(nodo){
    puestas().forEach(function(m){
      if (!m || m.id == null || nodo.querySelector('.ancla-marca[data-capa="' + String(m.id).replace(/"/g, '') + '"]')) return;
      envolver(nodo, m.id, m.texto);
    });
  }
  // Las marcas se conocen cuando Dibujante las pone (puede tardar un momento): se reintenta, y es idempotente.
  function enlazar(nodo){
    if (!nodo) return;
    desenlazar(nodo);
    enlazarYa(nodo);
    [500, 1500].forEach(function(ms){ setTimeout(function(){ if (document.contains(nodo)){ enlazarYa(nodo); estado(); } }, ms); });
    estado();
  }
  document.addEventListener('mouseover', function(e){
    var sp = e.target.closest && e.target.closest('.ancla-marca'); if (!sp) return;
    var id = sp.getAttribute('data-capa'), ahora = Date.now();
    if (ultimoLatido[id] && ahora - ultimoLatido[id] < 1500) return;
    ultimoLatido[id] = ahora;
    var a = api(); if (a && a.capa_latir) { try { a.capa_latir(id); } catch (err) {} }
  });

  // ---- botón 🎯 Reajustar ----
  function hay(){ return puestas().length > 0; }
  function estado(){
    if (!boton) return;
    var h = hay();
    boton.classList.toggle('reaj-gris', !h);
    boton.title = h ? 'Vuelve a poner las marcas y dibujos en su sitio si moviste o cambiaste de tamaño la ventana'
                    : 'No hay marcas puestas ahora (si señalaste algo, igual puedo reajustarlo)';
  }
  function nota(t){ var p = window.MARCAS_PAGINA; if (p && p.nota) p.nota(t); }
  function reajustar(){
    var a = api();
    if (!a || !a.reajustar || ocupado) return;
    ocupado = true; boton.disabled = true;
    a.reajustar().then(function(r){
      r = r || {};
      if (r.dibujos && window.Dibujante) Dibujante.mostrar(r.dibujos, '', {deslizar: true, sinVoz: true});
      nota(r.mensaje || (r.ok === false ? 'No pude reajustar las marcas.' : 'No hay nada puesto que reajustar.'));
      var p = window.MARCAS_PAGINA;
      if (r.tarjeta && p && p.tarjeta) p.tarjeta(r.tarjeta);
    }, function(){ nota('No pude reajustar las marcas.'); }).then(function(){
      ocupado = false; boton.disabled = false; setTimeout(estado, 400);
    });
  }
  function poner(){
    if (boton) return;
    var hueco = document.querySelector('[data-reajustar]'), borrar = document.getElementById('borrar');
    if (!hueco && !borrar) return;
    boton = document.createElement('button'); boton.type = 'button'; boton.id = 'reajustar';
    boton.className = (borrar ? borrar.className : 'btn') + ' reaj-gris';
    boton.style.marginLeft = '0';
    boton.innerHTML = '<span aria-hidden="true">🎯</span>Reajustar';
    boton.onclick = reajustar;
    if (hueco) hueco.replaceWith(boton); else borrar.after(boton);
    estado(); setInterval(estado, 2000);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', poner); else poner();

  window.MarcasUI = {enlazar: enlazar, reajustar: reajustar, estado: estado};
})();
