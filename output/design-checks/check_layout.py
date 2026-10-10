"""Capturas e checagens no servidor de dados fictícios."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = 'http://127.0.0.1:8766'
OUT = Path(__file__).resolve().parent
failures = []
errors = []

def capture(page, name, width):
    page.evaluate('document.fonts.ready')
    overflow = page.evaluate('''() => [...document.querySelectorAll('body *')].filter(el => {
      const r = el.getBoundingClientRect();
      return r.width && (r.right > innerWidth + 1 || r.left < -1) &&
        getComputedStyle(el).position !== 'absolute' &&
        !el.closest('.table-wrap, .tabs, .sr-only');
    }).map(el => `${el.tagName}.${el.className}#${el.id}`).slice(0, 8)''')
    if page.evaluate('document.documentElement.scrollWidth > innerWidth + 1'):
        failures.append(f'{name}-{width}: overflow {overflow}')
    page.screenshot(path=str(OUT / f'after-{name}-{width}.png'), full_page=True)

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    for width in [320, 390, 768, 1366]:
        context = browser.new_context(viewport={'width': width, 'height': 844 if width < 700 else 1000}, has_touch=width < 700, reduced_motion='reduce')
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(BASE + '/login.html')
        capture(page, 'login', width)
        page.goto(BASE + '/register.html')
        capture(page, 'register', width)
        page.locator('#role').select_option('professor')
        page.locator('#new-institution-toggle').click()
        capture(page, 'register-professor', width)
        for user, role, panels in [
            ('Aluno Teste', 'aluno', ['inicio', 'turmas', 'frequencia', 'entrar', 'perfil']),
            ('Docente Teste', 'professor', ['inicio', 'materias', 'turmas', 'relatorios', 'chamada', 'perfil']),
        ]:
            page.goto(BASE + '/login.html')
            page.locator('#username').fill(user)
            page.locator('#password').fill('Teste123!')
            page.locator('button[type=submit]').click()
            page.wait_for_url(f'**/{role}.html')
            expect(page.locator('#content')).to_be_visible()
            expect(page.locator('.stat').first).to_be_visible()
            for panel in panels:
                page.evaluate('(panel) => location.hash = panel', panel)
                expect(page.locator(f'[data-panel="{panel}"]')).to_be_visible()
                capture(page, f'{role}-{panel}', width)
                if panel in ['frequencia', 'relatorios'] and width < 700:
                    expect(page.locator('.responsive-table:visible')).to_be_visible()
                    wrapper = page.locator('.report-wrap:visible').first
                    if not wrapper.evaluate('(el) => el.scrollWidth <= el.clientWidth + 1'):
                        failures.append(f'{role}-{panel}-{width}: relatório com rolagem lateral')
            page.locator('.workspace-navigation [data-nav="turmas"]').click()
            expect(page.locator('[data-panel="turmas"]')).to_be_visible()
            if role == 'professor':
                page.locator('#group-list a').first.click()
                expect(page.locator('#group-detail-body .stats')).to_be_visible()
                capture(page, 'professor-detalhe', width)
                for tab in ['alunos', 'aulas', 'frequencia']:
                    page.locator(f'#tab-{tab}').click()
                    capture(page, 'professor-detalhe-' + tab, width)
                page.locator('.workspace-navigation [data-nav="materias"]').click()
                page.locator('[data-panel="materias"] [data-new="materia"]').first.click()
                expect(page.locator('#materia-dialog')).to_be_visible()
                capture(page, 'professor-dialog', width)
                page.keyboard.press('Escape')
            page.locator('#menu-toggle').click()
            expect(page.locator('#navigation-menu')).to_be_visible()
            capture(page, f'{role}-menu', width)
            page.locator('#logout-btn').click()
            page.wait_for_url('**/login.html')
        context.close()
    browser.close()
print('Erros JS:', errors)
print('Problemas de layout:', failures)
assert not errors and not failures
