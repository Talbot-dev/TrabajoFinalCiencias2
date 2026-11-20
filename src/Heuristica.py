import math
import networkx as nx

# guardamos en memoria las rutas ya calculadas. la clave es la pareja
# (nodo origen, nodo destino) y el valor es (ruta, tiempo, distancia),
# o none si no existe ruta. así nunca repetimos un a* con los mismos
# extremos, algo muy útil cuando construimos el grafo auxiliar de prim.
_cache_rutas = {}


def distancia_haversine(lat1, lon1, lat2, lon2):
    # calculamos la distancia en línea recta, en metros, entre dos
    # coordenadas sobre la esfera terrestre. la usamos como base de la
    # heurística porque ninguna ruta por calles puede ser más corta que
    # la línea recta.
    radio_tierra = 6371000

    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    dif_lat = lat2 - lat1
    dif_lon = lon2 - lon1

    a = (
        math.sin(dif_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dif_lon / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return radio_tierra * c


def velocidad_maxima_ms(grafo):
    # obtenemos la velocidad máxima del grafo en metros por segundo. la
    # calculamos una sola vez y la guardamos dentro del propio grafo,
    # para no recorrer todas las aristas en cada ejecución de a*.
    if "velocidad_max_ms" not in grafo.graph:

        velocidades = [
            datos["speed_kph"]
            for _, _, datos in grafo.edges(data=True)
            if "speed_kph" in datos
        ]

        if not velocidades:
            raise ValueError("el grafo no contiene velocidades registradas.")

        # dividimos entre 3.6 para pasar de km/h a m/s.
        grafo.graph["velocidad_max_ms"] = max(velocidades) / 3.6

    return grafo.graph["velocidad_max_ms"]


def mejor_tramo(grafo, u, v):
    # entre dos nodos puede haber varias calles paralelas (el grafo es
    # un multidigraph). seleccionamos la de menor tiempo, que es la misma
    # que elige a* cuando usa travel_time como peso.
    return min(grafo[u][v].values(), key=lambda datos: datos["travel_time"])


def resumen_ruta(grafo, ruta):
    # recorremos la ruta tramo por tramo sumando el tiempo (segundos) y
    # la longitud (metros) de cada calle utilizada.
    tiempo_total = 0.0
    distancia_total = 0.0

    for u, v in zip(ruta[:-1], ruta[1:]):
        tramo = mejor_tramo(grafo, u, v)
        tiempo_total += tramo["travel_time"]
        distancia_total += tramo.get("length", 0.0)

    return tiempo_total, distancia_total


def a_estrella(grafo, origen, destino):
    # si ya calculamos esta ruta antes, devolvemos el resultado guardado.
    clave = (origen, destino)

    if clave in _cache_rutas:
        return _cache_rutas[clave]

    # guardamos las coordenadas del destino y la velocidad máxima para
    # usarlas dentro de la heurística.
    lat_destino = grafo.nodes[destino]["y"]
    lon_destino = grafo.nodes[destino]["x"]
    velocidad_max = velocidad_maxima_ms(grafo)

    # definimos la heurística: el tiempo que tardaríamos en recorrer la
    # línea recta hasta el destino a la velocidad máxima del grafo. es
    # admisible porque nunca sobreestima el tiempo real, y por eso a*
    # garantiza encontrar la ruta de menor tiempo.
    def heuristica(nodo_actual, nodo_objetivo):
        distancia = distancia_haversine(
            grafo.nodes[nodo_actual]["y"],
            grafo.nodes[nodo_actual]["x"],
            lat_destino,
            lon_destino
        )
        return distancia / velocidad_max

    try:
        # calculamos la ruta de menor tiempo con a*. usamos travel_time
        # como peso y, como el grafo es dirigido, respetamos el sentido
        # de las calles.
        ruta = nx.astar_path(
            grafo,
            source=origen,
            target=destino,
            heuristic=heuristica,
            weight="travel_time"
        )
        tiempo, distancia = resumen_ruta(grafo, ruta)
        resultado = (ruta, tiempo, distancia)

    except (nx.NetworkXNoPath, nx.NodeNotFound):
        # si no existe ruta no detenemos el programa: guardamos none
        # y quien nos llamó decide qué hacer.
        resultado = None

    _cache_rutas[clave] = resultado
    return resultado


def tiempo_dijkstra(grafo, origen, destino):
    # calculamos el tiempo mínimo con dijkstra para verificar que a*
    # encontró el mismo costo. si no hay ruta devolvemos none.
    try:
        return nx.shortest_path_length(
            grafo, origen, destino, weight="travel_time"
        )
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None