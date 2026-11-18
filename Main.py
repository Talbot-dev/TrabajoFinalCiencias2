from Heuristica import a_estrella
from Arbol_recubridor_minimo import prim
from Mapa import grafo, prueba_tiempo

def optimizador():
    prueba_tiempo(grafo())
    a_estrella()
    prim()

if __name__ == "__main__":
    optimizador()