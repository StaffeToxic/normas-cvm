# Contrato: relatório de cobertura

Dois arquivos gerados a cada coleta, versionados na raiz:

- `cobertura/cobertura.json` — legível por máquina (contrato abaixo).
- `cobertura/COBERTURA.md` — mesma informação em tabelas para leitura humana.

## `cobertura.json`

```json
{
  "schema_versao": "1.0",
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
      "divergentes": 0
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
- Uma coleta sem mudança na fonte gera `cobertura.json` idêntico, exceto `gerado_em` e `coleta`
  (SC-005 compara os arquivos de `reguladores/`).
- Ordenação estável: categorias pela ordem da tabela de tipos; documentos por `id`.
