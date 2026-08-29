"""
Testes da identificação de tema e proposta (src/alvos.py).

Os testes de estrutura usam grafos montados à mão e rodam sempre. Os que
precisam interpretar texto são pulados sem o modelo do spaCy instalado.
"""

import unittest

from src import extracao
from src.alvos import (
    VERBOS_DE_INTERVENCAO,
    Alvos,
    _casar_com_grafo,
    identificar,
    identificar_propostas,
    identificar_tema,
)
from src.extracao import Extrator
from src.grafo import Grafo


def _modelo_disponivel() -> bool:
    try:
        extracao.carregar_modelo()
    except Exception:
        return False
    return True


requer_modelo = unittest.skipUnless(
    _modelo_disponivel(), "modelo pt_core_news_sm não instalado"
)


class TestAlvos(unittest.TestCase):

    def test_precisa_dos_dois_pontos(self):
        self.assertFalse(Alvos().utilizavel)
        self.assertFalse(Alvos(tema="pobreza").utilizavel)
        self.assertFalse(Alvos(propostas=["escola"]).utilizavel)
        self.assertTrue(Alvos(tema="pobreza", propostas=["escola"]).utilizavel)

    def test_resumo_diz_o_que_falta(self):
        self.assertIn("sem tema", Alvos(propostas=["escola"]).resumo())
        self.assertIn("sem proposta", Alvos(tema="pobreza").resumo())

    def test_resumo_completo_cita_o_tema(self):
        resumo = Alvos(tema="pobreza", origem_do_tema="titulo", propostas=["escola"]).resumo()
        self.assertIn("pobreza", resumo)
        self.assertIn("titulo", resumo)


class TestCasamento(unittest.TestCase):
    """O adjetivo varia; o núcleo nominal é a parte estável."""

    def setUp(self):
        self.grafo = Grafo.de_pares([
            ("comunidade tradicional", "invisibilidade social"),
            ("política público", "marginalização"),
        ])

    def test_casamento_exato(self):
        self.assertEqual(
            _casar_com_grafo("comunidade tradicional", self.grafo),
            ["comunidade tradicional"],
        )

    def test_casamento_pelo_nucleo(self):
        """'comunidade' no título deve achar 'comunidade tradicional' no grafo."""
        self.assertEqual(_casar_com_grafo("comunidade", self.grafo), ["comunidade tradicional"])

    def test_adjetivo_diferente_ainda_casa(self):
        self.assertEqual(
            _casar_com_grafo("comunidade ribeirinho", self.grafo),
            ["comunidade tradicional"],
        )

    def test_conceito_ausente(self):
        self.assertEqual(_casar_com_grafo("agronegócio", self.grafo), [])

    def test_nucleo_diferente_nao_casa(self):
        self.assertEqual(_casar_com_grafo("marginalidade", self.grafo), [])


@requer_modelo
class TestIdentificarTema(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.extrator = Extrator()

    def test_prefere_o_titulo(self):
        grafo = Grafo.de_pares([("pobreza", "evasão escolar"), ("escola", "cidadania")])
        tema, fonte, _ = identificar_tema(
            grafo, self.extrator, titulo="A pobreza no Brasil", introducao="A escola forma cidadãos."
        )
        self.assertEqual(tema, "pobreza")
        self.assertEqual(fonte, "titulo")

    def test_recua_para_a_introducao(self):
        grafo = Grafo.de_pares([("escola", "cidadania")])
        tema, fonte, _ = identificar_tema(
            grafo, self.extrator, titulo="Assunto inexistente aqui",
            introducao="A escola forma cidadãos.",
        )
        self.assertEqual(tema, "escola")
        self.assertEqual(fonte, "introducao")

    def test_prefere_conceito_com_grau_de_saida(self):
        """Uma folha não serve de origem: o Dijkstra não sairia do lugar."""
        grafo = Grafo.de_pares([("pobreza", "exclusão")])
        tema, _, _ = identificar_tema(
            grafo, self.extrator, titulo="A exclusão e a pobreza no país"
        )
        self.assertEqual(tema, "pobreza")

    def test_sem_candidato_no_grafo(self):
        grafo = Grafo.de_pares([("pobreza", "exclusão")])
        tema, fonte, candidatos = identificar_tema(
            grafo, self.extrator, titulo="A malha ferroviária brasileira"
        )
        self.assertIsNone(tema)
        self.assertEqual(fonte, "")
        self.assertTrue(candidatos, "os candidatos deviam ser reportados mesmo sem casar")

    def test_sem_texto_nenhum(self):
        grafo = Grafo.de_pares([("pobreza", "exclusão")])
        self.assertEqual(identificar_tema(grafo, self.extrator), (None, "", []))


@requer_modelo
class TestIdentificarPropostas(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.extrator = Extrator()

    def test_objeto_de_verbo_de_intervencao(self):
        grafo = Grafo.de_pares([("ministério", "campanha educativo"), ("escola", "cidadania")])
        propostas = identificar_propostas(
            grafo, self.extrator,
            "Portanto, o Ministério deve promover campanhas educativas nas escolas.",
        )
        self.assertIn("campanha educativo", propostas)

    def test_recua_para_todos_os_conceitos(self):
        """Sem verbo de intervenção, o fecho inteiro vira candidato."""
        grafo = Grafo.de_pares([("pobreza", "exclusão")])
        propostas = identificar_propostas(
            grafo, self.extrator, "Em suma, a pobreza permanece um problema."
        )
        self.assertIn("pobreza", propostas)

    def test_conclusao_vazia(self):
        grafo = Grafo.de_pares([("pobreza", "exclusão")])
        self.assertEqual(identificar_propostas(grafo, self.extrator, "   "), [])

    def test_so_devolve_conceitos_que_existem_no_grafo(self):
        grafo = Grafo.de_pares([("pobreza", "exclusão")])
        propostas = identificar_propostas(
            grafo, self.extrator, "É preciso garantir a reforma agrária imediatamente."
        )
        for conceito in propostas:
            self.assertIn(conceito, grafo)

    def test_sem_repetir_conceito(self):
        grafo = Grafo.de_pares([("estado", "saneamento básico")])
        propostas = identificar_propostas(
            grafo, self.extrator,
            "O Estado deve garantir o saneamento básico e ampliar o saneamento básico.",
        )
        self.assertEqual(len(propostas), len(set(propostas)))


@requer_modelo
class TestIdentificarCompleto(unittest.TestCase):

    def test_ponta_a_ponta(self):
        extrator = Extrator()
        texto = (
            "A desigualdade social compromete o acesso à educação no Brasil. "
            "A falta de acesso à educação aprofunda a desigualdade social. "
            "Portanto, o Ministério da Educação deve ampliar o acesso à educação."
        )
        resultado = extrator.extrair(texto)
        alvos = identificar(
            resultado, extrator,
            titulo="A desigualdade social e a educação",
            conclusao="Portanto, o Ministério da Educação deve ampliar o acesso à educação.",
        )
        self.assertTrue(alvos.utilizavel, alvos.resumo())
        self.assertIsNotNone(alvos.tema)


class TestVocabulario(unittest.TestCase):

    def test_verbos_estao_no_infinitivo(self):
        """A comparação é feita contra o lema, que vem no infinitivo."""
        for verbo in VERBOS_DE_INTERVENCAO:
            self.assertTrue(verbo.endswith(("ar", "er", "ir")), verbo)

    def test_verbos_em_minuscula(self):
        for verbo in VERBOS_DE_INTERVENCAO:
            self.assertEqual(verbo, verbo.lower())


if __name__ == "__main__":
    unittest.main()
