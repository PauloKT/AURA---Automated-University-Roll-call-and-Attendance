# Regras de domínio do AURA

Conferência do código em **12/10/2026**. Os conceitos estão no [glossário](../GLOSSARY.md); este documento registra o comportamento atual e os pontos que ainda precisam de uma decisão de produto. A documentação não altera regras de frequência ou dados existentes.

## Organização e acesso

- Uma matéria pertence a um professor; uma turma pertence a uma matéria; uma aula pertence a uma turma.
- O professor gerencia os recursos ligados às suas matérias. O aluno consulta suas turmas e confirma sua própria presença.
- O catálogo de matérias ainda permite leitura de todas as matérias por alunos autenticados. Os dados do painel têm escopo mais restrito: professor responsável ou aluno vinculado.
- O vínculo em turma é único por aluno e turma. Entrar novamente não cria um segundo vínculo.
- A matrícula do aluno é obrigatória no cadastro público, mas o campo admite dados legados sem matrícula e não possui unicidade. Ela não substitui o vínculo em turma.
- A entrada por código exige turma ativa. O código tem oito caracteres e é diferente do token da chamada; o convite antigo por identificador também continua aceito.

Referências: [modelos acadêmicos](../backend/courses/models.py), [cadastro](../backend/accounts/serializers.py), [acesso aos recursos](../backend/courses/views.py), [entrada em turma](../backend/accounts/views.py).

## Instituição e geocerca

- O cadastro de professor exige ao menos uma instituição ativa existente ou o cadastro de uma nova instituição. As duas modalidades não podem ser misturadas no mesmo envio.
- Uma instituição nova entra no catálogo com localização pendente. O cadastro público não define suas coordenadas nem seu raio.
- Na abertura, a chamada copia o centro e o raio da instituição escolhida pelo backend. Alterar a instituição depois não atualiza a geocerca de chamadas já criadas.
- A escolha atual usa a primeira instituição ativa vinculada ao professor. Somente se ela não existir, usa a instituição singular legada; sem nenhuma dessas instituições, usa as coordenadas legadas do professor. Uma instituição escolhida com localização pendente bloqueia a abertura: a ausência de coordenadas não faz o sistema tentar outra instituição. A interface ainda não escolhe campus por aula.
- Os campos `professor_latitude`, `professor_longitude` e `professor_radius_meters` da chamada guardam essa referência copiada; não representam a posição atual do computador.
- A validação aceita raios de 1 a 10.000 metros e inclui o limite do raio. Coordenadas precisam ser finitas e estar nos limites de latitude e longitude.

Referências: [cadastro](../backend/accounts/serializers.py), [abertura da chamada](../backend/attendance/views.py), [geolocalização](../backend/attendance/geolocation.py).

## Ciclo de chamada e confirmação

1. O professor inicia uma chamada de sua aula. Se já há chamada ativa nessa aula, a abertura a reutiliza; após o encerramento, uma nova abertura cria outra chamada.
2. O token do QR expira em 30 segundos. Consultar o token renova apenas o token vencido de uma chamada ainda aberta.
3. A leitura validada exige aluno vinculado à turma e token atual válido. Ela produz um comprovante associado ao aluno e à chamada, com prazo de 120 segundos.
4. A confirmação exige vínculo, chamada aberta, token válido ou comprovante válido e localização dentro da geocerca. O comprovante não dispensa essas outras condições.
5. Tentativas fora do raio ou com credencial inválida são rejeitadas sem criar presença. É possível tentar novamente enquanto as condições continuarem válidas.
6. Um novo registro confirmado devolve HTTP 201. Um reenvio válido de presença já confirmada devolve HTTP 200 e preserva o registro original, incluindo horário e localização. O reenvio ainda precisa passar pelas validações; uma chamada encerrada não aceita nova confirmação.
7. Um registro inválido legado pode ser corrigido por uma confirmação válida enquanto a chamada estiver aberta, sem criar um segundo registro para o mesmo aluno.
8. Antes de gravar, vínculo, estado da chamada, credencial e geocerca são revalidados na transação. O resultado de uma disputa entre confirmar e encerrar segue a ordem em que as operações obtêm a escrita no banco.

Referências: [operações da chamada](../backend/attendance/views.py), [confirmação](../backend/attendance/serializers.py), [transações](../backend/attendance/transactions.py), [testes de confirmação](../backend/attendance/test_confirmation.py).

## Frequência

Para um aluno e uma turma:

```text
chamadas consideradas = chamadas da turma com ativa=False
presenças consideradas = presenças válidas do aluno nessas chamadas
faltas = chamadas consideradas - presenças consideradas
frequência = presenças consideradas / chamadas consideradas × 100
```

- Sem chamadas encerradas, o contrato retorna percentual `0.0` e situação `sem_dados`; isso não significa frequência insuficiente.
- A comparação com o mínimo usa o percentual antes do arredondamento. O percentual retornado é arredondado para duas casas decimais.
- A interface exibe no máximo uma casa decimal. Esse arredondamento visual não altera a situação calculada nem o valor usado na exportação CSV.
- A partir do mínimo, o contrato usa `aprovado`; abaixo dele, `reprovado`. A interface apresenta **Regular** e **Atenção**. Esses nomes se referem somente à frequência.
- Chamadas abertas e suas presenças não entram no cálculo, mesmo que a aula já tenha ocorrido.
- Chamadas distintas de uma mesma aula contam separadamente. A data de entrada do aluno na turma não limita o histórico considerado hoje.
- A carga horária da matéria e a duração da aula não dão pesos diferentes às chamadas.
- O campo `aulas` nas linhas da API do painel contém a quantidade de chamadas encerradas, apesar do nome legado. A tabela e o CSV apresentam esse valor com o cabeçalho **Chamadas**.
- A frequência geral do aluno é calculada a partir das somas de presenças e chamadas das suas turmas.
- No painel do professor, a média de uma turma usa os percentuais dos alunos atualmente vinculados. O campo `media` é arredondado para uma casa decimal e fica sem valor quando não há alunos ou chamadas encerradas. No retorno do painel do aluno, esse mesmo campo considera somente o próprio aluno, pois os vínculos são filtrados antes do cálculo; ele não expõe a média dos colegas.
- A lista de registros recentes e o resultado ao vivo não constituem uma lista completa de faltas: as faltas são calculadas pela ausência de presença confirmada nas chamadas encerradas.

Exemplo: duas aulas cadastradas, três chamadas encerradas e duas presenças válidas produzem **66,67%**, independentemente de qual aula originou cada chamada. Com mínimo de 75%, a situação é **Atenção**.

Referências: [módulo de frequência](../backend/attendance/frequency.py), [consultas do aluno](../backend/accounts/views.py), [painel](../backend/backend/ui_api.py), [resumo do aluno](../frontend/student-workspace.js), [rótulos da interface](../frontend/ui.js), [contratos e casos de borda](../backend/attendance/test_frequency.py), [atualização após encerramento](../backend/accounts/test_medium_issues.py).

## Decisões ainda não tomadas

Os pontos abaixo são comportamentos existentes ou ambiguidades observadas, não novas regras aprovadas:

- **Entrada tardia:** hoje o aluno pode receber faltas por chamadas encerradas antes de seu vínculo. Excluir essas chamadas alteraria os resultados históricos.
- **Nova chamada na mesma aula:** cada chamada encerrada conta separadamente. Contar uma única vez por aula exigiria definir como combinar as presenças.
- **Campus por aula:** não existe seleção explícita. O vínculo singular legado pode apontar para instituição inativa, pois esse fallback não revalida `ativa`.
- **Turma inativa:** impede entrada por código, mas não impõe por si só uma proibição geral de novas chamadas. O fluxo de abertura verifica o professor e a localização, sem verificar `turma.ativa`.
- **Edição e exclusão do histórico:** exclusões acadêmicas podem apagar chamadas e presenças por cascata. Mudar a turma de uma aula também pode alterar a atribuição de chamadas existentes; ainda não há regra de arquivamento ou auditoria acadêmica.
- **Indicadores com nomes amplos:** “Matérias em atenção” no painel do aluno conta linhas por vínculo em turma, sem eliminar matérias repetidas. O total “aguardando” da chamada desconta registros existentes, inclusive inválidos legados, enquanto a lista de chamadas pendentes do aluno só desconta presenças válidas.

Uma refatoração estrutural deve preservar esses resultados até que a regra correspondente seja escolhida explicitamente. Não há ADR novo: nenhuma decisão de arquitetura difícil de reverter foi tomada nesta revisão.
