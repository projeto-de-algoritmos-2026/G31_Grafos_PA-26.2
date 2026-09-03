"""Desenho do grafo de conceitos, em DOT."""
from __future__ import annotations

from src.diagnostico import Diagnostico

COR_LACO = "#F6E3DD"
BORDA_LACO = "#A8402A"
COR_CAMINHO = "#DDEDE6"
BORDA_CAMINHO = "#1E6E5A"
COR_NEUTRA = "#F1F3F2"
BORDA_NEUTRA = "#B9C4BF"
COR_TEXTO = "#141917"


def _escapar(texto: str) -> str:
    """Deixa um rótulo seguro dentro de aspas no DOT."""
    return texto.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _espessura(frequencia: int) -> float:
    """Relação repetida no texto vira aresta mais grossa."""
    return min(1.0 + 0.8 * (frequencia - 1), 4.0)


def para_dot(d: Diagnostico, *, apenas_conectados: bool = False) -> str:
    """Converte o diagnóstico em uma string DOT."""
    grafo = d.grafo

    em_laco = {c for laco in d.lacos for c in laco}
    no_caminho = set(d.caminho.caminho or []) if d.caminho and d.caminho.alcancavel else set()
    arestas_do_caminho = set()
    if d.caminho and d.caminho.caminho:
        percurso = d.caminho.caminho
        arestas_do_caminho = {(percurso[i], percurso[i + 1]) for i in range(len(percurso) - 1)}

    com_relacao = set()
    for aresta in grafo.arestas():
        com_relacao.add(aresta.origem)
        com_relacao.add(aresta.destino)

    linhas = [
        "digraph redacao {",
        '  rankdir=LR;',
        '  bgcolor="transparent";',
        '  node [shape=box, style="rounded,filled", fontname="Helvetica", '
        f'fontsize=11, fontcolor="{COR_TEXTO}", margin="0.12,0.07"];',
        '  edge [fontname="Helvetica", fontsize=9, color="#8A9691", arrowsize=0.7];',
    ]

    for vertice in grafo.vertices:
        if apenas_conectados and vertice not in com_relacao:
            continue

        if vertice in em_laco:
            preenchimento, borda = COR_LACO, BORDA_LACO
        elif vertice in no_caminho:
            preenchimento, borda = COR_CAMINHO, BORDA_CAMINHO
        else:
            preenchimento, borda = COR_NEUTRA, BORDA_NEUTRA

        atributos = [
            f'label="{_escapar(d.exibir(vertice))}"',
            f'fillcolor="{preenchimento}"',
            f'color="{borda}"',
        ]
        if vertice == d.alvos.tema:
            atributos.append("penwidth=2.5")
            atributos.append('shape="box"')
            atributos.append('style="rounded,filled,bold"')

        linhas.append(f'  "{_escapar(vertice)}" [{", ".join(atributos)}];')

    for aresta in grafo.arestas():
        atributos = [f"penwidth={_espessura(aresta.frequencia):.1f}"]
        if (aresta.origem, aresta.destino) in arestas_do_caminho:
            atributos.append(f'color="{BORDA_CAMINHO}"')
            atributos.append("penwidth=2.5")
        elif aresta.origem in em_laco and aresta.destino in em_laco:
            atributos.append(f'color="{BORDA_LACO}"')
        if aresta.frequencia > 1:
            atributos.append(f'label="{aresta.frequencia}x"')
        if aresta.frases:
            atributos.append(f'tooltip="{_escapar(aresta.frases[0])}"')

        linhas.append(
            f'  "{_escapar(aresta.origem)}" -> "{_escapar(aresta.destino)}" '
            f'[{", ".join(atributos)}];'
        )

    linhas.append("}")
    return "\n".join(linhas)


def legenda() -> list[tuple[str, str]]:
    """Pares (cor, significado), para a interface montar a legenda."""
    return [
        (BORDA_CAMINHO, "ligação entre o tema e a sua proposta"),
        (BORDA_LACO, "argumento em círculo"),
        (BORDA_NEUTRA, "outras ideias"),
    ]
