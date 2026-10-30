# normas-cvm

**As normas da Comissão de Valores Mobiliários (CVM) em Markdown versionado.**

Resoluções, instruções, deliberações, pareceres de orientação e ofícios circulares da CVM, um arquivo `.md` por documento, com metadados em YAML, texto original e texto consolidado separados, e histórico de alterações rastreável pelo Git.

> **Status: MVP em andamento.** Coletor auditável, suíte de verificação automatizada com 231 testes e primeira norma publicada ([Resolução CVM nº 249/2026](reguladores/cvm/resolucoes/2026/cvm-resolucao-249-2026.md)). O catálogo oficial de 249 resoluções está estruturado em [`catalogo/resolucoes.json`](catalogo/resolucoes.json) e o relatório de cobertura em [`cobertura/COBERTURA.md`](cobertura/COBERTURA.md).

---

## Por que este repositório existe

O Diário Oficial da União traz cada ato **como foi publicado**. Para saber **qual regra vale hoje**, é preciso o que só o portal da CVM oferece:

| Informação | Onde está |
|---|---|
| Texto **consolidado**, com as alterações posteriores incorporadas | páginas de cada norma no portal da CVM |
| **Instruções CVM** anteriores a 2021, muitas ainda citadas | `conteudo.cvm.gov.br/legislacao/instrucoes/` |
| **Pareceres de Orientação** e **Ofícios Circulares** | catálogo de legislação da CVM |
| Relações **"altera" / "revoga"** entre normas | bloco de alterações de cada página |
| **Anexos** normativos e suplementos | links de download de cada norma |

Este repositório reúne essas informações a partir da fonte oficial da CVM, em um formato legível por pessoas e por máquinas.

## Cobertura: planejado vs. atual

Contagens do catálogo oficial da CVM consultado em 21/10/2026 comparadas ao acervo atual coletado:

| Família | Planejado (Catálogo CVM) | Catalogados | Publicados | Pendentes | Status |
|---|---:|---:|---:|---:|---|
| **Resoluções** | 249 | 249 | 1 | 248 | MVP implementado (1 publicada, 248 catalogadas/pendentes) |
| **Instruções** | 627 | 0 | 0 | 0 | Planejado (próxima fase) |
| **Deliberações** | 907 | 0 | 0 | 0 | Planejado (próxima fase) |
| **Pareceres de Orientação** | 41 | 0 | 0 | 0 | Planejado (próxima fase) |
| **Ofícios Circulares** | 600 | 0 | 0 | 0 | Planejado (próxima fase) |
| **Total** | **2.424** | **249** | **1** | **248** | **Fase 1 (Resoluções MVP) em andamento** |

São contadores da busca oficial, não um censo deduplicado de normas vigentes.

O detalhamento completo por norma, motivos de pendência (ex.: tabelas complexas, PDF/OCR, anexos) e integridade de fontes é atualizado a cada coleta em [cobertura/COBERTURA.md](cobertura/COBERTURA.md) e [cobertura/cobertura.json](cobertura/cobertura.json).

## Formato

Estrutura de pastas:

```text
reguladores/cvm/
├── resolucoes/<ano>/
├── instrucoes/<ano>/
├── deliberacoes/<ano>/
├── pareceres-orientacao/<ano>/
└── oficios-circulares/<ano>/
```

Cada documento é um `.md` com cabeçalho YAML, título e corpo:

```markdown
---
titulo: "RESOLUÇÃO CVM Nº 249, DE 13 DE OUTUBRO DE 2026"
orgao: "Comissão de Valores Mobiliários"
tipo: "Resolução"
numero: "249"
data: 2026-10-13
revogada: null
versao_texto: "publicação original"
fonte: "https://conteudo.cvm.gov.br/legislacao/resolucoes/resol249.html"
baixado_em: 2026-10-21
sha256_fonte: "24eb8b5a0808c547b8ca78c80b6c79d95509a8dbef63334715e08a642d3f71ef"
---
# RESOLUÇÃO CVM Nº 249, DE 13 DE OUTUBRO DE 2026

**Art. 1º** ...
```

Princípios do formato:

- **`revogada: null`** quando a situação não foi comprovada. O campo só é `true` ou `false` com evidência na fonte oficial.
- **Original e consolidado são arquivos distintos**, identificados por `versao_texto`.
- Campos adicionais: `sha256_fonte`, `alterada_por`, `revogada_por`, `anexos` e `unidade` (para ofícios de cada superintendência).
- **Commits com a data real da coleta.** O histórico do Git registra quando cada texto foi observado; as datas da norma ficam no cabeçalho.

O exemplo acima ilustra o formato. O esquema definitivo será documentado antes da primeira publicação de normas.

## Fontes

- Catálogo de legislação da CVM: <https://conteudo.cvm.gov.br/legislacao/index.html>
- Página de normas no gov.br: <https://www.gov.br/cvm/pt-br/assuntos/normas>
- RSS de legislação da CVM: <https://conteudo.cvm.gov.br/feed/legislacao.xml>
- Diário Oficial da União, para a publicação original: <https://www.in.gov.br/>

A coleta respeita o `robots.txt` de cada host, faz uma requisição por vez, identifica-se no User-Agent e não acessa caminhos excluídos.

## Limites

- **Este acervo não substitui o Diário Oficial da União nem o portal da CVM.** Conversões de PDF podem conter erros. Na dúvida, prevalece a fonte oficial indicada em `fonte`.
- Um texto consolidado reflete o que a CVM publicava na data de `baixado_em`; ele não prova qual redação vigorava em data passada.
- Vigência por dispositivo não é informada.

## Licença

- **Código** (coletor e conversores): [MIT](LICENSE).
- **Textos normativos**: atos oficiais não são protegidos por direito autoral (Lei nº 9.610/1998, art. 8º, IV).
- Anexos e materiais de terceiros eventualmente reproduzidos mantêm a titularidade original.

O arquivo [LICENSE](LICENSE) cobre apenas o código. Avisos de código de terceiros estão em [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Contribuindo

Encontrou uma norma faltando ou um erro de conversão? Abra uma [issue](https://github.com/StaffeToxic/normas-cvm/issues/new/choose).
