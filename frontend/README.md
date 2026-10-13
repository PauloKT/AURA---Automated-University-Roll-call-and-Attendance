# Frontend do AURA

A interface usa templates Django, CSS e JavaScript puro, sem compilação. Execute o projeto pelo Django conforme o [README principal](../README.md); os HTMLs não funcionam como arquivos abertos diretamente no navegador.

## Onde editar

- `templates/pages/`: páginas de login, cadastro, aluno, professor e confirmação de presença. As páginas dos painéis reúnem os includes de cada seção.
- `templates/layouts/base.html`: documento HTML, metadados, fonte, CSS e scripts compartilhados.
- `templates/layouts/auth_base.html`: estrutura visual de login e cadastro.
- `templates/layouts/app_base.html`: cabeçalho, navegação, conteúdo e rodapé dos painéis.
- `templates/includes/`: marca, ícones, navegação e perfil compartilhados.
- `templates/includes/aluno/`: início, turmas, frequência e entrada por código.
- `templates/includes/professor/`: início, matérias, turmas, detalhes, relatórios, chamada e formulários modais em `dialogs.html`.
- `static/css/app.css`: estilos, com índice de seções no início do arquivo.
- `static/js/`: comportamento das páginas e componentes. `api.js` centraliza as requisições; `ui.js` cuida da interface comum; `profile.js` cuida do perfil. `workspace.js` controla o painel do professor e `student-workspace.js` complementa o painel do aluno.
- `static/images/` e `static/fonts/`: imagens, ícones e fonte local com sua licença.
- `tests/`: testes JavaScript de autenticação e chamada.

## Convenções

Use dois espaços para indentar os HTMLs e mantenha cada seção em seu include. Componentes usados por mais de uma página ficam diretamente em `includes/`; componentes específicos ficam na pasta de aluno ou professor.

As páginas estendem um layout com `{% extends %}`. Use `{% include %}` para os componentes e `{% load static %}` nos arquivos que usam `{% static %}`. Caminhos de assets partem de `static/`, por exemplo `{% static 'js/aluno.js' %}` e `{% static 'images/brand.png' %}`. URLs dentro do CSS são relativas a `static/css/`, como `../fonts/manrope-latin-variable.woff2`.

Preserve os IDs e atributos `data-*` usados pelos scripts, assim como a ordem de carregamento: scripts compartilhados no layout base e scripts da página no bloco `scripts`. As rotas públicas continuam em `backend/backend/urls.py`, independentemente da organização dos arquivos HTML.

## Verificar alterações

Na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe backend/manage.py check
node --test frontend/tests/attendance-flow.test.cjs frontend/tests/browser-auth.test.cjs
```

Os testes completos e os testes opcionais no Chrome estão descritos no [README principal](../README.md#verificações-e-testes). Capturas geradas pelos testes ficam em `output/`, que pode ser excluída quando os registros não forem necessários.
