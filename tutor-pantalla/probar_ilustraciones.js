// node tutor-pantalla/probar_ilustraciones.js: intérprete de expresiones y texto→marcas de ilustraciones_ui.js
const I = require(require('path').join(__dirname, 'ilustraciones_ui.js'));
let mal = 0;
const igual = (a, b) => (Number.isNaN(b) ? Number.isNaN(a) : a === b || Math.abs(a - b) < 1e-9);
[['2x+1',3,7],['2(x+1)',1,4],['-x^2',3,-9],['2^-x',1,.5],['2^3^2',0,512],['sqrt(x)',-1,NaN],['1/2x',4,2],['sinx',Math.PI/2,1],['x^(1/3)',-8,-2],['2π',0,2*Math.PI],['√x',9,3],['log(x)',100,2],['y = x+1',1,2],['x²',4,16],['(x+1)(x-1)',3,8],['1/x',0,Infinity]]
 .forEach(([e,x,v]) => { const r = I.compilar(e)(x); if (!igual(r,v)){ mal++; console.log('MAL', e, r, v); } });
['', '2+', 'sqrt', 'foo(x)', '(1+2', 'x;1', 'alert(1)', 'constructor'].forEach(e => { try { I.compilar(e); mal++; console.log('debía fallar', e); } catch (_) {} });
const t = I.antes('cuesta $5 y $10; =SUMA($B$2:$B$9); $x^2$; `$a$`');
if ((t.match(/\u0002/g) || []).length !== 1 || !t.includes('$5 y $10') || !t.includes('$B$2:$B$9') || !t.includes('`$a$`')) { mal++; console.log('antes MAL', JSON.stringify(t)); }
console.log(mal ? mal + ' fallos' : 'todo bien');
