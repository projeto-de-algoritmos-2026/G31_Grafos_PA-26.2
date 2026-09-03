
import unittest

from src import corpus
from src.corpus import COMPETENCIAS, Redacao, amostra, carregar, estatisticas, filtrar


def _redacao(indice=0, notas=(160, 160, 120, 120, 120), tema_id=1, paragrafos=None) -> Redacao:
    if paragrafos is None:
        paragrafos = ("Primeiro parágrafo.", "Meio.", "Conclusão com proposta.")
    return Redacao(
        indice=indice,
        titulo=f"Título {indice}",
        paragrafos=paragrafos,
        tema_id=tema_id,
        tema="Texto motivador do tema.",
        competencias=notas,
        nota=sum(notas),
    )


def _corpus_disponivel() -> bool:
    return (corpus.CAMINHO_PADRAO / "essay-br.csv").exists()


requer_corpus = unittest.skipUnless(
    _corpus_disponivel(), "corpus Essay-BR não baixado (ver src/corpus.py)"
)


class TestRedacao(unittest.TestCase):

    def test_texto_junta_os_paragrafos(self):
        r = _redacao(paragrafos=("Um.", "Dois."))
        self.assertEqual(r.texto, "Um.\n\nDois.")

    def test_conclusao_e_o_ultimo_paragrafo(self):
        r = _redacao(paragrafos=("Introdução.", "Desenvolvimento.", "Proposta."))
        self.assertEqual(r.conclusao, "Proposta.")

    def test_conclusao_de_redacao_vazia_nao_quebra(self):
        r = _redacao(paragrafos=())
        self.assertEqual(r.conclusao, "")

    def test_competencias_por_nome(self):
        r = _redacao(notas=(200, 180, 160, 140, 120))
        self.assertEqual(r.norma_culta, 200)
        self.assertEqual(r.compreensao_do_tema, 180)
        self.assertEqual(r.coerencia, 160)
        self.assertEqual(r.coesao, 140)
        self.assertEqual(r.proposta_de_intervencao, 120)

    def test_competencia_por_numero(self):
        r = _redacao(notas=(200, 180, 160, 140, 120))
        self.assertEqual(r.competencia(3), 160)
        self.assertEqual(r.competencia(1), r.norma_culta)
        self.assertEqual(r.competencia(5), r.proposta_de_intervencao)

    def test_competencia_fora_da_faixa(self):
        r = _redacao()
        for invalido in (0, 6, -1):
            with self.assertRaises(ValueError):
                r.competencia(invalido)

    def test_nomes_das_competencias(self):
        self.assertEqual(len(COMPETENCIAS), 5)


class TestParsingDeListas(unittest.TestCase):

    def test_lista_serializada(self):
        self.assertEqual(corpus._como_lista("['a', 'b']"), ("a", "b"))

    def test_lista_de_numeros(self):
        self.assertEqual(corpus._como_lista("[160, 120]"), (160, 120))

    def test_texto_solto_vira_item_unico(self):
        self.assertEqual(corpus._como_lista("sem colchetes"), ("sem colchetes",))

    def test_aspas_desbalanceadas_nao_quebram(self):
        self.assertEqual(corpus._como_lista("['aberta"), ("['aberta",))


class TestFiltrar(unittest.TestCase):

    def setUp(self):
        self.redacoes = [
            _redacao(0, notas=(200, 200, 200, 200, 200), tema_id=1),
            _redacao(1, notas=(120, 120, 120, 120, 120), tema_id=1),
            _redacao(2, notas=(40, 40, 40, 40, 40), tema_id=2),
        ]

    def test_sem_criterio_devolve_tudo(self):
        self.assertEqual(len(filtrar(self.redacoes)), 3)

    def test_por_nota_total(self):
        altas = filtrar(self.redacoes, minimo=600)
        self.assertEqual([r.indice for r in altas], [0, 1])

    def test_por_competencia_especifica(self):
        boas_em_c3 = filtrar(self.redacoes, competencia=3, minimo=160)
        self.assertEqual([r.indice for r in boas_em_c3], [0])

    def test_faixa_fechada(self):
        meio = filtrar(self.redacoes, competencia=3, minimo=100, maximo=160)
        self.assertEqual([r.indice for r in meio], [1])

    def test_por_tema(self):
        self.assertEqual(len(filtrar(self.redacoes, tema_id=1)), 2)

    def test_por_numero_de_paragrafos(self):
        curta = _redacao(3, paragrafos=("Só um.",))
        self.assertEqual(len(filtrar(self.redacoes + [curta], min_paragrafos=3)), 3)

    def test_grupos_da_validacao_nao_se_sobrepoem(self):
        altas = filtrar(self.redacoes, competencia=3, minimo=160)
        baixas = filtrar(self.redacoes, competencia=3, maximo=80)
        self.assertEqual({r.indice for r in altas} & {r.indice for r in baixas}, set())


class TestAmostra(unittest.TestCase):

    def setUp(self):
        self.redacoes = [_redacao(i) for i in range(50)]

    def test_tamanho_pedido(self):
        self.assertEqual(len(amostra(self.redacoes, 10)), 10)

    def test_pedido_maior_que_o_corpus(self):
        self.assertEqual(len(amostra(self.redacoes, 999)), 50)

    def test_e_reprodutivel(self):
        a = [r.indice for r in amostra(self.redacoes, 10, semente=7)]
        b = [r.indice for r in amostra(self.redacoes, 10, semente=7)]
        self.assertEqual(a, b)

    def test_sementes_diferentes_dao_amostras_diferentes(self):
        a = [r.indice for r in amostra(self.redacoes, 10, semente=1)]
        b = [r.indice for r in amostra(self.redacoes, 10, semente=2)]
        self.assertNotEqual(a, b)


class TestEstatisticas(unittest.TestCase):

    def test_corpus_vazio(self):
        self.assertEqual(estatisticas([]), {"redacoes": 0})

    def test_medias(self):
        st = estatisticas([
            _redacao(0, notas=(200, 200, 200, 200, 200)),
            _redacao(1, notas=(100, 100, 100, 100, 100)),
        ])
        self.assertEqual(st["redacoes"], 2)
        self.assertEqual(st["nota_media"], 750)
        self.assertEqual(st["competencias_media"], [150] * 5)


class TestSplitInvalido(unittest.TestCase):

    def test_nome_de_split_errado(self):
        with self.assertRaises(ValueError):
            carregar(split="treino")


@requer_corpus
class TestCorpusReal(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.redacoes = carregar()

    def test_quantidade_esperada(self):
        self.assertGreater(len(self.redacoes), 4000)

    def test_toda_redacao_tem_cinco_competencias(self):
        for r in self.redacoes[:200]:
            self.assertEqual(len(r.competencias), 5)

    def test_notas_dentro_da_escala_do_enem(self):
        for r in self.redacoes[:200]:
            self.assertTrue(all(0 <= n <= 200 for n in r.competencias), r.competencias)
            self.assertTrue(0 <= r.nota <= 1000)

    def test_paragrafos_sao_texto_de_verdade(self):
        r = self.redacoes[0]
        self.assertGreater(len(r.texto), 200)
        self.assertIn(" ", r.texto)

    def test_temas_foram_associados(self):
        com_tema = [r for r in self.redacoes if r.tema]
        self.assertGreater(len(com_tema), len(self.redacoes) * 0.9)

    def test_split_e_menor_que_o_todo(self):
        dev = carregar(split="development")
        self.assertGreater(len(dev), 0)
        self.assertLess(len(dev), len(self.redacoes))

    def test_ha_material_para_os_dois_grupos_da_validacao(self):
        altas = filtrar(self.redacoes, competencia=3, minimo=160)
        baixas = filtrar(self.redacoes, competencia=3, maximo=80)
        self.assertGreater(len(altas), 50, "poucas redações com C3 alta")
        self.assertGreater(len(baixas), 50, "poucas redações com C3 baixa")


if __name__ == "__main__":
    unittest.main()
