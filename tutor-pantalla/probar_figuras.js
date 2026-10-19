// node tutor-pantalla/probar_figuras.js: el motor de figuras (motor_figuras.js): intérprete, gráficas y geometría con el lenguaje de MathStudio.
// Las posiciones de la geometría se comprueban NUMÉRICAMENTE (distancias, perpendicularidad, pertenencia), no mirando el SVG.
const F = require(require('path').join(__dirname, 'motor_figuras.js'));
let mal = 0, hechos = 0;
const bien = (cond, msg) => { hechos++; if (!cond) { mal++; console.log('MAL', msg); } };
const casi = (a, b, tol = 1e-6) => Math.abs(a - b) <= tol * Math.max(1, Math.abs(a), Math.abs(b));
const igual = (a, b) => (Number.isNaN(b) ? Number.isNaN(a) : a === b || casi(a, b, 1e-9));
const dist = (p, q) => Math.hypot(p.x - q.x, p.y - q.y);

// ---------- 1. intérprete ----------
[['2x+1', 3, 7], ['2(x+1)', 1, 4], ['-x^2', 3, -9], ['2^-x', 1, .5], ['2^3^2', 0, 512], ['sqrt(x)', -1, NaN], ['1/2x', 4, 2], ['sinx', Math.PI / 2, 1], ['x^(1/3)', -8, -2],
 ['2π', 0, 2 * Math.PI], ['√x', 9, 3], ['log(x)', 100, 2], ['y = x+1', 1, 2], ['x²', 4, 16], ['(x+1)(x-1)', 3, 8], ['1/x', 0, Infinity], ['sen(x)+tg(0)', Math.PI / 2, 1]]
 .forEach(([e, x, v]) => { let r; try { r = F.compilar(e)(x); } catch (er) { r = 'ERR ' + er.message; } bien(igual(r, v), `compilar ${e} en ${x}: ${r} (esperaba ${v})`); });
['', '2+', 'sqrt', 'foo(x)', '(1+2', 'x;1', 'alert(1)', 'constructor'].forEach(e => { let f = false; try { F.compilar(e); } catch (_) { f = true; } bien(f, 'debía fallar: ' + e); });

// ---------- 2. gráficas ----------
const numeros = d => (d.match(/-?\d+(?:\.\d+)?/g) || []).map(Number);
function trazosDe(svg, color) {                                   // los «d» de los <path> con ese stroke, como listas de puntos por tramo
  const out = [], re = new RegExp('<path d="([^"]+)" fill="none" stroke="' + color + '" stroke-width="2.4"', 'g'); let m;
  while ((m = re.exec(svg))) out.push(m[1]);
  return out;
}
{
  const g = F.grafica({x: [0, 4], funciones: [{f: 'sqrt(x)', color: 'azul'}], area: {f: 'sqrt(x)', x: [0, 4]}, puntos: [[4, 2, '(4,2)']]}, {tema: 'claro'});
  bien(/^<svg xmlns="http:\/\/www.w3.org\/2000\/svg" width="480" height="\d+" viewBox="0 0 480 \d+"/.test(g.svg) && g.w === 480, 'cabecera de la gráfica √x');
  const circ = /<circle cx="([\d.]+)" cy="([\d.]+)" r="4.4"/.exec(g.svg), ds = trazosDe(g.svg, '#2a5fd0');
  bien(!!circ && ds.length === 1, '√x: hay curva y punto');
  if (circ && ds.length) { const n = numeros(ds[0]), fin = [n[n.length - 2], n[n.length - 1]]; bien(casi(fin[0], +circ[1], 1e-3) && casi(fin[1], +circ[2], 1e-3), `√x llega a (4,2): curva ${fin} punto ${circ[1]},${circ[2]}`); }
  bien(/fill-opacity="0.24"/.test(g.svg), '√x: área sombreada');
  bien(!/<script|href=|onload|clip-path/.test(g.svg), 'sin scripts, enlaces ni clipPath');
}
{
  const g = F.grafica({x: ['-2*pi', '2*pi'], funciones: [{f: 'tan(x)', color: 'rojo'}]}, {tema: 'claro'});
  const ds = trazosDe(g.svg, '#d23a3a'), ph = Math.round(480 * 0.48);
  bien(ds.length === 1, 'tan: una curva');
  let saltos = 0, tramos = 0;
  (ds[0] || '').split('M').filter(Boolean).forEach(t => { tramos++; const n = numeros(t); for (let i = 3; i < n.length; i += 2) if (Math.abs(n[i] - n[i - 2]) > ph * 0.6) saltos++; });
  bien(tramos >= 4 && saltos === 0, `tan: ${tramos} tramos y ${saltos} saltos verticales falsos`);
  bien(g.svg.includes('>π</text>') && g.svg.includes('>−2π</text>'), 'tan: eje con π');
}
{
  const g = F.grafica({x: [-3, 3], funciones: ['x^2', 'sin(x)', '1/x']});                    // y automático
  bien(g.h > 100 && /viewBox="0 0 480 /.test(g.svg), 'gráfica con y automático');
  ['S', 'M', 'L'].forEach((t, i) => bien(F.grafica({funciones: ['x']}, {tam: t}).w === [320, 480, 720][i], 'tamaño ' + t));
  bien(F.grafica({funciones: ['x']}, {ancho: 520}).w === 520, 'ancho propio');
  bien(F.grafica({funciones: ['x']}, {fondo: 'blanco'}).svg.includes('fill="#ffffff"/>'), 'fondo blanco');
  bien(!/<rect x="0" y="0"/.test(F.grafica({funciones: ['x']}).svg), 'fondo transparente por omisión');
  const osc = F.grafica({funciones: ['x']}, {tema: 'oscuro'}).svg, cla = F.grafica({funciones: ['x']}, {tema: 'claro'}).svg;
  bien(osc !== cla && osc.includes(F.estilo.oscuro.tinta), 'tema oscuro distinto del claro');
  const p = F.plano({x: [-4, 4], y: [-3, 3]});
  bien(p.svg.includes('Plano cartesiano') && p.w === 480, 'plano suelto');
  [[null, /objeto/], [{}, /funciones/], [{funciones: ['2+']}, /función 1/], [{x: [3, 1], funciones: ['x']}, /mínimo/], [{funciones: ['x'], area: {}}, /area/]].forEach(([s, re]) => {
    let msg = ''; try { F.grafica(s); } catch (e) { msg = e.message; } bien(re.test(msg), 'error de gráfica ' + JSON.stringify(s) + ' → ' + msg);
  });
}

// ---------- 3. geometría: ayudas ----------
const G = (g, o) => F.geometria(g, o);
const por = (r, n) => r.objetos.find(o => o.nombre === n);
const sinErrores = (g, msg) => { const r = G(g); bien(!r.errores.length, `${msg}: ${r.errores.map(e => 'L' + e.linea + ' ' + e.mensaje).join(' | ')}`); return r; };
const conError = (g, re, msg, linea) => {
  const r = G(g); const e = r.errores[0];
  bien(!!e && re.test(e.mensaje) && (linea == null || e.linea === linea), `${msg}: ${e ? 'L' + e.linea + ' ' + e.mensaje : 'sin error'}`); return r;
};
const sobreRecta = (r, p) => Math.abs(r.d.x * (p.y - r.p.y) - r.d.y * (p.x - r.p.x)) < 1e-9;

const pts = 'A=(0,0)\nB=(4,0)\nC=(0,3)\nD=(4,3)';
// ---------- 3.1 el guion de §8 de la documentación de MathStudio ----------
{
  const r = sinErrores('A=(0,0)\nB=(6,0)\nC=(2,5)\nt=triangulo(A,B,C)\nM=puntomedio(B,C)\nh=altura(A,BC)\nP=interseccion(h,recta(B,C))\nc=circunferencia(M,3)\nu=tan(B,c,1)', '§8');
  const A = por(r, 'A'), B = por(r, 'B'), C = por(r, 'C'), M = por(r, 'M'), h = por(r, 'h'), P = por(r, 'P'), u = por(r, 'u'), c = por(r, 'c');
  bien(casi(M.x, 4) && casi(M.y, 2.5), 'puntomedio (4, 2.5)');
  // la altura desde A pasa por A y es perpendicular a BC
  bien(sobreRecta(h, A) && Math.abs(h.d.x * (C.x - B.x) + h.d.y * (C.y - B.y)) < 1e-9, 'la altura pasa por A y es perpendicular a BC');
  // su pie P está en la altura y en BC; esperado: proyección de A sobre BC
  const dBC = {x: C.x - B.x, y: C.y - B.y}, t = ((A.x - B.x) * dBC.x + (A.y - B.y) * dBC.y) / (dBC.x ** 2 + dBC.y ** 2), pie = {x: B.x + t * dBC.x, y: B.y + t * dBC.y};
  bien(dist(P, pie) < 1e-9, `pie de la altura (${P.x}, ${P.y}) = (${pie.x}, ${pie.y})`);
  bien(Math.abs((P.x - B.x) * dBC.y - (P.y - B.y) * dBC.x) < 1e-9, 'el pie está sobre BC');
  bien(c.r === 3 && dist(c.c, M) === 0, 'circunferencia(M,3)');
  // la tangente desde B a c toca c: distancia del centro a la recta = r
  const dd = Math.abs(u.d.x * (M.y - u.p.y) - u.d.y * (M.x - u.p.x));
  bien(casi(dd, 3, 1e-9) && sobreRecta(u, B), `tan(B,c,1): d(M,u) = ${dd}`);
}
// ---------- 3.2 tangentes punto–circunferencia ----------
{
  const r = sinErrores('O=(0,0)\nP=(5,1)\nc=circunferencia(O,2)\nu=tan(P,c,1)\nv=tan(P,c,2)', 'tangentes P–c');
  const O = por(r, 'O'), P = por(r, 'P'), u = por(r, 'u'), v = por(r, 'v');
  [u, v].forEach((t, i) => {
    bien(sobreRecta(t, P), `tangente ${i + 1} pasa por P`);
    bien(casi(Math.abs(t.d.x * (O.y - t.p.y) - t.d.y * (O.x - t.p.x)), 2, 1e-9), `tangente ${i + 1} a distancia r del centro`);
    bien(casi(dist(t.p, O), 2, 1e-9), `el punto de tangencia ${i + 1} está en la circunferencia`);       // p = punto de tangencia (ancla)
    bien(Math.abs((t.p.x - O.x) * t.d.x + (t.p.y - O.y) * t.d.y) < 1e-9, `el radio al punto ${i + 1} es perpendicular a la tangente`);
  });
  bien(dist(u.p, v.p) > 1, 'las dos tangentes son distintas');
  conError('O=(0,0)\nP=(1,0)\nc=circunferencia(O,2)\nu=tan(P,c,1)', /dentro de la circunferencia/, 'punto interior sin tangentes', 4);
  const s = sinErrores('O=(0,0)\nP=(2,0)\nc=circunferencia(O,2)\nu=tan(P,c,1)', 'punto sobre la circunferencia');
  bien(Math.abs(por(s, 'u').d.x) < 1e-9, 'la tangente en (2,0) es vertical');
}
// ---------- 3.3 tangentes entre dos circunferencias ----------
{
  const r = sinErrores('O1=(0,0)\nO2=(7,0)\nc=circunferencia(O1,2)\nd=circunferencia(O2,1)\na=tan(c,d,1)\nb=tan(c,d,2)\ne=tan(c,d,3)\nf=tan(c,d,4)', 'tangentes entre circunferencias');
  const c = por(r, 'c'), d = por(r, 'd'), dd = (t, o) => Math.abs(t.d.x * (o.c.y - t.p.y) - t.d.y * (o.c.x - t.p.x));
  ['a', 'b', 'e', 'f'].forEach(n => { const t = por(r, n); bien(casi(dd(t, c), 2, 1e-9) && casi(dd(t, d), 1, 1e-9), `tangente común ${n}: distancias ${dd(t, c)} y ${dd(t, d)}`); });
  const ds = ['a', 'b', 'e', 'f'].map(n => por(r, n)), distintas = new Set(ds.map(t => t.d.x.toFixed(6) + ',' + t.d.y.toFixed(6) + ',' + (t.p.x * t.d.y - t.p.y * t.d.x).toFixed(5))).size;
  bien(distintas === 4, 'las 4 tangentes comunes son distintas');
  conError('O1=(0,0)\nO2=(2,0)\nc=circunferencia(O1,2)\nd=circunferencia(O2,1)\na=tan(c,d,3)', /solo tienen 2/, 'circunferencias secantes: solo 2 tangentes', 5);
}
// ---------- 3.4 intersecciones ----------
{
  const r = sinErrores('O=(0,0)\nA=(-4,1)\nB=(4,1)\nc=circunferencia(O,3)\nr=recta(A,B)\nP=interseccion(r,c,1)\nQ=interseccion(c,r,2)\nS=interseccion(r,recta(O,(0,5)))', 'recta–circunferencia');
  const c = por(r, 'c'), P = por(r, 'P'), Q = por(r, 'Q'), S = por(r, 'S');
  [P, Q].forEach((p, i) => bien(casi(dist(p, c.c), 3, 1e-9) && casi(p.y, 1, 1e-9), `punto ${i + 1} sobre la recta y la circunferencia`));
  bien(dist(P, Q) > 1, 'los dos puntos son distintos (' + P.x + ' y ' + Q.x + ')');
  bien(casi(S.x, 0) && casi(S.y, 1), 'recta–recta (0,1)');
  const cc = sinErrores('O=(0,0)\nO2=(3,0)\nc=circunferencia(O,2)\nd=circunferencia(O2,2)\nM1=interseccion(c,d,1)\nM2=interseccion(c,d,2)', 'circunferencia–circunferencia');
  const c1 = por(cc, 'c'), d1 = por(cc, 'd');
  ['M1', 'M2'].forEach(n => { const p = por(cc, n); bien(casi(dist(p, c1.c), 2, 1e-9) && casi(dist(p, d1.c), 2, 1e-9), `${n} está en las dos`); });
  bien(casi(por(cc, 'M1').x, 1.5) && casi(Math.abs(por(cc, 'M1').y), Math.sqrt(4 - 2.25)), 'M1 en x = 1.5');
  conError('O=(0,0)\nO2=(9,0)\nc=circunferencia(O,2)\nd=circunferencia(O2,2)\nM=interseccion(c,d,1)', /No hay intersección/, 'circunferencias lejanas', 5);
  conError('O=(0,0)\nA=(-4,5)\nB=(4,5)\nc=circunferencia(O,2)\nr=recta(A,B)\nP=interseccion(r,c,1)', /No hay intersección/, 'recta lejana', 6);
  conError('A=(0,0)\nB=(1,0)\nC=(0,1)\nD=(1,1)\nr=recta(A,B)\ns=recta(C,D)\nP=interseccion(r,s)', /paralelas/, 'rectas paralelas', 7);
  conError('A=(0,0)\nB=(1,0)\nC=(3,-1)\nD=(3,1)\ns=segmento(A,B)\nt=segmento(C,D)\nP=interseccion(s,t)', /no se cortan/, 'segmentos que no llegan a cortarse', 7);
}
// ---------- 3.4b el orden de los índices, comprobado contra GeoGebra real (calibración con 280 casos al azar; aquí unos fijos) ----------
{
  const c1 = sinErrores('O=(0,0)\nQ=(3,0)\nc=circunferencia(O,2)\nd=circunferencia(Q,2)\nX=interseccion(c,d,1)\nY=interseccion(d,c,1)', 'orden circ–circ');
  bien(casi(por(c1, 'X').y, Math.sqrt(1.75)) && casi(por(c1, 'Y').y, Math.sqrt(1.75)), 'circunferencias: el 1 es el de la izquierda de (creada antes a creada después), sin importar el orden de los argumentos');
  const l1 = sinErrores('O=(0,0)\nA=(-5,0)\nB=(5,0)\nc=circunferencia(O,2)\nl=recta(A,B)\nX=interseccion(l,c,1)\nY=interseccion(c,l,2)', 'orden recta–circ');
  bien(casi(por(l1, 'X').x, -2) && casi(por(l1, 'Y').x, 2), 'recta–circunferencia: el 1 es el primero yendo de A a B');
  const t1 = sinErrores('O=(0,0)\nP=(5,0)\nc=circunferencia(O,2)\nu=tan(P,c,1)', 'orden tan P–c');
  bien(por(t1, 'u').p.y > 1.5, 'tan(P,c,1) toca en el lado antihorario desde P (tangencia arriba)');
  const t2 = sinErrores('O1=(0,0)\nO2=(7,0)\nc=circunferencia(O1,2)\nd=circunferencia(O2,1)\na=tan(c,d,1)\nb=tan(c,d,2)\ne=tan(c,d,3)', 'orden tan c–d');
  bien(por(t2, 'a').p.y < -1.5 && por(t2, 'b').p.y > 1.5 && por(t2, 'e').p.y < -0.5 && por(t2, 'e').ancla[1].y > 0, 'tan(c,d,i): exteriores (abajo, arriba) y luego interiores');
}
// ---------- 3.5 construcciones: paralela, perpendicular, mediatriz, bisectriz, mediana, circunscrita ----------
{
  const r = sinErrores(pts + '\nr=recta(A,B)\np=paralela(C,r)\nq=perpendicular(D,r)\nm=mediatriz(A,B)\nb=bisectriz(B,A,C)\nmd=mediana(C,AB)\nc=circunferencia(A,B,C)', 'construcciones');
  const p = por(r, 'p'), q = por(r, 'q'), m = por(r, 'm'), b = por(r, 'b'), md = por(r, 'md'), c = por(r, 'c');
  bien(Math.abs(p.d.y) < 1e-9 && sobreRecta(p, {x: 7, y: 3}), 'paralela por C a AB (horizontal y = 3)');
  bien(Math.abs(q.d.x) < 1e-9 && sobreRecta(q, {x: 4, y: 0}), 'perpendicular por D a AB (x = 4)');
  bien(Math.abs(m.d.y) > 0.999999 && sobreRecta(m, {x: 2, y: 0}), 'mediatriz de AB (x = 2)');
  bien(casi(Math.abs(b.d.x), Math.SQRT1_2) && casi(Math.abs(b.d.y), Math.SQRT1_2) && sobreRecta(b, {x: 0, y: 0}), 'bisectriz del ángulo recto en A');
  bien(casi(md.b.x, 2) && casi(md.b.y, 0) && md.a.x === 0 && md.a.y === 3, 'mediana de C al punto medio de AB');
  bien(casi(c.c.x, 2) && casi(c.c.y, 1.5) && casi(c.r, 2.5), 'circunscrita del 3-4-5: centro (2, 1.5), radio 2.5');
  ['A', 'B', 'C'].forEach(n => bien(casi(dist(por(r, n), c.c), c.r, 1e-9), `la circunscrita pasa por ${n}`));
  conError('A=(0,0)\nB=(1,1)\nC=(2,2)\nc=circunferencia(A,B,C)', /colineales/, 'tres puntos colineales', 4);
  const o = sinErrores('A=(0,0)\nB=(1,0)\nC=(0,1)\nr=semirrecta(A,B)\ns=poligono(A,B,C)\nc=circunferencia(A,1)\na=arco(c,B,C)\nz=sector(c,B,C)\nL=area(z)\np=perimetro(s)\nQ=area(c)', 'figuras y medidas');
  bien(casi(por(o, 'a').sw, Math.PI / 2) && casi(por(o, 'L').v, Math.PI / 4) && casi(por(o, 'Q').v, Math.PI) && casi(por(o, 'p').v, 2 + Math.SQRT2), 'arco/sector de 90°, áreas y perímetro');
}
// ---------- 3.6 medidas ----------
{
  const r = sinErrores(pts + '\nt=triangulo(A,B,C)\nd=distancia(B,C)\na=angulo(A,B,C)\nb=angulo(B,A,C)\nS=area(t)\np=perimetro(t)', 'medidas');
  bien(casi(por(r, 'd').v, 5), 'distancia 5');
  bien(casi(por(r, 'a').v, 360 - Math.atan2(3, 4) * 180 / Math.PI), 'angulo(A,B,C) = antihorario desde BA a BC como GeoGebra');
  bien(casi(por(r, 'b').v, 90), 'angulo(B,A,C) = 90');
  bien(casi(por(r, 'S').v, 6) && casi(por(r, 'p').v, 12), 'área 6 y perímetro 12');
  ['d = 5', 'S = 6', 'p = 12', 'b = 90°'].forEach(tx => bien(r.svg.includes('>' + tx + '</text>'), 'rótulo de la medida «' + tx + '»'));
}
// ---------- 3.7 notaciones: se dibujan en su sitio ----------
{
  const r = sinErrores('A=(0,0)\nB=(4,0)\nC=(0,3)\nt=triangulo(A,B,C)\nangulorecto(B,A,C)\nmarcaigual(AB,2)\nmarcaangulo(A,B,C,1)\nmarcaparalela(AC,1)\netiqueta(BC,"5 cm")', 'notaciones');
  const v = r.vista, px = p => ({x: v.ox + p.x * v.escala, y: v.oy - p.y * v.escala});
  // el cuadradito del ángulo recto empieza a 15 px del vértice A, hacia B, y acaba a 15 px hacia C
  const m = /<path d="M([\d.-]+) ([\d.-]+)L([\d.-]+) ([\d.-]+)L([\d.-]+) ([\d.-]+)" fill="none" stroke="#24344a" stroke-width="2.1"/.exec(r.svg);
  bien(!!m, 'hay un cuadradito de ángulo recto');
  if (m) {
    const A = px(por(r, 'A')), B = px(por(r, 'B')), C = px(por(r, 'C')), q1 = {x: +m[1], y: +m[2]}, q2 = {x: +m[3], y: +m[4]}, q3 = {x: +m[5], y: +m[6]};
    bien(casi(Math.hypot(q1.x - A.x, q1.y - A.y), 15, 2e-2) && casi(Math.hypot(q3.x - A.x, q3.y - A.y), 15, 2e-2), 'el cuadradito está en el vértice A');
    bien(Math.abs((q1.x - A.x) * (B.x - A.x) + (q1.y - A.y) * (B.y - A.y)) / (15 * Math.hypot(B.x - A.x, B.y - A.y)) > 0.999 && Math.abs((q3.x - A.x) * (C.x - A.x) + (q3.y - A.y) * (C.y - A.y)) / (15 * Math.hypot(C.x - A.x, C.y - A.y)) > 0.999, 'sus lados van hacia B y hacia C');
    bien(casi(q2.x, q1.x + q3.x - A.x, 3e-2) && casi(q2.y, q1.y + q3.y - A.y, 3e-2), 'cierra el cuadrado');
  }
  bien((r.svg.match(/stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"\/>/g) || []).length >= 6, 'rayitas, arco, flecha y cuadradito dibujados');
  bien(r.svg.includes('>5 cm</text>'), 'etiqueta del lado');
  conError('A=(0,0)\nB=(4,0)\nC=(1,1)\nangulorecto(A,B,C)', /no es recto/, 'angulorecto en un ángulo que no lo es', 4);
  conError('A=(0,0)\nB=(4,0)\ns=segmento(A,B)\nc=circunferencia(A,B)\netiqueta(c,"x")', /segmento/, 'etiqueta sobre una circunferencia', 5);
  conError(pts + '\nmarcaigual(AB,0)', /grupo/, 'índice de grupo 0', 5);
}
// ---------- 3.8 alias, anidación, atajo y reglas de la gramática (como geo-parser.test.mjs) ----------
{
  sinErrores(pts + '\nt=triángulo(A,B,C)', 'alias con tilde');
  sinErrores(pts + '\nt=triangle(A,B,C)', 'alias en inglés');
  sinErrores(pts + '\na=ángulo(A,B,C)\nt=triángulo(A,B,C)\nx=área(t)\np=perímetro(t)', 'tildes en medidas');
  sinErrores(pts + '\nc=CIRCLE(A,2)\nm=Midpoint(A,B)\nT=TRIANGULO(A,B,C)', 'mayúsculas y nombres en inglés');
  const h = sinErrores(pts + '\nh=perpendicular(C,recta(A,B))', 'anidación');
  bien(h.objetos.length === 5 && !h.objetos.some(o => o.tipo === 'recta' && o.nombre !== 'h'), 'los objetos intermedios no salen como objetos');
  const sh = sinErrores(pts + '\nm=mediana(C,AB)', 'atajo AB');
  bien(casi(por(sh, 'm').b.x, 2), 'mediana(C,AB) usa el punto medio de AB');
  const w = sinErrores(pts + '\nAB=segmento(C,D)\nm=mediana(A,AB)', 'nombre definido gana al atajo');
  bien(casi(por(w, 'm').b.x, 2) && casi(por(w, 'm').b.y, 3), 'mediana(A,AB) usa el segmento CD llamado AB');
  sinErrores(pts + '\ns=segmento(A,B)\nm=mediana(C,s)', 'unión segmento|par');
  sinErrores(pts + '\nc=circunferencia(A,2)\nt=tan(D,c,2)', 'tan índice 2');
  sinErrores(pts + '\nc=circunferencia(A,B)\nr=recta(C,D)\nP=interseccion(c,r,1)', 'interseccion(c,r,1)');
  sinErrores('A=(1/2, sqrt(3)/2)\nB=(-2*pi/3, 1.5)', 'coordenadas con expresiones');
  bien(casi(por(G('A=(1/2, sqrt(3)/2)'), 'A').y, Math.sqrt(3) / 2), 'coordenada sqrt(3)/2');
  sinErrores(pts + '\ns=segmento(A,B) fijo', 'sufijo fijo');
  conError('puntomedio(A,B)', /nombre.*=/i, 'falta el nombre', 1);
  conError('A=(0,0)\ns=segmento(A,B)\nB=(1,0)', /adelantada/i, 'referencia adelantada', 2);
  conError('A=(0,0)\nA=(1,1)', /repetido/i, 'nombre repetido', 2);
  conError(pts + '\ns=segmento(A)', /aridad/i, 'aridad', 5);
  conError(pts + '\nr=recta(A,B)\ns=segmento(A,r)', /argumento 2.*punto.*recta/i, 'tipos', 6);
  conError('A=(a,3)', /variable libre/i, 'variable libre', 1);
  conError('A=(0,0', /delimitadores/i, 'paréntesis', 1);
  conError(pts + '\nx=comandoInventado(A)', /GEO_COMMANDS/i, 'comando inventado', 5);
  conError(pts + '\nx=baricentro(A)', /Fase 2/i, 'comando de la Fase 2 (también lo rechaza MathStudio)', 5);
  conError(pts + '\nc=circunferencia(A,B)\nt=tan(D,c)', /2 ramas.*índice/i, 'tan sin índice', 6);
  conError(pts + '\nc=circunferencia(A,B)\nd=circunferencia(D,2)\nt=tan(c,d)', /4 ramas.*índice/i, 'tan de dos circunferencias sin índice', 7);
  conError(pts + '\nc=circunferencia(A,B)\nt=tan(D,c,3)', /índice debe estar entre 1 y 2/i, 'índice fuera de rango', 6);
  conError(pts + '\nc=circunferencia(A,B)\nd=circunferencia(D,C)\nP=interseccion(c,d)', /2 ramas.*índice/i, 'interseccion sin índice', 7);
  conError('A=(0,0)\nB=(1,0)\netiqueta(AB,"sin cierre)', /comillas/i, 'literal sin cerrar', 3);
  conError('A=(0,0)\nB=(1,0)\nt="hola"', /texto/i, 'texto con nombre', 3);
  conError('A=(0,0)\nB=(0,0)\ns=segmento(A,B)', /coinciden/i, 'puntos coincidentes', 3);
  conError('punto', /nombre.*=/i, 'una palabra suelta', 1);
  conError('A=(0,0)\nB=(1,0)\nP=punto(c)', /Referencia|MathStudio/i, 'punto(o) → esto, en MathStudio', 3);
  conError('A=(0,0)\nB=(1,0)\nc=circunferencia(A,B)\nP=punto(c)', /MathStudio/i, 'punto(o) sobre una circunferencia: esto, en MathStudio', 4);
}
// ---------- 3.9 errores por línea: lo válido se dibuja igual ----------
{
  const r = G('A=(0,0)\nB=(4,0)\nC=(2,3)\nt=triangulo(A,B,Z)\ns=segmento(A,B)\nu=segmento(B,C)\nv=recta(A,t)\nw=segmento(t,C)');
  bien(r.errores.length === 3 && [4, 7, 8].join() === r.errores.map(e => e.linea).join(), 'errores en las líneas 4, 7 y 8 (' + r.errores.map(e => e.linea) + ')');
  bien(/«t» no se pudo construir.*línea 4/.test(r.errores[2].mensaje), 'un nombre que falló lo dice: ' + r.errores[2].mensaje);
  bien(r.svg.includes('>A</text>') && r.svg.includes('>C</text>') && !!r.svg.length, 'con errores se dibuja lo válido');
  bien(G('').svg === '' && G('   \n\n').errores.length === 0, 'guion vacío: nada que dibujar y sin errores');
  const solo = G('x=(0,0'); bien(solo.svg === '' && solo.errores.length === 1, 'solo errores: sin dibujo');
}
// ---------- 3.10 el SVG: puntos con nombre, margen, vista manual, autocontenido ----------
{
  const r = sinErrores('A=(0,0)\nB=(6,0)\nC=(2,5)\nt=triangulo(A,B,C)\nc=circunferencia(A,B,C)\nM=puntomedio(B,C)\nh=altura(A,BC)\nP=interseccion(h,recta(B,C))\nangulorecto(A,P,B)\nd=distancia(A,P)', 'figura completa');
  ['A', 'B', 'C', 'M', 'P'].forEach(n => bien(r.svg.includes('>' + n + '</text>'), 'el punto ' + n + ' lleva su nombre'));
  bien(!/<script|<a |href=|xlink|javascript:|onload=|onclick=/i.test(r.svg), 'sin scripts ni enlaces');
  bien(/^<svg xmlns="http:\/\/www.w3.org\/2000\/svg" width="[\d.]+" height="[\d.]+" viewBox="[-\d. ]+" font-family="'Segoe UI', system-ui/.test(r.svg), 'cabecera con width/height/viewBox/Segoe UI');
  const [vx, vy, vw, vh] = r.vista.viewBox;
  bien(casi(vw, r.w) && casi(vh, r.h), 'width/height = viewBox en px');
  // margen: ningún punto ni texto a menos de 8 px del borde del viewBox; la circunferencia entera dentro
  const c = por(r, 'c'), v = r.vista, cx = v.ox + c.c.x * v.escala, cy = v.oy - c.c.y * v.escala, rr = c.r * v.escala;
  bien(cx - rr >= vx + 8 && cx + rr <= vx + vw - 8 && cy - rr >= vy + 8 && cy + rr <= vy + vh - 8, 'la circunferencia cabe con margen');
  let fuera = 0; const re = /<text x="([-\d.]+)" y="([-\d.]+)"/g; let m;
  while ((m = re.exec(r.svg))) if (+m[1] < vx + 6 || +m[1] > vx + vw - 6 || +m[2] < vy + 6 || +m[2] > vy + vh - 2) fuera++;
  bien(fuera === 0, 'ningún texto pegado al borde (' + fuera + ')');
  const claro = G('A=(0,0)\nB=(1,1)', {tema: 'claro'}).svg, osc = G('A=(0,0)\nB=(1,1)', {tema: 'oscuro'}).svg;
  bien(claro.includes(F.estilo.claro.punto) && osc.includes(F.estilo.oscuro.punto) && claro !== osc, 'claro y oscuro');
  const man = G('A=(0,0)\nB=(10,10)\ns=segmento(A,B)', {x: [-2, 4], y: [-2, 4], ejes: true, rejilla: true});
  bien(/clip-path="url\(#rec/.test(man.svg) && man.svg.includes('>2</text>'), 'vista manual con ejes y recorte');
  const lins = G('A=(0,0)\nB=(1,1)\nr=recta(A,B)'); bien(lins.w >= 480 - 1 && lins.h >= 480 * 0.34 - 1, 'una recta sola tiene tamaño razonable');
  bien(G('A=(1,1)').w === 480 && G('A=(1,1)').svg.includes('>A</text>'), 'un solo punto');
  ['S', 'L'].forEach((t, i) => bien(G(pts, {tam: t}).w >= [320, 720][i] - 1, 'geometría tamaño ' + t));
  bien(G('A=(0,0)\nB=(3,4)', {fondo: 'blanco'}).svg.includes('fill="#ffffff"'), 'geometría con fondo blanco');
}

console.log(mal ? mal + ' fallos de ' + hechos + ' comprobaciones' : 'figuras: todo bien (' + hechos + ' comprobaciones)');
process.exitCode = mal ? 1 : 0;
