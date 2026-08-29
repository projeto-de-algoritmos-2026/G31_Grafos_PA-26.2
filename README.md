# Raio-X da Redação

**Número do Grupo:** 31 &nbsp;·&nbsp; **Conteúdo da Disciplina:** Grafos

Diagnóstico da estrutura argumentativa de redações do ENEM por meio de algoritmos em grafos direcionados.

## Alunos

| Matrícula | Aluno |
| --- | --- |
| 222006534 | Anna Clara Cardoso Evangelista Brandão |
| 231026699 | Eduarda Domingos Rodrigues |

## Sobre

Uma redação dissertativo-argumentativa bem construída tem uma **cadeia causal**: o tema leva a uma causa, a causa a uma consequência, a consequência à proposta de intervenção. Textos com falha estrutural apresentam duas patologias recorrentes:

- **argumentação circular** — o autor justifica A com B e depois justifica B com A, e no fim não avançou;
- **partes desconectadas** — a proposta de intervenção trata de algo que os argumentos nunca prepararam.

A proposta deste trabalho é que essas duas percepções são **propriedades topológicas de um grafo direcionado** e, portanto, detectáveis por algoritmo:

| Percepção do leitor | Propriedade do grafo |
| --- | --- |
| "o texto anda em círculo" | componente fortemente conectado com mais de um vértice |
| "a conclusão veio do nada" | não existe caminho do tema até a proposta |

O aplicativo recebe a redação e o tema da prova e devolve um diagnóstico visual: cadeia argumentativa em ordem topológica, laços destacados, caminho mínimo entre tema e proposta, e conceitos órfãos. O diagnóstico é **rastreável** — cada aresta do grafo aponta para a frase original que a gerou.

## Modelagem

**Vértices** são conceitos: o núcleo nominal lematizado de cada sintagma relevante, com seu adjetivo adnominal (`identidade cultural`, `política pública`).

**Arestas** são direcionadas e vêm da análise sintática de dependências: para cada verbo, o substantivo que é seu sujeito recebe uma aresta para o substantivo que é seu objeto. A frase *"a expansão do agronegócio provoca a expulsão de povos indígenas"* produz `agronegócio → expulsão`. Semanticamente, `u → v` significa **"u leva a / justifica v"**.

**Pesos** são o inverso da frequência da relação. Uma relação que o autor afirma três vezes ao longo do texto está bem sustentada e, por isso, é barata de percorrer; uma relação mencionada de passagem é cara. O caminho mínimo passa a ser o **argumento mais bem sustentado**, não apenas o mais curto em número de saltos. Como a frequência é sempre ≥ 1, os pesos estão em (0, 1] — positivos, condição de validade do Dijkstra.

## Algoritmos implementados

Todos os algoritmos deste repositório foram **implementados do zero pela dupla**. Nenhuma biblioteca de grafos é utilizada — apenas estruturas da biblioteca padrão do Python.

| Algoritmo | Complexidade | O que revela no texto | Competência ENEM |
| --- | --- | --- | --- |
| Tarjan (SCC) | `O(V + E)` | Laços argumentativos: conjuntos de conceitos que se justificam mutuamente | C3 — coerência |
| Kahn (ordenação topológica) sobre o grafo condensado | `O(V + E)` | A cadeia argumentativa do texto e sua maior sequência causal | C3 — progressão |
| Dijkstra | `O((V + E) log V)` | Conexão entre o tema e a proposta de intervenção; conceitos periféricos | C2 e C5 |
| A* *(opcional)* | `O((V + E) log V)` | O mesmo caminho, com heurística semântica; comparação de nós expandidos | — |

Notas de implementação:

- **Tarjan é iterativo**, com pilha explícita. A versão recursiva estoura o limite de recursão do Python em textos maiores.
- A **condensação** dos componentes é o que torna a ordenação topológica possível: o grafo condensado é sempre um DAG (Cormen, cap. 22). Sem ela, um único ciclo no texto faria a ordenação falhar por inteiro.
- **Nem todo ciclo é defeito.** Ciclos viciosos existem no mundo real e podem estar sendo descritos de propósito. O aplicativo detecta e aponta; a interpretação fica com quem lê.
- **Árvore Geradora Mínima ficou de fora** por decisão de modelagem: exige grafo não-direcionado, e ignorar a direção responderia quase à mesma pergunta que a maior cadeia topológica já responde, com menos significado.

## Estrutura do projeto

```
├── app.py                 interface Streamlit
├── src/
│   ├── grafo.py           classe Grafo — lista de adjacência, sem biblioteca
│   ├── scc.py             Tarjan iterativo + condensação
│   ├── topologica.py      Kahn + maior caminho no DAG
│   ├── caminhos.py        Dijkstra com heap + A* opcional
│   ├── extracao.py        texto → conceitos e arestas (spaCy)
│   └── diagnostico.py     orquestra os algoritmos e traduz para as competências
├── tests/                 grafos pequenos com resposta conhecida
└── data/                  redações de exemplo
```

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download pt_core_news_sm
```

O modelo `pt_core_news_sm` **não possui vetores de palavra** (`nlp.vocab.vectors.shape == (0, 0)`). O A* opcional depende deles e exige o modelo médio: `python -m spacy download pt_core_news_md`.

## Uso

```bash
streamlit run app.py
```

## Testes

```bash
python -m unittest discover -s tests -t .
```

Os grafos de teste estão em `tests/grafos_exemplo.py` e têm resposta conhecida de antemão — incluindo o grafo da figura 22.9 do Cormen, o exemplo canônico de componentes fortemente conectados. Quando um teste falha, o problema está no algoritmo, nunca na expectativa.

## Apresentação

`<link do vídeo>`

## Origem do tema

O tema nasceu do interesse das autoras por análise automática de redações, explorado antes em um trabalho de outra disciplina que modelava o texto como uma rede **não-direcionada** de coocorrência de palavras. A modelagem em grafo direcionado, o diagnóstico estrutural e todos os algoritmos deste repositório são novos e foram desenvolvidos para esta disciplina.

## Referências

- CORMEN, T. H. et al. *Introduction to Algorithms*. 3. ed. Capítulos 22 a 24.
- BRASIL. INEP. *A redação no ENEM: cartilha do participante* — matriz de
  competências.
