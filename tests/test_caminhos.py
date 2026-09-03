
import unittest

from src.caminhos import (
    caminho_tema_proposta,
    dijkstra,
    distancia,
    orbita,
    reconstruir_caminho,
    INFINITO,
)
from src.grafo import Grafo
from tests import grafos_exemplo as ex


class TestDijkstra(unittest.TestCase):

    def test_distancias_batem_com_o_esperado(self):
        distancias, _ = dijkstra(ex.pesos_dijkstra(), "s")
        for v, esperado in ex.PESOS_DISTANCIAS.items():
            self.assertAlmostEqual(distancias[v], esperado, places=6)

    def test_ignora_caminho_ganancioso(self):
        distancias, _ = dijkstra(ex.pesos_dijkstra(), "s")
        self.assertAlmostEqual(distancias["b"], 0.75, places=6)

    def test_origem_tem_distancia_zero(self):
        distancias, _ = dijkstra(ex.pesos_dijkstra(), "s")
        self.assertEqual(distancias["s"], 0.0)

    def test_vertice_inalcancavel_nao_aparece_no_dicionario(self):
        distancias, _ = dijkstra(ex.desconexo(), "tema")
        self.assertNotIn("proposta", distancias)
        self.assertNotIn("acao", distancias)

    def test_origem_inexistente_devolve_vazio(self):
        distancias, predecessores = dijkstra(ex.pesos_dijkstra(), "não existe")
        self.assertEqual(distancias, {})
        self.assertEqual(predecessores, {})

    def test_grafo_vazio(self):
        distancias, predecessores = dijkstra(Grafo(), "qualquer")
        self.assertEqual(distancias, {})
        self.assertEqual(predecessores, {})

    def test_vertice_isolado_sem_saida(self):
        g = Grafo()
        g.adicionar_vertice("sozinho")
        distancias, _ = dijkstra(g, "sozinho")
        self.assertEqual(distancias, {"sozinho": 0.0})


class TestReconstruirCaminho(unittest.TestCase):

    def test_caminho_ate_d_bate_com_o_esperado(self):
        _, predecessores = dijkstra(ex.pesos_dijkstra(), "s")
        caminho = reconstruir_caminho(predecessores, "s", "d")
        self.assertEqual(caminho, ex.PESOS_CAMINHO_ATE_D)

    def test_caminho_ate_a_propria_origem(self):
        _, predecessores = dijkstra(ex.pesos_dijkstra(), "s")
        caminho = reconstruir_caminho(predecessores, "s", "s")
        self.assertEqual(caminho, ["s"])

    def test_caminho_para_destino_inalcancavel_e_none(self):
        _, predecessores = dijkstra(ex.desconexo(), "tema")
        caminho = reconstruir_caminho(predecessores, "tema", "proposta")
        self.assertIsNone(caminho)


class TestDistancia(unittest.TestCase):

    def test_distancia_de_vertice_alcancado(self):
        distancias, _ = dijkstra(ex.pesos_dijkstra(), "s")
        self.assertAlmostEqual(distancia(distancias, "c"), 1.0, places=6)

    def test_distancia_de_vertice_inalcancavel_e_infinito(self):
        distancias, _ = dijkstra(ex.desconexo(), "tema")
        self.assertEqual(distancia(distancias, "proposta"), INFINITO)


class TestCaminhoTemaProposta(unittest.TestCase):

    def test_proposta_alcancavel_encontra_o_caminho(self):
        g = ex.pesos_dijkstra()
        resultado = caminho_tema_proposta(g, tema="s", propostas=["d"])

        self.assertTrue(resultado.alcancavel)
        self.assertEqual(resultado.melhor_proposta, "d")
        self.assertAlmostEqual(resultado.custo, 1.5, places=6)
        self.assertEqual(resultado.caminho, ex.PESOS_CAMINHO_ATE_D)

    def test_proposta_inalcancavel_e_a_falha_da_competencia_5(self):
        g = ex.desconexo()
        resultado = caminho_tema_proposta(g, tema="tema", propostas=["proposta"])

        self.assertFalse(resultado.alcancavel)
        self.assertIsNone(resultado.melhor_proposta)
        self.assertEqual(resultado.custo, INFINITO)
        self.assertIsNone(resultado.caminho)

    def test_com_varias_propostas_escolhe_a_mais_barata(self):
        g = ex.pesos_dijkstra()
        resultado = caminho_tema_proposta(g, tema="s", propostas=["d", "c"])

        self.assertEqual(resultado.melhor_proposta, "c")
        self.assertAlmostEqual(resultado.custo, 1.0, places=6)

    def test_custos_por_proposta_reporta_todas_mesmo_as_inalcancaveis(self):
        g = ex.desconexo()
        resultado = caminho_tema_proposta(g, tema="tema", propostas=["proposta", "argumento"])

        self.assertEqual(resultado.custos_por_proposta["argumento"], 1.0)
        self.assertEqual(resultado.custos_por_proposta["proposta"], INFINITO)


class TestOrbita(unittest.TestCase):

    def test_orbita_e_equivalente_ao_dijkstra_bruto(self):
        distancias_esperadas, _ = dijkstra(ex.pesos_dijkstra(), "s")
        self.assertEqual(orbita(ex.pesos_dijkstra(), "s"), distancias_esperadas)

    def test_conceito_fora_da_orbita_nao_aparece(self):
        distancias = orbita(ex.desconexo(), "tema")
        self.assertNotIn("proposta", distancias)


if __name__ == "__main__":
    unittest.main()