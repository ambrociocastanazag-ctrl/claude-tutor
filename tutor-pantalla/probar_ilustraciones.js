// node tutor-pantalla/probar_ilustraciones.js: intérprete de expresiones y texto→marcas de ilustraciones_ui.js
const I = require(require('path').join(__dirname, 'ilustraciones_ui.js'));
let mal = 0;
const igual = (a, b) => (Number.isNaN(b) ? Number.isNaN(a) : a === b || Math.abs(a - b) < 1e-9);
[['2x+1',3,7],['2(x+1)',1,4],['-x^2',3,-9],['2^-x',1,.5],['2^3^2',0,512],['sqrt(x)',-1,NaN],['1/2x',4,2],['sinx',Math.PI/2,1],['x^(1/3)',-8,-2],['2π',0,2*Math.PI],['√x',9,3],['log(x)',100,2],['y = x+1',1,2],['x²',4,16],['(x+1)(x-1)',3,8],['1/x',0,Infinity]]
 .forEach(([e,x,v]) => { const r = I.compilar(e)(x); if (!igual(r,v)){ mal++; console.log('MAL', e, r, v); } });
['', '2+', 'sqrt', 'foo(x)', '(1+2', 'x;1', 'alert(1)', 'constructor'].forEach(e => { try { I.compilar(e); mal++; console.log('debía fallar', e); } catch (_) {} });
const t = I.antes('cuesta $5 y $10; =SUMA($B$2:$B$9); $x^2$; `$a$`');
if ((t.match(/\u0002/g) || []).length !== 1 || !t.includes('$5 y $10') || !t.includes('$B$2:$B$9') || !t.includes('`$a$`')) { mal++; console.log('antes MAL', JSON.stringify(t)); }
// bloques ```3d: marca con la spec, mayúsculas, hueco mientras no está cerrado, y los otros bloques siguen igual
const j3 = '{"revolucion": "sqrt(x)", "x": [0, 4]}';
const t3 = I.antes('mira\n```3d\n' + j3 + '\n```\nlisto'), t3b = I.antes('```3D Pie\n' + j3 + '\n```');
const r3 = Object.values(I._reg).filter(r => r.tipo === '3d');
if ((t3.match(/\u0002/g) || []).length !== 1 || t3.includes('```') || !r3.some(r => r.json === j3)) { mal++; console.log('3d MAL', JSON.stringify(t3)); }
if ((t3b.match(/\u0002/g) || []).length !== 1 || !r3.some(r => r.json === j3 && r.pie === 'Pie')) { mal++; console.log('3D MAL', JSON.stringify(t3b)); }
['```3d\n{"objetos": [', '```3', '```3d'].forEach(c => {
  const h = I.antes('texto\n' + c), id = (/\u0002(.+?)\u0003/.exec(h) || [])[1];
  if (!id || I._reg[id].tipo !== 'hueco') { mal++; console.log('3d a medias MAL', JSON.stringify(c), JSON.stringify(h)); }
});
const og = I.antes('```grafica\n{"x":[0,1]}\n```'), os = I.antes('```svg\n<svg viewBox="0 0 1 1"/>\n```');
if (!/\u0002g/.test(og) || !/\u0002s/.test(os)) { mal++; console.log('los otros bloques MAL'); }
const k3 = I.antes('```\ncódigo normal 3d\n```');
if (/\u0002/.test(k3) || !k3.includes('```')) { mal++; console.log('código normal MAL', JSON.stringify(k3)); }
// aGuion para «Editar en la tarjeta» (con motor_3d en node)
try {
  const M = require(require('path').join(__dirname, 'motor_3d.js'));
  const gu = M.aGuion(Object.assign(JSON.parse(j3), {vista: [10, 20]}));
  if (!gu || !/revolucion\(sqrt\(x\), 0, 4\)/.test(gu) || !/vista\(10, 20\)/.test(gu)) { mal++; console.log('aGuion MAL', gu); }
} catch (e) { mal++; console.log('motor_3d no carga', e.message); }
console.log(mal ? mal + ' fallos' : 'todo bien');
