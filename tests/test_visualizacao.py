"""
Testes do desenho do grafo (src/visualizacao.py).

Gerar DOT é função pura: entra um diagnóstico, sai uma string. Dá para
testar tudo sem spaCy e sem subir o Streamlit, que é justamente a razão de
a geração viver aqui e não dentro do `app.py`.
"""

import unittest

from src.alvos import Alvos
from src.caminhos import caminho_tema_proposta
from src.diagnostico import Diagnostico
from src.extracao import Extracao
from src.grafo import Grafo
from src.visualizacao import BORDA_CAMINHO, BORDA_LACO, legenda, para_dot


def _diagnostico(grafo, **kwargs) -> Diagnostico:
    rotulos = kwargs.pop("rotulos", {})
    return Diagnostico(extracao=Extracao(grafo=grafo, rotulos=rotulos),
                       alvos=kwargs.pop("alvos", Alvos()), **kwargs)


class TestEstrutura(unittest.TestCase):

    def test_grafo_vazio_gera_dot_valido(self):
        dot = para_dot(_diagnostico(Grafo()))
        self.assertTrue(dot.startswith("digraph redacao {"))
        self.assertTrue(dot.rstrip().endswith("}"))

    def test_todo_vertice_aparece(self):
        g = Grafo.de_pares([("a", "b"), ("b", "c")])
        dot = para_dot(_diagnostico(g))
        for v in ("a", "b", "c"):
            self.assertIn(f'"{v}" [', dot)

    def test_toda_aresta_aparece(self):
        g = Grafo.de_pares([("a", "b")])
        self.assertIn('"a" -> "b"', para_dot(_diagnostico(g)))

    def test_conceito_isolado_pode_ser_escondido(self):
        g = Grafo.de_pares([("a", "b")])
        g.adicionar_vertice("solto")
        self.assertIn('"solto"', para_dot(_diagnostico(g)))
        self.assertNotIn('"solto"', para_dot(_diagnostico(g), apenas_conectados=True))


class TestRotulos(unittest.TestCase):

    def test_usa_a_forma_de_exibicao(self):
        g = Grafo.de_pares([("política público", "exclusão")])
        dot = para_dot(_diagnostico(g, rotulos={"política público": "políticas públicas"}))
        self.assertIn('label="políticas públicas"', dot)

    def test_aspas_no_conceito_nao_quebram_o_dot(self):
        g = Grafo()
        g.adicionar_aresta('a "b"', "c")
        dot = para_dot(_diagnostico(g))
        self.assertIn('\\"b\\"', dot)

    def test_frase_com_aspas_na_tooltip_nao_quebra(self):
        g = Grafo()
        g.adicionar_aresta("a", "b", 'Ele disse "isso" ontem.')
        dot = para_dot(_diagnostico(g))
        self.assertNotIn('tooltip="Ele disse "isso"', dot)


class TestDestaques(unittest.TestCase):

    def test_laco_sai_em_vermelho(self):
        g = Grafo.de_pares([("a", "b"), ("b", "a")])
        dot = para_dot(_diagnostico(g, lacos=[["a", "b"]]))
        self.assertIn(BORDA_LACO, dot)

    def test_caminho_sai_em_verde(self):
        g = Grafo.de_pares([("tema", "meio"), ("meio", "fim")])
        d = _diagnostico(
            g, alvos=Alvos(tema="tema", propostas=["fim"]),
            caminho=caminho_tema_proposta(g, "tema", ["fim"]),
        )
        self.assertIn(BORDA_CAMINHO, para_dot(d))

    def test_tema_ganha_contorno_grosso(self):
        g = Grafo.de_pares([("tema", "outro")])
        dot = para_dot(_diagnostico(g, alvos=Alvos(tema="tema")))
        linha = [l for l in dot.splitlines() if l.strip().startswith('"tema" [')][0]
        self.assertIn("penwidth=2.5", linha)

    def test_relacao_repetida_fica_mais_grossa(self):
        g = Grafo()
        for _ in range(3):
            g.adicionar_aresta("a", "b")
        g.adicionar_aresta("c", "d")
        dot = para_dot(_diagnostico(g))
        forte = [l for l in dot.splitlines() if '"a" -> "b"' in l][0]
        fraca = [l for l in dot.splitlines() if '"c" -> "d"' in l][0]
        self.assertIn("3x", forte)
        self.assertNotIn("x\"", fraca)


class TestLegenda(unittest.TestCase):

    def test_cobre_os_tres_estados(self):
        self.assertEqual(len(legenda()), 3)

    def test_cores_batem_com_o_desenho(self):
        cores = {cor for cor, _ in legenda()}
        self.assertIn(BORDA_CAMINHO, cores)
        self.assertIn(BORDA_LACO, cores)


if __name__ == "__main__":
    unittest.main()
