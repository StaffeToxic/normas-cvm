# Validação da atualização incremental

Implementação T008, com **222 testes executados**, onze novos de RSS/atualização. Nenhuma
requisição adicional à CVM foi executada nesta etapa: o RSS real reutiliza bytes já auditados,
com hash de origem e transformação no manifesto; os cenários de coleta usam respostas locais.

## Comportamento implementado

`collect --incremental` consulta os canais de legislação e audiências como sinais e reconcilia
o catálogo completo antes de selecionar trabalho. Não extrai data do ato nem texto normativo do
RSS. Links legados só priorizam uma URL realmente enumerada no catálogo, sem certificar seu
redirecionamento. Sinais de audiências não se tornam resoluções nem produzem publicação de
manifestações; o escopo de minutas permanece no ticket próprio.

A prioridade é: URLs novas, sinais que casam com o catálogo, primeira página e uma fatia
rotativa de 50 URLs em ordem estável. A rotação muda a cada semana UTC iniciada na segunda-feira
e não exige cursor persistente, timestamp novo ou cache durável. Em catálogo fixo, as fatias
cobrem o conjunto após um ciclo; isso não constitui garantia de SLA no agendador externo.

Catálogo/relatório permanecem byte a byte quando o significado não muda. Uma remoção do
catálogo gera evento local e revisão manual, com exit 2 e preservação da fotografia anterior;
não apaga o ato nem inventa uma revogação. Uma mudança de bytes também não é, por si só,
declaração de alteração jurídica.

## Provas executadas

- RSS real: dez itens parseados, incluindo atualização de norma antiga e ofício novo;
  hash da fixture conferido contra seu manifesto.
- Fonte XML inválida, entidade declarada, link não HTTP e página HTML no lugar de RSS são
  rejeitados; timezone ausente/desconhecido não é convertido para UTC por suposição.
- Reconciliação encontra uma URL nova mesmo sem sinal no RSS.
- Repetição sem mudanças preserva catálogo, Markdown, cobertura e datas.
- Consolidado alterado na mesma URL atualiza o hash e aquela versão; original fica intacto.
- Remoção com contagem atualizada não apaga dados anteriores; o evento fica no log local.
- Bloqueio 429 ou soft-404 de feed interrompe sem promover execução parcial.
- Três semanas consecutivas cobriram todas as três fatias de um catálogo sintético de 120 URLs.

## UNVERIFIED

- Execução incremental ao vivo e o estado atual do feed de audiências nesta etapa.
- Runner hospedado, janela real de sete dias e frequência de alterações que excedam a retenção
  do RSS. A reconciliação de catálogo não garante observar imediatamente uma substituição
  silenciosa de corpo fora dos sinais e da fatia de hashes daquela semana.
- Novos formatos de feed ou estruturas não cobertas pelas fixtures.
