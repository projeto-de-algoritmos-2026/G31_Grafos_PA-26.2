# Dados

## `exemplo_sintetico_com_laco.txt`

Redação **sintética**, escrita pela dupla para servir de caso de teste. Não é
uma redação real do ENEM e não deve ser usada como evidência de nada sobre
redações reais.

Ela contém, de propósito:

- uma **cadeia causal** longa (`agronegócio → expulsão → práticas ancestrais →
  identidade cultural`), que a ordenação topológica deve devolver inteira;
- um **laço argumentativo** de três conceitos (`representatividade midiática →
  preconceito estrutural → políticas públicas → representatividade midiática`),
  que o Tarjan deve identificar como um único componente fortemente conectado;
- uma **proposta de intervenção** no último parágrafo, alvo do Dijkstra a
  partir do conceito-tema;
- as construções sintáticas que motivaram cada refinamento da extração
  (substantivo leve, oração relativa, aposto entre vírgulas, coordenação,
  verbo subordinado).

Extração atual: 19 conceitos, 17 arestas, cobertura de 91% das frases.

## Corpus real

As redações reais entram aqui na etapa de validação (03/09), separadas em
dois grupos — nota 1000 e com falha estrutural — para comparar as métricas
entre eles. Arquivos brutos não versionados ficam em `data/raw/`, que está
no `.gitignore`.
