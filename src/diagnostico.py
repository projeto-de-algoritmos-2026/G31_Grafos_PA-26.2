"""Diagnóstico da redação: onde os algoritmos viram avaliação."""
from __future__ import annotations

from dataclasses import dataclass, field

from src.alvos import Alvos, identificar
from src.analise import (Condensacao, cadeia_argumentativa,
                         ciclos_argumentativos, condensar, maior_caminho_dag,
                         rastrear_caminho, tarjan)
from src.caminhos import ResultadoTemaProposta, caminho_tema_proposta, orbita
from src.extracao import Extracao, Extrator
from src.grafo import Grafo

OK = "ok"
ATENCAO = "atencao"
FALHA = "falha"
INDEFINIDO = "indefinido"
OBSERVACAO = "observacao"

# Medido no Essay-BR, n=160: contar as ideias que o texto sustenta separa os
# grupos de C3 com 73% de acerto neste corte. Contar sobre o grafo CONDENSADO
# é o que faz o número existir também nas redações com laço.
CADEIA_CORTE = 20

CADEIA_MEDIANA_BOA = 29

# Profundidade: o maior caminho no grafo condensado separa os mesmos grupos com
# apenas 61%. É fraco, e por isso vira observação, nunca veredito.
MAIOR_CAMINHO_CORTE = 4


_EXTENSO = ("nenhum", "um", "dois", "três", "quatro", "cinco",
            "seis", "sete", "oito", "nove", "dez")


#: "uma ligação", não "um ligação" — só um e dois flexionam em português
_EXTENSO_F = {0: "nenhuma", 1: "uma", 2: "duas"}


def frase(texto: str) -> str:
    """
    Maiúscula inicial e ponto final, na hora de exibir.

    Os textos dos achados são escritos em minúscula e sem ponto porque também
    aparecem emendados depois do nome do achado ("progressão — suas ideias...").
    Quem os mostra como parágrafo solto chama esta função; assim a pontuação é
    decisão de quem exibe, e não fica presa dentro de cada mensagem.
    """
    if not texto:
        return texto
    texto = texto[:1].upper() + texto[1:]
    return texto if texto[-1] in ".!?:" else texto + "."


def _numero(n: int, *, feminino: bool = False) -> str:
    """Número por extenso até dez; acima disso, algarismo."""
    if not 0 <= n <= 10:
        return str(n)
    return _EXTENSO_F[n] if feminino and n in _EXTENSO_F else _EXTENSO[n]


def _quantia(n: int, singular: str, plural: str | None = None, *,
             feminino: bool = False) -> str:
    """
    "1 grupo" lê como planilha; "um grupo" lê como frase. Números até dez
    vão por extenso, o resto em algarismo — convenção de texto corrido.
    """
    # "nenhuma ligação", não "nenhuma ligações": zero pede singular em português
    substantivo = singular if n in (0, 1) else (plural or singular + "s")
    return f"{_numero(n, feminino=feminino)} {substantivo}"


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

    def __str__(self) -> str:
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
    condensacao: Condensacao | None = None
    maior_caminho: list[str] | None = None

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

    @property
    def tamanho_maior_caminho(self) -> int:
        """Passos da maior cadeia do grafo condensado — sobrevive a ciclo."""
        return len(self.maior_caminho) if self.maior_caminho else 0

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


def _avaliar_progressao(grafo: Grafo, cadeia: list[str] | None) -> Achado:
    """Quantas ideias distintas o texto sustenta — o indicador com 73% de acerto."""
    nome = "quantidade de ideias sustentadas"

    if not grafo.num_vertices:
        return Achado(
            3, nome, FALHA,
            "não identificamos nenhuma ideia neste texto. Confira se ele foi "
            "colado por inteiro",
        )

    ideias = len(cadeia) if cadeia else 0
    if ideias >= CADEIA_MEDIANA_BOA:
        return Achado(
            3, nome, OK,
            f"sua redação desenvolve {ideias} ideias distintas. Redações bem "
            f"avaliadas em coerência ficam em torno de {CADEIA_MEDIANA_BOA}",
        )
    if ideias >= CADEIA_CORTE:
        return Achado(
            3, nome, OK,
            f"sua redação desenvolve {ideias} ideias distintas, dentro da faixa "
            f"das redações bem avaliadas em coerência",
        )
    return Achado(
        3, nome, ATENCAO,
        f"sua redação desenvolve apenas {ideias} ideias distintas. Nas redações "
        f"que analisamos, abaixo de {CADEIA_CORTE} costuma indicar um texto que "
        f"repete o mesmo ponto em vez de avançar",
    )


def _avaliar_encadeamento(maior_caminho: list[str] | None) -> Achado:
    """Profundidade: o maior caminho. Sempre observação — só 61% de acerto."""
    nome = "profundidade do encadeamento"
    passos = max(len(maior_caminho) - 1, 0) if maior_caminho else 0

    return Achado(
        3, nome, OBSERVACAO,
        f"a sua ideia mais desenvolvida encadeia {_quantia(passos, 'passo')} — uma ideia "
        f"levando à outra, em sequência. Medimos isso em 160 redações corrigidas e "
        f"ele acerta pouco ({_quantia(MAIOR_CAMINHO_CORTE, 'passo')} separam os grupos "
        f"com só 61%), então mostramos o número sem transformar em nota",
    )


def _avaliar_lacos(lacos: list[list[str]], extracao: Extracao) -> Achado | None:
    """Componentes fortemente conectados com mais de um vértice (Tarjan)."""
    if not lacos:
        return None

    evidencias = [
        " ⇄ ".join(extracao.exibir(c) for c in laco) for laco in lacos
    ]
    return Achado(
        3, "ideias que se puxam", OBSERVACAO,
        f"{_quantia(len(lacos), 'grupo')} de ideias em que cada uma aparece como causa da "
        f"outra, formando um vai e vem. Isso não é erro — muitas vezes é o ciclo que "
        f"você quis descrever. Vale reler só para confirmar que foi de propósito",
        evidencias,
    )


def _avaliar_tema(grafo: Grafo, alvos: Alvos, extracao: Extracao) -> tuple[Achado, list[str]]:
    """Alcance do conceito-tema (Dijkstra a partir dele)."""
    # aparece como "Competência 2 — compreensão do tema · alcance da ideia
    # central": o nome do achado não pode repetir o da competência
    nome = "alcance da ideia central"

    if alvos.tema is None:
        return (
            Achado(
                2, nome, INDEFINIDO,
                "não conseguimos identificar qual ideia do texto representa o tema. "
                "Preencher o campo de título costuma resolver",
            ),
            list(grafo.vertices),
        )

    alcancadas = orbita(grafo, alvos.tema)
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


def _ligacao_ao_tema(ligadas: int, total: int) -> str:
    """"três de três ideias" soa a relatório; quando são todas, diga todas."""
    if ligadas == total:
        if total == 1:
            return "a única ideia da sua proposta se liga ao tema"
        return f"todas as {_quantia(total, 'ideia', feminino=True)} da sua proposta se ligam ao tema"
    verbo = "se liga" if ligadas == 1 else "se ligam"
    return (f"{_numero(ligadas, feminino=True)} de "
            f"{_quantia(total, 'ideia', feminino=True)} da sua proposta {verbo} ao tema")


def _avaliar_proposta(
    grafo: Grafo, alvos: Alvos, caminho: ResultadoTemaProposta | None, extracao: Extracao
) -> Achado:
    """Caminho mínimo (Dijkstra) do conceito-tema até os conceitos da proposta."""
    # idem: ao lado de "Competência 5 — proposta de intervenção"
    nome = "ligação com o tema"

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
    # Com uma aresta só, este resumo seria idêntico à linha detalhada logo
    # abaixo ("A → B: frase"). Só vale a pena quando há mais de um salto.
    evidencias = [" → ".join(conceitos)] if len(conceitos) > 2 else []

    if caminho.caminho and len(caminho.caminho) > 1:
        rastro = rastrear_caminho(grafo, caminho.caminho)
        for origem, destino, frases in rastro.arestas_frases:
            if frases:
                evidencias.append(
                    f"{extracao.exibir(origem)} → {extracao.exibir(destino)}: {frases[0]}"
                )

    total = len(caminho.custos_por_proposta) or 1
    ligadas = sum(1 for c in caminho.custos_por_proposta.values() if c < float("inf"))
    status = OK if ligadas == total else ATENCAO

    passos = max(len(conceitos) - 1, 0)
    detalhe = (
        f"{_ligacao_ao_tema(ligadas, total)}. A mais próxima é "
        f"'{extracao.exibir(caminho.melhor_proposta or '')}'"
        + (", que é o próprio tema" if passos == 0 else
           f", a {_quantia(passos, 'ligação', 'ligações', feminino=True)} de distância")
    )
    if ligadas < total:
        desligadas = [
            extracao.exibir(pr)
            for pr, c in caminho.custos_por_proposta.items()
            if c == float("inf")
        ]
        detalhe += f". Sem ligação com o tema: {', '.join(desligadas[:4])}"

    return Achado(5, nome, status, detalhe, evidencias)


def diagnosticar(
    texto: str,
    *,
    titulo: str = "",
    enunciado: str = "",
    extrator: Extrator | None = None,
) -> Diagnostico:
    """Analisa uma redação de ponta a ponta."""
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

    # A condensação vem antes de propósito: sobre ela o Kahn sempre ordena, então
    # o indicador de C3 existe em toda redação, inclusive nas que têm laço.
    condensacao = condensar(grafo, tarjan(grafo))
    cadeia = cadeia_argumentativa(condensacao.grafo)
    maior_caminho = maior_caminho_dag(condensacao.grafo)

    caminho = None
    if alvos.tema is not None and alvos.propostas:
        caminho = caminho_tema_proposta(grafo, alvos.tema, alvos.propostas)

    achado_tema, orfaos = _avaliar_tema(grafo, alvos, extracao)

    achados = [_avaliar_progressao(grafo, cadeia),
               _avaliar_encadeamento(maior_caminho)]
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
        condensacao=condensacao,
        maior_caminho=maior_caminho,
    )


_MARCAS = {
    OK: "[ ok         ]",
    ATENCAO: "[ atencao    ]",
    FALHA: "[ falha      ]",
    OBSERVACAO: "[ observacao ]",
    INDEFINIDO: "[ indefinido ]",
}


def _main(argv: list[str]) -> int:
    import sys
    import textwrap

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

    profundidade = max(d.tamanho_maior_caminho - 1, 0)
    print(f"{d.num_conceitos} ideias · {d.num_relacoes} ligações · "
          f"{d.cobertura:.0%} das frases aproveitadas · "
          f"maior encadeamento de {profundidade} passos")
    if d.alvos.tema:
        print(f"ideia central: {d.exibir(d.alvos.tema)} "
              f"(a partir do {d.alvos.origem_do_tema})")
    print()

    for achado in d.achados:
        print(f"{_MARCAS[achado.status]} C{achado.competencia} · {achado.nome}")
        print(f"                {frase(achado.resumo)}")
        for evidencia in achado.evidencias[:3]:
            recorte = evidencia if len(evidencia) <= 95 else evidencia[:92] + "..."
            print(f"                  · {recorte}")
        print()

    indefinidos = len(d.achados) - len(d.conclusivos)
    if indefinidos:
        verbo = "ficou" if indefinidos == 1 else "ficaram"
        total_pontos = _numero(len(d.achados))
        aviso = (
            f"{_quantia(indefinidos, 'ponto')} dos {total_pontos} acima {verbo} sem "
            "veredito: testamos esses indicadores em 160 redações já corrigidas e eles "
            "não separaram texto bom de ruim, então mostramos o número sem julgar."
        )
        print(textwrap.fill(frase(aviso), width=88))
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_main(sys.argv))
