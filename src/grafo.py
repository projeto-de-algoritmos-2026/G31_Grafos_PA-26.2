"""
Grafo direcionado com pesos, em lista de adjacência.

Implementado do zero para a disciplina de Projeto de Algoritmos (UnB/FGA).
Nenhuma biblioteca de grafos é utilizada em nenhum ponto deste projeto —
apenas estruturas da biblioteca padrão do Python.

MODELAGEM DO DOMÍNIO
--------------------
Cada vértice é um conceito extraído da redação (ex.: "identidade cultural").
Cada aresta u -> v significa "u leva a / justifica v", direção obtida da
análise sintática de dependências.

O peso da aresta é o INVERSO da sua frequência: uma relação que o autor
afirma três vezes ao longo do texto está bem sustentada e, portanto, é
barata de percorrer. Assim o caminho mínimo do Dijkstra é o argumento
mais bem sustentado, não apenas o mais curto em número de saltos.
Como a frequência é sempre >= 1, o peso está sempre em (0, 1] — positivo,
que é a condição de validade do algoritmo de Dijkstra.

Cada aresta guarda também as frases originais que a geraram, o que permite
a rastreabilidade no aplicativo: clicar numa aresta mostra de onde ela veio.
"""

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

    def __repr__(self) -> str:  # pragma: no cover - only for debugging
        return (
            f"Aresta({self.origem!r} -> {self.destino!r}, "
            f"freq={self.frequencia}, peso={self.peso:.3f})"
        )


class Grafo:
    """
    Grafo direcionado com pesos, em lista de adjacência.

    A lista de adjacência é um dicionário de dicionários:

        {origem: {destino: Aresta}}

    Essa escolha dá acesso O(1) a uma aresta específica — necessário para
    acumular a frequência quando a mesma relação reaparece no texto — sem
    abrir mão da iteração eficiente sobre a vizinhança, que é o que os
    algoritmos de percurso precisam.

    Custos (V = nº de vértices, E = nº de arestas):
        adicionar_vertice ....... O(1)
        adicionar_aresta ........ O(1)
        vizinhos ................ O(grau de saída)
        arestas ................. O(E)
        grau_entrada ............ O(V + E)
        transposto .............. O(V + E)
    """

    def __init__(self) -> None:
        self._adj: dict[str, dict[str, Aresta]] = {}

    # ------------------------------------------------------------------
    # Construção
    # ------------------------------------------------------------------

    def adicionar_vertice(self, v: str) -> None:
        """Insere um vértice isolado. Não faz nada se ele já existir."""
        self._adj.setdefault(v, {})

    def adicionar_aresta(self, u: str, v: str, frase: str | None = None) -> Aresta:
        """
        Registra uma ocorrência da relação u -> v.

        Se a aresta já existir, apenas incrementa a frequência (e portanto
        reduz o peso). Vértices ainda não vistos são criados.
        Laços (u == v) são rejeitados: um conceito não justifica a si mesmo,
        e um laço criaria um componente fortemente conectado espúrio.
        """
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

    # ------------------------------------------------------------------
    # Consulta
    # ------------------------------------------------------------------

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
        """
        Grau de entrada de cada vértice. O(V + E).

        Usado pelo algoritmo de Kahn (ordenação topológica): os vértices de
        grau de entrada zero são aqueles que nada causa, e por isso abrem a
        cadeia argumentativa.
        """
        graus = {v: 0 for v in self._adj}
        for aresta in self.arestas():
            graus[aresta.destino] += 1
        return graus

    def transposto(self) -> "Grafo":
        """
        Grafo com todas as arestas invertidas. O(V + E).

        Preserva frequências e frases, então o peso de cada aresta é o mesmo
        do grafo original.
        """
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

    # ------------------------------------------------------------------
    # Conveniências
    # ------------------------------------------------------------------

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

    def __repr__(self) -> str:  # pragma: no cover - only for debugging
        return f"Grafo({self.num_vertices} vértices, {self.num_arestas} arestas)"
