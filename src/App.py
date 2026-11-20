import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox

import osmnx as ox
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg,
    NavigationToolbar2Tk,
)

# aqui agrego todo lo de src
CARPETA_INTERFAZ = os.path.dirname(os.path.abspath(__file__))
CARPETA_SRC = os.path.join(os.path.dirname(CARPETA_INTERFAZ), "src")
sys.path.insert(0, CARPETA_SRC)

from Grafo import cargar_grafo
from Lugares import preparar_lugares
from Heuristica import a_estrella
from Rutas import (
    hospitales_disponibles,
    evaluar_hospitales,
    verificar_con_dijkstra,
)
from Prim import calcular_mst, comparar_individual_vs_mst

# colores y fuente 
COLOR_FONDO = "#eef2f7"
COLOR_AZUL = "#12355b"
COLOR_BOTON = "#2f6db5"
COLOR_VERDE = "#2e9e5b"
COLOR_MORADO = "#7b3fa0"
COLOR_GRIS = "#6b7785"
FUENTE = "Segoe UI"

# colores de las rutas dibujadas en el mapa.
COLOR_RUTA_RAPIDA = "#0b2a6f"      # azul oscuro: la ruta más rápida
COLOR_RUTA_OTRAS = "#90ee90"       # verde muy claro: las demás rutas
COLOR_RUTA_AMBULANCIA = "darkorange"


class App(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title("Despacho de ambulancias - Teusaquillo, Bogotá")
        self.geometry("1380x840")
        self.minsize(1100, 700)
        self.configure(bg=COLOR_FONDO)

        # guardamos aquí los datos que cargamos del proyecto.
        self.grafo = None
        self.hospitales = []
        self.emergencias = []
        self.ambulancias = []

        # guardamos los elementos del mapa que cambian (rutas, marcadores)
        # para poder borrarlos sin redibujar todo el grafo vial.
        self.dinamicos = []
        self.leyenda = None
        self.xlim = None
        self.ylim = None

        # variables de texto que se muestran en la interfaz.
        self.estado = tk.StringVar(value="iniciando...")
        self.modo = tk.StringVar(value="rapido")
        self.t1 = tk.StringVar()
        self.t2 = tk.StringVar()
        self.t3 = tk.StringVar()

        self._crear_encabezado()
        self._crear_barra_estado()
        self._crear_cuerpo()

        self._actualizar_tarea(self.t1, "○", "tarea 1", "pendiente")
        self._actualizar_tarea(self.t2, "○", "tarea 2", "pendiente")
        self._actualizar_tarea(self.t3, "○", "tarea 3", "pendiente")

        # esperamos un instante para que la ventana se muestre antes de
        # cargar el mapa, que puede tardar unos segundos.
        self.after(300, self._cargar_datos)

    # 
    # construcción de la ventana
    # 
    def _crear_encabezado(self):
        # creamos la franja azul superior con el título del sistema.
        cabecera = tk.Frame(self, bg=COLOR_AZUL)
        cabecera.pack(fill="x")

        tk.Label(cabecera, text="Sistema de despacho de ambulancias",
                 bg=COLOR_AZUL, fg="white",
                 font=(FUENTE, 17, "bold")).pack(anchor="w", padx=16, pady=(10, 0))
        tk.Label(cabecera,
                 text="Teusaquillo, Bogotá  ·  rutas con A*  ·  red de conexión con Prim",
                 bg=COLOR_AZUL, fg="#b9cce6",
                 font=(FUENTE, 10)).pack(anchor="w", padx=16, pady=(0, 10))

    def _crear_barra_estado(self):
        # creamos la barra inferior donde mostramos mensajes de estado.
        tk.Label(self, textvariable=self.estado, anchor="w",
                 bg=COLOR_AZUL, fg="white", font=(FUENTE, 9),
                 padx=12, pady=4).pack(side="bottom", fill="x")

    def _caja(self, padre, titulo):
        # creamos un recuadro con título para agrupar controles.
        caja = tk.LabelFrame(padre, text=titulo, bg=COLOR_FONDO,
                             fg=COLOR_AZUL, font=(FUENTE, 10, "bold"),
                             padx=8, pady=6)
        caja.pack(fill="x", pady=4)
        return caja

    def _boton(self, padre, texto, comando, color):
        # creamos un botón plano con color.
        return tk.Button(padre, text=texto, command=comando, bg=color,
                         fg="white", activebackground=color,
                         activeforeground="white", relief="flat",
                         font=(FUENTE, 10, "bold"), cursor="hand2",
                         padx=8, pady=6)

    def _crear_cuerpo(self):
        cuerpo = tk.Frame(self, bg=COLOR_FONDO)
        cuerpo.pack(fill="both", expand=True)

        # ---------- panel izquierdo: controles y resultados ----------
        panel = tk.Frame(cuerpo, bg=COLOR_FONDO, width=430)
        panel.pack(side="left", fill="y", padx=(10, 5), pady=8)
        panel.pack_propagate(False)

        # caja 1: pedir la ambulancia.
        caja = self._caja(panel, "1. pide una ambulancia")

        tk.Label(caja, text="lugar de recogida:", bg=COLOR_FONDO,
                 font=(FUENTE, 9)).pack(anchor="w")
        self.combo_emergencia = ttk.Combobox(caja, state="readonly", width=52)
        self.combo_emergencia.pack(fill="x", pady=(0, 6))

        tk.Label(caja, text="hospital de destino:", bg=COLOR_FONDO,
                 font=(FUENTE, 9)).pack(anchor="w")
        tk.Radiobutton(caja, text="el hospital más rápido en llegar",
                       variable=self.modo, value="rapido",
                       command=self._actualizar_modo, bg=COLOR_FONDO,
                       font=(FUENTE, 9)).pack(anchor="w")
        tk.Radiobutton(caja, text="el hospital de mi preferencia",
                       variable=self.modo, value="preferido",
                       command=self._actualizar_modo, bg=COLOR_FONDO,
                       font=(FUENTE, 9)).pack(anchor="w")
        self.combo_hospital = ttk.Combobox(caja, state="disabled", width=52)
        self.combo_hospital.pack(fill="x", pady=(0, 6))

        self._boton(caja, "PEDIR AMBULANCIA", self.pedir_ambulancia,
                    COLOR_VERDE).pack(fill="x")

        # caja de botones: prim, comparación y limpiar.
        fila = tk.Frame(panel, bg=COLOR_FONDO)
        fila.pack(fill="x", pady=4)
        self._boton(fila, "árbol de Prim", self.ver_prim,
                    COLOR_MORADO).pack(side="left", expand=True, fill="x", padx=(0, 3))
        self._boton(fila, "comparación", self.ver_comparacion,
                    COLOR_BOTON).pack(side="left", expand=True, fill="x", padx=3)
        self._boton(fila, "limpiar mapa", self.limpiar_mapa,
                    COLOR_GRIS).pack(side="left", expand=True, fill="x", padx=(3, 0))

        # caja de resultados: texto con barra de desplazamiento.
        caja_res = tk.LabelFrame(panel, text="resultados", bg=COLOR_FONDO,
                                 fg=COLOR_AZUL, font=(FUENTE, 10, "bold"),
                                 padx=6, pady=6)
        caja_res.pack(fill="both", expand=True, pady=4)

        barra = ttk.Scrollbar(caja_res)
        barra.pack(side="right", fill="y")
        self.texto = tk.Text(caja_res, height=12, wrap="word",
                             font=("Consolas", 9), bg="white",
                             relief="flat", yscrollcommand=barra.set,
                             state="disabled")
        self.texto.pack(side="left", fill="both", expand=True)
        barra.config(command=self.texto.yview)

        # caja de tareas del proyecto.
        caja_t = self._caja(panel, "tareas del proyecto")
        for variable in (self.t1, self.t2, self.t3):
            tk.Label(caja_t, textvariable=variable, bg=COLOR_FONDO,
                     justify="left", anchor="w", wraplength=390,
                     font=(FUENTE, 9)).pack(fill="x", pady=2)

        # ---------- panel derecho: el mapa ----------
        derecha = tk.Frame(cuerpo, bg="white")
        derecha.pack(side="left", fill="both", expand=True,
                     padx=(5, 10), pady=8)

        # usamos figure (sin pyplot) para incrustar el mapa en tkinter.
        self.fig = Figure(figsize=(8, 8), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=derecha)
        barra_mapa = NavigationToolbar2Tk(self.canvas, derecha)
        barra_mapa.update()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    # 
    # utilidades de texto y estado
    # 
    def _escribir(self, texto):
        # reemplazamos el contenido del cuadro de resultados.
        self.texto.configure(state="normal")
        self.texto.delete("1.0", "end")
        self.texto.insert("end", texto)
        self.texto.configure(state="disabled")

    def _ocupado(self, mensaje):
        # mostramos un mensaje y el cursor de espera mientras calculamos.
        self.estado.set(mensaje)
        self.config(cursor="watch")
        self.update_idletasks()

    def _libre(self, mensaje="listo"):
        # restauramos el cursor y el mensaje de estado.
        self.estado.set(mensaje)
        self.config(cursor="")

    def _actualizar_tarea(self, variable, icono, nombre, detalle):
        # escribimos en la interfaz el enunciado de cada tarea del proyecto
        # junto con su estado actual.
        enunciados = {
            "tarea 1": "Modelar grafo vial con distancias/tiempos; "
                       "implementar A* para rutas puntuales entre "
                       "estaciones y emergencias.",
            "tarea 2": "Calcular MST sobre nodos de interés para diseñar "
                       "red de patrullaje/inspección eficiente.",
            "tarea 3": "Comparar rutas individuales vs recorrido MST "
                       "optimizado (costo total, cobertura).",
        }
        variable.set(f"{icono} {nombre.capitalize()}: {enunciados[nombre]}\n"
                     f"     → {detalle}")

    def _actualizar_modo(self):
        # habilitamos la lista de hospitales solo si el usuario quiere
        # elegir uno específico.
        if self.modo.get() == "preferido":
            self.combo_hospital.configure(state="readonly")
        else:
            self.combo_hospital.configure(state="disabled")

    # 
    # carga de datos y dibujo del mapa base
    # 
    def _cargar_datos(self):
        # cargamos el grafo vial y los lugares usando los módulos de src.
        self._ocupado("cargando el mapa y los lugares (puede tardar unos segundos)...")

        try:
            self.grafo = cargar_grafo()
            self.hospitales, self.emergencias, self.ambulancias = \
                preparar_lugares(self.grafo)
        except SystemExit as error:
            messagebox.showerror("Error al cargar el mapa", str(error))
            self.destroy()
            return

        if not self.hospitales or not self.emergencias:
            messagebox.showerror(
                "Faltan datos",
                "no hay hospitales o puntos de emergencia con coordenadas válidas.")
            self.destroy()
            return

        # llenamos las listas desplegables con id y nombre de cada lugar.
        self.combo_emergencia["values"] = [
            f"{e['id']} - {e['nombre']}" for e in self.emergencias]
        self.combo_hospital["values"] = [
            f"{h['id']} - {h['nombre']}" for h in self.hospitales]
        self.combo_emergencia.current(0)
        self.combo_hospital.current(0)

        self._dibujar_base()

        self._actualizar_tarea(
            self.t1, "●", "tarea 1",
            f"grafo listo: {self.grafo.number_of_nodes()} intersecciones y "
            f"{self.grafo.number_of_edges()} calles con longitud, velocidad y "
            "tiempo. pide una ambulancia para ejecutar A*.")
        self._actualizar_tarea(self.t2, "○", "tarea 2",
                               "pulsa «árbol de Prim» para calcularlo.")
        self._actualizar_tarea(self.t3, "○", "tarea 3",
                               "pulsa «comparación» para calcularla.")

        self._escribir("mapa listo.\n\nelige un lugar de recogida, el hospital "
                       "de destino y pulsa «PEDIR AMBULANCIA».")
        self._libre("listo")

    def _dibujar_base(self):
        # dibujamos una sola vez la red vial en gris y encima todos los
        # hospitales, ambulancias y puntos de emergencia.
        ox.plot_graph(self.grafo, ax=self.ax, node_size=0,
                      edge_color="lightgray", edge_linewidth=0.5,
                      bgcolor="white", show=False, close=False)

        # puntos de emergencia: círculos dorados con su id.
        self.ax.scatter(
            [self.grafo.nodes[e["nodo"]]["x"] for e in self.emergencias],
            [self.grafo.nodes[e["nodo"]]["y"] for e in self.emergencias],
            marker="o", s=70, color="gold", edgecolors="black", zorder=5)

        # hospitales: cruces azules con su id.
        self.ax.scatter(
            [self.grafo.nodes[h["nodo"]]["x"] for h in self.hospitales],
            [self.grafo.nodes[h["nodo"]]["y"] for h in self.hospitales],
            marker="P", s=230, color="royalblue", edgecolors="white", zorder=6)

        # ambulancias: cuadrados rojos pequeños sobre su hospital.
        self.ax.scatter(
            [self.grafo.nodes[a["nodo"]]["x"] for a in self.ambulancias],
            [self.grafo.nodes[a["nodo"]]["y"] for a in self.ambulancias],
            marker="s", s=45, color="red", edgecolors="white", zorder=7)

        for lugar in self.emergencias + self.hospitales:
            self.ax.annotate(
                lugar["id"],
                (self.grafo.nodes[lugar["nodo"]]["x"],
                 self.grafo.nodes[lugar["nodo"]]["y"]),
                fontsize=7, fontweight="bold", xytext=(5, 5),
                textcoords="offset points", zorder=8)

        # guardamos la vista completa para poder volver a ella.
        self.xlim = self.ax.get_xlim()
        self.ylim = self.ax.get_ylim()

        self._poner_leyenda([])
        self.canvas.draw()

    # 
    # utilidades de dibujo
    # 
    def _limpiar_dinamicos(self):
        # borramos las rutas y marcadores del pedido anterior.
        for artista in self.dinamicos:
            try:
                artista.remove()
            except Exception:
                pass
        self.dinamicos = []

    def _linea(self, ruta, color, ancho, alpha, zorder, estilo="-"):
        # dibujamos una ruta siguiendo los nodos reales del grafo vial.
        xs = [self.grafo.nodes[n]["x"] for n in ruta]
        ys = [self.grafo.nodes[n]["y"] for n in ruta]
        linea, = self.ax.plot(xs, ys, color=color, linewidth=ancho,
                              alpha=alpha, zorder=zorder, linestyle=estilo,
                              solid_capstyle="round")
        self.dinamicos.append(linea)

    def _marcador(self, lugar, marcador, color, tamano, zorder, texto=None):
        # dibujamos un marcador grande sobre un lugar, con una etiqueta
        # opcional.
        x = self.grafo.nodes[lugar["nodo"]]["x"]
        y = self.grafo.nodes[lugar["nodo"]]["y"]
        punto = self.ax.scatter([x], [y], marker=marcador, s=tamano,
                                color=color, edgecolors="black",
                                zorder=zorder)
        self.dinamicos.append(punto)

        if texto:
            nota = self.ax.annotate(
                texto, (x, y), fontsize=8, fontweight="bold",
                xytext=(10, 12), textcoords="offset points", zorder=zorder + 1,
                bbox=dict(boxstyle="round", fc="white", ec="gray", alpha=0.92))
            self.dinamicos.append(nota)

    def _enfocar(self, rutas):
        # acercamos la vista al área que ocupan las rutas dibujadas.
        xs = [self.grafo.nodes[n]["x"] for r in rutas for n in r]
        ys = [self.grafo.nodes[n]["y"] for r in rutas for n in r]
        margen = max(max(xs) - min(xs), max(ys) - min(ys)) * 0.12 + 0.002
        self.ax.set_xlim(min(xs) - margen, max(xs) + margen)
        self.ax.set_ylim(min(ys) - margen, max(ys) + margen)

    def _vista_completa(self):
        # volvemos a mostrar todo el mapa.
        self.ax.set_xlim(self.xlim)
        self.ax.set_ylim(self.ylim)

    def _punto_leyenda(self, marcador, color, etiqueta, tamano=9):
        return Line2D([0], [0], marker=marcador, color="w",
                      markerfacecolor=color, markeredgecolor="black",
                      markersize=tamano, label=etiqueta)

    def _linea_leyenda(self, color, etiqueta, estilo="-"):
        return Line2D([0], [0], color=color, linewidth=3,
                      linestyle=estilo, label=etiqueta)

    def _poner_leyenda(self, extra):
        # reconstruimos la leyenda con los elementos base y los del
        # dibujo actual.
        if self.leyenda is not None:
            self.leyenda.remove()

        base = [
            self._punto_leyenda("o", "gold", "punto de emergencia", 8),
            self._punto_leyenda("P", "royalblue", "hospital", 10),
            self._punto_leyenda("s", "red", "ambulancia (en su hospital)", 7),
        ]
        self.leyenda = self.ax.legend(handles=base + extra,
                                      loc="upper right", fontsize=7.5,
                                      framealpha=0.95)

    # 
    # pedir ambulancia (a*)
    # 
    def pedir_ambulancia(self):
        if self.grafo is None:
            return

        # leemos el lugar de recogida elegido por el usuario.
        i = self.combo_emergencia.current()
        if i < 0:
            messagebox.showinfo("Falta un dato", "elige el lugar de recogida.")
            return
        emergencia = self.emergencias[i]

        # si el usuario prefiere un hospital, verificamos que pueda
        # recibir pacientes.
        hospital_pref = None
        if self.modo.get() == "preferido":
            j = self.combo_hospital.current()
            if j < 0:
                messagebox.showinfo("Falta un dato", "elige un hospital.")
                return
            hospital_pref = self.hospitales[j]
            if not hospital_pref.get("disponible_recibir"):
                messagebox.showwarning(
                    "Hospital no disponible",
                    f"{hospital_pref['nombre']} no puede recibir pacientes "
                    "en este momento.")
                return

        self._ocupado("calculando rutas con A*...")

        # 1) buscamos la ambulancia que llega más rápido al paciente.
        # comparamos con a* el tiempo de cada ambulancia disponible, no
        # solo la distancia en línea recta.
        disponibles = [a for a in self.ambulancias if a.get("disponible")]
        if not disponibles:
            self._libre()
            self._escribir("no hay ambulancias disponibles en este momento.")
            messagebox.showwarning("Sin ambulancias",
                                   "no hay ambulancias disponibles.")
            return

        llegadas = []
        for amb in disponibles:
            calculo = a_estrella(self.grafo, amb["nodo"], emergencia["nodo"])
            if calculo is not None:
                llegadas.append((amb, calculo))

        if not llegadas:
            self._libre()
            self._escribir("ninguna ambulancia puede llegar a ese punto.")
            return

        llegadas.sort(key=lambda item: item[1][1])
        amb, (ruta_amb, t_amb, d_amb) = llegadas[0]

        # 2) calculamos las rutas de la emergencia a todos los hospitales
        # para dibujarlas, y elegimos el destino según la opción del usuario.
        todos, _ = evaluar_hospitales(self.grafo, emergencia, self.hospitales)

        if hospital_pref is None:
            candidatos = hospitales_disponibles(self.hospitales)
        else:
            candidatos = [hospital_pref]

        validos, _ = evaluar_hospitales(self.grafo, emergencia, candidatos)

        if not validos:
            self._libre()
            self._escribir("no existe ruta hacia el hospital elegido.")
            messagebox.showwarning("Sin ruta", "no existe ruta hacia ese hospital.")
            return

        destino = validos[0]
        hospital = destino["hospital"]
        verificacion = "OK" if verificar_con_dijkstra(
            self.grafo, emergencia, destino) else "REVISAR"

        # 3) dibujamos todo en el mapa.
        self._limpiar_dinamicos()
        rutas_zoom = [ruta_amb, destino["ruta"]]

        # rutas posibles a los demás hospitales: verde muy claro.
        for r in todos:
            if r["hospital"]["id"] != hospital["id"]:
                self._linea(r["ruta"], COLOR_RUTA_OTRAS, 3, 0.9, 3)
                rutas_zoom.append(r["ruta"])

        # ruta de la ambulancia hacia el paciente: naranja punteada.
        self._linea(ruta_amb, COLOR_RUTA_AMBULANCIA, 3, 1, 4, "--")

        # ruta más rápida del paciente al hospital: azul oscuro.
        self._linea(destino["ruta"], COLOR_RUTA_RAPIDA, 4.5, 1, 5)

        self._marcador(emergencia, "*", "gold", 520, 9, "paciente")
        self._marcador(hospital, "P", "royalblue", 420, 9,
                       f"destino: {hospital['nombre']}")
        self._marcador(amb, "s", "red", 260, 10,
                       f"ambulancia más rápida:\n{amb['nombre']}")

        self._enfocar(rutas_zoom)
        self._poner_leyenda([
            self._punto_leyenda("*", "gold", "paciente (lugar de recogida)", 13),
            self._punto_leyenda("s", "red", "ambulancia más rápida", 9),
            self._linea_leyenda(COLOR_RUTA_AMBULANCIA, "ambulancia → paciente", "--"),
            self._linea_leyenda(COLOR_RUTA_RAPIDA, "ruta más rápida al hospital"),
            self._linea_leyenda(COLOR_RUTA_OTRAS, "otras rutas posibles"),
        ])
        self.canvas.draw()

        # 4) escribimos el resumen del pedido.
        hospital_amb = next((h for h in self.hospitales
                             if h["id"] == amb["hospital_id"]), None)
        origen_amb = hospital_amb["nombre"] if hospital_amb else "?"
        simulada = " (simulada)" if amb.get("simulada") else ""
        simulado_h = " (dato simulado)" if hospital.get("disponibilidad_simulada") else ""

        lineas = [
            "PEDIDO DE AMBULANCIA",
            f"recogida: {emergencia['nombre']}",
            "",
            "AMBULANCIA MÁS RÁPIDA (A*)",
            f"  {amb['nombre']}{simulada}",
            f"  sale de: {origen_amb}",
            f"  llega en {t_amb / 60:.1f} min ({d_amb / 1000:.2f} km)",
            "  comparación de ambulancias:",
        ]
        for otra, (_, t, _) in llegadas:
            lineas.append(f"    - {otra['nombre']}: {t / 60:.1f} min")

        modo_texto = "más rápido" if hospital_pref is None else "elegido por el usuario"
        lineas += [
            "",
            f"HOSPITAL DE DESTINO ({modo_texto})",
            f"  {hospital['nombre']}",
            f"  paciente → hospital: {destino['tiempo_s'] / 60:.1f} min "
            f"({destino['distancia_m'] / 1000:.2f} km)",
            f"  disponibilidad: disponible{simulado_h}",
            "  otras rutas posibles:",
        ]
        for r in todos:
            if r["hospital"]["id"] != hospital["id"]:
                lineas.append(
                    f"    - {r['hospital']['nombre']}: {r['tiempo_s'] / 60:.1f} min")

        lineas += [
            "",
            f"TIEMPO TOTAL: {(t_amb + destino['tiempo_s']) / 60:.1f} min",
            f"  ({t_amb / 60:.1f} de llegada + {destino['tiempo_s'] / 60:.1f} "
            "de traslado)",
            f"verificación con Dijkstra: {verificacion}",
        ]
        self._escribir("\n".join(lineas))

        self._actualizar_tarea(
            self.t1, "✔", "tarea 1",
            f"A* ejecutado sobre el grafo vial usando el tiempo de cada calle: "
            f"{amb['nombre']} llega en {t_amb / 60:.1f} min y traslada al "
            f"paciente a {hospital['nombre']} en {destino['tiempo_s'] / 60:.1f} min.")
        self._libre("ruta calculada")

    #  
    # árbol de prim
    #  
    def ver_prim(self):
        if self.grafo is None:
            return

        self._ocupado("calculando el árbol de Prim (la primera vez puede tardar)...")

        puntos = self.emergencias + self.hospitales
        nombres = {p["id"]: p["nombre"] for p in puntos}
        mst = calcular_mst(self.grafo, puntos)

        # dibujamos cada conexión del árbol siguiendo las calles reales.
        # usamos rojo si la conexión toca un hospital y morado si no.
        self._limpiar_dinamicos()
        ids_hospitales = {h["id"] for h in self.hospitales}

        for a in mst["aristas"]:
            con_hospital = (a["origen_id"] in ids_hospitales
                            or a["destino_id"] in ids_hospitales)
            self._linea(a["ruta"], "crimson" if con_hospital else "purple",
                        3, 0.7, 4)

        self._vista_completa()
        self._poner_leyenda([
            self._linea_leyenda("crimson", "conexión con un hospital"),
            self._linea_leyenda("purple", "conexión entre emergencias"),
        ])
        self.canvas.draw()

        # escribimos las conexiones del árbol en el cuadro de resultados.
        lineas = [
            "ÁRBOL DE EXPANSIÓN MÍNIMA (PRIM)",
            f"puntos de interés: {len(puntos)}",
            f"conexiones: {len(mst['aristas'])}",
            f"peso total: {mst['peso_total_s'] / 60:.1f} min",
            "",
            "conexiones (sentido real de la ruta):",
        ]
        for a in mst["aristas"]:
            lineas.append(
                f"  {a['origen_id']} → {a['destino_id']}: "
                f"{a['tiempo_s'] / 60:.1f} min, {a['distancia_m'] / 1000:.2f} km")
        self._escribir("\n".join(lineas))

        self._actualizar_tarea(
            self.t2, "✔", "tarea 2",
            f"Prim conectó los {len(puntos)} nodos de interés con "
            f"{len(mst['aristas'])} conexiones. peso total: "
            f"{mst['peso_total_s'] / 60:.1f} min.")
        self._libre("árbol de Prim calculado")

    #  
    # comparación individuales vs mst
    #  
    def ver_comparacion(self):
        if self.grafo is None:
            return

        self._ocupado("calculando la comparación (la primera vez puede tardar)...")

        puntos = self.emergencias + self.hospitales
        mst = calcular_mst(self.grafo, puntos)
        comp = comparar_individual_vs_mst(self.grafo, puntos,
                                          self.hospitales, mst)

        if comp is None:
            self._libre()
            self._escribir("no hay hospitales para usar como base.")
            return

        ind = comp["individual"]
        red = comp["mst"]

        # dibujamos en el mapa las rutas individuales desde la base.
        self._limpiar_dinamicos()
        for ruta in comp["rutas_individuales"]:
            self._linea(ruta, "darkorange", 2.5, 0.6, 4)
        self._marcador(comp["base"], "P", "royalblue", 420, 9,
                       f"base: {comp['base']['nombre']}")
        self._vista_completa()
        self._poner_leyenda([
            self._linea_leyenda("darkorange", "rutas individuales desde la base"),
        ])
        self.canvas.draw()

        lineas = [
            "COMPARACIÓN: INDIVIDUALES vs MST",
            f"base: {comp['base']['nombre']}",
            "(el hospital base con menor costo)",
            "",
            f"{'métrica':<28}{'indiv.':>8}{'MST':>8}",
            f"{'costo total (min)':<28}{ind['tiempo_s'] / 60:>8.1f}{red['tiempo_s'] / 60:>8.1f}",
            f"{'distancia recorrida (km)':<28}{ind['distancia_m'] / 1000:>8.1f}{red['distancia_m'] / 1000:>8.1f}",
            f"{'calles distintas (km)':<28}{ind['km_calles']:>8.1f}{red['km_calles']:>8.1f}",
            f"{'intersecciones':<28}{ind['nodos']:>8}{red['nodos']:>8}",
            f"{'cobertura del mapa (%)':<28}{ind['cobertura_pct']:>8.1f}{red['cobertura_pct']:>8.1f}",
            f"{'puntos alcanzados':<28}{ind['puntos']:>8}{red['puntos']:>8}",
            "",
            f"el MST cambia el costo en {comp['ahorro_tiempo_pct']:.1f}% "
            "frente a las rutas individuales.",
            "nota: el MST usa el menor tiempo entre ambos sentidos.",
        ]
        self._escribir("\n".join(lineas))

        self._actualizar_tarea(
            self.t3, "✔", "tarea 3",
            f"costo individual {ind['tiempo_s'] / 60:.1f} min vs MST "
            f"{red['tiempo_s'] / 60:.1f} min ({comp['ahorro_tiempo_pct']:.1f}%). "
            f"cobertura: {ind['cobertura_pct']:.1f}% vs {red['cobertura_pct']:.1f}%.")

        self._ventana_comparacion(comp)
        self._libre("comparación calculada")

    def _ventana_comparacion(self, comp):
        # abrimos una ventana con barras que comparan las dos estrategias.
        ventana = tk.Toplevel(self)
        ventana.title("Comparación: rutas individuales vs MST")
        ventana.geometry("920x420")

        ind = comp["individual"]
        red = comp["mst"]

        metricas = [
            ("costo total (min)", ind["tiempo_s"] / 60, red["tiempo_s"] / 60),
            ("calles distintas (km)", ind["km_calles"], red["km_calles"]),
            ("cobertura del mapa (%)", ind["cobertura_pct"], red["cobertura_pct"]),
        ]

        fig = Figure(figsize=(9, 4), dpi=100)
        for k, (nombre, valor_ind, valor_mst) in enumerate(metricas, start=1):
            eje = fig.add_subplot(1, 3, k)
            barras = eje.bar(["individuales", "MST"], [valor_ind, valor_mst],
                             color=["darkorange", "purple"])
            eje.set_title(nombre, fontsize=10)
            for barra, valor in zip(barras, [valor_ind, valor_mst]):
                eje.text(barra.get_x() + barra.get_width() / 2, valor,
                         f"{valor:.1f}", ha="center", va="bottom", fontsize=9)
        fig.tight_layout()

        lienzo = FigureCanvasTkAgg(fig, master=ventana)
        lienzo.draw()
        lienzo.get_tk_widget().pack(fill="both", expand=True)

    #  
    # limpiar
    #  
    def limpiar_mapa(self):
        # quitamos las rutas y volvemos a la vista completa del mapa.
        if self.grafo is None:
            return
        self._limpiar_dinamicos()
        self._vista_completa()
        self._poner_leyenda([])
        self.canvas.draw()
        self._escribir("mapa limpio. elige un lugar y pide una ambulancia.")


if __name__ == "__main__":
    App().mainloop()