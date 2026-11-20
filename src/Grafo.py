import os
import time
import osmnx as ox

CARPETA_PROYECTO = os.path.dirname(os.path.abspath(__file__))

# Ruta del archivo graphml donde guardamos el grafo vial. lo descargamos
# una sola vez y en las siguientes ejecuciones lo leemos desde el disco.
RUTA_GRAFO = os.path.join(CARPETA_PROYECTO, "mapas", "teusaquillo.graphml")

PUNTO_REFERENCIA = (4.6425, -74.0830) # Ubicación central desde donde se construye el mapa
RADIO_ZONA_M = 3500 # Zona radial que abarca el mapa desde el punto de referencia

""" Distancia máxima (en metros) permitida entre un lugar registrado y su
    nodo vial más cercano.
"""
DISTANCIA_MAX_NODO = 300

SERVIDORES_DE_DESCARGA = [
    "https://overpass-api.de/api",
    "https://overpass.kumi.systems/api",
    "https://maps.mail.ru/osm/tools/overpass/api",
]

# Cantidad de intentos por servidor y segundos de espera entre intentos.
INTENTOS_POR_SERVIDOR = 2
ESPERA_ENTRE_INTENTOS = 5


def _descargar_con_reintentos():
    for servidor in SERVIDORES_DE_DESCARGA:
        ox.settings.overpass_url = servidor
        for intento in range(1, INTENTOS_POR_SERVIDOR + 1):
            print(f"  servidor {servidor} (intento {intento}/{INTENTOS_POR_SERVIDOR})...")
            try:
                return ox.graph_from_point(
                    PUNTO_REFERENCIA,
                    dist=RADIO_ZONA_M,
                    network_type="drive"
                )
            except Exception as error:
                """ En caso de no respuesta, se presenta un resumen corto
                    del error y esperamos antes de reintentar."""
                print(f"falló: {type(error).__name__}")
                time.sleep(ESPERA_ENTRE_INTENTOS)

    return None


def cargar_grafo():
    ox.settings.use_cache = True  # Activamos la caché de osmnx para no repetir consultas idénticas
    ox.settings.requests_timeout = 30

    if os.path.exists(RUTA_GRAFO):
        print("cargando el grafo vial guardado en el disco...")
        return ox.load_graphml(RUTA_GRAFO)
    
    print("descargando el grafo vial de openstreetmap (solo ocurre la primera vez)...")
    grafo = _descargar_con_reintentos()

    if grafo is None:
        raise SystemExit(
            "\nno pudimos descargar el grafo vial: ningún servidor respondió.\n"
            "prueba lo siguiente:\n"
            "  1. cambia de red (por ejemplo, datos móviles del celular).\n"
            "  2. desactiva vpn o proxy si los usas.\n"
            "  3. vuelve a intentarlo en unos minutos.\n"
            f"cuando funcione, el grafo quedará guardado en:\n  {RUTA_GRAFO}"
        )

    """ Nos quedamos con la componente fuertemente conexa, es decir, el
        conjunto de nodos entre los que siempre existe ruta en ambos
        sentidos. así evitamos callejones sin salida aislados que harían
        fallar a a* sin necesidad.
    """
    grafo = ox.truncate.largest_component(grafo, strongly=True)

    """ Agregamos la velocidad estimada de cada tramo (speed_kph) y el
        tiempo de recorrido en segundos (travel_time = length / velocidad).
        el tiempo será el peso de las aristas en todos los algoritmos.
    """
    grafo = ox.add_edge_speeds(grafo)
    grafo = ox.add_edge_travel_times(grafo)

    # creamos la carpeta mapas si no existe y guardamos el grafo una
    # única vez para reutilizarlo después.
    os.makedirs(os.path.dirname(RUTA_GRAFO), exist_ok=True)
    ox.save_graphml(grafo, RUTA_GRAFO)
    print("grafo guardado en:", RUTA_GRAFO)

    return grafo