"""
Identificação da origem e do destino do caminho mínimo.

O Dijkstra só responde a uma pergunta se souber de onde parte e aonde quer
chegar. No nosso caso:

    origem   -> o conceito que representa o TEMA da prova
    destino  -> os conceitos de que trata a PROPOSTA DE INTERVENÇÃO

Com esses dois pontos, o caminho mínimo mede se o autor construiu uma
ponte argumentativa entre a proposta que apresenta no fim e o tema que
recebeu no enunciado. Distância infinita significa proposta que o texto
nunca preparou — perda direta na Competência 5.

POR QUE ISSO PODE SER SIMPLES
-----------------------------
A redação do ENEM tem estrutura obrigatória, e é ela que faz o trabalho:

- o tema não é adivinhado, ele vem do enunciado da prova. Basta descobrir
  qual conceito do grafo o representa;
- a proposta de intervenção é cobrada explicitamente e vem no último
  parágrafo, quase sempre marcada por um verbo de ação ("deve promover",
  "é necessário implementar", "cabe ao Estado garantir").

Nada aqui precisa ser inteligente. Precisa ser fiel à estrutura do gênero.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.extracao import Extracao, Extrator
from src.grafo import Grafo

#: Verbos que marcam proposta de intervenção. A Competência 5 pede agente,
#: ação, meio e finalidade — e a ação quase sempre cai neste vocabulário.
VERBOS_DE_INTERVENCAO: frozenset[str] = frozenset({
    "promover", "criar", "implementar", "implantar", "garantir", "assegurar",
    "fiscalizar", "investir", "conscientizar", "ampliar", "incentivar",
    "desenvolver", "elaborar", "estabelecer", "oferecer", "disponibilizar",
    "combater", "reduzir", "erradicar", "capacitar", "divulgar", "instituir",
    "reformular", "viabilizar", "subsidiar", "regulamentar", "sanar",
})


@dataclass
class Alvos:
    """Origem e destinos do caminho mínimo, com o rastro da decisão."""

    tema: str | None = None
    #: de onde veio o conceito-tema: "titulo", "enunciado" ou "introducao"
    origem_do_tema: str = ""
    propostas: list[str] = field(default_factory=list)
    #: candidatos que apareciam no texto mas não estão no grafo
    tema_candidatos: list[str] = field(default_factory=list)

    @property
    def utilizavel(self) -> bool:
        """Só faz sentido rodar o Dijkstra com os dois pontos definidos."""
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


# ---------------------------------------------------------------------------
# Tema
# ---------------------------------------------------------------------------

def _grau_de_saida(grafo: Grafo, vertice: str) -> int:
    return sum(1 for _ in grafo.sucessores(vertice))


def _casar_com_grafo(candidato: str, grafo: Grafo) -> list[str]:
    """
    Vértices do grafo que correspondem a um conceito citado no texto.

    A correspondência exata falha com frequência por causa do adjetivo. Em
    "comunidades e povos tradicionais", o parser prende "tradicionais" a
    "povos", então o título produz o candidato `comunidade` — enquanto no
    corpo da redação a mesma ideia aparece como `comunidade tradicional`.
    São o mesmo conceito, e tratá-los como distintos faria a busca pelo
    tema falhar e escolher um conceito qualquer no lugar.

    Por isso: tentativa exata primeiro, e depois casamento pelo NÚCLEO
    NOMINAL, que é a parte estável. O adjetivo é o que varia.
    """
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
    """
    Escolhe o vértice do grafo que melhor representa o tema.

    As três fontes são consultadas em ordem de confiabilidade decrescente:

    1. **título** — o estudante resume ali o que entendeu do tema, em
       poucas palavras e sem ruído;
    2. **enunciado** — o texto motivador da prova, que é o tema oficial mas
       vem longo e cheio de conceitos periféricos;
    3. **introdução** — o primeiro parágrafo, recuo para quando as duas
       primeiras não deram em nada.

    Entre os candidatos que existem no grafo, vence o de maior grau de
    saída. O critério não é arbitrário: o conceito-tema é aquele de que o
    texto *parte*, então ele precisa alcançar coisas. Um candidato com grau
    de saída zero está no texto mas não sustenta argumento nenhum, e usá-lo
    como origem faria o Dijkstra devolver "nada é alcançável" por defeito
    da escolha, não por defeito da redação.
    """
    candidatos_vistos: list[str] = []
    reserva: str | None = None
    reserva_fonte = ""

    for fonte, texto in (("titulo", titulo), ("enunciado", enunciado), ("introducao", introducao)):
        if not texto.strip():
            continue

        candidatos = extrator.conceitos_do_texto(texto)
        candidatos_vistos.extend(c for c in candidatos if c not in candidatos_vistos)

        # posição do candidato no texto, para desempate
        posicao: dict[str, int] = {}
        for i, candidato in enumerate(candidatos):
            for vertice in _casar_com_grafo(candidato, grafo):
                posicao.setdefault(vertice, i)

        if not posicao:
            continue

        # empate no grau de saída se decide pela ordem de aparição no texto
        melhor = max(posicao, key=lambda v: (_grau_de_saida(grafo, v), -posicao[v]))

        if _grau_de_saida(grafo, melhor) > 0:
            return melhor, fonte, candidatos_vistos

        # todos os candidatos desta fonte são folhas: guarda como recuo e
        # continua, porque uma fonte menos confiável pode ter algo melhor
        if reserva is None:
            reserva, reserva_fonte = melhor, fonte

    return reserva, reserva_fonte, candidatos_vistos


# ---------------------------------------------------------------------------
# Proposta de intervenção
# ---------------------------------------------------------------------------

def identificar_propostas(grafo: Grafo, extrator: Extrator, conclusao: str) -> list[str]:
    """
    Conceitos de que trata a proposta de intervenção.

    Duas passadas, da mais específica para a mais tolerante:

    1. conceitos que são **objeto de um verbo de intervenção** — "promover
       a *demarcação*", "garantir o *acesso*". É a proposta propriamente
       dita, e é o alvo certo;
    2. se nenhum verbo de intervenção aparecer, todos os conceitos do
       último parágrafo que existam no grafo. Redação sem proposta clara
       também precisa de diagnóstico, e nesse caso a pergunta vira "o
       fecho tem alguma ligação com o tema?".

    Devolve apenas conceitos presentes no grafo — não adianta buscar
    caminho até um vértice que não existe.
    """
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


# ---------------------------------------------------------------------------
# Atalho
# ---------------------------------------------------------------------------

def identificar(
    extracao: Extracao,
    extrator: Extrator,
    *,
    titulo: str = "",
    enunciado: str = "",
    introducao: str = "",
    conclusao: str = "",
) -> Alvos:
    """Aplica as duas identificações e devolve tudo junto."""
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
