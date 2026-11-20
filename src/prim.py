import heapq
import networkx as nx

from heuristica import a_estrella, mejor_tramo

# guardamos en memoria el mst ya calculado. la clave identifica el
# conjunto de puntos de interés, así que mientras los datos no cambien
# reutilizamos el resultado y no volvemos a ejecutar prim.
_cache_mst = {}


def construir_grafo_auxiliar(grafo, puntos):
    # construimos el grafo auxiliar: un grafo completo cuyos nodos son los
    # puntos de interés (emergencias y hospitales) y cuyas aristas llevan
    # como peso el tiempo de la mejor ruta vial entre cada pareja.
    #
    # como las calles pueden ser de un solo sentido, el tiempo de a hacia
    # b puede ser distinto al de b hacia a. por eso calculamos ambos
    # sentidos con a*. como prim trabaja con aristas no dirigidas, nos
    # quedamos con el sentido de menor tiempo y guardamos su ruta real y
    # su dirección. si solo existe ruta en un sentido, usamos ese.
    auxiliar = nx.Graph()

    for punto in puntos:
        auxiliar.add_node(punto["id"])

    total_parejas = len(puntos) * (len(puntos) - 1) // 2
    parejas_hechas = 0
    parejas_asimetricas = 0
    parejas_sin_ruta = 0

    for i in range(len(puntos)):
        for j in range(i + 1, len(puntos)):

            a = puntos[i]
            b = puntos[j]

            # calculamos la ruta de ida y la de vuelta. el diccionario de
            # caché de heuristica.py evita repetir cálculos ya hechos.
            ida = a_estrella(grafo, a["nodo"], b["nodo"])
            vuelta = a_estrella(grafo, b["nodo"], a["nodo"])

            candidatos = []

            if ida is not None:
                candidatos.append((ida[1], a["id"], b["id"], ida))

            if vuelta is not None:
                candidatos.append((vuelta[1], b["id"], a["id"], vuelta))

            if not candidatos:
                # no hay conexión entre estos dos puntos en ningún
                # sentido: no agregamos arista y seguimos.
                parejas_sin_ruta += 1
            else:
                if ida is not None and vuelta is not None:
                    if abs(ida[1] - vuelta[1]) > 1.0:
                        parejas_asimetricas += 1

                # seleccionamos el sentido de menor tiempo.
                mejor = min(candidatos, key=lambda c: c[0])
                tiempo, origen_id, destino_id, calculo = mejor
                ruta, _, distancia = calculo

                auxiliar.add_edge(
                    a["id"], b["id"],
                    tiempo_s=tiempo,
                    distancia_m=distancia,
                    ruta=ruta,
                    origen_id=origen_id,
                    destino_id=destino_id
                )

            parejas_hechas += 1

            # mostramos el avance cada 50 parejas para que el usuario
            # sepa que el programa sigue trabajando.
            if parejas_hechas % 50 == 0 or parejas_hechas == total_parejas:
                print(f"  parejas calculadas: {parejas_hechas}/{total_parejas}")

    print(f"  parejas con tiempos distintos según el sentido: "
          f"{parejas_asimetricas}")
    print(f"  parejas sin ruta en ningún sentido: {parejas_sin_ruta}")

    return auxiliar


def ejecutar_prim(auxiliar):
    # aplicamos el algoritmo de prim sobre el grafo auxiliar. partimos de
    # un nodo, agregamos a una cola de prioridad todas sus aristas y en
    # cada paso sacamos la más barata que conecte con un nodo nuevo.
    # repetimos hasta que no queden nodos alcanzables.
    #
    # si el grafo auxiliar no es conexo, reiniciamos desde un nodo no
    # visitado y obtenemos un bosque de expansión mínima, sin detener el
    # programa.
    visitados = set()
    aristas_mst = []
    componentes = 0

    for inicio in auxiliar.nodes:

        if inicio in visitados:
            continue

        componentes += 1
        visitados.add(inicio)
        cola = []

        # cargamos en la cola las aristas del nodo inicial. cada
        # elemento es (peso, nodo desde, nodo hacia).
        for vecino, datos in auxiliar[inicio].items():
            heapq.heappush(cola, (datos["tiempo_s"], inicio, vecino))

        while cola:
            peso, desde, hacia = heapq.heappop(cola)

            # si el nodo destino ya está en el árbol, esta arista
            # formaría un ciclo y la ignoramos.
            if hacia in visitados:
                continue

            # aceptamos la arista, marcamos el nodo como visitado y
            # agregamos sus aristas a la cola.
            visitados.add(hacia)
            aristas_mst.append((desde, hacia))

            for vecino, datos in auxiliar[hacia].items():
                if vecino not in visitados:
                    heapq.heappush(cola, (datos["tiempo_s"], hacia, vecino))

    return aristas_mst, componentes


def calcular_mst(grafo, puntos):
    # construimos la clave de la caché con los puntos y sus nodos viales.
    clave = tuple(sorted((p["id"], p["nodo"]) for p in puntos))

    # si ya calculamos el mst para estos mismos puntos, lo reutilizamos.
    if clave in _cache_mst:
        return _cache_mst[clave]

    print(f"construyendo el grafo auxiliar con {len(puntos)} puntos de interés...")
    auxiliar = construir_grafo_auxiliar(grafo, puntos)

    print("ejecutando prim sobre el grafo auxiliar...")
    pares, componentes = ejecutar_prim(auxiliar)

    # recuperamos los datos completos (tiempo, distancia, ruta real y
    # sentido) de cada arista seleccionada por prim.
    aristas = []

    for desde, hacia in pares:
        datos = auxiliar[desde][hacia]
        aristas.append({
            "origen_id": datos["origen_id"],
            "destino_id": datos["destino_id"],
            "tiempo_s": datos["tiempo_s"],
            "distancia_m": datos["distancia_m"],
            "ruta": datos["ruta"]
        })

    peso_total = sum(a["tiempo_s"] for a in aristas)

    # verificamos el resultado comparando el peso total con el que
    # obtiene la implementación de referencia de networkx.
    referencia = nx.minimum_spanning_tree(
        auxiliar, weight="tiempo_s", algorithm="prim"
    ).size(weight="tiempo_s")
    verificado = abs(referencia - peso_total) < 0.01

    resultado = {
        "aristas": aristas,
        "peso_total_s": peso_total,
        "componentes": componentes,
        "verificado": verificado
    }

    _cache_mst[clave] = resultado
    return resultado


def imprimir_mst(resultado, nombres):
    # mostramos cada conexión del árbol con su sentido real, su tiempo
    # y su distancia, y al final el peso total y el número de conexiones.
    print("\nconexiones seleccionadas por prim (en el sentido real de la ruta):")

    for a in resultado["aristas"]:
        origen = nombres[a["origen_id"]]
        destino = nombres[a["destino_id"]]
        print(f"  {a['origen_id']} {origen}  -->  {a['destino_id']} {destino}: "
              f"{a['tiempo_s'] / 60:.2f} min, {a['distancia_m'] / 1000:.2f} km, "
              f"{len(a['ruta'])} intersecciones")

    print(f"\nnúmero de conexiones seleccionadas: {len(resultado['aristas'])}")
    print(f"peso total del árbol: {resultado['peso_total_s'] / 60:.2f} minutos")

    if resultado["componentes"] > 1:
        print(f"aviso: el grafo auxiliar tiene {resultado['componentes']} "
              "componentes separadas, así que obtuvimos un bosque.")

    estado = "OK" if resultado["verificado"] else "REVISAR"
    print(f"verificación contra networkx: {estado}")


# ---------------------------------------------------------------------
# comparación: rutas individuales vs recorrido mst
# ---------------------------------------------------------------------
def _cobertura(grafo, rutas):
    # calculamos qué parte de la red vial recorre un conjunto de rutas.
    # guardamos las intersecciones distintas y las calles distintas, sin
    # importar el sentido, para no contar dos veces la misma calle. la
    # longitud de cada calle distinta se suma una sola vez.
    nodos = set()
    tramos = {}

    for ruta in rutas:
        nodos.update(ruta)

        for u, v in zip(ruta[:-1], ruta[1:]):
            clave = frozenset((u, v))

            if clave not in tramos:
                tramos[clave] = mejor_tramo(grafo, u, v).get("length", 0.0)

    return nodos, sum(tramos.values())


def _rutas_individuales_desde(grafo, base, puntos):
    # calculamos con a* una ruta independiente desde la base hacia cada
    # uno de los demás puntos de interés. sumamos los tiempos y las
    # distancias de todas las rutas, porque cada una se recorre completa
    # y por separado, aunque comparta calles con otra.
    rutas = []
    tiempo = 0.0
    distancia = 0.0
    sin_ruta = 0

    for punto in puntos:

        if punto["id"] == base["id"]:
            continue

        calculo = a_estrella(grafo, base["nodo"], punto["nodo"])

        # si no existe ruta, la contamos aparte y seguimos sin detener
        # el programa.
        if calculo is None:
            sin_ruta += 1
            continue

        ruta, t, d = calculo
        rutas.append(ruta)
        tiempo += t
        distancia += d

    return rutas, tiempo, distancia, sin_ruta


def comparar_individual_vs_mst(grafo, puntos, hospitales, resultado_mst):
    # comparamos dos estrategias para conectar todos los puntos de interés:
    #   a) rutas individuales: desde un hospital base, una ruta a* por
    #      separado hacia cada punto.
    #   b) recorrido mst: la red de prim, donde cada conexión se recorre
    #      una sola vez.
    #
    # para ser justos con las rutas individuales, probamos cada hospital
    # como base y nos quedamos con el que da menor costo total.
    if not hospitales:
        return None

    mejor = None

    for base in hospitales:
        datos = _rutas_individuales_desde(grafo, base, puntos)

        # preferimos la base con menos puntos sin ruta y, a igualdad,
        # la de menor tiempo total.
        clave = (datos[3], datos[1])

        if mejor is None or clave < mejor[0]:
            mejor = (clave, base, datos)

    _, base, (rutas_ind, tiempo_ind, distancia_ind, sin_ruta) = mejor

    # obtenemos las rutas reales de las conexiones del mst.
    rutas_mst = [a["ruta"] for a in resultado_mst["aristas"]]
    tiempo_mst = resultado_mst["peso_total_s"]
    distancia_mst = sum(a["distancia_m"] for a in resultado_mst["aristas"])

    # calculamos la cobertura de cada estrategia sobre el mapa.
    nodos_ind, km_ind = _cobertura(grafo, rutas_ind)
    nodos_mst, km_mst = _cobertura(grafo, rutas_mst)
    total_nodos = grafo.number_of_nodes()

    # contamos los puntos de interés alcanzados por cada estrategia.
    ids_mst = set()
    for a in resultado_mst["aristas"]:
        ids_mst.add(a["origen_id"])
        ids_mst.add(a["destino_id"])

    ahorro = 0.0
    if tiempo_ind > 0:
        ahorro = (tiempo_ind - tiempo_mst) / tiempo_ind * 100

    return {
        "base": base,
        "rutas_individuales": rutas_ind,
        "sin_ruta": sin_ruta,
        "total_nodos_grafo": total_nodos,
        "ahorro_tiempo_pct": ahorro,
        "individual": {
            "tiempo_s": tiempo_ind,
            "distancia_m": distancia_ind,
            "km_calles": km_ind / 1000,
            "nodos": len(nodos_ind),
            "cobertura_pct": len(nodos_ind) / total_nodos * 100,
            "puntos": len(rutas_ind) + 1,
        },
        "mst": {
            "tiempo_s": tiempo_mst,
            "distancia_m": distancia_mst,
            "km_calles": km_mst / 1000,
            "nodos": len(nodos_mst),
            "cobertura_pct": len(nodos_mst) / total_nodos * 100,
            "puntos": len(ids_mst),
        },
    }


def imprimir_comparacion(comp):
    # mostramos una tabla con las métricas de las dos estrategias y una
    # conclusión que explica el resultado.
    ind = comp["individual"]
    mst = comp["mst"]

    print(f"\nbase de las rutas individuales: {comp['base']['nombre']}")
    print("(probamos los hospitales como base y usamos el de menor costo)")

    print("\n" + "-" * 72)
    print(f"{'métrica':<40}{'individuales':>16}{'mst (prim)':>16}")
    print("-" * 72)
    print(f"{'costo total (min)':<40}"
          f"{ind['tiempo_s'] / 60:>16.2f}{mst['tiempo_s'] / 60:>16.2f}")
    print(f"{'distancia total recorrida (km)':<40}"
          f"{ind['distancia_m'] / 1000:>16.2f}{mst['distancia_m'] / 1000:>16.2f}")
    print(f"{'calles distintas recorridas (km)':<40}"
          f"{ind['km_calles']:>16.2f}{mst['km_calles']:>16.2f}")
    print(f"{'intersecciones distintas recorridas':<40}"
          f"{ind['nodos']:>16}{mst['nodos']:>16}")
    print(f"{'cobertura del mapa (%)':<40}"
          f"{ind['cobertura_pct']:>16.2f}{mst['cobertura_pct']:>16.2f}")
    print(f"{'puntos de interés alcanzados':<40}"
          f"{ind['puntos']:>16}{mst['puntos']:>16}")
    print("-" * 72)

    print("\nconclusión:")
    print(f"  el mst cambia el costo total en {comp['ahorro_tiempo_pct']:.1f}% "
          "respecto a las rutas individuales.")

    if mst["cobertura_pct"] >= ind["cobertura_pct"]:
        print("  además, el mst cubre igual o más intersecciones del mapa.")
    else:
        print("  el mst recorre menos intersecciones, pero conecta todos los "
              "puntos con menor costo.")

    print("  nota: el mst usa el menor tiempo entre los dos sentidos de cada "
          "pareja,\n  mientras que las rutas individuales respetan el sentido "
          "real desde la base.")

    if comp["sin_ruta"] > 0:
        print(f"  aviso: {comp['sin_ruta']} puntos no tienen ruta desde la base.")