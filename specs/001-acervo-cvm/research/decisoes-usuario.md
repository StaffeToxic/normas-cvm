# Decisões do usuário — acervo CVM

Registro de decisões tomadas em conversa (2026-10-21).

- **D-U1 — Repo separado e aberto.** O coletor de normas CVM vive em repositório próprio e independente de aplicações consumidoras. Estas só consomem o que ele publica.
- **D-U2 — Estrutura e formato da referência.** Árvore de pastas, convenção de nomes e formato do `.md` (cabeçalho de metadados, hierarquia de títulos/artigos/incisos) seguem a referência pesquisada. Divergências necessárias por particularidade da CVM devem ser registradas explicitamente em `research.md`. Para reuso de código de terceiro sob MIT, ver `THIRD_PARTY_NOTICES.md`.
- **D-U3 — Qualidade do `.md` é o requisito principal.** A conversão PDF → `.md` deve reproduzir o método confirmado no código de referência: Poppler `pdftotext -layout` seguido de conversor de parágrafos. Formatação final limpa e consistente; OCR condicionado à falta de camada textual. Benchmark e limites em `pdf-para-md.md`.
- **Pendente:** o repo aberto terá só dados ou também ferramenta de busca (API/MCP)? Sem resposta ainda; assumir só dados + coletor até decisão.
- **D-U5 — Atribuição somente onde exigida pela licença (2026-10-21).** A referência nominal ao projeto de terceiro fica em `THIRD_PARTY_NOTICES.md` (aviso MIT, já na `main`) e nos cabeçalhos de copyright de código copiado ou derivado. README, descrição, specs e docs públicos usam referências neutras. Os três relatórios privados de estudo de referência, projetos similares e integração foram devolvidos ao repositório privado de origem, fora deste Git. Evidências locais de benchmark não são versionadas. A branch pública é reconstruída a partir de `origin/main`, sem esses relatórios e sem evidências temporárias em seu histórico.
- **D-U6 — Escopo ampliado.** Além das 5 famílias (resoluções, instruções, deliberações, pareceres de orientação, ofícios circulares), entram: notas explicativas, decisões conjuntas e portarias de caráter normativo. Material de interpretação (notas, FAQ, ofícios) recebe `tipo` próprio para não ser citado como regra.
- **D-U7 — Audiências e consultas públicas entram como minuta.** `tipo: minuta`, com vínculo para a norma resultante quando houver; nunca tratadas como norma vigente.
- **D-U8 — Fora deste repo:** decisões do Colegiado, processos sancionadores (jurisprudência) e leis/decretos federais.
