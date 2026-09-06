# Dados

## Redações de exemplo

As três são **sintéticas**, escritas pela dupla para servir de caso de teste. Não
são redações reais do ENEM e não devem ser usadas como evidência de nada sobre
redações reais. Cada uma foi escrita para cair num diagnóstico diferente, de
modo que trocar de exemplo no aplicativo mostre o laudo mudando.

| arquivo | conceitos | relações | cobertura | o que exercita |
| --- | --- | --- | --- | --- |
| `exemplo_sintetico_bem_encadeado.txt` | 38 | 26 | 87% | texto longo e encadeado — C3 aprovada |
| `exemplo_sintetico_com_laco.txt` | 20 | 20 | 91% | argumento em círculo — Tarjan e condensação |
| `exemplo_sintetico_fragmentado.txt` | 8 | 5 | 36% | ideias soltas — C3 em alerta, cobertura baixa |

Para reproduzir qualquer linha da tabela:

```bash
python -m src.extracao data/<arquivo>.txt
```

### `exemplo_sintetico_com_laco.txt`

É o mais completo, e contém de propósito:

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

É também o exemplo que justifica a condensação: sem ela, o laço trava o Kahn e a
Competência 3 sairia como "não sabemos avaliar" — logo neste texto, que a
medição no corpus indica não ser pior por ter um ciclo.

## Corpus real

A validação usa o [Essay-BR](https://github.com/rafaelanchieta/essay) — 4.570
redações de estudantes do ensino médio, com nota por competência. Os grupos
comparados são os extremos de uma competência (por exemplo, C3 ≥ 160 contra
C3 ≤ 80), amostrados com semente fixa para os números do README serem
reproduzíveis.

Os arquivos brutos ficam em `data/raw/`, que está no `.gitignore` — o corpus
não é versionado aqui. Rodar `python validacao.py` sem ele imprime os
comandos de download.
