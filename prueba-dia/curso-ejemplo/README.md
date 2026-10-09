# Curso de ejemplo: «UML en Dia: primeros pasos»

Un curso pequeño para el panel de clase en vivo de Dia (`../panel_dia.py`) que usa todo lo que el panel sabe hacer y sirve de **plantilla** para escribir cursos nuevos. Se abre con:

```
python prueba-dia/panel_dia.py prueba-dia/curso-ejemplo/curso.json
python prueba-dia/panel_dia.py prueba-dia/curso-ejemplo/curso.json --probar    # sin ventanas: pasos, Tu turno y errores típicos
```

| Módulo | Pasos | Lo que enseña del panel |
|---|---|---|
| 1. Clases y relaciones (`m1_clases.json`) | dos clases, asociación con multiplicidades, herencia, añadir un atributo, Tu turno | flechas a la herramienta Clase, Asociación y Generalización; «Hazlo por mí» (elegir la herramienta; abrir Propiedades de Libro en Atributos) con flechas a Libro, la pestaña, «Nuevo» y el campo «Nombre» |
| 2. Casos de uso (`m2_casos.json`) | actor y caso, «include», «extend», Tu turno | el Tu turno empieza con los objetos dibujados (`inicial`) y la persona añade las relaciones; tres errores típicos (extend por include, include al revés, extend al revés) |
| 3. Secuencia (`m3_secuencia.json`) | participantes, mensajes en orden, retorno, un mensaje en medio, Tu turno | mensajes que se meten entre dos (`despues_de`); errores típicos de orden y de retorno |

## Historia y decisiones

- **2026-10-08:** hecho junto con los cursos de Dia (ver «Historia y decisiones» de `../README.md`). Tres módulos cortos para que se pruebe todo en pocos minutos: cada uno con pasos que se suman, algo que señalar en Dia y un «Tu turno» con solución y errores típicos comprobados por `--probar`.
- Comprobado: `--probar` (todo bien) y los tres módulos armados en un Dia aparte con una copia del curso.

## Archivos

- `curso.json`: título, modelo del tutor y la lista de módulos.
- `m1_clases.json`, `m2_casos.json`, `m3_secuencia.json`: los módulos (formato en «Cómo hacer un curso» de `../README.md`).
- **Se generan** al abrirlo (no se editan ni van al repositorio): `pasos/` (la pestaña de la lección y los pasos de cada módulo armados en Dia), `tutor/` (lo que crea el tutor) y `progreso.json` (dónde te quedaste).
- **Son de quien estudia:** `mis_diagramas/mi_clases.dia`, `mi_casos.dia`, `mi_secuencia.dia` (uno por módulo). El panel los crea si no existen y nunca los sobrescribe.

## Cómo cambiarlo

1. Edita el JSON del módulo (o copia la carpeta para un curso nuevo).
2. `python prueba-dia/panel_dia.py <curso.json> --probar` hasta que termine en «Curso de Dia: todo bien».
3. Ábrelo con el panel: la primera vez que entres a un módulo cambiado, sus pasos se vuelven a armar en Dia.

## Dependencias

Las del panel de Dia (`../README.md`).
