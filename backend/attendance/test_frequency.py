"""Contratos públicos da frequência, compartilhados por turmas e painéis."""
from datetime import date, time

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APITestCase

from courses.models import Aula, Materia, Turma, TurmaAluno
from .frequency import consultar_frequencias
from .models import Presenca, SessaoChamada


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class FrequencyContractTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.professor = User.objects.create_user(username='Professor A', role='professor')
        cls.outro_professor = User.objects.create_user(username='Professor B', role='professor')
        cls.aluno = User.objects.create_user(username='Aluno A', role='aluno', matricula='101')
        cls.colega = User.objects.create_user(username='Aluno B', role='aluno', matricula='102')
        cls.visitante = User.objects.create_user(username='Aluno C', role='aluno')
        cls.materia = Materia.objects.create(
            nome='Matéria principal', codigo='FREQ-1', carga_horaria=60,
            frequencia_minima=75, professor=cls.professor,
        )
        cls.turma = Turma.objects.create(nome='Turma principal', materia=cls.materia, semestre='2', ano=2026)
        cls.aula = Aula.objects.create(
            turma=cls.turma, titulo='Aula principal', data=date(2026, 10, 1),
            horario_inicio=time(19), horario_fim=time(21),
        )
        TurmaAluno.objects.create(turma=cls.turma, aluno=cls.aluno)
        TurmaAluno.objects.create(turma=cls.turma, aluno=cls.colega)

    def chamada(self, presentes=(), *, ativa=False, aula=None):
        chamada = SessaoChamada.objects.create(
            aula=aula or self.aula, ativa=ativa,
            professor_latitude=-20, professor_longitude=-54,
        )
        for aluno in presentes:
            Presenca.objects.create(sessao=chamada, aluno=aluno, latitude=-20, longitude=-54)
        return chamada

    def painel(self, usuario):
        self.client.force_authenticate(usuario)
        response = self.client.get('/api/interface/painel/')
        self.assertEqual(response.status_code, 200)
        return response.data

    def assert_frequencia(self, aluno, turma, *, chamadas, presencas, percentual, situacao):
        self.client.force_authenticate(aluno)
        individual = self.client.get('/api/aluno/minha-frequencia/', {'turma': turma.pk})
        self.assertEqual(individual.status_code, 200)
        self.assertEqual(individual.data, {'percentual': percentual, 'situacao': situacao})
        response = self.client.get('/api/aluno/turmas/')
        self.assertEqual(response.status_code, 200)
        resumo = next(item for item in response.data['turmas'] if item['turma_id'] == turma.pk)
        self.assertEqual(
            (resumo['presencas'], resumo['faltas'], resumo['percentual'], resumo['situacao']),
            (presencas, chamadas - presencas, percentual, situacao),
        )
        self.assertEqual(set(resumo), {
            'turma_id', 'nome', 'materia', 'semestre', 'ano', 'ativa',
            'percentual', 'situacao', 'professor', 'presencas', 'faltas',
        })
        for usuario in (aluno, turma.materia.professor):
            with self.subTest(usuario=usuario.username):
                rows = self.painel(usuario)['frequencias']
                linha = next(item for item in rows if item['aluno_id'] == aluno.pk and item['turma_id'] == turma.pk)
                self.assertEqual(
                    (linha['aulas'], linha['presencas'], linha['faltas'], linha['percentual'], linha['situacao']),
                    (chamadas, presencas, chamadas - presencas, percentual, situacao),
                )
                self.assertEqual(set(linha), {
                    'vinculo_id', 'aluno_id', 'aluno', 'matricula', 'turma_id', 'turma',
                    'materia_id', 'materia', 'aulas', 'presencas', 'faltas', 'percentual',
                    'situacao', 'minimo',
                })

    def test_multiple_calls_for_same_lesson_and_late_enrollment_still_count(self):
        self.chamada([self.aluno])
        self.chamada([self.aluno])
        self.chamada()
        self.chamada([self.aluno], ativa=True)
        TurmaAluno.objects.filter(turma=self.turma, aluno=self.aluno).update(
            data_entrada=timezone.now() + timezone.timedelta(days=1),
        )
        self.assert_frequencia(self.aluno, self.turma, chamadas=3, presencas=2,
                              percentual=66.67, situacao='reprovado')

    def test_invalid_legacy_presence_does_not_count_but_stays_in_recent_records(self):
        chamada = self.chamada()
        Presenca.objects.create(sessao=chamada, aluno=self.aluno, latitude=-21, longitude=-54)
        self.assert_frequencia(self.aluno, self.turma, chamadas=1, presencas=0,
                              percentual=0.0, situacao='reprovado')
        self.assertEqual(self.painel(self.aluno)['recentes'][0]['status'], 'falta')

    def test_classification_uses_unrounded_percentage(self):
        self.materia.frequencia_minima = 1
        self.materia.save(update_fields=['frequencia_minima'])
        for index in range(201):
            self.chamada([self.aluno] if index < 2 else [])
        # 2/201 = 0,995...%; aparece como 1,00%, mas ainda está abaixo do mínimo.
        self.assert_frequencia(self.aluno, self.turma, chamadas=201, presencas=2,
                              percentual=1.0, situacao='reprovado')

    def test_exact_minimum_is_regular_and_no_calls_is_not_insufficient(self):
        self.assert_frequencia(self.aluno, self.turma, chamadas=0, presencas=0,
                              percentual=0.0, situacao='sem_dados')
        for index in range(4):
            self.chamada([self.aluno] if index < 3 else [])
        self.assert_frequencia(self.aluno, self.turma, chamadas=4, presencas=3,
                              percentual=75.0, situacao='aprovado')

    def test_teacher_mean_and_student_mean_keep_their_own_scope(self):
        self.chamada([self.aluno, self.colega])
        self.chamada([self.aluno])
        turma_professor = self.painel(self.professor)['turmas'][0]
        turma_aluno = self.painel(self.aluno)['turmas'][0]
        self.assertEqual((turma_professor['alunos'], turma_professor['chamadas'], turma_professor['media']), (2, 2, 75.0))
        self.assertEqual((turma_aluno['alunos'], turma_aluno['chamadas'], turma_aluno['media']), (1, 2, 100.0))
        self.assertIsNone(turma_aluno['codigo_acesso'])
        self.assertEqual(turma_professor['codigo_acesso'], self.turma.codigo_acesso)

    def test_groups_without_enrollments_keep_call_total_and_no_mean(self):
        self.chamada([self.aluno])
        TurmaAluno.objects.filter(turma=self.turma).delete()
        painel = self.painel(self.professor)
        self.assertEqual(painel['frequencias'], [])
        self.assertEqual((painel['turmas'][0]['alunos'], painel['turmas'][0]['chamadas'], painel['turmas'][0]['media']), (0, 1, None))
        self.assertEqual(len(painel['recentes']), 1)
        self.assertEqual(self.painel(self.aluno)['turmas'], [])

    def test_groups_students_and_teacher_ownership_are_isolated(self):
        materia = Materia.objects.create(
            nome='Outra matéria', codigo='FREQ-2', carga_horaria=30,
            frequencia_minima=50, professor=self.outro_professor,
        )
        turma = Turma.objects.create(nome='Outra turma', materia=materia, semestre='2', ano=2026, ativa=False)
        aula = Aula.objects.create(turma=turma, titulo='Outra aula', data=date(2026, 10, 2), horario_inicio=time(8), horario_fim=time(9))
        TurmaAluno.objects.create(turma=turma, aluno=self.aluno)
        self.chamada([self.colega])
        self.chamada([self.aluno], aula=aula)
        self.chamada(aula=aula)
        self.assert_frequencia(self.aluno, self.turma, chamadas=1, presencas=0,
                              percentual=0.0, situacao='reprovado')
        self.assert_frequencia(self.aluno, turma, chamadas=2, presencas=1,
                              percentual=50.0, situacao='aprovado')
        self.assertEqual({item['turma_id'] for item in self.painel(self.professor)['frequencias']}, {self.turma.pk})
        self.assertEqual({item['turma_id'] for item in self.painel(self.outro_professor)['frequencias']}, {turma.pk})
        self.assertEqual({item['aluno_id'] for item in self.painel(self.aluno)['frequencias']}, {self.aluno.pk})
        self.client.force_authenticate(self.visitante)
        self.assertEqual(self.client.get('/api/aluno/minha-frequencia/', {'turma': self.turma.pk}).status_code, 403)
        self.assertEqual(self.painel(self.visitante)['frequencias'], [])
        self.client.force_authenticate(self.professor)
        self.assertEqual(self.client.get('/api/aluno/minha-frequencia/', {'turma': self.turma.pk}).status_code, 403)
        self.client.force_authenticate(None)
        for path in ('/api/aluno/minha-frequencia/', '/api/aluno/turmas/', '/api/interface/painel/'):
            self.assertEqual(self.client.get(path).status_code, 401)

    def test_query_count_does_not_grow_per_group_or_enrollment(self):
        self.chamada([self.aluno])
        cases = [(self.professor, '/api/interface/painel/'), (self.aluno, '/api/aluno/turmas/')]

        def query_counts():
            counts = []
            for usuario, path in cases:
                self.client.force_authenticate(usuario)
                with CaptureQueriesContext(connection) as queries:
                    response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                counts.append(len(queries))
            return counts

        initial = query_counts()
        for index in range(5):
            turma = Turma.objects.create(nome=f'Turma adicional {index}', materia=self.materia, semestre='2', ano=2026)
            aula = Aula.objects.create(turma=turma, titulo='Aula adicional', data=date(2026, 10, 2), horario_inicio=time(8), horario_fim=time(9))
            for aluno in (self.aluno, self.colega, self.visitante):
                TurmaAluno.objects.create(turma=turma, aluno=aluno)
            self.chamada([self.aluno, self.colega], aula=aula)
        self.assertEqual(query_counts(), initial)

    def test_batch_result_includes_empty_groups_and_loaded_metadata(self):
        self.chamada([self.aluno])
        vazia = Turma.objects.create(nome='Turma vazia', materia=self.materia, semestre='2', ano=2026)
        ids = (pk for pk in (self.turma.pk, vazia.pk, self.turma.pk))
        with CaptureQueriesContext(connection) as queries:
            frequencias = consultar_frequencias(ids)
        self.assertLessEqual(len(queries), 2)
        # Consumidores podem percorrer o resultado e seus metadados sem mais I/O.
        with self.assertNumQueries(0):
            self.assertEqual(set(frequencias.turmas), {self.turma.pk, vazia.pk})
            self.assertEqual(len(frequencias.vinculos), 2)
            resumo = frequencias.turmas[self.turma.pk]
            self.assertEqual((resumo.chamadas, resumo.alunos, resumo.media), (1, 2, 50.0))
            resumo_vazio = frequencias.turmas[vazia.pk]
            self.assertEqual((resumo_vazio.chamadas, resumo_vazio.alunos, resumo_vazio.media), (0, 0, None))
            for frequencia in frequencias.vinculos:
                vinculo = frequencia.vinculo
                self.assertIn(vinculo.aluno.username, ('Aluno A', 'Aluno B'))
                self.assertEqual(vinculo.turma.materia.professor.username, 'Professor A')
                self.assertEqual(frequencia.faltas, 0 if vinculo.aluno_id == self.aluno.pk else 1)

    def test_call_closing_between_reads_keeps_counts_consistent(self):
        self.chamada([self.aluno])
        aberta = self.chamada([self.aluno], ativa=True)
        vazia = Turma.objects.create(nome='Turma vazia', materia=self.materia, semestre='2', ano=2026)
        leituras = 0

        def encerrar_entre_leituras(execute, sql, params, many, context):
            nonlocal leituras
            if sql.lstrip().upper().startswith('SELECT'):
                leituras += 1
                if leituras == 2:
                    SessaoChamada.objects.filter(pk=aberta.pk).update(ativa=False)
            return execute(sql, params, many, context)

        # Simula o encerramento entre leituras, sem depender do escalonamento de threads.
        with connection.execute_wrapper(encerrar_entre_leituras):
            resultado = consultar_frequencias([self.turma.pk, vazia.pk], aluno_id=self.aluno.pk)
        frequencia = resultado.vinculos[0]
        self.assertIn((frequencia.chamadas, frequencia.presencas), ((1, 1), (2, 2)))
        self.assertEqual((frequencia.percentual, frequencia.faltas), (100.0, 0))
        self.assertEqual(resultado.turmas[self.turma.pk].chamadas, frequencia.chamadas)

        # Uma nova consulta deve refletir o encerramento; o resultado não fica em cache.
        SessaoChamada.objects.filter(pk=aberta.pk).update(ativa=False)
        atualizada = consultar_frequencias([self.turma.pk], aluno_id=self.aluno.pk).vinculos[0]
        self.assertEqual((atualizada.chamadas, atualizada.presencas, atualizada.faltas), (2, 2, 0))

    def test_empty_batch_and_unenrolled_student_do_not_expose_other_students(self):
        with self.assertNumQueries(0):
            vazio = consultar_frequencias([])
        self.assertEqual(vazio.vinculos, ())
        self.assertEqual(vazio.turmas, {})
        self.chamada([self.aluno])
        restrito = consultar_frequencias([self.turma.pk], aluno_id=self.visitante.pk)
        self.assertEqual(restrito.vinculos, ())
        resumo = restrito.turmas[self.turma.pk]
        self.assertEqual((resumo.chamadas, resumo.alunos, resumo.media), (1, 0, None))
