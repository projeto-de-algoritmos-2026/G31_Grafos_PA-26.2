
from __future__ import annotations

import ast
import csv
import random
import sys
from dataclasses import dataclass
from pathlib import Path

CAMINHO_PADRAO = Path("data/raw/essay-master/essay-br")

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


@dataclass(frozen=True)
class Redacao:

    indice: int
    titulo: str
    paragrafos: tuple[str, ...]
    tema_id: int
    tema: str
    competencias: tuple[int, int, int, int, int]
    nota: int

    @property
    def texto(self) -> str:
        return "\n\n".join(self.paragrafos)

    @property
    def conclusao(self) -> str:

        return self.paragrafos[-1] if self.paragrafos else ""

    @property
    def num_paragrafos(self) -> int:
        return len(self.paragrafos)

    @property
    def norma_culta(self) -> int:
        return self.competencias[0]

    @property
    def compreensao_do_tema(self) -> int:
        return self.competencias[1]

    @property
    def coerencia(self) -> int:
        return self.competencias[2]

    @property
    def coesao(self) -> int:
        return self.competencias[3]

    @property
    def proposta_de_intervencao(self) -> int:
        return self.competencias[4]

    def competencia(self, numero: int) -> int:
        if not 1 <= numero <= 5:
            raise ValueError(f"competência precisa estar entre 1 e 5, veio {numero}")
        return self.competencias[numero - 1]

    def __repr__(self) -> str:
        return (
            f"Redacao(#{self.indice}, {self.titulo[:40]!r}, "
            f"nota={self.nota}, C3={self.coerencia})"
        )


def _como_lista(bruto: str) -> tuple:

    try:
        valor = ast.literal_eval(bruto)
    except (ValueError, SyntaxError):
        return (bruto.strip(),)
    if isinstance(valor, (list, tuple)):
        return tuple(valor)
    return (valor,)


def _ler_temas(pasta: Path) -> dict[int, str]:
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
                    competencias=notas,
                    nota=int(linha["score"]),
                )
            )

    return redacoes


def filtrar(
    redacoes: list[Redacao],
    *,
    competencia: int | None = None,
    minimo: int | None = None,
    maximo: int | None = None,
    tema_id: int | None = None,
    min_paragrafos: int | None = None,
) -> list[Redacao]:

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

    if n >= len(redacoes):
        return list(redacoes)
    return random.Random(semente).sample(redacoes, n)


def estatisticas(redacoes: list[Redacao]) -> dict:
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


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
