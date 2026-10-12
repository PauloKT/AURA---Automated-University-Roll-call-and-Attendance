# AURA — acompanhamento de presença acadêmica

O AURA organiza matérias, turmas e aulas e acompanha a frequência dos alunos por chamadas com QR Code e localização. Este vocabulário distingue os conceitos já usados no sistema.

## Pessoas e locais

**Professor**:
Pessoa responsável pelas matérias e, por meio delas, pelas turmas, aulas e chamadas.
_Evitar_: administrador, quando se trata do responsável pela matéria.

**Aluno**:
Pessoa que participa de turmas e confirma a própria presença nas chamadas.
_Evitar_: usuário, quando a regra se aplica especificamente ao aluno.

**Matrícula do aluno**:
Identificador acadêmico informado no cadastro do aluno. É diferente da participação desse aluno em uma turma.
_Evitar_: vínculo em turma, inscrição em turma.

**Instituição**:
Local acadêmico cadastrado com nome e endereço, usado como referência geográfica das chamadas. Na interface, esse local também pode ser chamado de campus.
_Evitar_: posição do professor, localização do computador.

## Organização acadêmica

**Matéria**:
Unidade de ensino de um professor, com código, carga horária e frequência mínima. Pode reunir várias turmas.
_Evitar_: curso, turma, aula.

**Turma**:
Grupo de uma matéria identificado por nome, semestre e ano. Reúne os vínculos dos alunos e as aulas.
_Evitar_: matéria, sala física.

**Vínculo em turma**:
Participação de um aluno em uma turma, com data de entrada. Um aluno pode ter vínculos em várias turmas.
_Evitar_: matrícula, quando não estiver claro se é o identificador acadêmico ou a participação na turma.

**Código de acesso da turma**:
Código compartilhado pelo professor para que o aluno entre em uma turma.
_Evitar_: token de chamada, comprovante de leitura.

**Aula**:
Encontro de uma turma com título, data e horários de início e fim. Pode ter mais de uma chamada ao longo do seu histórico.
_Evitar_: chamada, sessão de chamada.

## Chamada e presença

**Chamada**:
Ocasião de registro de presença associada a uma aula, com abertura, encerramento e referência geográfica próprios. Também é denominada sessão de chamada.
_Evitar_: aula, sessão de login.

**Geocerca da chamada**:
Área circular em torno da referência geográfica da chamada, definida por um centro e um raio permitido.
_Evitar_: localização atual do professor, alcance do Wi-Fi.

**Token da chamada**:
Código temporário apresentado pelo QR Code de uma chamada aberta. Sua validade é diferente da validade do comprovante de leitura.
_Evitar_: código da turma, credencial de login.

**Comprovante de leitura**:
Comprovação temporária de que determinado aluno leu um QR válido de determinada chamada. Permite concluir a confirmação enquanto a chamada e o comprovante continuam válidos.
_Evitar_: presença confirmada, comprovante de frequência.

**Presença confirmada**:
Registro válido da participação de um aluno em uma chamada, associado ao horário do registro e à localização usada na confirmação.
_Evitar_: leitura do QR, tentativa de confirmação.

**Tentativa de confirmação**:
Pedido do aluno para confirmar presença em uma chamada. Uma tentativa rejeitada não constitui presença confirmada.
_Evitar_: falta, presença inválida, quando não existe um registro salvo.

## Acompanhamento

**Frequência na turma**:
Percentual de chamadas encerradas da turma nas quais o aluno tem presença confirmada.
_Evitar_: percentual de aulas cadastradas, frequência por carga horária.

**Frequência mínima**:
Percentual definido na matéria para comparar a frequência do aluno em cada turma dessa matéria.
_Evitar_: nota mínima, quantidade mínima de presenças.

**Falta no relatório**:
Chamada encerrada da turma na qual o aluno não tem presença confirmada, considerada no cálculo de frequência.
_Evitar_: tentativa rejeitada, falha de GPS.

**Situação de frequência**:
Resultado da comparação entre frequência na turma e frequência mínima, ou ausência de dados quando nenhuma chamada foi encerrada.
_Evitar_: aprovação acadêmica final, nota da matéria.

**Frequência geral do aluno**:
Percentual obtido pela soma das presenças confirmadas e das chamadas encerradas consideradas nas turmas do aluno.
_Evitar_: média simples dos percentuais das turmas.

**Frequência média da turma**:
Média dos percentuais de frequência dos alunos atualmente vinculados à turma.
_Evitar_: frequência geral do aluno.
