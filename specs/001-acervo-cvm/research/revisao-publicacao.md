# Verificação dos gates de publicação

Execução local com Python 3.12.13, em 29/10/2026. Sem HTTP novo nesta etapa.

## Resultado executado

A suíte completa executou **166 testes**, incluindo **41 testes contratuais novos**. Os casos
usam a fixture oficial da Resolução 249, fixtures estruturais e entradas corrompidas. A saída
integral esperada da 249 foi registrada como golden, acompanhada da proveniência e das
limitações; não é chamada de transcrição independente.

| Verificação | Prova negativa executada |
|---|---|
| Sequência exata de texto e dispositivos | Remoção, permutação e duplicação de trechos; mudança de sinal, decimal e acento |
| Extração independente do artefato | Anexo omitido simultaneamente da referência e do Markdown é detectado pelo HTML original |
| Tabelas | Achatamento, alteração de mesclagem e grade sobreposta são rejeitados |
| Links, tachado e imagens | Destino alterado, tachado removido e imagem desconhecida são rejeitados |
| Formato editorial | Dispositivo sem negrito ou anexo sem heading é rejeitado |
| Proveniência | Hash de Markdown no lugar do hash da fonte, URL/data de coleta incorretas e íntegra relabelada são rejeitados |
| Anexos | Descoberta desconhecida ou URL descoberta sem proveniência correspondente bloqueia publicação |
| Schema | Campos ausentes, extras, tipos errados e identidade incompatível são rejeitados |
| Cobertura | Contagem divergente, duplicação, publicação sem identidade e caminho inválido são rejeitados |
| Versões mistas | Original aprovado e consolidado pendente contam uma vez como pendente, mantendo apenas o arquivo aprovado |
| Idempotência | Mudança somente de métricas/datas mantém os bytes públicos e o horário de modificação |
| Falha de gravação | Erro na segunda promoção restaura o primeiro arquivo; exclusão seguida de erro também é revertida |

O gate editorial encontrou um detalhe real na 249: `Parágrafo único:` não recebia negrito.
O normalizador agora preserva e inclui os dois-pontos no marcador. Uma regressão verifica a
frase real, sem trocar a pontuação da fonte.

## Limites

- A implementação desta etapa é para o MVP, com uma categoria na cobertura. As outras famílias
  permanecem nos tickets posteriores, com seus testes próprios.
- O leitor sem dependências aceita o perfil YAML emitido pelo coletor: uma chave por linha,
  valores no formato flow JSON. Edições fora desse perfil são rejeitadas de forma conservadora;
  não se alega suporte a todo YAML.
- A promoção prepara todos os bytes e reverte falhas capturadas. Recuperação após desligamento
  abrupto do processo ou da máquina permanece **UNVERIFIED**; não se alega transação de filesystem
  resistente a queda de energia.
- Os gates não fazem inferência jurídica de vigência. A descoberta de anexos depende dos links
  oficiais inspecionados; descoberta ainda desconhecida bloqueia publicação.
- SC-001..SC-009 não são certificados por esta suíte. A coleta real pela CLI, repetição sem
  alterações, 50 HTMLs e tabelas oficiais complexas continuam dependentes das etapas seguintes.
