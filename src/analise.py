"""Análise avançada de grafos: ciclos, cadeias, rastreabilidade, métricas."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.grafo import Grafo

INFINITO = float("inf")


def tarjan(grafo: Grafo) -> list[set[str]]:
    """Algoritmo de Tarjan para encontrar componentes fortemente conectadas."""
    indice = 0
    pilha: list[str] = []
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    em_pilha: set[str] = set()
    sccs: list[set[str]] = []

    def strongconnect(v: str) -> None:
        nonlocal indice
        indices[v] = indice
        lowlinks[v] = indice
        indice += 1
        pilha.append(v)
        em_pilha.add(v)

        for w, _ in grafo.vizinhos(v):
            if w not in indices:
                strongconnect(w)
                lowlinks[v] = min(lowlinks[v], lowlinks[w])
            elif w in em_pilha:
                lowlinks[v] = min(lowlinks[v], indices[w])

        if lowlinks[v] == indices[v]:
            scc: set[str] = set()
            while True:
                w = pilha.pop()
                em_pilha.remove(w)
                scc.add(w)
                if w == v:
                    break
            sccs.append(scc)

    for v in grafo.vertices:
        if v not in indices:
            strongconnect(v)

    return sccs


def ciclos_argumentativos(grafo: Grafo) -> list[set[str]]:
    """Retorna os ciclos (argumentações circulares) do grafo."""
    return [scc for scc in tarjan(grafo) if len(scc) > 1]


def kahn(grafo: Grafo) -> list[str] | None:
    """Algoritmo de Kahn para ordenação topológica."""
    graus = grafo.grau_entrada()
    fila: list[str] = [v for v in grafo.vertices if graus[v] == 0]
    ordem: list[str] = []

    while fila:
        u = fila.pop(0)
        ordem.append(u)

        for v, _ in grafo.vizinhos(u):
            graus[v] -= 1
            if graus[v] == 0:
                fila.append(v)

    if len(ordem) != grafo.num_vertices:
        return None

    return ordem


def cadeia_argumentativa(grafo: Grafo) -> list[str] | None:
    """Retorna a cadeia argumentativa (vértices em ordem topológica)."""
    return kahn(grafo)


@dataclass
class CaminhoRastreavel:
    """Caminho com suas frases sustentadoras."""
    conceitos: list[str]
    arestas_frases: list[tuple[str, str, list[str]]]
    custo_total: float

    def __str__(self) -> str:
        """Representação em string do caminho com frases."""
        linhas = [f"Custo total: {self.custo_total:.3f}\n"]

        for i, (origem, destino, frases) in enumerate(self.arestas_frases, 1):
            linhas.append(f"{i}. {origem} → {destino}")
            for frase in frases:
                linhas.append(f"   • {frase}")

        return "\n".join(linhas)


def rastrear_caminho(
    grafo: Grafo, caminho: list[str]
) -> CaminhoRastreavel:
    """Constrói um caminho com rastreabilidade: frases originais de cada aresta."""
    arestas_frases: list[tuple[str, str, list[str]]] = []
    custo_total = 0.0

    for i in range(len(caminho) - 1):
        u, v = caminho[i], caminho[i + 1]
        aresta = grafo.aresta(u, v)
        if aresta is None:
            raise ValueError(f"Aresta inválida: {u} → {v}")

        arestas_frases.append((u, v, aresta.frases))
        custo_total += aresta.peso

    return CaminhoRastreavel(
        conceitos=caminho,
        arestas_frases=arestas_frases,
        custo_total=custo_total,
    )


def forca_argumentativa(grafo: Grafo, caminho: list[str]) -> float:
    """Calcula a força argumentativa de um caminho."""
    if len(caminho) < 2:
        return 1.0

    frequencias = []
    for i in range(len(caminho) - 1):
        aresta = grafo.aresta(caminho[i], caminho[i + 1])
        if aresta:
            frequencias.append(aresta.frequencia)

    if not frequencias:
        return 0.0

    media = sum(frequencias) / len(frequencias)
    max_freq = max(frequencias)

    return media / max_freq


def qualidade_geral(grafo: Grafo) -> dict[str, float | int]:
    """Calcula métricas gerais de qualidade do grafo."""
    V = grafo.num_vertices
    E = grafo.num_arestas
    density = E / (V * (V - 1)) if V > 1 else 0.0
    ciclos = ciclos_argumentativos(grafo)
    eh_aciclico = len(ciclos) == 0

    return {
        "vertices": V,
        "arestas": E,
        "densidade": density,
        "ciclos_detectados": len(ciclos),
        "eh_aciclico": eh_aciclico,
    }


@dataclass
class PropostaAvaliada:
    """Uma proposta com suas métricas."""
    nome: str
    custo: float
    alcancavel: bool
    forca: float | None = None


def ranking_propostas(
    grafo: Grafo,
    tema: str,
    propostas: list[str],
    caminhos: dict[str, list[str]] | None = None,
) -> list[PropostaAvaliada]:
    """Ranking de propostas ordenadas por custo (melhor primeiro)."""
    from src.caminhos import dijkstra, distancia

    distancias, predecessores = dijkstra(grafo, tema)

    resultado = []
    for proposta in propostas:
        custo = distancia(distancias, proposta)
        alcancavel = custo < float("inf")

        forca = None
        if alcancavel and caminhos and proposta in caminhos:
            forca = forca_argumentativa(grafo, caminhos[proposta])

        resultado.append(
            PropostaAvaliada(
                nome=proposta,
                custo=custo,
                alcancavel=alcancavel,
                forca=forca,
            )
        )

    return sorted(resultado, key=lambda p: (not p.alcancavel, p.custo))
