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
    observacao  fato sobre o texto que não é elogio nem alerta
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

O QUE MEDIMOS SOBRE OS CICLOS
----------------------------
Em 400 redações do corpus, ciclo aparece em 3,2% (13 casos). Dessas 13, a
média de Competência 3 é 120, contra 113 nas 387 sem ciclo — ou seja,
levemente MELHOR, o contrário da hipótese inicial. E 8 dos 13 ciclos têm
apenas dois conceitos, o que costuma ser relação mútua legítima ("a pobreza
compromete a educação, e a falta de educação perpetua a pobreza"), não
falácia.

Conclusão: ciclo é `observacao`, não `atencao`. Marcar com alerta seria
inventar um problema que a medição não encontrou.

O PAPEL DO TARJAN, ENTÃO
------------------------
Não é pontuar. É garantir que o indicador de Competência 3 funcione em
TODA redação: sem a condensação dos componentes, o Kahn não ordena grafo
cíclico, e 3,2% dos textos perderiam o único diagnóstico que a validação
sustenta. O SCC é a camada de robustez do indicador principal — que é
exatamente o papel dele no Cormen, cap. 22.5.
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
#: fato sobre o texto, sem juízo — nem elogio nem alerta
OBSERVACAO = "observacao"

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
                 OBSERVACAO: "[observacao]", INDEFINIDO: "[indefinido]"}[self.status]
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
            (a for a in self.conclusivos if a.status in ordem),
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
# Competência 3 — o indicador validado
#
# LINGUAGEM: os textos daqui aparecem na tela para quem escreveu a redação,
# não para quem escreveu o código. Por isso "sequência de ideias" e não
# "ordenação topológica", "argumento em círculo" e não "componente
# fortemente conectado". O termo técnico fica no comentário ao lado.
# ---------------------------------------------------------------------------

def _avaliar_progressao(grafo: Grafo, cadeia: list[str] | None) -> Achado:
    """
    Comprimento da ordenação topológica — o único indicador que a medição
    sustenta: distingue redações bem e mal avaliadas em coerência com 74%
    de acerto no corpus (n=160).
    """
    nome = "encadeamento das ideias"

    if not grafo.num_vertices:
        return Achado(
            3, nome, FALHA,
            "não identificamos nenhuma ideia neste texto. Confira se ele foi "
            "colado por inteiro",
        )

    # cadeia is None = o Kahn não ordena grafo com ciclo; a condensação dos
    # componentes fortemente conectados resolveria
    if cadeia is None:
        return Achado(
            3, nome, INDEFINIDO,
            "não conseguimos calcular a sequência porque há um grupo de ideias que "
            "se puxam (veja abaixo). Isso é limitação do nosso cálculo, não do seu "
            "texto",
        )

    passos = len(cadeia)
    if passos >= CADEIA_MEDIANA_BOA:
        return Achado(
            3, nome, OK,
            f"suas ideias formam uma sequência de {passos} passos, uma puxando a "
            f"outra. Redações bem avaliadas em coerência ficam em torno de "
            f"{CADEIA_MEDIANA_BOA} passos",
        )
    if passos >= CADEIA_CORTE:
        return Achado(
            3, nome, OK,
            f"suas ideias formam uma sequência de {passos} passos, dentro da faixa "
            f"das redações bem avaliadas em coerência",
        )
    return Achado(
        3, nome, ATENCAO,
        f"suas ideias formam uma sequência de apenas {passos} passos. Nas redações "
        f"que analisamos, abaixo de {CADEIA_CORTE} costuma indicar ideias que "
        f"aparecem soltas, sem uma levar à outra",
    )


def _avaliar_lacos(lacos: list[list[str]], extracao: Extracao) -> Achado | None:
    """
    Componentes fortemente conectados com mais de um vértice (Tarjan).

    `observacao`, nunca `atencao`: ver a medição no topo do módulo — ciclo
    não se correlacionou com coerência pior, e a maioria tem dois conceitos,
    o que é relação mútua e não falácia.
    """
    if not lacos:
        return None

    evidencias = [
        " ⇄ ".join(extracao.exibir(c) for c in laco) for laco in lacos
    ]
    plural = "s" if len(lacos) > 1 else ""
    return Achado(
        3, "ideias que se puxam", OBSERVACAO,
        f"{len(lacos)} grupo{plural} de ideias em que cada uma aparece como causa da "
        f"outra, formando um vai e vem. Isso não é erro — muitas vezes é o ciclo que "
        f"você quis descrever. Vale reler só para confirmar que foi de propósito",
        evidencias,
    )


# ---------------------------------------------------------------------------
# Competências 2 e 5 — calculadas e mostradas, sem virar juízo
# ---------------------------------------------------------------------------

def _avaliar_tema(grafo: Grafo, alvos: Alvos, extracao: Extracao) -> tuple[Achado, list[str]]:
    """
    Alcance do conceito-tema (Dijkstra a partir dele).

    Fica `indefinido` porque a fragmentação do grafo limita o alcance a
    cerca de um terço dos vértices mesmo em redação boa — o número não
    discrimina.
    """
    nome = "ligação com o tema"

    if alvos.tema is None:
        return (
            Achado(
                2, nome, INDEFINIDO,
                "não conseguimos identificar qual ideia do texto representa o tema. "
                "Preencher o campo de título costuma resolver",
            ),
            list(grafo.vertices),
        )

    alcancadas = orbita(grafo, alvos.tema)  # distâncias a partir do tema
    soltas = [v for v in grafo.vertices if v not in alcancadas]

    return (
        Achado(
            2, nome, INDEFINIDO,
            f"a ideia central '{extracao.exibir(alvos.tema)}' se conecta a "
            f"{len(alcancadas)} das {grafo.num_vertices} ideias do texto. Ainda não "
            f"sabemos ler esse número: nas redações que analisamos ele fica baixo "
            f"mesmo em textos bem avaliados",
            [extracao.exibir(o) for o in soltas[:6]],
        ),
        soltas,
    )


def _avaliar_proposta(
    grafo: Grafo, alvos: Alvos, caminho: ResultadoTemaProposta | None, extracao: Extracao
) -> Achado:
    """
    Caminho mínimo (Dijkstra) do conceito-tema até os conceitos da proposta.

    Não achar proposta é achado sobre o TEXTO, e vale como falha. Não achar
    caminho é, na maioria dos casos, limitação da modelagem — fica
    `indefinido`.
    """
    nome = "proposta de intervenção"

    if not alvos.propostas:
        return Achado(
            5, nome, FALHA,
            "não encontramos uma proposta de intervenção no último parágrafo",
        )

    if caminho is None or not caminho.alcancavel:
        return Achado(
            5, nome, INDEFINIDO,
            "não encontramos um encadeamento de ideias ligando o tema à sua proposta. "
            "Na maioria das redações isso é limitação da nossa análise, e não do texto",
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

    # Reportar só a proposta mais próxima infla o resultado: bastaria UMA ideia
    # do fecho estar ligada ao tema para o laudo soar aprovado. O denominador
    # tem que aparecer.
    total = len(caminho.custos_por_proposta) or 1
    ligadas = sum(1 for c in caminho.custos_por_proposta.values() if c < float("inf"))
    status = OK if ligadas == total else ATENCAO

    passos = max(len(conceitos) - 1, 0)
    detalhe = (
        f"{ligadas} de {total} ideia(s) da sua proposta se ligam ao tema. A mais "
        f"próxima é '{extracao.exibir(caminho.melhor_proposta or '')}', a {passos} "
        f"ligação(ões) de distância"
    )
    if ligadas < total:
        desligadas = [
            extracao.exibir(pr)
            for pr, c in caminho.custos_por_proposta.items()
            if c == float("inf")
        ]
        detalhe += f". Sem ligação com o tema: {', '.join(desligadas[:4])}"

    return Achado(5, nome, status, detalhe, evidencias)


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
    OBSERVACAO: "[ observacao ]",
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

    # vértices · arestas · cobertura da extração · comprimento da ordenação
    sequencia = "—" if d.cadeia is None else str(d.tamanho_da_cadeia)
    print(f"{d.num_conceitos} ideias · {d.num_relacoes} ligações · "
          f"{d.cobertura:.0%} das frases aproveitadas · "
          f"sequência de {sequencia} passos")
    if d.alvos.tema:
        print(f"ideia central: {d.exibir(d.alvos.tema)} "
              f"(a partir do {d.alvos.origem_do_tema})")
    print()

    for achado in d.achados:
        print(f"{_MARCAS[achado.status]} C{achado.competencia} · {achado.nome}")
        print(f"                {achado.resumo}")
        for evidencia in achado.evidencias[:3]:
            recorte = evidencia if len(evidencia) <= 95 else evidencia[:92] + "..."
            print(f"                  · {recorte}")
        print()

    indefinidos = len(d.achados) - len(d.conclusivos)
    if indefinidos:
        print(f"{indefinidos} dos {len(d.achados)} pontos acima ficaram sem veredito: "
              f"testamos esses indicadores em 160 redações já corrigidas")
        print("e eles não separaram texto bom de ruim, então mostramos o número sem julgar.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys

    raise SystemExit(_main(sys.argv))
