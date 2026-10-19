/* Atajos del campo de ecuación de la Tarjeta SVG.
 * Son los de MathStudio (js/mathfield.js + js/comandos.js), tal cual, pero como script normal
 * (no módulo ES): window.Atajos = {inlineShortcuts, configurar(mathfield)}.
 *
 * REGLA DE PREFIJOS (de la documentación de MathStudio, §5): MathLive espera a ver si hay un atajo
 * más largo, pero esa espera se pierde si el atajo corto lleva un marcador #?: el cursor salta al
 * marcador y lo tecleado se corta ahí. Así que un atajo cuyo prefijo sea otro atajo con #? NUNCA
 * se dispara. Por eso: 'base' y no 'logb'; 'sah/cah/tah' y no sinh/cosh/tanh (los anulaban sin,
 * cos, tan) ni sh/ch/th (anulaban theta y chi); 'vec' ocupa el prefijo (no puede haber 'vector').
 * Al añadir uno, compara en las dos direcciones contra estos y contra los de MathLive (letras griegas
 * incluidas: siguen activos, porque configurar() los conserva).
 */
(function (global) {
  'use strict';

  var inlineShortcuts = {
    sen: '\\sin\\left(#?\\right)',
    sin: '\\sin\\left(#?\\right)',
    cos: '\\cos\\left(#?\\right)',
    tan: '\\tan\\left(#?\\right)',
    sec: '\\sec\\left(#?\\right)',
    csc: '\\csc\\left(#?\\right)',
    cot: '\\cot\\left(#?\\right)',
    arcsin: '\\arcsin\\left(#?\\right)',
    arccos: '\\arccos\\left(#?\\right)',
    arctan: '\\arctan\\left(#?\\right)',
    sah: '\\sinh\\left(#?\\right)',
    cah: '\\cosh\\left(#?\\right)',
    tah: '\\tanh\\left(#?\\right)',
    log: '\\log\\left(#?\\right)',
    ln: '\\ln\\left(#?\\right)',
    lg: '\\operatorname{lg}\\left(#?\\right)',
    RR: '\\mathbb{R}',
    NN: '\\mathbb{N}',
    ZZ: '\\mathbb{Z}',
    QQ: '\\mathbb{Q}',
    CC: '\\mathbb{C}',
    '+-': '\\pm',
    '!=': '\\ne',
    '~=': '\\approx',
    approx: '\\approx',
    inf: '\\infty',
    period: '\\overline{#?}',
    vec: '\\vec{#?}',
    base: '\\log_{#?}\\left(#?\\right)',
    '->': '\\to',
    '<-': '\\leftarrow',
    '<->': '\\leftrightarrow',
    sqrt: '\\sqrt{#?}',
    root: '\\sqrt[#?]{#?}',
    abs: '\\left|#?\\right|',
    sum: '\\sum_{#?}^{#?}#?',
    prod: '\\prod_{#?}^{#?}#?',
    int: '\\int_{#?}^{#?}#?\\,d#?',
    lim: '\\lim_{#?\\to#?}#?',
    matrix: '\\begin{pmatrix}#?&#?\\\\#?&#?\\end{pmatrix}',
    cases: '\\begin{cases}#?&#?\\\\#?&#?\\end{cases}',
    system: '\\left\\{\\begin{aligned}#?&#?\\\\#?&#?\\end{aligned}\\right.',
    'eval[]': '\\left[#?\\right]_{#?}^{#?}',
    'eval|': '\\left.#?\\right|_{#?}^{#?}'
  };

  // Igual que configurarMathfield() de MathStudio: primero los de MathLive, encima los propios.
  function configurar(mathfield) {
    mathfield.smartMode = false;
    mathfield.smartFence = true;
    mathfield.removeExtraneousParentheses = false;
    var base = mathfield.inlineShortcuts || {};
    var todos = {};
    Object.keys(base).forEach(function (k) { todos[k] = base[k]; });
    Object.keys(inlineShortcuts).forEach(function (k) { todos[k] = inlineShortcuts[k]; });
    mathfield.inlineShortcuts = todos;
  }

  global.Atajos = { inlineShortcuts: inlineShortcuts, configurar: configurar };
})(window);
