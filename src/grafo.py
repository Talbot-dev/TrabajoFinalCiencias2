import os
import time
import osmnx as ox

# guardamos la carpeta donde vive el proyecto para construir las rutas
# de los archivos (grafo, datos) sin depender de desde dónde se ejecute
# el programa.
CARPETA_PROYECTO = os.path.dirname(os.path.abspath(__file__))

# ruta del archivo graphml donde guardamos el grafo vial. lo descargamos
# una sola vez y en las siguientes ejecuciones lo leemos desde el disco.
RUTA_GRAFO = os.path.join(CARPETA_PROYECTO, "mapas", "teusaquillo.graphml")

# centro y radio de la zona que descargamos (latitud, longitud). usamos
# un cuadro de unos 7 km de lado para que queden dentro los 5 hospitales
# y los 20 puntos de emergencia, incluyendo los más alejados del barrio.
CENTRO_ZONA = (4.6425, -74.0830)
RADIO_ZONA_M = 3500

# distancia máxima (en metros) permitida entre un lugar registrado y su
# nodo vial más cercano. si la superamos, consideramos que el lugar está
# fuera de la cobertura del grafo y lo descartamos con un aviso.
DISTANCIA_MAX_NODO_M = 300

# lista de servidores overpass que probamos en orden. si el primero no
# responde, pasamos al siguiente, ya que los servidores públicos a veces
# se saturan o quedan bloqueados según la red desde la que nos conectamos.
SERVIDORES_OVERPASS = [
    "https://overpass-api.de/api",
    "https://overpass.kumi.systems/api",
    "https://maps.mail.ru/osm/tools/overpass/api",
]

# cantidad de intentos por servidor y segundos de espera entre intentos.
INTENTOS_POR_SERVIDOR = 2
ESPERA_ENTRE_INTENTOS_S = 5


def _descargar_con_reintentos():
    # intentamos descargar el grafo recorriendo los servidores uno por
    # uno. en cada servidor hacemos varios intentos antes de rendirnos.
    # devolvemos el grafo si alguno funciona, o none si todos fallan.
    for servidor in SERVIDORES_OVERPASS:

        # cambiamos el servidor que usa osmnx para sus consultas.
        ox.settings.overpass_url = servidor

        for intento in range(1, INTENTOS_POR_SERVIDOR + 1):
            print(f"  servidor {servidor} (intento {intento}/{INTENTOS_POR_SERVIDOR})...")

            try:
                # network_type="drive" trae las calles transitables por
                # vehículos y el grafo resultante es dirigido, de modo
                # que las calles de un solo sentido quedan con una sola
                # dirección.
                return ox.graph_from_point(
                    CENTRO_ZONA,
                    dist=RADIO_ZONA_M,
                    network_type="drive"
                )
            except Exception as error:
                # no detenemos el programa: mostramos un resumen corto
                # del error y esperamos antes de reintentar.
                print(f"    falló: {type(error).__name__}")
                time.sleep(ESPERA_ENTRE_INTENTOS_S)

    return None


def cargar_grafo():
    # activamos la caché de osmnx para no repetir consultas idénticas a
    # internet. usamos un tiempo de espera de 30 segundos para que, si un
    # servidor no responde, pasemos pronto al siguiente.
    ox.settings.use_cache = True
    ox.settings.requests_timeout = 30

    # si el archivo graphml ya existe, lo cargamos desde el disco. así
    # evitamos descargar y procesar la red vial en cada ejecución.
    if os.path.exists(RUTA_GRAFO):
        print("cargando el grafo vial guardado en el disco...")
        return ox.load_graphml(RUTA_GRAFO)

    # si no existe, lo descargamos de openstreetmap probando varios
    # servidores.
    print("descargando el grafo vial de openstreetmap (solo ocurre la primera vez)...")
    grafo = _descargar_con_reintentos()

    # si ningún servidor respondió, explicamos qué puede hacer el usuario
    # y detenemos el programa con un mensaje claro.
    if grafo is None:
        raise SystemExit(
            "\nno pudimos descargar el grafo vial: ningún servidor respondió.\n"
            "prueba lo siguiente:\n"
            "  1. cambia de red (por ejemplo, datos móviles del celular).\n"
            "  2. desactiva vpn o proxy si los usas.\n"
            "  3. vuelve a intentarlo en unos minutos.\n"
            f"cuando funcione, el grafo quedará guardado en:\n  {RUTA_GRAFO}"
        )

    # nos quedamos con la componente fuertemente conexa, es decir, el
    # conjunto de nodos entre los que siempre existe ruta en ambos
    # sentidos. así evitamos callejones sin salida aislados que harían
    # fallar a a* sin necesidad.
    grafo = ox.truncate.largest_component(grafo, strongly=True)

    # agregamos la velocidad estimada de cada tramo (speed_kph) y el
    # tiempo de recorrido en segundos (travel_time = length / velocidad).
    # el tiempo será el peso de las aristas en todos los algoritmos.
    grafo = ox.add_edge_speeds(grafo)
    grafo = ox.add_edge_travel_times(grafo)

    # creamos la carpeta mapas si no existe y guardamos el grafo una
    # única vez para reutilizarlo después.
    os.makedirs(os.path.dirname(RUTA_GRAFO), exist_ok=True)
    ox.save_graphml(grafo, RUTA_GRAFO)
    print("grafo guardado en:", RUTA_GRAFO)

    return grafo