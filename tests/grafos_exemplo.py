
from src.grafo import Grafo


def dag_simples() -> Grafo:
    return Grafo.de_pares([("a", "b"), ("b", "c"), ("a", "c")])


DAG_SIMPLES_SCCS = [{"a"}, {"b"}, {"c"}]
DAG_SIMPLES_ORDEM = ["a", "b", "c"]


def com_ciclo() -> Grafo:
    return Grafo.de_pares([("a", "b"), ("b", "c"), ("c", "a"), ("c", "d")])


COM_CICLO_SCCS = [{"a", "b", "c"}, {"d"}]
COM_CICLO_ORDEM_CONDENSADA = [{"a", "b", "c"}, {"d"}]


def cormen_22_9() -> Grafo:
    return Grafo.de_pares([
        ("a", "b"),
        ("b", "c"), ("b", "e"), ("b", "f"),
        ("c", "d"), ("c", "g"),
        ("d", "c"), ("d", "h"),
        ("e", "a"), ("e", "f"),
        ("f", "g"),
        ("g", "f"), ("g", "h"),
    ])


CORMEN_SCCS = [{"a", "b", "e"}, {"c", "d"}, {"f", "g"}, {"h"}]


def pesos_dijkstra() -> Grafo:
    g = Grafo()
    for u, v, freq in [
        ("s", "a", 4),
        ("s", "b", 1),
        ("a", "b", 2),
        ("a", "c", 1),
        ("b", "c", 4),
        ("c", "d", 2),
    ]:
        for _ in range(freq):
            g.adicionar_aresta(u, v)
    return g


PESOS_DISTANCIAS = {"s": 0.0, "a": 0.25, "b": 0.75, "c": 1.0, "d": 1.5}
PESOS_CAMINHO_ATE_D = ["s", "a", "b", "c", "d"]


def desconexo() -> Grafo:
    return Grafo.de_pares([
        ("tema", "argumento"),
        ("proposta", "acao"),
    ])


DESCONEXO_INALCANCAVEIS_DE_TEMA = {"proposta", "acao"}
