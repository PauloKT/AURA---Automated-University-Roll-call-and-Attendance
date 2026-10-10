"""Regressões de cadastro, login por senha e fotos privadas."""
import tempfile
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import override_settings
from PIL import Image
from rest_framework.test import APIClient, APITestCase


User = get_user_model()
FAST_PASSWORDS = ['django.contrib.auth.hashers.MD5PasswordHasher']


@override_settings(PASSWORD_HASHERS=FAST_PASSWORDS)
class AccountIdentityTests(APITestCase):
    def payload(self, **extra):
        return {'username': 'Pessoa de Teste', 'email': 'conta@example.com', 'role': 'aluno',
                'matricula': '123', 'password': 'Senha123!', 'password2': 'Senha123!', **extra}

    def test_register_spaces_and_login_by_username_or_case_insensitive_email(self):
        created = self.client.post('/api/register/', self.payload(), format='json')
        self.assertEqual(created.status_code, 201, created.data)
        for identifier in ('Pessoa de Teste', 'CONTA@EXAMPLE.COM'):
            with self.subTest(identifier=identifier):
                self.client.logout()
                result = self.client.post('/api/auth/login/', {'username': identifier, 'password': 'Senha123!'})
                self.assertEqual(result.status_code, 200, result.data)
                self.assertEqual(self.client.get('/api/interface/perfil/').data['username'], 'Pessoa de Teste')

    def test_spaces_supported_in_jwt_login_too(self):
        self.client.post('/api/register/', self.payload(), format='json')
        response = self.client.post('/api/login/', {'username': 'Pessoa de Teste', 'password': 'Senha123!'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)

    def test_duplicate_email_case_insensitive_and_identifier_collision_rejected(self):
        User.objects.create_user(username='Existente', email='conta@example.com')
        for payload in (self.payload(email='CONTA@EXAMPLE.COM'), self.payload(username='conta@example.com', email='outro@example.com')):
            with self.subTest(payload=payload):
                response = self.client.post('/api/register/', payload, format='json')
                self.assertEqual(response.status_code, 400)
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(username='outro', email='CONTA@example.com')

    def test_tabs_linebreaks_and_html_in_username_rejected(self):
        for username in ('Pessoa\tTeste', 'Pessoa\nTeste', '<b>Pessoa</b>', '  '):
            with self.subTest(username=username):
                response = self.client.post('/api/register/', self.payload(username=username), format='json')
                self.assertEqual(response.status_code, 400)

    def test_ambiguous_legacy_identifier_fails_closed(self):
        User.objects.create_user(username='conta@example.com', password='Senha123!', role='aluno')
        User.objects.create_user(username='Pessoa', email='conta@example.com', password='Senha123!', role='aluno')
        response = self.client.post('/api/auth/login/', {'username': 'conta@example.com', 'password': 'Senha123!'})
        self.assertEqual(response.status_code, 400)


@override_settings(PASSWORD_HASHERS=FAST_PASSWORDS)
class ProfilePhotoTests(APITestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        settings = override_settings(MEDIA_ROOT=directory.name)
        settings.enable()
        self.addCleanup(settings.disable)
        self.user = User.objects.create_user(username='Pessoa Teste', role='aluno', password='Senha123!')
        self.client.force_login(self.user)

    def photo(self, color='red', fmt='PNG'):
        output = BytesIO()
        Image.new('RGB', (900, 600), color).save(output, format=fmt)
        return SimpleUploadedFile('foto.' + fmt.lower(), output.getvalue(), content_type='image/' + fmt.lower())

    def upload(self, **extra):
        return self.client.patch('/api/interface/perfil/', {'foto': self.photo(), **extra}, format='multipart')

    def test_upload_resize_name_and_private_image(self):
        result = self.upload(nome='Pessoa de Teste Completo', role='professor', username='changed')
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data['nome'], 'Pessoa de Teste Completo')
        self.assertEqual(result.data['username'], 'Pessoa Teste')
        self.assertEqual(result.data['role'], 'aluno')
        response = self.client.get(result.data['foto_url'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        with Image.open(BytesIO(b''.join(response.streaming_content))) as image:
            self.assertEqual(image.format, 'WEBP')
            self.assertLessEqual(max(image.size), 512)
            self.assertFalse(image.getexif())
        self.client.logout()
        self.assertEqual(self.client.get(result.data['foto_url']).status_code, 401)

    def test_url_never_exposes_another_users_photo_or_media_path(self):
        result = self.upload()
        self.user.refresh_from_db()
        self.assertEqual(self.client.get('/media/' + self.user.foto.name).status_code, 404)
        other = User.objects.create_user(username='Outra pessoa', role='aluno')
        self.client.force_login(other)
        self.assertEqual(self.client.get(result.data['foto_url']).status_code, 404)

    def test_replacing_and_removing_photo_deletes_old_file(self):
        self.upload()
        self.user.refresh_from_db()
        old_name, storage = self.user.foto.name, self.user.foto.storage
        with self.captureOnCommitCallbacks(execute=True):
            result = self.upload()
        self.assertEqual(result.status_code, 200)
        self.assertFalse(storage.exists(old_name))
        self.user.refresh_from_db()
        current_name = self.user.foto.name
        with self.captureOnCommitCallbacks(execute=True):
            removed = self.client.delete('/api/interface/perfil/foto/')
        self.assertIsNone(removed.data['foto_url'])
        self.assertFalse(storage.exists(current_name))
        self.assertEqual(self.client.get('/api/interface/perfil/foto/').status_code, 404)

    def test_invalid_format_size_and_pixels_rejected(self):
        files = [SimpleUploadedFile('bad.png', b'not an image', content_type='image/png'),
                 SimpleUploadedFile('evil.svg', b'<svg onload="alert(1)"/>', content_type='image/svg+xml'),
                 SimpleUploadedFile('large.png', b'x' * (5 * 1024 * 1024 + 1), content_type='image/png'),
                 self.photo(fmt='GIF')]
        for photo in files:
            with self.subTest(file=photo.name):
                response = self.client.patch('/api/interface/perfil/', {'foto': photo}, format='multipart')
                self.assertEqual(response.status_code, 400, response.data)
        with patch('accounts.profile.MAX_PHOTO_PIXELS', 10):
            self.assertEqual(self.upload().status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.foto)

    def test_photo_and_name_updates_require_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.patch('/api/interface/perfil/', {'nome': 'Outra pessoa'}).status_code, 403)
        self.assertEqual(client.delete('/api/interface/perfil/foto/').status_code, 403)

    def test_crop_is_saved_with_photo_and_can_be_changed_without_reupload(self):
        result = self.upload(foto_posicao_x=90, foto_posicao_y=80, foto_zoom=2)
        self.assertEqual(result.status_code, 200, result.data)
        self.user.refresh_from_db()
        original_name = self.user.foto.name
        response = self.client.patch('/api/interface/perfil/', {
            'foto_posicao_x': 25, 'foto_posicao_y': 100, 'foto_zoom': 1.5,
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.foto.name, original_name)
        data = self.client.get('/api/interface/perfil/').data
        self.assertEqual((data['foto_posicao_x'], data['foto_posicao_y'], data['foto_zoom']), (25, 100, 1.5))
        # A imagem completa continua disponível para reajustar o recorte depois.
        with self.user.foto.open('rb') as original, Image.open(original) as image:
            self.assertGreater(image.width, image.height)

    def test_crop_limits_and_nonfinite_values_are_rejected_without_changing_saved_photo(self):
        self.upload()
        self.user.refresh_from_db()
        original_name = self.user.foto.name
        cases = [
            {'foto_posicao_x': -1}, {'foto_posicao_y': 101}, {'foto_zoom': 0.5},
            {'foto_zoom': 3.1}, {'foto_zoom': 'NaN'}, {'foto_posicao_x': 'Infinity'},
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                response = self.client.patch('/api/interface/perfil/', payload, format='multipart')
                self.assertEqual(response.status_code, 400, response.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.foto.name, original_name)
        self.assertEqual((self.user.foto_posicao_x, self.user.foto_posicao_y, self.user.foto_zoom), (50, 50, 1))

    def test_new_photo_and_removal_reset_previous_crop(self):
        self.upload(foto_posicao_x=5, foto_posicao_y=95, foto_zoom=3)
        response = self.upload()
        self.assertEqual((response.data['foto_posicao_x'], response.data['foto_posicao_y'], response.data['foto_zoom']), (50, 50, 1))
        self.client.patch('/api/interface/perfil/', {'foto_zoom': 2}, format='json')
        response = self.client.delete('/api/interface/perfil/foto/')
        self.assertEqual((response.data['foto_posicao_x'], response.data['foto_posicao_y'], response.data['foto_zoom']), (50, 50, 1))

    def test_crop_requires_a_photo_and_is_scoped_to_logged_in_user(self):
        response = self.client.patch('/api/interface/perfil/', {'foto_zoom': 2}, format='json')
        self.assertEqual(response.status_code, 400)
        self.upload()
        other = User.objects.create_user(username='Outra conta', role='professor')
        self.client.patch('/api/interface/perfil/', {'id': other.pk, 'foto_zoom': 2}, format='json')
        other.refresh_from_db()
        self.assertEqual(other.foto_zoom, 1)
        self.client.logout()
        self.assertEqual(self.client.patch('/api/interface/perfil/', {'foto_zoom': 2}, format='json').status_code, 401)


class PasswordOnlyLoginTests(APITestCase):
    def test_removed_google_routes_are_unavailable(self):
        for action in ('start', 'callback', 'pending', 'complete'):
            with self.subTest(action=action):
                url = f'/api/auth/google/{action}/'
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(url, {}).status_code, 404)

    def test_auth_and_profile_templates_have_no_google_login(self):
        for page in ('/login.html', '/register.html', '/professor.html', '/aluno.html'):
            with self.subTest(page=page):
                response = self.client.get(page)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, '/api/auth/google/')
                self.assertNotContains(response, 'google-button')
                self.assertNotContains(response, 'Ex.: Pessoa Teste')
        self.assertContains(self.client.get('/login.html'), 'placeholder="Digite seu usuário ou e-mail"')
