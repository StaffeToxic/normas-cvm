# normas-cvm

**As normas da Comissão de Valores Mobiliários (CVM) em Markdown versionado.**

Resoluções, instruções, deliberações, pareceres de orientação e ofícios circulares da CVM, um arquivo `.md` por documento, com metadados em YAML, texto original e texto consolidado separados, e histórico de alterações rastreável pelo Git.

> **Status: em construção.** Este repositório está na fase de pesquisa e desenho do coletor. Ainda não há normas publicadas aqui. Acompanhe pelos commits e pelas issues.

---

## Por que este repositório existe

O [`ctresb/leis`](https://github.com/ctresb/leis) reúne a legislação brasileira em Markdown e já inclui uma parte das normas da CVM, coletadas do Diário Oficial da União. O DOU traz o ato **como foi publicado**. Para saber **qual regra vale hoje**, falta o que só o portal da CVM oferece:

| O que falta | Onde está |
|---|---|
| Texto **consolidado**, com as alterações posteriores incorporadas | páginas de cada norma no portal da CVM |
| **Instruções CVM** anteriores a 2021, muitas ainda citadas | `conteudo.cvm.gov.br/legislacao/instrucoes/` |
| **Pareceres de Orientação** e **Ofícios Circulares** | catálogo de legislação da CVM |
| Relações **"altera" / "revoga"** entre normas | bloco de alterações de cada página |
| **Anexos** normativos e suplementos | links de download de cada norma |

Este repositório usa o mesmo formato do `ctresb/leis`, aproveita o que ele já coletou e completa essas lacunas a partir da fonte oficial da CVM.

## Cobertura planejada

Contagens do catálogo oficial da CVM consultado em 21/10/2026:

| Família | Registros no catálogo |
|---|---:|
| Resoluções | 249 |
| Instruções | 627 |
| Deliberações | 907 |
| Pareceres de Orientação | 41 |
| Ofícios Circulares | 600 |
| **Total** | **2.424** |

São contadores da busca oficial, não um censo deduplicado de normas vigentes. A cobertura efetivamente publicada será informada em um relatório próprio, a cada coleta.

## Formato

Estrutura de pastas, compatível com `ctresb/leis`:

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

Diferenças deliberadas em relação ao `ctresb/leis`:

- **`revogada: null`** quando a situação não foi comprovada. O campo só é `true` ou `false` com evidência na fonte oficial.
- **Original e consolidado são arquivos distintos**, identificados por `versao_texto`.
- Campos adicionais: `sha256_fonte`, `alterada_por`, `revogada_por`, `anexos` e `unidade` (para ofícios de cada superintendência).
- **Commits com a data real da coleta.** O histórico do Git registra quando cada texto foi observado; as datas da norma ficam no cabeçalho.

O exemplo acima ilustra o formato. O esquema definitivo será documentado antes da primeira publicação de normas.

## Fontes

- Catálogo de legislação da CVM: <https://conteudo.cvm.gov.br/legislacao/index.html>
- Página de normas no gov.br: <https://www.gov.br/cvm/pt-br/assuntos/normas>
- RSS de legislação da CVM: <https://conteudo.cvm.gov.br/feed/legislacao.xml>
- Base inicial: [`ctresb/leis`](https://github.com/ctresb/leis), `reguladores/cvm/`

A coleta respeita o `robots.txt` de cada host, faz uma requisição por vez, identifica-se no User-Agent e não acessa caminhos excluídos.

## Limites

- **Este acervo não substitui o Diário Oficial da União nem o portal da CVM.** Conversões de PDF podem conter erros. Na dúvida, prevalece a fonte oficial indicada em `fonte`.
- Um texto consolidado reflete o que a CVM publicava na data de `baixado_em`; ele não prova qual redação vigorava em data passada.
- Vigência por dispositivo não é informada.

## Licença

- **Código** (coletor e conversores): [MIT](LICENSE).
- **Textos normativos**: atos oficiais não são protegidos por direito autoral (Lei nº 9.610/1998, art. 8º, IV).
- Anexos e materiais de terceiros eventualmente reproduzidos mantêm a titularidade original.

Detalhes em [LICENSE](LICENSE).

## Agradecimentos

Ao [`ctresb/leis`](https://github.com/ctresb/leis), cujo formato e método serviram de referência para este projeto.

## Contribuindo

Encontrou uma norma faltando ou um erro de conversão? Abra uma [issue](https://github.com/StaffeToxic/normas-cvm/issues/new/choose).
