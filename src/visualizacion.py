import matplotlib.pyplot as plt
import osmnx as ox


def _dibujar_base(grafo):
    # dibujamos la red vial en gris claro y dejamos la figura abierta
    # (show=False, close=False) para agregar encima las rutas y los
    # marcadores antes de mostrarla.
    fig, ax = ox.plot_graph(
        grafo,
        figsize=(10, 10),
        node_size=0,
        edge_color="lightgray",
        edge_linewidth=0.4,
        bgcolor="white",
        show=False,
        close=False
    )
    return fig, ax


def _coordenadas(grafo, ruta):
    # obtenemos las listas x (longitud) y y (latitud) de los nodos de
    # una ruta, para dibujarla siguiendo las calles reales.
    xs = [grafo.nodes[n]["x"] for n in ruta]
    ys = [grafo.nodes[n]["y"] for n in ruta]
    return xs, ys


def mapa_ruta_astar(grafo, emergencia, resultado, otros_hospitales):
    # dibujamos la visualización 1: la ruta más rápida con a* desde el
    # punto de emergencia hasta el hospital de destino.
    fig, ax = _dibujar_base(grafo)

    hospital = resultado["hospital"]
    ruta = resultado["ruta"]
    xs, ys = _coordenadas(grafo, ruta)

    # dibujamos la ruta en un color llamativo y con buen grosor.
    ax.plot(xs, ys, color="red", linewidth=3.5, zorder=3,
            label="ruta más rápida (a*)")

    # dibujamos en pequeño los demás hospitales como referencia.
    if otros_hospitales:
        ax.scatter(
            [h_nodo_x(grafo, h) for h in otros_hospitales],
            [h_nodo_y(grafo, h) for h in otros_hospitales],
            marker="P", s=90, color="lightskyblue", edgecolors="gray",
            zorder=4, label="otros hospitales"
        )

    # marcamos el punto de emergencia con una estrella y el hospital de
    # destino con una cruz azul, ambos grandes para destacarlos.
    ax.scatter(xs[0], ys[0], marker="*", s=450, color="gold",
               edgecolors="black", zorder=6,
               label=f"emergencia: {emergencia['nombre']}")
    ax.scatter(xs[-1], ys[-1], marker="P", s=300, color="blue",
               edgecolors="white", zorder=6,
               label=f"hospital: {hospital['nombre']}")

    # acercamos la vista a la ruta con un margen, porque el mapa
    # completo es muy grande y la ruta se vería diminuta.
    margen = max(max(xs) - min(xs), max(ys) - min(ys)) * 0.25 + 0.002
    ax.set_xlim(min(xs) - margen, max(xs) + margen)
    ax.set_ylim(min(ys) - margen, max(ys) + margen)

    # escribimos el título con el origen, el destino, el tiempo y la
    # distancia total.
    ax.set_title(
        f"{emergencia['nombre']}  →  {hospital['nombre']}\n"
        f"tiempo: {resultado['tiempo_s'] / 60:.2f} min   |   "
        f"distancia: {resultado['distancia_m'] / 1000:.2f} km",
        fontsize=11
    )
    ax.legend(loc="upper right", fontsize=8)
    plt.show()


def h_nodo_x(grafo, lugar):
    # devolvemos la longitud (x) del nodo vial de un lugar.
    return grafo.nodes[lugar["nodo"]]["x"]


def h_nodo_y(grafo, lugar):
    # devolvemos la latitud (y) del nodo vial de un lugar.
    return grafo.nodes[lugar["nodo"]]["y"]


def mapa_mst(grafo, emergencias, hospitales, resultado):
    # dibujamos la visualización 2: el árbol de expansión mínima de
    # prim, siguiendo las rutas reales de las calles.
    fig, ax = _dibujar_base(grafo)

    ids_hospitales = {h["id"] for h in hospitales}

    # definimos un color por tipo de conexión para distinguir cómo
    # conecta prim los hospitales con los puntos de emergencia.
    colores = {
        "hospital - emergencia": "crimson",
        "emergencia - emergencia": "purple",
        "hospital - hospital": "green",
    }
    ya_en_leyenda = set()

    for arista in resultado["aristas"]:

        # clasificamos la conexión según los tipos de sus extremos.
        origen_es_h = arista["origen_id"] in ids_hospitales
        destino_es_h = arista["destino_id"] in ids_hospitales

        if origen_es_h and destino_es_h:
            tipo = "hospital - hospital"
        elif origen_es_h or destino_es_h:
            tipo = "hospital - emergencia"
        else:
            tipo = "emergencia - emergencia"

        # solo agregamos la etiqueta una vez por tipo para que la
        # leyenda no se llene de entradas repetidas.
        etiqueta = tipo if tipo not in ya_en_leyenda else None
        ya_en_leyenda.add(tipo)

        xs, ys = _coordenadas(grafo, arista["ruta"])
        ax.plot(xs, ys, color=colores[tipo], linewidth=3, alpha=0.7,
                zorder=3, label=etiqueta)

    # dibujamos los puntos de emergencia como círculos dorados y los
    # hospitales como cruces azules más grandes.
    ax.scatter(
        [h_nodo_x(grafo, e) for e in emergencias],
        [h_nodo_y(grafo, e) for e in emergencias],
        marker="o", s=90, color="gold", edgecolors="black", zorder=5,
        label="puntos de emergencia"
    )
    ax.scatter(
        [h_nodo_x(grafo, h) for h in hospitales],
        [h_nodo_y(grafo, h) for h in hospitales],
        marker="P", s=260, color="blue", edgecolors="white", zorder=6,
        label="hospitales"
    )

    # escribimos el id de cada punto junto a su marcador. la
    # correspondencia id-nombre se imprime en la consola.
    for lugar in emergencias + hospitales:
        ax.annotate(lugar["id"],
                    (h_nodo_x(grafo, lugar), h_nodo_y(grafo, lugar)),
                    fontsize=8, fontweight="bold",
                    xytext=(5, 5), textcoords="offset points", zorder=7)

    ax.set_title(
        "árbol de expansión mínima (prim)\n"
        f"peso total: {resultado['peso_total_s'] / 60:.2f} min   |   "
        f"conexiones: {len(resultado['aristas'])}",
        fontsize=11
    )
    ax.legend(loc="upper right", fontsize=8)
    plt.show()