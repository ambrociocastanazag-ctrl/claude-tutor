# Tutor de estudio

Un tutor personalizado que corre dentro de Claude Code. Tú traes un tema, un curso o un programa que quieres aprender, y el tutor te explica, te pone ejercicios y, cuando la herramienta existe, te enseña **dentro del propio programa**, señalándote encima de la ventana dónde hacer cada cosa.

## Qué incluye

- [`tutor-pantalla/`](../tutor-pantalla/README.md): un asistente que mira **una** ventana de cualquier programa (solo cuando tú lo apruebas) y dibuja flechas y anotaciones encima. También sirve para armar cursos de un programa. Nunca mueve el ratón ni escribe por ti.
- [`panel-excel/`](../panel-excel/README.md): clase en vivo dentro de Excel.
- [`prueba-dia/`](../prueba-dia/README.md): clase en vivo dentro del editor de diagramas Dia.
- [`tarjeta-svg/`](../tarjeta-svg/README.md) y [`clase-viva/`](../clase-viva/README.md): figuras y guías interactivas con el tutor.
- [`herramientas/`](../herramientas/): capturas con Chrome y búsqueda de fotos y videos con licencia libre.

## Instalación

Necesitas Python 3, git y Claude Code.

```
git clone https://github.com/ambrociocastanazag-ctrl/claude-tutor tutor-de-estudio
cd tutor-de-estudio
python -m pip install -r paquete-tutor/requirements.txt
```

Abre Claude Code en esa carpeta y dile: **«lee [INSTALAR_TUTOR.md](../INSTALAR_TUTOR.md) y síguelo»**. Te hará unas preguntas y dejará la carpeta convertida en tu tutor.

## Actualizar

```
git pull
```

Tus temas, cursos y preferencias no se versionan, así que actualizar no choca con lo tuyo.
