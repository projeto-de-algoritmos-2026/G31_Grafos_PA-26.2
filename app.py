from __future__ import annotations
 
from pathlib import Path
 
import streamlit as st
 
from src.diagnostico import (ATENCAO, FALHA, INDEFINIDO, OBSERVACAO, OK,
                             diagnosticar)
from src.extracao import Extrator
from src.visualizacao import legenda, para_dot, para_dot_condensado
 
PASTA_EXEMPLOS = Path("data")
 
APARENCIA = {
    OK: ("", "#1E6E5A", "tudo certo"),
    ATENCAO: ("", "#B8860B", "vale conferir"),
    FALHA: ("", "#A8402A", "precisa de atenção"),
    OBSERVACAO: ("", "#3B6EA5", "só para você saber"),
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
 
 
def listar_exemplos() -> dict[str, Path]:
    if not PASTA_EXEMPLOS.exists():
        return {}
    return {p.stem.replace("_", " "): p for p in sorted(PASTA_EXEMPLOS.glob("*.txt"))}
 
 
def cabecalho() -> None:
    st.set_page_config(page_title="Raio-X da Redação", page_icon="", layout="wide")
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
        escolha = "(colar meu texto)"
        if exemplos:
            escolha = st.selectbox(
                "Carregar exemplo", ["(colar meu texto)"] + list(exemplos)
            )
            if escolha != "(colar meu texto)":
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
             help="Cada assunto que a redação trata, contado uma vez só.")
    b.metric("Ligações", d.num_relacoes,
             help="Quantas vezes uma ideia leva a outra: \"X provoca Y\", \"X gera Y\".")
 

    if d.cadeia is None:
        c.metric("Sequência de ideias", "—",
                 help="Não foi possível calcular: há um argumento em círculo no texto.")
    else:
        c.metric("Sequência de ideias", d.tamanho_da_cadeia,
                 help="Quantos passos a redação encadeia, uma ideia levando à outra. "
                      "É o número que melhor prevê a nota de coerência.")

    e.metric("Frases aproveitadas", f"{d.cobertura:.0%}",
             help="Das frases da redação, quantas o programa conseguiu ler como "
                  "uma ligação entre ideias.")
 
 
def mostrar_achados(d) -> None:
    st.subheader("O que encontramos")
 
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
            f"{indefinidos} dos {len(d.achados)} pontos acima estão marcados como "
            "\"não sabemos avaliar\". Isso é proposital: testamos esses indicadores em "
            "160 redações já corrigidas por humanos e eles não distinguiram texto bom "
            "de ruim, então preferimos mostrar o número sem dar veredito. O "
            "encadeamento das ideias, sim, foi validado."
        )
 
 
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
            for frase in frases:
                st.write(f"“{frase}”")
 
 
def _rotulo_legivel(d, rotulo: str) -> str:
    """Nomes legíveis dos conceitos agrupados num super-vértice condensado."""
    if d.condensacao is None:
        return rotulo
    membros = d.condensacao.membros.get(rotulo, {rotulo})
    return " + ".join(sorted(d.exibir(m) for m in membros))
 
 
def mostrar_estrutura_argumento(d) -> None:

    if d.condensacao is None:
        return
 
    st.subheader("Espinha dorsal do argumento")
    st.caption(
    )
 
    if not d.maior_caminho:
        st.info("Não há uma cadeia a destacar neste texto.")
        return
 
    passos = max(d.tamanho_maior_caminho - 1, 0)
    inicio = _rotulo_legivel(d, d.maior_caminho[0])
    fim = _rotulo_legivel(d, d.maior_caminho[-1])
 
    st.metric(
        "Maior cadeia (grafo condensado)", f"{passos} passo(s)",
        help="Caminho mais longo no DAG condensado — a sequência de ideias "
             "mais extensa que o texto sustenta, ponta a ponta.",
    )
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
 
