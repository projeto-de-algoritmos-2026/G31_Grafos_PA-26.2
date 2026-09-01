"""
Diagnóstico da redação: onde os algoritmos viram avaliação.

Este módulo é a junção do projeto. Recebe o texto de uma redação e devolve
um laudo estruturado, atravessando o pipeline inteiro:

    texto
      -> extracao.py   grafo direcionado de conceitos
      -> alvos.py      qual conceito é o tema, quais são a proposta
      -> analise.py    Tarjan (laços) e Kahn (cadeia argumentativa)
      -> caminhos.py   Dijkstra a partir do tema
      -> aqui          tudo isso traduzido para as competências do ENEM

A tradução é o ponto do trabalho. Um componente fortemente conectado não
diz nada a um estudante; "estes três conceitos se justificam em círculo,
olha as frases" diz.

O QUE ESTE MÓDULO AFIRMA E O QUE NÃO AFIRMA
-------------------------------------------
Cada veredito abaixo foi calibrado contra o corpus Essay-BR, e o módulo só
emite juízo onde a medição sustenta:

    ok          nada a apontar
    atencao     há indício, mas a decisão é de quem escreveu
    falha       problema objetivo na estrutura do texto
    indefinido  a modelagem atual não permite concluir

O `indefinido` não é evasiva, é resultado. Medimos, no corpus:

  * COMPETÊNCIA 3 — a cadeia argumentativa FUNCIONA como indicador.
    Redações bem avaliadas em coerência têm mediana de 29 conceitos
    encadeados; as mal avaliadas, 18. Um corte simples em 20 conceitos
    separa os dois grupos com 74% de acerto (n=160).

  * COMPETÊNCIAS 2 e 5 — NÃO funcionam com esta modelagem. O grafo de uma
    redação fica fragmentado em ~6 componentes, e o maior deles segura só
    um terço dos conceitos, porque relações causais expressas dentro de
    frases isoladas não encadeiam um texto inteiro. Consequência: o caminho
    do tema até a proposta quase nunca existe — e, quando existe, aparece
    MAIS nas redações mal avaliadas em C5 (23%) do que nas bem avaliadas
    (12%). A métrica estava medindo fragmentação, não qualidade.

    Duas tentativas de correção foram medidas e descartadas: arestas por
    conectivo discursivo e vértices menos específicos levaram o maior
    componente de 28% para 34% dos conceitos, o que não muda a conclusão.

    Por isso o módulo continua CALCULANDO e MOSTRANDO o caminho tema →
    proposta, que é informativo quando existe, mas não o converte em nota.

Laço argumentativo é sempre `atencao`, nunca `falha`: ciclos viciosos
existem no mundo real e um autor pode estar descrevendo um de propósito
("a pobreza gera baixa escolaridade, que gera pobreza"). A ferramenta
detecta e aponta; quem lê decide.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.alvos import Alvos, identificar
from src.analise import cadeia_argumentativa, ciclos_argumentativos, rastrear_caminho
from src.caminhos import ResultadoTemaProposta, caminho_tema_proposta, orbita
from src.extracao import Extracao, Extrator
from src.grafo import Grafo

OK = "ok"
ATENCAO = "atencao"
FALHA = "falha"
INDEFINIDO = "indefinido"

#: Corte que melhor separa os dois grupos de Competência 3 no Essay-BR:
#: 74% de acerto sobre 160 redações (80 com C3 >= 160, 80 com C3 <= 80).
CADEIA_CORTE = 20

#: Mediana da cadeia nas redações bem avaliadas em C3. Serve de referência
#: para o texto do laudo, não de limiar.
CADEIA_MEDIANA_BOA = 29


@dataclass
class Achado:
    """Uma constatação sobre uma competência, com o que a sustenta."""

    competencia: int
    nome: str
    status: str
    resumo: str
    evidencias: list[str] = field(default_factory=list)

    @property
    def conclusivo(self) -> bool:
        """Falso quando a modelagem não permite emitir juízo."""
        return self.status != INDEFINIDO

    def __str__(self) -> str:  # pragma: no cover - only for debugging
        marca = {OK: "[ok]", ATENCAO: "[atencao]", FALHA: "[falha]",
                 INDEFINIDO: "[indefinido]"}[self.status]
        return f"{marca} C{self.competencia} {self.nome} — {self.resumo}"


@dataclass
class Diagnostico:
    """O laudo completo de uma redação."""

    extracao: Extracao
    alvos: Alvos
    lacos: list[list[str]] = field(default_factory=list)
    cadeia: list[str] | None = None
    caminho: ResultadoTemaProposta | None = None
    orfaos: list[str] = field(default_factory=list)
    achados: list[Achado] = field(default_factory=list)

    # -- atalhos -----------------------------------------------------------

    @property
    def grafo(self) -> Grafo:
        return self.extracao.grafo

    @property
    def num_conceitos(self) -> int:
        return self.grafo.num_vertices

    @property
    def num_relacoes(self) -> int:
        return self.grafo.num_arestas

    @property
    def cobertura(self) -> float:
        """Fração das frases da redação que virou aresta no grafo."""
        return self.extracao.cobertura

    @property
    def tamanho_da_cadeia(self) -> int:
        return len(self.cadeia) if self.cadeia else 0

    def exibir(self, chave: str) -> str:
        """Nome legível de um conceito."""
        return self.extracao.exibir(chave)

    def achados_de(self, competencia: int) -> list[Achado]:
        return [a for a in self.achados if a.competencia == competencia]

    @property
    def conclusivos(self) -> list[Achado]:
        """Só os achados que a medição sustenta."""
        return [a for a in self.achados if a.conclusivo]

    @property
    def problemas(self) -> list[Achado]:
        """Achados conclusivos que não são `ok`, do mais grave para o menos."""
        ordem = {FALHA: 0, ATENCAO: 1}
        return sorted(
            (a for a in self.conclusivos if a.status != OK),
            key=lambda a: ordem[a.status],
        )

    def resumo(self) -> str:
        linhas = [
            f"{self.num_conceitos} conceitos, {self.num_relacoes} relações, "
            f"cobertura {self.cobertura:.0%}"
        ]
        linhas += [str(a) for a in self.achados]
        return "\n".join(linhas)


# ---------------------------------------------------------------------------
# Competência 3 — coerência e progressão (validada)
# ---------------------------------------------------------------------------

def _avaliar_progressao(grafo: Grafo, cadeia: list[str] | None) -> Achado:
    """
    O indicador que a medição sustenta.

    O comprimento da cadeia argumentativa — a ordenação topológica do grafo
    — distingue redações bem e mal avaliadas em coerência com 74% de acerto
    no corpus. Não é um classificador; é um indicador com força medida, e o
    laudo diz isso em vez de fingir precisão.
    """
    nome = "progressão"

    if not grafo.num_vertices:
        return Achado(3, nome, FALHA, "nenhum conceito foi extraído do texto")

    if cadeia is None:
        return Achado(
            3, nome, INDEFINIDO,
            "a cadeia não pôde ser ordenada porque o grafo tem ciclos — "
            "a condensação dos componentes resolve isso",
        )

    tamanho = len(cadeia)
    if tamanho >= CADEIA_MEDIANA_BOA:
        return Achado(
            3, nome, OK,
            f"cadeia de {tamanho} conceitos encadeados, acima da mediana das "
            f"redações bem avaliadas em coerência ({CADEIA_MEDIANA_BOA})",
        )
    if tamanho >= CADEIA_CORTE:
        return Achado(
            3, nome, OK,
            f"cadeia de {tamanho} conceitos encadeados, dentro da faixa das "
            f"redações bem avaliadas em coerência",
        )
    return Achado(
        3, nome, ATENCAO,
        f"cadeia de apenas {tamanho} conceitos. No corpus, redações abaixo de "
        f"{CADEIA_CORTE} conceitos encadeados costumam receber nota baixa em "
        f"coerência — as ideias aparecem sem se encadear umas nas outras",
    )


def _avaliar_lacos(lacos: list[list[str]], extracao: Extracao) -> Achado | None:
    """Laço argumentativo, quando existe. Aponta, não condena."""
    if not lacos:
        return None

    evidencias = [
        " → ".join(extracao.exibir(c) for c in laco) + " → (volta ao início)"
        for laco in lacos
    ]
    plural = "s" if len(lacos) > 1 else ""
    return Achado(
        3, "circularidade", ATENCAO,
        f"{len(lacos)} laço{plural} argumentativo{plural}: o texto retoma como "
        f"justificativa um ponto que ele mesmo derivou. Confira se é um ciclo "
        f"que você quis descrever.",
        evidencias,
    )


# ---------------------------------------------------------------------------
# Competências 2 e 5 — calculadas, reportadas, não convertidas em juízo
# ---------------------------------------------------------------------------

def _avaliar_tema(grafo: Grafo, alvos: Alvos, extracao: Extracao) -> tuple[Achado, list[str]]:
    """
    Competência 2 — alcance do tema.

    Reporta quantos conceitos são atingíveis a partir do conceito-tema. O
    número é informativo para quem olha o grafo, mas não vira veredito: a
    fragmentação limita o alcance a cerca de um terço dos conceitos mesmo
    em redações boas.
    """
    nome = "alcance do tema"

    if alvos.tema is None:
        return (
            Achado(2, nome, INDEFINIDO,
                   "não foi possível identificar, no grafo, o conceito que representa o tema"),
            list(grafo.vertices),
        )

    distancias = orbita(grafo, alvos.tema)
    orfaos = [v for v in grafo.vertices if v not in distancias]
    alcance = len(distancias) / grafo.num_vertices if grafo.num_vertices else 0.0

    return (
        Achado(
            2, nome, INDEFINIDO,
            f"o tema '{extracao.exibir(alvos.tema)}' alcança {len(distancias)} dos "
            f"{grafo.num_vertices} conceitos ({alcance:.0%}). O grafo é fragmentado por "
            f"limitação da extração, então este número não distingue redação boa de ruim",
            [extracao.exibir(o) for o in orfaos[:6]],
        ),
        orfaos,
    )


def _avaliar_proposta(
    grafo: Grafo, alvos: Alvos, caminho: ResultadoTemaProposta | None, extracao: Extracao
) -> Achado:
    """
    Competência 5 — proposta de intervenção.

    Não ter identificado proposta nenhuma no último parágrafo é um achado
    sobre o TEXTO, e vale como falha. Já a ausência de caminho entre tema e
    proposta é, na maior parte dos casos, limitação da modelagem — por isso
    fica `indefinido`, com o caminho ainda calculado e exibido quando existe.
    """
    nome = "proposta de intervenção"

    if not alvos.propostas:
        return Achado(
            5, nome, FALHA,
            "nenhuma proposta de intervenção foi identificada no último parágrafo",
        )

    if caminho is None or not caminho.alcancavel:
        return Achado(
            5, nome, INDEFINIDO,
            "não há caminho no grafo entre o tema e a proposta. Na maioria das "
            "redações isso reflete a fragmentação do grafo, não a redação",
            [extracao.exibir(p) for p in alvos.propostas[:4]],
        )

    conceitos = [extracao.exibir(c) for c in (caminho.caminho or [])]
    evidencias = [" → ".join(conceitos)] if conceitos else []

    if caminho.caminho and len(caminho.caminho) > 1:
        rastro = rastrear_caminho(grafo, caminho.caminho)
        for origem, destino, frases in rastro.arestas_frases:
            if frases:
                evidencias.append(
                    f"{extracao.exibir(origem)} → {extracao.exibir(destino)}: {frases[0]}"
                )

    return Achado(
        5, nome, OK,
        f"a proposta '{extracao.exibir(caminho.melhor_proposta or '')}' se liga ao tema "
        f"por {len(conceitos) - 1} relação(ões), custo {caminho.custo:.2f}",
        evidencias,
    )


# ---------------------------------------------------------------------------
# Orquestração
# ---------------------------------------------------------------------------

def diagnosticar(
    texto: str,
    *,
    titulo: str = "",
    enunciado: str = "",
    extrator: Extrator | None = None,
) -> Diagnostico:
    """
    Analisa uma redação de ponta a ponta.

    `titulo` e `enunciado` ajudam a achar o conceito-tema; sem eles, o
    primeiro parágrafo é o recuo. A conclusão é sempre o último parágrafo —
    é a estrutura obrigatória do gênero que torna isso confiável.

    Passar um `extrator` já construído evita recarregar o modelo do spaCy a
    cada redação, o que importa ao rodar sobre o corpus inteiro.
    """
    extrator = extrator or Extrator()
    extracao = extrator.extrair(texto)
    grafo = extracao.grafo

    paragrafos = [p.strip() for p in texto.split("\n\n") if p.strip()]
    introducao = paragrafos[0] if paragrafos else ""
    conclusao = paragrafos[-1] if paragrafos else ""

    alvos = identificar(
        extracao, extrator,
        titulo=titulo, enunciado=enunciado,
        introducao=introducao, conclusao=conclusao,
    )

    lacos = [sorted(c) for c in ciclos_argumentativos(grafo)]
    cadeia = cadeia_argumentativa(grafo)

    caminho = None
    if alvos.tema is not None and alvos.propostas:
        caminho = caminho_tema_proposta(grafo, alvos.tema, alvos.propostas)

    achado_tema, orfaos = _avaliar_tema(grafo, alvos, extracao)

    achados = [_avaliar_progressao(grafo, cadeia)]
    laco = _avaliar_lacos(lacos, extracao)
    if laco is not None:
        achados.append(laco)
    achados.append(achado_tema)
    achados.append(_avaliar_proposta(grafo, alvos, caminho, extracao))

    return Diagnostico(
        extracao=extracao,
        alvos=alvos,
        lacos=lacos,
        cadeia=cadeia,
        caminho=caminho,
        orfaos=orfaos,
        achados=achados,
    )


# ---------------------------------------------------------------------------
# Execução direta, para inspecionar o laudo de um texto
#
#     python -m src.diagnostico data/exemplo_sintetico_com_laco.txt
#     python -m src.diagnostico data/exemplo_sintetico_com_laco.txt "Título da redação"
# ---------------------------------------------------------------------------

_MARCAS = {
    OK: "[ ok         ]",
    ATENCAO: "[ atencao    ]",
    FALHA: "[ falha      ]",
    INDEFINIDO: "[ indefinido ]",
}


def _main(argv: list[str]) -> int:
    import sys

    if not 2 <= len(argv) <= 3:
        print("uso: python -m src.diagnostico <arquivo.txt> [titulo]", file=sys.stderr)
        return 2

    caminho = argv[1]
    titulo = argv[2] if len(argv) == 3 else ""

    try:
        texto = open(caminho, encoding="utf-8").read()
    except OSError as erro:
        print(f"não consegui ler {caminho}: {erro}", file=sys.stderr)
        return 1

    d = diagnosticar(texto, titulo=titulo)

    print(f"{d.num_conceitos} conceitos · {d.num_relacoes} relações · "
          f"cobertura {d.cobertura:.0%} · cadeia de {d.tamanho_da_cadeia}")
    if d.alvos.tema:
        print(f"tema identificado: {d.exibir(d.alvos.tema)} (do {d.alvos.origem_do_tema})")
    print()

    for achado in d.achados:
        print(f"{_MARCAS[achado.status]} C{achado.competencia} · {achado.nome}")
        print(f"                {achado.resumo}")
        for evidencia in achado.evidencias[:3]:
            recorte = evidencia if len(evidencia) <= 95 else evidencia[:92] + "..."
            print(f"                  · {recorte}")
        print()

    conclusivos = len(d.conclusivos)
    print(f"{conclusivos} de {len(d.achados)} achados são conclusivos; "
          f"o restante depende de modelagem que esta versão não sustenta.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys

    raise SystemExit(_main(sys.argv))
