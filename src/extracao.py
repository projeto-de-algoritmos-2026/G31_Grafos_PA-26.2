"""
Extração do grafo de conceitos a partir do texto da redação.

Implementado do zero para a disciplina de Projeto de Algoritmos (UnB/FGA).

COMO O TEXTO VIRA GRAFO
-----------------------
O spaCy devolve, para cada frase, uma árvore de dependências sintáticas:
cada palavra aponta para seu núcleo através de uma relação rotulada. Este
módulo lê essa árvore e produz arestas direcionadas entre conceitos.

REGRA BASE
    Para cada verbo, o substantivo que é seu sujeito (`nsubj`) recebe uma
    aresta para o substantivo que é seu objeto (`obj`, `obl`, ...).

        "a expansão do agronegócio provoca a expulsão de povos indígenas"

        expansão --nsubj--> provoca <--obj-- expulsão
                          |
                          v
                  agronegócio -> expulsão

    A sintaxe do português coloca a causa na posição de sujeito na
    esmagadora maioria das construções argumentativas: "X provoca Y",
    "X gera Y", "X compromete Y", "X aprofunda Y".

A regra base sozinha perde arestas importantes. Este módulo aplica quatro
refinamentos, cada um documentado na função que o implementa:

    (a) substantivo leve      -> `_nucleo_semantico`
    (b) oração relativa       -> `_resolver_pronome`
    (c) aposto entre vírgulas -> `_sujeitos_do_verbo`
    (d) coordenação           -> `_expandir_coordenados` e `_sujeitos_do_verbo`
    (e) verbo subordinado     -> `_herdar_sujeitos`
    (f) verbo mal etiquetado  -> `_e_nucleo_verbal`
    (g) coesão entre frases   -> `_abre_com_conectivo` e `_conceito_principal`

Os refinamentos (a) a (f) recuperam arestas perdidas DENTRO de uma frase.
O (g) é diferente: liga frases VIZINHAS quando a segunda abre marcando
consequência ("portanto", "dessa forma").

Sobre o (g), o que foi medido em 50 redações do corpus: ele levou o maior
componente do grafo de 28% para 34% dos conceitos. Pouco. Conectivos
consecutivos em início de frase são raros — uma ou duas ocorrências por
redação —, então entram poucas arestas. Ele fica no código porque a relação
que captura é real e a direção é segura, mas NÃO resolve a fragmentação do
grafo. Relações causais expressas dentro de frases isoladas não encadeiam
uma redação inteira; essa é uma limitação da modelagem, documentada no
README.

O spaCy é usado aqui apenas como SENSOR: ele transforma texto em arestas.
Toda a modelagem do grafo e todos os algoritmos que operam sobre ele são
implementação própria (ver `src/grafo.py`, `src/scc.py`, ...).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterator

from src.grafo import Grafo

MODELO_PADRAO = "pt_core_news_sm"


# ---------------------------------------------------------------------------
# Vocabulário de apoio
# ---------------------------------------------------------------------------

#: Substantivos que não são conceitos, e sim operadores sobre um conceito.
#: "a ausência de políticas públicas" fala de políticas públicas, não de
#: ausência. O valor é a polaridade que o operador imprime na relação.
SUBSTANTIVOS_LEVES: dict[str, int] = {
    "ausência": -1,
    "escassez": -1,
    "carência": -1,
    "falta": -1,
    "perda": -1,
    "fragilidade": -1,
    "redução": -1,
    "queda": -1,
    "precariedade": -1,
    "presença": +1,
    "aumento": +1,
    "expansão": +1,
    "crescimento": +1,
    "avanço": +1,
    "criação": 0,
    "exercício": 0,
    "vínculo": 0,
    "processo": 0,
    "ciclo": 0,
    "nível": 0,
}

#: Substantivos vazios de conteúdo argumentativo. Aparecem sobretudo em
#: locuções adverbiais ("dessa forma", "por sua vez", "em primeiro lugar")
#: que o parser às vezes anexa ao verbo como se fossem complementos.
SUBSTANTIVOS_VAZIOS: frozenset[str] = frozenset({
    "forma", "vez", "lugar", "fim", "meio", "modo", "parte", "caso",
    "ponto", "sentido", "âmbito", "contexto", "exemplo", "tema", "texto",
    "questão", "aspecto", "maneira", "ordem", "termo", "tipo", "número",
    "ademais", "outrossim", "conclusão", "início",
})

#: Pronomes relativos que precisam ser trocados pelo seu antecedente.
PRONOMES_RELATIVOS: frozenset[str] = frozenset({"que", "qual", "quais", "cujo", "cuja", "onde"})

#: Relações de dependência que indicam sujeito.
DEP_SUJEITO: frozenset[str] = frozenset({"nsubj", "nsubj:pass", "csubj", "csubj:pass"})

#: Relações de dependência que indicam objeto ou complemento.
DEP_OBJETO: frozenset[str] = frozenset({"obj", "iobj", "obl", "obl:agent", "xcomp", "ccomp"})

#: Categorias gramaticais que podem virar vértice.
POS_NOMINAL: frozenset[str] = frozenset({"NOUN", "PROPN"})

#: Conectivos que marcam CONSEQUÊNCIA e abrem a frase: o que veio antes é a
#: causa, o que vem depois é o efeito. A direção é inequívoca, e é por isso
#: que só estes entram — conectivos de causa ("porque", "já que") invertem
#: o sentido conforme a posição na frase, e o risco de errar a direção não
#: compensa.
CONECTIVOS_CONSECUTIVOS: tuple[str, ...] = (
    "portanto", "logo", "assim", "então", "consequentemente", "por conseguinte",
    "dessa forma", "desse modo", "dessa maneira", "por isso", "diante disso",
    "diante desse", "nesse sentido", "com isso", "por consequência", "sendo assim",
    "em vista disso", "por essa razão", "por esse motivo", "destarte",
)

#: Quantos tokens do começo da frase são inspecionados à procura do conectivo.
JANELA_DO_CONECTIVO = 5

#: Relações em que um verbo subordinado compartilha o sujeito do verbo acima.
#: "o Ministério **deve promover** a demarcação" — o sujeito está em "deve",
#: o objeto está em "promover".
DEP_HERANCA: frozenset[str] = frozenset({"xcomp", "ccomp", "advcl", "conj"})


# ---------------------------------------------------------------------------
# Resultado da extração
# ---------------------------------------------------------------------------

@dataclass
class Extracao:
    """O grafo extraído mais os números que permitem auditar a extração."""

    grafo: Grafo
    frases_totais: int = 0
    frases_produtivas: int = 0
    frases_sem_aresta: list[str] = field(default_factory=list)
    #: chave canônica do vértice -> forma como o conceito aparece na tela
    rotulos: dict[str, str] = field(default_factory=dict)

    def exibir(self, chave: str) -> str:
        """Nome legível de um vértice, com recuo para a própria chave."""
        return self.rotulos.get(chave, chave)

    @property
    def cobertura(self) -> float:
        """Fração das frases que produziu ao menos uma aresta.

        É a métrica honesta de qualidade do sensor: uma cobertura baixa
        significa que o grafo está vendo pouco do texto, e isso precisa
        ser reportado junto com o diagnóstico, não escondido.
        """
        if self.frases_totais == 0:
            return 0.0
        return self.frases_produtivas / self.frases_totais

    def resumo(self) -> str:
        return (
            f"{self.grafo.num_vertices} conceitos, "
            f"{self.grafo.num_arestas} arestas, "
            f"cobertura {self.cobertura:.0%} "
            f"({self.frases_produtivas}/{self.frases_totais} frases)"
        )


# ---------------------------------------------------------------------------
# Carga do modelo
# ---------------------------------------------------------------------------

@lru_cache(maxsize=2)
def carregar_modelo(nome: str = MODELO_PADRAO):
    """Carrega o modelo de língua do spaCy, uma única vez por nome.

    O modelo leva alguns segundos para carregar; o cache evita pagar esse
    custo a cada redação analisada no aplicativo.
    """
    import spacy  # importado aqui para o módulo poder ser lido sem spaCy instalado

    try:
        return spacy.load(nome)
    except OSError as erro:  # pragma: no cover - depende do ambiente
        raise RuntimeError(
            f"modelo '{nome}' não encontrado. Instale com:\n"
            f"    python -m spacy download {nome}"
        ) from erro


# ---------------------------------------------------------------------------
# Refinamentos
# ---------------------------------------------------------------------------

def _nucleo_semantico(token, profundidade: int = 0) -> tuple[object, int]:
    """
    Refinamento (a) — substantivo leve.

    Em "a **fragilidade** da identidade cultural facilita a expulsão", o
    sujeito sintático é "fragilidade", que não é um conceito: é um operador
    sobre um conceito. O conceito real está no `nmod` que o modifica.

    Devolve o token que de fato carrega o conteúdo, junto com a polaridade
    que o operador imprimiu (-1 para ausência/escassez, +1 para
    aumento/expansão, 0 para neutro).

    A descida é recursiva, para dar conta de encadeamentos como
    "a ausência de criação de políticas públicas", com limite de
    profundidade para nunca entrar em laço.
    """
    if profundidade >= 3:
        return token, 0

    polaridade = SUBSTANTIVOS_LEVES.get(token.lemma_.lower())
    if polaridade is None:
        return token, 0

    for filho in token.children:
        if filho.dep_ in ("nmod", "obl") and filho.pos_ in POS_NOMINAL:
            interno, polaridade_interna = _nucleo_semantico(filho, profundidade + 1)
            # polaridades se acumulam por multiplicação quando ambas são não-nulas
            combinada = polaridade * polaridade_interna if polaridade_interna else polaridade
            return interno, combinada

    return token, polaridade


def _resolver_pronome(token):
    """
    Refinamento (b) — oração relativa.

    Em "a invisibilidade social, **que** retroalimenta a escassez", o sujeito
    de "retroalimenta" é o pronome `que`, que não é substantivo e seria
    descartado pela regra base. O conceito está no antecedente que a oração
    relativa modifica: sobe-se do pronome para o verbo, e do verbo para o
    núcleo que ele qualifica.

    Devolve None quando o token não pode virar conceito.
    """
    if token.pos_ in POS_NOMINAL:
        return token

    if token.pos_ in ("PRON", "DET") and token.lemma_.lower() in PRONOMES_RELATIVOS:
        # caminho principal: a relativa se prende diretamente a um substantivo
        verbo = token.head
        antecedente = verbo.head
        if antecedente is not verbo and antecedente.pos_ in POS_NOMINAL:
            return antecedente

        # recuo: a relativa se prendeu a um verbo, e o antecedente sintático
        # se perdeu. O substantivo imediatamente à esquerda do pronome acerta
        # na maioria dos casos, porque em português o relativo vem colado ao
        # termo que retoma ("a população, que sofre...").
        return _nominal_a_esquerda(token)

    return None


def _nominal_a_esquerda(token):
    """Substantivo mais próximo à esquerda, dentro da mesma frase."""
    frase = token.sent
    for anterior in reversed(list(frase[: token.i - frase.start])):
        if anterior.pos_ in POS_NOMINAL:
            return anterior
    return None


def _e_nucleo_verbal(token) -> bool:
    """
    Refinamento (f) — verbo mal etiquetado.

    O parser erra a classe gramatical em frases sem artigo: em "a pobreza
    gera exclusão", "gera" é etiquetado como nome próprio, e a frase inteira
    se perderia. Mas um token que TEM sujeito está funcionando como núcleo
    de predicado, qualquer que seja a etiqueta que recebeu.

    O critério sintático é mais confiável que o morfológico aqui, e o
    ganho é direto em texto real, que raramente é tão bem-comportado
    quanto os exemplos de gramática.
    """
    if token.pos_ in ("VERB", "AUX"):
        return True
    return any(filho.dep_ in DEP_SUJEITO for filho in token.children)


def _sujeitos_do_verbo(verbo) -> list:
    """
    Sujeitos de um verbo, com dois refinamentos.

    Refinamento (c) — aposto entre vírgulas. Em "o preconceito estrutural,
    **por sua vez**, desestimula a criação de políticas", a interrupção
    confunde o parser, que rotula "preconceito" com a relação genérica
    `dep` em vez de `nsubj`. Quando o verbo não tem nenhum sujeito legítimo,
    aceita-se um `dep` nominal no lugar.

    Refinamento (d) — verbo coordenado. Em "a expansão provoca a expulsão
    e **gera** a perda", o segundo verbo não repete o sujeito. Um verbo
    ligado ao anterior por `conj` herda o sujeito dele.
    """
    sujeitos = [f for f in verbo.children if f.dep_ in DEP_SUJEITO]

    if not sujeitos:
        sujeitos = [
            f for f in verbo.children
            if f.dep_ == "dep" and f.pos_ in POS_NOMINAL
        ]

    if not sujeitos:
        sujeitos = _herdar_sujeitos(verbo)

    return sujeitos


def _herdar_sujeitos(verbo, saltos: int = 0) -> list:
    """
    Refinamento (e) — verbo subordinado sem sujeito próprio.

    Em "o Ministério **deve promover** a demarcação de territórios", o
    sujeito está preso ao auxiliar "deve" e o objeto ao verbo "promover",
    que pende dele por `xcomp`. Nenhum dos dois tem sujeito e objeto ao
    mesmo tempo, e a frase inteira — justamente a proposta de intervenção —
    se perderia.

    A solução é subir a cadeia de subordinação até achar um verbo que
    tenha sujeito, com limite de saltos para não percorrer a frase toda.
    """
    if saltos >= 3:
        return []
    if verbo.dep_ not in DEP_HERANCA:
        return []

    acima = verbo.head
    if acima is verbo or not _e_nucleo_verbal(acima):
        return []

    herdados = [f for f in acima.children if f.dep_ in DEP_SUJEITO]
    if herdados:
        return herdados
    return _herdar_sujeitos(acima, saltos + 1)


def _expandir_coordenados(tokens) -> Iterator:
    """
    Refinamento (d) — substantivos coordenados.

    Em "a expansão provoca a expulsão e a marginalização", apenas "expulsão"
    é `obj` do verbo; "marginalização" pende dela por `conj`. Sem isso, a
    segunda aresta se perde.
    """
    for token in tokens:
        yield token
        for filho in token.children:
            if filho.dep_ == "conj" and filho.pos_ in POS_NOMINAL:
                yield filho


def _abre_com_conectivo(frase) -> bool:
    """A frase começa marcando consequência do que veio antes?"""
    inicio = frase.text.strip().lower()
    for conectivo in CONECTIVOS_CONSECUTIVOS:
        if inicio.startswith(conectivo):
            # exige fronteira de palavra: "assim" sim, "assimetria" não
            resto = inicio[len(conectivo):]
            if not resto or not resto[0].isalpha():
                return True
    return False


def _rotulo(token) -> str:
    """
    Nome do vértice: lema do núcleo somado ao seu primeiro adjetivo.

    "identidade cultural", "política pública", "preconceito estrutural".
    O adjetivo entra porque distingue conceitos que o lema sozinho
    confundiria — "política pública" e "política externa" são coisas
    diferentes na argumentação.
    """
    modificadores = [f.lemma_.lower() for f in token.children if f.dep_ == "amod"]
    base = token.lemma_.lower().strip()
    if modificadores:
        return f"{base} {modificadores[0]}"
    return base


def _texto_exibicao(token) -> str:
    """
    Como o conceito aparece na tela, em vez de como ele é indexado.

    O lema do adjetivo vem sempre no masculino singular, então a chave
    canônica de "políticas públicas" é "política público" — boa para
    agrupar ocorrências, péssima para mostrar ao usuário. Aqui se guarda
    o trecho como o autor escreveu, em ordem de posição na frase.
    """
    pedacos = [(token.i, token.text)]
    pedacos += [(f.i, f.text) for f in token.children if f.dep_ == "amod"]
    pedacos.sort()
    return " ".join(texto for _, texto in pedacos).lower()


def _e_conceito_valido(token, rotulo: str) -> bool:
    """Filtra o que não deve virar vértice."""
    if token.pos_ not in POS_NOMINAL:
        return False
    if not rotulo or len(rotulo) < 3:
        return False
    if rotulo.split()[0] in SUBSTANTIVOS_VAZIOS:
        return False
    return True


# ---------------------------------------------------------------------------
# Extração
# ---------------------------------------------------------------------------

class Extrator:
    """
    Transforma o texto de uma redação num grafo direcionado de conceitos.

    Uso:
        extrator = Extrator()
        resultado = extrator.extrair(texto_da_redacao)
        grafo = resultado.grafo
    """

    def __init__(self, modelo: str = MODELO_PADRAO, nlp=None) -> None:
        self._nlp = nlp if nlp is not None else carregar_modelo(modelo)

    def extrair(self, texto: str) -> Extracao:
        """Percorre cada frase do texto e acumula as arestas encontradas."""
        documento = self._nlp(texto)
        resultado = Extracao(grafo=Grafo())
        anterior: str | None = None  # conceito principal da frase anterior

        for frase in documento.sents:
            texto_frase = frase.text.strip()
            if not texto_frase:
                continue

            resultado.frases_totais += 1
            arestas = list(self._arestas_da_frase(frase, resultado.rotulos))

            # refinamento (g): coesão entre frases
            principal = self._conceito_principal(frase, resultado.rotulos)
            if anterior and principal and _abre_com_conectivo(frase):
                if anterior != principal:
                    arestas.append((anterior, principal))

            if arestas:
                resultado.frases_produtivas += 1
                for origem, destino in arestas:
                    resultado.grafo.adicionar_aresta(origem, destino, texto_frase)
            else:
                resultado.frases_sem_aresta.append(texto_frase)

            if principal:
                anterior = principal

        return resultado

    def _conceito_principal(self, frase, exibicao=None) -> str | None:
        """
        O conceito de que a frase fala.

        Preferência pelo sujeito do verbo principal, que é de quem a frase
        predica algo. Sem sujeito nominal, cai no primeiro conceito válido
        que aparecer.
        """
        for token in frase:
            if not _e_nucleo_verbal(token):
                continue
            nomes = self._rotulos(_sujeitos_do_verbo(token), exibicao)
            if nomes:
                return nomes[0]

        nomes = self._rotulos((t for t in frase if t.pos_ in POS_NOMINAL), exibicao)
        return nomes[0] if nomes else None

    def _arestas_da_frase(self, frase, exibicao=None) -> Iterator[tuple[str, str]]:
        """Aplica a regra base e os quatro refinamentos a uma única frase."""
        vistas: set[tuple[str, str]] = set()

        for token in frase:
            if not _e_nucleo_verbal(token):
                continue

            sujeitos = _sujeitos_do_verbo(token)
            if not sujeitos:
                continue

            objetos = [f for f in token.children if f.dep_ in DEP_OBJETO]
            if not objetos:
                continue

            origens = self._rotulos(_expandir_coordenados(sujeitos), exibicao)
            destinos = self._rotulos(_expandir_coordenados(objetos), exibicao)

            for origem in origens:
                for destino in destinos:
                    if origem == destino:
                        continue  # o Grafo rejeita laços; evita a exceção
                    par = (origem, destino)
                    if par in vistas:
                        continue  # a mesma frase não conta duas vezes
                    vistas.add(par)
                    yield par

    def conceitos_do_texto(self, texto: str) -> list[str]:
        """
        Conceitos mencionados num trecho, sem exigir estrutura de frase.

        A extração de ARESTAS precisa de sujeito e objeto de um verbo. Mas
        às vezes só interessa saber QUAIS conceitos aparecem num pedaço de
        texto — no título da redação, que quase nunca tem verbo, ou no
        último parágrafo, para achar de que a proposta de intervenção fala.

        Devolve as chaves canônicas, na ordem de aparição, sem repetir.
        """
        documento = self._nlp(texto)
        return self._rotulos(t for t in documento if t.pos_ in POS_NOMINAL)

    def _rotulos(self, tokens, exibicao: dict[str, str] | None = None) -> list[str]:
        """Converte tokens sintáticos em nomes de vértice, já refinados."""
        nomes: list[str] = []
        for token in tokens:
            nominal = _resolver_pronome(token)
            if nominal is None:
                continue

            nucleo, _polaridade = _nucleo_semantico(nominal)
            rotulo = _rotulo(nucleo)

            if not _e_conceito_valido(nucleo, rotulo):
                continue

            if exibicao is not None:
                visivel = _texto_exibicao(nucleo)
                anterior = exibicao.get(rotulo)
                # a forma mais curta costuma ser o singular: melhor para exibir
                if anterior is None or len(visivel) < len(anterior):
                    exibicao[rotulo] = visivel

            if rotulo not in nomes:
                nomes.append(rotulo)
        return nomes


# ---------------------------------------------------------------------------
# Atalho
# ---------------------------------------------------------------------------

def extrair_grafo(texto: str, modelo: str = MODELO_PADRAO) -> Grafo:
    """Atalho para quem só quer o grafo e não as estatísticas."""
    return Extrator(modelo).extrair(texto).grafo


# ---------------------------------------------------------------------------
# Execução direta, para inspecionar a extração de um texto qualquer
#
#     python -m src.extracao data/exemplo_sintetico_com_laco.txt
# ---------------------------------------------------------------------------

def _main(argv: list[str]) -> int:
    import sys

    if len(argv) != 2:
        print("uso: python -m src.extracao <arquivo.txt>", file=sys.stderr)
        return 2

    caminho = argv[1]
    try:
        texto = open(caminho, encoding="utf-8").read()
    except OSError as erro:
        print(f"não consegui ler {caminho}: {erro}", file=sys.stderr)
        return 1

    resultado = Extrator().extrair(texto)
    grafo = resultado.grafo

    print(resultado.resumo())
    print()
    print("ARESTAS (origem -> destino, peso)")
    arestas = sorted(grafo.arestas(), key=lambda a: (-a.frequencia, a.origem))
    largura = max((len(resultado.exibir(a.origem)) for a in arestas), default=10)
    for aresta in arestas:
        origem = resultado.exibir(aresta.origem)
        destino = resultado.exibir(aresta.destino)
        print(f"  {origem:<{largura}} -> {destino:<{largura}}  {aresta.peso:.2f}")

    if resultado.frases_sem_aresta:
        print()
        print("FRASES QUE NÃO PRODUZIRAM ARESTA")
        for frase in resultado.frases_sem_aresta:
            recorte = frase if len(frase) <= 90 else frase[:87] + "..."
            print(f"  - {recorte}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys

    raise SystemExit(_main(sys.argv))
