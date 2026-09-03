

import unittest

from src import extracao as _extracao
from src.alvos import Alvos
from src.diagnostico import (
    ATENCAO,
    OBSERVACAO,
    CADEIA_CORTE,
    CADEIA_MEDIANA_BOA,
    FALHA,
    INDEFINIDO,
    OK,
    Achado,
    Diagnostico,
    _avaliar_lacos,
    _avaliar_progressao,
    _avaliar_proposta,
    _avaliar_tema,
    diagnosticar,
)
from src.extracao import Extracao, Extrator
from src.grafo import Grafo


def _cadeia(n: int) -> Grafo:
    g = Grafo()
    for i in range(n - 1):
        g.adicionar_aresta(f"c{i}", f"c{i+1}")
    return g


def _extracao_de(grafo: Grafo, rotulos=None) -> Extracao:
    return Extracao(grafo=grafo, rotulos=rotulos or {})


def _modelo_disponivel() -> bool:
    try:
        _extracao.carregar_modelo()
    except Exception:
        return False
    return True


requer_modelo = unittest.skipUnless(
    _modelo_disponivel(), "modelo pt_core_news_sm não instalado"
)


class TestCalibragem(unittest.TestCase):
    def test_o_corte_medido_e_respeitado(self):
        self.assertEqual(CADEIA_CORTE, 20)
        self.assertEqual(CADEIA_MEDIANA_BOA, 29)
        self.assertLess(CADEIA_CORTE, CADEIA_MEDIANA_BOA)


class TestProgressao(unittest.TestCase):
    def avaliar(self, n):
        g = _cadeia(n)
        return _avaliar_progressao(g, list(g.vertices))

    def test_cadeia_longa_e_aprovada(self):
        a = self.avaliar(CADEIA_MEDIANA_BOA + 5)
        self.assertEqual(a.status, OK)
        self.assertIn(str(CADEIA_MEDIANA_BOA), a.resumo)

    def test_cadeia_na_faixa_boa(self):
        a = self.avaliar(CADEIA_CORTE + 2)
        self.assertEqual(a.status, OK)
        self.assertNotIn(str(CADEIA_MEDIANA_BOA), a.resumo)

    def test_exatamente_no_corte_ainda_passa(self):
        self.assertEqual(self.avaliar(CADEIA_CORTE).status, OK)

    def test_um_abaixo_do_corte_vira_atencao(self):
        a = self.avaliar(CADEIA_CORTE - 1)
        self.assertEqual(a.status, ATENCAO)
        self.assertIn(str(CADEIA_CORTE), a.resumo)

    def test_grafo_vazio_e_falha(self):
        a = _avaliar_progressao(Grafo(), None)
        self.assertEqual(a.status, FALHA)

    def test_grafo_ciclico_fica_indefinido(self):
        g = Grafo.de_pares([("a", "b"), ("b", "a")])
        a = _avaliar_progressao(g, None)
        self.assertEqual(a.status, INDEFINIDO)
        self.assertIn("nosso cálculo", a.resumo)
        self.assertIn("não do seu texto", a.resumo)

    def test_sempre_e_competencia_3(self):
        self.assertEqual(self.avaliar(25).competencia, 3)


class TestLacos(unittest.TestCase):

    def test_sem_laco_nao_gera_achado(self):
        self.assertIsNone(_avaliar_lacos([], _extracao_de(Grafo())))

    def test_laco_e_observacao_nao_alerta(self):
        a = _avaliar_lacos([["a", "b", "c"]], _extracao_de(Grafo()))
        self.assertEqual(a.status, OBSERVACAO)
        self.assertNotIn(a.status, (ATENCAO, FALHA))

    def test_laco_nao_entra_na_lista_de_problemas(self):
        d = Diagnostico(
            extracao=_extracao_de(_cadeia(3)), alvos=Alvos(),
            achados=[_avaliar_lacos([["a", "b"]], _extracao_de(Grafo()))],
        )
        self.assertEqual(d.problemas, [])

    def test_mostra_o_ciclo_como_evidencia(self):
        a = _avaliar_lacos([["pobreza", "desemprego"]], _extracao_de(Grafo()))
        self.assertEqual(len(a.evidencias), 1)
        self.assertIn("pobreza", a.evidencias[0])
        self.assertIn("⇄", a.evidencias[0])

    def test_plural_com_mais_de_um_laco(self):
        a = _avaliar_lacos([["a", "b"], ["c", "d"]], _extracao_de(Grafo()))
        self.assertIn("2 grupo", a.resumo)

    def test_usa_o_rotulo_de_exibicao(self):
        e = _extracao_de(Grafo(), {"política público": "políticas públicas"})
        a = _avaliar_lacos([["política público", "x"]], e)
        self.assertIn("políticas públicas", a.evidencias[0])


class TestTema(unittest.TestCase):
    def test_sem_tema_fica_indefinido(self):
        g = _cadeia(5)
        achado, orfaos = _avaliar_tema(g, Alvos(), _extracao_de(g))
        self.assertEqual(achado.status, INDEFINIDO)
        self.assertEqual(len(orfaos), 5)

    def test_com_tema_continua_indefinido(self):
        g = _cadeia(5)
        achado, _ = _avaliar_tema(g, Alvos(tema="c0"), _extracao_de(g))
        self.assertEqual(achado.status, INDEFINIDO)

    def test_reporta_o_alcance_real(self):
        g = _cadeia(5)
        g.adicionar_vertice("solto")
        achado, orfaos = _avaliar_tema(g, Alvos(tema="c0"), _extracao_de(g))
        self.assertIn("5 das 6", achado.resumo)
        self.assertEqual(orfaos, ["solto"])

    def test_explica_por_que_nao_conclui(self):
        g = _cadeia(3)
        achado, _ = _avaliar_tema(g, Alvos(tema="c0"), _extracao_de(g))
        self.assertIn("não sabemos ler", achado.resumo)


class TestProposta(unittest.TestCase):
    def test_sem_proposta_identificada_e_falha(self):
        g = _cadeia(3)
        a = _avaliar_proposta(g, Alvos(tema="c0"), None, _extracao_de(g))
        self.assertEqual(a.status, FALHA)

    def test_proposta_inalcancavel_fica_indefinido(self):
        from src.caminhos import caminho_tema_proposta

        g = Grafo.de_pares([("tema", "meio"), ("proposta", "outra")])
        alvos = Alvos(tema="tema", propostas=["proposta"])
        caminho = caminho_tema_proposta(g, "tema", ["proposta"])
        a = _avaliar_proposta(g, alvos, caminho, _extracao_de(g))
        self.assertEqual(a.status, INDEFINIDO)
        self.assertNotEqual(a.status, FALHA)

    def test_proposta_alcancavel_e_ok_com_rastro(self):
        from src.caminhos import caminho_tema_proposta

        g = Grafo()
        g.adicionar_aresta("tema", "meio", "O tema leva ao meio.")
        g.adicionar_aresta("meio", "proposta", "O meio sustenta a proposta.")
        alvos = Alvos(tema="tema", propostas=["proposta"])
        caminho = caminho_tema_proposta(g, "tema", ["proposta"])
        a = _avaliar_proposta(g, alvos, caminho, _extracao_de(g))
        self.assertEqual(a.status, OK)
        self.assertIn("tema → meio → proposta", a.evidencias[0])
        self.assertTrue(
            any("O tema leva ao meio." in e for e in a.evidencias),
            "as frases originais deviam aparecer como evidência",
        )


class TestDiagnostico(unittest.TestCase):
    def setUp(self):
        self.d = Diagnostico(
            extracao=_extracao_de(_cadeia(4)),
            alvos=Alvos(),
            achados=[
                Achado(3, "progressão", ATENCAO, "curta"),
                Achado(2, "alcance do tema", INDEFINIDO, "fragmentado"),
                Achado(5, "proposta", FALHA, "ausente"),
                Achado(3, "circularidade", OK, "sem laços"),
            ],
        )

    def test_achados_por_competencia(self):
        self.assertEqual(len(self.d.achados_de(3)), 2)
        self.assertEqual(len(self.d.achados_de(2)), 1)

    def test_indefinido_fica_fora_dos_conclusivos(self):
        self.assertEqual(len(self.d.conclusivos), 3)

    def test_problemas_vem_do_mais_grave(self):
        status = [a.status for a in self.d.problemas]
        self.assertEqual(status, [FALHA, ATENCAO])

    def test_indefinido_nunca_e_problema(self):
        for a in self.d.problemas:
            self.assertNotEqual(a.status, INDEFINIDO)

    def test_atalhos_de_leitura(self):
        self.assertEqual(self.d.num_conceitos, 4)
        self.assertEqual(self.d.num_relacoes, 3)
        self.assertEqual(self.d.tamanho_da_cadeia, 0)

    def test_exibir_recua_para_a_chave(self):
        self.assertEqual(self.d.exibir("inexistente"), "inexistente")


@requer_modelo
class TestPontaAPonta(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.extrator = Extrator()

    def test_redacao_curta_nao_quebra(self):
        d = diagnosticar("A pobreza gera a exclusão.", extrator=self.extrator)
        self.assertGreaterEqual(len(d.achados), 3)

    def test_texto_vazio_nao_quebra(self):
        d = diagnosticar("", extrator=self.extrator)
        self.assertEqual(d.num_conceitos, 0)

    def test_toda_competencia_esperada_aparece(self):
        texto = (
            "A desigualdade social compromete o acesso à educação.\n\n"
            "A falta de acesso à educação aprofunda a pobreza.\n\n"
            "Portanto, o Ministério da Educação deve ampliar o acesso à educação."
        )
        d = diagnosticar(texto, titulo="Desigualdade e educação", extrator=self.extrator)
        competencias = {a.competencia for a in d.achados}
        self.assertEqual(competencias, {2, 3, 5})

    def test_resumo_e_legivel(self):
        d = diagnosticar("A pobreza gera a exclusão.", extrator=self.extrator)
        self.assertIn("conceitos", d.resumo())


if __name__ == "__main__":
    unittest.main()