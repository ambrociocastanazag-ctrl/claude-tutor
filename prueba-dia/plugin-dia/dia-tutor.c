/* dia-tutor.c — plugin para Dia 0.97.2 (Windows, 32 bits) que deja mandar ordenes a la
 * ventana abierta desde fuera (Python). Prototipo del tutor en vivo.
 *
 * Cada 100 ms mira si existe <dir>/orden.txt. Si esta, lo lee, lo borra,
 * ejecuta sus lineas sobre el diagrama abierto y escribe <dir>/respuesta.txt.
 * <dir> = %DIA_TUTOR_DIR%, o si no, %USERPROFILE%\.dia\tutor
 *
 * Ordenes (una por linea; admite comillas; "@archivo.dia" elige el diagrama por nombre,
 * si no se da se usa el diagrama activo):
 *   ping
 *   ventanas                    lista los diagramas abiertos (* = activo)
 *   widgets                     posicion en pantalla de ventanas, menus, botones, pestanas, campos
 *   clase X Y NOMBRE            crea una clase UML en (X,Y) cm
 *   seleccionar NOMBRE          selecciona los objetos con ese nombre (resalta)
 *   deseleccionar
 *   cargar RUTA.dia             sustituye el contenido de la capa activa por el del archivo
 *   accion NOMBRE               dispara una accion del menu (ObjectsProperties, FileSave, ViewShowall...)
 *   pulsar TEXTO                pulsa el boton (o abre la pestana) con ese texto visible
 *   activar                     pone al frente la pestana del diagrama (con @archivo.dia) y su ventana
 *   modificado                  "si" si el diagrama (con @archivo.dia) tiene cambios sin guardar, "no" si no
 *
 * Marcas del tutor (en la capa propia "Tutor", encima de las demas; se crea si no existe y la capa
 * activa NO cambia, asi lo que dibuje la persona sigue yendo a su capa). No pasan por Deshacer ni
 * marcan el diagrama como modificado. COLOR = rojo, verde, amarillo, azul, negro o #rrggbb.
 *   recuadro X Y W H [COLOR] [GROSOR]          marco sin relleno (cm del diagrama)
 *   flecha X1 Y1 X2 Y2 [COLOR] [GROSOR] [TEXTO] linea con punta en (X2,Y2) y, si se da, un rotulo
 *   nota X Y TEXTO [COLOR] [HX HY]             texto en negrita con fondo suave y borde, esquina
 *                                              superior izquierda en (X,Y); con HX HY, flecha hasta ahi.
 *                                              Responde "ok nota x y w h" (la caja de la nota)
 *   borrar_marcas                              vacia la capa "Tutor" (no la quita: ver README)
 *   cajas [NOMBRE]                             caja actual (cm) de cada objeto con nombre, fuera de la capa
 *                                              Tutor, y de cada fila (atributo/metodo) de las clases UML.
 *                                              Lineas separadas por tabuladores:
 *                                              caja  NOMBRE TIPO X Y W H
 *                                              fila  CLASE MIEMBRO atributo|metodo X Y W H
 *   capas                                      capas de abajo arriba: "capa NOMBRE N_OBJETOS [activa]"
 *
 * Cambios del tutor que SI cuentan como cambio del diagrama (pasan por el Deshacer de Dia: el diagrama
 * queda modificado, Dia pregunta al cerrar y Ctrl+Z los deshace; van a la capa de la persona, nunca a "Tutor").
 * REF = tag:ETIQUETA (meta "tutor" de lo que creo el tutor) | clase:NOMBRE | id:On (el "id" de la orden copia).
 *   anadir RUTA            anade (sin borrar nada) los objetos de RUTA.dia y pega cada relacion a sus clases:
 *                          meta "conecta_inicio"/"conecta_fin" = REF o REF#PUNTO (punto de conexion; si no, automatico).
 *                          Responde "nuevo<TAB>ETIQUETA<TAB>TIPO" por objeto y "ok anadidos N". Si una REF no existe, no anade nada.
 *   quitar REF [REF...]    quita esos objetos; lo que estaba pegado a ellos queda suelto ("falta<TAB>REF" si no esta)
 *   reemplazar REF RUTA    el objeto toma las propiedades (nombre, atributos, metodos...) del objeto del mismo tipo de RUTA,
 *                          sin moverse ni soltar sus relaciones
 *   transaccion            cierra el grupo de cambios (un Ctrl+Z lo deshace entero). Responde "ok transaccion ID"
 *   deshacer_ultimo ID     si lo ultimo de la pila de Deshacer es el grupo ID, lo deshace como Ctrl+Z ("ok deshecho" +
 *                          "guardado" o "modificado"); si no, "no es lo ultimo"
 *   copia RUTA             guarda en RUTA una copia de lo que hay en pantalla (sin tocar el archivo ni el estado de guardado)
 *   abrir RUTA             abre el archivo como pestana nueva de la misma ventana (sin @; "ok ya abierto" si ya estaba)
 *   guardar                guarda el diagrama en su archivo (lo usa el panel solo con los diagramas del tutor)
 *   cerrar [forzar]        cierra la pestana sin dialogo (si tiene cambios sin guardar, solo con forzar)
 *   mover REF DX DY        mueve un objeto (cm) arrastrando lo que tiene pegado (para pruebas; no pasa por Deshacer)
 *   version                "ok version 5" (el panel la usa para saber si el plugin sabe aplicar cambios)
 *
 * Version 4: cualquier tipo de diagrama (casos de uso, secuencia, actividades, estados, componentes... y el modo libre)
 *   REF tambien puede ser nombre:TEXTO (cualquier objeto por su nombre, su texto o su meta "nombre"), y en
 *   conecta_inicio/conecta_fin, REF@X,Y = el punto de conexion de ese objeto mas cercano a (X, Y) (lineas de vida, lados).
 *   poner REF PROP=VALOR [PROP=VALOR...]   cambia propiedades de cualquier objeto con el sistema de propiedades de Dia
 *                          (texto con \n, numeros, true/false, #rrggbb o color por nombre, enum/flecha/estilo por numero, X,Y,
 *                          fuente "sans[,negrita]"). Un solo cambio con Deshacer. Responde "antes PROP VALOR" y "ok puesto REF".
 *                          No acepta propiedades de archivo ni listas.
 *   reemplazar REF RUTA geometria   como reemplazar, pero copiando tambien la esquina y el tamano
 *   medir RUTA             importa RUTA sin anadirla y dice el tamano real de cada objeto: "medida ETIQUETA TIPO X Y W H [EX EY EW EH]"
 *   exportar RUTA          dibuja lo que hay en pantalla en RUTA (.svg o .png por la extension) sin la capa "Tutor" y sin dialogos
 *   tipos                  "tipo NOMBRE" de cada tipo de objeto registrado (868 en este Dia)
 *   plantilla TIPO RUTA    guarda en RUTA (.dia) un objeto de ese tipo con sus valores por defecto (para catalogo.py)
 *   propiedades TIPO       "prop NOMBRE TIPO FLAGS DESCRIPCION [opcion=valor...]" de cada propiedad del tipo
 *   cajas                  ademas de "caja" y "fila", una linea "objeto On TIPO X Y W H NOMBRE" por cada objeto (con o sin nombre)
 *
 * Version 5: la clase en vivo sobre la interfaz de Dia (flechas del panel encima de la ventana y «hazlo por mi»)
 *   widgets                ahora la linea "ventana" lleva hwnd="N" (el HWND de Windows) y rol="..." (properties_window = Propiedades),
 *                          y los botones de alternar que estan pulsados (la herramienta elegida) acaban en " activo"
 *   pantalla REF [REF...]  donde se ve cada objeto en la pantalla (pixeles, como widgets) si su pestana esta a la vista:
 *                          "lienzo X Y W H" y "pantalla<TAB>REF<TAB>X<TAB>Y<TAB>W<TAB>H" (o "fuera"/"falta"); REF o un nombre
 *   seleccionar REF [REF...]  con tag:/nombre:/id:/clase: (o varios nombres) selecciona todos los que encuentra
 *   hoja NOMBRE            pone esa hoja (UML, Flowchart...) en la caja de herramientas, como elegirla en su menu
 *   (una sola instancia)   dueno.txt guarda el PID del Dia que atiende la carpeta; otro Dia que arranque con la misma carpeta
 *                          mientras ese siga vivo no recibe ordenes (si no, se quitarian las ordenes y respuestas el uno al otro)
 *   (seguridad) si el dialogo Propiedades edita un objeto que «cargar», «quitar» o un Deshacer quitan, se cierra antes:
 *                          si no, «Aceptar» tocaria un objeto destruido y Dia se cerraria
 *
 * Se compila con compilar.py (MinGW de C:\MinGW + cabeceras de Dia 0.97.2 y GTK 2.24).
 */
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <stdlib.h>
#include <glib.h>
#include <glib/gstdio.h>
#include <gtk/gtk.h>

#include "plug-ins.h"
#include "object.h"
#include "diagramdata.h"
#include "properties.h"
#include "prop_text.h"
#include "prop_inttypes.h"
#include "prop_geomtypes.h"
#include "prop_attr.h"
#include "prop_sdarray.h"
#include "arrows.h"
#include "font.h"
#include "color.h"
#include "filter.h"
#include "diagram.h"
#include "display.h"
#include "undo.h"
#include "interface.h"   /* ToolButtonData: que objeto crea cada boton de la caja de herramientas */
#include "group.h"
#include "load_save.h"
#include "connectionpoint_ops.h"
/* el menu de hojas de la caja de herramientas (DiaDynamicMenu, de lib/widgets.h, que no se puede incluir: pide config.h) */
typedef struct _DiaDynamicMenu DiaDynamicMenu;
void dia_dynamic_menu_select_entry(DiaDynamicMenu *ddm, const gchar *entry);
/* HWND de cada ventana, para el overlay del panel (de gdk/gdkwin32.h, que no se incluye: trae windows.h y su Rectangle choca con el de Dia) */
gpointer gdk_win32_drawable_get_handle(GdkDrawable *drawable);
#include <math.h>

static gchar *dir_ordenes = NULL;
static void destruir(GList *objs);
static void cerrar_dialogo_de(GList *objs);   /* version 5, mas abajo */
static void poner_titulo(Diagram *dia);

static void tlog(const char *fmt, ...)
{
  gchar *ruta = g_build_filename(dir_ordenes, "log.txt", NULL);
  FILE *f = g_fopen(ruta, "ab");
  if (f) {
    va_list ap; va_start(ap, fmt); vfprintf(f, fmt, ap); va_end(ap);
    fputc('\n', f); fclose(f);
  }
  g_free(ruta);
}

/* ---- utilidades sobre objetos ---- */

static gchar *nombre_de(DiaObject *obj)
{
  GPtrArray *props = g_ptr_array_new();
  StringProperty *sp = (StringProperty *) make_new_prop("name", PROP_TYPE_STRING, 0);
  gchar *n;
  g_ptr_array_add(props, sp);
  if (obj->ops->get_props) obj->ops->get_props(obj, props);
  n = g_strdup(sp->string_data ? sp->string_data : "");
  prop_list_free(props);
  return n;
}

/* nombre "visible" de cualquier objeto (version 4): su "name"; si no tiene, su texto ("text", como texto
 * con formato o como cadena); si no, la meta "nombre" (la que pone el tutor a los objetos sin texto:
 * nodo inicial, decision...). Se usa para las cajas de las marcas y para las referencias nombre:TEXTO. */
static gchar *nombre_visible(DiaObject *obj)
{
  gchar *n = nombre_de(obj);
  if (!*n && obj->ops->get_props) {
    GPtrArray *props = g_ptr_array_new();
    TextProperty *tp = (TextProperty *) make_new_prop("text", PROP_TYPE_TEXT, 0);
    g_ptr_array_add(props, tp);
    obj->ops->get_props(obj, props);
    if (tp->text_data && *tp->text_data) { g_free(n); n = g_strdup(tp->text_data); }
    prop_list_free(props);
  }
  if (!*n && obj->ops->get_props) {
    GPtrArray *props = g_ptr_array_new();
    StringProperty *sp = (StringProperty *) make_new_prop("text", PROP_TYPE_STRING, 0);
    g_ptr_array_add(props, sp);
    obj->ops->get_props(obj, props);
    if (sp->string_data && *sp->string_data) { g_free(n); n = g_strdup(sp->string_data); }
    prop_list_free(props);
  }
  if (!*n) {
    gchar *m = dia_object_get_meta(obj, "nombre");
    if (m && *m) { g_free(n); n = m; } else g_free(m);
  }
  return n;
}

static void poner_nombre(DiaObject *obj, const char *nombre)
{
  GPtrArray *props = g_ptr_array_new();
  StringProperty *sp = (StringProperty *) make_new_prop("name", PROP_TYPE_STRING, 0);
  sp->string_data = g_strdup(nombre);
  g_ptr_array_add(props, sp);
  obj->ops->set_props(obj, props);
  prop_list_free(props);
}

static void refrescar(Diagram *dia)
{
  diagram_update_extents(dia);
  diagram_add_update_all(dia);
  diagram_flush(dia);
}

static Diagram *buscar_diagrama(const char *base)
{
  GList *l;
  if (!base) {
    DDisplay *d = ddisplay_active();
    return d ? d->diagram : NULL;
  }
  for (l = dia_open_diagrams(); l; l = l->next) {
    Diagram *dia = l->data;
    if (dia->filename) {
      gchar *b = g_path_get_basename(dia->filename);
      gboolean ok = g_ascii_strcasecmp(b, base) == 0;
      g_free(b);
      if (ok) return dia;
    }
  }
  return NULL;
}

/* Copia de undo_clear()+undo_remove_redo_info() de app/undo.c (no estan exportadas):
 * deja la pila de deshacer vacia para que Ctrl+Z no toque objetos que ya no existen. */
static void limpiar_deshacer(Diagram *dia)
{
  UndoStack *s = dia->undo;
  Change *c, *n;
  if (!s || !s->current_change) return;
  c = s->current_change;
  while (c->prev) c = c->prev;
  n = c->next; c->next = NULL;
  s->current_change = c; s->last_change = c; s->last_save = c; s->depth = 0;
  while (n) {
    Change *sig = n->next;
    if (n->free) (n->free)(n);
    g_free(n);
    n = sig;
  }
}

/* ---- ordenes sobre el diagrama ---- */

static void cmd_clase(Diagram *dia, double x, double y, const char *nombre, GString *resp)
{
  DiaObjectType *tipo = object_get_type("UML - Class");
  Point p; Handle *h1, *h2; DiaObject *obj;
  if (!tipo) { g_string_append(resp, "error no existe el tipo UML - Class\n"); return; }
  p.x = x; p.y = y;
  obj = tipo->ops->create(&p, tipo->default_user_data, &h1, &h2);
  poner_nombre(obj, nombre);
  layer_add_object(dia->data->active_layer, obj);
  refrescar(dia);
  g_string_append_printf(resp, "ok clase %s en (%g, %g)\n", nombre, x, y);
}

static void cmd_seleccionar(Diagram *dia, const char *nombre, GString *resp)
{
  GList *l; int n = 0;
  diagram_remove_all_selected(dia, FALSE);
  for (l = dia->data->active_layer->objects; l; l = l->next) {
    DiaObject *obj = l->data;
    gchar *nn = nombre_de(obj);
    if (g_strcmp0(nn, nombre) == 0) { diagram_select(dia, obj); n++; }
    g_free(nn);
  }
  refrescar(dia);
  g_string_append_printf(resp, "ok seleccionados %d con nombre %s\n", n, nombre);
}

static void cmd_cargar(Diagram *dia, const char *ruta, GString *resp)
{
  DiaImportFilter *f = filter_guess_import_filter(ruta);
  Diagram *tmp; DiagramData *td; Layer *capa; GList *viejos, *l; guint i; int n = 0;
  if (!f) { g_string_append_printf(resp, "error no hay filtro para %s\n", ruta); return; }
  if (!g_file_test(ruta, G_FILE_TEST_EXISTS)) { g_string_append_printf(resp, "error no existe %s\n", ruta); return; }
  /* diagrama temporal sin ventana: solo para que el filtro .dia cree los objetos */
  tmp = g_object_new(diagram_get_type(), NULL);
  td = (DiagramData *) tmp;
  if (!f->import_func(ruta, td, f->user_data)) {
    g_object_unref(tmp);
    g_string_append_printf(resp, "error al importar %s\n", ruta);
    return;
  }
  /* 1) quitar lo que habia en la capa activa */
  capa = dia->data->active_layer;
  diagram_remove_all_selected(dia, FALSE);
  viejos = g_list_copy(capa->objects);
  cerrar_dialogo_de(viejos);          /* version 5: si Propiedades edita uno de estos objetos, se cierra antes */
  for (l = viejos; l; l = l->next) layer_remove_object(capa, (DiaObject *) l->data);
  destruir(viejos);
  /* 2) mover los objetos de todas las capas del temporal a la capa activa (menos la de marcas "Tutor") */
  for (i = 0; i < td->layers->len; i++) {
    Layer *tl = g_ptr_array_index(td->layers, i);
    GList *objs;
    if (tl->name && g_strcmp0(tl->name, "Tutor") == 0) continue;
    objs = tl->objects;
    tl->objects = NULL;
    n += g_list_length(objs);
    layer_add_objects(capa, objs);
  }
  g_object_unref(tmp);
  limpiar_deshacer(dia);
  refrescar(dia);
  dia->mollified = FALSE;   /* el paso cargado cuenta como guardado: al cerrar Dia no pregunta por la leccion */
  poner_titulo(dia);        /* version 5: y el titulo de la pestana pierde el «*» (si antes se armo un paso en ella) */
  g_string_append_printf(resp, "ok cargados %d objetos de %s\n", n, ruta);
}

static void cmd_ventanas(GString *resp)
{
  GList *l; DDisplay *act = ddisplay_active();
  for (l = dia_open_diagrams(); l; l = l->next) {
    Diagram *dia = l->data;
    g_string_append_printf(resp, "%s%s\n", (act && act->diagram == dia) ? "* " : "  ",
                           dia->filename ? dia->filename : "(sin nombre)");
  }
  g_string_append(resp, "ok ventanas\n");
}

/* Dispara una accion de menu por su nombre (las de los xml de ui: FileSave, ObjectsProperties...).
 * En la interfaz integrada ddisp->ui_manager es NULL, asi que se busca la accion recorriendo
 * los menus (incluidos los submenus aun no mostrados) y preguntando a cada elemento su accion. */
typedef struct { const char *nombre; GtkAction *accion; } BusqAccion;
static void buscar_accion_en(GtkWidget *w, gpointer data)
{
  BusqAccion *b = data;
  if (b->accion) return;
  if (GTK_IS_MENU_ITEM(w)) {
    GtkWidget *sub;
    GtkAction *a = gtk_activatable_get_related_action(GTK_ACTIVATABLE(w));
    if (a && g_strcmp0(gtk_action_get_name(a), b->nombre) == 0) { b->accion = a; return; }
    sub = gtk_menu_item_get_submenu(GTK_MENU_ITEM(w));
    if (sub) gtk_container_forall(GTK_CONTAINER(sub), buscar_accion_en, data);
  }
  if (GTK_IS_CONTAINER(w)) gtk_container_forall(GTK_CONTAINER(w), buscar_accion_en, data);
}

static GtkAction *buscar_accion(Diagram *dia, const char *nombre)
{
  BusqAccion b = { nombre, NULL };
  DDisplay *ddisp = dia && dia->displays ? dia->displays->data : NULL;
  if (ddisp && ddisp->ui_manager) {
    GList *l;
    for (l = gtk_ui_manager_get_action_groups(ddisp->ui_manager); l && !b.accion; l = l->next)
      b.accion = gtk_action_group_get_action(GTK_ACTION_GROUP(l->data), nombre);
  }
  if (!b.accion) {
    GList *tops = gtk_window_list_toplevels(), *l;
    for (l = tops; l && !b.accion; l = l->next) buscar_accion_en(GTK_WIDGET(l->data), &b);
    g_list_free(tops);
  }
  return b.accion;
}

static void cmd_accion(Diagram *dia, const char *nombre, GString *resp)
{
  BusqAccion b = { nombre, buscar_accion(dia, nombre) };
  if (!b.accion) { g_string_append_printf(resp, "error no existe la accion %s\n", nombre); return; }
  if (!gtk_action_get_sensitive(b.accion)) { g_string_append_printf(resp, "error la accion %s esta desactivada ahora\n", nombre); return; }
  gtk_action_activate(b.accion);
  g_string_append_printf(resp, "ok accion %s\n", nombre);
}

/* ---- widgets: geometria y pulsar (solo lo que esta en pantalla: MAPPED) ---- */

typedef void (*VisitaFn)(GtkWidget *w, gpointer data);
typedef struct { VisitaFn fn; gpointer data; } Visita;

static void visitar(GtkWidget *w, gpointer data);
static void visitar_hijo(GtkWidget *w, gpointer data) { visitar(w, data); }
static void visitar(GtkWidget *w, gpointer data)
{
  Visita *v = data;
  if (!GTK_WIDGET_MAPPED(w)) return;
  v->fn(w, v->data);
  if (GTK_IS_CONTAINER(w)) gtk_container_forall(GTK_CONTAINER(w), visitar_hijo, data);
}

static void visitar_todo(VisitaFn fn, gpointer data)
{
  Visita v = { fn, data };
  GList *tops = gtk_window_list_toplevels(), *l;
  for (l = tops; l; l = l->next)
    if (GTK_WIDGET_MAPPED(GTK_WIDGET(l->data))) visitar(GTK_WIDGET(l->data), &v);
  g_list_free(tops);
}

/* primera etiqueta (GtkLabel) dentro de un widget: sirve para botones normales y de stock */
static void buscar_label(GtkWidget *w, gpointer data)
{
  GtkWidget **out = data;
  if (*out) return;
  if (GTK_IS_LABEL(w)) { *out = w; return; }
  if (GTK_IS_CONTAINER(w)) gtk_container_forall(GTK_CONTAINER(w), buscar_label, data);
}
static const gchar *texto_de(GtkWidget *w)
{
  GtkWidget *lab = NULL;
  if (GTK_IS_LABEL(w)) return gtk_label_get_text(GTK_LABEL(w));
  if (GTK_IS_CONTAINER(w)) gtk_container_forall(GTK_CONTAINER(w), buscar_label, &lab);
  return lab ? gtk_label_get_text(GTK_LABEL(lab)) : NULL;
}

static void rect_de(GtkWidget *w, gint *x, gint *y)
{
  gint ox = 0, oy = 0;
  if (w->window) gdk_window_get_origin(w->window, &ox, &oy);
  if (GTK_WIDGET_NO_WINDOW(w)) { *x = ox + w->allocation.x; *y = oy + w->allocation.y; }
  else { *x = ox; *y = oy; }
}

static void volcar_widget(GtkWidget *w, gpointer data)
{
  GString *resp = data;
  const gchar *texto = NULL, *tipo = "";
  gchar *tip;
  ToolButtonData *td;
  gint x, y;
  if (GTK_IS_WINDOW(w)) {
    const gchar *t = gtk_window_get_title(GTK_WINDOW(w));
    const gchar *rol = gtk_window_get_role(GTK_WINDOW(w));
    rect_de(w, &x, &y);
    /* version 5: el HWND de la ventana y su rol (el overlay del panel se pega a ella y sigue sus movimientos) */
    g_string_append_printf(resp, "ventana x=%d y=%d w=%d h=%d titulo=\"%s\" hwnd=\"%lu\" rol=\"%s\"\n", x, y,
                           w->allocation.width, w->allocation.height, t ? t : "",
                           w->window ? (unsigned long) gdk_win32_drawable_get_handle(w->window) : 0UL, rol ? rol : "");
    return;
  }
  if (GTK_IS_NOTEBOOK(w)) {
    GtkNotebook *nb = GTK_NOTEBOOK(w); gint i, n = gtk_notebook_get_n_pages(nb);
    for (i = 0; i < n; i++) {
      GtkWidget *pag = gtk_notebook_get_nth_page(nb, i);
      GtkWidget *tab = gtk_notebook_get_tab_label(nb, pag);
      const gchar *tt = gtk_notebook_get_tab_label_text(nb, pag);
      if (tab) {
        rect_de(tab, &x, &y);
        g_string_append_printf(resp, "pestana %d x=%d y=%d w=%d h=%d texto=\"%s\"%s\n", i, x, y,
                               tab->allocation.width, tab->allocation.height, tt ? tt : "",
                               gtk_notebook_get_current_page(nb) == i ? " activa" : "");
      }
    }
    return;
  }
  tip = gtk_widget_get_tooltip_text(w);
  if (!tip) {
    GtkTooltipsData *vt = gtk_tooltips_data_get(w);
    if (vt && vt->tip_text) tip = g_strdup(vt->tip_text);
  }
  td = g_object_get_data(G_OBJECT(w), "Dia::ToolButtonData");
  if (td && td->type == CREATE_OBJECT_TOOL && td->extra_data) tipo = (const char *) td->extra_data;
  if (GTK_IS_BUTTON(w) || GTK_IS_MENU_ITEM(w) || GTK_IS_LABEL(w)) texto = texto_de(w);
  if (tip || td || texto || GTK_IS_ENTRY(w) || GTK_IS_COMBO_BOX(w) || GTK_IS_TEXT_VIEW(w) || GTK_IS_TREE_VIEW(w)) {
    rect_de(w, &x, &y);
    if (tip) g_strdelimit(tip, "\n", ' ');
    g_string_append_printf(resp, "widget %s x=%d y=%d w=%d h=%d texto=\"%s\" tipo=\"%s\" tip=\"%s\"%s\n",
                           G_OBJECT_TYPE_NAME(w), x, y, w->allocation.width, w->allocation.height,
                           texto ? texto : "", tipo, tip ? tip : "",
                           GTK_IS_TOGGLE_BUTTON(w) && gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(w)) ? " activo" : "");
  }
  g_free(tip);
}

static void cmd_widgets(GString *resp)
{
  visitar_todo(volcar_widget, resp);
  g_string_append(resp, "ok widgets\n");
}

typedef struct { const char *texto; GtkWidget *boton; GtkNotebook *cuaderno; gint pagina; } Busqueda;
static void buscar_pulsable(GtkWidget *w, gpointer data)
{
  Busqueda *b = data;
  if (b->boton || b->cuaderno) return;
  if (GTK_IS_NOTEBOOK(w)) {
    GtkNotebook *nb = GTK_NOTEBOOK(w); gint i, n = gtk_notebook_get_n_pages(nb);
    for (i = 0; i < n; i++) {
      const gchar *tt = gtk_notebook_get_tab_label_text(nb, gtk_notebook_get_nth_page(nb, i));
      if (tt && g_strcmp0(tt, b->texto) == 0) { b->cuaderno = nb; b->pagina = i; return; }
    }
  }
  if (GTK_IS_BUTTON(w)) {
    const gchar *t = texto_de(w);
    gchar *tip = NULL;
    gboolean ok = (t && g_strcmp0(t, b->texto) == 0);
    if (!ok) {
      tip = gtk_widget_get_tooltip_text(w);
      if (!tip) { GtkTooltipsData *vt = gtk_tooltips_data_get(w); if (vt && vt->tip_text) tip = g_strdup(vt->tip_text); }
      ok = (tip && g_strcmp0(tip, b->texto) == 0);
      g_free(tip);
    }
    if (ok && GTK_WIDGET_SENSITIVE(w)) b->boton = w;
  }
}

static void cmd_pulsar(const char *texto, GString *resp)
{
  Busqueda b = { texto, NULL, NULL, 0 };
  visitar_todo(buscar_pulsable, &b);
  if (b.cuaderno) { gtk_notebook_set_current_page(b.cuaderno, b.pagina); g_string_append_printf(resp, "ok pestana %s\n", texto); }
  else if (b.boton) { gtk_button_clicked(GTK_BUTTON(b.boton)); g_string_append_printf(resp, "ok pulsado %s\n", texto); }
  else g_string_append_printf(resp, "error no hay boton ni pestana visible con texto %s\n", texto);
}

/* ---- marcas del tutor: objetos Standard en una capa propia "Tutor", encima de todo ----
 * Se crean con propiedades (como hace el filtro de importacion SVG de Dia). Nunca se toca
 * data->active_layer: lo que la persona dibuje despues sigue yendo a su capa. La capa no se
 * destruye nunca (borrar_marcas solo la vacia): la lista de capas de la interfaz guarda punteros
 * a las capas y destruir una que esta en la lista podria cerrar Dia. */

#define CAPA_TUTOR "Tutor"

static gboolean es_capa_tutor(Layer *capa)
{
  return capa && capa->name && g_strcmp0(capa->name, CAPA_TUTOR) == 0;
}

static Layer *capa_tutor(Diagram *dia, gboolean crear)
{
  DiagramData *data = dia->data;
  Layer *activa = data->active_layer, *capa = NULL;
  guint i;
  for (i = 0; i < data->layers->len; i++)
    if (es_capa_tutor(g_ptr_array_index(data->layers, i))) { capa = g_ptr_array_index(data->layers, i); break; }
  if (!capa) {
    if (!crear) return NULL;
    capa = new_layer(g_strdup(CAPA_TUTOR), data);
    capa->visible = TRUE;
    capa->connectable = FALSE;           /* que las lineas de la persona no se peguen a las marcas */
    data_add_layer(data, capa);          /* al final del arreglo = encima de las demas */
    tlog("capa Tutor creada");
  } else if (crear) {                    /* p. ej. la que vino en un archivo guardado con marcas */
    if (capa != activa) capa->connectable = FALSE;
    if (data->layers->len > 1 && g_ptr_array_index(data->layers, data->layers->len - 1) != capa) {
      g_ptr_array_remove(data->layers, capa);   /* que quede siempre encima */
      g_ptr_array_add(data->layers, capa);
    }
  }
  data->active_layer = activa;           /* la capa activa NO cambia */
  return capa;
}

static gboolean leer_color(const char *s, Color *c)
{
  static const struct { const char *nombre, *hex; } nombres[] = {
    { "rojo", "#c02828" }, { "verde", "#1e8c46" }, { "amarillo", "#d79100" }, { "azul", "#1e5ac8" },
    { "negro", "#000000" }, { "blanco", "#ffffff" }, { NULL, NULL } };
  unsigned int r, g, b; int i;
  if (!s || !*s) return FALSE;
  for (i = 0; nombres[i].nombre; i++)
    if (g_ascii_strcasecmp(s, nombres[i].nombre) == 0) { s = nombres[i].hex; break; }
  if (s[0] == '#' && strlen(s) == 7 && sscanf(s + 1, "%2x%2x%2x", &r, &g, &b) == 3) {
    c->red = r / 255.0f; c->green = g / 255.0f; c->blue = b / 255.0f;
    return TRUE;
  }
  return FALSE;
}

static Color color_o(const char *s, const char *defecto)
{
  Color c;
  if (!leer_color(s, &c)) leer_color(defecto, &c);
  return c;
}

/* el mismo color, mucho mas claro: fondo de las notas (Dia 0.97 no tiene transparencia) */
static Color suave(Color c)
{
  Color s;
  s.red = c.red + (1.0f - c.red) * 0.86f;
  s.green = c.green + (1.0f - c.green) * 0.86f;
  s.blue = c.blue + (1.0f - c.blue) * 0.86f;
  return s;
}

static DiaObject *crear_objeto(const char *tipo, real x, real y)
{
  DiaObjectType *t = object_get_type((char *) tipo);
  Handle *h1, *h2; Point p;
  if (!t) return NULL;
  p.x = x; p.y = y;
  return t->ops->create(&p, t->default_user_data, &h1, &h2);
}

static PropDescription desc_recuadro[] = {
  { "elem_corner", PROP_TYPE_POINT },
  { "elem_width", PROP_TYPE_REAL },
  { "elem_height", PROP_TYPE_REAL },
  { PROP_STDNAME_LINE_WIDTH, PROP_STDTYPE_LINE_WIDTH },
  { "line_colour", PROP_TYPE_COLOUR },
  { "fill_colour", PROP_TYPE_COLOUR },
  { "show_background", PROP_TYPE_BOOL },
  { "corner_radius", PROP_TYPE_REAL },
  { "line_style", PROP_TYPE_LINESTYLE },
  PROP_DESC_END };

static DiaObject *hacer_recuadro(real x, real y, real w, real h, Color borde, real grosor,
                                 gboolean con_fondo, Color fondo, real radio)
{
  DiaObject *obj = crear_objeto("Standard - Box", x, y);
  GPtrArray *props;
  if (!obj) return NULL;
  props = prop_list_from_descs(desc_recuadro, pdtpp_true);
  ((PointProperty *) g_ptr_array_index(props, 0))->point_data.x = x;
  ((PointProperty *) g_ptr_array_index(props, 0))->point_data.y = y;
  ((RealProperty *) g_ptr_array_index(props, 1))->real_data = w;
  ((RealProperty *) g_ptr_array_index(props, 2))->real_data = h;
  ((LengthProperty *) g_ptr_array_index(props, 3))->length_data = grosor;
  ((ColorProperty *) g_ptr_array_index(props, 4))->color_data = borde;
  ((ColorProperty *) g_ptr_array_index(props, 5))->color_data = fondo;
  ((BoolProperty *) g_ptr_array_index(props, 6))->bool_data = con_fondo;
  ((RealProperty *) g_ptr_array_index(props, 7))->real_data = radio;
  ((LinestyleProperty *) g_ptr_array_index(props, 8))->style = LINESTYLE_SOLID;
  ((LinestyleProperty *) g_ptr_array_index(props, 8))->dash = 1.0;
  obj->ops->set_props(obj, props);
  prop_list_free(props);
  return obj;
}

static PropDescription desc_flecha[] = {
  { "start_point", PROP_TYPE_POINT },
  { "end_point", PROP_TYPE_POINT },
  { PROP_STDNAME_LINE_WIDTH, PROP_STDTYPE_LINE_WIDTH },
  { "line_colour", PROP_TYPE_COLOUR },
  { "start_arrow", PROP_TYPE_ARROW },
  { "end_arrow", PROP_TYPE_ARROW },
  { "line_style", PROP_TYPE_LINESTYLE },
  PROP_DESC_END };

static DiaObject *hacer_flecha(real x1, real y1, real x2, real y2, Color color, real grosor)
{
  DiaObject *obj = crear_objeto("Standard - Line", x1, y1);
  GPtrArray *props; ArrowProperty *ap;
  if (!obj) return NULL;
  props = prop_list_from_descs(desc_flecha, pdtpp_true);
  ((PointProperty *) g_ptr_array_index(props, 0))->point_data.x = x1;
  ((PointProperty *) g_ptr_array_index(props, 0))->point_data.y = y1;
  ((PointProperty *) g_ptr_array_index(props, 1))->point_data.x = x2;
  ((PointProperty *) g_ptr_array_index(props, 1))->point_data.y = y2;
  ((LengthProperty *) g_ptr_array_index(props, 2))->length_data = grosor;
  ((ColorProperty *) g_ptr_array_index(props, 3))->color_data = color;
  ap = g_ptr_array_index(props, 4);
  ap->arrow_data.type = ARROW_NONE; ap->arrow_data.length = 0.5; ap->arrow_data.width = 0.5;
  ap = g_ptr_array_index(props, 5);
  ap->arrow_data.type = ARROW_FILLED_TRIANGLE;
  ap->arrow_data.length = 0.35 + grosor * 2; ap->arrow_data.width = 0.3 + grosor * 2;
  ((LinestyleProperty *) g_ptr_array_index(props, 6))->style = LINESTYLE_SOLID;
  ((LinestyleProperty *) g_ptr_array_index(props, 6))->dash = 1.0;
  obj->ops->set_props(obj, props);
  prop_list_free(props);
  return obj;
}

static PropDescription desc_texto[] = {
  { "text", PROP_TYPE_TEXT },
  PROP_DESC_END };

/* texto en negrita con su esquina superior izquierda en (x, y) */
static DiaObject *hacer_texto(real x, real y, const char *texto, Color color, real alto)
{
  DiaObject *obj = crear_objeto("Standard - Text", x, y);
  GPtrArray *props; TextProperty *tp; Point p;
  if (!obj) return NULL;
  props = prop_list_from_descs(desc_texto, pdtpp_true);
  tp = g_ptr_array_index(props, 0);
  g_free(tp->text_data);
  tp->text_data = g_strdup(texto);
  tp->attr.font = dia_font_new_from_style(DIA_FONT_SANS | DIA_FONT_BOLD, alto);   /* lo libera prop_list_free */
  tp->attr.height = alto;
  tp->attr.position.x = x;
  tp->attr.position.y = y + alto;
  tp->attr.color = color;
  tp->attr.alignment = ALIGN_LEFT;
  obj->ops->set_props(obj, props);
  prop_list_free(props);
  /* ajustar para que el borde de arriba quede justo en y */
  p = obj->position;
  p.y += y - obj->bounding_box.top;
  obj->ops->move(obj, &p);
  return obj;
}

static Layer *poner_marca(Diagram *dia, DiaObject *obj)
{
  Layer *capa = capa_tutor(dia, TRUE);
  layer_add_object(capa, obj);
  return capa;
}

static void cmd_recuadro(Diagram *dia, gchar **argv, gint argc, GString *resp)
{
  real x = g_ascii_strtod(argv[1], NULL), y = g_ascii_strtod(argv[2], NULL);
  real w = g_ascii_strtod(argv[3], NULL), h = g_ascii_strtod(argv[4], NULL);
  Color c = color_o(argc > 5 ? argv[5] : NULL, "rojo");
  real grosor = argc > 6 ? g_ascii_strtod(argv[6], NULL) : 0.1;
  DiaObject *obj;
  if (w <= 0 || h <= 0) { g_string_append(resp, "error recuadro con ancho o alto <= 0\n"); return; }
  obj = hacer_recuadro(x, y, w, h, c, grosor > 0 ? grosor : 0.1, FALSE, c, 0.15);
  if (!obj) { g_string_append(resp, "error no existe el tipo Standard - Box\n"); return; }
  poner_marca(dia, obj);
  refrescar(dia);
  g_string_append_printf(resp, "ok recuadro %.3f %.3f %.3f %.3f\n", x, y, w, h);
}

/* rotulo de una flecha o una nota: texto con caja de fondo suave y borde del color */
static Rectangle poner_rotulo(Diagram *dia, real x, real y, const char *texto, Color c, real alto)
{
  DiaObject *txt = hacer_texto(x, y, texto, c, alto), *caja;
  Rectangle r = { x, y, x, y };
  real pad = 0.2;
  if (!txt) return r;
  r = txt->bounding_box;
  r.left -= pad; r.top -= pad * 0.7; r.right += pad; r.bottom += pad * 0.7;
  caja = hacer_recuadro(r.left, r.top, r.right - r.left, r.bottom - r.top, c, 0.05, TRUE, suave(c), 0.2);
  if (caja) poner_marca(dia, caja);        /* primero la caja, luego el texto: el texto queda encima */
  poner_marca(dia, txt);
  return r;
}

static void cmd_flecha(Diagram *dia, gchar **argv, gint argc, GString *resp)
{
  real x1 = g_ascii_strtod(argv[1], NULL), y1 = g_ascii_strtod(argv[2], NULL);
  real x2 = g_ascii_strtod(argv[3], NULL), y2 = g_ascii_strtod(argv[4], NULL);
  Color c = color_o(argc > 5 ? argv[5] : NULL, "rojo");
  real grosor = argc > 6 ? g_ascii_strtod(argv[6], NULL) : 0.08;
  DiaObject *obj = hacer_flecha(x1, y1, x2, y2, c, grosor > 0 ? grosor : 0.08);
  if (!obj) { g_string_append(resp, "error no existe el tipo Standard - Line\n"); return; }
  poner_marca(dia, obj);
  if (argc > 7 && *argv[7]) poner_rotulo(dia, (x1 + x2) / 2 + 0.2, (y1 + y2) / 2 - 1.1, argv[7], c, 0.6);
  refrescar(dia);
  g_string_append_printf(resp, "ok flecha %.3f %.3f %.3f %.3f\n", x1, y1, x2, y2);
}

static void cmd_nota(Diagram *dia, gchar **argv, gint argc, GString *resp)
{
  real x = g_ascii_strtod(argv[1], NULL), y = g_ascii_strtod(argv[2], NULL);
  Color c = color_o(argc > 4 ? argv[4] : NULL, "rojo");
  Rectangle r = poner_rotulo(dia, x, y, argv[3], c, 0.7);
  if (argc > 6) {   /* flecha desde el borde de la nota hasta (hx, hy) */
    real hx = g_ascii_strtod(argv[5], NULL), hy = g_ascii_strtod(argv[6], NULL), sx, sy;
    real cy = (r.top + r.bottom) / 2, cx = (r.left + r.right) / 2;
    DiaObject *fl;
    if (hx < r.left) { sx = r.left; sy = cy; }
    else if (hx > r.right) { sx = r.right; sy = cy; }
    else { sx = cx; sy = hy < r.top ? r.top : r.bottom; }
    fl = hacer_flecha(sx, sy, hx, hy, c, 0.06);
    if (fl) poner_marca(dia, fl);
  }
  refrescar(dia);
  g_string_append_printf(resp, "ok nota %.3f %.3f %.3f %.3f\n", r.left, r.top, r.right - r.left, r.bottom - r.top);
}

static void cmd_borrar_marcas(Diagram *dia, GString *resp)
{
  Layer *capa = capa_tutor(dia, FALSE);
  GList *viejos, *l; int n = 0;
  if (capa && capa->objects) {
    if (dia->data->active_layer == capa) diagram_remove_all_selected(dia, FALSE);
    viejos = g_list_copy(capa->objects);
    for (l = viejos; l; l = l->next) { layer_remove_object(capa, (DiaObject *) l->data); n++; }
    destroy_object_list(viejos);
    refrescar(dia);
  }
  g_string_append_printf(resp, "ok borradas %d marcas\n", n);
}

static void cmd_capas(Diagram *dia, GString *resp)
{
  guint i;
  for (i = 0; i < dia->data->layers->len; i++) {
    Layer *capa = g_ptr_array_index(dia->data->layers, i);
    g_string_append_printf(resp, "capa\t%s\t%d%s\n", capa->name ? capa->name : "",
                           g_list_length(capa->objects), capa == dia->data->active_layer ? "\tactiva" : "");
  }
  g_string_append(resp, "ok capas\n");
}

/* ---- cajas: geometria actual de los objetos (aunque no se haya guardado) ---- */

static real prop_real(DiaObject *obj, const char *nombre, const char *tipo, real defecto)
{
  Property *p = object_prop_by_name_type(obj, nombre, tipo);
  real v = defecto;
  if (p) { v = ((RealProperty *) p)->real_data; p->ops->free(p); }
  return v;
}

static gboolean prop_bool(DiaObject *obj, const char *nombre, gboolean defecto)
{
  Property *p = object_prop_by_name_type(obj, nombre, PROP_TYPE_BOOL);
  gboolean v = defecto;
  if (p) { v = ((BoolProperty *) p)->bool_data; p->ops->free(p); }
  return v;
}

static gchar *limpio(const char *s)
{
  gchar *c = g_strdup(s ? s : "");
  g_strdelimit(c, "\t\r\n", ' ');
  return c;
}

/* nombres de los registros de una propiedad lista (attributes / operations de una clase UML) */
static GPtrArray *nombres_de_lista(DiaObject *obj, const char *lista)
{
  GPtrArray *res = g_ptr_array_new();
  Property *p = object_prop_by_name_type(obj, lista, PROP_TYPE_DARRAY);
  guint i, j;
  if (!p) return res;
  for (i = 0; i < ((ArrayProperty *) p)->records->len; i++) {
    GPtrArray *reg = g_ptr_array_index(((ArrayProperty *) p)->records, i);
    const gchar *n = "";
    for (j = 0; j < reg->len; j++) {
      Property *q = g_ptr_array_index(reg, j);
      if (q->name && strcmp(q->name, "name") == 0) { n = ((StringProperty *) q)->string_data; break; }
    }
    g_ptr_array_add(res, limpio(n));
  }
  p->ops->free(p);
  return res;
}

static void volcar_caja(DiaObject *obj, const char *nombre, GString *resp)
{
  Property *pc = object_prop_by_name_type(obj, "elem_corner", PROP_TYPE_POINT);
  real x, y, w, h;
  gchar *n = limpio(nombre);
  if (pc) {
    x = ((PointProperty *) pc)->point_data.x; y = ((PointProperty *) pc)->point_data.y;
    pc->ops->free(pc);
    w = prop_real(obj, "elem_width", PROP_TYPE_REAL, 0);
    h = prop_real(obj, "elem_height", PROP_TYPE_REAL, 0);
  } else {
    x = obj->bounding_box.left; y = obj->bounding_box.top;
    w = obj->bounding_box.right - x; h = obj->bounding_box.bottom - y;
  }
  g_string_append_printf(resp, "caja\t%s\t%s\t%.3f\t%.3f\t%.3f\t%.3f\n", n, obj->type->name, x, y, w, h);
  /* filas de una clase UML: misma cuenta que umlclass_calculate_data (objects/UML/class.c) sin
   * comentarios visibles ni operaciones partidas; la altura del recuadro del nombre sale de restar. */
  if (pc && g_strcmp0(obj->type->name, "UML - Class") == 0) {
    real fh = prop_real(obj, "normal_font_height", PROP_TYPE_REAL, 0.8);
    gboolean ver_at = prop_bool(obj, "visible_attributes", TRUE), ver_op = prop_bool(obj, "visible_operations", TRUE);
    gboolean sup_at = prop_bool(obj, "suppress_attributes", FALSE), sup_op = prop_bool(obj, "suppress_operations", FALSE);
    GPtrArray *ats = nombres_de_lista(obj, "attributes"), *ops = nombres_de_lista(obj, "operations");
    real caja_at = 0, caja_op = 0, nombre_h, y0;
    guint i;
    if (ver_at) { caja_at = 0.2 + fh * ats->len; if (caja_at < 0.4 || sup_at) caja_at = 0.4; }
    if (ver_op) { caja_op = 0.2 + fh * ops->len; if (caja_op < 0.4 || sup_op) caja_op = 0.4; }
    nombre_h = h - caja_at - caja_op;
    g_string_append_printf(resp, "fila\t%s\t\tnombre\t%.3f\t%.3f\t%.3f\t%.3f\n", n, x, y, w, nombre_h);
    if (ver_at && !sup_at) {
      y0 = y + nombre_h + 0.1;
      for (i = 0; i < ats->len; i++)
        g_string_append_printf(resp, "fila\t%s\t%s\tatributo\t%.3f\t%.3f\t%.3f\t%.3f\n", n,
                               (gchar *) g_ptr_array_index(ats, i), x, y0 + i * fh, w, fh);
    }
    if (ver_op && !sup_op) {
      y0 = y + nombre_h + caja_at + 0.1;
      for (i = 0; i < ops->len; i++)
        g_string_append_printf(resp, "fila\t%s\t%s\tmetodo\t%.3f\t%.3f\t%.3f\t%.3f\n", n,
                               (gchar *) g_ptr_array_index(ops, i), x, y0 + i * fh, w, fh);
    }
    for (i = 0; i < ats->len; i++) g_free(g_ptr_array_index(ats, i));
    for (i = 0; i < ops->len; i++) g_free(g_ptr_array_index(ops, i));
    g_ptr_array_free(ats, TRUE); g_ptr_array_free(ops, TRUE);
  }
  g_free(n);
}

/* version 4: de cada objeto (con o sin nombre) sale tambien una linea "objeto ID TIPO X Y W H NOMBRE" con su
 * caja exterior (bounding box) y su id en el orden en que Dia lo guarda (el mismo "On" de la orden copia) */
static void volcar_objetos(GList *objs, int *k, GString *resp, gboolean tutor)
{
  GList *l;
  for (l = objs; l; l = l->next) {
    DiaObject *o = l->data;
    if (IS_GROUP(o) && group_objects(o)) { volcar_objetos(group_objects(o), k, resp, tutor); continue; }
    if (!tutor) {
      gchar *nn = nombre_visible(o), *c = limpio(nn);
      Rectangle *b = &o->bounding_box;
      g_string_append_printf(resp, "objeto\tO%d\t%s\t%.3f\t%.3f\t%.3f\t%.3f\t%s\n", *k, o->type->name,
                             b->left, b->top, b->right - b->left, b->bottom - b->top, c);
      g_free(nn); g_free(c);
    }
    (*k)++;
  }
}

static void cmd_cajas(Diagram *dia, const char *solo, GString *resp)
{
  guint i; GList *l; int n = 0, k = 0;
  for (i = 0; i < dia->data->layers->len; i++) {
    Layer *capa = g_ptr_array_index(dia->data->layers, i);
    if (es_capa_tutor(capa)) continue;
    for (l = capa->objects; l; l = l->next) {
      DiaObject *obj = l->data;
      gchar *nn = nombre_visible(obj);
      if (*nn && (!solo || g_strcmp0(nn, solo) == 0)) { volcar_caja(obj, nn, resp); n++; }
      g_free(nn);
    }
  }
  if (!solo)
    for (i = 0; i < dia->data->layers->len; i++) {
      Layer *capa = g_ptr_array_index(dia->data->layers, i);
      volcar_objetos(capa->objects, &k, resp, es_capa_tutor(capa));
    }
  g_string_append_printf(resp, "ok cajas %d\n", n);
}

/* ==== Cambios del tutor que SI cuentan como cambio del diagrama ====
 * Pasan por la pila de Deshacer de Dia (con cambios propios copiados de app/undo.c, que no exporta
 * nada): el diagrama queda modificado ("modificado" dice "si", Dia pregunta al cerrar) y Ctrl+Z
 * los deshace de una vez (la orden "transaccion" cierra el grupo). Los objetos que crea el tutor
 * llevan meta "tutor" = etiqueta (se guarda en el archivo). Referencias a objetos (REF):
 *   tag:ETIQUETA   el objeto con esa etiqueta del tutor
 *   clase:NOMBRE   la clase UML con ese nombre
 *   id:On          el objeto n-esimo en el orden en que Dia lo guarda (el "id" de la orden "copia")
 * Nunca se toca la capa "Tutor" (marcas). */

#define META_TUTOR "tutor"

/* el puntero de la funcion "punto de transaccion" de undo.c es estatico: el fondo de la pila siempre es uno */
static UndoApplyFunc funcion_tp(UndoStack *s)
{
  Change *c = s->current_change;
  while (c && c->prev) c = c->prev;
  return c ? c->apply : NULL;
}

static void apilar(Diagram *dia, Change *c)      /* = undo_push_change + undo_remove_redo_info */
{
  UndoStack *s = dia->undo;
  if (s->current_change != s->last_change) {
    Change *r = s->current_change->next, *n;
    s->current_change->next = NULL;
    s->last_change = s->current_change;
    while (r) { n = r->next; if (r->free) (r->free)(r); g_free(r); r = n; }
  }
  c->prev = s->last_change; c->next = NULL;
  s->last_change->next = c; s->last_change = c; s->current_change = c;
}

static void poner_titulo(Diagram *dia)            /* = diagram_modified (no exportada) */
{
  const gchar *fn = dia->filename ? dia->filename : "";
  gchar *nombre = g_path_get_basename(fn), *dir = g_path_get_dirname(fn);
  gchar *t = g_strdup_printf("%s%s (%s)", diagram_is_modified(dia) ? "*" : "", nombre, dir);
  GSList *l;
  for (l = dia->displays; l; l = l->next) ddisplay_set_title((DDisplay *) l->data, t);
  if (diagram_is_modified(dia)) { dia->autosaved = FALSE; dia->is_default = FALSE; }
  g_free(nombre); g_free(dir); g_free(t);
  /* Deshacer / Rehacer del menu (ddisplay_do_update_menu_sensitivity no se exporta): solo si es la pestana activa */
  if (ddisplay_active() && ddisplay_active()->diagram == dia) {
    GtkAction *a = buscar_accion(dia, "EditUndo"), *b = buscar_accion(dia, "EditRedo");
    if (a) gtk_action_set_sensitive(a, dia->undo->current_change->prev != NULL);
    if (b) gtk_action_set_sensitive(b, dia->undo->current_change->next != NULL);
  }
}

/* destruir objetos que ya no estan en ninguna capa: primero se sueltan TODOS sus extremos y luego se destruyen
 * (si se destruye una clase antes que la linea pegada a ella, soltar la linea despues tocaria memoria liberada) */
static void destruir(GList *objs)
{
  GList *l; int h;
  for (l = objs; l; l = l->next) {
    DiaObject *o = l->data;
    for (h = 0; h < o->num_handles; h++) if (o->handles[h]->connected_to) object_unconnect(o, o->handles[h]);
  }
  destroy_object_list(objs);
}

/* -- cambio: insertar objetos -- */
typedef struct { Change c; Layer *capa; GList *objs; int aplicado; } CInsertar;
static void ins_apply(Change *ch, Diagram *dia)
{ CInsertar *c = (CInsertar *) ch; c->aplicado = 1; layer_add_objects(c->capa, g_list_copy(c->objs)); diagram_add_update_all(dia); }
static void ins_revert(Change *ch, Diagram *dia)
{ CInsertar *c = (CInsertar *) ch; c->aplicado = 0; cerrar_dialogo_de(c->objs); diagram_remove_all_selected(dia, FALSE); layer_remove_objects(c->capa, c->objs); diagram_add_update_all(dia); }
static void ins_free(Change *ch)
{ CInsertar *c = (CInsertar *) ch; if (!c->aplicado) destruir(c->objs); else g_list_free(c->objs); }

/* -- cambio: quitar objetos (de una capa) -- */
typedef struct { Change c; Layer *capa; GList *objs; GList *originales; int aplicado; } CQuitar;
static void qui_apply(Change *ch, Diagram *dia)
{ CQuitar *c = (CQuitar *) ch; c->aplicado = 1; cerrar_dialogo_de(c->objs); diagram_remove_all_selected(dia, FALSE); layer_remove_objects(c->capa, c->objs); diagram_add_update_all(dia); }
static void qui_revert(Change *ch, Diagram *dia)
{ CQuitar *c = (CQuitar *) ch; c->aplicado = 0; layer_set_object_list(c->capa, g_list_copy(c->originales)); diagram_add_update_all(dia); }
static void qui_free(Change *ch)
{ CQuitar *c = (CQuitar *) ch; if (c->aplicado) destruir(c->objs); else g_list_free(c->objs); g_list_free(c->originales); }

/* -- cambio: conectar o desconectar un extremo. El punto de conexion se guarda por indice (y no por
 *    puntero) porque al cambiar los atributos de una clase sus puntos de las filas se recrean. -- */
typedef struct { Change c; DiaObject *obj; int handle; DiaObject *destino; int punto; Point antes; int conectar; } CConexion;
static void con_hacer(CConexion *c, Diagram *dia, int conectar)
{
  Handle *h = c->obj->handles[c->handle];
  if (conectar) {
    ConnectionPoint *cp;
    if (c->punto < 0 || c->punto >= c->destino->num_connections) return;
    cp = c->destino->connections[c->punto];
    object_connect(c->obj, h, cp);
    c->obj->ops->move_handle(c->obj, h, &cp->pos, cp, HANDLE_MOVE_CONNECTED, 0);
  } else {
    object_unconnect(c->obj, h);
    c->obj->ops->move_handle(c->obj, h, &c->antes, NULL, HANDLE_MOVE_USER_FINAL, 0);
  }
  diagram_add_update_all(dia);
}
static void con_apply(Change *ch, Diagram *dia) { CConexion *c = (CConexion *) ch; con_hacer(c, dia, c->conectar); }
static void con_revert(Change *ch, Diagram *dia) { CConexion *c = (CConexion *) ch; con_hacer(c, dia, !c->conectar); }

static int indice_punto(DiaObject *o, ConnectionPoint *cp)
{
  int i;
  for (i = 0; i < o->num_connections; i++) if (o->connections[i] == cp) return i;
  return -1;
}

/* conectar (conectar=1) o soltar (conectar=0) el extremo `handle` de obj, apilado y aplicado */
static void conexion(Diagram *dia, DiaObject *obj, int handle, DiaObject *destino, int punto, int conectar)
{
  CConexion *c = g_new0(CConexion, 1);
  c->c.apply = con_apply; c->c.revert = con_revert; c->c.free = NULL;
  c->obj = obj; c->handle = handle; c->destino = destino; c->punto = punto; c->conectar = conectar;
  c->antes = obj->handles[handle]->pos;
  apilar(dia, (Change *) c);
  con_hacer(c, dia, conectar);
}

/* -- cambio: propiedades de un objeto (ObjectChange de object_apply_props, ya aplicado) -- */
typedef struct { Change c; DiaObject *obj; ObjectChange *oc; } CObjeto;
static void obj_apply(Change *ch, Diagram *dia)
{ CObjeto *c = (CObjeto *) ch; c->oc->apply(c->oc, c->obj); diagram_update_connections_object(dia, c->obj, TRUE); diagram_add_update_all(dia); }
static void obj_revert(Change *ch, Diagram *dia)
{ CObjeto *c = (CObjeto *) ch; c->oc->revert(c->oc, c->obj); diagram_update_connections_object(dia, c->obj, TRUE); diagram_add_update_all(dia); }
static void obj_free(Change *ch)
{ CObjeto *c = (CObjeto *) ch; if (c->oc->free) c->oc->free(c->oc); g_free(c->oc); }


/* -- buscar objetos -- */
static Layer *capa_usuario(Diagram *dia)
{
  DiagramData *d = dia->data; gint i;
  if (!es_capa_tutor(d->active_layer)) return d->active_layer;
  for (i = (gint) d->layers->len - 1; i >= 0; i--)
    if (!es_capa_tutor(g_ptr_array_index(d->layers, i))) return g_ptr_array_index(d->layers, i);
  return d->active_layer;
}

static gboolean tiene_tag(DiaObject *o, const char *tag)
{
  gchar *m = dia_object_get_meta(o, META_TUTOR);
  gboolean ok = m && g_strcmp0(m, tag) == 0;
  g_free(m);
  return ok;
}

/* numeracion de write_objects (app/load_save.c): todas las capas, los grupos por dentro */
static DiaObject *numerar(GList *objs, int *n, int buscado, gboolean *en_grupo, gboolean dentro)
{
  GList *l;
  for (l = objs; l; l = l->next) {
    DiaObject *o = l->data, *r;
    if (IS_GROUP(o) && group_objects(o)) {
      if ((r = numerar(group_objects(o), n, buscado, en_grupo, TRUE))) return r;
    } else {
      if (*n == buscado) { *en_grupo = dentro; return o; }
      (*n)++;
    }
  }
  return NULL;
}

/* el objeto de una REF, fuera de la capa "Tutor" y no dentro de un grupo; *capa = su capa */
static DiaObject *por_ref(Diagram *dia, const char *ref, Layer **capa)
{
  DiagramData *d = dia->data; guint i; GList *l;
  if (g_str_has_prefix(ref, "id:O")) {
    int n = 0, buscado = atoi(ref + 4); gboolean en_grupo = FALSE;
    for (i = 0; i < d->layers->len; i++) {
      Layer *c = g_ptr_array_index(d->layers, i);
      DiaObject *o = numerar(c->objects, &n, buscado, &en_grupo, FALSE);
      if (o) {
        if (en_grupo || es_capa_tutor(c)) return NULL;
        if (capa) *capa = c;
        return o;
      }
    }
    return NULL;
  }
  for (i = 0; i < d->layers->len; i++) {
    Layer *c = g_ptr_array_index(d->layers, i);
    if (es_capa_tutor(c)) continue;
    for (l = c->objects; l; l = l->next) {
      DiaObject *o = l->data; gboolean ok = FALSE;
      if (g_str_has_prefix(ref, "tag:")) ok = tiene_tag(o, ref + 4);
      else if (g_str_has_prefix(ref, "clase:") && g_strcmp0(o->type->name, "UML - Class") == 0) {
        gchar *nn = nombre_de(o); ok = g_strcmp0(nn, ref + 6) == 0; g_free(nn);
      }
      else if (g_str_has_prefix(ref, "nombre:")) {
        gchar *nn = nombre_visible(o); ok = g_strcmp0(nn, ref + 7) == 0; g_free(nn);
      }
      if (ok) { if (capa) *capa = c; return o; }
    }
  }
  return NULL;
}

/* punto de conexion "automatico" de `dest` mirando hacia `otro`: en una clase, el centro de arriba o
 * de abajo si estan una encima de otra, o el lado (a la altura del nombre) si estan una al lado de otra;
 * si ya esta ocupado se prueban las esquinas (salvo `compartir`: herencias que confluyen). Con `vertical`
 * (herencia, realizacion) se prefiere arriba/abajo siempre que una clase este encima de la otra */
static int punto_auto(DiaObject *dest, DiaObject *otro, gboolean compartir, gboolean vertical)
{
  Rectangle *a = &dest->bounding_box, *b = &otro->bounding_box;
  real dx = (b->left + b->right - a->left - a->right) / 2, dy = (b->top + b->bottom - a->top - a->bottom) / 2;
  int i, mejor = 0; real dmin = 1e30;
  if (g_strcmp0(dest->type->name, "UML - Class") == 0 && dest->num_connections >= 8) {
    static const int abajo[] = { 6, 5, 7 }, arriba[] = { 1, 0, 2 }, der[] = { 4, 7, 2 }, izq[] = { 3, 5, 0 };
    gboolean separadas_v = b->top >= a->bottom || b->bottom <= a->top;
    gboolean separadas_h = b->left >= a->right || b->right <= a->left;
    const int *c = (separadas_v && (vertical || !separadas_h || fabs(dy) * 1.3 >= fabs(dx))) ? (dy > 0 ? abajo : arriba) : (dx > 0 ? der : izq);
    if (compartir) return c[0];
    for (i = 0; i < 3; i++) if (!dest->connections[c[i]]->connected) return c[i];
    return c[0];
  }
  for (i = 0; i < dest->num_connections; i++) {   /* otro objeto: el punto mas cercano al centro del otro */
    Point *p = &dest->connections[i]->pos;
    real ex = p->x - (b->left + b->right) / 2, ey = p->y - (b->top + b->bottom) / 2, dd = ex * ex + ey * ey;
    if (dd < dmin) { dmin = dd; mejor = i; }
  }
  return mejor;
}

/* importa un .dia a un diagrama temporal sin ventana (como "cargar") */
static Diagram *importar(const char *ruta, GString *resp)
{
  DiaImportFilter *f = filter_guess_import_filter(ruta);
  Diagram *tmp;
  if (!f || !g_file_test(ruta, G_FILE_TEST_EXISTS)) { g_string_append_printf(resp, "error no existe o no se puede leer %s\n", ruta); return NULL; }
  tmp = g_object_new(diagram_get_type(), NULL);
  if (!f->import_func(ruta, (DiagramData *) tmp, f->user_data)) {
    g_object_unref(tmp); g_string_append_printf(resp, "error al importar %s\n", ruta); return NULL;
  }
  return tmp;
}

/* "conecta_inicio" / "conecta_fin" = "REF" o "REF#PUNTO" (PUNTO = numero o auto) */
typedef struct { DiaObject *obj; int handle; DiaObject *dest; int punto; gboolean cerca; real cx, cy; } Pend;

static DiaObject *ref_en(Diagram *dia, GList *nuevos, const char *ref)
{
  GList *l;
  if (g_str_has_prefix(ref, "tag:"))
    for (l = nuevos; l; l = l->next) if (tiene_tag(l->data, ref + 4)) return l->data;
  if (g_str_has_prefix(ref, "clase:"))
    for (l = nuevos; l; l = l->next)
      if (g_strcmp0(((DiaObject *) l->data)->type->name, "UML - Class") == 0) {
        gchar *nn = nombre_de(l->data); gboolean ok = g_strcmp0(nn, ref + 6) == 0; g_free(nn);
        if (ok) return l->data;
      }
  if (g_str_has_prefix(ref, "nombre:"))
    for (l = nuevos; l; l = l->next) {
      gchar *nn = nombre_visible(l->data); gboolean ok = g_strcmp0(nn, ref + 7) == 0; g_free(nn);
      if (ok) return l->data;
    }
  return por_ref(dia, ref, NULL);
}

/* "X,Y" -> punto (con g_ascii_strtod: Dia pone el idioma del sistema y en espanol sscanf espera coma decimal) */
static gboolean leer_punto(const char *s, real *x, real *y)
{
  char *fin;
  *x = g_ascii_strtod(s, &fin);
  if (fin == s || *fin != ',') return FALSE;
  s = fin + 1;
  *y = g_ascii_strtod(s, &fin);
  return fin != s && *fin == 0;
}

/* el punto de conexion de `o` mas cercano a (x, y) (REF@X,Y: p. ej. el de la linea de vida a la altura de un mensaje) */
static int punto_cercano(DiaObject *o, real x, real y)
{
  int i, mejor = 0; real dmin = 1e30;
  for (i = 0; i < o->num_connections; i++) {
    real dx = o->connections[i]->pos.x - x, dy = o->connections[i]->pos.y - y, d = dx * dx + dy * dy;
    if (d < dmin) { dmin = d; mejor = i; }
  }
  return mejor;
}

static gboolean leer_pendiente(Diagram *dia, GList *nuevos, DiaObject *o, const char *clave, int handle, GArray *pend, GString *resp)
{
  gchar *v = dia_object_get_meta(o, clave), *almohadilla, *arroba;
  Pend p;
  if (!v) return TRUE;
  if (o->num_handles < 2) { g_string_append_printf(resp, "error %s: el objeto no se puede conectar\n", v); g_free(v); return FALSE; }
  p.punto = -1; p.cerca = FALSE; p.cx = p.cy = 0;
  arroba = strrchr(v, '@');                     /* REF@X,Y: el punto mas cercano a (X, Y) */
  if (arroba && leer_punto(arroba + 1, &p.cx, &p.cy)) { *arroba = 0; p.cerca = TRUE; }
  almohadilla = p.cerca ? NULL : strrchr(v, '#');
  if (almohadilla && (g_ascii_isdigit(almohadilla[1]) || g_strcmp0(almohadilla + 1, "auto") == 0)) {
    *almohadilla = 0;
    if (g_ascii_isdigit(almohadilla[1])) p.punto = atoi(almohadilla + 1);
  }
  p.obj = o; p.handle = handle; p.dest = ref_en(dia, nuevos, v);
  if (!p.dest) { g_string_append_printf(resp, "error no encuentro %s para conectar\n", v); g_free(v); return FALSE; }
  if (p.punto >= p.dest->num_connections) { g_string_append_printf(resp, "error %s no tiene el punto %d\n", v, p.punto); g_free(v); return FALSE; }
  g_array_append_val(pend, p);
  g_free(v);
  return TRUE;
}

/* anadir RUTA: anade (sin borrar nada) los objetos del archivo a la capa de la persona y los conecta.
 * Responde "nuevo<TAB>ETIQUETA<TAB>TIPO" por objeto. Si una conexion no se puede resolver, no anade nada. */
static void cmd_anadir(Diagram *dia, const char *ruta, GString *resp)
{
  Diagram *tmp = importar(ruta, resp);
  DiagramData *td; GList *nuevos = NULL, *l; GArray *pend; guint i; gboolean ok = TRUE;
  CInsertar *c;
  if (!tmp) return;
  td = (DiagramData *) tmp;
  for (i = 0; i < td->layers->len; i++) {
    Layer *tl = g_ptr_array_index(td->layers, i);
    if (es_capa_tutor(tl)) continue;
    nuevos = g_list_concat(nuevos, tl->objects);
    tl->objects = NULL;
  }
  pend = g_array_new(FALSE, FALSE, sizeof(Pend));
  for (l = nuevos; l && ok; l = l->next) {
    ok = leer_pendiente(dia, nuevos, l->data, "conecta_inicio", 0, pend, resp)
      && leer_pendiente(dia, nuevos, l->data, "conecta_fin", 1, pend, resp);
  }
  if (!ok || !nuevos) {
    if (!nuevos && ok) g_string_append(resp, "error el archivo no trae objetos\n");
    destruir(nuevos); g_array_free(pend, TRUE); g_object_unref(tmp);
    return;
  }
  /* 1) insertar (apilado en Deshacer) */
  c = g_new0(CInsertar, 1);
  c->c.apply = ins_apply; c->c.revert = ins_revert; c->c.free = ins_free;
  c->capa = capa_usuario(dia); c->objs = nuevos;
  apilar(dia, (Change *) c);
  ins_apply((Change *) c, dia);
  /* 2) conectar los extremos (cada uno, un cambio en Deshacer); el punto automatico mira al otro extremo */
  for (i = 0; i < pend->len; i++) {
    Pend *p = &g_array_index(pend, Pend, i);
    dia_object_set_meta(p->obj, p->handle ? "conecta_fin" : "conecta_inicio", NULL);
    if (p->cerca) p->punto = punto_cercano(p->dest, p->cx, p->cy);
    else if (p->punto < 0) {
      DiaObject *otro = NULL; guint k;
      for (k = 0; k < pend->len; k++) {
        Pend *q = &g_array_index(pend, Pend, k);
        if (q->obj == p->obj && q->handle != p->handle) otro = q->dest;
      }
      if (otro && otro != p->dest) {
        gboolean compartir = g_strcmp0(p->obj->type->name, "UML - Generalization") == 0 || g_strcmp0(p->obj->type->name, "UML - Realizes") == 0;
        p->punto = punto_auto(p->dest, otro, compartir && p->handle == 0, compartir);
      } else p->punto = 0;
    }
    conexion(dia, p->obj, p->handle, p->dest, p->punto, 1);
  }
  for (i = 0; i < pend->len; i++) diagram_update_connections_object(dia, g_array_index(pend, Pend, i).dest, TRUE);
  for (l = nuevos; l; l = l->next) {
    DiaObject *o = l->data; gchar *t = dia_object_get_meta(o, META_TUTOR);
    g_string_append_printf(resp, "nuevo\t%s\t%s\n", t ? t : "", o->type->name);
    g_free(t);
  }
  g_array_free(pend, TRUE);
  g_object_unref(tmp);
  refrescar(dia); poner_titulo(dia);
  g_string_append_printf(resp, "ok anadidos %d\n", g_list_length(nuevos));
}

/* soltar (con Deshacer) todo lo que conecta a `objs` con objetos que no estan en `objs` */
static int soltar_externas(Diagram *dia, GList *objs)
{
  DiagramData *d = dia->data; guint i; GList *l, *m; int n = 0, h, k;
  for (l = objs; l; l = l->next) {
    DiaObject *o = l->data;
    for (h = 0; h < o->num_handles; h++) {            /* sus extremos pegados a otros */
      ConnectionPoint *cp = o->handles[h]->connected_to;
      if (cp && !g_list_find(objs, cp->object)) { conexion(dia, o, h, cp->object, indice_punto(cp->object, cp), 0); n++; }
    }
  }
  for (i = 0; i < d->layers->len; i++) {               /* los de otros pegados a ellos */
    Layer *c = g_ptr_array_index(d->layers, i);
    for (m = c->objects; m; m = m->next) {
      DiaObject *x = m->data;
      if (g_list_find(objs, x)) continue;
      for (k = 0; k < x->num_handles; k++) {
        ConnectionPoint *cp = x->handles[k]->connected_to;
        if (cp && g_list_find(objs, cp->object)) { conexion(dia, x, k, cp->object, indice_punto(cp->object, cp), 0); n++; }
      }
    }
  }
  return n;
}

/* quitar REF [REF...]: quita esos objetos (con Deshacer). Lo que estaba pegado a ellos queda suelto. */
static void cmd_quitar(Diagram *dia, gchar **argv, gint argc, GString *resp)
{
  GList *objs = NULL, *capas = NULL, *l; int i, sueltos;
  for (i = 1; i < argc; i++) {
    Layer *capa = NULL; DiaObject *o = por_ref(dia, argv[i], &capa);
    if (!o) { g_string_append_printf(resp, "falta\t%s\n", argv[i]); continue; }
    if (!g_list_find(objs, o)) { objs = g_list_append(objs, o); if (!g_list_find(capas, capa)) capas = g_list_append(capas, capa); }
  }
  if (!objs) { g_list_free(capas); g_string_append(resp, "ok quitados 0\n"); return; }
  sueltos = soltar_externas(dia, objs);
  for (l = capas; l; l = l->next) {                   /* un cambio por capa */
    Layer *capa = l->data; GList *deesta = NULL, *m;
    CQuitar *c;
    for (m = objs; m; m = m->next) if (((DiaObject *) m->data)->parent_layer == capa) deesta = g_list_append(deesta, m->data);
    c = g_new0(CQuitar, 1);
    c->c.apply = qui_apply; c->c.revert = qui_revert; c->c.free = qui_free;
    c->capa = capa; c->objs = deesta; c->originales = g_list_copy(capa->objects);
    apilar(dia, (Change *) c);
    qui_apply((Change *) c, dia);
  }
  g_string_append_printf(resp, "ok quitados %d sueltos %d\n", g_list_length(objs), sueltos);
  g_list_free(objs); g_list_free(capas);
  refrescar(dia); poner_titulo(dia);
}

/* que propiedades se copian al "reemplazar": las que se guardan, menos la posicion, la caja y la meta */
static gboolean copiable(const PropDescription *pd)
{
  static const char *fuera[] = { "obj_pos", "obj_bb", "elem_corner", "elem_width", "elem_height", "meta", NULL };
  int i;
  if (pd->flags & PROP_FLAG_DONT_SAVE) return FALSE;
  for (i = 0; fuera[i]; i++) if (g_strcmp0(pd->name, fuera[i]) == 0) return FALSE;
  return TRUE;
}

/* "reemplazar ... geometria" (version 4): tambien la esquina y el tamano (mover o cambiar el tamano con Deshacer) */
static gboolean copiable_geo(const PropDescription *pd)
{
  static const char *fuera[] = { "obj_pos", "obj_bb", "meta", NULL };
  int i;
  if (pd->flags & PROP_FLAG_DONT_SAVE) return FALSE;
  for (i = 0; fuera[i]; i++) if (g_strcmp0(pd->name, fuera[i]) == 0) return FALSE;
  return TRUE;
}

/* reemplazar REF RUTA: el objeto toma las propiedades (nombre, atributos, metodos...) del primer objeto del
 * mismo tipo que haya en RUTA, sin moverse y sin soltar sus relaciones (con Deshacer). Las que estaban
 * pegadas a una fila (atributo o metodo) pasan a un punto fijo de la caja, porque las filas se recrean. */
static void cmd_reemplazar(Diagram *dia, const char *ref, const char *ruta, gboolean geometria, GString *resp)
{
  DiaObject *o = por_ref(dia, ref, NULL), *modelo = NULL;
  Diagram *tmp; DiagramData *td; guint i; GList *l; GPtrArray *props; ObjectChange *oc; CObjeto *c;
  GArray *repegar; int k;
  if (!o) { g_string_append_printf(resp, "error no encuentro %s\n", ref); return; }
  if (!(tmp = importar(ruta, resp))) return;
  td = (DiagramData *) tmp;
  for (i = 0; i < td->layers->len && !modelo; i++)
    for (l = ((Layer *) g_ptr_array_index(td->layers, i))->objects; l && !modelo; l = l->next)
      if (((DiaObject *) l->data)->type == o->type) modelo = l->data;
  if (!modelo) { g_object_unref(tmp); g_string_append_printf(resp, "error %s no trae un objeto %s\n", ruta, o->type->name); return; }
  /* relaciones pegadas a filas de la clase: se sueltan y luego se pegan a un punto fijo */
  repegar = g_array_new(FALSE, FALSE, sizeof(Pend));
  if (g_strcmp0(o->type->name, "UML - Class") == 0) {
    for (k = 8; k < o->num_connections - 1; k++) {
      GList *x = g_list_copy(o->connections[k]->connected);
      for (l = x; l; l = l->next) {
        DiaObject *otro = l->data; int h;
        for (h = 0; h < otro->num_handles; h++)
          if (otro->handles[h]->connected_to == o->connections[k]) {
            Pend p = { otro, h, o, -1 };
            conexion(dia, otro, h, o, k, 0);
            g_array_append_val(repegar, p);
          }
      }
      g_list_free(x);
    }
  }
  props = prop_list_from_descs(object_get_prop_descriptions(modelo), geometria ? copiable_geo : copiable);
  modelo->ops->get_props(modelo, props);
  oc = object_apply_props(o, props);
  prop_list_free(props);
  c = g_new0(CObjeto, 1);
  c->c.apply = obj_apply; c->c.revert = obj_revert; c->c.free = obj_free;
  c->obj = o; c->oc = oc;
  apilar(dia, (Change *) c);
  for (i = 0; i < repegar->len; i++) {
    Pend *p = &g_array_index(repegar, Pend, i);
    DiaObject *otro_extremo = p->obj->handles[1 - p->handle]->connected_to ? p->obj->handles[1 - p->handle]->connected_to->object : NULL;
    conexion(dia, p->obj, p->handle, o, otro_extremo ? punto_auto(o, otro_extremo, FALSE, FALSE) : 0, 1);
  }
  g_array_free(repegar, TRUE);
  diagram_update_connections_object(dia, o, TRUE);
  g_object_unref(tmp);
  refrescar(dia); poner_titulo(dia);
  g_string_append_printf(resp, "ok reemplazado %s\n", ref);
}

/* transaccion: cierra el grupo de cambios del tutor (un Ctrl+Z lo deshace entero). Responde "ok transaccion ID":
 * con ese ID, "deshacer_ultimo ID" sabe si lo ultimo de la pila sigue siendo ESE grupo. */
static void cmd_transaccion(Diagram *dia, GString *resp)
{
  UndoStack *s = dia->undo; UndoApplyFunc f = funcion_tp(s);
  if (!f) { g_string_append(resp, "error pila de deshacer vacia\n"); return; }
  if (s->current_change->apply != f) {
    Change *t = g_new0(Change, 1);
    t->apply = f; t->revert = f; t->free = NULL;
    apilar(dia, t); s->depth++;
  }
  poner_titulo(dia);
  g_string_append_printf(resp, "ok transaccion t%p\n", (void *) s->current_change);
}

/* deshacer_ultimo ID: si lo ultimo de la pila de Deshacer de Dia es el grupo ID del tutor, lo deshace como Ctrl+Z
 * (asi, si no se hizo nada mas, el diagrama vuelve a quedar como guardado). Si no, responde "no es lo ultimo". */
static void cmd_deshacer_ultimo(Diagram *dia, const char *id, GString *resp)
{
  UndoStack *s = dia->undo; UndoApplyFunc f = funcion_tp(s);
  Change *c, *p;
  gchar *actual = g_strdup_printf("t%p", (void *) s->current_change);
  gboolean es = id && g_strcmp0(actual, id) == 0 && s->current_change->prev;
  g_free(actual);
  if (!es) { g_string_append(resp, "no es lo ultimo\n"); return; }
  diagram_remove_all_selected(dia, FALSE);
  c = s->current_change;
  do { p = c->prev; (c->revert)(c, dia); c = p; } while (c && c->apply != f);
  s->current_change = c; s->depth--;
  refrescar(dia); poner_titulo(dia);
  g_string_append_printf(resp, "ok deshecho\n%s\n", diagram_is_modified(dia) ? "modificado" : "guardado");
}

/* copia RUTA: guarda una copia de lo que hay en pantalla (todas las capas) sin cambiar el archivo del
 * diagrama ni su estado de guardado: asi el panel lee lo que no se ha guardado */
static void cmd_copia(Diagram *dia, const char *ruta, GString *resp)
{
  DiaExportFilter *ef = filter_guess_export_filter(ruta);
  if (!ef) { g_string_append(resp, "error no hay filtro para .dia\n"); return; }
  ef->export_func(dia->data, ruta, dia->filename, ef->user_data);
  if (!g_file_test(ruta, G_FILE_TEST_EXISTS)) { g_string_append_printf(resp, "error no pude escribir %s\n", ruta); return; }
  g_string_append_printf(resp, "ok copia %s\n", ruta);
}

/* abrir RUTA: abre el archivo como pestana nueva de la misma ventana (o la deja si ya esta abierto) */
static void cmd_abrir(const char *ruta, GString *resp)
{
  gchar *base = g_path_get_basename(ruta);
  Diagram *dia = buscar_diagrama(base);
  g_free(base);
  if (dia) { g_string_append(resp, "ok ya abierto\n"); return; }
  if (!g_file_test(ruta, G_FILE_TEST_EXISTS)) { g_string_append_printf(resp, "error no existe %s\n", ruta); return; }
  dia = diagram_load(ruta, NULL);
  if (!dia) { g_string_append_printf(resp, "error no pude abrir %s\n", ruta); return; }
  diagram_update_extents(dia);
  if (!dia->displays) new_display(dia);
  g_string_append(resp, "ok abierto\n");
}

/* guardar: guarda el diagrama en su archivo (solo para los diagramas del tutor) */
static void cmd_guardar(Diagram *dia, GString *resp)
{
  if (!dia->filename || !diagram_save(dia, dia->filename)) { g_string_append(resp, "error no pude guardar\n"); return; }
  poner_titulo(dia);
  g_string_append(resp, "ok guardado\n");
}

/* cerrar [forzar]: cierra la pestana del diagrama sin preguntar (si tiene cambios sin guardar, solo con forzar) */
static void cmd_cerrar(Diagram *dia, gboolean forzar, GString *resp)
{
  GSList *ds, *l;
  if (diagram_is_modified(dia) && !forzar) { g_string_append(resp, "error tiene cambios sin guardar\n"); return; }
  dia->mollified = FALSE;
  dia->undo->last_save = dia->undo->current_change;   /* = undo_mark_save: asi no sale el dialogo */
  ds = g_slist_copy(dia->displays);
  for (l = ds; l; l = l->next) ddisplay_close((DDisplay *) l->data);   /* el ultimo destruye el diagrama */
  g_slist_free(ds);
  g_string_append(resp, "ok cerrado\n");
}

/* mover REF DX DY: mueve un objeto (cm) y arrastra lo que tiene pegado, como al moverlo con el raton.
 * Sirve para comprobar que las relaciones siguen pegadas; no pasa por Deshacer. */
static void cmd_mover(Diagram *dia, const char *ref, real dx, real dy, GString *resp)
{
  DiaObject *o = por_ref(dia, ref, NULL);
  Point p; ObjectChange *oc;
  if (!o) { g_string_append_printf(resp, "error no encuentro %s\n", ref); return; }
  p = o->position; p.x += dx; p.y += dy;
  oc = o->ops->move(o, &p);
  if (oc) { if (oc->free) oc->free(oc); g_free(oc); }
  diagram_update_connections_object(dia, o, TRUE);
  refrescar(dia);
  g_string_append_printf(resp, "ok movido %s a %.3f %.3f\n", ref, p.x, p.y);
}

/* ==== Version 4: catalogo de tipos, medir, exportar ==== */

/* tipos: todos los tipos de objeto registrados en este Dia (UML, Standard, Flowchart, ER, Network, formas...) */
static void anotar_tipo(gpointer clave, gpointer valor, gpointer data)
{
  DiaObjectType *t = valor;
  g_string_append_printf((GString *) data, "tipo\t%s\n", t && t->name ? t->name : (const char *) clave);
}
static void cmd_tipos(GString *resp)
{
  object_registry_foreach(anotar_tipo, resp);
  g_string_append(resp, "ok tipos\n");
}

static DiaObject *objeto_por_defecto(const char *tipo, GString *resp)
{
  DiaObjectType *t = object_get_type((char *) tipo);
  Handle *h1 = NULL, *h2 = NULL; Point p = { 0, 0 }; DiaObject *o;
  if (!t || !t->ops || !t->ops->create) { g_string_append_printf(resp, "error no existe el tipo %s\n", tipo); return NULL; }
  o = t->ops->create(&p, t->default_user_data, &h1, &h2);
  if (!o) g_string_append_printf(resp, "error no pude crear un %s\n", tipo);
  return o;
}

/* plantilla TIPO RUTA: guarda en RUTA (.dia) un objeto de ese tipo con sus valores por defecto. De ahi saca
 * Python el XML exacto de cada tipo (catalogo_dia.json) para crear objetos de cualquier tipo. */
static void cmd_plantilla(const char *tipo, const char *ruta, GString *resp)
{
  DiaExportFilter *ef = filter_guess_export_filter(ruta);
  DiaObject *o; Diagram *tmp;
  if (!ef) { g_string_append(resp, "error no hay filtro para .dia\n"); return; }
  if (!(o = objeto_por_defecto(tipo, resp))) return;
  tmp = g_object_new(diagram_get_type(), NULL);
  layer_add_object(((DiagramData *) tmp)->active_layer, o);
  ef->export_func((DiagramData *) tmp, ruta, ruta, ef->user_data);
  g_object_unref(tmp);
  g_string_append_printf(resp, "ok plantilla %s\n", tipo);
}

/* propiedades TIPO: "prop NOMBRE TIPO FLAGS DESCRIPCION [opcion=valor...]" de cada propiedad del tipo */
static void cmd_propiedades(const char *tipo, GString *resp)
{
  DiaObject *o = objeto_por_defecto(tipo, resp);
  const PropDescription *pd;
  if (!o) return;
  for (pd = object_get_prop_descriptions(o); pd && pd->name; pd++) {
    g_string_append_printf(resp, "prop\t%s\t%s\t%u\t%s", pd->name, pd->type ? pd->type : "", pd->flags,
                           pd->description ? pd->description : "");
    if (pd->type && g_strcmp0(pd->type, PROP_TYPE_ENUM) == 0 && pd->extra_data) {
      const PropEnumData *e;
      for (e = pd->extra_data; e->name; e++) g_string_append_printf(resp, "\t%s=%u", e->name, e->enumv);
    }
    g_string_append_c(resp, '\n');
  }
  destroy_object_list(g_list_prepend(NULL, o));
  g_string_append_printf(resp, "ok propiedades %s\n", tipo);
}

/* medir RUTA: importa el archivo sin anadirlo a nada y dice el tamano real que le da Dia a cada objeto
 * ("medida ETIQUETA TIPO X Y W H" con su caja exterior). Python coloca los objetos con estas medidas. */
static void cmd_medir(const char *ruta, GString *resp)
{
  Diagram *tmp = importar(ruta, resp);
  guint i; GList *l; int n = 0;
  if (!tmp) return;
  for (i = 0; i < ((DiagramData *) tmp)->layers->len; i++)
    for (l = ((Layer *) g_ptr_array_index(((DiagramData *) tmp)->layers, i))->objects; l; l = l->next) {
      DiaObject *o = l->data; gchar *t = dia_object_get_meta(o, META_TUTOR);
      Rectangle *b = &o->bounding_box;
      Property *pc = object_prop_by_name_type(o, "elem_corner", PROP_TYPE_POINT);
      g_string_append_printf(resp, "medida\t%s\t%s\t%.3f\t%.3f\t%.3f\t%.3f", t ? t : "", o->type->name,
                             b->left, b->top, b->right - b->left, b->bottom - b->top);
      if (pc) {
        g_string_append_printf(resp, "\t%.3f\t%.3f\t%.3f\t%.3f", ((PointProperty *) pc)->point_data.x, ((PointProperty *) pc)->point_data.y,
                               prop_real(o, "elem_width", PROP_TYPE_REAL, 0), prop_real(o, "elem_height", PROP_TYPE_REAL, 0));
        pc->ops->free(pc);
      }
      g_string_append_c(resp, '\n');
      g_free(t); n++;
    }
  g_object_unref(tmp);
  g_string_append_printf(resp, "ok medidos %d\n", n);
}

/* exportar RUTA: dibuja lo que hay en pantalla en RUTA (.svg o .png, por la extension) con el filtro de Dia,
 * sin dialogos y sin la capa "Tutor" (el panel dibuja las marcas encima). No cambia el estado de guardado. */
static void cmd_exportar(Diagram *dia, const char *ruta, GString *resp)
{
  DiaExportFilter *ef = filter_guess_export_filter(ruta);
  Layer *t = capa_tutor(dia, FALSE);
  gboolean vis = t ? t->visible : FALSE;
  if (!ef) { g_string_append_printf(resp, "error no hay filtro para %s\n", ruta); return; }
  g_unlink(ruta);
  if (t) t->visible = FALSE;
  ef->export_func(dia->data, ruta, dia->filename, ef->user_data);
  if (t) t->visible = vis;
  if (!g_file_test(ruta, G_FILE_TEST_EXISTS)) { g_string_append_printf(resp, "error no pude escribir %s\n", ruta); return; }
  g_string_append_printf(resp, "ok exportado %s\t%.3f\t%.3f\t%.3f\t%.3f\n", ef->unique_name ? ef->unique_name : "",
                         dia->data->extents.left, dia->data->extents.top, dia->data->extents.right, dia->data->extents.bottom);
}

/* ---- poner REF PROP=VALOR [PROP=VALOR...]: cambia propiedades de cualquier objeto por su nombre (version 4) ----
 * Usa el sistema de propiedades de Dia (el mismo del dialogo Propiedades), asi vale para cualquier tipo aunque su
 * XML use otros nombres. Todo en un solo cambio con Deshacer. Responde "antes PROP VALOR" (para poder devolverlo)
 * y "ok puesto REF". Valores: texto (con \n = salto de linea), numero, true/false, #rrggbb o color por nombre,
 * entero del enum, flecha y estilo de linea por numero, punto X,Y, fuente "familia[,negrita][,cursiva]".
 * No se aceptan propiedades de archivo (rutas) ni listas. */
static gchar *desescapar(const char *s)
{
  GString *g = g_string_new("");
  for (; *s; s++) {
    if (s[0] == '\\' && s[1] == 'n') { g_string_append_c(g, '\n'); s++; }
    else g_string_append_c(g, *s);
  }
  return g_string_free(g, FALSE);
}

static gchar *escapar(const char *s)
{
  GString *g = g_string_new("");
  for (; s && *s; s++) {
    if (*s == '\n') g_string_append(g, "\\n");
    else if (*s == '\t' || *s == '\r') g_string_append_c(g, ' ');
    else g_string_append_c(g, *s);
  }
  return g_string_free(g, FALSE);
}

static gboolean es_tipo(const char *t, const char *u) { return g_strcmp0(t, u) == 0; }

static gboolean valor_a_prop(Property *p, const char *tipo, const char *v)
{
  char *fin = NULL;
  if (es_tipo(tipo, PROP_TYPE_STRING) || es_tipo(tipo, PROP_TYPE_MULTISTRING)) {
    StringProperty *sp = (StringProperty *) p; g_free(sp->string_data); sp->string_data = desescapar(v); return TRUE;
  }
  if (es_tipo(tipo, PROP_TYPE_TEXT)) {
    TextProperty *tp = (TextProperty *) p; g_free(tp->text_data); tp->text_data = desescapar(v); return TRUE;
  }
  if (es_tipo(tipo, PROP_TYPE_REAL) || es_tipo(tipo, PROP_TYPE_LENGTH) || es_tipo(tipo, PROP_TYPE_FONTSIZE)) {
    real r = g_ascii_strtod(v, &fin);
    if (fin == v || *fin) return FALSE;
    if (es_tipo(tipo, PROP_TYPE_REAL)) ((RealProperty *) p)->real_data = r;
    else if (es_tipo(tipo, PROP_TYPE_LENGTH)) ((LengthProperty *) p)->length_data = r;
    else ((FontsizeProperty *) p)->fontsize_data = r;
    return TRUE;
  }
  if (es_tipo(tipo, PROP_TYPE_INT) || es_tipo(tipo, PROP_TYPE_ENUM)) {
    long n = strtol(v, &fin, 10);
    if (fin == v || *fin) return FALSE;
    if (es_tipo(tipo, PROP_TYPE_INT)) ((IntProperty *) p)->int_data = n; else ((EnumProperty *) p)->enum_data = n;
    return TRUE;
  }
  if (es_tipo(tipo, PROP_TYPE_BOOL)) {
    if (!strcmp(v, "true") || !strcmp(v, "1")) ((BoolProperty *) p)->bool_data = TRUE;
    else if (!strcmp(v, "false") || !strcmp(v, "0")) ((BoolProperty *) p)->bool_data = FALSE;
    else return FALSE;
    return TRUE;
  }
  if (es_tipo(tipo, PROP_TYPE_COLOUR)) return leer_color(v, &((ColorProperty *) p)->color_data);
  if (es_tipo(tipo, PROP_TYPE_ARROW)) {
    ArrowProperty *ap = (ArrowProperty *) p; long n = strtol(v, &fin, 10);
    if (fin == v || *fin || n < 0 || n >= MAX_ARROW_TYPE) return FALSE;
    ap->arrow_data.type = n;
    if (ap->arrow_data.length <= 0) ap->arrow_data.length = 0.5;
    if (ap->arrow_data.width <= 0) ap->arrow_data.width = 0.5;
    return TRUE;
  }
  if (es_tipo(tipo, PROP_TYPE_LINESTYLE)) {
    LinestyleProperty *lp = (LinestyleProperty *) p; long n = strtol(v, &fin, 10);
    if (fin == v || *fin || n < 0 || n > 4) return FALSE;
    lp->style = n; if (lp->dash <= 0) lp->dash = 1.0;
    return TRUE;
  }
  if (es_tipo(tipo, PROP_TYPE_POINT)) {
    real x, y;
    if (!leer_punto(v, &x, &y)) return FALSE;
    ((PointProperty *) p)->point_data.x = x; ((PointProperty *) p)->point_data.y = y;
    return TRUE;
  }
  if (es_tipo(tipo, PROP_TYPE_FONT)) {
    FontProperty *fp = (FontProperty *) p; real alto = 0.8; DiaFontStyle st = 0;
    gchar **partes = g_strsplit(v, ",", 3); int i;
    if (!partes[0] || !*partes[0]) { g_strfreev(partes); return FALSE; }
    for (i = 1; partes[i]; i++) {
      if (!strcmp(partes[i], "negrita")) st |= DIA_FONT_BOLD;
      else if (!strcmp(partes[i], "cursiva")) st |= DIA_FONT_ITALIC;
    }
    if (fp->font_data) { alto = dia_font_get_height(fp->font_data); dia_font_unref(fp->font_data); }
    fp->font_data = dia_font_new(partes[0], st, alto);
    g_strfreev(partes);
    return fp->font_data != NULL;
  }
  return FALSE;
}

static gchar *prop_a_texto(Property *p, const char *tipo)
{
  gchar n[G_ASCII_DTOSTR_BUF_SIZE], m[G_ASCII_DTOSTR_BUF_SIZE];
  if (es_tipo(tipo, PROP_TYPE_STRING) || es_tipo(tipo, PROP_TYPE_MULTISTRING)) return escapar(((StringProperty *) p)->string_data);
  if (es_tipo(tipo, PROP_TYPE_TEXT)) return escapar(((TextProperty *) p)->text_data);
  if (es_tipo(tipo, PROP_TYPE_REAL)) return g_strdup(g_ascii_dtostr(n, sizeof n, ((RealProperty *) p)->real_data));
  if (es_tipo(tipo, PROP_TYPE_LENGTH)) return g_strdup(g_ascii_dtostr(n, sizeof n, ((LengthProperty *) p)->length_data));
  if (es_tipo(tipo, PROP_TYPE_FONTSIZE)) return g_strdup(g_ascii_dtostr(n, sizeof n, ((FontsizeProperty *) p)->fontsize_data));
  if (es_tipo(tipo, PROP_TYPE_INT)) return g_strdup_printf("%d", ((IntProperty *) p)->int_data);
  if (es_tipo(tipo, PROP_TYPE_ENUM)) return g_strdup_printf("%d", ((EnumProperty *) p)->enum_data);
  if (es_tipo(tipo, PROP_TYPE_BOOL)) return g_strdup(((BoolProperty *) p)->bool_data ? "true" : "false");
  if (es_tipo(tipo, PROP_TYPE_COLOUR)) {
    Color *c = &((ColorProperty *) p)->color_data;
    return g_strdup_printf("#%02x%02x%02x", (int) (c->red * 255 + 0.5), (int) (c->green * 255 + 0.5), (int) (c->blue * 255 + 0.5));
  }
  if (es_tipo(tipo, PROP_TYPE_ARROW)) return g_strdup_printf("%d", (int) ((ArrowProperty *) p)->arrow_data.type);
  if (es_tipo(tipo, PROP_TYPE_LINESTYLE)) return g_strdup_printf("%d", (int) ((LinestyleProperty *) p)->style);
  if (es_tipo(tipo, PROP_TYPE_POINT)) {
    Point *q = &((PointProperty *) p)->point_data;
    g_ascii_dtostr(n, sizeof n, q->x); g_ascii_dtostr(m, sizeof m, q->y);
    return g_strdup_printf("%s,%s", n, m);
  }
  if (es_tipo(tipo, PROP_TYPE_FONT)) {
    DiaFont *f = ((FontProperty *) p)->font_data;
    return g_strdup(f ? dia_font_get_family(f) : "sans");
  }
  return NULL;
}

static gboolean prop_a_texto_soporta(const char *tipo)
{
  static const char *si[] = { PROP_TYPE_STRING, PROP_TYPE_MULTISTRING, PROP_TYPE_TEXT, PROP_TYPE_REAL, PROP_TYPE_LENGTH,
    PROP_TYPE_FONTSIZE, PROP_TYPE_INT, PROP_TYPE_ENUM, PROP_TYPE_BOOL, PROP_TYPE_COLOUR, PROP_TYPE_ARROW,
    PROP_TYPE_LINESTYLE, PROP_TYPE_POINT, PROP_TYPE_FONT, NULL };
  int i;
  for (i = 0; si[i]; i++) if (es_tipo(tipo, si[i])) return TRUE;
  return FALSE;
}

static void cmd_poner(Diagram *dia, gchar **argv, gint argc, GString *resp)
{
  DiaObject *o = por_ref(dia, argv[1], NULL);
  const PropDescription *descs;
  GPtrArray *props; GString *antes; int i; gboolean ok = TRUE;
  ObjectChange *oc; CObjeto *c;
  if (!o) { g_string_append_printf(resp, "error no encuentro %s\n", argv[1]); return; }
  descs = object_get_prop_descriptions(o);
  props = g_ptr_array_new(); antes = g_string_new("");
  for (i = 2; i < argc && ok; i++) {
    gchar *nombre = g_strdup(argv[i]), *eq = strchr(nombre, '='), *viejo;
    const PropDescription *pd = NULL; Property *p; GPtrArray *uno;
    if (eq) { *eq = 0; pd = prop_desc_list_find_prop(descs, nombre); }
    if (!eq) { g_string_append_printf(resp, "error falta = en %s\n", argv[i]); ok = FALSE; }
    else if (!pd) { g_string_append_printf(resp, "error %s no tiene la propiedad %s\n", o->type->name, nombre); ok = FALSE; }
    else if (es_tipo(pd->type, PROP_TYPE_FILE) || es_tipo(pd->type, PROP_TYPE_DARRAY) || es_tipo(pd->type, PROP_TYPE_SARRAY)
             || es_tipo(pd->type, PROP_TYPE_DICT) || !prop_a_texto_soporta(pd->type)) {
      g_string_append_printf(resp, "error la propiedad %s (%s) no se puede cambiar asi\n", nombre, pd->type); ok = FALSE;
    } else {
      p = make_new_prop(pd->name, pd->type, 0);
      uno = g_ptr_array_new(); g_ptr_array_add(uno, p);
      o->ops->get_props(o, uno);
      g_ptr_array_free(uno, FALSE);
      viejo = prop_a_texto(p, pd->type);
      if (!valor_a_prop(p, pd->type, eq + 1)) {
        g_string_append_printf(resp, "error valor no valido para %s (%s): %s\n", nombre, pd->type, eq + 1);
        p->ops->free(p); ok = FALSE;
      } else {
        g_ptr_array_add(props, p);
        g_string_append_printf(antes, "antes\t%s\t%s\n", pd->name, viejo ? viejo : "");
      }
      g_free(viejo);
    }
    g_free(nombre);
  }
  if (!ok || props->len == 0) {
    if (ok) g_string_append(resp, "error no dice que propiedad cambiar\n");
    prop_list_free(props); g_string_free(antes, TRUE); return;
  }
  oc = object_apply_props(o, props);
  prop_list_free(props);
  c = g_new0(CObjeto, 1);
  c->c.apply = obj_apply; c->c.revert = obj_revert; c->c.free = obj_free;
  c->obj = o; c->oc = oc;
  apilar(dia, (Change *) c);
  diagram_update_connections_object(dia, o, TRUE);
  refrescar(dia); poner_titulo(dia);
  g_string_append(resp, antes->str);
  g_string_free(antes, TRUE);
  g_string_append_printf(resp, "ok puesto %s\n", argv[1]);
}

/* ==== Version 5: clase en vivo sobre la interfaz (overlay, «hazlo por mi») y cursos ==== */

/* El dialogo de Propiedades de Dia (rol "properties_window") si esta a la vista, y la parte del objeto que muestra */
static GtkWidget *dialogo_propiedades(GtkWidget **parte)
{
  GList *tops = gtk_window_list_toplevels(), *l, *hijos, *h;
  GtkWidget *dlg = NULL;
  for (l = tops; l && !dlg; l = l->next) {
    GtkWidget *w = l->data;
    if (GTK_IS_DIALOG(w) && GTK_WIDGET_VISIBLE(w) && g_strcmp0(gtk_window_get_role(GTK_WINDOW(w)), "properties_window") == 0) dlg = w;
  }
  g_list_free(tops);
  if (dlg && parte) {
    *parte = NULL;
    hijos = gtk_container_get_children(GTK_CONTAINER(GTK_DIALOG(dlg)->vbox));
    for (h = hijos; h; h = h->next)
      if (h->data != (gpointer) GTK_DIALOG(dlg)->action_area && !GTK_IS_SEPARATOR(h->data)) *parte = h->data;
    g_list_free(hijos);
  }
  return dlg;
}

/* Si el dialogo de Propiedades esta editando alguno de estos objetos (que se van a quitar o destruir), se cierra
 * como con su boton Cerrar. Dia lo hace solo cuando borra objetos (properties_hide_if_shown, que no se exporta);
 * sin esto, «Aceptar» aplicaria los cambios a un objeto que ya no existe y Dia se cerraria. */
static void cerrar_dialogo_de(GList *objs)
{
  GtkWidget *parte = NULL, *dlg = dialogo_propiedades(&parte);
  PropDialog *pd; GList *l; gboolean suyo = FALSE;
  if (!dlg || !parte) return;
  pd = g_object_get_data(G_OBJECT(parte), "object-props:dialogdata");
  for (l = objs; l && !suyo; l = l->next) {
    DiaObject *o = l->data;
    if (pd) { if (g_list_find(pd->copies, o)) suyo = TRUE; }
    else if (o->ops->get_properties && g_strcmp0(o->type->name, "UML - Class") == 0) {
      /* la clase UML guarda su propio dialogo: si es el que se ve, es suyo */
      if (o->ops->get_properties(o, FALSE) == parte) suyo = TRUE;
    }
  }
  if (suyo) { tlog("cierro el dialogo de Propiedades: su objeto se quita"); gtk_dialog_response(GTK_DIALOG(dlg), GTK_RESPONSE_CLOSE); }
}

/* pantalla REF [REF...]: donde se ve cada objeto en la pantalla (pixeles, como «widgets») en la pestana de su
 * diagrama, si esa pestana esta a la vista: "pantalla REF X Y W H" (o "fuera REF" si no se ve) */
static void cmd_pantalla(Diagram *dia, gchar **argv, gint argc, GString *resp)
{
  DDisplay *dd = dia->displays ? dia->displays->data : NULL;
  gint i, ox = 0, oy = 0, ancho, alto;
  Rectangle *v;
  if (!dd || !dd->canvas || !GTK_WIDGET_MAPPED(dd->canvas) || !dd->canvas->window) {
    g_string_append(resp, "error la pestana de ese diagrama no esta a la vista\n"); return;
  }
  gdk_window_get_origin(dd->canvas->window, &ox, &oy);
  if (GTK_WIDGET_NO_WINDOW(dd->canvas)) { ox += dd->canvas->allocation.x; oy += dd->canvas->allocation.y; }
  ancho = dd->canvas->allocation.width; alto = dd->canvas->allocation.height;
  v = &dd->visible;
  g_string_append_printf(resp, "lienzo %d %d %d %d\n", ox, oy, ancho, alto);
  for (i = 1; i < argc; i++) {
    DiaObject *o = por_ref(dia, argv[i], NULL);
    Rectangle *b; double x0, y0, x1, y1;
    if (!o) {
      gchar *r = g_strconcat("nombre:", argv[i], NULL);
      o = por_ref(dia, r, NULL); g_free(r);
    }
    if (!o || v->right <= v->left || v->bottom <= v->top) { g_string_append_printf(resp, "falta\t%s\n", argv[i]); continue; }
    b = &o->bounding_box;
    x0 = (b->left - v->left) * ancho / (v->right - v->left); x1 = (b->right - v->left) * ancho / (v->right - v->left);
    y0 = (b->top - v->top) * alto / (v->bottom - v->top);    y1 = (b->bottom - v->top) * alto / (v->bottom - v->top);
    if (x1 < 0 || y1 < 0 || x0 > ancho || y0 > alto) { g_string_append_printf(resp, "fuera\t%s\n", argv[i]); continue; }
    g_string_append_printf(resp, "pantalla\t%s\t%d\t%d\t%d\t%d\n", argv[i], ox + (int) floor(x0), oy + (int) floor(y0),
                           (int) ceil(x1 - x0), (int) ceil(y1 - y0));
  }
  g_string_append(resp, "ok pantalla\n");
}

/* seleccionar REF [REF...] (version 5): ademas de un nombre, tag:ETIQUETA, nombre:TEXTO, id:On o clase:NOMBRE;
 * deja seleccionados todos los que encuentra (resaltar lo nuevo de un paso) */
static void cmd_seleccionar_refs(Diagram *dia, gchar **argv, gint argc, GString *resp)
{
  gint i, n = 0;
  diagram_remove_all_selected(dia, FALSE);
  for (i = 1; i < argc; i++) {
    DiaObject *o = por_ref(dia, argv[i], NULL);
    if (o && !diagram_is_selected(dia, o)) { diagram_select(dia, o); n++; }
    else if (!o) g_string_append_printf(resp, "falta\t%s\n", argv[i]);
  }
  refrescar(dia);
  g_string_append_printf(resp, "ok seleccionados %d\n", n);
}

/* hoja NOMBRE: pone esa hoja (UML, Flowchart...) en la caja de herramientas, como elegirla en su menu */
typedef struct { GtkWidget *menu; } BusqHoja;
static void buscar_hoja(GtkWidget *w, gpointer data)
{
  BusqHoja *b = data;
  if (!b->menu && g_strcmp0(G_OBJECT_TYPE_NAME(w), "DiaDynamicMenu") == 0) b->menu = w;
}
static void cmd_hoja(const char *nombre, GString *resp)
{
  BusqHoja b = { NULL };
  DDisplay *dd = ddisplay_active();
  GtkWidget *top = dd ? (dd->container ? gtk_widget_get_toplevel(dd->container) : dd->shell) : NULL;
  if (top && GTK_WIDGET_MAPPED(top)) { Visita v = { buscar_hoja, &b }; visitar(top, &v); }
  else visitar_todo(buscar_hoja, &b);
  if (!b.menu) { g_string_append(resp, "error no encuentro el menu de hojas de la caja de herramientas\n"); return; }
  dia_dynamic_menu_select_entry((DiaDynamicMenu *) b.menu, nombre);
  g_string_append_printf(resp, "ok hoja %s\n", nombre);
}

/* ---- despacho ---- */

static void cmd_activar(Diagram *dia, GString *resp);   /* definida mas abajo */

static void ejecutar_linea(const char *linea, GString *resp)
{
  gint argc = 0; gchar **argv = NULL; GError *err = NULL;
  const char *objetivo = NULL; Diagram *dia; int i, j;
  if (!*linea) return;
  if (!g_shell_parse_argv(linea, &argc, &argv, &err)) {
    g_string_append_printf(resp, "error sintaxis: %s\n", err ? err->message : "?");
    if (err) g_error_free(err);
    return;
  }
  /* @archivo.dia elige el diagrama */
  for (i = 0, j = 0; i < argc; i++) {
    if (argv[i][0] == '@') objetivo = argv[i] + 1; else argv[j++] = argv[i];
  }
  argc = j;
  if (argc == 0) { g_strfreev(argv); return; }
  if (g_strcmp0(argv[0], "ping") == 0) { g_string_append(resp, "ok ping\n"); g_strfreev(argv); return; }
  if (g_strcmp0(argv[0], "ventanas") == 0) { cmd_ventanas(resp); g_strfreev(argv); return; }
  if (g_strcmp0(argv[0], "widgets") == 0) { cmd_widgets(resp); g_strfreev(argv); return; }
  if (g_strcmp0(argv[0], "pulsar") == 0 && argc >= 2) { cmd_pulsar(argv[1], resp); g_strfreev(argv); return; }
  if (g_strcmp0(argv[0], "abrir") == 0 && argc >= 2) { cmd_abrir(argv[1], resp); g_strfreev(argv); return; }
  if (g_strcmp0(argv[0], "version") == 0) { g_string_append(resp, "ok version 5\n"); g_strfreev(argv); return; }
  if (g_strcmp0(argv[0], "hoja") == 0 && argc >= 2) { cmd_hoja(argv[1], resp); g_strfreev(argv); return; }
  if (g_strcmp0(argv[0], "tipos") == 0) { cmd_tipos(resp); g_strfreev(argv); return; }
  if (g_strcmp0(argv[0], "plantilla") == 0 && argc >= 3) { cmd_plantilla(argv[1], argv[2], resp); g_strfreev(argv); return; }
  if (g_strcmp0(argv[0], "propiedades") == 0 && argc >= 2) { cmd_propiedades(argv[1], resp); g_strfreev(argv); return; }
  if (g_strcmp0(argv[0], "medir") == 0 && argc >= 2) { cmd_medir(argv[1], resp); g_strfreev(argv); return; }
  dia = buscar_diagrama(objetivo);
  if (!dia && !objetivo && g_strcmp0(argv[0], "accion") == 0 && argc >= 2) {   /* sin diagramas (p. ej. FileQuit) */
    cmd_accion(NULL, argv[1], resp); g_strfreev(argv); return;
  }
  if (!dia) { g_string_append(resp, "error no hay diagrama activo (o no se encontro el pedido)\n"); g_strfreev(argv); return; }
  if (g_strcmp0(argv[0], "clase") == 0 && argc >= 4)
    cmd_clase(dia, g_ascii_strtod(argv[1], NULL), g_ascii_strtod(argv[2], NULL), argv[3], resp);
  else if (g_strcmp0(argv[0], "seleccionar") == 0 && argc >= 2 && (argc > 2 || strchr(argv[1], ':')))
    cmd_seleccionar_refs(dia, argv, argc, resp);
  else if (g_strcmp0(argv[0], "seleccionar") == 0 && argc >= 2)
    cmd_seleccionar(dia, argv[1], resp);
  else if (g_strcmp0(argv[0], "pantalla") == 0 && argc >= 2)
    cmd_pantalla(dia, argv, argc, resp);
  else if (g_strcmp0(argv[0], "deseleccionar") == 0) {
    diagram_remove_all_selected(dia, FALSE); refrescar(dia); g_string_append(resp, "ok deseleccionado\n");
  }
  else if (g_strcmp0(argv[0], "cargar") == 0 && argc >= 2)
    cmd_cargar(dia, argv[1], resp);
  else if (g_strcmp0(argv[0], "accion") == 0 && argc >= 2)
    cmd_accion(dia, argv[1], resp);
  else if (g_strcmp0(argv[0], "activar") == 0)
    cmd_activar(dia, resp);
  else if (g_strcmp0(argv[0], "modificado") == 0)
    g_string_append_printf(resp, "%s\nok modificado\n", diagram_is_modified(dia) ? "si" : "no");
  else if (g_strcmp0(argv[0], "recuadro") == 0 && argc >= 5)
    cmd_recuadro(dia, argv, argc, resp);
  else if (g_strcmp0(argv[0], "flecha") == 0 && argc >= 5)
    cmd_flecha(dia, argv, argc, resp);
  else if (g_strcmp0(argv[0], "nota") == 0 && argc >= 4)
    cmd_nota(dia, argv, argc, resp);
  else if (g_strcmp0(argv[0], "borrar_marcas") == 0)
    cmd_borrar_marcas(dia, resp);
  else if (g_strcmp0(argv[0], "cajas") == 0)
    cmd_cajas(dia, argc >= 2 ? argv[1] : NULL, resp);
  else if (g_strcmp0(argv[0], "capas") == 0)
    cmd_capas(dia, resp);
  else if (g_strcmp0(argv[0], "anadir") == 0 && argc >= 2)
    cmd_anadir(dia, argv[1], resp);
  else if (g_strcmp0(argv[0], "quitar") == 0)
    cmd_quitar(dia, argv, argc, resp);
  else if (g_strcmp0(argv[0], "reemplazar") == 0 && argc >= 3)
    cmd_reemplazar(dia, argv[1], argv[2], argc >= 4 && g_strcmp0(argv[3], "geometria") == 0, resp);
  else if (g_strcmp0(argv[0], "transaccion") == 0)
    cmd_transaccion(dia, resp);
  else if (g_strcmp0(argv[0], "deshacer_ultimo") == 0)
    cmd_deshacer_ultimo(dia, argc >= 2 ? argv[1] : NULL, resp);
  else if (g_strcmp0(argv[0], "copia") == 0 && argc >= 2)
    cmd_copia(dia, argv[1], resp);
  else if (g_strcmp0(argv[0], "mover") == 0 && argc >= 4)
    cmd_mover(dia, argv[1], g_ascii_strtod(argv[2], NULL), g_ascii_strtod(argv[3], NULL), resp);
  else if (g_strcmp0(argv[0], "poner") == 0 && argc >= 3)
    cmd_poner(dia, argv, argc, resp);
  else if (g_strcmp0(argv[0], "exportar") == 0 && argc >= 2)
    cmd_exportar(dia, argv[1], resp);
  else if (g_strcmp0(argv[0], "guardar") == 0)
    cmd_guardar(dia, resp);
  else if (g_strcmp0(argv[0], "cerrar") == 0)
    cmd_cerrar(dia, argc >= 2 && g_strcmp0(argv[1], "forzar") == 0, resp);
  else
    g_string_append_printf(resp, "error orden desconocida: %s\n", linea);
  g_strfreev(argv);
}

/* ---- activar: en la interfaz integrada cada diagrama vive en una pestana del cuaderno;
 *      ddisp->container es la pagina. Cambiar de pagina hace que Dia lo marque como activo. ---- */
static void cmd_activar(Diagram *dia, GString *resp)
{
  DDisplay *dd = dia->displays ? dia->displays->data : NULL;
  GtkWidget *padre, *top;
  if (!dd) { g_string_append(resp, "error el diagrama no tiene ventana\n"); return; }
  if (dd->container && (padre = gtk_widget_get_parent(dd->container)) && GTK_IS_NOTEBOOK(padre)) {
    gint n = gtk_notebook_page_num(GTK_NOTEBOOK(padre), dd->container);
    if (n >= 0) gtk_notebook_set_current_page(GTK_NOTEBOOK(padre), n);
  }
  top = dd->container ? gtk_widget_get_toplevel(dd->container) : dd->shell;
  if (top && GTK_IS_WINDOW(top)) gtk_window_present(GTK_WINDOW(top));
  g_string_append(resp, "ok activado\n");
}

static gboolean sondeo(gpointer data)
{
  static gboolean en_curso = FALSE;     /* version 5: una orden que hace girar el bucle de GTK (abrir, Propiedades...) no deja
                                           que el temporizador vuelva a entrar y atienda otra a medias */
  gchar *orden, *contenido = NULL;
  if (en_curso) return TRUE;
  orden = g_build_filename(dir_ordenes, "orden.txt", NULL);
  en_curso = TRUE;
  if (g_file_get_contents(orden, &contenido, NULL, NULL)) {
    gchar **lineas, **p; GString *resp = g_string_new("");
    gchar *tmp = g_build_filename(dir_ordenes, "respuesta.tmp", NULL);
    gchar *fin = g_build_filename(dir_ordenes, "respuesta.txt", NULL);
    g_unlink(orden);
    tlog("orden: %.300s", contenido);
    lineas = g_strsplit(contenido, "\n", -1);
    for (p = lineas; *p; p++) { g_strstrip(*p); ejecutar_linea(*p, resp); }
    g_strfreev(lineas);
    g_file_set_contents(tmp, resp->str, -1, NULL);
    g_unlink(fin); g_rename(tmp, fin);
    tlog("respuesta: %.300s%s", resp->str, resp->len > 300 ? " [...]" : "");   /* version 5: corta (el panel pide widgets cada segundo) */
    g_string_free(resp, TRUE);
    g_free(tmp); g_free(fin); g_free(contenido);
  }
  g_free(orden);
  en_curso = FALSE;
  return TRUE; /* seguir sondeando */
}

/* Una sola instancia por carpeta de ordenes (version 5): "dueno.txt" guarda el PID del Dia que la atiende. Si ese proceso sigue
 * vivo y es un Dia, esta instancia no sondea. Se declaran a mano las funciones de kernel32 (windows.h choca con Rectangle de Dia). */
__declspec(dllimport) void * __stdcall OpenProcess(unsigned long acceso, int heredar, unsigned long pid);
__declspec(dllimport) int __stdcall GetExitCodeProcess(void *proceso, unsigned long *codigo);
__declspec(dllimport) int __stdcall QueryFullProcessImageNameA(void *proceso, unsigned long flags, char *nombre, unsigned long *tam);
__declspec(dllimport) int __stdcall CloseHandle(void *h);
__declspec(dllimport) unsigned long __stdcall GetCurrentProcessId(void);

static gboolean otro_dueno(void)
{
  gchar *ruta = g_build_filename(dir_ordenes, "dueno.txt", NULL), *txt = NULL;
  gboolean otro = FALSE;
  unsigned long yo = GetCurrentProcessId();
  if (g_file_get_contents(ruta, &txt, NULL, NULL)) {
    unsigned long pid = strtoul(txt, NULL, 10);
    if (pid && pid != yo) {
      void *p = OpenProcess(0x1000 /* PROCESS_QUERY_LIMITED_INFORMATION */, 0, pid);
      if (p) {
        unsigned long codigo = 0; char nombre[520]; unsigned long tam = sizeof nombre;
        if (GetExitCodeProcess(p, &codigo) && codigo == 259 /* STILL_ACTIVE */ &&
            QueryFullProcessImageNameA(p, 0, nombre, &tam) && (g_str_has_suffix(g_ascii_strdown(nombre, -1), "diaw.exe") || g_str_has_suffix(g_ascii_strdown(nombre, -1), "dia.exe")))
          otro = TRUE;
        CloseHandle(p);
      }
    }
    g_free(txt);
  }
  if (!otro) {
    gchar *s = g_strdup_printf("%lu\n", yo);
    g_file_set_contents(ruta, s, -1, NULL);
    g_free(s);
  }
  g_free(ruta);
  return otro;
}

DIA_PLUGIN_CHECK_INIT

PluginInitResult
dia_plugin_init(PluginInfo *info)
{
  const gchar *env = g_getenv("DIA_TUTOR_DIR");
  if (!dia_plugin_info_init(info, "Tutor", "Recibe ordenes del tutor en vivo (prototipo)", NULL, NULL))
    return DIA_PLUGIN_INIT_ERROR;
  if (env && *env) dir_ordenes = g_strdup(env);
  else dir_ordenes = g_build_filename(g_get_home_dir(), ".dia", "tutor", NULL);
  g_mkdir_with_parents(dir_ordenes, 0755);
  tlog("plugin cargado; carpeta de ordenes: %s", dir_ordenes);
  if (otro_dueno()) {
    /* version 5: otro Dia vivo ya atiende esta carpeta. Si los dos la sondearan, se quitarian las ordenes y las
     * respuestas el uno al otro (paso en una prueba: un panel lanzo un segundo Dia porque el primero tardo en responder).
     * Este Dia funciona normal, pero sin recibir ordenes. */
    tlog("otro Dia ya atiende esta carpeta: este no recibe ordenes");
    return DIA_PLUGIN_INIT_OK;
  }
  g_timeout_add(100, sondeo, NULL);
  return DIA_PLUGIN_INIT_OK;
}
