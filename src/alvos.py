
from __future__ import annotations

from dataclasses import dataclass, field

from src.extracao import Extracao, Extrator
from src.grafo import Grafo

VERBOS_DE_INTERVENCAO: frozenset[str] = frozenset({
    "promover", "criar", "implementar", "implantar", "garantir", "assegurar",
    "fiscalizar", "investir", "conscientizar", "ampliar", "incentivar",
    "desenvolver", "elaborar", "estabelecer", "oferecer", "disponibilizar",
    "combater", "reduzir", "erradicar", "capacitar", "divulgar", "instituir",
    "reformular", "viabilizar", "subsidiar", "regulamentar", "sanar",
})


@dataclass
class Alvos:

    tema: str | None = None
    origem_do_tema: str = ""
    propostas: list[str] = field(default_factory=list)
    tema_candidatos: list[str] = field(default_factory=list)

    @property
    def utilizavel(self) -> bool:
        return self.tema is not None and bool(self.propostas)

    def resumo(self) -> str:
        if not self.utilizavel:
            faltando = []
            if self.tema is None:
                faltando.append("tema")
            if not self.propostas:
                faltando.append("proposta")
            return f"alvos incompletos: sem {' e sem '.join(faltando)}"
        return (
            f"tema '{self.tema}' (do {self.origem_do_tema}) -> "
            f"{len(self.propostas)} conceito(s) de proposta: "
            f"{', '.join(self.propostas[:4])}"
        )


def _grau_de_saida(grafo: Grafo, vertice: str) -> int:
    return sum(1 for _ in grafo.sucessores(vertice))


def _casar_com_grafo(candidato: str, grafo: Grafo) -> list[str]:
    if candidato in grafo:
        return [candidato]
    nucleo = candidato.split()[0]
    return [v for v in grafo.vertices if v.split()[0] == nucleo]


def identificar_tema(
    grafo: Grafo,
    extrator: Extrator,
    *,
    titulo: str = "",
    enunciado: str = "",
    introducao: str = "",
) -> tuple[str | None, str, list[str]]:
    candidatos_vistos: list[str] = []
    reserva: str | None = None
    reserva_fonte = ""

    for fonte, texto in (("titulo", titulo), ("enunciado", enunciado), ("introducao", introducao)):
        if not texto.strip():
            continue

        candidatos = extrator.conceitos_do_texto(texto)
        candidatos_vistos.extend(c for c in candidatos if c not in candidatos_vistos)

        posicao: dict[str, int] = {}
        for i, candidato in enumerate(candidatos):
            for vertice in _casar_com_grafo(candidato, grafo):
                posicao.setdefault(vertice, i)

        if not posicao:
            continue

        melhor = max(posicao, key=lambda v: (_grau_de_saida(grafo, v), -posicao[v]))

        if _grau_de_saida(grafo, melhor) > 0:
            return melhor, fonte, candidatos_vistos

        if reserva is None:
            reserva, reserva_fonte = melhor, fonte

    return reserva, reserva_fonte, candidatos_vistos


def identificar_propostas(grafo: Grafo, extrator: Extrator, conclusao: str) -> list[str]:
    if not conclusao.strip():
        return []

    documento = extrator._nlp(conclusao)

    alvos_diretos: list[str] = []
    for token in documento:
        if token.pos_ not in ("VERB", "AUX"):
            continue
        if token.lemma_.lower() not in VERBOS_DE_INTERVENCAO:
            continue
        objetos = [f for f in token.children if f.dep_ in ("obj", "obl", "xcomp", "ccomp")]
        for conceito in extrator._rotulos(objetos):
            for vertice in _casar_com_grafo(conceito, grafo):
                if vertice not in alvos_diretos:
                    alvos_diretos.append(vertice)

    if alvos_diretos:
        return alvos_diretos

    conceitos: list[str] = []
    for candidato in extrator.conceitos_do_texto(conclusao):
        for vertice in _casar_com_grafo(candidato, grafo):
            if vertice not in conceitos:
                conceitos.append(vertice)
    return conceitos


def identificar(
    extracao: Extracao,
    extrator: Extrator,
    *,
    titulo: str = "",
    enunciado: str = "",
    introducao: str = "",
    conclusao: str = "",
) -> Alvos:
    grafo = extracao.grafo
    tema, fonte, candidatos = identificar_tema(
        grafo, extrator, titulo=titulo, enunciado=enunciado, introducao=introducao
    )
    return Alvos(
        tema=tema,
        origem_do_tema=fonte,
        propostas=identificar_propostas(grafo, extrator, conclusao),
        tema_candidatos=candidatos,
    )
