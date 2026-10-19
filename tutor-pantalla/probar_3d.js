// node tutor-pantalla/probar_3d.js: el motor 3D (motor_3d.js): spec JSON, guion de Geometría, ocultas, encuadre y rapidez.
// Lo visual se revisa además con capturas (ver CONTRATO-3D.md); aquí, lo que se puede comprobar sin mirar.
const path = require('path');
const F = require(path.join(__dirname, 'motor_figuras.js'));
const F3 = require(path.join(__dirname, 'motor_3d.js'));
let mal = 0, hechos = 0;
const bien = (cond, msg) => { hechos++; if (!cond) { mal++; console.log('MAL', msg); } };
const sano = r => !!r.svg && /^<svg xmlns="http:\/\/www.w3.org\/2000\/svg"/.test(r.svg) && r.svg.endsWith('</svg>') && !/NaN|Infinity|undefined/.test(r.svg);

// ---------- 1. intérprete con varias variables ----------
bien(F.compilar('x^2-y^2', {vars: ['x', 'y']})(3, 1) === 8, 'f(x, y) = x² − y²');
bien(F.compilar('xy+2t', {vars: ['x', 'y', 't']})(2, 3, 1) === 8, 'xy + 2t (multiplicación implícita entre variables)');
bien(F.compilar('2x+1')(3) === 7, 'f(x) de siempre sigue igual');
{ let f = false; try { F.compilar('x+z', {vars: ['x', 'y']}); } catch (_) { f = true; } bien(f, 'una variable que no está en vars falla'); }

// ---------- 2. cada tipo dibuja sin errores (claro y oscuro) ----------
const casos = {
  superficie: {superficie: 'x^2-y^2', x: [-2, 2], y: [-2, 2]},
  parametrica: {objetos: [{tipo: 'parametrica', x: '(2+cos(v))*cos(u)', y: '(2+cos(v))*sin(u)', z: 'sin(v)'}]},
  revolucion: {revolucion: 'sqrt(x)', x: [0, 4], angulo: 300},
  arandela: {objetos: [{tipo: 'revolucion', f: 'x', g: 'x^2', x: [0, 1], corte: 0.5}]},
  capa: {objetos: [{tipo: 'revolucion', f: '4-x^2', x: [0, 2], eje: 'y', capa: 1}]},
  curva: {objetos: [{tipo: 'curva', x: 'cos(t)', y: 'sin(t)', z: 't/4', t: [0, 12.5], flecha: true}]},
  solidos: {objetos: [{tipo: 'cubo', en: [0, 0, 0], lado: 2}, {tipo: 'caja', de: [3, 0, 0], a: [4, 2, 1]}, {tipo: 'prisma', base: [[0, 3, 0], [1, 3, 0], [0, 4, 0]], altura: 2},
    {tipo: 'piramide', base: [[3, 3, 0], [5, 3, 0], [5, 5, 0], [3, 5, 0]], apice: [4, 4, 2]}, {tipo: 'cilindro', de: [-3, 0, 0], a: [-3, 0, 2], radio: 1},
    {tipo: 'cono', base: [-3, 3, 0], apice: [-3, 3, 2], radio: 1}, {tipo: 'esfera', centro: [0, -3, 1], radio: 1}]},
  geometria: {objetos: [{tipo: 'punto', en: [1, 2, 3], nombre: 'A'}, {tipo: 'segmento', de: [0, 0, 0], a: [1, 2, 3]}, {tipo: 'recta', por: [[0, 0, 0], [1, 1, 1]]},
    {tipo: 'vector', a: [2, 0, 1], nombre: 'v'}, {tipo: 'poligono', puntos: [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}, {tipo: 'plano', ecuacion: 'x + y + z = 1'},
    {tipo: 'etiqueta', en: [0, 0, 2], texto: 'hola'}, {tipo: 'cota', de: [0, 0, 0], a: [1, 2, 3]}, {tipo: 'angulo', a: [1, 0, 0], b: [0, 0, 0], c: [0, 1, 0]}]},
  fisica: {objetos: [{tipo: 'carga', en: [-1, 0, 0], q: 1}, {tipo: 'carga', en: [1, 0, 0], q: -1}, {tipo: 'campo'}, {tipo: 'esfera', radio: 2, opacidad: 0.2}]},
  campoE: {objetos: [{tipo: 'campo', E: ['-y', 'x', '0'], x: [-1, 1], y: [-1, 1], z: [-1, 1], n: 3}]},
  malla: {objetos: [{tipo: 'malla', vertices: [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], caras: [[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]]}]}
};
for (const [k, s] of Object.entries(casos)) for (const tema of ['claro', 'oscuro']) {
  const r = F3.figura(s, {tema});
  bien(sano(r) && !r.errores.length, `${k} (${tema}): ${JSON.stringify(r.errores)}`);
}
['S', 'M', 'L'].forEach((t, i) => bien(F3.figura(casos.solidos, {tam: t}).w === [320, 480, 720][i], 'tamaño ' + t));
bien(F3.figura(casos.solidos, {fondo: 'blanco'}).svg.includes('fill="#ffffff"/>'), 'fondo blanco');

// ---------- 3. lo que se tapa ----------
{
  const r = F3.figura({objetos: [{tipo: 'cubo', en: [0, 0, 0], lado: 2}, {tipo: 'punto', en: [0, 0, 0], nombre: 'A'}, {tipo: 'punto', en: [2, 2, 2], nombre: 'G'}]}, {vista: [30, 22]});
  bien(/<circle[^>]*opacity="0\.65"/.test(r.svg), 'el vértice de atrás del cubo sale hueco (tapado)');
  bien((r.svg.match(/<circle/g) || []).length === 2, 'dos puntos');
  bien(r.svg.includes('stroke-dasharray'), 'las aristas ocultas del cubo van a trazos');
  const s = F3.figura({objetos: [{tipo: 'cubo', en: [0, 0, 0], lado: 2}], ejes: false}, {vista: [30, 22]});
  const caras = (s.svg.match(/<path d="M[^"]+Z"/g) || []).length;
  bien(caras === 3, 'un cubo opaco enseña 3 caras desde arriba en diagonal (salen ' + caras + ')');
  const t = F3.figura({objetos: [{tipo: 'cubo', en: [0, 0, 0], lado: 2, opacidad: 0.4}], ejes: false}, {vista: [30, 22]});
  bien((t.svg.match(/<path d="M[^"]+Z"/g) || []).length === 6, 'un cubo transparente enseña sus 6 caras');
}

// ---------- 4. errores en español, y lo válido se dibuja ----------
{
  const r = F3.figura({objetos: [{tipo: 'nube'}, {tipo: 'esfera', radio: 1}, {tipo: 'caja', de: [0, 0, 0], a: [1, 1, 0]},
    {tipo: 'plano', por: [[0, 0, 0], [1, 1, 1], [2, 2, 2]]}, {tipo: 'revolucion', f: 'sqrt(x)', x: [-1, 1]}, {tipo: 'superficie', f: 'x+'}]});
  bien(sano(r), 'con errores igual dibuja la esfera');
  const m = r.errores.map(e => e.objeto + ':' + e.mensaje).join(' | ');
  bien(r.errores.length === 5, 'cinco errores: ' + m);
  bien(/no conozco el tipo «nube»/.test(m) && /plana/.test(m) && /alineados/.test(m) && /no están definidas/.test(m), 'mensajes claros: ' + m);
  bien(F3.figura('no es json').errores[0].objeto === -1, 'JSON roto: error general');
  bien(F3.figura({}).svg === '', 'nada que dibujar → svg vacío');
}

// ---------- 5. el guion de la pestaña Geometría ----------
bien(F3.es3d('A=(1,2,3)'), 'punto con z → 3D');
bien(F3.es3d('e=esfera(A,1)'), 'comando de 3D → 3D');
bien(F3.es3d('s=segmento((0,0,0),(1,1,1))'), 'terna dentro de un comando → 3D');
bien(!F3.es3d('A=(1,2)\nc=circunferencia(A,2)'), 'geometría plana sigue en 2D');
bien(!F3.es3d('A=(0,0)\nB=(1,0)\nC=(0,1)\nc=circunferencia(A,B,C)'), 'tres puntos con nombre no es una terna');
bien(!F3.es3d('# esfera(A,1) en un comentario\nA=(1,1)'), 'un comentario no cuenta');
{
  const g = F3.guion('A=(0,0,0)\nB=(2,0,0)\nc=cubo(A,2, color=verde)\ne=esfera((1,1,3),1)\nm=circunferencia(A,2)\np=plano(2x+y-z=3)\nr=revolucion(sqrt(x),0,4,eje=x,angulo=270)\nd=distancia(A,B)\nvista(40, 25)\nX=(1,1)');
  bien(sano(g), 'el guion dibuja');
  bien(g.errores.length === 1 && g.errores[0].linea === 5 && /geometría plana/.test(g.errores[0].mensaje), 'el error de circunferencia cae en su línea: ' + JSON.stringify(g.errores));
  bien(g.vista[0] === 40 && g.vista[1] === 25, 'vista(40, 25)');
  bien(g.spec.objetos.filter(o => o.tipo === 'punto').length === 3, 'tres puntos con nombre (A, B y X en z = 0)');
  const e = F3.guion('A=(0,0,0)\ncaja(A, (1,1,0))\n(1,2,3)\nA=(1,1,1)\ncilindro(A,(0,0,2))');
  bien(e.errores.map(x => x.linea).join(',') === '2,3,4,5', 'líneas con error: ' + JSON.stringify(e.errores));
}

// ---------- 6. de la spec al guion (Editar en la tarjeta) ----------
['solidos', 'geometria', 'revolucion', 'superficie', 'curva', 'fisica'].forEach(k => {
  const g = F3.aGuion(casos[k]);
  if (!g) { bien(false, 'aGuion de ' + k + ' devolvió null'); return; }
  const a = F3.aSpec(g);
  bien(!a.errores.length, `aGuion(${k}) se vuelve a leer sin errores: ${JSON.stringify(a.errores)}\n${g}`);
  bien(a.spec.objetos.length === F3.escena(casos[k]).errores.length + (casos[k].objetos || [1]).length, `aGuion(${k}) conserva los objetos`);
});
bien(F3.aGuion(casos.parametrica) === null && F3.aGuion(casos.malla) === null, 'lo que no tiene comando en el guion → null');

// ---------- 7. girar: tamaño fijo y rápido ----------
{
  const e = F3.escena(casos.solidos), a = e.dibujar([10, 10], {encuadre: 'esfera'}), b = e.dibujar([200, -40], {encuadre: 'esfera'});
  bien(a.w === b.w && a.h === b.h, 'con encuadre esfera el tamaño no cambia al girar');
  const er = F3.escena(casos.solidos, {rapido: true}), t0 = Date.now();
  for (let i = 0; i < 60; i++) er.dibujar([i * 6, 20], {encuadre: 'esfera'});
  const ms = (Date.now() - t0) / 60;
  bien(ms < 25, 'girar en modo rápido: ' + ms.toFixed(1) + ' ms por cuadro');
  const big = F3.figura(casos.arandela).svg.length;
  bien(big < 260 * 1024, 'la arandela pesa ' + Math.round(big / 1024) + ' KB');
}

console.log(mal ? mal + ' fallos de ' + hechos + ' comprobaciones' : '3d: todo bien (' + hechos + ' comprobaciones)');
process.exitCode = mal ? 1 : 0;
