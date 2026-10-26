---
id_disciplina: "DEMO"
disciplina: "DEMO"
id_aula: "DEMO123"
video_id: "DEMO123"
data: "2026-10-25"
hora: "17:48"
titulo: "Árvores binárias de busca"
canal: ""
idioma_legenda: ""
legenda_automatica: false
pagina: "https://moodle.exemplo.edu.br/course/view.php?id=123"
pagina_titulo: "AVA - Estruturas de Dados"
duracao: "02:42"
partes: 1
falhas: []
modelo: "qwen3:4b-instruct"
gerado_em: "2026-10-25T17:48:32"
tags: ["aula", "DEMO"]
---

# Árvores binárias de busca

**Disciplina:** DEMO (`DEMO`) · **Data:** 2026-10-25 · **Duração:** 02:42 · **Fonte:** https://moodle.exemplo.edu.br/course/view.php?id=123

## Resumo

- Uma árvore binária de busca é uma estrutura de dados onde cada nó tem no máximo dois filhos.
- A propriedade fundamental é que todos os elementos na subárvore esquerda são menores e na direita são maiores do que a chave do nó.
- A busca começa na raiz e segue para esquerda ou direita com base na comparação da chave procurada.
- O custo de busca é proporcional à altura da árvore: O(n) no pior caso e O(log n) em árvores balanceadas.
- Exemplo dado mostra inserção de chaves 50, 30, 70, 20 e 40 na árvore binária de busca.
- O trabalho prático envolve implementar inserção, busca e remoção em Python.
- Lista ordenada tem custo alto para inserção por deslocamento de elementos, enquanto árvores balanceadas têm inserção e busca em O(log n).
- Na próxima aula serão abordadas rotações e árvores AVL.

## Conceitos-chave

| Termo | Definição |
| --- | --- |
| **árvore binária de busca** | estrutura de dados onde cada nó tem no máximo dois filhos, com propriedade que todos os elementos na subárvore esquerda são menores e na direita são maiores do que a chave do nó. |
| **altura da árvore** | número de nós no caminho mais longo desde a raiz até uma folha, determina o custo de busca. |
| **busca em árvore binária de busca** | começa na raiz e compara a chave procurada com o valor do nó; se menor, vai para esquerda; se maior, para direita; termina ao encontrar ou chegar em uma folha. |
| **complexidade de busca** | no pior caso é O(n), quando a árvore é degenerada; em árvores balanceadas é O(log n). |

## Desenvolvimento
### Propriedade da árvore binária de busca  
`00:02` · `00:27`
- Todos os elementos na subárvore esquerda são menores que a chave do nó.
- Todos os elementos na subárvore direita são maiores que a chave do nó.
- Essa propriedade se aplica recursivamente para todas as subárvores.

### Algoritmo de busca em árvore binária de busca  
`00:27` · `00:47`
- A busca começa na raiz e compara a chave procurada com o valor do nó.
- Se for igual, encontramos; se menor, descemos para esquerda; se maior, para direita.
- O processo repete até encontrar ou chegar em uma folha.

### Custo da busca e comparação com listas ordenadas  
`00:47` · `01:08` · `02:12`
- O custo é proporcional à altura da árvore.
- No pior caso, a busca custa O(n); em árvores balanceadas, custa O(log n).
- Inserir em uma lista ordenada custa O(n) devido ao deslocamento dos elementos; na árvore, custa O(log n).

### Exemplo de inserção em árvore binária de busca  
`01:08` · `01:30` · `01:52`
- Inserimos 50 como raiz.
- 30 vai para a esquerda porque é menor que 50.
- 70 vai para a direita porque é maior que 50.
- 20 vai para o filho esquerdo de 30, pois é menor que ambos.
- 40 vai para o filho direito de 30, pois é maior que 30 e menor que 50.

### Trabalho prático e leitura para próxima aula  
`01:52` · `02:12`
- O trabalho deve implementar inserção, busca e remoção em Python.
- A entrega é na próxima sexta-feira pelo ambiente virtual.
- Para a próxima aula, devem ser lidos o capítulo quatro do livro, seção de árvores balanceadas.

## Fórmulas

- `O(n)` `01:08` — complexidade do custo da busca em um pior caso, quando a árvore é degenerada e tem altura n.
- `O(log n)` `01:08` — complexidade do custo da busca em uma árvore balanceada, com altura logarítmica de n na base dois.

## Exemplos

- Inserção das chaves 50, 30, 70, 20 e 40 em uma árvore binária de busca com as seguintes relações: 50 é raiz; 30 à esquerda; 70 à direita; 20 filho esquerdo de 30; 40 filho direito de 30. `01:30`

## Pontos de dúvida

- Por que não usar uma lista ordenada em vez de uma árvore binária de busca?
- Como a inserção funciona na árvore binária de busca e qual é o seu custo?

## Tarefas e prazos

- **Implementar inserção, busca e remoção em uma árvore binária de busca em Python.**
  - prazo dito: "na próxima sexta-feira" · ouvido em `01:52`
  - evidência: O trabalho prático vai ser entregue na próxima sexta-feira. O trabalho deve implementar inserção, busca e remoção em uma árvore binária de busca. A entrega é pelo ambiente virtual, em um arquivo único em Python.
- **Ler o capítulo quatro do livro, seção de árvores balanceadas.**
  - prazo dito: "para a próxima aula" · ouvido em `02:12`
  - evidência: Para a próxima aula, leiam o capítulo quatro do livro, seção de árvores balanceadas.

## Perguntas de revisão

1. O que é uma árvore binária de busca e como ela funciona?
2. Por que a inserção em uma lista ordenada é mais lenta do que em uma árvore binária de busca?
3. Qual é o custo da busca em uma árvore binária degenerada e em uma árvore balanceada?
4. Como os elementos são posicionados durante a inserção em uma árvore binária de busca?
