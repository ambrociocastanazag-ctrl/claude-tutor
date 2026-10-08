// Abre una página en el Chrome instalado, espera a que dibuje, guarda una captura y, si se pide,
// evalúa una expresión de JavaScript en la página e imprime el resultado en JSON.
//   node captura.js <url|archivo.txt> <salida.png> [espera_ms] [expresión JS]
const puppeteer = require('puppeteer-core');
const fs = require('fs');

const [, , destino, salida, espera = '4000', expr] = process.argv;
if (!destino || !salida) { console.error('uso: node captura.js <url|archivo.txt> <salida.png> [espera_ms] [expresión]'); process.exit(1); }
const url = fs.existsSync(destino) ? fs.readFileSync(destino, 'utf8').trim() : destino;

(async () => {
  const navegador = await puppeteer.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: true,
    args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--no-first-run'],
    defaultViewport: { width: 1400, height: 850 },
  });
  try {
    const pagina = await navegador.newPage();
    const errores = [];
    pagina.on('pageerror', e => errores.push(String(e.message || e)));
    pagina.on('console', m => { if (m.type() === 'error' || m.type() === 'warn') errores.push(m.type() + ': ' + m.text().slice(0, 200)); });
    await pagina.goto(url, { waitUntil: 'networkidle2', timeout: 60000 });
    await new Promise(r => setTimeout(r, Number(espera)));
    await pagina.screenshot({ path: salida });
    const res = { errores };
    if (expr) res.valor = await pagina.evaluate(expr).catch(e => 'ERROR: ' + e.message);
    console.log(JSON.stringify(res));
  } finally {
    await navegador.close();
  }
})().catch(e => { console.error(e.message); process.exit(1); });
