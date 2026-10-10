"""Verificação opcional no Chrome; comando de execução em docs/PERFIL_E_LOGIN.md.

Usa banco isolado de testes e diretório temporário para fotos, sem alterar dados reais.
"""
import importlib.util
import tempfile
from contextlib import ExitStack
from io import BytesIO
from unittest import skipUnless
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connections
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.test.runner import DiscoverRunner
from PIL import Image, ImageDraw


class BrowserTestRunner(DiscoverRunner):
    """SQLite em arquivo: requisições concorrentes não compartilham conexão em memória."""
    def setup_databases(self, **kwargs):
        self.directory = tempfile.TemporaryDirectory(prefix='aura-browser-')
        self.test_options = connections['default'].settings_dict['TEST']
        self.previous_name = self.test_options.get('NAME')
        self.test_options['NAME'] = self.directory.name + '/test.sqlite3'
        try:
            return super().setup_databases(**kwargs)
        except Exception:
            self.test_options['NAME'] = self.previous_name
            self.directory.cleanup()
            raise

    def teardown_databases(self, old_config, **kwargs):
        try:
            super().teardown_databases(old_config, **kwargs)
        finally:
            self.test_options['NAME'] = self.previous_name
            self.directory.cleanup()


@skipUnless(importlib.util.find_spec('playwright'), 'Instale playwright para executar os testes de navegador.')
@override_settings(SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ProfileBrowserTests(StaticLiveServerTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        temporary = override_settings(MEDIA_ROOT=directory.name)
        temporary.enable()
        self.addCleanup(temporary.disable)
        self.artifacts = settings.BASE_DIR.parent / 'output' / 'profile-checks'
        self.artifacts.mkdir(parents=True, exist_ok=True)

    def test_register_login_photo_preview_save_replace_remove_and_mobile(self):
        from playwright.sync_api import sync_playwright, expect
        output = BytesIO()
        Image.new('RGB', (800, 600), '#007d68').save(output, format='PNG')
        errors = []
        with sync_playwright() as playwright, ExitStack() as stack:
            browser = playwright.chromium.launch(channel='chrome', headless=True)
            stack.callback(browser.close)
            page = browser.new_page(viewport={'width': 1366, 'height': 1000})
            page.on('response', self.log_http_error)
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(self.live_server_url + '/register.html')
            page.locator('#username').fill('Pessoa de Teste')
            page.locator('#email').fill('conta@example.com')
            page.locator('#password').fill('Senha123!')
            page.locator('#password2').fill('Senha123!')
            page.locator('#matricula').fill('123')
            page.locator('#register-form button[type=submit]').click()
            page.wait_for_url('**/login.html')
            page.locator('#username').fill('Pessoa de Teste')
            page.locator('#password').fill('Senha123!')
            page.locator('#login-form button[type=submit]').click()
            page.wait_for_url('**/aluno.html')
            page.locator('.account-link').click()
            expect(page.locator('#profile-form')).to_be_visible()
            page.locator('#profile-photo').set_input_files({'name': 'foto.png', 'mimeType': 'image/png', 'buffer': output.getvalue()})
            expect(page.locator('#profile-feedback')).to_contain_text('Prévia')
            expect(page.locator('#profile-avatar img')).to_have_attribute('src', __import__('re').compile('^blob:'))
            page.locator('#profile-name').fill('Pessoa Teste')
            page.locator('#profile-form button[type=submit]').click()
            expect(page.locator('#profile-feedback')).to_have_text('Perfil atualizado.')
            expect(page.locator('#user-name')).to_have_text('Pessoa Teste')
            expect(page.locator('#user-avatar img')).to_be_visible()
            source = page.locator('#user-avatar img').get_attribute('src')
            page.screenshot(path=str(self.artifacts / 'perfil-desktop.png'), full_page=True)
            page.reload()
            expect(page.locator('#user-avatar img')).to_have_attribute('src', source)
            page.locator('#profile-photo').set_input_files({'name': 'nova.png', 'mimeType': 'image/png', 'buffer': output.getvalue()})
            page.locator('#profile-form button[type=submit]').click()
            expect(page.locator('#profile-feedback')).to_have_text('Perfil atualizado.')
            self.assertNotEqual(page.locator('#user-avatar img').get_attribute('src'), source)
            page.set_viewport_size({'width': 390, 'height': 844})
            page.screenshot(path=str(self.artifacts / 'perfil-mobile.png'), full_page=True)
            self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
            page.locator('#profile-photo-remove').click()
            expect(page.locator('#profile-feedback')).to_have_text('Foto removida.')
            expect(page.locator('#user-avatar img')).to_have_count(0)
            page.locator('[data-logout]:visible').click()
            page.wait_for_url('**/login.html')
            page.screenshot(path=str(self.artifacts / 'login-mobile.png'), full_page=True)
            page.locator('#username').fill('CONTA@EXAMPLE.COM')
            page.locator('#password').fill('Senha123!')
            page.locator('#login-form button[type=submit]').click()
            page.wait_for_url('**/aluno.html')
            self.assertEqual(errors, [])

    def test_login_error_shows_only_reason_and_neutral_placeholder(self):
        from playwright.sync_api import sync_playwright, expect
        with sync_playwright() as playwright, ExitStack() as stack:
            browser = playwright.chromium.launch(channel='chrome', headless=True)
            stack.callback(browser.close)
            page = browser.new_page()
            for width, height in ((1366, 1000), (390, 844)):
                page.set_viewport_size({'width': width, 'height': height})
                page.goto(self.live_server_url + '/login.html')
                expect(page.locator('#username')).to_have_attribute('placeholder', 'Digite seu usuário ou e-mail')
                expect(page.locator('.google-button')).to_have_count(0)
                page.locator('#username').fill('conta inexistente')
                page.locator('#password').fill('senha incorreta')
                page.locator('#login-form button[type=submit]').click()
                expect(page.locator('#error-message')).to_have_text('Impossível fazer login com as credenciais fornecidas.')
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
                page.screenshot(path=str(self.artifacts / f'login-error-{width}.png'), full_page=True)

    def test_photo_crop_drag_zoom_keyboard_cancel_persistence_and_touch(self):
        from playwright.sync_api import sync_playwright, expect
        get_user_model().objects.create_user(username='Conta de teste', password='Senha123!', role='aluno')
        image = Image.new('RGB', (600, 900), '#e7eff2')
        drawing = ImageDraw.Draw(image)
        drawing.rectangle((0, 0, 600, 400), fill='#153e56')
        drawing.ellipse((350, 620, 490, 760), fill='#e66926')
        output = BytesIO()
        image.save(output, format='PNG')
        with sync_playwright() as playwright, ExitStack() as stack:
            browser = playwright.chromium.launch(channel='chrome', headless=True)
            stack.callback(browser.close)
            for width, height, touch in ((1366, 1100, False), (390, 844, True)):
                page = browser.new_page(viewport={'width': width, 'height': height}, has_touch=touch, is_mobile=touch)
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(self.live_server_url + '/login.html')
                page.locator('#username').fill('Conta de teste')
                page.locator('#password').fill('Senha123!')
                page.locator('#login-form button[type=submit]').click()
                page.wait_for_url('**/aluno.html')
                page.locator('.account-link').click()
                expect(page.locator('#profile-form')).to_be_visible()
                page.locator('#profile-photo').set_input_files({'name': 'portrait.png', 'mimeType': 'image/png', 'buffer': output.getvalue()})
                stage = page.locator('#profile-crop-stage')
                expect(stage).to_be_visible()
                page.wait_for_function("document.querySelector('#profile-crop-stage img')?.naturalWidth > 0")
                page.locator('#profile-photo-zoom').evaluate("input => { input.value = '2'; input.dispatchEvent(new Event('input', {bubbles: true})); }")
                expect(page.locator('#profile-zoom-value')).to_have_text('200%')
                stage.scroll_into_view_if_needed()
                rect = stage.bounding_box()
                size = stage.evaluate('node => node.clientWidth')
                start_x, start_y = rect['x'] + rect['width'] / 2, rect['y'] + rect['height'] / 2
                end_x, end_y = start_x - size * 0.4, start_y - size * 0.8
                if touch:
                    cdp = page.context.new_cdp_session(page)
                    cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': start_x, 'y': start_y}]})
                    for step in range(1, 6):
                        cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': start_x + (end_x - start_x) * step / 5, 'y': start_y + (end_y - start_y) * step / 5}]})
                    cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
                    cdp.detach()
                else:
                    page.mouse.move(start_x, start_y)
                    page.mouse.down()
                    page.mouse.move(end_x, end_y, steps=8)
                    page.mouse.up()
                # O ponto fora do centro deve aparecer no centro do círculo após arrastar.
                capture = Image.open(BytesIO(stage.screenshot()))
                center = capture.convert('RGB').getpixel((capture.width // 2, capture.height // 2))
                self.assertLess(sum(abs(a - b) for a, b in zip(center, (230, 105, 38))), 25)
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
                page.screenshot(path=str(self.artifacts / f'photo-crop-{width}.png'), full_page=True)
                page.locator('#profile-form button[type=submit]').click()
                expect(page.locator('#profile-feedback')).to_have_text('Perfil atualizado.')
                saved = page.request.get(self.live_server_url + '/api/interface/perfil/').json()
                self.assertAlmostEqual(saved['foto_posicao_x'], 90, delta=1)
                self.assertAlmostEqual(saved['foto_posicao_y'], 90, delta=1)
                self.assertEqual(saved['foto_zoom'], 2)
                page.reload()
                expect(page.locator('#user-avatar img')).to_be_visible()
                self.assertEqual(page.locator('#user-avatar img').evaluate('node => getComputedStyle(node).transform'), 'matrix(2, 0, 0, 2, 0, 0)')
                header_capture = Image.open(BytesIO(page.locator('#user-avatar').screenshot()))
                center = header_capture.convert('RGB').getpixel((header_capture.width // 2, header_capture.height // 2))
                header_geometry = page.locator('#user-avatar img').evaluate("node => ({width: node.clientWidth, height: node.clientHeight, position: getComputedStyle(node).objectPosition, origin: getComputedStyle(node).transformOrigin, natural: [node.naturalWidth, node.naturalHeight]})")
                self.assertLess(sum(abs(a - b) for a, b in zip(center, (230, 105, 38))), 35, (center, header_geometry))
                page.locator('#profile-photo-adjust').click()
                stage.focus()
                before = stage.evaluate("node => node.style.getPropertyValue('--photo-x')")
                stage.press('ArrowLeft')
                self.assertNotEqual(stage.evaluate("node => node.style.getPropertyValue('--photo-x')"), before)
                page.locator('#profile-cancel').click()
                page.locator('#profile-photo-adjust').click()
                self.assertEqual(stage.evaluate("node => node.style.getPropertyValue('--photo-x')"), before)
                page.locator('#profile-crop-reset').click()
                expect(page.locator('#profile-photo-zoom')).to_have_value('1')
                # Reenquadrar a foto salva não exige novo arquivo.
                page.locator('#profile-form button[type=submit]').click()
                expect(page.locator('#profile-feedback')).to_have_text('Perfil atualizado.')
                reset = page.request.get(self.live_server_url + '/api/interface/perfil/').json()
                self.assertEqual(reset['foto_url'], saved['foto_url'])
                self.assertEqual((reset['foto_posicao_x'], reset['foto_posicao_y'], reset['foto_zoom']), (50, 50, 1))
                self.assertEqual(errors, [])
                page.close()

    @staticmethod
    def log_http_error(response):
        if response.status >= 400:
            print('HTTP error:', response.status, urlsplit(response.url).path, response.text()[:900])
