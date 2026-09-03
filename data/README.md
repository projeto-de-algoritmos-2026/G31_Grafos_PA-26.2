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

Extração atual: **20 conceitos, 20 relações, 91% das frases aproveitadas
(10 de 11)**. Para reproduzir:

```bash
python -m src.extracao data/exemplo_sintetico_com_laco.txt
```

Como o laço é proposital, este exemplo **não** produz a sequência de ideias: o
Kahn não ordena grafo com ciclo, e o laudo devolve "não sabemos avaliar" na
Competência 3. Isso é esperado enquanto a condensação dos componentes não
entrar no caminho do cálculo.

## Corpus real

A validação usa o [Essay-BR](https://github.com/rafaelanchieta/essay) — 4.570
redações de estudantes do ensino médio, com nota por competência. Os grupos
comparados são os extremos de uma competência (por exemplo, C3 ≥ 160 contra
C3 ≤ 80), amostrados com semente fixa para os números do README serem
reproduzíveis.

Os arquivos brutos ficam em `data/raw/`, que está no `.gitignore` — o corpus
não é versionado aqui. Rodar `python validacao.py` sem ele imprime os
comandos de download.
