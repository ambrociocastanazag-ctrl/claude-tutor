/* Forma «3d» del dibujante: una figura 3D (motor_3d.js, la spec de CONTRATO-3D.md §2) encima de la app. Ahí los clics pasan a
   la app, así que no se arrastra: la figura gira sola, despacio, y capa.py repite los fotogramas. Contrato: DIBUJOS.md.

   {"tipo": "dibujo", "forma": "3d", "spec": {…}, "vista": [az, el], "giro": "vaiven" | "vuelta" | "no", objetivo opcional}

   Se carga después de motor_figuras.js y motor_3d.js. Todo en píxeles de cliente; los tamaños se multiplican por d.escala. */
(function(){
  if (!window.Dibujante) return;
  var D = window.Dibujante;

  var VAIVEN = 30;                       // grados a cada lado de la vista
  var T_VAIVEN = 8000, T_VUELTA = 9000;  // ms por ciclo: despacio (con ≤ 60 fotogramas, ~6 a 7 por segundo)
  var MAX_FOTOS = 60, PRESUPUESTO = 14e6; // fotogramas × píxeles de la capa (el mismo tope que el svg animado)

  // ---- tema: el del panel si tiene las variables de siempre (--surface, --ink…); si no, el claro ----
  var lienzoColor = document.createElement('canvas'); lienzoColor.width = lienzoColor.height = 1;
  var cc = lienzoColor.getContext('2d', {willReadFrequently: true});
  function aRGB(css){                    // cualquier color CSS (oklch incluido) → [r, g, b] o null
    try { cc.clearRect(0, 0, 1, 1); cc.fillStyle = '#000'; cc.fillStyle = css; cc.fillRect(0, 0, 1, 1); var p = cc.getImageData(0, 0, 1, 1).data; return [p[0], p[1], p[2]]; }
    catch (e){ return null; }
  }
  function hex(c){ return '#' + c.map(function(v){ return ('0' + v.toString(16)).slice(-2); }).join(''); }
  function variable(nombre){             // el color de una variable CSS del panel (null si no existe)
    var raiz = document.documentElement, v = getComputedStyle(raiz).getPropertyValue(nombre).trim();
    if (!v) return null;
    var sonda = document.createElement('div'); sonda.style.cssText = 'position:fixed;left:-9999px;top:0;visibility:hidden';
    sonda.style.color = 'var(' + nombre + ')'; raiz.appendChild(sonda);
    var c = aRGB(getComputedStyle(sonda).color); sonda.remove();
    return c;
  }
  function tema(d){                      // {modo, paleta, fondo, borde} para el motor y para la tarjeta
    var sup = variable('--surface'), tin = variable('--ink'), lin = variable('--line'), acc = variable('--acc');
    var modo = d.tema === 'oscuro' || d.tema === 'claro' ? d.tema
             : sup ? ((0.299 * sup[0] + 0.587 * sup[1] + 0.114 * sup[2]) < 128 ? 'oscuro' : 'claro') : 'claro';
    var P = {}, usar = !d.tema || d.tema === modo;          // un tema forzado distinto del panel no mezcla sus colores
    if (usar && tin) P.tinta = hex(tin);
    if (usar && lin) P.suave = hex(lin);
    if (usar && sup) P.fondo = hex(sup);
    if (usar && acc) P.acento = hex(acc);
    var oscuro = modo === 'oscuro';
    return {modo: modo, paleta: P, fondo: P.fondo || (oscuro ? '#2b2e3a' : '#fcfbf8'), borde: P.suave || (oscuro ? '#454a5a' : '#d9d6cc')};
  }

  function vistaDe(v){ return Array.isArray(v) && v.length === 2 && isFinite(+v[0]) && isFinite(+v[1]) ? [+v[0], +v[1]] : null; }

  D.registrar('3d', async function(d, U){
    var F = window.Figuras3D;
    if (!F) throw new Error('3d: falta motor_3d.js');
    var spec = d.spec;
    if (typeof spec === 'string'){ try { spec = JSON.parse(spec); } catch (e){ throw new Error('3d: el JSON de «spec» no se entiende (' + e.message + ')'); } }
    if (!spec || typeof spec !== 'object' || Array.isArray(spec)) throw new Error('3d: falta «spec» (un objeto con la figura, ver CONTRATO-3D.md)');
    var giro = d.giro == null ? 'vaiven' : String(d.giro);
    if (giro !== 'vaiven' && giro !== 'vuelta' && giro !== 'no') throw new Error('3d: «giro» es vaiven, vuelta o no');

    var s = d.escala || 1, c = d.cliente || [1600, 900], T = tema(d);
    var pad = 10 * s, marg = 18 * s;                         // pad: aire dentro de la tarjeta · marg: lo que ocupa su sombra
    // tamaño de la figura: lo que quepa en el objetivo o, sin él, un tercio de la ventana
    var W = d.r ? Math.min(d.r[2] - 2 * pad, (d.r[3] - 2 * pad) / 0.78)
                : Math.min(0.34 * c[0], 460 * s, (0.62 * c[1] - 2 * pad) / 0.78);
    W = Math.round(Math.max(160, Math.min(2400, W)));

    var opts = {tema: T.modo, paleta: T.paleta, ancho: W, fondo: 'transparente'};
    var esc;
    try { esc = F.escena(spec, opts); } catch (e){ throw new Error('3d: ' + e.message); }
    var vista0 = vistaDe(d.vista) || esc.vista;
    var f0 = esc.dibujar(vista0, {encuadre: 'esfera'});
    if (!f0.svg){
      var e0 = (esc.errores || [])[0];
      throw new Error('3d: no hay nada que dibujar' + (e0 ? ' (' + e0.mensaje + ')' : ''));
    }
    if ((esc.errores || []).length) console.warn('3d: ' + esc.errores.map(function(e){ return (e.objeto >= 0 ? 'objeto ' + e.objeto + ': ' : '') + e.mensaje; }).join(' | '));

    // la tarjeta, centrada en el objetivo (o en la ventana) y sin salirse del cliente
    var tw = f0.w + 2 * pad, th = f0.h + 2 * pad;
    var cx = d.r ? d.r[0] + d.r[2] / 2 : c[0] / 2, cy = d.r ? d.r[1] + d.r[3] / 2 : c[1] / 2;
    var tx = Math.min(Math.max(marg, cx - tw / 2), Math.max(marg, c[0] - tw - marg)), ty = Math.min(Math.max(marg, cy - th / 2), Math.max(marg, c[1] - th - marg));
    var rx = 12 * s, sw = 1.4 * s;
    var base = '<defs><filter id="sb3d" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" dy="' + 3 * s + '" stdDeviation="' + 5 * s +
               '" flood-color="#0b1020" flood-opacity="0.30"/></filter></defs>' +
               '<rect x="' + tx + '" y="' + ty + '" width="' + tw + '" height="' + th + '" rx="' + rx + '" fill="' + T.fondo + '" fill-opacity="0.97" stroke="' + T.borde +
               '" stroke-width="' + sw + '" filter="url(#sb3d)"/>';
    function poner(figSvg){                                  // el SVG de la figura, anidado dentro de la tarjeta
      return base + figSvg.replace(/^<svg /, '<svg x="' + (tx + pad) + '" y="' + (ty + pad) + '" ');
    }
    var nota = d.texto ? U.nota(d, d.texto, {color: d.color, cerca: d.r ? null : [tx, ty, tw, th]}) : null;
    var caja = [tx - marg, ty - marg, tw + 2 * marg, th + 2 * marg];
    if (nota){ var nb = nota.caja, x0 = Math.min(caja[0], nb[0]), y0 = Math.min(caja[1], nb[1]); caja = [x0, y0, Math.max(caja[0] + caja[2], nb[0] + nb[2]) - x0, Math.max(caja[1] + caja[3], nb[1] + nb[3]) - y0]; }

    if (giro === 'no') return U.capa(d, caja, poner(f0.svg) + (nota ? nota.svg : ''), {ocupa: [[tx, ty, tw, th]]});

    // girando: ≤ 60 fotogramas (menos si la capa es grande). Vaivén: az0 + 30°·sen, que ya es suave y cierra el bucle sin saltos
    var k = U.recorte(d, caja), area = k ? k[2] * k[3] : 1;
    var n = Math.max(12, Math.min(MAX_FOTOS, Math.floor(PRESUPUESTO / area))), dur = giro === 'vuelta' ? T_VUELTA : T_VAIVEN;
    function azimut(i){ return giro === 'vuelta' ? vista0[0] + 360 * i / n : vista0[0] + VAIVEN * Math.sin(2 * Math.PI * i / n); }
    var fotos = await U.fotos(d, caja, n, function(i){
      return poner(esc.dibujar([azimut(i), vista0[1]], {encuadre: 'esfera'}).svg);
    });
    if (!fotos.length) return null;
    return U.capa(d, caja, nota ? nota.svg : '', {fotos: fotos, fps: n * 1000 / dur, duracion: dur, repetir: true, pausa: 0, ocupa: [[tx, ty, tw, th]]});
  });
})();
