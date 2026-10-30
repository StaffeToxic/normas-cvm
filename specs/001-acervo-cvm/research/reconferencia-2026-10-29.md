# Reconferência das fontes em 29/10/2026

Coleta realizada em **29/10/2026, horário de Brasília**, entre
`2026-10-30T00:24:25Z` e `2026-10-30T00:32:45Z`. Todas as contagens abaixo vieram de respostas
HTTP novas, sem reaproveitar páginas antigas como se fossem atuais. Capturas, listas completas
de URLs, hashes por resposta e logs permanecem em evidência local não versionada.

## 1. Enumeração das cinco famílias

Foi usado o GET público do índice, com `buscado=true`, `contCategoriasCheck=1`,
`vimDaCategoria=/legislacao/<familia>/`, `itensPagina=50` e `searchPage=N`.
Cada página apresentou o mesmo contador da sua família; links em `h3 > a` foram enumerados,
sem repetição entre páginas. A enumeração terminou quando atingiu exatamente o contador,
sem inferir a quantidade pelo maior número de ato.

| Família / listagem | Contador novo | URLs distintas enumeradas | Páginas novas | Comparação com a enumeração local anterior |
|---|---:|---:|---:|---|
| [Resoluções](https://conteudo.cvm.gov.br/legislacao/index.html?buscado=true&contCategoriasCheck=1&vimDaCategoria=/legislacao/resolucoes/&itensPagina=50) | 249 | 249 | 5 | Mesmo conjunto de URLs |
| [Instruções](https://conteudo.cvm.gov.br/legislacao/index.html?buscado=true&contCategoriasCheck=1&vimDaCategoria=/legislacao/instrucoes/&itensPagina=50) | 627 | 627 | 13 | Mesmo conjunto de URLs |
| [Deliberações](https://conteudo.cvm.gov.br/legislacao/index.html?buscado=true&contCategoriasCheck=1&vimDaCategoria=/legislacao/deliberacoes/&itensPagina=50) | 907 | 907 | 19 | Mesmo conjunto de URLs |
| [Pareceres de Orientação](https://conteudo.cvm.gov.br/legislacao/index.html?buscado=true&contCategoriasCheck=1&vimDaCategoria=/legislacao/pareceres-orientacao/&itensPagina=50) | 41 | 41 | 1 | Mesmo conjunto de URLs |
| [Ofícios circulares](https://conteudo.cvm.gov.br/legislacao/index.html?buscado=true&contCategoriasCheck=1&vimDaCategoria=/legislacao/oficios-circulares/&itensPagina=50) | 600 | 600 | 12 | Uma URL a mais em relação às 599 da enumeração anterior |
| **Total destas cinco famílias** | **2.424** | **2.424** | **50** | Não é o total do escopo ampliado |

A URL adicional é o [Ofício Circular 4/2026/CVM/SMI](https://conteudo.cvm.gov.br/legislacao/oficios-circulares/smi/oc-smi-0426.html).
A página respondeu 200 e confirmou esse título. O RSS informa data de 27/10/2026 para o item.
Nenhuma URL saiu dos cinco conjuntos comparados. A diferença histórica entre contador 600 e
enumeração 599 nas pesquisas de 21–22/10 continua sem explicação completa; a nova enumeração
não autoriza reescrever retroativamente aqueles resultados.

## 2. Robots: redirecionamento oficial e limite do transporte

A requisição nova de [robots.txt](https://conteudo.cvm.gov.br/robots.txt) respondeu **302**,
com a seguinte cadeia publicada pelo próprio servidor:

| Passo | URL requisitada | HTTP | Destino informado |
|---|---|---:|---|
| 1 | `https://conteudo.cvm.gov.br/robots.txt` | 302 | `http://www.cvm.gov.br/export/sites/cvm/robots.txt` |
| 2 | `http://www.cvm.gov.br/export/sites/cvm/robots.txt` | 301 | `https://conteudo.cvm.gov.br/export/sites/cvm/robots.txt` |
| 3 | `https://conteudo.cvm.gov.br/export/sites/cvm/robots.txt` | 200 | Arquivo de regras, 540 bytes |

SHA-256 do arquivo final:
`3e0e60679f99362c75728caf55df1f74aff83e8c7ace309106c2e1bf40d473b5`.
Os bytes coincidem com a política capturada anteriormente. Continuam presentes as exclusões
específicas, inclusive a página da Deliberação 233 e o diretório `noindex` de anexos.

O transporte em `1c96fa2` interrompeu corretamente sua primeira tentativa pela proteção local
`cross-origin-robots-redirect`, sem acessar catálogos. Porém, essa proteção também impede
inicializar a coleta pelo endereço oficial atual de robots. Isso é uma **limitação de
compatibilidade confirmada**, não evidência de proibição dos catálogos pela CVM.

A [RFC 9309, seção 2.3.1.2](https://www.rfc-editor.org/rfc/rfc9309.html#section-2.3.1.2)
orienta acompanhar redirecionamentos de robots entre autoridades e aplicar o arquivo obtido à
autoridade inicial; a seção 2.4 trata de cache. Nesta pesquisa, uma inspeção restrita aos
endereços de robots explicitamente publicados resolveu a cadeia. A política recém-obtida foi
carregada em cache para a autoridade inicial, com idade inferior a 24 horas e hash conferido,
antes da enumeração. Não houve alteração do código de produção ou de suas proteções.

Adequação futura de T002 deve distinguir obtenção de robots de acesso a conteúdo e preservar
o bloqueio da API em **todo** envio, limite de saltos, fila por hostname e interrupção em
401/403/429/5xx. Seguir o `Location` publicado não deve virar reescrita arbitrária de host,
esquema ou caminho, nem tentativa alternativa após uma resposta de bloqueio.

## 3. Exemplos e hashes reconferidos

| Artefato | Resultado novo |
|---|---|
| [Instrução 400](https://conteudo.cvm.gov.br/legislacao/instrucoes/inst400.html) | 200; `h2` mantém `Instrução CVM 400 (Revogada)` |
| [PDF da Resolução 249](https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/resolucoes/anexos/200/resol249.pdf) | 200; 342.863 bytes; SHA-256 `24eb8b5a0808c547b8ca78c80b6c79d95509a8dbef63334715e08a642d3f71ef`, idêntico ao anterior |
| [HTML da Resolução 249](https://conteudo.cvm.gov.br/legislacao/resolucoes/anexos/200/resol249.htm) | 200; 39.927 bytes; SHA-256 `409fccb29e8c06dccbbafef304d4b06ceca5f7889d827c8db59efcf06964194e`, diferente da captura anterior |
| [Página da Resolução 175](https://conteudo.cvm.gov.br/legislacao/resolucoes/resol175.html) | 200; links de alteradoras ainda chegam à 240; não foi encontrado link para a 247 nesse bloco |
| [Hub de resoluções](https://conteudo.cvm.gov.br/legislacao/resolucoes.html) | 200; mantém referência à 247; a divergência entre páginas não está resolvida |

No HTML da 249, a diferença de bytes foi isolada: acrescentou-se uma linha de script de
analytics. Remover apenas essa linha na comparação local reconstruiu **exatamente** os bytes
da captura anterior, sem normalizar quebras de linha. O hash anterior era
`4ecd56d72acffb325d882fbca55ae720f9e1b22ac059385006eb35ecaa20d78b`, com 39.566 bytes.
O script externo não foi baixado nem executado.

Isso confirma uma mudança do artefato HTTP, sem demonstrar alteração normativa. Não substituir
o hash dos bytes recebidos por hash de HTML limpo. Reaproveitar corpo convertido pode ser
possível após conferência, mas a proveniência de uma nova observação deve continuar usando os
bytes reais. Igualdade do texto não basta para afirmar igualdade da fonte ou dos metadados.

## 4. RSS e atualização de páginas antigas

O [RSS de legislação](https://conteudo.cvm.gov.br/feed/legislacao.xml) respondeu 200 com
**10 itens**. O primeiro é a Deliberação 906, datada no título de 11/03/2026, enquanto seu
`pubDate` é `27/10/2026`. O item seguinte é o novo ofício da SMI. Isso reconfirma que a data do
feed não é necessariamente a data do ato. Os links dos itens ainda usam o host legado
`http://www.cvm.gov.br`; nenhuma íntegra foi obtida simplesmente tratando esse endereço como
canônico. A [página de feeds](https://conteudo.cvm.gov.br/feed.html) também respondeu 200.

## 5. Auditoria da coleta

Nos scripts HTTP desta rodada foram registradas **63 requisições**: 60 a `conteudo.cvm.gov.br`,
1 ao host legado e 2 a `www.gov.br` para robots e reconferência do aviso do hub.
As 50 páginas de catálogo estão incluídas nesse total. Consultas bibliográficas à RFC, ao
texto da licença e à legislação não fazem parte desses contadores.

- Intervalo mínimo registrado entre requisições ao mesmo hostname: **5,000 s** onde houve mais
  de uma requisição; para o host legado houve apenas uma observação, sem intervalo calculável.
- User-Agent identificado com URL deste repositório; nenhuma requisição a `dados.cvm.gov.br/api`.
- Nenhum caminho excluído pela política obtida foi requisitado.
- O primeiro bloqueio foi uma decisão local do cliente; a cadeia inspecionada depois retornou
  somente 302/301/200. Não houve tentativa de contornar 401/403/429/5xx.

## Decision / Rationale / Alternatives considered

**Decision:** manter os novos números como retrato datado das cinco famílias, atualizar o
risco de inicialização de robots e separar alteração de bytes de alteração jurídica. Manter
T004 pendente conforme [revisão do HTML](revisao-html.md) e direitos por artefato conforme
[reconferência de licenças](licencas-reconferencia.md).

**Rationale:** houve enumeração integral desses catálogos e hashes novos, com política atual
conferida; o resultado não é uma estimativa nem prova de fidelidade de conversão.

**Alternatives considered:** confiar em contadores históricos sem percorrer páginas; ignorar
robots por causa do redirecionamento; interpretar qualquer hash novo como norma alterada; ou
extrapolar cinco famílias para todo o escopo. Todas foram rejeitadas.

## UNVERIFIED

- Censo atualizado das demais categorias, deduplicação jurídica por ato/versão e vigência por dispositivo.
- Equivalência integral entre todos os formatos; a conferência de bytes da 249 não certifica conversão.
- Conteúdo jurídico do novo ofício, cuja página foi conferida, mas cujos anexos não foram convertidos.
- Motivo completo da diferença histórica de contagem de ofícios e completude das relações da 175.
- Funcionamento do coletor de produção sem o cache de robots preparado para esta pesquisa.
- Runner real, agendamento e atendimento ao prazo de atualização de sete dias.
