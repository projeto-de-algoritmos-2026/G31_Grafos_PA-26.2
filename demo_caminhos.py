

from src.grafo import Grafo
from src.caminhos import caminho_tema_proposta, orbita
from src.analise import (
    ciclos_argumentativos,
    cadeia_argumentativa,
    rastrear_caminho,
    forca_argumentativa,
    ranking_propostas,
    qualidade_geral,
)


def montar_redacao_bem_amarrada() -> Grafo:
    g = Grafo()
    for u, v, frase in [
        ("desigualdade social", "acesso à educação", 
         "A falta de oportunidades limita o acesso à educação."),
        ("desigualdade social", "acesso à educação",
         "A desigualdade perpetua a exclusão escolar."),
        ("acesso à educação", "qualificação profissional",
         "Educação adequada desenvolve qualificações."),
        ("qualificação profissional", "política pública",
         "Profissionais qualificados demandam políticas inclusivas."),
    ]:
        g.adicionar_aresta(u, v, frase)
    return g


def montar_redacao_com_proposta_solta() -> Grafo:
    g = Grafo()
    g.adicionar_aresta("desigualdade social", "acesso à educação",
                       "A desigualdade afeta oportunidades educacionais.")
    # proposta não conectada a nada que venha do tema: falha da Comp. 5
    g.adicionar_aresta("política pública", "fiscalização",
                       "Políticas devem ser fiscalizadas.")
    return g


def montar_redacao_com_ciclo() -> Grafo:
    """Exemplo de argumentação circular (falha de coerência)."""
    g = Grafo()
    g.adicionar_aresta("pobreza", "falta de educação",
                       "Pobreza impede acesso à educação.")
    g.adicionar_aresta("falta de educação", "desemprego",
                       "Falta de educação causa desemprego.")
    g.adicionar_aresta("desemprego", "pobreza",
                       "Desemprego perpetua a pobreza (ciclo!).")
    return g


def main() -> None:
    print("=" * 70)
    print("CASO 1: Redacao bem estruturada")
    print("=" * 70)
    g1 = montar_redacao_bem_amarrada()
    
    print("\nMetricas gerais:")
    metricas = qualidade_geral(g1)
    for chave, valor in metricas.items():
        if isinstance(valor, float):
            print(f"  {chave}: {valor:.3f}")
        else:
            print(f"  {chave}: {valor}")
    
    print("\nCiclos argumentativos (falha C3 - coerencia):")
    ciclos = ciclos_argumentativos(g1)
    if ciclos:
        for i, ciclo in enumerate(ciclos, 1):
            print(f"  Ciclo {i}: {' <-> '.join(ciclo)}")
    else:
        print("  [OK] Sem ciclos! (boa coerencia)")
    
    print("\nCadeia argumentativa (progressao C3):")
    cadeia = cadeia_argumentativa(g1)
    if cadeia:
        print(f"  {' -> '.join(cadeia)}")
    else:
        print("  [ERRO] Grafo ciclico (sem ordenacao topologica possivel)")
    
    print("\nCaminho tema -> proposta:")
    resultado = caminho_tema_proposta(g1, tema="desigualdade social", 
                                       propostas=["politica publica"])
    print(f"  Alcancavel: {resultado.alcancavel}")
    print(f"  Custo: {resultado.custo:.3f}")
    
    if resultado.caminho:
        print("\nRastreabilidade (frases sustentadoras):")
        rastravel = rastrear_caminho(g1, resultado.caminho)
        print(rastravel)
        
        print(f"\nForca argumentativa: {forca_argumentativa(g1, resultado.caminho):.2%}")
    
    print("\n" + "=" * 70)
    print("CASO 2: Proposta desconectada do tema (falha C5)")
    print("=" * 70)
    g2 = montar_redacao_com_proposta_solta()
    
    print("\nMetricas gerais:")
    metricas2 = qualidade_geral(g2)
    for chave, valor in metricas2.items():
        if isinstance(valor, float):
            print(f"  {chave}: {valor:.3f}")
        else:
            print(f"  {chave}: {valor}")
    
    resultado2 = caminho_tema_proposta(g2, tema="desigualdade social",
                                        propostas=["politica publica"])
    print(f"\n  Alcancavel: {resultado2.alcancavel}")
    print(f"  [FALHA] Proposta nao conectada ao tema (falha C5)")
    
    print("\n" + "=" * 70)
    print("CASO 3: Ciclo argumentativo (falha C3)")
    print("=" * 70)
    g3 = montar_redacao_com_ciclo()
    
    print("\nCiclos detectados (argumentacao circular):")
    ciclos3 = ciclos_argumentativos(g3)
    if ciclos3:
        for i, ciclo in enumerate(ciclos3, 1):
            ciclo_list = sorted(list(ciclo))
            ciclo_str = ' -> '.join(ciclo_list) + f" -> {ciclo_list[0]}"
            print(f"  [CICLO {i}] {ciclo_str}")
    else:
        print("  [OK] Sem ciclos")
    
    print("\nOrdenacao topologica (cadeia argumentativa):")
    cadeia3 = cadeia_argumentativa(g3)
    if cadeia3:
        print(f"  {' -> '.join(cadeia3)}")
    else:
        print("  [ERRO] Nao e possivel (grafo ciclico - incoerente!)")
    
    print("\n" + "=" * 70)
    print("CASO 1 (continuacao): Orbita do tema")
    print("=" * 70)
    distancias = orbita(g1, "desigualdade social")
    print("\nDistancias do tema a cada conceito:")
    for conceito, dist in sorted(distancias.items(), key=lambda item: item[1]):
        print(f"  {conceito}: {dist:.3f}")
    
    print("\n" + "=" * 70)
    print("RANKING DE PROPOSTAS")
    print("=" * 70)
    propostas = ["politica publica", "educacao inclusiva", "reforma agraria"]
    g_ranking = Grafo()
    g_ranking.adicionar_aresta("tema", "politica publica", "A primeira proposta.")
    g_ranking.adicionar_aresta("tema", "educacao inclusiva", "Educacao e importante.")
    g_ranking.adicionar_aresta("tema", "educacao inclusiva", "Muito importante mesmo.")
    g_ranking.adicionar_aresta("tema", "reforma agraria", "Reforma agraria tambem.")
    # "reforma agraria" nao e alcancavel por essa simples construcao
    
    ranking = ranking_propostas(g_ranking, "tema", propostas)
    print("\nPropostas ordenadas por custo (viabilidade):")
    for i, prop in enumerate(ranking, 1):
        status = "[OK]" if prop.alcancavel else "[FALHA]"
        custo_str = f"{prop.custo:.3f}" if prop.alcancavel else "inf"
        print(f"  {i}. {status} {prop.nome}: custo={custo_str}", end="")
        if prop.forca is not None:
            print(f", forca={prop.forca:.2%}", end="")
        print()


if __name__ == "__main__":
    main()