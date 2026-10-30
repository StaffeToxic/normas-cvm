# Reconferência de direitos e licenças dos materiais

Data: **29/10/2026**, horário de Brasília. Registro HTTP do hub gov.br em
`2026-10-30T00:28:26Z`. Este relatório separa aviso de portal, texto de licença e classificação
do material; não certifica uma licença única para todo o acervo.

## Fontes efetivamente conferidas

| Fonte | Resultado confirmado | Limite |
|---|---|---|
| [Hub de normas da CVM no gov.br](https://www.gov.br/cvm/pt-br/assuntos/normas) | GET 200; 134.613 bytes; rodapé com link `rel="license"` para CC BY-ND 3.0 | O aviso é do site; não prova por si só os direitos de cada PDF, figura ou documento em outro domínio |
| [Texto da CC BY-ND 3.0](https://creativecommons.org/licenses/by-nd/3.0/legalcode.en) | Seções 2, 3 e 4 conferidas no texto publicado pela Creative Commons | Distinguir permissão de formato, restrição de adaptação, atribuição e direitos que o licenciante pode conceder |
| [Lei 9.610/1998, texto atualizado na Câmara](https://www2.camara.leg.br/legin/fed/lei/1998/lei-9610-19-fevereiro-1998-365399-normaatualizada-pl.html) | Art. 8º, IV inclui textos de leis, decretos, regulamentos, decisões judiciais e demais atos oficiais entre as exclusões de proteção autoral | Não estende automaticamente essa classificação a todo conteúdo editorial publicado por um órgão |
| [Texto no Planalto](https://www.planalto.gov.br/ccivil_03/leis/l9610.htm) | A resposta à consulta mostrou página de acesso negado; nenhuma nova tentativa para contornar o bloqueio | A confirmação textual usada acima veio da publicação oficial da Câmara, não dessa resposta |

SHA-256 dos bytes do hub gov.br:
`16034fb5f12996b16a4ef058a273db8071f770431f1ee6620d88e111ba652378`.
Captura bruta e log de requisições permanecem em evidência local não versionada.

## Formato técnico não é sinônimo de autorização irrestrita

A seção 3 da CC BY-ND 3.0 permite os formatos abrangidos e modificações tecnicamente necessárias
para exercê-los. A seção 4 mantém condições de licença e atribuição; não concede liberdade geral
para adaptações. A seção 2 preserva usos decorrentes de exceções legais. Portanto, a presença de
BY-ND não proíbe automaticamente toda mudança de suporte, nem autoriza reescrever um material
protegido. Essas conclusões se limitam ao texto da licença; a classificação de uma transformação
concreta em Markdown continua **UNVERIFIED** sem examinar material e alterações.

## Matriz operacional para o acervo

| Material | Tratamento proposto | Estado da confirmação |
|---|---|---|
| Texto de ato normativo oficial | Registrar fonte e integridade; aplicar a distinção do art. 8º, IV, sem chamar o texto de código MIT | Base legal conferida; identificação do conteúdo como ato oficial exige evidência por documento |
| Página editorial do hub gov.br | Preservar aviso e atribuição quando houver reuso abrangido pela licença | Aviso BY-ND 3.0 reconfirmado nessa página |
| FAQ, guia, manual ou explicação | Examinar aviso aplicável e natureza do material; não equiparar automaticamente a um ato normativo | Licença e direitos por documento: **UNVERIFIED** |
| Figura, tabela ou anexo de terceiro | Verificar autoria, proveniência e termos próprios antes de redistribuir | Não existe certificação global nesta pesquisa |
| Compilação externa usada como referência | Manter separada da coleta direta oficial; não presumir licença do corpo a partir da licença do código | Continua **UNVERIFIED** |
| Código deste repositório | Seguir [LICENSE](../../../LICENSE) e avisos de terceiros quando houver código derivado | Licença do código não relicencia os insumos |

## Decision

Manter direitos e proveniência por artefato. Não aplicar ODbL de conjuntos de dados, MIT do código
ou o aviso do hub gov.br indistintamente aos textos do portal de legislação. Usar o caminho
oficial direto para atos identificados, conservando bloqueios para materiais de direitos não
confirmados. Nenhum aviso de publicação da raiz foi alterado.

## Rationale

Há três questões diferentes: natureza jurídica do texto, licença declarada onde ele foi publicado
e modificações efetivamente feitas. A coleta observou um aviso BY-ND no hub e conferiu a exclusão
legal para atos oficiais; isso não resolve todos os anexos e materiais explicativos.

## Alternatives considered

- Classificar todo conteúdo CVM como MIT ou ODbL: rejeitado, pois não há evidência dessa extensão.
- Tratar qualquer conversão de formato como adaptação proibida: rejeitado como conclusão geral;
  a licença distingue modificações técnicas e a lei trata separadamente atos oficiais.
- Considerar todo manual ou FAQ um ato oficial excluído de proteção: rejeitado sem exame do material.

## UNVERIFIED

- Licença declarada de cada artefato em `conteudo.cvm.gov.br`; o aviso do hub não encerra essa questão.
- Direitos sobre cada imagem, quadro, tabela de origem externa e compilação editorial.
- Classificação de conversões concretas que reorganizem, excluam ou acrescentem conteúdo.
- Ausência de direitos de terceiros em todos os documentos de uma categoria. Este relatório não
  representa uma autorização coletiva de publicação.
