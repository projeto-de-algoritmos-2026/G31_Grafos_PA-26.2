
import unittest

from validacao import Grupo, grafico_svg, melhor_corte, tabela_markdown


class TestGrupo(unittest.TestCase):

    def test_grupo_vazio_nao_quebra(self):
        g = Grupo("vazio")
        self.assertEqual(g.n, 0)
        self.assertEqual(g.mediana, 0.0)
        self.assertEqual(g.quartil(0.5), 0.0)

    def test_quartis(self):
        g = Grupo("teste", list(range(1, 101)))
        self.assertEqual(g.quartil(0.25), 25.0)
        self.assertEqual(g.mediana, 50.5)
        self.assertEqual(g.quartil(0.75), 75.0)

    def test_quartil_ignora_ordem_de_entrada(self):
        self.assertEqual(Grupo("t", [9, 1, 5]).quartil(0.5), 5.0)


class TestMelhorCorte(unittest.TestCase):

    def test_grupos_perfeitamente_separados(self):
        altas = Grupo("alta", [10, 11, 12])
        baixas = Grupo("baixa", [1, 2, 3])
        corte, taxa = melhor_corte(altas, baixas)
        self.assertEqual(taxa, 1.0)
        self.assertTrue(3 < corte <= 10)

    def test_grupos_identicos_nao_separam(self):
        valores = [5, 6, 7, 8]
        _, taxa = melhor_corte(Grupo("a", valores), Grupo("b", list(valores)))
        self.assertLessEqual(taxa, 0.75)

    def test_grupo_vazio_devolve_zero(self):
        self.assertEqual(melhor_corte(Grupo("a", [1, 2]), Grupo("b")), (0, 0.0))

    def test_taxa_e_uma_fracao(self):
        altas = Grupo("a", [20, 25, 30, 12])
        baixas = Grupo("b", [5, 8, 22, 15])
        _, taxa = melhor_corte(altas, baixas)
        self.assertGreaterEqual(taxa, 0.5)
        self.assertLessEqual(taxa, 1.0)

    def test_separacao_invertida_nao_e_premiada(self):
        altas = Grupo("a", [1, 2, 3])
        baixas = Grupo("b", [10, 11, 12])
        _, taxa = melhor_corte(altas, baixas)
        self.assertLessEqual(taxa, 0.5)


class TestGrafico(unittest.TestCase):

    def setUp(self):
        self.altas = Grupo("alta", [20, 25, 30, 35, 28, 22])
        self.baixas = Grupo("baixa", [8, 12, 15, 18, 11, 14])

    def desenhar(self, **kwargs):
        base = dict(corte=20, taxa=0.75, competencia=3,
                    metrica="comprimento da cadeia argumentativa")
        base.update(kwargs)
        return grafico_svg(self.altas, self.baixas, **base)

    def test_svg_bem_formado(self):
        svg = self.desenhar()
        self.assertTrue(svg.startswith("<svg"))
        self.assertTrue(svg.rstrip().endswith("</svg>"))

    def test_tem_as_duas_cores_da_paleta_validada(self):
        svg = self.desenhar()
        self.assertIn("#0F8F71", svg)
        self.assertIn("#B8461F", svg)

    def test_corte_e_taxa_aparecem_no_desenho(self):
        svg = self.desenhar(corte=20, taxa=0.74)
        self.assertIn("corte 20", svg)
        self.assertIn("74%", svg)

    def test_cada_faceta_se_nomeia(self):
        svg = self.desenhar()
        self.assertIn("Nota alta", svg)
        self.assertIn("Nota baixa", svg)

    def test_fundo_explicito(self):
        self.assertIn('fill="#FCFCFB"', self.desenhar())

    def test_grupos_vazios_nao_quebram(self):
        svg = grafico_svg(Grupo("a"), Grupo("b"), corte=0, taxa=0.0,
                          competencia=3, metrica="x")
        self.assertTrue(svg.startswith("<svg"))


class TestTabela(unittest.TestCase):

    def test_tem_uma_linha_por_grupo(self):
        tabela = tabela_markdown(
            Grupo("alta", [20, 30]), Grupo("baixa", [5, 10]), 15, 0.9, "métrica"
        )
        self.assertIn("| alta |", tabela)
        self.assertIn("| baixa |", tabela)
        self.assertIn("90%", tabela)


if __name__ == "__main__":
    unittest.main()
