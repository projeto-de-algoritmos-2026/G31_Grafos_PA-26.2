
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
    return texto.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
 
 
def _espessura(frequencia: int) -> float:
    return min(1.0 + 0.8 * (frequencia - 1), 4.0)
 
 
def para_dot(d: Diagnostico, *, apenas_conectados: bool = False) -> str:

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
 
 
def para_dot_condensado(d: Diagnostico) -> str:
    condensacao = d.condensacao
    if condensacao is None:
        return "digraph vazio {}"
 
    no_maior_caminho = set(d.maior_caminho or [])
    arestas_do_maior_caminho = set()
    if d.maior_caminho:
        percurso = d.maior_caminho
        arestas_do_maior_caminho = {
            (percurso[i], percurso[i + 1]) for i in range(len(percurso) - 1)
        }
 
    linhas = [
        "digraph condensado {",
        '  rankdir=LR;',
        '  bgcolor="transparent";',
        '  node [shape=box, style="rounded,filled", fontname="Helvetica", '
        f'fontsize=11, fontcolor="{COR_TEXTO}", margin="0.12,0.07"];',
        '  edge [fontname="Helvetica", fontsize=9, color="#8A9691", arrowsize=0.7];',
    ]
 
    for rotulo, membros in condensacao.membros.items():
        eh_laco = len(membros) > 1
        preenchimento, borda = (COR_LACO, BORDA_LACO) if eh_laco else (COR_NEUTRA, BORDA_NEUTRA)
        texto_rotulo = " + ".join(sorted(d.exibir(m) for m in membros))
 
        atributos = [
            f'label="{_escapar(texto_rotulo)}"',
            f'fillcolor="{preenchimento}"',
            f'color="{borda}"',
        ]
        if rotulo in no_maior_caminho:
            atributos.append("penwidth=2.5")
 
        linhas.append(f'  "{_escapar(rotulo)}" [{", ".join(atributos)}];')
 
    for aresta in condensacao.grafo.arestas():
        atributos = []
        if (aresta.origem, aresta.destino) in arestas_do_maior_caminho:
            atributos.append(f'color="{BORDA_CAMINHO}"')
            atributos.append("penwidth=2.5")
        linhas.append(
            f'  "{_escapar(aresta.origem)}" -> "{_escapar(aresta.destino)}" '
            f'[{", ".join(atributos)}];'
        )
 
    linhas.append("}")
    return "\n".join(linhas)
 
 
def legenda() -> list[tuple[str, str]]:

    return [
        (BORDA_CAMINHO, "ligação entre o tema e a sua proposta"),
        (BORDA_LACO, "argumento em círculo"),
        (BORDA_NEUTRA, "outras ideias"),
    ]
 
