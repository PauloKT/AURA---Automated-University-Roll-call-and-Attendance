"""Regressões de navegação e layout. Usa o BrowserTestRunner com banco isolado.

python backend/manage.py test accounts.browser_layout --testrunner accounts.browser_profiles.BrowserTestRunner
"""
import importlib.util
from datetime import date, time
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.utils import timezone

from attendance.models import SessaoChamada, Presenca
from courses.models import Materia, Turma, TurmaAluno, Aula


@skipUnless(importlib.util.find_spec('playwright'), 'Instale playwright para os testes no navegador.')
@override_settings(SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ResponsiveLayoutTests(StaticLiveServerTestCase):
    def setUp(self):
        User = get_user_model()
        self.teacher = User.objects.create_user(username='Docente Teste', password='Teste123!', role='professor')
        self.student = User.objects.create_user(username='Estudante de Teste com Nome Comprido', password='Teste123!', role='aluno', matricula='202600001')
        subject = Materia.objects.create(nome='Desenvolvimento de Aplicações e Arquitetura de Sistemas Distribuídos', codigo='TADS-TESTE', carga_horaria=60, professor=self.teacher)
        self.group = Turma.objects.create(nome='Análise e Desenvolvimento de Sistemas — turma do período noturno', materia=subject, semestre='2º semestre', ano=2026)
        TurmaAluno.objects.create(turma=self.group, aluno=self.student)
        lesson = Aula.objects.create(turma=self.group, titulo='Revisão e prática em laboratório', data=date.today(), horario_inicio=time(19), horario_fim=time(21))
        session = SessaoChamada.objects.create(aula=lesson, ativa=False, encerrada_em=timezone.now(), professor_latitude=-20, professor_longitude=-54)
        Presenca.objects.create(sessao=session, aluno=self.student, latitude=-20, longitude=-54)

    def login(self, page, username, role):
        page.goto(self.live_server_url + '/login.html')
        page.locator('#username').fill(username)
        page.locator('#password').fill('Teste123!')
        page.locator('button[type=submit]').click()
        page.wait_for_url(f'**/{role}.html')
        page.locator('#content').wait_for(state='visible')
        page.locator('.stat').first.wait_for()

    def assert_fits(self, page):
        self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'))

    def test_navigation_reports_long_names_and_keyboard_at_phone_tablet_desktop(self):
        from playwright.sync_api import sync_playwright, expect
        errors = []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='chrome', headless=True)
            for width in [320, 390, 768, 1366]:
                for role, user, report in [('aluno', self.student, 'frequencia'), ('professor', self.teacher, 'relatorios')]:
                    with self.subTest(width=width, role=role):
                        context = browser.new_context(viewport={'width': width, 'height': 844}, has_touch=width < 700)
                        page = context.new_page()
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        self.login(page, user.username, role)
                        self.assert_fits(page)
                        nav = page.locator('.workspace-navigation')
                        expect(nav).to_be_visible()
                        for link in nav.locator('a').all():
                            self.assertGreaterEqual(link.bounding_box()['height'], 44)
                        nav.locator(f'[data-nav="{report}"]').click()
                        expect(nav.locator(f'[data-nav="{report}"]')).to_have_attribute('aria-current', 'page')
                        expect(page.locator(f'[data-panel="{report}"]')).to_be_visible()
                        expect(page.locator('.responsive-table:visible tbody tr')).to_have_count(1)
                        expect(page.locator('.responsive-table:visible')).to_contain_text('100%')
                        self.assertTrue(page.locator('.report-wrap:visible').evaluate('(el) => el.scrollWidth <= el.clientWidth + 1'))
                        self.assert_fits(page)
                        page.reload()
                        expect(nav.locator(f'[data-nav="{report}"]')).to_have_attribute('aria-current', 'page')
                        expect(page.locator('.responsive-table:visible tbody tr')).to_have_count(1)
                        nav.locator('[data-nav="turmas"]').focus()
                        page.keyboard.press('Enter')
                        expect(page.locator('[data-panel="turmas"]')).to_be_visible()
                        expect(page.locator('[data-panel="turmas"] h1')).to_be_focused()
                        self.assert_fits(page)
                        if role == 'professor':
                            page.locator('#group-list a').first.click()
                            page.locator('#tab-alunos').click()
                            expect(page.locator('.roster-table')).to_contain_text(self.student.username)
                            self.assert_fits(page)
                        expect(page.locator('#menu-toggle, #navigation-menu')).to_have_count(0)
                        expect(page.locator('[data-logout]:visible')).to_have_count(1)
                        if width < 700:
                            expect(page.locator('.topbar [data-logout]')).to_be_visible()
                            expect(nav.locator('[data-logout]')).to_be_hidden()
                        else:
                            expect(nav.locator('[data-logout]')).to_be_visible()
                            widths = [link.bounding_box()['width'] for link in nav.locator('a').all()]
                            self.assertLess(max(widths) - min(widths), 1)
                        context.close()
            browser.close()
        self.assertEqual(errors, [])

    def test_mobile_join_create_subject_and_short_viewport_form(self):
        from playwright.sync_api import sync_playwright, expect
        another = Turma.objects.create(nome='Nova turma', materia=self.group.materia, semestre='2º', ano=2026)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='chrome', headless=True)
            page = browser.new_page(viewport={'width': 390, 'height': 844}, has_touch=True)
            self.login(page, self.student.username, 'aluno')
            page.locator('.workspace-navigation [data-nav="entrar"]').click()
            page.locator('#invite-code').fill(another.codigo_acesso)
            self.assertGreaterEqual(float(page.locator('#invite-code').evaluate('(el) => parseFloat(getComputedStyle(el).fontSize)')), 16)
            page.locator('#join-btn').click()
            expect(page.locator('#join-message')).to_have_class('success show')
            page.locator('.workspace-navigation [data-nav="turmas"]').click()
            expect(page.locator('#turmas-list .turma-card')).to_have_count(2)
            page.locator('[data-logout]:visible').click()
            page.wait_for_url('**/login.html')
            self.login(page, self.teacher.username, 'professor')
            page.locator('.workspace-navigation [data-nav="materias"]').click()
            page.locator('[data-panel="materias"] [data-new="materia"]').click()
            expect(page.locator('#materia-dialog')).to_be_visible()
            page.set_viewport_size({'width': 390, 'height': 400})
            page.locator('#materia-nome').fill('Interfaces para dispositivos móveis')
            page.locator('#materia-codigo').fill('MOBILE-01')
            page.locator('#materia-carga').fill('60')
            page.locator('#create-materia-btn').scroll_into_view_if_needed()
            expect(page.locator('#create-materia-btn')).to_be_in_viewport()
            self.assert_fits(page)
            page.locator('#create-materia-btn').click()
            expect(page.locator('#materia-dialog')).to_be_hidden()
            expect(page.locator('#subject-list')).to_contain_text('Interfaces para dispositivos móveis')
            browser.close()

    def test_logout_failure_can_retry_and_success_ends_session_on_mobile_and_desktop(self):
        from playwright.sync_api import sync_playwright, expect
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='chrome', headless=True)
            for width in [390, 1366]:
                with self.subTest(width=width):
                    context = browser.new_context(viewport={'width': width, 'height': 844})
                    page = context.new_page()
                    self.login(page, self.student.username, 'aluno')
                    page.locator('.account-link').click()
                    expect(page.locator('#profile-form')).to_be_visible()
                    page.route('**/api/auth/logout/', lambda route: route.fulfill(status=503, json={'detail': 'Não foi possível sair. Tente novamente.'}))
                    logout = page.locator('[data-logout]:visible')
                    logout.click()
                    expect(page.locator('.toast[data-kind="error"]')).to_contain_text('Tente novamente')
                    expect(logout).to_be_enabled()
                    self.assertEqual(context.request.get(self.live_server_url + '/api/interface/perfil/').status, 200)
                    page.unroute('**/api/auth/logout/')
                    logout.focus()
                    page.keyboard.press('Enter')
                    page.wait_for_url('**/login.html')
                    self.assertEqual(context.request.get(self.live_server_url + '/api/interface/perfil/').status, 401)
                    context.close()
            browser.close()
