# Research — normas-cvm (Fase 0 consolidada)

Data: 2026-10-21. Fontes públicas: `research/fontes-cvm.md`, `research/reconferencia.md`, `research/pdf-para-md.md` e `research/decisoes-usuario.md`. Pesquisas de referência e integração permanecem em arquivo privado, fora deste repositório.

## D-1 Repositório
- **Decision:** repo aberto e independente `StaffeToxic/normas-cvm`, clonado em `Documents\normas-cvm`. Sistemas consumidores utilizam releases publicadas.
- **Rationale:** pedido do usuário; o produtor não conhece usuários, carteiras nem credenciais dos consumidores.
- **Alternatives:** pasta dentro de uma aplicação privada (descartada: misturaria históricos e responsabilidades).

## D-2 Base reaproveitada e atribuição
- **Decision:** importar 319 normas CVM de uma base de referência pesquisada como semente do tipo "publicação original (DOU)", com atribuição. Reaproveitar, quando útil, código de terceiro sob MIT (`html2md.py`, padrões de cache/hash/escrita atômica); ver `THIRD_PARTY_NOTICES.md` e preservar os cabeçalhos de copyright nos arquivos copiados ou derivados.
- **Rationale:** pedido do usuário ("use o que já tem e vá atrás do que falta"); licença MIT para código; texto de ato oficial excluído de proteção pela Lei 9.610/1998, art. 8º, **IV**. Não reproduzir referência incorreta ao inciso I.
- **Alternatives:** recoletar tudo do zero; contribuir apenas na base de referência (não cobre consolidados e instruções legadas necessários).

## D-3 Estrutura e formato
- **Decision:** árvore `reguladores/cvm/<tipo>/<ano>/<slug>.md`; um `.md` por documento; front matter YAML com `titulo`, `orgao`, `tipo`, `numero`, `data`, `revogada`, `versao_texto`, `publicacao`, `data_publicacao`, `fonte`, `baixado_em` + `# Título` + corpo com `**Art. Nº**`.
- **Divergências necessárias (registradas):**
  - `revogada` aceita `null` = desconhecido; nunca `false` sem evidência.
  - `versao_texto` distingue `"publicação original"` e `"consolidada"`; original e consolidado são arquivos distintos (mesma norma, sufixos diferentes).
  - Campos extras: `sha256_fonte`, `fonte_cvm` (página da norma), `alterada_por`/`revogada_por` (lista de URLs com contexto), `anexos` (rótulo, URL, sha256), `unidade` (para ofícios SEP/SIN/...).
  - Commits com data real da coleta (histórico de observação), não reconstruídos.
- **Rationale:** usuário pediu o mesmo formato da referência; divergências explicitam incerteza, versões, relações e proveniência.

## D-4 Escopo inicial (fonte: catálogo CVM)
- **Decision:** coletar do portal `conteudo.cvm.gov.br/legislacao/` as famílias: resoluções (~249), instruções (~627), deliberações (~907), pareceres de orientação (~41), ofícios circulares (~600). Para cada norma: página de metadados, íntegra (HTML se existir, senão PDF), consolidado, anexos, relações altera/revoga.
- Inventário via GET paginado `index.html?buscado=true&contCategoriasCheck=1&vimDaCategoria=/legislacao/<familia>/&searchPage=N`; incremental via RSS `feed/legislacao.xml` + reconciliação periódica do catálogo + rechecagem de hash (consolidado muda na mesma URL).
- Respeitar `robots.txt` (exclusões específicas de deliberações); não usar `dados.cvm.gov.br/api/` (Disallow). Fila conservadora com User-Agent identificado e recuo em erro.
- **Contagens:** reconferidas por nova requisição na rodada 2, sem divergências; ver `research/reconferencia.md`. Cobertura integral e deduplicação continuam **UNVERIFIED**.

## D-5 Conversão para Markdown (decidida após benchmark, `research/pdf-para-md.md`)
- **Decision:** ordem de preferência por norma: (1) **íntegra HTML oficial** → conversor estrutural; (2) **PDF textual** → Poppler `pdftotext -layout` + normalizador próprio; (3) **PDF escaneado** → Tesseract `por`, só quando a página não tiver camada de texto. **Docling não é o caminho padrão.**
- **Rationale:** na Resolução 249, HTML e Poppler deram o mesmo corpo (similaridade de tokens 0,9988; só a epígrafe difere) com 26 artigos, 15 parágrafos e 99 incisos em início de linha; Docling deu 3/3/0, juntou incisos em blocos de até 2.558 caracteres, repetiu o cabeçalho 14 vezes e levou 79,5 s contra 0,08 s. No Parecer 40, Docling repetiu o endereço da CVM 22 vezes. Nenhum dos 3 PDFs precisou de OCR.
- **Normalizador (requisito principal, D-U3):** regras 1–8 de `research/pdf-para-md.md` §7 — cabeçalho/rodapé por zona da página, Art./§/Parágrafo único em negrito, incisos e alíneas em parágrafos próprios, `ANEXO X` como heading, hifenização que preserva URLs e hífens lexicais, notas ligadas à chamada, portões editoriais de comparação com a fonte.
- **Tabelas — ainda aberto:** Poppler + parágrafos achata tabelas (Resolução 175, suplementos). Proibido publicar tabela achatada como fiel. Candidato: usar Docling **só para regiões de tabela**, emitindo `<table>` HTML no `.md`. Decidir com o resultado do Docling na 175.
- **Alternatives:** Docling para tudo (rejeitado: regrediu ordem, blocos e cabeçalhos); só Poppler sem tratamento de tabela (rejeitado: perde estrutura dos anexos).

## D-6 Integração com sistemas consumidores (fora do escopo deste repo)
- Integrações posteriores usam importador versionado, busca textual, citação tipada e evento regulatório próprio. Contratos de aplicações privadas permanecem fora deste repositório; o produtor publica dados e metadados verificáveis sem dependência desses consumidores.

## Aberto
- Repo terá só dados+coletor ou também busca (API/MCP)? Assumido: só dados+coletor.
- Licença MIT para código; tratamento separado para textos oficiais (art. 8º, IV) e anexos de terceiros **UNVERIFIED**. Ver os avisos de publicação na raiz.
- Linguagem do coletor: Python (permite reuso de código de terceiro sob MIT) — a confirmar no plano.
