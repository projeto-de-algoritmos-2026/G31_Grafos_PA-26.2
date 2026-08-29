"""
Grafos pequenos com resposta conhecida.

Servem de base para os testes de TODOS os algoritmos do projeto: a resposta
correta é conhecida de antemão (ou vem direto do Cormen), então quando um
teste falha o problema está no algoritmo, nunca na expectativa.

A trilha de algoritmos trabalha em cima destes grafos enquanto a extração
de texto ainda não está pronta — é o que permite as duas frentes andarem
em paralelo sem bloqueio.
"""

from src.grafo import Grafo


# ---------------------------------------------------------------------------
# 1. DAG simples
# ---------------------------------------------------------------------------

def dag_simples() -> Grafo:
    """
        a -> b -> c
        a ------> c

    Sem ciclos. Toda ordem topológica válida começa em 'a' e termina em 'c'.
    """
    return Grafo.de_pares([("a", "b"), ("b", "c"), ("a", "c")])


DAG_SIMPLES_SCCS = [{"a"}, {"b"}, {"c"}]
DAG_SIMPLES_ORDEM = ["a", "b", "c"]


# ---------------------------------------------------------------------------
# 2. Ciclo único
# ---------------------------------------------------------------------------

def com_ciclo() -> Grafo:
    """
        a -> b -> c -> a
                  c -> d

    Um componente fortemente conectado {a, b, c} e um vértice solto {d}.
    É o caso mínimo de "argumentação circular" no domínio da redação.
    """
    return Grafo.de_pares([("a", "b"), ("b", "c"), ("c", "a"), ("c", "d")])


COM_CICLO_SCCS = [{"a", "b", "c"}, {"d"}]
COM_CICLO_ORDEM_CONDENSADA = [{"a", "b", "c"}, {"d"}]


# ---------------------------------------------------------------------------
# 3. Cormen, figura 22.9 — o exemplo canônico de SCC
# ---------------------------------------------------------------------------

def cormen_22_9() -> Grafo:
    """
    Grafo da figura 22.9 do Cormen (3ª edição), capítulo 22.

    Diferença: o laço h -> h do livro foi omitido, porque a nossa classe
    Grafo rejeita laços por decisão de modelagem (um conceito não justifica
    a si mesmo). Isso não altera os componentes — {h} é unitário de todo
    jeito.
    """
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


# ---------------------------------------------------------------------------
# 4. Grafo com pesos, para Dijkstra
# ---------------------------------------------------------------------------

def pesos_dijkstra() -> Grafo:
    """
    Pesos são 1/frequência, então a frequência é que é declarada aqui.

        s -> a   freq 4   peso 0.25
        s -> b   freq 1   peso 1.00
        a -> b   freq 2   peso 0.50
        a -> c   freq 1   peso 1.00
        b -> c   freq 4   peso 0.25
        c -> d   freq 2   peso 0.50

    O caminho ganancioso s -> b (1.00) é pior que s -> a -> b (0.75):
    o teste pega qualquer implementação que esqueça de relaxar arestas.
    """
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


# ---------------------------------------------------------------------------
# 5. Grafo desconexo
# ---------------------------------------------------------------------------

def desconexo() -> Grafo:
    """
        tema -> argumento

        proposta -> acao        (ilha separada)

    Modela a falha da Competência 5: a proposta de intervenção não é
    alcançável a partir do tema. O Dijkstra deve devolver distância
    infinita, sem quebrar.
    """
    return Grafo.de_pares([
        ("tema", "argumento"),
        ("proposta", "acao"),
    ])


DESCONEXO_INALCANCAVEIS_DE_TEMA = {"proposta", "acao"}
