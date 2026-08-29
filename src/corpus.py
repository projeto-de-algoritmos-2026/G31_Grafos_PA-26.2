"""
Carregamento do corpus Essay-BR.

O Essay-BR é um corpus público de 4.570 redações de estudantes do ensino
médio brasileiro, avaliadas segundo os critérios do ENEM. Licença MIT.

    https://github.com/rafaelanchieta/essay

O que torna este corpus adequado ao nosso trabalho é a nota SEPARADA POR
COMPETÊNCIA. As nossas métricas não afirmam prever a nota final da redação:
elas afirmam detectar problemas de competências específicas —

    ordenação topológica e SCC  ->  Competência 3 (coerência e progressão)
    Dijkstra a partir do tema   ->  Competências 2 (tema) e 5 (proposta)

Com a nota humana de cada competência em mãos, a validação deixa de ser
"escolhemos duas redações que ilustram bem o ponto" e passa a ser uma
pergunta respondível sobre 4.570 textos: a métrica separa os grupos que a
correção humana separou?

FORMATO DO CORPUS
-----------------
`essay-br.csv` tem cinco colunas. Duas delas guardam listas do Python
serializadas como texto, e precisam ser reinterpretadas na leitura:

    prompt      id do tema, que remete a `prompts.csv`
    title       título dado pelo estudante
    essay       lista de parágrafos, como texto
    competence  lista de 5 notas (0 a 200 cada), como texto
    score       nota total (0 a 1000)

Este módulo não usa pandas: o `csv` da biblioteca padrão dá conta, e manter
o projeto com o mínimo de dependências facilita a vida de quem clona.
"""

from __future__ import annotations

import ast
import csv
import random
import sys
from dataclasses import dataclass
from pathlib import Path

#: Onde o corpus é descompactado. Fica em `data/raw/`, que está no
#: .gitignore — 24 MB de texto de terceiros não pertencem ao repositório.
CAMINHO_PADRAO = Path("data/raw/essay-master/essay-br")

#: Nomes das competências, na ordem em que aparecem no corpus.
COMPETENCIAS = (
    "norma culta",
    "compreensão do tema",
    "coerência e argumentação",
    "coesão",
    "proposta de intervenção",
)

_INSTRUCOES = """corpus não encontrado em {caminho}

Para baixar:
    mkdir -p data/raw && cd data/raw
    curl -sSL -o essay-br.zip https://github.com/rafaelanchieta/essay/archive/refs/heads/master.zip
    unzip -q essay-br.zip
"""


# ---------------------------------------------------------------------------
# Uma redação
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Redacao:
    """Uma redação do corpus, com sua avaliação humana."""

    indice: int
    titulo: str
    paragrafos: tuple[str, ...]
    tema_id: int
    tema: str
    competencias: tuple[int, int, int, int, int]
    nota: int

    # -- texto ------------------------------------------------------------

    @property
    def texto(self) -> str:
        """A redação inteira, com os parágrafos separados por linha em branco."""
        return "\n\n".join(self.paragrafos)

    @property
    def conclusao(self) -> str:
        """
        Último parágrafo — onde mora a proposta de intervenção.

        A estrutura do texto dissertativo-argumentativo do ENEM torna isso
        confiável: a proposta é cobrada explicitamente e vem no fecho.
        É daqui que sai o destino do caminho mínimo.
        """
        return self.paragrafos[-1] if self.paragrafos else ""

    @property
    def num_paragrafos(self) -> int:
        return len(self.paragrafos)

    # -- avaliação humana --------------------------------------------------

    @property
    def norma_culta(self) -> int:
        """Competência 1."""
        return self.competencias[0]

    @property
    def compreensao_do_tema(self) -> int:
        """Competência 2 — o que o Dijkstra a partir do tema deve refletir."""
        return self.competencias[1]

    @property
    def coerencia(self) -> int:
        """Competência 3 — o que o SCC e a ordenação topológica devem refletir."""
        return self.competencias[2]

    @property
    def coesao(self) -> int:
        """Competência 4."""
        return self.competencias[3]

    @property
    def proposta_de_intervencao(self) -> int:
        """Competência 5 — o que a conexão tema→proposta deve refletir."""
        return self.competencias[4]

    def competencia(self, numero: int) -> int:
        """Nota da competência `numero`, de 1 a 5."""
        if not 1 <= numero <= 5:
            raise ValueError(f"competência precisa estar entre 1 e 5, veio {numero}")
        return self.competencias[numero - 1]

    def __repr__(self) -> str:  # pragma: no cover - only for debugging
        return (
            f"Redacao(#{self.indice}, {self.titulo[:40]!r}, "
            f"nota={self.nota}, C3={self.coerencia})"
        )


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------

def _como_lista(bruto: str) -> tuple:
    """
    Reinterpreta uma coluna que guarda uma lista do Python como texto.

    Se o valor não for uma lista serializada, devolve-o como item único —
    assim uma linha malformada vira um dado pobre, não uma exceção que
    derruba a leitura das outras 4.569.
    """
    try:
        valor = ast.literal_eval(bruto)
    except (ValueError, SyntaxError):
        return (bruto.strip(),)
    if isinstance(valor, (list, tuple)):
        return tuple(valor)
    return (valor,)


def _ler_temas(pasta: Path) -> dict[int, str]:
    """Mapa id do tema -> texto motivador, vindo de `prompts.csv`."""
    caminho = pasta / "prompts.csv"
    if not caminho.exists():
        return {}

    temas: dict[int, str] = {}
    with open(caminho, encoding="utf-8", newline="") as arquivo:
        for linha in csv.DictReader(arquivo):
            try:
                identificador = int(linha["id"])
            except (KeyError, TypeError, ValueError):
                continue
            temas[identificador] = " ".join(_como_lista(linha.get("description", "")))
    return temas


def carregar(caminho: Path | str | None = None, split: str | None = None) -> list[Redacao]:
    """
    Lê o corpus e devolve as redações.

    `split` aceita "training", "development" ou "testing" para ler apenas
    uma das partições já preparadas pelos autores do corpus; com None, lê o
    arquivo completo. Para a nossa validação o corpus inteiro serve, porque
    não estamos treinando modelo nenhum — só medindo.
    """
    pasta = Path(caminho) if caminho is not None else CAMINHO_PADRAO

    if split is None:
        arquivo_csv = pasta / "essay-br.csv"
    else:
        permitidos = {"training", "development", "testing"}
        if split not in permitidos:
            raise ValueError(f"split precisa ser um de {sorted(permitidos)}, veio {split!r}")
        arquivo_csv = pasta / "splits" / f"{split}.csv"

    if not arquivo_csv.exists():
        raise FileNotFoundError(_INSTRUCOES.format(caminho=arquivo_csv))

    # os parágrafos são campos longos; o limite padrão do módulo csv não basta
    csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

    temas = _ler_temas(pasta)
    redacoes: list[Redacao] = []

    with open(arquivo_csv, encoding="utf-8", newline="") as arquivo:
        for indice, linha in enumerate(csv.DictReader(arquivo)):
            paragrafos = tuple(p.strip() for p in _como_lista(linha["essay"]) if str(p).strip())
            if not paragrafos:
                continue

            notas = tuple(int(n) for n in _como_lista(linha["competence"]))
            if len(notas) != 5:
                continue

            try:
                tema_id = int(linha["prompt"])
            except (TypeError, ValueError):
                tema_id = -1

            redacoes.append(
                Redacao(
                    indice=indice,
                    titulo=(linha.get("title") or "").strip(),
                    paragrafos=paragrafos,
                    tema_id=tema_id,
                    tema=temas.get(tema_id, ""),
                    competencias=notas,  # type: ignore[arg-type]
                    nota=int(linha["score"]),
                )
            )

    return redacoes


# ---------------------------------------------------------------------------
# Seleção
# ---------------------------------------------------------------------------

def filtrar(
    redacoes: list[Redacao],
    *,
    competencia: int | None = None,
    minimo: int | None = None,
    maximo: int | None = None,
    tema_id: int | None = None,
    min_paragrafos: int | None = None,
) -> list[Redacao]:
    """
    Recorta o corpus.

    Com `competencia`, os limites `minimo` e `maximo` se aplicam à nota
    daquela competência; sem ela, aplicam-se à nota total. É assim que se
    montam os dois grupos da validação — por exemplo, as redações com
    Competência 3 alta contra as com Competência 3 baixa, mantendo tudo
    o mais igual.
    """
    def nota_de(r: Redacao) -> int:
        return r.competencia(competencia) if competencia else r.nota

    selecionadas = redacoes
    if minimo is not None:
        selecionadas = [r for r in selecionadas if nota_de(r) >= minimo]
    if maximo is not None:
        selecionadas = [r for r in selecionadas if nota_de(r) <= maximo]
    if tema_id is not None:
        selecionadas = [r for r in selecionadas if r.tema_id == tema_id]
    if min_paragrafos is not None:
        selecionadas = [r for r in selecionadas if r.num_paragrafos >= min_paragrafos]
    return selecionadas


def amostra(redacoes: list[Redacao], n: int, semente: int = 42) -> list[Redacao]:
    """
    Amostra aleatória e REPRODUTÍVEL.

    A semente fixa é proposital: um número que aparece no README ou no
    vídeo precisa dar o mesmo resultado quando alguém repetir a medição.
    """
    if n >= len(redacoes):
        return list(redacoes)
    return random.Random(semente).sample(redacoes, n)


def estatisticas(redacoes: list[Redacao]) -> dict:
    """Números descritivos do recorte, para conferir o que se está medindo."""
    if not redacoes:
        return {"redacoes": 0}

    notas = [r.nota for r in redacoes]
    return {
        "redacoes": len(redacoes),
        "temas": len({r.tema_id for r in redacoes}),
        "nota_media": sum(notas) / len(notas),
        "nota_minima": min(notas),
        "nota_maxima": max(notas),
        "paragrafos_media": sum(r.num_paragrafos for r in redacoes) / len(redacoes),
        "competencias_media": [
            sum(r.competencias[i] for r in redacoes) / len(redacoes) for i in range(5)
        ],
    }


# ---------------------------------------------------------------------------
# Execução direta
#
#     python -m src.corpus
# ---------------------------------------------------------------------------

def _main(argv: list[str]) -> int:
    split = argv[1] if len(argv) > 1 else None

    try:
        redacoes = carregar(split=split)
    except (FileNotFoundError, ValueError) as erro:
        print(erro, file=sys.stderr)
        return 1

    st = estatisticas(redacoes)
    print(f"{st['redacoes']} redações, {st['temas']} temas")
    print(
        f"nota total: média {st['nota_media']:.0f}, "
        f"de {st['nota_minima']} a {st['nota_maxima']}"
    )
    print(f"parágrafos por redação: média {st['paragrafos_media']:.1f}")
    print()
    print("MÉDIA POR COMPETÊNCIA (0 a 200)")
    for nome, media in zip(COMPETENCIAS, st["competencias_media"]):
        barra = "█" * round(media / 200 * 30)
        print(f"  {nome:<26} {media:5.0f}  {barra}")

    print()
    print("DISTRIBUIÇÃO DA COMPETÊNCIA 3 (coerência)")
    for faixa in (0, 40, 80, 120, 160, 200):
        quantas = len([r for r in redacoes if r.coerencia == faixa])
        print(f"  {faixa:>3}: {quantas:>5}  {'▏' * round(quantas / 40)}")

    exemplo = amostra(redacoes, 1)[0]
    print()
    print(f"EXEMPLO — #{exemplo.indice}: {exemplo.titulo!r}")
    print(f"  nota {exemplo.nota}, competências {list(exemplo.competencias)}")
    print(f"  {exemplo.num_paragrafos} parágrafos")
    print(f"  conclusão: {exemplo.conclusao[:150]}...")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main(sys.argv))
