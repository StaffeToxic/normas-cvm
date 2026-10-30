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
