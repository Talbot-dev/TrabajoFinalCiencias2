import json
import os
import time
import osmnx as ox

from grafo import CARPETA_PROYECTO, DISTANCIA_MAX_NODO_M

# archivo con los hospitales, puntos de emergencia y ambulancias. para
# agregar lugares nuevos solo modificamos este archivo.
RUTA_LUGARES = os.path.join(CARPETA_PROYECTO, "datos", "lugares.json")

# archivo donde guardamos las coordenadas obtenidas por geocodificación,
# para no consultar internet cada vez que ejecutamos el programa.
RUTA_CACHE = os.path.join(CARPETA_PROYECTO, "datos", "coordenadas_cache.json")


def _leer_json(ruta, valor_por_defecto):
    # si el archivo no existe devolvemos el valor por defecto, y si
    # existe lo leemos como utf-8 para conservar tildes y eñes.
    if not os.path.exists(ruta):
        return valor_por_defecto

    with open(ruta, "r", encoding="utf-8") as archivo:
        return json.load(archivo)


def _guardar_json(ruta, datos):
    # guardamos el diccionario como json legible (con sangría) y sin
    # escapar los caracteres especiales del español.
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, ensure_ascii=False, indent=2)


def _geocodificar(lugar):
    # armamos una lista de consultas de la más específica a la más
    # general: primero la consulta escrita a mano en el json (si existe),
    # luego el nombre del lugar y por último su dirección.
    consultas = []

    if lugar.get("consulta"):
        consultas.append(lugar["consulta"])

    consultas.append(f"{lugar['nombre']}, Bogotá, Colombia")

    if lugar.get("direccion") and lugar["direccion"] != "pendiente":
        consultas.append(f"{lugar['direccion']}, Bogotá, Colombia")

    # probamos cada consulta hasta que el servicio de nominatim devuelva
    # un resultado. esperamos un segundo entre consultas porque el
    # servicio público limita la cantidad de peticiones por segundo.
    for consulta in consultas:
        try:
            latitud, longitud = ox.geocode(consulta)
            time.sleep(1)
            return latitud, longitud, consulta
        except Exception:
            time.sleep(1)

    # si ninguna consulta funcionó no inventamos nada: devolvemos none y
    # el programa avisará que ese lugar quedó sin coordenadas.
    return None


def _completar_coordenadas(lugares, cache):
    # recorremos los lugares y completamos las coordenadas faltantes.
    # devolvemos true si agregamos algo nuevo a la caché.
    cache_modificada = False

    for lugar in lugares:

        # si el lugar ya trae latitud y longitud en el json, las
        # respetamos tal como están.
        if lugar.get("latitud") is not None and lugar.get("longitud") is not None:
            continue

        # si ya geocodificamos este lugar en una ejecución anterior,
        # reutilizamos las coordenadas guardadas en la caché.
        if lugar["id"] in cache:
            lugar["latitud"] = cache[lugar["id"]]["latitud"]
            lugar["longitud"] = cache[lugar["id"]]["longitud"]
            lugar["estado_coordenadas"] = "geocodificada (verificar)"
            continue

        # en caso contrario las buscamos por geocodificación y las
        # guardamos en la caché para la próxima vez.
        print(f"  geocodificando: {lugar['nombre']}...")
        resultado = _geocodificar(lugar)

        if resultado is None:
            print("    no se encontró. completa latitud y longitud "
                  f"de {lugar['id']} manualmente en lugares.json")
            lugar["estado_coordenadas"] = "sin coordenadas"
            continue

        latitud, longitud, consulta = resultado
        lugar["latitud"] = latitud
        lugar["longitud"] = longitud
        lugar["estado_coordenadas"] = "geocodificada (verificar)"
        cache[lugar["id"]] = {
            "latitud": latitud,
            "longitud": longitud,
            "consulta": consulta
        }
        cache_modificada = True

    return cache_modificada


def _asignar_nodos(grafo, lugares):
    # separamos los lugares que sí tienen coordenadas de los que no.
    con_coordenadas = [
        l for l in lugares
        if l.get("latitud") is not None and l.get("longitud") is not None
    ]

    if not con_coordenadas:
        return []

    # buscamos todos los nodos más cercanos en una sola llamada, que es
    # más rápido que hacerlo lugar por lugar. recordamos que x es la
    # longitud y y es la latitud.
    nodos, distancias = ox.distance.nearest_nodes(
        grafo,
        X=[l["longitud"] for l in con_coordenadas],
        Y=[l["latitud"] for l in con_coordenadas],
        return_dist=True
    )

    validos = []

    for lugar, nodo, distancia in zip(con_coordenadas, nodos, distancias):

        # si el nodo más cercano queda muy lejos, el lugar está fuera de
        # la cobertura del grafo y no podemos calcular rutas confiables.
        if distancia > DISTANCIA_MAX_NODO_M:
            print(f"  aviso: {lugar['nombre']} queda a {distancia:.0f} m de la "
                  "calle más cercana (fuera de cobertura). se descarta.")
            continue

        lugar["nodo"] = int(nodo)
        lugar["distancia_al_nodo_m"] = float(distancia)
        validos.append(lugar)

    return validos


def preparar_lugares(grafo):
    # leemos el archivo de datos. si no existe, avisamos con un error
    # claro porque sin él no hay nada que calcular.
    datos = _leer_json(RUTA_LUGARES, None)

    if datos is None:
        raise FileNotFoundError(f"no encontramos el archivo {RUTA_LUGARES}")

    hospitales = datos["hospitales"]
    emergencias = datos["puntos_emergencia"]
    ambulancias = datos.get("ambulancias", [])

    # completamos las coordenadas que falten usando la caché o la
    # geocodificación controlada.
    cache = _leer_json(RUTA_CACHE, {})

    print("verificando coordenadas de los lugares...")
    cache_modificada = _completar_coordenadas(hospitales + emergencias, cache)

    if cache_modificada:
        _guardar_json(RUTA_CACHE, cache)

    # asociamos cada lugar con su nodo vial y descartamos los que no
    # tienen coordenadas o están fuera de la cobertura del grafo.
    hospitales = _asignar_nodos(grafo, hospitales)
    emergencias = _asignar_nodos(grafo, emergencias)

    # conectamos cada ambulancia con su hospital. si el hospital fue
    # descartado, descartamos también su ambulancia.
    hospitales_por_id = {h["id"]: h for h in hospitales}
    ambulancias_validas = []

    for ambulancia in ambulancias:
        hospital = hospitales_por_id.get(ambulancia["hospital_id"])

        if hospital is None:
            continue

        # la ubicación inicial de la ambulancia es el nodo de su hospital.
        ambulancia["nodo"] = hospital["nodo"]
        ambulancias_validas.append(ambulancia)

    return hospitales, emergencias, ambulancias_validas