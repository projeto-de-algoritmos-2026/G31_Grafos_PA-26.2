"""
Raio-X da Redação — interface.

    streamlit run app.py

A tela é fina de propósito: toda a lógica está em `src/`, e este arquivo só
pede o texto, chama `diagnosticar()` e desenha o resultado. Isso mantém o
diagnóstico testável sem subir a interface, que é o que permite a suíte
rodar em um segundo.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.diagnostico import ATENCAO, FALHA, INDEFINIDO, OK, diagnosticar
from src.extracao import Extrator
from src.visualizacao import legenda, para_dot

PASTA_EXEMPLOS = Path("data")

APARENCIA = {
    OK: ("✅", "#1E6E5A", "sem apontamentos"),
    ATENCAO: ("⚠️", "#B8860B", "vale conferir"),
    FALHA: ("⛔", "#A8402A", "problema na estrutura"),
    INDEFINIDO: ("○", "#6B7975", "sem conclusão possível"),
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


def listar_exemplos() -> dict[str, Path]:
    if not PASTA_EXEMPLOS.exists():
        return {}
    return {p.stem.replace("_", " "): p for p in sorted(PASTA_EXEMPLOS.glob("*.txt"))}


def cabecalho() -> None:
    st.set_page_config(page_title="Raio-X da Redação", page_icon="🕸️", layout="wide")
    st.title("Raio-X da Redação")
    st.caption(
        "Diagnóstico da estrutura argumentativa por algoritmos em grafos · "
        "Projeto de Algoritmos 2026.2 · UnB/FGA"
    )


def painel_de_entrada() -> tuple[str, str, str, bool, bool]:
    exemplos = listar_exemplos()

    with st.sidebar:
        st.subheader("Redação")

        texto_inicial = ""
        escolha = "(colar meu texto)"
        if exemplos:
            escolha = st.selectbox(
                "Carregar exemplo", ["(colar meu texto)"] + list(exemplos)
            )
            if escolha != "(colar meu texto)":
                texto_inicial = exemplos[escolha].read_text(encoding="utf-8")

        titulo = st.text_input(
            "Título da redação",
            help="Ajuda a identificar o conceito que representa o tema.",
        )
        enunciado = st.text_area(
            "Tema da prova (opcional)", height=80,
            help="O texto motivador. Usado se o título não bastar.",
        )
        apenas_conectados = st.checkbox(
            "Esconder conceitos isolados", value=False,
            help="Conceitos sem nenhuma relação. Em texto real são muitos.",
        )
        analisar = st.button("Analisar", type="primary", use_container_width=True)

    # A chave depende do exemplo escolhido de propósito. O Streamlit guarda o
    # estado do widget por chave e IGNORA um novo `value` quando o usuário já
    # digitou algo — então, sem isso, escolher um exemplo depois de mexer na
    # caixa não trocaria o texto, e falharia em silêncio.
    texto = st.text_area(
        "Cole a redação aqui — separe os parágrafos com uma linha em branco",
        value=texto_inicial, height=260, key=f"redacao::{escolha}",
    )
    return texto, titulo, enunciado, apenas_conectados, analisar


def mostrar_metricas(d) -> None:
    a, b, c, e = st.columns(4)
    a.metric("Conceitos", d.num_conceitos)
    b.metric("Relações", d.num_relacoes)
    # Cadeia indisponível não é cadeia de tamanho zero: mostrar "0" aqui leria
    # como qualidade nula, quando o que houve foi o Kahn não poder ordenar.
    if d.cadeia is None:
        c.metric("Cadeia argumentativa", "—",
                 help="Não calculável: o grafo tem ciclo, e a ordenação topológica "
                      "exige a condensação dos componentes.")
    else:
        c.metric("Cadeia argumentativa", d.tamanho_da_cadeia,
                 help="Conceitos encadeados na ordenação topológica. É o indicador validado.")
    e.metric("Cobertura", f"{d.cobertura:.0%}",
             help="Fração das frases da redação que produziu ao menos uma relação.")


def mostrar_achados(d) -> None:
    st.subheader("Laudo")

    for achado in d.achados:
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
            st.write(achado.resumo)
            for evidencia in achado.evidencias:
                st.caption(f"· {evidencia}")

    indefinidos = len(d.achados) - len(d.conclusivos)
    if indefinidos:
        st.info(
            f"{indefinidos} dos {len(d.achados)} apontamentos ficaram sem conclusão. "
            "Isso é resultado de medição, não omissão: as competências 2 e 5 dependem "
            "de o grafo estar conectado, e a extração por frase não sustenta isso. "
            "A Competência 3 é a que a validação no corpus banca."
        )


def mostrar_grafo(d, apenas_conectados: bool) -> None:
    st.subheader("Grafo de conceitos")

    cores = " &nbsp;·&nbsp; ".join(
        f"<span style='color:{cor}'>█</span> {texto}" for cor, texto in legenda()
    )
    st.markdown(f"<small>{cores}</small>", unsafe_allow_html=True)

    if not d.num_conceitos:
        st.warning("Nenhum conceito foi extraído deste texto.")
        return

    st.graphviz_chart(para_dot(d, apenas_conectados=apenas_conectados), use_container_width=True)


def mostrar_rastro(d) -> None:
    """As frases que sustentam cada relação do caminho tema → proposta."""
    if not (d.caminho and d.caminho.alcancavel and d.caminho.caminho):
        return

    st.subheader("De onde veio cada ligação")
    st.caption(
        "Cada relação do caminho aponta para a frase da redação que a gerou. "
        "É o que torna o diagnóstico verificável em vez de opinativo."
    )

    from src.analise import rastrear_caminho

    rastro = rastrear_caminho(d.grafo, d.caminho.caminho)
    for origem, destino, frases in rastro.arestas_frases:
        with st.expander(f"{d.exibir(origem)} → {d.exibir(destino)}"):
            for frase in frases:
                st.write(f"“{frase}”")


def main() -> None:
    cabecalho()
    texto, titulo, enunciado, apenas_conectados, analisar = painel_de_entrada()

    if not analisar:
        st.info(
            "Cole uma redação e clique em **Analisar**, ou carregue um exemplo pela "
            "barra lateral."
        )
        return

    if not texto.strip():
        st.warning("Sem texto para analisar.")
        return

    with st.spinner("Montando o grafo e rodando os algoritmos..."):
        d = diagnosticar(
            texto, titulo=titulo, enunciado=enunciado, extrator=carregar_extrator()
        )

    mostrar_metricas(d)
    if d.alvos.tema:
        st.caption(
            f"Conceito-tema identificado: **{d.exibir(d.alvos.tema)}** "
            f"(a partir do {d.alvos.origem_do_tema})"
        )

    esquerda, direita = st.columns([3, 2])
    with esquerda:
        mostrar_grafo(d, apenas_conectados)
    with direita:
        mostrar_achados(d)

    mostrar_rastro(d)


if __name__ == "__main__":
    main()
