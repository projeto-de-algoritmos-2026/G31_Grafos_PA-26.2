
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

CADEIA_MEDIANA_BOA = 29
 
 
@dataclass
class Achado:

    competencia: int
    nome: str
    status: str
    resumo: str
    evidencias: list[str] = field(default_factory=list)
 
    @property
    def conclusivo(self) -> bool:
        return self.status != INDEFINIDO

    def __str__(self) -> str:
        marca = {OK: "[ok]", ATENCAO: "[atencao]", FALHA: "[falha]",
                 OBSERVACAO: "[observacao]", INDEFINIDO: "[indefinido]"}[self.status]
        return f"{marca} C{self.competencia} {self.nome} — {self.resumo}"
 
 
@dataclass
class Diagnostico:

    extracao: Extracao
    alvos: Alvos
    lacos: list[list[str]] = field(default_factory=list)
    cadeia: list[str] | None = None
    caminho: ResultadoTemaProposta | None = None
    orfaos: list[str] = field(default_factory=list)
    achados: list[Achado] = field(default_factory=list)

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
        return self.extracao.cobertura
 
    @property
    def tamanho_da_cadeia(self) -> int:
        return len(self.cadeia) if self.cadeia else 0
 
    @property
    def tamanho_maior_caminho(self) -> int:
        return len(self.maior_caminho) if self.maior_caminho else 0
 
    def exibir(self, chave: str) -> str:
        return self.extracao.exibir(chave)
 
    def achados_de(self, competencia: int) -> list[Achado]:
        return [a for a in self.achados if a.competencia == competencia]
 
    @property
    def conclusivos(self) -> list[Achado]:
        return [a for a in self.achados if a.conclusivo]
 
    @property
    def problemas(self) -> list[Achado]:
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

    nome = "encadeamento das ideias"
 
    if not grafo.num_vertices:
        return Achado(
            3, nome, FALHA,
            "não identificamos nenhuma ideia neste texto. Confira se ele foi "
            "colado por inteiro",
        )

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
 
 
def _avaliar_proposta(
    grafo: Grafo, alvos: Alvos, caminho: ResultadoTemaProposta | None, extracao: Extracao
) -> Achado:

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

def diagnosticar(
    texto: str,
    *,
    titulo: str = "",
    enunciado: str = "",
    extrator: Extrator | None = None,
) -> Diagnostico:

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
 
    condensacao = condensar(grafo, tarjan(grafo))
    maior_caminho = maior_caminho_dag(condensacao.grafo)
 
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

if __name__ == "__main__":
    import sys
 
    raise SystemExit(_main(sys.argv))
 
