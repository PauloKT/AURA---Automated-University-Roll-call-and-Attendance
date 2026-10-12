"""Frequência na turma: seleção, contagens e classificação em lote.

Os chamadores fornecem somente IDs de turmas cujo acesso já foi autorizado.
O resultado inclui todos os vínculos atuais, ou apenas os de ``aluno_id``.
Chamadas anteriores ao vínculo e chamadas distintas da mesma aula continuam
contando. Os metadados dos vínculos são carregados junto, sem consultas por linha.
"""
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from django.db.models import Count, F, FilteredRelation, Q

from courses.models import TurmaAluno
from .models import SessaoChamada


@dataclass(frozen=True)
class FrequenciaAluno:
    vinculo: TurmaAluno
    chamadas: int
    presencas: int
    percentual: float
    situacao: str

    @property
    def faltas(self) -> int:
        return self.chamadas - self.presencas


@dataclass(frozen=True)
class FrequenciaTurma:
    chamadas: int
    alunos: int
    media: float | None


@dataclass(frozen=True)
class Frequencias:
    vinculos: tuple[FrequenciaAluno, ...]
    turmas: dict[int, FrequenciaTurma]


def _classificar(chamadas: int, presencas: int, minimo: int) -> tuple[float, str]:
    if not chamadas:
        return 0.0, 'sem_dados'
    percentual = presencas / chamadas * 100
    situacao = 'aprovado' if percentual >= minimo else 'reprovado'
    return round(percentual, 2), situacao


def consultar_frequencias(turma_ids: Iterable[int], *, aluno_id: int | None = None) -> Frequencias:
    """Consulta um conjunto autorizado em até duas consultas, sem gravar ou fazer cache.

    ``turmas`` inclui até turmas sem vínculos; ``vinculos`` contém uma frequência
    por vínculo, ordenada por turma e ID do vínculo. Cada vínculo já inclui aluno,
    turma, matéria e professor. A média usa somente os vínculos consultados: com
    ``aluno_id``, não inclui dados dos colegas. IDs vazios não consultam o banco.
    """
    turma_ids = tuple(dict.fromkeys(turma_ids))
    if not turma_ids:
        return Frequencias(vinculos=(), turmas={})

    vinculos = TurmaAluno.objects.filter(turma_id__in=turma_ids)
    if aluno_id is not None:
        vinculos = vinculos.filter(aluno_id=aluno_id)
    # Numerador e denominador vêm da mesma instrução SQL, mesmo durante encerramentos.
    # O JOIN de presenças considera apenas o aluno do vínculo, sem multiplicar colegas.
    vinculos = vinculos.annotate(
        chamadas_encerradas=FilteredRelation(
            'turma__aulas__sessoes', condition=Q(turma__aulas__sessoes__ativa=False),
        ),
        presencas_confirmadas=FilteredRelation(
            'chamadas_encerradas__presencas',
            condition=Q(
                chamadas_encerradas__presencas__aluno_id=F('aluno_id'),
                chamadas_encerradas__presencas__valida=True,
            ),
        ),
    ).annotate(
        total_chamadas=Count('chamadas_encerradas', distinct=True),
        total_presencas=Count('presencas_confirmadas', distinct=True),
    ).select_related('aluno', 'turma__materia__professor').order_by('turma_id', 'pk')

    resultados = []
    totais = {}
    percentuais = defaultdict(list)
    for vinculo in vinculos:
        chamadas = vinculo.total_chamadas
        presencas_aluno = vinculo.total_presencas
        percentual, situacao = _classificar(chamadas, presencas_aluno, vinculo.turma.materia.frequencia_minima)
        resultados.append(FrequenciaAluno(vinculo, chamadas, presencas_aluno, percentual, situacao))
        totais[vinculo.turma_id] = chamadas
        percentuais[vinculo.turma_id].append(percentual)

    # Turmas sem vínculos no conjunto consultado ainda exibem seu total de chamadas.
    sem_vinculos = [turma_id for turma_id in turma_ids if turma_id not in totais]
    if sem_vinculos:
        totais.update(
            SessaoChamada.objects.filter(aula__turma_id__in=sem_vinculos, ativa=False)
            .values('aula__turma_id').annotate(total=Count('id'))
            .values_list('aula__turma_id', 'total')
        )

    turmas = {}
    for turma_id in turma_ids:
        chamadas = totais.get(turma_id, 0)
        valores = percentuais[turma_id]
        media = round(sum(valores) / len(valores), 1) if valores and chamadas else None
        turmas[turma_id] = FrequenciaTurma(chamadas=chamadas, alunos=len(valores), media=media)
    return Frequencias(vinculos=tuple(resultados), turmas=turmas)
