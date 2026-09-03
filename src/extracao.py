
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterator

from src.grafo import Grafo

MODELO_PADRAO = "pt_core_news_sm"


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

SUBSTANTIVOS_VAZIOS: frozenset[str] = frozenset({
    "forma", "vez", "lugar", "fim", "meio", "modo", "parte", "caso",
    "ponto", "sentido", "âmbito", "contexto", "exemplo", "tema", "texto",
    "questão", "aspecto", "maneira", "ordem", "termo", "tipo", "número",
    "ademais", "outrossim", "conclusão", "início",
})

PRONOMES_RELATIVOS: frozenset[str] = frozenset({"que", "qual", "quais", "cujo", "cuja", "onde"})

DEP_SUJEITO: frozenset[str] = frozenset({"nsubj", "nsubj:pass", "csubj", "csubj:pass"})

DEP_OBJETO: frozenset[str] = frozenset({"obj", "iobj", "obl", "obl:agent", "xcomp", "ccomp"})

POS_NOMINAL: frozenset[str] = frozenset({"NOUN", "PROPN"})

CONECTIVOS_CONSECUTIVOS: tuple[str, ...] = (
    "portanto", "logo", "assim", "então", "consequentemente", "por conseguinte",
    "dessa forma", "desse modo", "dessa maneira", "por isso", "diante disso",
    "diante desse", "nesse sentido", "com isso", "por consequência", "sendo assim",
    "em vista disso", "por essa razão", "por esse motivo", "destarte",
)

JANELA_DO_CONECTIVO = 5

DEP_HERANCA: frozenset[str] = frozenset({"xcomp", "ccomp", "advcl", "conj"})


@dataclass
class Extracao:

    grafo: Grafo
    frases_totais: int = 0
    frases_produtivas: int = 0
    frases_sem_aresta: list[str] = field(default_factory=list)
    rotulos: dict[str, str] = field(default_factory=dict)

    def exibir(self, chave: str) -> str:
        return self.rotulos.get(chave, chave)

    @property
    def cobertura(self) -> float:
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


@lru_cache(maxsize=2)
def carregar_modelo(nome: str = MODELO_PADRAO):
    import spacy

    try:
        return spacy.load(nome)
    except OSError as erro:
        raise RuntimeError(
            f"modelo '{nome}' não encontrado. Instale com:\n"
            f"    python -m spacy download {nome}"
        ) from erro


def _nucleo_semantico(token, profundidade: int = 0) -> tuple[object, int]:
    if profundidade >= 3:
        return token, 0

    polaridade = SUBSTANTIVOS_LEVES.get(token.lemma_.lower())
    if polaridade is None:
        return token, 0

    for filho in token.children:
        if filho.dep_ in ("nmod", "obl") and filho.pos_ in POS_NOMINAL:
            interno, polaridade_interna = _nucleo_semantico(filho, profundidade + 1)
            combinada = polaridade * polaridade_interna if polaridade_interna else polaridade
            return interno, combinada

    return token, polaridade


def _resolver_pronome(token):
    if token.pos_ in POS_NOMINAL:
        return token

    if token.pos_ in ("PRON", "DET") and token.lemma_.lower() in PRONOMES_RELATIVOS:
        verbo = token.head
        antecedente = verbo.head
        if antecedente is not verbo and antecedente.pos_ in POS_NOMINAL:
            return antecedente

        return _nominal_a_esquerda(token)

    return None


def _nominal_a_esquerda(token):
    frase = token.sent
    for anterior in reversed(list(frase[: token.i - frase.start])):
        if anterior.pos_ in POS_NOMINAL:
            return anterior
    return None


def _e_nucleo_verbal(token) -> bool:
    if token.pos_ in ("VERB", "AUX"):
        return True
    return any(filho.dep_ in DEP_SUJEITO for filho in token.children)


def _sujeitos_do_verbo(verbo) -> list:
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
    for token in tokens:
        yield token
        for filho in token.children:
            if filho.dep_ == "conj" and filho.pos_ in POS_NOMINAL:
                yield filho


def _abre_com_conectivo(frase) -> bool:
    inicio = frase.text.strip().lower()
    for conectivo in CONECTIVOS_CONSECUTIVOS:
        if inicio.startswith(conectivo):
            resto = inicio[len(conectivo):]
            if not resto or not resto[0].isalpha():
                return True
    return False


def _rotulo(token) -> str:
    modificadores = [f.lemma_.lower() for f in token.children if f.dep_ == "amod"]
    base = token.lemma_.lower().strip()
    if modificadores:
        return f"{base} {modificadores[0]}"
    return base


def _texto_exibicao(token) -> str:
    pedacos = [(token.i, token.text)]
    pedacos += [(f.i, f.text) for f in token.children if f.dep_ == "amod"]
    pedacos.sort()
    return " ".join(texto for _, texto in pedacos).lower()


def _e_conceito_valido(token, rotulo: str) -> bool:
    if token.pos_ not in POS_NOMINAL:
        return False
    if not rotulo or len(rotulo) < 3:
        return False
    if rotulo.split()[0] in SUBSTANTIVOS_VAZIOS:
        return False
    return True


class Extrator:

    def __init__(self, modelo: str = MODELO_PADRAO, nlp=None) -> None:
        self._nlp = nlp if nlp is not None else carregar_modelo(modelo)

    def extrair(self, texto: str) -> Extracao:
        documento = self._nlp(texto)
        resultado = Extracao(grafo=Grafo())
        anterior: str | None = None

        for frase in documento.sents:
            texto_frase = frase.text.strip()
            if not texto_frase:
                continue

            resultado.frases_totais += 1
            arestas = list(self._arestas_da_frase(frase, resultado.rotulos))

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
        for token in frase:
            if not _e_nucleo_verbal(token):
                continue
            nomes = self._rotulos(_sujeitos_do_verbo(token), exibicao)
            if nomes:
                return nomes[0]

        nomes = self._rotulos((t for t in frase if t.pos_ in POS_NOMINAL), exibicao)
        return nomes[0] if nomes else None

    def _arestas_da_frase(self, frase, exibicao=None) -> Iterator[tuple[str, str]]:
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
                        continue
                    par = (origem, destino)
                    if par in vistas:
                        continue
                    vistas.add(par)
                    yield par

    def conceitos_do_texto(self, texto: str) -> list[str]:
        documento = self._nlp(texto)
        return self._rotulos(t for t in documento if t.pos_ in POS_NOMINAL)

    def _rotulos(self, tokens, exibicao: dict[str, str] | None = None) -> list[str]:
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
                if anterior is None or len(visivel) < len(anterior):
                    exibicao[rotulo] = visivel

            if rotulo not in nomes:
                nomes.append(rotulo)
        return nomes


def extrair_grafo(texto: str, modelo: str = MODELO_PADRAO) -> Grafo:
    return Extrator(modelo).extrair(texto).grafo


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


if __name__ == "__main__":
    import sys

    raise SystemExit(_main(sys.argv))
