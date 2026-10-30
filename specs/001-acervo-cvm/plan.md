# Implementation Plan: Acervo de normas da CVM

**Branch**: `001-acervo-cvm` | **Date**: 2026-10-22 | **Spec**: [spec.md](spec.md)

## Summary

Construir um coletor local e agendável que enumera o catálogo oficial, publica Markdown fiel e registra cada item não publicado com motivo. MVP: resoluções com íntegra HTML; todos os registros da família entram na cobertura, inclusive os que dependem de PDF ou revisão. As demais histórias ampliam conversores e categorias, sem reduzir gates para atingir contagens.

O catálogo oficial e a classificação de escopo do mantenedor prevalecem. Os 319 arquivos externos são auxiliares, não semente canônica. Os 241 casamentos de identidade e a triagem de 9 textos não certificam publicação. D-5 permanece intacta; decisões posteriores a complementam.

## Technical Context

**Language/Version**: Python 3.12; código e identificadores em inglês, documentação pt-BR.

**Primary Dependencies**: biblioteca padrão em runtime; Poppler para PDF; Tesseract `por` somente nas páginas sem texto. LibreOffice via apt é auxiliar condicional para DOC legado; instalação portátil não aprovada. Docling não é padrão.

**Storage**: arquivos UTF-8/LF; bytes brutos em cache local ignorado; `cobertura/cobertura.json` é índice durável de hashes. Sem banco, serviço HTTP ou busca nesta feature.

**Testing**: `unittest`; fixtures reais versionadas com saída esperada; transporte simulado; execução real controlada e testes em estado commitado. Gates novos incluem sabotagem.

**Target Platform**: Windows para CLI/HTML e Linux Ubuntu 24.04 para Actions/conversores externos. Versões e tempos no runner real UNVERIFIED até execução.

**Project Type**: biblioteca Python com CLI e workflows de verificação/coleta.

**Performance Goals**: uma requisição por host a cada pelo menos 5 s, sem paralelismo; lotes limitados por quantidade e duração medida, abaixo de 6 h/job. Capacidade por lote ainda UNVERIFIED.

**Constraints**: robots por host/redirecionamento, User-Agent identificado, API de dados proibida, recuo/interrupção em bloqueio; nenhuma tabela achatada ou metadado inventado. Publicação posterior aos gates.

**Scale/Scope**: aproximadamente 2.990 registros históricos, ainda sem censo global deduplicado. Primeira entrega enumera todas as resoluções, confrontando a referência de 249 sem fixá-la no programa.

## Constitution Check

| Princípio | Antes e depois do desenho / evidência exigida |
|---|---|
| I — fonte oficial | Proveniência e nulabilidade definidas; hash dos bytes convertidos, evidência de revogação/relações; testes de adulteração |
| II — fidelidade | Nenhuma triagem externa aprova corpo; sequência, dispositivos, anexos e tabelas; falha torna artefato pendente |
| III — coleta educada | Fila única, robots e intervalo mínimo; testes de relógio/redirecionamento/bloqueio e log real |
| IV — verificação executada | Testes em cada história e sabotagem em commits exatos; critérios externos UNVERIFIED até execução |
| V — formato estável | Contratos preservados; schema, aliases, versões e repetição testados; mudanças justificadas e versionadas |
| VI — simplicidade | CLI/arquivos e biblioteca padrão; dependências auxiliares justificadas por medidas reais |

O desenho atende aos princípios; não declara histórias ou testes concluídos. A exigência constitucional de testes em toda história prevalece sobre o template genérico.

## Project Structure

```text
specs/001-acervo-cvm/
  plan.md, research.md, data-model.md, quickstart.md, tasks.md
  contracts/front-matter.md, coverage-report.md, cli.md, workflow.md
src/cvm_archive/
  __init__.py, models.py, cli.py
  fetch/client.py
  sources/catalog.py, document.py, feeds.py
  convert/html.py, pdf.py, word.py, ocr.py
  normalize/text.py
  gates/fidelity.py, metadata.py
  publish/markdown.py, coverage.py
 tests/unit/, tests/contract/, tests/integration/, tests/fixtures/
 reguladores/cvm/<tipo>/<ano>/
 cobertura/cobertura.json, COBERTURA.md
 .github/workflows/test.yml, collect.yml
```

Criar somente módulos necessários ao ticket; não criar conversores vazios. Fixtures são documentos oficiais com redistribuição conferida. Downloads de pesquisa e evidências de execução ficam locais, não versionados.

## Fluxo e interfaces internas do MVP

1. `fetch.client.PoliteClient.fetch(url)` retorna `Artifact(url, bytes, content_type, sha256, fetched_at)`. A URL é a final, após redirecionamentos verificados; a cadeia fica no log. `FetchError` carrega status e motivo; `BlockedError` interrompe a coleta. A fila cobre também requests de robots. Intervalo inferior a 5 s é inválido.
2. `sources.catalog.catalog_url(category, page)` e `parse_catalog(html, base_url, category)` retornam entradas e contador declarado. `enumerate_catalog(client, category)` enumera todas as páginas, deduplica e detecta contagem incoerente. `CatalogEntry(url, title, category, number, date)` não inventa número/data.
3. `sources.document.parse_document_page(html, url, category)` separa metadados, íntegra HTML, PDF próprio, consolidado e alteradoras. Um link HTML só vira íntegra depois de inspecionar seu conteúdo. Nome de arquivo, inclusive `site`, não prova versão jurídica. Epígrafe/página definem identidade.
   Candidatos internos de artefato podem ter `version: None` e motivo de revisão quando houver
   republicação ou indicação contraditória. Isso nunca cria um terceiro enum público. Uma
   contradição de revogação preserva as declarações oficiais para o relatório, sem escolher uma.
4. `convert.html.convert_html(html, source_url)` retorna `Conversion(source_text, markdown, warnings, pending_reason)`. Seleciona corpo normativo, preserva entidades, dispositivos, tabelas e links seguros; rejeita seleção ambígua e estrutura não suportada. Normalização formata sem reescrever conteúdo.
5. `gates.fidelity.check_fidelity(source_text, markdown)` compara sequência e contagens, nunca conjuntos. A referência precede a transformação. Fixtures e conferência real verificam também seleção do corpo; um gate sobre referência já truncada não basta. Metadados têm gate próprio.
6. `publish` prepara arquivos temporários e substitui arquivos completos atomicamente. Falha de enumeração não substitui cobertura anterior por catálogo parcial. Pendência não gera Markdown novo. Documento antes publicado que falhe após mudança da fonte sai da árvore corrente e fica pendente, com histórico Git preservado.

## Identidade, versões e atualizações

- Original e consolidado compartilham identidade do ato, com arquivos/hashes separados. Cobertura conta o ato uma vez e descreve versões pendentes; original publicado não transforma consolidado pendente em completo.
- Cobertura 2.0 (D-13) mantém entradas ainda não visitadas por URL, com `id: null` e sem publicação. Número/data do catálogo continuam candidatos; a identidade só é preenchida após confirmação oficial. A mudança MAJOR de nulabilidade está descrita no contrato e não altera o front matter 1.0.
- `fonte`/`sha256_fonte` são do mesmo artefato. Relações vazias significam nenhuma encontrada na fonte consultada, não inexistência universal. `revogada: null` é válido.
- As três republicações externas conhecidas ficam pendentes por artefato; não criar enum por inferência.
- Sem mudança semântica, preservar bytes de documentos e cobertura, inclusive datas. Logs locais guardam contadores da execução; o relatório público só muda com conteúdo/estado. O contrato permite diferenças de execução, mas não as exige; esta opção mais restrita atende FR-023 e US6.
- Cache local é descartável; hashes da cobertura permitem rechecagem em runner novo. Não reconverter hash inalterado; não confundir cache local com índice durável.
- Corpo externo não é pré-requisito do caminho oficial. Reuso exige direitos compatíveis, bytes verificáveis e gates por documento; campos públicos de origem auxiliar dependem de contrato versionado.

## Tratamento dos conflitos R3

| Conflito | Tratamento / teste obrigatório |
|---|---|
| C1 republicação | 59/2021 em revisão; 100/2022 e 110/2022 parciais pendentes; fixtures negativas, sem rótulo original/consolidado inventado |
| C2 tipo/ID | Deliberação 870/2021 e Pareceres 39/2021 e 40/2022 pela epígrafe; aliases e teste contra pasta/tipo incorretos |
| C3 hash | Recalcular por artefato; 260 hashes históricos não são renomeados sem conferir; 59 ausentes não são preenchidos artificialmente |
| C4 URLs | Separar DOU/PDF/HTML convertido da página CVM; `fonte_cvm` anulável conforme contrato |
| C5 campos | Validar chaves, nulabilidade, relações/anexos; desconhecimento não vira negativa jurídica |
| C6 órgão/unidade | CVM e órgãos conjuntos; unidade só explícita; testar variantes |
| C7 denominador | Catálogo por categoria/escopo; 78 portarias sem equivalente no recorte curado exigem classificação individual |
| C8 triagem | Nenhum dos 10 certificado; gates ordenados por documento com deleção, repetição e permutação sabotadas |
| C9 anexos/tabelas | Descoberta oficial, tabelas reais; conteúdo ausente implica pendência; exclusões CPC explícitas |
| C10 revogação | Não copiar os 59 falsos sem evidência; ausência de afirmação oficial produz `null` |
| C11 identidade | ID estável sem sufixo DOU, aliases, ordenação/repetição; identidade sem número/data definida em contrato antes de publicar |
| C12 direitos | Compilação externa UNVERIFIED; URL/revisão/digest auxiliar sem campos públicos inventados; fonte oficial direta independente |

C1–C12 são requisitos de execução, não conflitos encerrados somente pelo desenho. Não há importação canônica de 319 nem aprovação automática de 238/241.

### Conciliação antes da implementação

FR-022 foi esclarecida para seguir o contrato de cobertura: soft-404 é pendência com motivo, 404/410 é indisponibilidade. A agregação por ato preserva versões aprovadas quando outra versão está pendente, sem dupla contagem. Não houve alteração dos contratos front matter/cobertura nem de D-5. O nome interno do payload é `Artifact.bytes`, conforme modelo final. Timestamp de execução pode diferir segundo o contrato; a implementação não o modifica quando o conteúdo/estado público permanece igual, preservando FR-023/US6.

## Entrega incremental e critérios

1. **Fundação:** pacote/modelos, fixtures, transporte educado, parser de catálogo e gates.
2. **MVP US1:** catálogo integral de resoluções e lote real HTML, schema e tabela/anexo suportado ou pendência; teste real da Resolução 249. Confrontar 249 e registrar deriva. SC-002 exige amostra posterior de 50, não se cumpre com um documento.
3. **US2/US6:** versões/relações/divergências, publicação transacional; RSS/primeira página, reconciliação completa e hashes rotativos; workflow por lotes. Dois crons não garantem SC-006. Ativação depende de workflow na default branch e observação real; nenhum ajuste automático de destino para main.
4. **US3:** PDF, normalizador por zona, tabelas Word condicionais e OCR somente sem texto. Inspecionar página vazia/vetorial/raster; poucos caracteres não disparam OCR. F5 não elimina esta rota.
5. **US4/US5:** classes de orientação e identidade de itens sem número antes de publicação; peças oficiais de consultas, manifestações somente como link.
6. **Fechamento:** SC-001..009 com evidência ou UNVERIFIED; main recebe merge revisado/testado. Autoria humana do mantenedor; dados agendados usam bot D-U12.

## Complexity Tracking

Nenhuma exceção constitucional proposta. Word é auxiliar condicional, não substitui padrão. Mudanças para identidade sem número, proveniência auxiliar ou republicação têm ticket próprio, motivo e migração quando aplicável. Bloqueiam esses artefatos sem bloquear MVP de resoluções identificadas.
