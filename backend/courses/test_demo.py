"""Valida o carregamento da demonstração em banco temporário, sem dados reais."""
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from attendance.models import Presenca, SessaoChamada
from .models import Aula, Instituicao, Materia, Turma, TurmaAluno


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class DemoDataTests(APITestCase):
    def seed(self, password='SenhaDemoTeste!'):
        output = StringIO()
        with patch.dict('os.environ', {'AURA_DEMO_PASSWORD': password}):
            call_command('seed_demo', stdout=output)
        return output.getvalue()

    def test_demo_has_coherent_history_and_varied_reports(self):
        self.seed()
        User = get_user_model()
        self.assertEqual(User.objects.filter(email__endswith='@demo.aura.test', role='professor').count(), 4)
        self.assertEqual(User.objects.filter(email__endswith='@demo.aura.test', role='aluno').count(), 24)
        self.assertFalse(User.objects.filter(email__endswith='@demo.aura.test', is_staff=True).exists())
        self.assertEqual(Instituicao.objects.filter(geocoding_source='aura-demo-v1').count(), 3)
        self.assertEqual(Materia.objects.count(), 6)
        self.assertEqual(Turma.objects.count(), 8)
        self.assertEqual(Aula.objects.count(), 72)
        self.assertEqual(SessaoChamada.objects.count(), 56)
        self.assertFalse(SessaoChamada.objects.filter(ativa=True).exists())
        self.assertFalse(Presenca.objects.filter(valida=False).exists())
        for session in SessaoChamada.objects.select_related('aula'):
            self.assertEqual(timezone.localdate(session.iniciada_em), session.aula.data)
            self.assertLess(session.iniciada_em, session.encerrada_em)
            self.assertLess(session.encerrada_em, timezone.now())
            self.assertLess(session.token_expira_em, session.encerrada_em)
        for presence in Presenca.objects.select_related('sessao__aula'):
            self.assertLessEqual(presence.sessao.iniciada_em, presence.registrada_em)
            self.assertLessEqual(presence.registrada_em, presence.sessao.encerrada_em)
        for enrollment in TurmaAluno.objects.select_related('turma__materia__professor'):
            self.assertLess(enrollment.data_entrada, timezone.now())
            professor = enrollment.turma.materia.professor
            self.assertTrue(professor.instituicoes.exists())

        student = User.objects.get(username='Lucas Martins')
        self.assertTrue(student.check_password('SenhaDemoTeste!'))
        self.client.force_authenticate(student)
        response = self.client.get('/api/interface/painel/')
        self.assertEqual(response.status_code, 200)
        percentages = {row['materia']: row['percentual'] for row in response.data['frequencias'] if row['aulas']}
        self.assertEqual(percentages, {
            'Banco de Dados II': 100.0, 'Desenvolvimento Web': 87.5,
            'Engenharia de Software': 75.0, 'Redes de Computadores': 50.0,
        })
        self.assertEqual({row['situacao'] for row in response.data['frequencias']}, {'aprovado', 'reprovado', 'sem_dados'})
        self.assertTrue(response.data['recentes'])
        self.client.force_authenticate(User.objects.get(username='Mariana Costa'))
        response = self.client.get('/api/interface/painel/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['turmas']), 5)
        self.assertEqual(len(response.data['materias']), 3)
        self.assertGreater(len(response.data['frequencias']), 50)

    def test_rerun_keeps_passwords_records_and_unrelated_data(self):
        User = get_user_model()
        existing = User.objects.create_user(username='Cadastro existente', password='OutraSenha!', role='professor')
        subject = Materia.objects.create(nome='Matéria existente', codigo='REAL-01', carga_horaria=40, professor=existing)
        self.seed()
        SessaoChamada.objects.create(
            aula=Aula.objects.filter(turma__materia__codigo='DEMO-BD202').first(),
            ativa=False, professor_latitude=-20.787, professor_longitude=-51.703,
        )
        models = (User, Instituicao, Materia, Turma, TurmaAluno, Aula, SessaoChamada, Presenca)
        counts = [model.objects.count() for model in models]
        student = User.objects.get(username='Lucas Martins')
        original_password = student.password
        original_history = list(Presenca.objects.values_list('pk', 'registrada_em', 'valida'))
        original_dates = list(Aula.objects.values_list('pk', 'data'))
        with patch('courses.management.commands.seed_demo.timezone.localdate', return_value=timezone.localdate() + timezone.timedelta(days=10)):
            output = self.seed(password='NaoDeveTrocar!')
        self.assertEqual([model.objects.count() for model in models], counts)
        student.refresh_from_db()
        existing.refresh_from_db()
        subject.refresh_from_db()
        self.assertEqual(student.password, original_password)
        self.assertTrue(existing.check_password('OutraSenha!'))
        self.assertEqual(subject.nome, 'Matéria existente')
        self.assertEqual(list(Presenca.objects.values_list('pk', 'registrada_em', 'valida')), original_history)
        self.assertEqual(list(Aula.objects.values_list('pk', 'data')), original_dates)
        self.assertIn('Nenhuma conta nova', output)
        self.assertNotIn('NaoDeveTrocar!', output)

    def test_collision_rolls_back_entire_demo_instead_of_reusing_real_account(self):
        User = get_user_model()
        existing = User.objects.create_user(username='Beatriz Souza', email='beatriz@example.test', role='aluno')
        institution_count = Instituicao.objects.count()
        with self.assertRaisesMessage(CommandError, 'já está em uso fora da demonstração'):
            self.seed()
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Instituicao.objects.count(), institution_count)
        self.assertEqual(Materia.objects.count(), 0)
        existing.refresh_from_db()
        self.assertEqual(existing.email, 'beatriz@example.test')
