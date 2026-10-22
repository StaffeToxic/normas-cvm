# Reconferência independente — rodada 2

Consulta em **21/10/2026, 23:17, America/Sao_Paulo** (22/10/2026, 02:17 UTC). Este relatório usa respostas novas, obtidas nesta rodada, não os corpos HTTP da Fase 0. “Independente” refere-se à nova medição; não houve parecer externo.

## Setup e preservação dos arquivos

- Clone real de `https://github.com/StaffeToxic/normas-cvm.git` em clone local, a partir de `9e0e045` (`Initial commit`), seguido de `git switch -c 001-acervo-cvm`.
- Executado o comando solicitado `specify init --here --force --integration claude`, com Specify **0.12.18**. A primeira execução não concluiu a seleção de script no ambiente sem stdin; foi interrompida e repetida com **`--script ps`**, concluindo com exit 0 e “Project ready”.
- A constituição gerada por Spec Kit é **template não ratificado**, com placeholders. D-1 a D-6 foram preservadas como decisões da pesquisa; não se declarou uma nova constituição aprovada.
- A pasta inteira `specs/051-normas-cvm` foi **movida**, não duplicada, para `specs/001-acervo-cvm`. Os seis arquivos tiveram SHA-256 calculado antes e depois; os mapas coincidiram exatamente. O manifesto anterior está em evidência local não versionada (`migration-before.json`).
- O repositório privado de origem foi preservado fora da migração autorizada. Na rodada 3, três relatórios privados foram devolvidos à origem com hashes preservados; os demais documentos foram preparados para publicação.

## Método de rede

Instrumento reproduzível: evidência local não versionada (`verify_sources.py`). A fila usa **uma requisição por vez**, intervalo mínimo de **3 segundos entre inícios**, timeout de 60 s e o User-Agent identificado:

`NormasCVMResearch/0.2 (+https://github.com/StaffeToxic/normas-cvm; research benchmark)`.

Primeiro foi requisitado [robots.txt](https://conteudo.cvm.gov.br/robots.txt), HTTP 200; cada alvo foi comparado com suas regras usando `urllib.robotparser`. As exclusões de `/apoio`, `/jornalistas`, `/teste`, da Deliberação 233, do diretório `noindex` e dos dois PDFs de decisões não foram acessadas. **Nenhuma requisição a `dados.cvm.gov.br/api` foi feita nesta rodada.** Não houve bloqueio a contornar nem retentativa nesta série.

Evidências completas, incluindo URL solicitada/final, status, headers, instante UTC, tamanho, SHA-256 e duração de cada resposta: evidência local não versionada (`http-evidence.json`). Corpos originais: evidência local não versionada (`input/`). Resumo mecanicamente extraído: evidência local não versionada (`reconfirmation.json`).

## Cinco famílias de D-4

Padrão GET efetivamente usado:

`https://conteudo.cvm.gov.br/legislacao/index.html?buscado=true&contCategoriasCheck=1&vimDaCategoria=/legislacao/<familia>/&searchPage=1`

O número foi extraído do texto `N resultados encontrados` da resposta HTML. Não foi deduzido do número máximo de uma norma.

| Família | Esperado em D-4 | HTTP | Nova contagem | Diferença |
|---|---:|---:|---:|---:|
| [Resoluções](https://conteudo.cvm.gov.br/legislacao/index.html?buscado=true&contCategoriasCheck=1&vimDaCategoria=/legislacao/resolucoes/&searchPage=1) | 249 | 200 | **249** | **0** |
| [Instruções](https://conteudo.cvm.gov.br/legislacao/index.html?buscado=true&contCategoriasCheck=1&vimDaCategoria=/legislacao/instrucoes/&searchPage=1) | 627 | 200 | **627** | **0** |
| [Deliberações](https://conteudo.cvm.gov.br/legislacao/index.html?buscado=true&contCategoriasCheck=1&vimDaCategoria=/legislacao/deliberacoes/&searchPage=1) | 907 | 200 | **907** | **0** |
| [Pareceres de orientação](https://conteudo.cvm.gov.br/legislacao/index.html?buscado=true&contCategoriasCheck=1&vimDaCategoria=/legislacao/pareceres-orientacao/&searchPage=1) | 41 | 200 | **41** | **0** |
| [Ofícios circulares](https://conteudo.cvm.gov.br/legislacao/index.html?buscado=true&contCategoriasCheck=1&vimDaCategoria=/legislacao/oficios-circulares/&searchPage=1) | 600 | 200 | **600** | **0** |
| **Soma dos contadores** | **2.424** | — | **2.424** | **0** |

**Divergências de contagem: nenhuma nesta consulta.** Isso confirma os contadores do catálogo naquele instante. Não é censo deduplicado de identidades, normas vigentes ou recursos anexos. Enumeração completa de todas as páginas, integridade da busca oficial e equivalência entre contagem e documentos disponíveis continuam **UNVERIFIED**.

## Instrução CVM 400

URL nova: <https://conteudo.cvm.gov.br/legislacao/instrucoes/inst400.html>, **HTTP 200**.

Título extraído de `h2`, após decodificação HTML: **`Instrução CVM 400 (Revogada)`**. Comparação literal com a expectativa: **igual**. O corpo capturado está em evidência local não versionada (`inst400.html`).

**Divergência do título: nenhuma.** Isso confirma a marca editorial do portal; não é uma validação jurídica de todos os dispositivos ou de sua aplicação temporal. Não se classificaram as outras instruções como revogadas por analogia.

## Resolução CVM 249 — integridade dos bytes PDF

URL requisitada novamente: <https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/resolucoes/anexos/200/resol249.pdf>.

- HTTP **200**, `Content-Type: application/pdf`, assinatura dos bytes `%PDF-1.7`.
- Tamanho recebido: **342.863 bytes**.
- SHA-256 esperado da Fase 0: `24eb8b5a0808c547b8ca78c80b6c79d95509a8dbef63334715e08a642d3f71ef`.
- SHA-256 recalculado: **`24eb8b5a0808c547b8ca78c80b6c79d95509a8dbef63334715e08a642d3f71ef`**.
- Comparação dos hashes: **igual**, diferença de bytes detectável pelo SHA-256: nenhuma.

O arquivo recém-obtido, evidência local não versionada (`resol249.pdf`), é a entrada PDF do benchmark. A igualdade de hash não demonstra qualidade de conversão, vigência nem licença de outros artefatos. Esses temas são separados em [pdf-para-md.md](pdf-para-md.md).

## Limites e divergências explicitamente preservadas

Os sete alvos de reconferência — cinco contadores, título e hash — coincidiram com as expectativas. A diferença operacional do setup foi o uso de `--script ps` para concluir a inicialização. Este registro descreve a rodada 2. A rodada 3 neutralizou referências privadas, preservando D-5 byte a byte. O benchmark da etapa seguinte usa os mesmos bytes capturados e registra suas próprias falhas e resultados, sem promover esta reconferência a aprovação do corpus completo.
