"""
Validação: a métrica de grafo separa o que a correção humana separou?

    python validacao.py                      # Competência 3, métrica padrão
    python validacao.py --competencia 5      # outra competência
    python validacao.py --n 120              # amostra maior

A pergunta é uma só, e é falsificável: tomando redações que corretores
humanos avaliaram bem e mal numa competência específica, uma métrica
calculada sobre o grafo distingue os dois grupos?

O script devolve o ponto de corte que melhor separa os grupos e a taxa de
acerto desse corte. Uma taxa perto de 50% significa que a métrica não sabe
nada — é o resultado que a gente teria que reportar se fosse o caso.

TROCAR A MÉTRICA
----------------
A métrica é injetada, não fixa. Hoje o padrão é o comprimento da ordenação
topológica (`cadeia_argumentativa`), que na prática mede quantos conceitos
o texto encadeia. Quando o MAIOR CAMINHO NO DAG existir, é trocar uma
linha em `METRICAS` e rodar de novo — os dois resultados lado a lado
mostram se a profundidade da cadeia diz mais que o tamanho dela.

REPRODUTIBILIDADE
-----------------
A amostragem tem semente fixa. Todo número que sai daqui e vai para o
README ou para o vídeo pode ser reproduzido por quem rodar o comando.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

from src.analise import cadeia_argumentativa
from src.corpus import COMPETENCIAS, Redacao, amostra, carregar, filtrar
from src.extracao import Extrator
from src.grafo import Grafo

PASTA_RESULTADOS = Path("resultados")

#: Notas do Essay-BR são múltiplos de 40, de 0 a 200. Estes são os extremos.
NOTA_ALTA = 160
NOTA_BAIXA = 80


def _tamanho_da_cadeia(grafo: Grafo) -> int:
    """
    Métrica padrão: quantos conceitos a ordenação topológica encadeia.

    Ressalva honesta: sem ciclo, o Kahn devolve TODOS os vértices, então
    este número é na prática o tamanho do grafo — não a profundidade da
    cadeia causal. Ciclos são raros em redação real (1 em 180), então os
    dois quase sempre coincidem. O maior caminho no DAG é a métrica que
    mediria profundidade de verdade.
    """
    cadeia = cadeia_argumentativa(grafo)
    return len(cadeia) if cadeia else 0


#: Métricas disponíveis. Acrescentar aqui é o único passo para validar uma
#: métrica nova — o resto do script não muda.
METRICAS = {
    "cadeia": ("comprimento da cadeia argumentativa", _tamanho_da_cadeia),
    "conceitos": ("número de conceitos", lambda g: g.num_vertices),
    "relacoes": ("número de relações", lambda g: g.num_arestas),
}


# ---------------------------------------------------------------------------
# Estatística
# ---------------------------------------------------------------------------

@dataclass
class Grupo:
    nome: str
    valores: list[int] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.valores)

    def quartil(self, p: float) -> float:
        """Quartil por posição (nearest-rank), sem interpolação."""
        if not self.valores:
            return 0.0
        ordenados = sorted(self.valores)
        return float(ordenados[int(p * (len(ordenados) - 1))])

    @property
    def mediana(self) -> float:
        return statistics.median(self.valores) if self.valores else 0.0


def melhor_corte(altas: Grupo, baixas: Grupo) -> tuple[int, float]:
    """
    Corte que maximiza a separação, e a taxa de acerto correspondente.

    Testa todos os inteiros no intervalo observado. Acerto é a fração de
    redações classificadas do lado certo: alta com valor >= corte, baixa
    com valor < corte. Um corte que acerta ~50% é o mesmo que jogar moeda.
    """
    todos = altas.valores + baixas.valores
    if not todos or not altas.valores or not baixas.valores:
        return 0, 0.0

    total = len(todos)
    melhor = (0, 0.0)
    for corte in range(min(todos), max(todos) + 1):
        acertos = sum(1 for v in altas.valores if v >= corte)
        acertos += sum(1 for v in baixas.valores if v < corte)
        taxa = acertos / total
        if taxa > melhor[1]:
            melhor = (corte, taxa)
    return melhor


# ---------------------------------------------------------------------------
# Gráfico — SVG escrito à mão, sem dependência
# ---------------------------------------------------------------------------

COR_ALTA = "#0F8F71"
COR_BAIXA = "#B8461F"
FUNDO = "#FCFCFB"
TINTA = "#141917"
TINTA_FRACA = "#5A6763"
GRADE = "#E4E8E6"

LARGURA, ALTURA = 760, 428
# topo generoso: cabem título, subtítulo, o rótulo do corte e o da faceta,
# em quatro linhas que não se encostam
MARGEM = {"esq": 46, "dir": 24, "topo": 100, "base": 54}
ALTURA_FACETA = 116
ESPACO_FACETA = 34
LARGURA_BIN = 4


def _barra(x: float, base: float, largura: float, altura: float, raio: float = 4.0) -> str:
    """Barra ancorada na linha de base, com o topo arredondado."""
    if altura <= 0:
        return ""
    r = min(raio, largura / 2, altura)
    topo = base - altura
    return (
        f"M{x:.1f},{base:.1f} V{topo + r:.1f} "
        f"Q{x:.1f},{topo:.1f} {x + r:.1f},{topo:.1f} "
        f"H{x + largura - r:.1f} "
        f"Q{x + largura:.1f},{topo:.1f} {x + largura:.1f},{topo + r:.1f} "
        f"V{base:.1f} Z"
    )


def _histograma(valores: list[int], inicio: int, fim: int) -> list[int]:
    bins = [0] * ((fim - inicio) // LARGURA_BIN + 1)
    for v in valores:
        indice = min(max((v - inicio) // LARGURA_BIN, 0), len(bins) - 1)
        bins[indice] += 1
    return bins


def grafico_svg(
    altas: Grupo, baixas: Grupo, *, corte: int, taxa: float,
    competencia: int, metrica: str,
) -> str:
    """
    Dois histogramas empilhados, mesma escala, com o corte atravessando.

    A escolha da forma é deliberada: barras sobrepostas esconderiam a
    sobreposição entre os grupos, e é justamente ela que explica por que o
    acerto é 74% e não 95%. Facetas separadas com eixo compartilhado
    mostram a diferença de posição E a sobreposição ao mesmo tempo.
    """
    todos = altas.valores + baixas.valores
    inicio = 0
    fim = max(todos) + LARGURA_BIN if todos else 40

    bins_altas = _histograma(altas.valores, inicio, fim)
    bins_baixas = _histograma(baixas.valores, inicio, fim)
    pico = max(max(bins_altas, default=1), max(bins_baixas, default=1), 1)

    largura_plot = LARGURA - MARGEM["esq"] - MARGEM["dir"]
    n_bins = len(bins_altas)
    passo = largura_plot / n_bins
    largura_barra = max(passo - 2, 1)  # 2px de respiro entre barras

    def x_de(valor: float) -> float:
        return MARGEM["esq"] + (valor - inicio) / (fim - inicio) * largura_plot

    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{LARGURA}" height="{ALTURA}" '
        f'viewBox="0 0 {LARGURA} {ALTURA}" font-family="Helvetica, Arial, sans-serif">',
        f'<rect width="{LARGURA}" height="{ALTURA}" fill="{FUNDO}"/>',
        f'<text x="{MARGEM["esq"]}" y="26" font-size="15" font-weight="600" fill="{TINTA}">'
        f'A métrica separa o que a correção humana separou?</text>',
        f'<text x="{MARGEM["esq"]}" y="45" font-size="11.5" fill="{TINTA_FRACA}">'
        f'{metrica} · Competência {competencia} ({COMPETENCIAS[competencia - 1]}) · '
        f'corpus Essay-BR, n={altas.n + baixas.n}</text>',
    ]

    facetas = [
        (f"Nota alta (&#8805; {NOTA_ALTA})", altas, bins_altas, COR_ALTA),
        (f"Nota baixa (&#8804; {NOTA_BAIXA})", baixas, bins_baixas, COR_BAIXA),
    ]

    for i, (rotulo, grupo, bins, cor) in enumerate(facetas):
        topo = MARGEM["topo"] + i * (ALTURA_FACETA + ESPACO_FACETA)
        base = topo + ALTURA_FACETA

        # grade recessiva: uma linha no meio da escala
        p.append(
            f'<line x1="{MARGEM["esq"]}" y1="{base - ALTURA_FACETA / 2:.1f}" '
            f'x2="{LARGURA - MARGEM["dir"]}" y2="{base - ALTURA_FACETA / 2:.1f}" '
            f'stroke="{GRADE}" stroke-width="1"/>'
        )

        for j, contagem in enumerate(bins):
            if not contagem:
                continue
            altura_barra = contagem / pico * ALTURA_FACETA
            x = MARGEM["esq"] + j * passo + 1
            p.append(f'<path d="{_barra(x, base, largura_barra, altura_barra)}" fill="{cor}"/>')

        p.append(
            f'<line x1="{MARGEM["esq"]}" y1="{base}" x2="{LARGURA - MARGEM["dir"]}" '
            f'y2="{base}" stroke="{TINTA_FRACA}" stroke-width="1"/>'
        )
        # escala vertical, discreta: quantas redações cada altura representa
        for valor, y in ((0, base), (pico / 2, base - ALTURA_FACETA / 2), (pico, base - ALTURA_FACETA)):
            p.append(
                f'<text x="{MARGEM["esq"] - 7}" y="{y + 3.5:.1f}" font-size="9.5" '
                f'fill="{TINTA_FRACA}" text-anchor="end">{valor:.0f}</text>'
            )
        # rótulo direto: sem caixa de legenda, cada faceta se nomeia
        p.append(
            f'<text x="{MARGEM["esq"]}" y="{topo - 8}" font-size="12" font-weight="600" '
            f'fill="{cor}">{rotulo}</text>'
        )
        # à direita: o traço do corte é vertical e cruzaria o texto se ele
        # ficasse ao lado do rótulo da faceta
        p.append(
            f'<text x="{LARGURA - MARGEM["dir"]}" y="{topo - 8}" font-size="11" '
            f'fill="{TINTA_FRACA}" text-anchor="end">n={grupo.n} · '
            f'mediana {grupo.mediana:.0f}</text>'
        )

    # o corte atravessa as duas facetas
    x_corte = x_de(corte)
    fim_facetas = MARGEM["topo"] + 2 * ALTURA_FACETA + ESPACO_FACETA
    p.append(
        f'<line x1="{x_corte:.1f}" y1="{MARGEM["topo"] - 24}" x2="{x_corte:.1f}" '
        f'y2="{fim_facetas}" stroke="{TINTA}" stroke-width="1.5" stroke-dasharray="5 4"/>'
    )
    p.append(
        f'<text x="{x_corte + 6:.1f}" y="{MARGEM["topo"] - 30}" font-size="11.5" '
        f'font-weight="600" fill="{TINTA}">corte {corte} &#183; {taxa:.0%} de acerto</text>'
    )

    # eixo x
    eixo_y = fim_facetas + 20
    for valor in range(inicio, fim + 1, 10):
        p.append(
            f'<text x="{x_de(valor):.1f}" y="{eixo_y}" font-size="10.5" '
            f'fill="{TINTA_FRACA}" text-anchor="middle">{valor}</text>'
        )
    p.append(
        f'<text x="{LARGURA / 2}" y="{eixo_y + 20}" font-size="11" fill="{TINTA_FRACA}" '
        f'text-anchor="middle">{metrica}</text>'
    )

    p.append("</svg>")
    return "\n".join(p)


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def medir(redacoes: list[Redacao], metrica, extrator: Extrator) -> list[int]:
    return [metrica(extrator.extrair(r.texto).grafo) for r in redacoes]


def tabela_markdown(altas: Grupo, baixas: Grupo, corte: int, taxa: float, metrica: str) -> str:
    linhas = [
        f"| grupo | n | p25 | mediana | p75 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for g in (altas, baixas):
        linhas.append(
            f"| {g.nome} | {g.n} | {g.quartil(.25):.0f} | {g.mediana:.0f} | {g.quartil(.75):.0f} |"
        )
    linhas.append("")
    linhas.append(f"Melhor corte: **{metrica} >= {corte}** — **{taxa:.0%} de acerto** "
                  f"na separação dos dois grupos.")
    return "\n".join(linhas)


def _main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--competencia", type=int, default=3, choices=[1, 2, 3, 4, 5])
    ap.add_argument("--metrica", default="cadeia", choices=list(METRICAS))
    ap.add_argument("--n", type=int, default=80, help="redações por grupo")
    ap.add_argument("--semente", type=int, default=5)
    args = ap.parse_args(argv[1:])

    rotulo_metrica, funcao = METRICAS[args.metrica]

    try:
        corpus = carregar()
    except FileNotFoundError as erro:
        print(erro, file=sys.stderr)
        return 1

    extrator = Extrator()
    print(f"Medindo '{rotulo_metrica}' em {2 * args.n} redações...", file=sys.stderr)

    altas = Grupo(f"Competência {args.competencia} alta")
    baixas = Grupo(f"Competência {args.competencia} baixa")
    altas.valores = medir(
        amostra(filtrar(corpus, competencia=args.competencia, minimo=NOTA_ALTA),
                args.n, semente=args.semente),
        funcao, extrator,
    )
    baixas.valores = medir(
        amostra(filtrar(corpus, competencia=args.competencia, maximo=NOTA_BAIXA),
                args.n, semente=args.semente),
        funcao, extrator,
    )

    corte, taxa = melhor_corte(altas, baixas)

    print()
    print(tabela_markdown(altas, baixas, corte, taxa, rotulo_metrica))

    PASTA_RESULTADOS.mkdir(exist_ok=True)
    base = PASTA_RESULTADOS / f"validacao_c{args.competencia}_{args.metrica}"

    svg = grafico_svg(altas, baixas, corte=corte, taxa=taxa,
                      competencia=args.competencia, metrica=rotulo_metrica)
    base.with_suffix(".svg").write_text(svg, encoding="utf-8")

    base.with_suffix(".md").write_text(
        tabela_markdown(altas, baixas, corte, taxa, rotulo_metrica) + "\n", encoding="utf-8"
    )
    base.with_suffix(".json").write_text(
        json.dumps(
            {
                "competencia": args.competencia,
                "metrica": args.metrica,
                "rotulo": rotulo_metrica,
                "semente": args.semente,
                "corte": corte,
                "acerto": round(taxa, 4),
                "grupos": {
                    g.nome: {
                        "n": g.n, "p25": g.quartil(.25),
                        "mediana": g.mediana, "p75": g.quartil(.75),
                        "valores": g.valores,
                    }
                    for g in (altas, baixas)
                },
            },
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print(f"gravado em {base}.svg, .md e .json")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main(sys.argv))
