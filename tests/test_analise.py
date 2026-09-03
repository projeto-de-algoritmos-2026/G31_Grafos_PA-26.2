 
import unittest
 
from src.analise import condensar, kahn, maior_caminho_dag
from src.grafo import Grafo
from tests import grafos_exemplo as ex
 
 
class TestCondensar(unittest.TestCase):
 
    def test_com_ciclo_vira_dois_super_vertices(self):
        g = ex.com_ciclo()
        condensacao = condensar(g)
 
        self.assertEqual(condensacao.grafo.num_vertices, 2)
        rotulo_laco = "a + b + c"
        self.assertIn(rotulo_laco, condensacao.grafo)
        self.assertIn("d", condensacao.grafo)
        self.assertIsNotNone(condensacao.grafo.aresta(rotulo_laco, "d"))
 
    def test_membros_do_super_vertice_batem_com_o_scc(self):
        condensacao = condensar(ex.com_ciclo())
        self.assertEqual(condensacao.membros["a + b + c"], {"a", "b", "c"})
        self.assertEqual(condensacao.membros["d"], {"d"})
 
    def test_rotulo_de_mapeia_todo_conceito_original(self):
        g = ex.cormen_22_9()
        condensacao = condensar(g)
        for v in g.vertices:
            self.assertIn(v, condensacao.rotulo_de)
 
    def test_resultado_e_sempre_um_dag(self):
        condensacao = condensar(ex.cormen_22_9())
        for aresta in condensacao.grafo.arestas():
            self.assertNotEqual(aresta.origem, aresta.destino)
        self.assertIsNotNone(kahn(condensacao.grafo))
 
    def test_dag_sem_ciclo_condensa_para_ele_mesmo(self):
        g = ex.dag_simples()
        condensacao = condensar(g)
        self.assertEqual(condensacao.grafo.num_vertices, g.num_vertices)
        self.assertEqual(condensacao.grafo.num_arestas, g.num_arestas)
 
    def test_aceita_sccs_ja_calculados_sem_recalcular(self):
        g = ex.com_ciclo()
        sccs = [{"a", "b", "c"}, {"d"}]
        condensacao = condensar(g, sccs)
        self.assertEqual(condensacao.grafo.num_vertices, 2)
 
    def test_grafo_vazio(self):
        condensacao = condensar(Grafo())
        self.assertEqual(condensacao.grafo.num_vertices, 0)
        self.assertEqual(condensacao.membros, {})
 
 
class TestMaiorCaminhoDag(unittest.TestCase):
 
    def test_dag_simples_acha_o_caminho_mais_longo(self):
        caminho = maior_caminho_dag(ex.dag_simples())
        self.assertEqual(caminho, ["a", "b", "c"])
 
    def test_grafo_com_ciclo_devolve_none(self):
        self.assertIsNone(maior_caminho_dag(ex.com_ciclo()))
 
    def test_funciona_apos_condensar_um_grafo_com_ciclo(self):
        g = ex.com_ciclo()
        condensacao = condensar(g)
        caminho = maior_caminho_dag(condensacao.grafo)
        self.assertEqual(caminho, ["a + b + c", "d"])
 
    def test_grafo_vazio(self):
        self.assertEqual(maior_caminho_dag(Grafo()), [])
 
    def test_vertice_isolado(self):
        g = Grafo()
        g.adicionar_vertice("solitario")
        self.assertEqual(maior_caminho_dag(g), ["solitario"])
 
    def test_prefere_caminho_mais_longo_a_atalho_mais_barato(self):
        g = Grafo()
        g.adicionar_aresta("x", "z")
        for _ in range(10):
            g.adicionar_aresta("x", "y")
        g.adicionar_aresta("y", "z")
        caminho = maior_caminho_dag(g)
        self.assertEqual(caminho, ["x", "y", "z"])
 
 
if __name__ == "__main__":
    unittest.main()
 
