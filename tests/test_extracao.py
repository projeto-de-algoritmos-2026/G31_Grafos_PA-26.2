
import unittest

from src import extracao
from src.extracao import (
    Extrator,
    SUBSTANTIVOS_LEVES,
    SUBSTANTIVOS_VAZIOS,
    _rotulo,
    _texto_exibicao,
)


def _modelo_disponivel() -> bool:
    try:
        extracao.carregar_modelo()
    except Exception:
        return False
    return True


TEM_MODELO = _modelo_disponivel()
requer_modelo = unittest.skipUnless(
    TEM_MODELO, "modelo pt_core_news_sm não instalado"
)


@requer_modelo
class TestRegraBase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.extrator = Extrator()

    def arestas(self, texto):
        grafo = self.extrator.extrair(texto).grafo
        return {(a.origem, a.destino) for a in grafo.arestas()}

    def test_sujeito_vira_causa_e_objeto_vira_consequencia(self):
        arestas = self.arestas(
            "A expansão do agronegócio provoca a expulsão de povos indígenas."
        )
        self.assertIn(("agronegócio", "expulsão"), arestas)

    def test_direcao_nao_se_inverte(self):
        arestas = self.arestas("A pobreza gera a evasão escolar.")
        self.assertIn(("pobreza", "evasão escolar"), arestas)
        self.assertNotIn(("evasão escolar", "pobreza"), arestas)

    def test_frase_sem_verbo_nao_gera_aresta(self):
        resultado = self.extrator.extrair("Educação e cidadania.")
        self.assertEqual(resultado.grafo.num_arestas, 0)


@requer_modelo
class TestRefinamentos(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.extrator = Extrator()

    def arestas(self, texto):
        grafo = self.extrator.extrair(texto).grafo
        return {(a.origem, a.destino) for a in grafo.arestas()}

    def test_a_substantivo_leve_desce_para_o_conceito(self):
        arestas = self.arestas(
            "A ausência de políticas públicas perpetua a marginalização."
        )
        self.assertIn(("política público", "marginalização"), arestas)
        self.assertNotIn(("ausência", "marginalização"), arestas)

    def test_b_oracao_relativa_resolve_o_antecedente(self):
        arestas = self.arestas(
            "A carência de políticas públicas aprofunda a invisibilidade social, "
            "que retroalimenta a escassez de representatividade midiática."
        )
        self.assertTrue(
            any(destino == "representatividade midiático" for _, destino in arestas),
            f"a oração relativa não produziu aresta: {arestas}",
        )

    def test_c_aposto_entre_virgulas_nao_apaga_o_sujeito(self):
        arestas = self.arestas(
            "O preconceito estrutural, por sua vez, desestimula a criação "
            "de políticas públicas."
        )
        self.assertIn(("preconceito estrutural", "política público"), arestas)

    def test_d_objetos_coordenados_geram_duas_arestas(self):
        arestas = self.arestas(
            "A desigualdade provoca a evasão escolar e a violência urbana."
        )
        self.assertIn(("desigualdade", "evasão escolar"), arestas)
        self.assertIn(("desigualdade", "violência urbano"), arestas)

    def test_e_verbo_subordinado_herda_o_sujeito(self):
        arestas = self.arestas(
            "O Ministério da Educação deve promover a demarcação de territórios."
        )
        self.assertIn(("ministério", "demarcação"), arestas)


@requer_modelo
class TestFiltros(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.extrator = Extrator()

    def test_locucao_adverbial_nao_vira_conceito(self):
        grafo = self.extrator.extrair(
            "Dessa forma, a desigualdade compromete a cidadania."
        ).grafo
        self.assertNotIn("forma", grafo.vertices)

    def test_nenhum_conceito_vazio_sobrevive(self):
        grafo = self.extrator.extrair(
            "Em primeiro lugar, a pobreza agrava a exclusão. "
            "Por outro lado, a escola reduz a exclusão."
        ).grafo
        for vertice in grafo.vertices:
            self.assertNotIn(vertice.split()[0], SUBSTANTIVOS_VAZIOS)

    def test_nao_cria_lacos(self):
        texto = (
            "A identidade cultural sustenta a identidade cultural das comunidades. "
            "A pobreza gera pobreza."
        )
        grafo = self.extrator.extrair(texto).grafo
        for aresta in grafo.arestas():
            self.assertNotEqual(aresta.origem, aresta.destino)


@requer_modelo
class TestRastreabilidadeECobertura(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.extrator = Extrator()

    def test_aresta_guarda_a_frase_de_origem(self):
        frase = "A desigualdade provoca a exclusão."
        grafo = self.extrator.extrair(frase).grafo
        aresta = grafo.aresta("desigualdade", "exclusão")
        self.assertIsNotNone(aresta)
        self.assertIn(frase, aresta.frases)

    def test_relacao_repetida_fica_mais_barata(self):
        texto = (
            "A desigualdade provoca a exclusão. "
            "A desigualdade agrava a exclusão. "
            "A escola reduz a exclusão."
        )
        grafo = self.extrator.extrair(texto).grafo
        repetida = grafo.aresta("desigualdade", "exclusão")
        unica = grafo.aresta("escola", "exclusão")
        self.assertEqual(repetida.frequencia, 2)
        self.assertLess(repetida.peso, unica.peso)

    def test_cobertura_e_contabilizada(self):
        resultado = self.extrator.extrair(
            "A pobreza gera exclusão. Educação e cidadania."
        )
        self.assertEqual(resultado.frases_totais, 2)
        self.assertEqual(resultado.frases_produtivas, 1)
        self.assertEqual(resultado.cobertura, 0.5)
        self.assertEqual(len(resultado.frases_sem_aresta), 1)

    def test_cobertura_de_texto_vazio_nao_divide_por_zero(self):
        self.assertEqual(self.extrator.extrair("").cobertura, 0.0)


@requer_modelo
class TestRotulos(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.extrator = Extrator()

    def test_singular_e_plural_viram_o_mesmo_conceito(self):
        grafo = self.extrator.extrair(
            "A política pública combate a exclusão. "
            "As políticas públicas reduzem a exclusão."
        ).grafo
        chaves = [v for v in grafo.vertices if v.startswith("política")]
        self.assertEqual(len(chaves), 1, f"conceitos não agruparam: {chaves}")

    def test_exibicao_corrige_a_concordancia_do_lema(self):
        resultado = self.extrator.extrair(
            "As políticas públicas reduzem a exclusão."
        )
        self.assertEqual(resultado.exibir("política público"), "políticas públicas")

    def test_exibir_recua_para_a_propria_chave(self):
        resultado = self.extrator.extrair("A pobreza gera exclusão.")
        self.assertEqual(resultado.exibir("inexistente"), "inexistente")


class TestVocabulario(unittest.TestCase):

    def test_polaridades_sao_validas(self):
        for palavra, polaridade in SUBSTANTIVOS_LEVES.items():
            self.assertIn(polaridade, (-1, 0, 1), f"polaridade inválida em {palavra}")

    def test_listas_nao_se_sobrepoem(self):
        self.assertEqual(set(SUBSTANTIVOS_LEVES) & SUBSTANTIVOS_VAZIOS, set())


if __name__ == "__main__":
    unittest.main()
