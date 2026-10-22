# Contrato: relatório de cobertura

Dois arquivos gerados a cada coleta, versionados na raiz:

- `cobertura/cobertura.json` — legível por máquina (contrato abaixo).
- `cobertura/COBERTURA.md` — mesma informação em tabelas para leitura humana.

## `cobertura.json`

```json
{
  "schema_versao": "1.1",
  "gerado_em": "2026-10-22T03:00:00Z",
  "coleta": { "modo": "completa | incremental | documento", "requisicoes": 0, "falhas_http": 0 },
  "categorias": [
    {
      "tipo": "Resolução",
      "catalogo_total": 249,
      "catalogo_metodo": "contador da busca | enumeração",
      "publicados": 0,
      "pendentes": 0,
      "indisponiveis": 0,
      "divergentes": 0,
      "fora_de_escopo": 0
    }
  ],
  "documentos": [
    {
      "id": "cvm-resolucao-175-2022",
      "estado": "publicado | pendente | indisponivel | divergente | fora-de-escopo",
      "motivo": null,
      "arquivos": ["reguladores/cvm/resolucoes/2022/resolucao-cvm-n-175-de-23-de-dezembro-de-2022.md"],
      "fonte_cvm": "https://conteudo.cvm.gov.br/legislacao/resolucoes/resol175.html",
      "urls_alternativas": [],
      "sha256_fontes": { "<url>": "<hex>" },
      "verificado_em": "2026-10-22"
    }
  ],
  "divergencias": [
    { "id": "cvm-resolucao-175-2022", "descricao": "...", "evidencias": ["<url>", "<url>"] }
  ]
}
```

## Regras

- `estado` e `motivo`: `pendente` sempre tem `motivo` (ex.: `tabela-nao-reproduzida`, `portao-fidelidade`,
  `soft-404`, `ocr-pendente`, `revisao-manual`). `indisponivel` cobre 404/410.
- `sha256_fontes` é também o índice de mudança: a coleta incremental compara com ele em vez de
  depender de cache persistente.
- Uma coleta sem mudança semântica na fonte/estado preserva os bytes de todos os arquivos públicos,
  inclusive `gerado_em`, `coleta` e `verificado_em`. Métricas da execução corrente ficam no log local e
  no stdout da CLI; não gerar commit apenas para mudar a data. Isso atende FR-023 e US6.
- Ordenação estável: categorias pela ordem da tabela de tipos; documentos por `id`.
- O relatório agrega por ato, não por versão. Original aprovado e consolidado pendente produzem
  um ato `pendente`, `arquivos` apenas com o original aprovado e `motivo` identificando a versão
  faltante e a causa. O ato conta uma vez em `pendentes`, sem duplicação em `publicados`.
- `catalogo_total` inclui todos os atos enumerados da categoria. A soma de `publicados`, `pendentes`,
  `indisponiveis`, `divergentes` e `fora_de_escopo` deve ser esse total, sem duplicações. Para medir
  cobertura no escopo, excluir apenas os classificados `fora-de-escopo` com motivo verificável;
  classificação desconhecida permanece pendente. O denominador no escopo é `catalogo_total - fora_de_escopo`.

## Migração 1.0 → 1.1

Acrescentado `fora_de_escopo`, contador opcional por categoria, com valor padrão zero para leitores
de arquivos antigos. Emissão nova usa schema 1.1; o front matter dos documentos continua 1.0.
Motivo: explicitar a reconciliação das contagens quando a enumeração encontra itens administrativos.
As regras de versões mistas e de não reescrever timestamps esclarecem invariantes de publicação;
não acrescentam valores a `estado` nem a `versao_texto`.
