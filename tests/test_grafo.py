
import unittest

from src.grafo import Aresta, Grafo
from tests import grafos_exemplo as ex


class TestConstrucao(unittest.TestCase):

    def test_aresta_cria_os_vertices(self):
        g = Grafo()
        g.adicionar_aresta("pobreza", "evasao escolar")
        self.assertEqual(g.num_vertices, 2)
        self.assertIn("pobreza", g)
        self.assertIn("evasao escolar", g)

    def test_vertice_isolado(self):
        g = Grafo()
        g.adicionar_vertice("conceito orfao")
        self.assertEqual(g.num_vertices, 1)
        self.assertEqual(g.num_arestas, 0)

    def test_adicionar_vertice_e_idempotente(self):
        g = Grafo()
        g.adicionar_vertice("x")
        g.adicionar_vertice("x")
        self.assertEqual(g.num_vertices, 1)

    def test_laco_e_rejeitado(self):
        g = Grafo()
        with self.assertRaises(ValueError):
            g.adicionar_aresta("x", "x")

    def test_ordem_de_insercao_preservada(self):
        g = Grafo.de_pares([("c", "a"), ("a", "b")])
        self.assertEqual(g.vertices, ["c", "a", "b"])


class TestPesos(unittest.TestCase):

    def test_relacao_unica_tem_peso_um(self):
        g = Grafo()
        g.adicionar_aresta("a", "b")
        self.assertEqual(g.aresta("a", "b").peso, 1.0)

    def test_relacao_repetida_fica_mais_barata(self):
        g = Grafo()
        for _ in range(4):
            g.adicionar_aresta("a", "b")
        aresta = g.aresta("a", "b")
        self.assertEqual(aresta.frequencia, 4)
        self.assertEqual(aresta.peso, 0.25)

    def test_repetir_nao_duplica_a_aresta(self):
        g = Grafo()
        for _ in range(3):
            g.adicionar_aresta("a", "b")
        self.assertEqual(g.num_arestas, 1)

    def test_pesos_sao_sempre_positivos(self):
        g = ex.pesos_dijkstra()
        for aresta in g.arestas():
            self.assertGreater(aresta.peso, 0.0)
            self.assertLessEqual(aresta.peso, 1.0)

    def test_aresta_sem_ocorrencia_nao_tem_peso(self):
        with self.assertRaises(ValueError):
            _ = Aresta("a", "b").peso


class TestRastreabilidade(unittest.TestCase):

    def test_frases_ficam_guardadas(self):
        g = Grafo()
        g.adicionar_aresta("agronegocio", "expulsao", "A expansão provoca a expulsão.")
        g.adicionar_aresta("agronegocio", "expulsao", "O avanço gera expulsão.")
        frases = g.aresta("agronegocio", "expulsao").frases
        self.assertEqual(len(frases), 2)
        self.assertIn("A expansão provoca a expulsão.", frases)

    def test_frase_e_opcional(self):
        g = Grafo()
        g.adicionar_aresta("a", "b")
        self.assertEqual(g.aresta("a", "b").frases, [])


class TestConsulta(unittest.TestCase):

    def test_aresta_inexistente_devolve_none(self):
        g = ex.dag_simples()
        self.assertIsNone(g.aresta("c", "a"))

    def test_vizinhos_traz_destino_e_peso(self):
        g = ex.dag_simples()
        self.assertEqual(dict(g.vizinhos("a")), {"b": 1.0, "c": 1.0})

    def test_vizinhos_de_vertice_sem_saida(self):
        g = ex.dag_simples()
        self.assertEqual(list(g.vizinhos("c")), [])

    def test_grau_entrada(self):
        g = ex.dag_simples()
        self.assertEqual(g.grau_entrada(), {"a": 0, "b": 1, "c": 2})

    def test_grau_entrada_cobre_todos_os_vertices(self):
        g = ex.com_ciclo()
        self.assertEqual(set(g.grau_entrada()), set(g.vertices))

    def test_contagem_no_exemplo_do_cormen(self):
        g = ex.cormen_22_9()
        self.assertEqual(g.num_vertices, 8)
        self.assertEqual(g.num_arestas, 13)


class TestTransposto(unittest.TestCase):

    def test_inverte_as_arestas(self):
        t = ex.dag_simples().transposto()
        self.assertIsNotNone(t.aresta("b", "a"))
        self.assertIsNone(t.aresta("a", "b"))

    def test_preserva_vertices_e_contagem(self):
        g = ex.cormen_22_9()
        t = g.transposto()
        self.assertEqual(set(t.vertices), set(g.vertices))
        self.assertEqual(t.num_arestas, g.num_arestas)

    def test_preserva_os_pesos(self):
        g = ex.pesos_dijkstra()
        t = g.transposto()
        self.assertEqual(t.aresta("s", "a"), None)
        self.assertEqual(t.aresta("a", "s").peso, g.aresta("s", "a").peso)

    def test_transposto_do_transposto(self):
        g = ex.com_ciclo()
        tt = g.transposto().transposto()
        originais = {(a.origem, a.destino) for a in g.arestas()}
        voltas = {(a.origem, a.destino) for a in tt.arestas()}
        self.assertEqual(originais, voltas)


if __name__ == "__main__":
    unittest.main()
