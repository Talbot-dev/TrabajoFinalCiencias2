from grafo import cargar_grafo
from lugares import preparar_lugares
from rutas import (
    hospitales_disponibles,
    ambulancia_de_hospital,
    evaluar_hospitales,
    verificar_con_dijkstra,
    nombres_calles,
)
from prim import (
    calcular_mst,
    imprimir_mst,
    comparar_individual_vs_mst,
    imprimir_comparacion,
)
from visualizacion import mapa_ruta_astar, mapa_mst


def titulo(texto):
    # imprimimos un título entre líneas para separar las secciones.
    print("\n" + "=" * 70)
    print(texto)
    print("=" * 70)


def pedir_opcion(mensaje, minimo, maximo):
    # pedimos un número hasta que el usuario escriba uno válido dentro
    # del rango. así evitamos errores por entradas incorrectas.
    while True:
        texto = input(mensaje).strip()

        if texto.isdigit() and minimo <= int(texto) <= maximo:
            return int(texto)

        print(f"  opción inválida: escribe un número entre {minimo} y {maximo}.")


def pedir_si_no(mensaje):
    # pedimos una respuesta s/n y la validamos.
    while True:
        texto = input(mensaje).strip().lower()

        if texto in ("s", "si", "sí"):
            return True
        if texto in ("n", "no"):
            return False

        print("  escribe s o n.")


def texto_disponibilidad(hospital):
    # armamos el texto de disponibilidad dejando claro si el dato es
    # simulado, para no hacer pasar datos de prueba como reales.
    estado = "disponible" if hospital.get("disponible_recibir") else "NO disponible"

    if hospital.get("disponibilidad_simulada"):
        estado += " (dato simulado/configurable, no es información real)"

    return estado


def seleccionar_emergencia(emergencias):
    # mostramos todos los puntos de emergencia con su número y nombre.
    titulo("SELECCIÓN DEL PUNTO DE EMERGENCIA")

    for i, punto in enumerate(emergencias, start=1):
        print(f"  {i:>2}. {punto['nombre']}")

    opcion = pedir_opcion("\nelige el punto de emergencia: ", 1, len(emergencias))
    return emergencias[opcion - 1]


def seleccionar_destino(grafo, emergencia, hospitales):
    # preguntamos al usuario si quiere el hospital más rápido o uno
    # específico, y devolvemos el resultado de la ruta elegida.
    titulo("SELECCIÓN DEL DESTINO MÉDICO")

    print("¿a dónde desea dirigirse?")
    print("  1. cualquier centro de atención médica disponible "
          "(el sistema busca la ruta más rápida)")
    print("  2. seleccionar un hospital específico")

    modo = pedir_opcion("\nelige una opción: ", 1, 2)

    if modo == 1:
        # comparamos con a* los tiempos hacia todos los hospitales
        # disponibles y elegimos el menor.
        candidatos = hospitales_disponibles(hospitales)

        if not candidatos:
            print("\nno hay hospitales disponibles en este momento.")
            return None

        resultados, descartados = evaluar_hospitales(grafo, emergencia, candidatos)

        print("\ncomparación de tiempos con a* (de menor a mayor):")
        for r in resultados:
            print(f"  - {r['hospital']['nombre']}: {r['tiempo_s'] / 60:.2f} min, "
                  f"{r['distancia_m'] / 1000:.2f} km")

        for h in descartados:
            print(f"  - {h['nombre']}: sin ruta (descartado)")

        if not resultados:
            print("\nningún hospital tiene ruta desde este punto.")
            return None

        return resultados[0]

    # modo 2: mostramos la lista de hospitales para que el usuario elija.
    print("\nhospitales registrados:")
    for i, h in enumerate(hospitales, start=1):
        print(f"  {i}. {h['nombre']} - {texto_disponibilidad(h)}")

    opcion = pedir_opcion("\nelige un hospital: ", 1, len(hospitales))
    hospital = hospitales[opcion - 1]

    # no despachamos a un hospital que no puede recibir pacientes.
    if not hospital.get("disponible_recibir"):
        print(f"\n{hospital['nombre']} no está disponible para recibir pacientes.")
        return None

    # calculamos solamente la ruta hacia el hospital elegido.
    resultados, _ = evaluar_hospitales(grafo, emergencia, [hospital])

    if not resultados:
        print(f"\nno existe ruta desde la emergencia hasta {hospital['nombre']}.")
        return None

    return resultados[0]


def imprimir_resumen(grafo, emergencia, resultado, ambulancias):
    # mostramos el resumen final de la consulta.
    hospital = resultado["hospital"]
    ambulancia = ambulancia_de_hospital(hospital, ambulancias)
    verificacion = "OK" if verificar_con_dijkstra(grafo, emergencia, resultado) \
        else "REVISAR"

    titulo("RESUMEN DE LA CONSULTA")

    print(f"punto de emergencia: {emergencia['nombre']}")
    print(f"hospital de destino: {hospital['nombre']}")
    print("algoritmo: a* (peso = tiempo de recorrido)")
    print(f"tiempo estimado: {resultado['tiempo_s'] / 60:.2f} minutos")
    print(f"distancia total: {resultado['distancia_m'] / 1000:.2f} kilómetros")
    print(f"estado de disponibilidad: {texto_disponibilidad(hospital)}")

    if ambulancia is not None:
        estado_amb = "disponible" if ambulancia["disponible"] else "ocupada"
        simulada = " (simulada)" if ambulancia.get("simulada") else ""
        print(f"ambulancia asociada al hospital: {ambulancia['nombre']} - "
              f"{estado_amb}{simulada}")

    print(f"verificación con dijkstra: {verificacion}")
    print(f"\nruta encontrada: {len(resultado['ruta'])} intersecciones")
    print("calles principales: " + " -> ".join(nombres_calles(grafo, resultado["ruta"])))


def consultar_emergencia(grafo, emergencias, hospitales, ambulancias):
    # ejecutamos una consulta completa: emergencia, destino, resumen y mapa.
    emergencia = seleccionar_emergencia(emergencias)
    resultado = seleccionar_destino(grafo, emergencia, hospitales)

    if resultado is None:
        return

    imprimir_resumen(grafo, emergencia, resultado, ambulancias)

    # dibujamos el mapa solo si el usuario lo pide, para no abrir
    # ventanas innecesarias.
    if pedir_si_no("\n¿deseas ver el mapa de la ruta? (s/n): "):
        otros = [h for h in hospitales if h["id"] != resultado["hospital"]["id"]]
        mapa_ruta_astar(grafo, emergencia, resultado, otros)


def ver_mst(grafo, emergencias, hospitales):
    # calculamos (o reutilizamos) el mst sobre todos los puntos de interés.
    titulo("ÁRBOL DE EXPANSIÓN MÍNIMA (PRIM)")

    puntos = emergencias + hospitales
    nombres = {p["id"]: p["nombre"] for p in puntos}

    print(f"puntos de interés: {len(puntos)} "
          f"({len(emergencias)} emergencias + {len(hospitales)} hospitales)")

    resultado = calcular_mst(grafo, puntos)
    imprimir_mst(resultado, nombres)

    if pedir_si_no("\n¿deseas ver el mapa del árbol? (s/n): "):
        mapa_mst(grafo, emergencias, hospitales, resultado)


def ver_comparacion(grafo, emergencias, hospitales):
    # comparamos las rutas individuales contra el recorrido del mst. el
    # mst se reutiliza de la caché si ya lo calculamos antes.
    titulo("COMPARACIÓN: RUTAS INDIVIDUALES vs RECORRIDO MST")

    puntos = emergencias + hospitales
    print(f"puntos de interés: {len(puntos)}")

    resultado = calcular_mst(grafo, puntos)
    comparacion = comparar_individual_vs_mst(grafo, puntos, hospitales, resultado)

    if comparacion is None:
        print("no hay hospitales para usar como base.")
        return

    imprimir_comparacion(comparacion)


def main():
    titulo("SISTEMA DE RUTAS DE EMERGENCIA - TEUSAQUILLO, BOGOTÁ")

    # cargamos el grafo vial y luego los lugares asociados a sus nodos.
    grafo = cargar_grafo()
    print(f"nodos (intersecciones): {grafo.number_of_nodes()}")
    print(f"aristas (calles): {grafo.number_of_edges()}")

    hospitales, emergencias, ambulancias = preparar_lugares(grafo)

    # mostramos el origen de las coordenadas para que podamos verificarlas.
    print(f"\nhospitales cargados: {len(hospitales)}")
    for h in hospitales:
        print(f"  {h['id']} {h['nombre']} - coordenadas: {h['estado_coordenadas']}")

    print(f"puntos de emergencia cargados: {len(emergencias)}")
    pendientes = [e for e in emergencias
                  if e["estado_coordenadas"] != "dada_por_usuario"]
    for e in pendientes:
        print(f"  {e['id']} {e['nombre']} - coordenadas: {e['estado_coordenadas']}")

    if not hospitales or not emergencias:
        print("\nfaltan hospitales o puntos de emergencia con coordenadas "
              "válidas. revisa datos/lugares.json.")
        return

    # menú principal: permite hacer varias consultas sin reiniciar.
    while True:
        titulo("MENÚ PRINCIPAL")
        print("  1. consultar una emergencia (a*)")
        print("  2. ver el árbol de expansión mínima (prim)")
        print("  3. comparar rutas individuales vs mst")
        print("  4. salir")

        opcion = pedir_opcion("\nelige una opción: ", 1, 4)

        if opcion == 1:
            consultar_emergencia(grafo, emergencias, hospitales, ambulancias)
        elif opcion == 2:
            ver_mst(grafo, emergencias, hospitales)
        elif opcion == 3:
            ver_comparacion(grafo, emergencias, hospitales)
        else:
            print("\nhasta pronto.")
            break


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nprograma finalizado.")