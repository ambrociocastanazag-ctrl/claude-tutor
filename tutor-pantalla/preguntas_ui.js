/* Preguntas del tutor en el chat (encuestas, opción múltiple, abiertas). ojos_panel.inyectar_ui() mete este archivo en
   la página de cualquier panel; Python separa el bloque <preguntas> de la respuesta (ojos_panel.separar_preguntas) y la
   página llama:

   Preguntas.tarjeta(lista, enviar)  → elemento para poner en la burbuja del tutor. Al responder, corrige al instante lo
                                       que trae "correcta" (✔/✘ y la explicación, sin IA) y llama enviar(texto) con
                                       «Mis respuestas: …» para que el tutor siga.
   Cada pregunta: {pregunta, opciones?, correcta? (índice o lista), explicacion?, multiple?, otra?, no_se?}.
   Sin opciones es abierta (caja de texto). Una sola pregunta de opción única se manda con un clic. */
(function(){
  if (window.Preguntas) return;
  var css = '' +
    '.pq{margin-top:10px;border:1px solid var(--line);border-radius:12px;background:var(--surface);overflow:hidden;font-family:var(--sans)}' +
    '.pq-p{padding:12px 13px 10px;border-top:1px solid var(--line2)} .pq-p:first-child{border-top:0}' +
    '.pq-q{font-size:14px;font-weight:650;line-height:1.45;margin-bottom:8px;color:var(--ink)}' +
    '.pq-n{display:inline-grid;place-items:center;min-width:20px;height:20px;margin-right:7px;border-radius:6px;background:var(--acc-soft);color:var(--acc-text);font-size:12px;font-weight:700;vertical-align:1px}' +
    '.pq-tipo{display:block;margin:-4px 0 7px 27px;font-size:11.5px;color:var(--ink3)}' +
    '.pq-ops{display:flex;flex-direction:column;gap:6px}' +
    '.pq-op{display:flex;align-items:center;gap:9px;width:100%;min-height:38px;padding:7px 11px;border:1px solid var(--line);border-radius:9px;background:var(--bg);' +
      'font:inherit;font-size:13.5px;line-height:1.4;color:var(--ink);text-align:left;cursor:pointer;transition:border-color .12s,background .12s}' +
    '.pq-op:hover:not(:disabled){border-color:var(--acc-mid)} .pq-op:disabled{cursor:default}' +
    '.pq-op .pq-m{flex:none;width:17px;height:17px;border:2px solid var(--ink3);border-radius:50%;display:grid;place-items:center}' +
    '.pq-multi .pq-op .pq-m{border-radius:5px}' +
    '.pq-op.pq-sel{border-color:var(--acc);background:var(--acc-soft)} .pq-op.pq-sel .pq-m{border-color:var(--acc);background:var(--acc)}' +
    '.pq-op.pq-sel .pq-m::after{content:"";width:6px;height:6px;border-radius:50%;background:var(--on-acc,#fff)}' +
    '.pq-multi .pq-op.pq-sel .pq-m::after{width:8px;height:4px;border-radius:0;background:none;border:solid var(--on-acc,#fff);border-width:0 0 2px 2px;transform:rotate(-45deg) translate(1px,-1px)}' +
    '.pq-op.pq-bien{border-color:var(--ok,#1e8c46);background:color-mix(in oklch,var(--ok,#1e8c46) 12%,var(--bg))}' +
    '.pq-op.pq-mal{border-color:var(--bad,#c02828);background:color-mix(in oklch,var(--bad,#c02828) 10%,var(--bg))}' +
    '.pq-op .pq-v{margin-left:auto;font-weight:700} .pq-bien .pq-v{color:var(--ok,#1e8c46)} .pq-mal .pq-v{color:var(--bad,#c02828)}' +
    '.pq-txt{width:100%;min-height:36px;margin-top:6px;padding:7px 10px;border:1px solid var(--line);border-radius:9px;background:var(--bg);color:var(--ink);font:inherit;font-size:13.5px;resize:vertical;box-sizing:border-box}' +
    '.pq-txt:focus{outline:2px solid var(--acc-mid);outline-offset:0}' +
    '.pq-exp{margin-top:8px;padding:8px 10px;border-radius:8px;background:var(--sunk);font-size:13px;line-height:1.5;color:var(--ink2)}' +
    '.pq-exp b{color:var(--ink)}' +
    '.pq-pie{display:flex;align-items:center;gap:10px;padding:10px 13px;border-top:1px solid var(--line2);background:var(--bg)}' +
    '.pq-pie span{flex:1;font-size:12.5px;color:var(--ink3)}' +
    '.pq-env{height:34px;padding:0 14px;border:0;border-radius:9px;background:var(--acc);color:var(--on-acc,#fff);font:inherit;font-size:13.5px;font-weight:650;cursor:pointer}' +
    '.pq-env:disabled{opacity:.45;cursor:default}' +
    '.pq-hecho .pq-pie{display:none}';
  var st = document.createElement('style'); st.textContent = css; (document.head || document.documentElement).appendChild(st);

  function esc(s){ return String(s == null ? '' : s).replace(/[&<>"]/g, function(c){ return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }
  function lista(v){ return v == null ? [] : Array.isArray(v) ? v : [v]; }

  // Una "pregunta" con "volver" no es una pregunta: es la tarjeta «¿Vuelvo a mirar «ventana»?» de ojos_ui.js (Sí / No / Recortar).
  // Y una con "archivo" es la tarjeta «¿Dejo que el tutor lea…?» (Sí / No) de ojos_ui.js.
  function tarjeta(preguntas, enviar){
    var arch = preguntas.filter(function(q){ return q && q.archivo; });
    if (arch.length && window.Ojos && Ojos.tarjetaArchivo){
      var otras = preguntas.filter(function(q){ return !(q && q.archivo); });
      var c = document.createElement('div');
      c.appendChild(Ojos.tarjetaArchivo(arch[0].archivo, enviar));
      if (otras.length) c.appendChild(tarjeta(otras, enviar));
      return c;
    }
    var vol = preguntas.filter(function(q){ return q && q.volver; });
    if (vol.length && window.Ojos && Ojos.tarjetaVolver){
      var resto = preguntas.filter(function(q){ return !(q && q.volver); });
      var caja = document.createElement('div');
      caja.appendChild(Ojos.tarjetaVolver(vol[0].volver, enviar));
      if (resto.length) caja.appendChild(tarjetaPreguntas(resto, enviar));
      return caja;
    }
    return tarjetaPreguntas(preguntas.filter(function(q){ return !(q && q.volver); }), enviar);
  }

  function tarjetaPreguntas(preguntas, enviar){
    var raiz = document.createElement('div'); raiz.className = 'pq';
    var varias = preguntas.length > 1, estado = [];
    var directa = !varias && preguntas[0].opciones && preguntas[0].opciones.length && !preguntas[0].multiple && !preguntas[0].otra;

    preguntas.forEach(function(q, k){
      var abierta = !(q.opciones && q.opciones.length), ops = (q.opciones || []).slice();
      if (!abierta && q.no_se) ops.push('No sé');
      var e = {q: q, sel: [], texto: '', abierta: abierta, ops: ops, otraIdx: -1};
      estado.push(e);
      var p = document.createElement('div'); p.className = 'pq-p' + (q.multiple ? ' pq-multi' : '');
      p.innerHTML = '<div class="pq-q">' + (varias ? '<span class="pq-n">' + (k + 1) + '</span>' : '') + esc(q.pregunta) + '</div>' +
        (q.multiple ? '<span class="pq-tipo">Puedes elegir varias</span>' : '');
      if (abierta){
        var t = document.createElement('textarea'); t.className = 'pq-txt'; t.rows = 1; t.placeholder = 'Tu respuesta…';
        t.addEventListener('input', function(){ e.texto = t.value; listo(); });
        t.addEventListener('keydown', function(ev){ if (ev.key === 'Enter' && !ev.shiftKey){ ev.preventDefault(); if (!boton.disabled) mandar(); } });
        p.appendChild(t); e.caja = t;
      } else {
        var cont = document.createElement('div'); cont.className = 'pq-ops';
        if (q.otra){ e.otraIdx = ops.length; ops.push('Otra…'); }
        e.botones = ops.map(function(o, i){
          var b = document.createElement('button'); b.type = 'button'; b.className = 'pq-op';
          b.innerHTML = '<span class="pq-m"></span><span>' + esc(o) + '</span>';
          b.onclick = function(){
            if (q.multiple){ var j = e.sel.indexOf(i); if (j >= 0) e.sel.splice(j, 1); else e.sel.push(i); }
            else e.sel = [i];
            e.botones.forEach(function(x, n){ x.classList.toggle('pq-sel', e.sel.indexOf(n) >= 0); });
            if (e.otraIdx >= 0){ e.otraCaja.hidden = e.sel.indexOf(e.otraIdx) < 0; if (!e.otraCaja.hidden) e.otraCaja.focus(); }
            if (directa) mandar(); else listo();
          };
          cont.appendChild(b); return b;
        });
        p.appendChild(cont);
        if (e.otraIdx >= 0){
          var oc = document.createElement('textarea'); oc.className = 'pq-txt'; oc.rows = 1; oc.placeholder = 'Escribe tu respuesta…'; oc.hidden = true;
          oc.addEventListener('input', function(){ e.texto = oc.value; listo(); });
          p.appendChild(oc); e.otraCaja = oc;
        }
      }
      e.nodo = p; raiz.appendChild(p);
    });

    var pie = document.createElement('div'); pie.className = 'pq-pie';
    pie.innerHTML = '<span>' + (varias ? 'Responde todas y envía' : '') + '</span>';
    var boton = document.createElement('button'); boton.type = 'button'; boton.className = 'pq-env'; boton.textContent = varias ? 'Enviar respuestas' : 'Enviar';
    boton.disabled = true; boton.onclick = mandar; pie.appendChild(boton);
    if (!directa) raiz.appendChild(pie);

    function contestada(e){
      if (e.abierta) return e.texto.trim().length > 0;
      if (!e.sel.length) return false;
      return e.sel.indexOf(e.otraIdx) < 0 || e.texto.trim().length > 0;
    }
    function listo(){ boton.disabled = !estado.every(contestada); }

    var enviado = false;
    function mandar(){
      if (enviado || !estado.every(contestada)) return;
      enviado = true; raiz.classList.add('pq-hecho');
      var lineas = estado.map(function(e, k){
        var q = e.q, resp, marca = '';
        if (e.abierta) resp = e.texto.trim();
        else resp = e.sel.slice().sort(function(a, b){ return a - b; }).map(function(i){ return i === e.otraIdx ? 'Otra: ' + e.texto.trim() : e.ops[i]; }).join('; ');
        if (e.botones) e.botones.forEach(function(b){ b.disabled = true; });
        if (e.caja) e.caja.disabled = true;
        if (e.otraCaja) e.otraCaja.disabled = true;
        var ok = lista(q.correcta).filter(function(i){ return typeof i === 'number' && i >= 0 && i < (q.opciones || []).length; });
        if (!e.abierta && ok.length){              // corrección al instante: ✔/✘ en cada opción y la explicación
          var sel = e.sel.filter(function(i){ return i !== e.otraIdx; }).sort().join(','), bien = sel === ok.slice().sort().join(',');
          e.botones.forEach(function(b, i){
            var es = ok.indexOf(i) >= 0, elegida = e.sel.indexOf(i) >= 0;
            if (es){ b.classList.add('pq-bien'); b.insertAdjacentHTML('beforeend', '<span class="pq-v">✔</span>'); }
            else if (elegida){ b.classList.add('pq-mal'); b.insertAdjacentHTML('beforeend', '<span class="pq-v">✘</span>'); }
          });
          var correctas = ok.map(function(i){ return q.opciones[i]; }).join('; ');
          e.nodo.insertAdjacentHTML('beforeend', '<div class="pq-exp"><b>' + (bien ? '¡Bien!' : 'No es esa.') + '</b>' +
            (bien ? '' : ' La correcta: ' + esc(correctas) + '.') + (q.explicacion ? ' ' + esc(q.explicacion) : '') + '</div>');
          marca = bien ? ' ✔ (correcta)' : ' ✘ (la correcta era: ' + correctas + ')';
        }
        return (estado.length > 1 ? (k + 1) + '. ' : '') + q.pregunta + ' → ' + resp + marca;
      });
      enviar((estado.length > 1 ? 'Mis respuestas:\n' : 'Mi respuesta: ') + lineas.join('\n'));
    }
    return raiz;
  }

  window.Preguntas = {tarjeta: tarjeta};
})();
