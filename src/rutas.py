from heuristica import a_estrella, mejor_tramo, tiempo_dijkstra


def hospitales_disponibles(hospitales):
    # seleccionamos los hospitales marcados como disponibles para
    # recibir pacientes. este dato es configurable en lugares.json y,
    # si no tenemos información real, es simulado.
    return [h for h in hospitales if h.get("disponible_recibir")]


def ambulancia_de_hospital(hospital, ambulancias):
    # buscamos la ambulancia asignada al hospital. devolvemos none si
    # el hospital no tiene ninguna registrada.
    for ambulancia in ambulancias:
        if ambulancia["hospital_id"] == hospital["id"]:
            return ambulancia

    return None


def evaluar_hospitales(grafo, emergencia, hospitales):
    # calculamos con a* la ruta de menor tiempo desde el punto de
    # emergencia hasta cada hospital candidato. la ambulancia parte de
    # la emergencia y se dirige al hospital.
    resultados = []
    descartados = []

    for hospital in hospitales:
        calculo = a_estrella(grafo, emergencia["nodo"], hospital["nodo"])

        # si no existe ruta, descartamos ese hospital y seguimos con el
        # siguiente sin detener el programa.
        if calculo is None:
            descartados.append(hospital)
            continue

        ruta, tiempo, distancia = calculo
        resultados.append({
            "hospital": hospital,
            "ruta": ruta,
            "tiempo_s": tiempo,
            "distancia_m": distancia
        })

    # ordenamos de menor a mayor tiempo, de modo que el primer elemento
    # sea el hospital más rápido de alcanzar.
    resultados.sort(key=lambda r: r["tiempo_s"])

    return resultados, descartados


def verificar_con_dijkstra(grafo, emergencia, resultado):
    # comparamos el tiempo de a* con el de dijkstra. si coinciden, la
    # heurística no nos hizo perder la ruta óptima.
    t_dijkstra = tiempo_dijkstra(
        grafo, emergencia["nodo"], resultado["hospital"]["nodo"]
    )

    if t_dijkstra is None:
        return False

    return abs(t_dijkstra - resultado["tiempo_s"]) < 0.001


def nombres_calles(grafo, ruta):
    # recorremos la ruta y obtenemos el nombre de la calle de cada
    # tramo. unimos los tramos consecutivos con el mismo nombre para que
    # la lista sea corta y fácil de leer.
    nombres = []

    for u, v in zip(ruta[:-1], ruta[1:]):
        nombre = mejor_tramo(grafo, u, v).get("name")

        if nombre is None:
            nombre = "(calle sin nombre)"
        elif isinstance(nombre, list):
            nombre = " / ".join(nombre)

        if not nombres or nombres[-1] != nombre:
            nombres.append(str(nombre))

    return nombres