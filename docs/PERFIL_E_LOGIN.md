# Login e fotos de perfil

Revisado em **12/10/2026**.

O acesso ao AURA usa **usuário ou e-mail e senha**. O nome de usuário aceita espaços e o e-mail não diferencia maiúsculas de minúsculas. Novos cadastros não podem repetir um e-mail existente.

O acesso por Google foi retirado do login, cadastro e perfil. As antigas rotas `/api/auth/google/` não estão disponíveis. As colunas históricas do banco foram preservadas, sem uso na autenticação. Não é necessário configurar credenciais externas.

Se as credenciais estiverem incorretas, a tela exibe apenas o motivo do erro, sem nomes internos como `non_field_errors`.

## Cadastro e perfil

- Alunos informam matrícula; professores selecionam suas instituições ou cadastram um campus.
- Em **Meu perfil**, é possível alterar o nome exibido e adicionar, substituir ou remover a foto.
- O nome exibido é independente do usuário usado para entrar.
- Antes de salvar uma foto, a página mostra uma prévia. **Cancelar** restaura os dados salvos.
- Em **Ajustar enquadramento**, arraste a imagem dentro do círculo e use o controle de zoom para centralizar o rosto. No teclado, selecione a prévia e use as setas; com Shift, o movimento é maior.
- **Salvar alterações** grava posição e zoom para o perfil e o cabeçalho. A imagem processada pelo servidor é guardada sem recorte permanente, então é possível ajustar novamente sem reenviar o arquivo; o arquivo original em resolução integral não é mantido. **Redefinir enquadramento** volta ao centro e ao zoom inicial.

## Fotos

- JPG, PNG ou WebP de até 5 MB e 20 megapixels.
- O servidor valida a imagem, corrige a orientação, reduz para até 512 × 512 e grava WebP sem metadados EXIF.
- Os arquivos ficam em `backend/media/avatars/`, fora do Git, e são entregues pelo endpoint autenticado do próprio perfil.
- Inclua a pasta `backend/media/` e o banco SQLite no backup. `prepare_local` copia somente o banco.
- Substituir ou remover a foto exclui o arquivo anterior depois que a alteração é salva no banco.

As rotas são `GET/PATCH /api/interface/perfil/` e `GET/DELETE /api/interface/perfil/foto/`. O `PATCH` recebe `nome`, `foto` e os ajustes de enquadramento; o upload é enviado como formulário multipart. Todas exigem autenticação, e a rota da foto entrega apenas a imagem do próprio usuário.

## Onde editar a aparência

`frontend/app.css` tem um índice no início, com seções numeradas. Use **Ctrl+F** para encontrar “Login e cadastro”, “Perfil do usuário e foto” ou “Formulários, validação e avisos”.

Para o globo, procure **Globo do login — computador** ou **Globo do login — celular**. Ajuste `width` e `height` juntos. Os valores atuais são 350px no computador e 200px no celular.

## Verificação

```powershell
.\.venv\Scripts\python.exe backend/manage.py test accounts attendance courses --testrunner accounts.browser_profiles.BrowserTestRunner --noinput
node --test frontend/browser-auth.test.cjs frontend/attendance-flow.test.cjs
```

Verificação opcional, com Chrome instalado, banco e fotos temporários:

```powershell
.\.venv\Scripts\python.exe -m pip install playwright
.\.venv\Scripts\python.exe backend/manage.py test accounts.browser_profiles --testrunner accounts.browser_profiles.BrowserTestRunner --noinput
```

As capturas ficam em `output/profile-checks/`, ignorado pelo Git. O teste percorre cadastro, login, mensagens de erro e edição das fotos, incluindo o layout de celular. Ele usa HTTP local com cookies ajustados somente para o processo de teste; não exige túnel nem modifica o `.env`.
