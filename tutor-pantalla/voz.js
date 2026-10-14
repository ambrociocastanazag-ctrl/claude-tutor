/* La voz del tutor. Si el panel da voz natural (api.voz_audio → voz_natural.py, edge-tts: Dalia o Jorge de México), lee
   con ella: Python genera el MP3 de cada trozo y aquí suena con un <audio>, pidiendo el siguiente mientras suena el
   actual. Si no hay internet o falla, usa speechSynthesis (las voces de Windows, sin enviar nada fuera).

   Voz.activa()    → bool (apagada por defecto; se recuerda en localStorage)
   Voz.alternar()  → nuevo estado (al apagarla, calla)
   Voz.callar()    corta lo que dice y resuelve las promesas pendientes
   Voz.decir(t)    → Promise que se resuelve al terminar de decirlo (o al callar). Sin voces instaladas espera un
                     tiempo proporcional al texto (~65 ms por letra, máx. 8 s) para que la animación siga el ritmo
   Voz.boton()     → <button> 32×32 para la barra del panel (altavoz; con ondas si suena, tachado si no) */
(function(){
  if (window.Voz) return;
  var CLAVE = 'voz_tutor_activa', MS_LETRA = 65, MAX_ESPERA = 8000;
  var sy = window.speechSynthesis || null;
  var activa = false, turno = 0, pendientes = [], botones = [], voz = null;
  var fallosNatural = 0, sonando = null;           // tras 2 fallos seguidos se deja la natural (sin internet)
  function api(){ return window.pywebview && window.pywebview.api; }
  function natural(){ var a = api(); return !!(a && a.voz_audio) && fallosNatural < 2; }
  try { activa = localStorage.getItem(CLAVE) === '1'; } catch (e){}

  // ---- estilo mínimo del botón ----
  function estilo(){
    if (document.getElementById('vz-estilo')) return;
    var s = document.createElement('style'); s.id = 'vz-estilo';
    s.textContent = '.vz-btn{width:32px;height:32px;padding:0;border:0;border-radius:8px;background:transparent;color:var(--ink2,#5b6270);' +
      'cursor:pointer;display:inline-flex;align-items:center;justify-content:center;flex:none;transition:background .12s}' +
      '.vz-btn:hover{background:var(--line2,#e3e5ea)}.vz-btn:focus-visible{outline:2px solid var(--ink2,#5b6270);outline-offset:1px}' +
      '.vz-btn svg{display:block;width:20px;height:20px}';
    (document.head || document.documentElement).appendChild(s);
  }
  if (document.head) estilo(); else document.addEventListener('DOMContentLoaded', estilo);

  // ---- elegir la voz: es-MX / es-US / es-419, mejor si es «Natural» de Microsoft; luego cualquier es-* ----
  function elegir(){
    var lista = sy && sy.getVoices ? sy.getVoices() : [];
    var mejor = null, pm = -1;
    lista.forEach(function(v){
      var l = String(v.lang || '').replace('_', '-').toLowerCase();
      if (l.indexOf('es') !== 0) return;
      var p = l === 'es-mx' ? 100 : l === 'es-us' ? 90 : l === 'es-419' ? 80 : 50;
      if (/natural/i.test(v.name)) p += 30;
      if (/microsoft/i.test(v.name)) p += 5;
      if (p > pm){ pm = p; mejor = v; }
    });
    voz = mejor;
    return lista.length;
  }
  if (sy && sy.addEventListener) try { sy.addEventListener('voiceschanged', elegir); } catch (e){}
  elegir();

  // ---- partir en frases (Chromium corta los enunciados largos) ----
  function trozos(texto){
    var t = String(texto || '').replace(/\s+/g, ' ').trim();
    if (!t) return [];
    var frases = t.match(/[^.!?;:…]+[.!?;:…]*\s*/g) || [t], out = [];
    frases.forEach(function(f){
      f = f.trim();
      while (f.length > 160){
        var i = f.lastIndexOf(',', 160); if (i < 40) i = f.lastIndexOf(' ', 160); if (i < 20) i = 160;
        out.push(f.slice(0, i + 1).trim()); f = f.slice(i + 1).trim();
      }
      if (f) out.push(f);
    });
    return out;
  }

  function esperar(ms, mio, fin){                 // sin voz: se espera lo que tardaría y sigue
    var p = {fin: fin, timer: setTimeout(function(){ salir(p); }, ms)};
    pendientes.push(p); return p;
  }
  function salir(p){
    var i = pendientes.indexOf(p); if (i >= 0) pendientes.splice(i, 1);
    clearTimeout(p.timer); p.fin();
  }

  // Para la voz natural: la primera frase sola (empieza antes) y el resto en trozos de hasta ~350 letras (menos cortes)
  function bloques(partes){
    var out = [], cur = '';
    partes.forEach(function(f, i){
      if (i === 0){ out.push(f); return; }
      if (cur && (cur + ' ' + f).length > 350){ out.push(cur); cur = f; } else cur = cur ? cur + ' ' + f : f;
    });
    if (cur) out.push(cur);
    return out;
  }
  function pedir(t){ return Promise.resolve(api().voz_audio(t)).then(function(r){ return r && r.ok ? r.audio : null; }, function(){ return null; }); }

  // Lee los trozos con la voz natural; el que no se pueda generar se dice con la de Windows.
  function decirNatural(partes, mio, ok){
    var bs = bloques(partes), i = 0, prox = pedir(bs[0]);
    (function siguiente(){
      if (mio !== turno || i >= bs.length) return ok();
      var esta = prox, texto = bs[i++];
      prox = i < bs.length ? pedir(bs[i]) : null;            // el siguiente se pide mientras suena este
      esta.then(function(url){
        if (mio !== turno) return ok();
        if (!url){ fallosNatural++; return decirSistema(trozos(texto), mio, siguiente); }
        fallosNatural = 0;
        var au = new Audio(url), hecho = false, p;
        function listo(){ if (hecho) return; hecho = true; sonando = null; var k = pendientes.indexOf(p); if (k >= 0) pendientes.splice(k, 1); clearTimeout(p.timer); siguiente(); }
        p = {fin: function(){ try { au.pause(); } catch (e){} listo(); }, timer: setTimeout(listo, Math.min(60000, texto.length * 160 + 6000))};
        pendientes.push(p); sonando = au;
        au.onended = listo; au.onerror = listo;
        var r = au.play(); if (r && r.catch) r.catch(listo);
      });
    })();
  }

  function decir(texto){
    var partes = trozos(texto), mio = turno;
    return new Promise(function(ok){
      if (!partes.length) return ok();
      if (natural()) return decirNatural(partes, mio, ok);
      decirSistema(partes, mio, ok);
    });
  }

  function decirSistema(partes, mio, ok){
      if (!partes.length) return ok();
      var hay = sy && sy.speak && typeof window.SpeechSynthesisUtterance === 'function' ? elegir() : 0;
      if (!hay){                                  // sin voces: espera proporcional al texto
        var n = partes.join(' ').length;
        return void esperar(Math.min(MAX_ESPERA, n * MS_LETRA), mio, ok);
      }
      var i = 0;
      (function siguiente(){
        if (mio !== turno || i >= partes.length) return ok();
        var u = new SpeechSynthesisUtterance(partes[i++]), hecho = false, p;
        if (voz){ u.voice = voz; u.lang = voz.lang; } else u.lang = 'es-MX';
        u.rate = 1.05;
        function listo(){ if (hecho) return; hecho = true; if (p) { var k = pendientes.indexOf(p); if (k >= 0) pendientes.splice(k, 1); clearTimeout(p.timer); } siguiente(); }
        u.onend = listo; u.onerror = listo;
        // seguro: si el motor nunca avisa que terminó, seguimos pasado un tiempo razonable
        p = {fin: listo, timer: setTimeout(listo, Math.min(30000, u.text.length * 140 + 4000))};
        pendientes.push(p);
        try { sy.speak(u); } catch (e){ listo(); }
      })();
  }

  function callar(){
    turno++;
    try { if (sy && sy.cancel) sy.cancel(); } catch (e){}
    try { if (sonando) sonando.pause(); } catch (e){}
    pendientes.slice().forEach(salir);
  }

  // ---- el botón ----
  var ICONO_ON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M4 9.5v5h3.5L12 18.5v-13L7.5 9.5z" fill="currentColor" fill-opacity=".15"/><path d="M15.5 9a4 4 0 0 1 0 6"/><path d="M18 6.5a8 8 0 0 1 0 11"/></svg>';
  var ICONO_OFF = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
    '<path d="M4 9.5v5h3.5L12 18.5v-13L7.5 9.5z" fill="currentColor" fill-opacity=".15"/><path d="M16 9.5l5 5M21 9.5l-5 5"/></svg>';
  function pintar(b){
    b.innerHTML = activa ? ICONO_ON : ICONO_OFF;
    var t = activa ? 'Leer en voz alta' : 'Voz apagada';
    b.title = t; b.setAttribute('aria-label', t); b.setAttribute('aria-pressed', activa ? 'true' : 'false');
  }
  function alternar(){
    activa = !activa;
    try { localStorage.setItem(CLAVE, activa ? '1' : '0'); } catch (e){}
    if (!activa) callar();
    botones.forEach(pintar);
    return activa;
  }
  function boton(){
    estilo();
    var b = document.createElement('button'); b.type = 'button'; b.className = 'vz-btn';
    pintar(b);
    b.addEventListener('click', function(){ alternar(); });
    botones.push(b);
    return b;
  }

  window.Voz = {activa: function(){ return activa; }, alternar: alternar, callar: callar, decir: decir, boton: boton};
})();
