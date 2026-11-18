import osmnx as ox
import networkx as nx

def grafo():
    #Aproximadamente la estación universidad nacional, NQS con calle 45
    punto_central = (4.6358, -74.0794) 
    dist = 2000 
    mapa = ox.graph_from_point(punto_central, dist=dist, network_type='drive')
    mapa_tiempos = ox.add_edge_travel_times(ox.add_edge_speeds(mapa))
    return mapa_tiempos

def prueba_tiempo(grafo):
    print(f"- Nodos (intersecciones): {grafo.number_of_nodes()}")
    print(f"- Aristas (calles): {grafo.number_of_edges()}")
    
    lat_origen, lon_origen = 4.6358, -74.0794
    lat_destino, lon_destino = 4.6367632, -74.0650575
    
    nodo_origen = ox.distance.nearest_nodes(grafo, X=lon_origen, Y=lat_origen)
    nodo_destino = ox.distance.nearest_nodes(grafo, X=lon_destino, Y=lat_destino)
    
    print(f"El origen corresponde al nodo intersección: {nodo_origen}")
    print(f"El destino corresponde al nodo intersección: {nodo_destino}")
    
    ruta = nx.shortest_path(grafo, source=nodo_origen, target=nodo_destino, weight='travel_time')
    
    tiempo_en_segundos = nx.path_weight(grafo, ruta, weight='travel_time')
    tiempo_en_minutos = (tiempo_en_segundos / 60 ) * 1.6
    
    print(f"--- RESULTADO ---")
    print(f"Cantidad de esquinas/intersecciones a cruzar: {len(ruta)}")
    print(f"Tiempo total de viaje: {tiempo_en_minutos:.2f} minutos")