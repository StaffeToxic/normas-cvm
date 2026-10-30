# Revisão das versões e relações

Checkpoint de implementação em 29/10/2026, horário de Brasília. **T007 em andamento**.

## Resultado executado

**201 testes** passaram, incluindo dez cenários novos de versões. Entradas corrompidas ou
ambíguas reproduziram falhas antes das correções:

- Negativa de alteração era registrada como relação positiva.
- Uma frase com alteração e revogação atribuía os links ao tipo errado.
- Revogação parcial perdia o vínculo para a revogadora.
- Republicação parcial era rotulada como original e podia produzir estado publicado.
- O rótulo “sem marcas” isolado era interpretado como prova de consolidação.

Agora cada link segue a declaração que o precede. A revogação parcial mantém o contexto e o
vínculo, mas não transforma `revogada` em `true`. Negação não vira relação positiva.

Um candidato de republicação ou versão ambígua tem `version: None` apenas internamente, com
motivo. Não cria enum público. O motivo da cobertura identifica o artefato por URL. Um original
aprovado pode permanecer publicado enquanto a republicação fica pendente.

Os testes também executaram original e consolidado HTML com caminhos e hashes distintos,
contados como um ato. Após corromper somente o consolidado, o original foi preservado e o ato
passou a pendente. Uma contradição de status na mesma página conserva ambas as declarações no
relatório, sem publicar a versão conflitante; a resolução da contradição retira o apontamento.

## Limites deste checkpoint

- Os cenários de duas versões publicáveis são sintéticos. A Resolução 175 real ainda exige
  PDF e tratamento de tabelas; não se declaram seus dois arquivos aprovados.
- Os três artefatos de republicação já conhecidos continuam pendentes até verificação própria;
  não se certificaram os nove casos da triagem nem se importou corpo auxiliar.
- Agregação de aliases semânticos, comparação entre páginas oficiais e fixtures reais
  complementares ainda estão em execução no ticket. Não se marca T007 concluído aqui.

## Consolidação posterior: aliases e fontes reais

A suíte passou a **211 testes**. As novas verificações agregam somente IDs já confirmados em
páginas oficiais, preservando cada URL. O contador bruto de URLs continua no catálogo; o
denominador da cobertura só diminui quando duas entradas foram confirmadas como o mesmo ato.
Um candidato ainda não visitado não é agregado por semelhança de número/data. Um teste retira
uma entrada e ajusta os contadores para esconder a remoção; o vínculo com o catálogo detecta
a adulteração mesmo com a soma interna consistente.

Aliases conhecidos são reavaliados juntos ao processar um ato, inclusive com limite um. Isso
evita conservar uma divergência antiga apenas porque a segunda URL ficou fora do limite.
Divergências preservam os valores/trechos e as páginas oficiais, tanto no JSON quanto no
relatório humano. Dois hashes recebidos para a mesma URL ficam explícitos no relato; nenhum
é escolhido silenciosamente como hash corrente, nem se infere alteração jurídica só por bytes.

O relatório humano passou a mostrar também métricas da coleta, divergências, URLs alternativas
e hashes. Foi regenerado offline a partir do JSON existente, cujos bytes não mudaram.

As seis fixtures adicionais vêm de bytes oficiais com manifesto. Confirmaram Pareceres de
Orientação 39/2021 e 40/2022, sem íntegra HTML nesses recortes; a Deliberação 870 mantém seu tipo
pela epígrafe, mesmo quando o contexto do catálogo for incorreto. A 175 tem 17 candidatos de
artefato, versões original/consolidada e oito alteradoras no snapshot, sem transformar ausência
de outro link em prova de inexistência.

As páginas 59 e 110 foram novamente requisitadas pelo cliente commitado; cinco requisições,
incluindo robots, zero falhas HTTP. Os outros recortes reutilizam downloads já disponíveis;
timestamps exatos ausentes continuam UNVERIFIED no manifesto. A 59 identifica “redação original”
separadamente do consolidado, apesar do aviso de republicação da página. O código não bloqueia
automaticamente todos os artefatos por esse aviso. As três normas 59/100/110 permaneceram
pendentes no teste com as páginas reais e o conversor PDF ainda desativado; não houve aprovação
dos artefatos de republicação da compilação auxiliar.

Foi refinada uma expectativa de teste: “NÃO REVOGADA pela norma X” não prova ausência de
revogação por outra norma. Essa negativa qualificada agora deixa o status `null` e não cria
relação positiva. `false` exige uma declaração global explícita, como “NÃO REVOGADA.” ou
“Em vigor”. O caso falhou antes da correção e passou depois.

O fundamento de versões e aliases está implementado. O aceite integral de US2 com dois
Markdowns reais da 175 continua condicionado a PDF/tabelas e aos gates; sua tabela LIG segue
sem aprovação automática. Nenhuma dessas verificações substitui FR-014 por documento.

## Coleta real da 175

Código `e6537e6`, dados `9dc613b`. A CLI foi executada contra a página oficial da Resolução 175,
com catálogo completo existente. Resultado: quatro requisições incluindo robots, zero falhas,
um ato processado e cobertura total inalterada em 249 atos: um publicado e 248 pendentes.
O registro da 175 agora tem identidade confirmada, hash da página
`551f4059dc6369c239a3668d78bf571fd22beaee6690ef6e0f2b56a8e4f95e29` e motivo
`consolidada: anexo-revisao-manual; publicação original: pdf-conversor-pendente`.
Não foram publicados arquivos da 175 nem declarada sua tabela aprovada.

Após commitar, a mesma coleta foi repetida: `changed: false`, um ato reavaliado, quatro
requisições, zero falhas, Git limpo. O reprocessamento de uma pendência em modo documento não
invocou conversor PDF nem alterou datas públicas. O verificador offline, com os caches oficiais
reutilizados, retornou `violacoes: []`, `UNVERIFIED: []` para os controles implementados.
Esses resultados encerram a implementação do fundamento T007; o aceite completo de US2 com
PDF/tabelas continua nos tickets posteriores e não foi certificado.
