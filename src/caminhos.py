
from __future__ import annotations
 
import heapq
from dataclasses import dataclass, field
 
from src.grafo import Grafo
 
INFINITO = float("inf")
 
 
def dijkstra(grafo: Grafo, origem: str) -> tuple[dict[str, float], dict[str, str | None]]:
    """Distância mínima de `origem` a cada vértice alcançável, com heap."""
    distancias: dict[str, float] = {}
    predecessores: dict[str, str | None] = {}
 
    if origem not in grafo:
        return distancias, predecessores
 
    distancias[origem] = 0.0
    predecessores[origem] = None
 
    fila: list[tuple[float, str]] = [(0.0, origem)]
    finalizados: set[str] = set()
 
    while fila:
        dist_u, u = heapq.heappop(fila)
 
        if u in finalizados:
            continue
        finalizados.add(u)
 
        for v, peso in grafo.vizinhos(u):
            nova_dist = dist_u + peso
            if v not in distancias or nova_dist < distancias[v]:
                distancias[v] = nova_dist
                predecessores[v] = u
                heapq.heappush(fila, (nova_dist, v))
 
    return distancias, predecessores
 
 
def reconstruir_caminho(
    predecessores: dict[str, str | None], origem: str, destino: str
) -> list[str] | None:

    if destino not in predecessores:
        return None
 
    caminho = [destino]
    atual = destino
    while atual != origem:
        anterior = predecessores[atual]
        if anterior is None:
            break
        caminho.append(anterior)
        atual = anterior
 
    caminho.reverse()
    return caminho
 
 
def distancia(distancias: dict[str, float], destino: str) -> float:
    return distancias.get(destino, INFINITO)
 
 
@dataclass
class ResultadoTemaProposta:
 
    tema: str
    melhor_proposta: str | None
    custo: float
    caminho: list[str] | None
    custos_por_proposta: dict[str, float] = field(default_factory=dict)
 
    @property
    def alcancavel(self) -> bool:
        return self.melhor_proposta is not None
 
 
def caminho_tema_proposta(grafo: Grafo, tema: str, propostas: list[str]) -> ResultadoTemaProposta:
    distancias, predecessores = dijkstra(grafo, tema)
 
    custos_por_proposta = {p: distancia(distancias, p) for p in propostas}
 
    melhor_proposta: str | None = None
    melhor_custo = INFINITO
    for proposta, custo in custos_por_proposta.items():
        if custo < melhor_custo:
            melhor_custo = custo
            melhor_proposta = proposta
 
    caminho = None
    if melhor_proposta is not None:
        caminho = reconstruir_caminho(predecessores, tema, melhor_proposta)
 
    return ResultadoTemaProposta(
        tema=tema,
        melhor_proposta=melhor_proposta,
        custo=melhor_custo,
        caminho=caminho,
        custos_por_proposta=custos_por_proposta,
    )
 
 
def orbita(grafo: Grafo, tema: str) -> dict[str, float]:

    distancias, _ = dijkstra(grafo, tema)
    return distancias
 
