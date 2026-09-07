"""Raio-X da Redação — interface."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.diagnostico import (ATENCAO, FALHA, INDEFINIDO, OBSERVACAO, OK,
                             _numero, _quantia, diagnosticar, frase)
from src.extracao import Extrator
from src.visualizacao import legenda, para_dot, para_dot_condensado

PASTA_EXEMPLOS = Path("data")

APARENCIA = {
    OK: ("✅", "#1E6E5A", "tudo certo"),
    ATENCAO: ("⚠️", "#B8860B", "vale conferir"),
    FALHA: ("⛔", "#A8402A", "precisa de atenção"),
    OBSERVACAO: ("💡", "#3B6EA5", "só para você saber"),
    INDEFINIDO: ("○", "#6B7975", "não sabemos avaliar"),
}

NOMES_DAS_COMPETENCIAS = {
    2: "Competência 2 — compreensão do tema",
    3: "Competência 3 — coerência e argumentação",
    5: "Competência 5 — proposta de intervenção",
}


@st.cache_resource(show_spinner="Carregando o modelo de português...")
def carregar_extrator() -> Extrator:
    """O modelo do spaCy leva alguns segundos; carrega uma vez só."""
    return Extrator()


#: Nome de arquivo não é rótulo de interface: os arquivos são sem acento por
#: portabilidade, e "exemplo sintetico com laco" não diz nada a quem vai
#: escolher. Aqui o rótulo descreve o que a redação exercita.
ROTULOS_DOS_EXEMPLOS = {
    "exemplo_sintetico_bem_encadeado": "Redação bem encadeada",
    "exemplo_sintetico_com_laco": "Redação com argumento em círculo",
    "exemplo_sintetico_fragmentado": "Redação com ideias soltas",
}

COLAR = "Colar a minha redação"


def rotular(nome_do_arquivo: str) -> str:
    """Rótulo bonito para um exemplo; sem entrada na tabela, arruma o nome."""
    if nome_do_arquivo in ROTULOS_DOS_EXEMPLOS:
        return ROTULOS_DOS_EXEMPLOS[nome_do_arquivo]
    return nome_do_arquivo.replace("_", " ").capitalize()


def listar_exemplos() -> dict[str, Path]:
    if not PASTA_EXEMPLOS.exists():
        return {}
    return {rotular(p.stem): p for p in sorted(PASTA_EXEMPLOS.glob("*.txt"))}


#: O botão de tela cheia do Streamlit é posicionado em `right: -48px`, ou seja,
#: fora do próprio elemento. Em uma página de coluna única ele cai na margem e
#: ninguém nota; ao lado de outra coluna, ele pousa em cima do conteúdo do
#: vizinho. Trazemos para dentro do gráfico.
_CSS = """
<style>
[data-testid="stFullScreenFrame"] button[data-testid="StyledFullScreenButton"] {
    right: 0.25rem !important;
    top: 0.25rem !important;
}
</style>
"""


def cabecalho() -> None:
    st.set_page_config(page_title="Raio-X da Redação", page_icon="🕸️", layout="wide")
    st.markdown(_CSS, unsafe_allow_html=True)
    st.title("Raio-X da Redação")
    st.caption(
        "Veja como as ideias da sua redação se ligam umas às outras — e onde o "
        "encadeamento falha · Projeto de Algoritmos 2026.2 · UnB/FGA"
    )


def painel_de_entrada() -> tuple[str, str, str, bool, bool]:
    exemplos = listar_exemplos()

    with st.sidebar:
        st.subheader("Redação")

        texto_inicial = ""
        escolha = COLAR
        if exemplos:
            escolha = st.selectbox("Carregar exemplo", [COLAR] + list(exemplos))
            if escolha != COLAR:
                texto_inicial = exemplos[escolha].read_text(encoding="utf-8")

        titulo = st.text_input(
            "Título da redação",
            help="Ajuda a descobrir qual ideia do texto é a ideia central.",
        )
        enunciado = st.text_area(
            "Tema da prova (opcional)", height=80,
            help="O enunciado que você recebeu. Usado quando o título não basta.",
        )
        apenas_conectados = st.checkbox(
            "Esconder ideias soltas", value=False,
            help="Ideias que aparecem no texto sem se ligar a nenhuma outra. "
                 "Deixa o mapa bem mais limpo.",
        )
        analisar = st.button("Analisar", type="primary", use_container_width=True)

    texto = st.text_area(
        "Cole a redação aqui — separe os parágrafos com uma linha em branco",
        value=texto_inicial, height=260, key=f"redacao::{escolha}",
    )
    return texto, titulo, enunciado, apenas_conectados, analisar


def mostrar_metricas(d) -> None:
    a, b, c, e = st.columns(4)
    a.metric("Ideias no texto", d.num_conceitos,
             help="Cada assunto que a redação trata, contado uma vez só. É o número "
                  "que melhor prevê a nota de coerência: 73% de acerto em 160 "
                  "redações já corrigidas.")
    b.metric("Ligações", d.num_relacoes,
             help="Quantas vezes uma ideia leva a outra: \"X provoca Y\", \"X gera Y\".")

    # Maior caminho no grafo condensado: a única medida de profundidade real.
    # A contagem de ideias já aparece no primeiro cartão — é ela que vira veredito.
    c.metric("Maior encadeamento", max(d.tamanho_maior_caminho - 1, 0),
             help="O trecho mais desenvolvido do texto: quantas vezes seguidas uma "
                  "ideia leva à seguinte. Mede profundidade, não quantidade.")
    e.metric("Frases aproveitadas", f"{d.cobertura:.0%}",
             help="Das frases da redação, quantas o programa conseguiu ler como "
                  "uma ligação entre ideias.")


def _cartao(achado) -> None:
    icone, cor, rotulo = APARENCIA[achado.status]
    titulo = NOMES_DAS_COMPETENCIAS.get(
        achado.competencia, f"Competência {achado.competencia}"
    )
    with st.container(border=True):
        st.markdown(
            f"{icone} **{titulo}** · {achado.nome} "
            f"<span style='color:{cor}'>({rotulo})</span>",
            unsafe_allow_html=True,
        )
        st.write(frase(achado.resumo))
        for evidencia in achado.evidencias:
            st.caption(f"· {evidencia}")


def mostrar_achados(d) -> None:
    # Os achados que mudam de redação para redação vêm primeiro. Os outros —
    # a profundidade, que é sempre observação, e o alcance do tema, que é
    # sempre indefinido — ficam agrupados abaixo: repetir os cinco com o mesmo
    # peso faz o laudo parecer igual em toda redação, mesmo quando não é.
    st.subheader("O que encontramos")

    VEREDITOS = (OK, ATENCAO, FALHA)
    vereditos = [a for a in d.achados if a.status in VEREDITOS]
    complementares = [a for a in d.achados if a.status not in VEREDITOS]

    for achado in vereditos:
        _cartao(achado)

    if complementares:
        st.markdown("**Números que mostramos sem avaliar**")
        for achado in complementares:
            _cartao(achado)

    indefinidos = len(d.achados) - len(d.conclusivos)
    if indefinidos:
        # frase() vai no texto inteiro, nunca num pedaço: aplicada ao trecho
        # inicial, ela enfiaria um ponto final no meio da oração.
        aviso = (
            f"{_quantia(indefinidos, 'ponto')} dos {_numero(len(d.achados))} acima "
            f"{'está marcado' if indefinidos == 1 else 'estão marcados'} como "
            "\"não sabemos avaliar\". Isso é proposital: testamos esses indicadores em "
            "160 redações já corrigidas por humanos e eles não distinguiram texto bom "
            "de ruim, então preferimos mostrar o número sem dar veredito. A quantidade "
            "de ideias que o texto sustenta, essa sim, foi validada."
        )
        st.info(frase(aviso))


def mostrar_grafo(d, apenas_conectados: bool) -> None:
    st.subheader("Mapa das suas ideias")

    cores = " &nbsp;·&nbsp; ".join(
        f"<span style='color:{cor}'>█</span> {texto}" for cor, texto in legenda()
    )
    st.markdown(f"<small>{cores}</small>", unsafe_allow_html=True)

    if not d.num_conceitos:
        st.warning("Não conseguimos identificar ideias neste texto.")
        return

    st.graphviz_chart(para_dot(d, apenas_conectados=apenas_conectados), use_container_width=True)


def mostrar_rastro(d) -> None:
    """As frases que sustentam cada relação do caminho tema → proposta."""
    if not (d.caminho and d.caminho.alcancavel and d.caminho.caminho):
        return

    st.subheader("De onde veio cada ligação")
    st.caption(
        "Cada ligação aponta para a frase da sua redação que a criou. Assim você "
        "confere se a leitura do programa faz sentido."
    )

    from src.analise import rastrear_caminho

    rastro = rastrear_caminho(d.grafo, d.caminho.caminho)
    for origem, destino, frases in rastro.arestas_frases:
        with st.expander(f"{d.exibir(origem)} → {d.exibir(destino)}"):
            for citacao in frases:
                st.write(f"“{citacao}”")


def _rotulo_legivel(d, rotulo: str) -> str:
    """Nomes legíveis dos conceitos agrupados num super-vértice condensado."""
    if d.condensacao is None:
        return rotulo
    membros = d.condensacao.membros.get(rotulo, {rotulo})
    return " + ".join(sorted(d.exibir(m) for m in membros))


def mostrar_estrutura_argumento(d) -> None:
    """A maior cadeia do grafo condensado — funciona mesmo com laço no texto."""
    if d.condensacao is None:
        return

    st.subheader("Espinha dorsal do argumento")
    st.caption(
        "A sequência mais longa de ideias que o seu texto sustenta do começo "
        "ao fim. Quando um grupo de ideias se puxa em círculo, ele entra aqui "
        "como um bloco só — por isso este número existe mesmo quando a "
        "sequência de ideias não pôde ser calculada."
    )

    if not d.maior_caminho:
        st.info("Não há uma cadeia a destacar neste texto.")
        return

    # O número já está no cartão "Maior encadeamento" lá em cima; repetir aqui
    # como st.metric só duplicava a informação. Aqui interessa o percurso.
    inicio = _rotulo_legivel(d, d.maior_caminho[0])
    fim = _rotulo_legivel(d, d.maior_caminho[-1])

    st.write(f"De **{inicio}** até **{fim}**:")
    st.write(" → ".join(_rotulo_legivel(d, r) for r in d.maior_caminho))

    with st.expander("Ver os componentes condensados"):
        st.caption(
            "Cada bloco em vermelho é um argumento em círculo (um laço) "
            "colapsado num único vértice. O resultado é sempre um grafo "
            "sem ciclos — é por isso que dá para calcular uma cadeia "
            "principal mesmo quando o texto tem um laço."
        )
        st.graphviz_chart(para_dot_condensado(d), use_container_width=True)


def main() -> None:
    cabecalho()
    texto, titulo, enunciado, apenas_conectados, analisar = painel_de_entrada()

    if not analisar:
        st.info(
            "Cole a sua redação e clique em **Analisar**. Se quiser ver como funciona "
            "primeiro, carregue um exemplo na barra lateral."
        )
        return

    if not texto.strip():
        st.warning("A caixa está vazia — cole uma redação para analisar.")
        return

    with st.spinner("Lendo o texto e montando o mapa de ideias..."):
        d = diagnosticar(
            texto, titulo=titulo, enunciado=enunciado, extrator=carregar_extrator()
        )

    mostrar_metricas(d)
    if d.alvos.tema:
        st.caption(
            f"Ideia central identificada: **{d.exibir(d.alvos.tema)}** "
            f"(a partir do {d.alvos.origem_do_tema})"
        )

    esquerda, direita = st.columns([3, 2])
    with esquerda:
        mostrar_grafo(d, apenas_conectados)
    with direita:
        mostrar_achados(d)

    mostrar_rastro(d)
    mostrar_estrutura_argumento(d)


if __name__ == "__main__":
    main()
