# Validação executada do MVP de resoluções

Executada em **29/10/2026 no horário de Brasília**, entre **30/10/2026 01:42 e 01:45 UTC**.
Código em `e779a29`; primeira coleta registrada em `c21cdb5`. Não inclui as histórias posteriores.

## Comandos e resultados reais

A coleta foi executada em árvore limpa do código commitado, usando diretório local de cache
não versionado informado em `--cache-dir`. Forma de reprodução com o caminho de cache padrão:

```bash
python -m cvm_archive.cli collect --category resolucoes --output . \
  --document https://conteudo.cvm.gov.br/legislacao/resolucoes/resol249.html \
  --cache-dir .scratch/cache
```

| Execução | Resultado | Requisições | Falhas HTTP |
|---|---|---:|---:|
| Inicial, sem catálogo local | `changed: true`, 1 publicado, 248 pendentes, 1 processado | 10 | 0 |
| Repetição após commitar os dados | `changed: false`, 1 publicado, 248 pendentes, 0 processados | 5 | 0 |

A primeira execução enumerou cinco páginas de catálogo e confirmou **249 URLs distintas**.
Os 248 atos ainda não consultados têm `id: null`, `verificado_em: null`, motivo
`nao-processado` e nenhum arquivo. Não receberam identidade pelos candidatos da listagem.
O catálogo não é reduzido ao documento solicitado.

A segunda execução terminou com **árvore Git limpa**: catálogo, documento e cobertura não
mudaram. A sequência de bytes, inclusive as datas da primeira execução, permaneceu igual.
O teste instrumentado da repetição com cache também reprova qualquer chamada ao conversor.

## Artefato publicado

- Página: [Resolução CVM 249](https://conteudo.cvm.gov.br/legislacao/resolucoes/resol249.html).
- Fonte convertida: [íntegra HTML oficial](https://conteudo.cvm.gov.br/legislacao/resolucoes/anexos/200/resol249.htm).
- SHA-256 da fonte: `409fccb29e8c06dccbbafef304d4b06ceca5f7889d827c8db59efcf06964194e`.
- Corpo conferido contra os bytes baixados, com sequência exata de tokens, **26 artigos,
  15 parágrafos numerados, 99 incisos e 1 anexo**. Parágrafos únicos são verificados separadamente.
- Arquivo: `reguladores/cvm/resolucoes/2026/cvm-resolucao-249-2026.md`.
- `revogada: null`: a ausência de afirmação oficial não virou declaração de vigência.

O verificador offline foi executado também com o cache efetivamente usado na coleta:
`violacoes: []`, `UNVERIFIED: []` para os controles que implementa. Isso não certifica os
critérios globais nem materiais ainda não coletados. A CLI `verify` procura o cache padrão;
quando os bytes estão apenas em um cache alternativo, informa sua verificação como UNVERIFIED.

## Auditoria da fila

Os dois logs registraram **15 requisições**: 13 para `conteudo.cvm.gov.br` e 2 para o host
legado `www.cvm.gov.br`, usado pelo redirecionamento publicado de robots. O mínimo observado
entre requisições ao host de conteúdo foi **5,000 s**; no legado, **115,125 s**.
Todas as requisições usaram o cliente com User-Agent identificado. A cadeia de robots foi
obtida pelo próprio cliente, sem cache de política preparado. Nenhuma chamada à API de dados.

As janelas dos eventos de auditoria foram 40,122 s na primeira execução e 15,118 s na segunda;
não são medições de runner hospedado. Logs, bytes originais e evidências ficam locais,
não versionados.

## Testes e limites

**189 testes** passaram no código e novamente após o commit dos dados, em árvore limpa.
São 22 novos testes de integração da CLI e uma regressão adicional de metadados: links de
download não são incorporados à ementa quando a página não contém aviso do DOU.

Os testes cobrem enumeração completa, falha sem promoção, códigos 2/3, lote fixo de 50,
limite de pendências novas, original preservado quando só o consolidado falha, cache alterado,
hash/proveniência, remoção da árvore corrente após falha de uma fonte modificada e ausência
de reconversão para conteúdo inalterado. Pendência inalterada pode ser reavaliada com
`--document`; publicado inalterado não é reconvertido.

Continuam **UNVERIFIED** ou fora desta entrega:

- Cobertura completa de todas as famílias e dos 249 corpos de resolução; esta coleta publicou um.
- SC-002 com 50 HTMLs, tabelas oficiais complexas, PDF/OCR e materiais de terceiros.
- Resolução automática de aliases semânticos e divergências de versões: T007.
- Reprocessamento automático de pendências após ativação de novos conversores: os tickets
  correspondentes devem habilitar essa passagem; o MVP permite revisão pontual por documento.
- Execução no runner real, agendamento, janela de sete dias e carga inicial completa.
