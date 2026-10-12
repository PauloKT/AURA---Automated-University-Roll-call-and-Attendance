"""Frequência encerrada, cadastro, catálogo e autenticação do navegador."""
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from attendance.models import Presenca, SessaoChamada
from courses.models import Aula, Instituicao, Materia, Turma, TurmaAluno


class FixtureMixin:
    @classmethod
    def setUpTestData(cls):
        user = get_user_model()
        cls.aluno = user.objects.create_user(username='aluno', password='Senha-segura-123', role='aluno', matricula='123')
        cls.professor = user.objects.create_user(username='professor', role='professor')
        cls.instituicao = Instituicao.objects.create(
            nome='Campus', logradouro='Rua Teste', numero='1', bairro='Centro',
            cidade='Três Lagoas', estado='MS', latitude=-20.78, longitude=-51.66,
        )
        materia = Materia.objects.create(nome='Matéria', codigo='TST', carga_horaria=40, professor=cls.professor)
        cls.turma = Turma.objects.create(nome='Turma', materia=materia, semestre='2', ano=2026)
        TurmaAluno.objects.create(turma=cls.turma, aluno=cls.aluno)
        cls.aula = Aula.objects.create(turma=cls.turma, titulo='Aula', data='2026-10-01', horario_inicio='19:00', horario_fim='20:00')

    def session(self, *, active, attended):
        session = SessaoChamada.objects.create(
            aula=self.aula, ativa=active, professor_latitude=-20.78, professor_longitude=-51.66,
        )
        if attended:
            Presenca.objects.create(sessao=session, aluno=self.aluno, latitude=-20.78, longitude=-51.66)
        return session


class FrequencyTests(FixtureMixin, APITestCase):
    def assert_frequency(self, percentage, total, attended, situation):
        self.client.force_authenticate(self.aluno)
        single = self.client.get('/api/aluno/minha-frequencia/', {'turma': self.turma.pk})
        self.assertEqual(single.status_code, 200)
        self.assertEqual(single.data, {'percentual': percentage, 'situacao': situation})
        group = self.client.get('/api/aluno/turmas/').data['turmas'][0]
        self.assertEqual((group['percentual'], group['presencas'], group['faltas']), (percentage, attended, total - attended))
        for user in (self.aluno, self.professor):
            with self.subTest(role=user.role):
                self.client.force_authenticate(user)
                dashboard = self.client.get('/api/interface/painel/').data
                row = dashboard['frequencias'][0]
                self.assertEqual((row['aulas'], row['presencas'], row['faltas'], row['percentual'], row['situacao']),
                                 (total, attended, total - attended, percentage, situation))
                self.assertEqual(dashboard['turmas'][0]['chamadas'], total)

    def test_open_sessions_and_their_presences_do_not_change_frequency(self):
        self.session(active=False, attended=True)
        self.session(active=False, attended=False)
        self.session(active=True, attended=True)
        self.session(active=True, attended=False)
        self.assert_frequency(50.0, 2, 1, 'reprovado')

    def test_only_open_sessions_have_no_frequency_even_with_presence(self):
        self.session(active=True, attended=True)
        self.assert_frequency(0.0, 0, 0, 'sem_dados')

    def test_closing_session_updates_all_reports(self):
        self.session(active=False, attended=True)
        opened = self.session(active=True, attended=False)
        self.assert_frequency(100.0, 1, 1, 'aprovado')
        self.client.force_authenticate(self.professor)
        self.assertEqual(self.client.post(f'/api/sessoes/{opened.pk}/encerrar/').status_code, 200)
        self.assert_frequency(50.0, 2, 1, 'reprovado')


class RegistrationAndCatalogTests(FixtureMixin, APITestCase):
    def test_teacher_registration_uses_institution_without_network_lookup(self):
        payload = {'username': 'novo-professor', 'email': 'professor@faculdade.edu.br',
                   'role': 'professor', 'instituicoes': [self.instituicao.pk],
                   'password': 'Senha-segura-123', 'password2': 'Senha-segura-123'}
        with patch('requests.get') as request:
            result = self.client.post('/api/register/', payload, format='json')
        self.assertEqual(result.status_code, 201)
        request.assert_not_called()
        user = get_user_model().objects.get(username='novo-professor')
        self.assertTrue(user.check_password(payload['password']))
        self.assertEqual(user.instituicao_id, self.instituicao.pk)
        self.assertEqual(list(user.instituicoes.values_list('pk', flat=True)), [self.instituicao.pk])

    def test_saving_legacy_teacher_preserves_coordinates_without_network_lookup(self):
        self.professor.cep = '79600-000'
        for latitude, longitude in ((None, None), (-20.78, -51.66)):
            with self.subTest(latitude=latitude), patch('requests.get') as request, patch('threading.Thread.start') as start:
                self.professor.latitude = latitude
                self.professor.longitude = longitude
                self.professor.save()
                self.professor.refresh_from_db()
                self.assertEqual((self.professor.latitude, self.professor.longitude), (latitude, longitude))
                self.assertEqual(self.professor.cep, '79600-000')
                request.assert_not_called()
                start.assert_not_called()

    def test_institutional_email_is_accepted_and_invalid_email_rejected(self):
        payload = {'username': 'novo', 'email': 'aluno@faculdade.edu.br', 'role': 'aluno',
                   'matricula': '456', 'password': 'Senha-segura-123', 'password2': 'Senha-segura-123'}
        result = self.client.post('/api/register/', payload, format='json')
        self.assertEqual(result.status_code, 201)
        self.assertEqual(get_user_model().objects.get(username='novo').email, payload['email'])
        payload.update(username='invalido', email='sem-arroba')
        self.assertEqual(self.client.post('/api/register/', payload, format='json').status_code, 400)
        self.assertFalse(get_user_model().objects.filter(username='invalido').exists())

    def test_full_institution_data_requires_authentication(self):
        for path in ('/api/instituicoes/', f'/api/instituicoes/{self.instituicao.pk}/'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 401)
        self.client.force_authenticate(self.professor)
        result = self.client.get(f'/api/instituicoes/{self.instituicao.pk}/')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data['latitude'], -20.78)
        self.assertEqual(result.data['radius_meters'], 100)

    def test_public_catalog_exposes_only_registration_fields(self):
        result = self.client.get('/api/instituicoes/catalogo/')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.data), 2)  # Campus de teste e AEMS da migration.
        for item in result.data:
            self.assertEqual(set(item), {'id', 'nome', 'cidade', 'estado', 'localizacao_confirmada'})
        campus = next(item for item in result.data if item['id'] == self.instituicao.pk)
        self.assertTrue(campus['localizacao_confirmada'])
        self.instituicao.longitude = None
        self.instituicao.save(update_fields=['longitude'])
        result = self.client.get('/api/instituicoes/catalogo/')
        campus = next(item for item in result.data if item['id'] == self.instituicao.pk)
        self.assertFalse(campus['localizacao_confirmada'])

    def test_public_catalog_does_not_enable_admin_actions(self):
        self.client.force_authenticate(self.professor)
        result = self.client.post(f'/api/instituicoes/{self.instituicao.pk}/confirmar-localizacao/',
                                  {'latitude': 0, 'longitude': 0}, format='json')
        self.assertEqual(result.status_code, 403)


@override_settings(ALLOWED_HOSTS=['testserver'])
class BrowserAuthTests(FixtureMixin, APITestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        page = self.client.get('/login.html')
        self.assertEqual(page.status_code, 200)
        self.csrf = self.client.cookies['csrftoken'].value

    def login(self, **options):
        return self.client.post('/api/auth/login/', {'username': 'aluno', 'password': 'Senha-segura-123'},
                                format='json', HTTP_X_CSRFTOKEN=self.csrf, **options)

    def test_login_sets_httponly_session_without_exposing_tokens(self):
        result = self.login()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(set(result.data), {'user'})
        self.assertEqual(result['Cache-Control'], 'no-store')
        cookie = result.cookies[settings.SESSION_COOKIE_NAME]
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertEqual(cookie['max-age'], 86400)
        self.assertEqual(self.client.get('/api/interface/perfil/').status_code, 200)

    def test_login_requires_csrf_even_for_anonymous_user(self):
        result = self.client.post('/api/auth/login/', {'username': 'aluno', 'password': 'Senha-segura-123'}, format='json')
        self.assertEqual(result.status_code, 403)
        self.assertFalse(Session.objects.exists())

    def test_untrusted_origin_is_rejected_even_with_csrf_token(self):
        self.assertEqual(self.login(HTTP_ORIGIN='https://evil.test').status_code, 403)
        self.assertFalse(Session.objects.exists())

    def test_tunnel_origin_with_csrf_configuration_is_accepted(self):
        with self.settings(CSRF_TRUSTED_ORIGINS=['https://testserver'], SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True):
            result = self.login(HTTP_ORIGIN='https://testserver')
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.cookies[settings.SESSION_COOKIE_NAME]['secure'])
        self.assertTrue(result.cookies['csrftoken']['secure'])

    def test_login_rotates_csrf_and_mutations_require_the_new_token(self):
        self.login()
        new_csrf = self.client.cookies['csrftoken'].value
        self.assertNotEqual(new_csrf, self.csrf)
        path = '/api/aluno/entrar-turma/'
        payload = {'codigo_acesso': self.turma.codigo_acesso}
        self.assertEqual(self.client.post(path, payload, format='json').status_code, 403)
        self.assertEqual(self.client.post(path, payload, format='json', HTTP_X_CSRFTOKEN=self.csrf).status_code, 403)
        self.assertEqual(self.client.post(path, payload, format='json', HTTP_X_CSRFTOKEN=new_csrf).status_code, 200)

    def test_logout_revokes_the_server_session_and_requires_csrf(self):
        self.login()
        saved_cookie = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        self.assertEqual(self.client.post('/api/auth/logout/').status_code, 403)
        self.assertTrue(Session.objects.filter(session_key=saved_cookie).exists())
        result = self.client.post('/api/auth/logout/', HTTP_X_CSRFTOKEN=self.client.cookies['csrftoken'].value)
        self.assertEqual(result.status_code, 200)
        self.assertFalse(Session.objects.filter(session_key=saved_cookie).exists())
        self.client.cookies[settings.SESSION_COOKIE_NAME] = saved_cookie
        self.assertEqual(self.client.get('/api/interface/perfil/').status_code, 401)

    def test_expired_session_requires_new_login(self):
        self.login()
        Session.objects.update(expire_date=timezone.now() - timezone.timedelta(seconds=1))
        self.assertEqual(self.client.get('/api/interface/perfil/').status_code, 401)

    def test_invalid_credentials_do_not_create_session(self):
        result = self.client.post('/api/auth/login/', {'username': 'aluno', 'password': 'errada'},
                                  format='json', HTTP_X_CSRFTOKEN=self.csrf)
        self.assertEqual(result.status_code, 400)
        self.assertFalse(Session.objects.exists())

    def test_bearer_clients_keep_jwt_login_and_refresh(self):
        result = self.client.post('/api/login/', {'username': 'aluno', 'password': 'Senha-segura-123'}, format='json')
        self.assertEqual(result.status_code, 200)
        self.assertNotIn(settings.SESSION_COOKIE_NAME, result.cookies)
        refresh = self.client.post('/api/token/refresh/', {'refresh': result.data['refresh']}, format='json')
        self.assertEqual(refresh.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + refresh.data['access'])
        self.assertEqual(self.client.get('/api/interface/perfil/').status_code, 200)
        # JWT enviado explicitamente no header não depende do cookie CSRF.
        self.assertEqual(self.client.post('/api/aluno/entrar-turma/', {'codigo_acesso': self.turma.codigo_acesso}, format='json').status_code, 200)
