"""Grafo direcionado com pesos, em lista de adjacência."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Iterator


@dataclass
class Aresta:
    """Uma relação causal entre dois conceitos."""
    origem: str
    destino: str
    frequencia: int = 0
    frases: list[str] = field(default_factory=list)

    @property
    def peso(self) -> float:
        """Custo de percorrer a relação: 1 / frequência."""
        if self.frequencia <= 0:
            raise ValueError(
                f"aresta {self.origem} -> {self.destino} sem ocorrência registrada"
            )
        return 1.0 / self.frequencia

    def registrar(self, frase: str | None = None) -> None:
        """Contabiliza mais uma ocorrência desta relação no texto."""
        self.frequencia += 1
        if frase is not None:
            self.frases.append(frase)

    def __repr__(self) -> str:
        return (
            f"Aresta({self.origem!r} -> {self.destino!r}, "
            f"freq={self.frequencia}, peso={self.peso:.3f})"
        )


class Grafo:
    """Grafo direcionado com pesos, em lista de adjacência."""
    def __init__(self) -> None:
        self._adj: dict[str, dict[str, Aresta]] = {}

    def adicionar_vertice(self, v: str) -> None:
        """Insere um vértice isolado. Não faz nada se ele já existir."""
        self._adj.setdefault(v, {})

    def adicionar_aresta(self, u: str, v: str, frase: str | None = None) -> Aresta:
        """Registra uma ocorrência da relação u -> v."""
        if u == v:
            raise ValueError(f"laço não permitido: {u!r} -> {v!r}")

        self.adicionar_vertice(u)
        self.adicionar_vertice(v)

        aresta = self._adj[u].get(v)
        if aresta is None:
            aresta = Aresta(origem=u, destino=v)
            self._adj[u][v] = aresta
        aresta.registrar(frase)
        return aresta

    @property
    def vertices(self) -> list[str]:
        """Todos os vértices, em ordem de inserção."""
        return list(self._adj)

    @property
    def num_vertices(self) -> int:
        return len(self._adj)

    @property
    def num_arestas(self) -> int:
        return sum(len(destinos) for destinos in self._adj.values())

    def vizinhos(self, u: str) -> Iterator[tuple[str, float]]:
        """Sucessores de u, como pares (destino, peso)."""
        for destino, aresta in self._adj.get(u, {}).items():
            yield destino, aresta.peso

    def sucessores(self, u: str) -> Iterator[str]:
        """Sucessores de u, ignorando os pesos."""
        return iter(self._adj.get(u, {}))

    def arestas(self) -> Iterator[Aresta]:
        """Todas as arestas do grafo."""
        for destinos in self._adj.values():
            yield from destinos.values()

    def aresta(self, u: str, v: str) -> Aresta | None:
        """A aresta u -> v, ou None se não existir."""
        return self._adj.get(u, {}).get(v)

    def grau_entrada(self) -> dict[str, int]:
        """Grau de entrada de cada vértice."""
        graus = {v: 0 for v in self._adj}
        for aresta in self.arestas():
            graus[aresta.destino] += 1
        return graus

    def transposto(self) -> "Grafo":
        """Grafo com todas as arestas invertidas."""
        t = Grafo()
        for v in self._adj:
            t.adicionar_vertice(v)
        for aresta in self.arestas():
            nova = t._adj[aresta.destino].get(aresta.origem)
            if nova is None:
                nova = Aresta(origem=aresta.destino, destino=aresta.origem)
                t._adj[aresta.destino][aresta.origem] = nova
            nova.frequencia = aresta.frequencia
            nova.frases = list(aresta.frases)
        return t

    @classmethod
    def de_pares(cls, pares: Iterable[tuple[str, str]]) -> "Grafo":
        """Constrói um grafo a partir de uma sequência de pares (u, v)."""
        g = cls()
        for u, v in pares:
            g.adicionar_aresta(u, v)
        return g

    def __contains__(self, v: object) -> bool:
        return v in self._adj

    def __len__(self) -> int:
        return len(self._adj)

    def __iter__(self) -> Iterator[str]:
        return iter(self._adj)

    def __repr__(self) -> str:
        return f"Grafo({self.num_vertices} vértices, {self.num_arestas} arestas)"
