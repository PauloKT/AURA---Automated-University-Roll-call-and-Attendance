# AURA — Controle Automatizado de Chamada Universitária

Sistema acadêmico desenvolvido como TCC para gerenciar turmas e registrar presença com **QR Code rotativo, localização do navegador e validação de vínculo em turma**. Documentação revisada em **12/10/2026**.

O Django serve tanto as páginas quanto a API. O banco é SQLite, salvo no próprio computador. **O fluxo de execução do projeto usa sempre Django e Cloudflare Tunnel juntos**, com acesso pelo endereço HTTPS do túnel no computador e no celular.

Já instalou o projeto? Vá direto para [Rodar o projeto com Django e Cloudflare](#rodar-o-projeto-com-django-e-cloudflare).

## Funcionalidades atuais

- **Professor:** cadastro com instituições, matérias, turmas, aulas, código de entrada na turma, abertura e encerramento de chamada, resultados, frequência e exportação CSV.
- **Aluno:** cadastro com matrícula, entrada na turma por código de 8 caracteres, consulta de turmas/frequência e confirmação de presença pelo QR Code.
- **Instituições:** cadastro de campus pelo professor e confirmação administrativa de coordenadas e raio.
- **Contas:** login por usuário (com espaços) ou e-mail e senha; nome exibido e foto editáveis em **Meu perfil**.
- **Chamada:** QR válido por 30 segundos, renovado pelo painel. Uma leitura validada dá ao aluno 120 segundos para concluir a localização, desde que a chamada continue aberta.
- **Presença:** dentro do raio, confirma; fora do raio, rejeita sem gravar e permite nova tentativa. Uma presença confirmada não é duplicada nem sobrescrita.
- **Frequência:** considera somente chamadas encerradas. O raio inicial é de 100 m, ajustável na instituição e copiado ao abrir cada chamada.

O navegador usa sessão Django com cookie `HttpOnly` e proteção CSRF. A API também oferece JWT. Os avisos de chamadas do aluno e os registros da chamada em andamento são consultados em intervalos de cinco segundos. Os indicadores e relatórios não têm atualização periódica geral; recarregue o painel para consultar os dados mais recentes.

Veja [Conta e foto de perfil](#conta-e-foto-de-perfil). As fotos ficam em `backend/media/` e devem acompanhar o banco nas cópias de segurança.

## Pré-requisitos

- **Python 3.11 a 3.14**, com `pip` e `venv` disponíveis. O ambiente usado na verificação foi Python 3.14; veja a [compatibilidade do Django 5.2](https://docs.djangoproject.com/en/5.2/faq/install/#what-python-version-can-i-use-with-django).
- **Git**, se for clonar o repositório; também é possível baixar e extrair o projeto.
- **Cloudflared**, necessário para abrir o túnel HTTPS usado no acesso ao projeto.
- **Node.js**, opcional, para executar os testes JavaScript.

A interface usa modelos de página do Django, HTML, CSS e JavaScript puro: não há etapa de `npm install` nem compilação da interface. SQLite acompanha o Python; não é necessário instalar um servidor de banco de dados.

As bibliotecas Python estão em [requirements.txt](requirements.txt). O **`cloudflared` é um programa instalado separadamente**; `pip install -r requirements.txt` instala as bibliotecas da aplicação. Instale os dois conforme os passos abaixo.

## Primeira execução no Windows (PowerShell)

Execute os comandos a partir da **raiz do projeto**, a pasta que contém `README.md`, `requirements.txt`, `backend` e `frontend`. No VS Code, abra essa pasta e depois um terminal PowerShell.

### 1. Criar o ambiente e instalar as dependências e o Cloudflare

Confira se o Python está disponível:

```powershell
python --version
```

Crie o ambiente virtual e instale as bibliotecas:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Se o Windows reconhecer apenas `py`, use `py -m venv .venv` no primeiro comando. Os comandos seguintes usam diretamente o Python da `.venv`, então **não é necessário ativar o ambiente** nem alterar a política de execução do PowerShell.

Em outra máquina, crie uma `.venv` nova; não copie a pasta de um computador para outro.

Instale também o executável do Cloudflare pelo [catálogo WinGet](https://github.com/microsoft/winget-pkgs/tree/master/manifests/c/Cloudflare/cloudflared):

```powershell
winget install --id Cloudflare.cloudflared --exact
```

Abra um novo terminal após a instalação e confira:

```powershell
cloudflared --version
```

Se não tiver `winget`, use o instalador para Windows na [página oficial de downloads do Cloudflare](https://developers.cloudflare.com/tunnel/downloads/). O pacote Python `cloudflare` é um cliente da API e não substitui esse executável.

### 2. Configurar o arquivo `.env`

Crie uma cópia do modelo, preservando o arquivo caso ele já exista:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Na primeira instalação, gere uma chave:

```powershell
.\.venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Abra `.env` no editor e substitua o valor de `SECRET_KEY` pela chave gerada, entre aspas simples. Use esta configuração inicial; o nome do servidor e a origem HTTPS serão preenchidos assim que o túnel mostrar o endereço:

```dotenv
SECRET_KEY='cole-a-chave-gerada-aqui'
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
CSRF_TRUSTED_ORIGINS=
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
CORS_ALLOWED_ORIGINS=http://127.0.0.1:8000,http://localhost:8000
```

Mantenha os cookies seguros como `True`, pois o acesso será por HTTPS. Se já usa o projeto, mantenha a chave existente e confira as opções novas em [.env.example](.env.example). O `.env` fica na raiz e não deve ser enviado ao Git. Reinicie o Django sempre que editar esse arquivo.

O arquivo `.env.example` é apenas um modelo: a aplicação carrega o `.env`. Variáveis já definidas no ambiente do terminal têm prioridade sobre esse arquivo. Se uma configuração não mudar após reiniciar, confira também as variáveis do terminal.

### 3. Preparar o banco de dados

```powershell
.\.venv\Scripts\python.exe backend/manage.py prepare_local
```

Esse comando aplica as migrações, que criam ou atualizam as tabelas, e verifica a configuração. Na primeira execução, cria `backend/db.sqlite3`; quando já existe banco, faz uma cópia em `backend/backups/` antes de migrar. As migrações cadastram a instituição inicial AEMS quando são aplicadas pela primeira vez. Não criam usuários nem o cenário de demonstração.

A existência de `db.sqlite3`, por si só, não indica que o banco esteja preparado: um arquivo vazio ainda precisa das migrações. Para confirmar que todas foram aplicadas, execute `.\.venv\Scripts\python.exe backend/manage.py migrate --check`.

Se o banco foi zerado mantendo o histórico de migrações, executar `prepare_local` novamente **não recria a AEMS nem as contas removidas**. Siga [Começar com um banco vazio](#começar-com-um-banco-vazio).

### 4. Criar o administrador

Para conferir as instituições e configurar a localização de um campus:

```powershell
.\.venv\Scripts\python.exe backend/manage.py createsuperuser
```

Siga as perguntas do terminal. A senha não aparece enquanto você digita. Essa conta serve para o painel administrativo; crie as contas de professor e aluno pela tela de cadastro do AURA.

### 5. Rodar o projeto

Siga a seção abaixo para iniciar os dois processos e configurar a URL do túnel. Esse é o mesmo procedimento usado nas próximas vezes.

## Rodar o projeto com Django e Cloudflare

Mantenha **dois terminais abertos**: um com o Django e outro com o Cloudflare. O Django escuta em `127.0.0.1:8000`; o Cloudflare encaminha o acesso HTTPS para esse endereço. No navegador, use sempre a URL HTTPS do túnel.

### 1. Terminal 1 — iniciar o Django

Escolha **um** dos comandos, conforme a pasta atual do terminal. Copie a linha completa, incluindo o Python antes de `manage.py`.

**Se está em `D:\TCC-AURA\backend` com a `.venv` ativada**, como no prompt `(.venv) PS D:\TCC-AURA\backend>`:

```powershell
python manage.py runserver 127.0.0.1:8000
```

**Se está na raiz `D:\TCC-AURA`**, use o Python da `.venv` diretamente, sem precisar ativá-la:

```powershell
.\.venv\Scripts\python.exe backend/manage.py runserver 127.0.0.1:8000
```

O `manage.py` é um arquivo Python. Executar apenas `manage.py runserver ...` no PowerShell causa o erro de comando não reconhecido. O prefixo `python` (ou o caminho completo do executável da `.venv`) faz parte do comando.

Deixe o servidor rodando nesse terminal. Se ele já estiver nessa porta, não inicie outra instância.

### 2. Terminal 2 — iniciar o Cloudflare

Em outro PowerShell, em qualquer pasta:

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

O terminal mostrará uma URL como `https://nome-gerado.trycloudflare.com`. Copie a URL real e mantenha esse terminal aberto. Esse [Quick Tunnel](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/) dispensa conta e domínio próprio; o endereço é temporário e muda ao criar outro túnel.

### 3. Configurar a URL do túnel no `.env`

No `.env`, ajuste as linhas abaixo usando o endereço que apareceu no terminal:

```dotenv
ALLOWED_HOSTS=127.0.0.1,localhost,nome-gerado.trycloudflare.com
CSRF_TRUSTED_ORIGINS=https://nome-gerado.trycloudflare.com
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

Em `ALLOWED_HOSTS`, use apenas o nome do servidor, sem `https://` e sem barra. Em `CSRF_TRUSTED_ORIGINS`, use a origem completa com `https://`, sem barra final. A interface e a API usam a mesma origem; mantenha `CORS_ALLOWED_ORIGINS` como está para esse fluxo.

No **terminal 1**, pressione `Ctrl+C` e execute novamente o comando do Django. Mantenha o **terminal 2** rodando para preservar o endereço do túnel.

### 4. Acessar pelo endereço HTTPS

**Professor e aluno devem acessar a URL HTTPS do túnel.** O professor precisa gerar o QR a partir desse endereço; se abrir o painel em `localhost` ou `127.0.0.1`, o link do QR apontará para o próprio celular.

Faça login pelo endereço HTTPS e permita o acesso à localização no celular. Os dois aparelhos precisam de internet, mas podem estar em redes diferentes.

No endereço HTTPS gerado, use estes caminhos:

- `/` — login.
- `/register.html` — cadastro de professor ou aluno.
- `/admin/` — administração.
- `/api/schema/swagger-ui/` — documentação interativa da API.

Por exemplo, para administrar as instituições, acrescente `/admin/` à URL real do túnel.

### 5. Encerrar e iniciar novamente

Para encerrar tudo, pressione `Ctrl+C` nos dois terminais.

Para **trocar apenas o túnel**, pressione `Ctrl+C` no terminal do Cloudflare e execute novamente:

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

Copie a nova URL, substitua o nome antigo do servidor em `ALLOWED_HOSTS` e a origem antiga em `CSRF_TRUSTED_ORIGINS`, salve o `.env` e reinicie somente o Django. Deixe o novo túnel rodando. Abra o novo endereço e faça login novamente nos aparelhos; o QR deve ser gerado pelo endereço novo.

Na próxima execução completa, repita os passos 1 a 4.

O túnel torna o servidor de desenvolvimento acessível pela internet enquanto está ligado. Esse fluxo é destinado a testes e demonstrações.

## Depois de atualizar os arquivos do projeto

Pare o Django e execute na **raiz do projeto**:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe backend/manage.py prepare_local
```

Depois siga [Rodar o projeto com Django e Cloudflare](#rodar-o-projeto-com-django-e-cloudflare). Não é necessário recriar o administrador ou a `.venv` a cada execução.

Para alterar somente HTML, CSS ou JavaScript em desenvolvimento, salve os arquivos e recarregue a página; `Ctrl+F5` ajuda a descartar o cache no computador. Não é necessário fechar o túnel. Alterações no `.env` exigem reiniciar o Django.

### Atualizar as bibliotecas Python

O [requirements.txt](requirements.txt) define versões mínimas e limites de atualização. A revisão de **12/10/2026** consultou as versões publicadas no PyPI. O projeto permanece na série [Django 5.2 LTS](https://www.djangoproject.com/download/#supported-versions), com suporte estendido até abril de 2028; a migração para Django 6 exige uma revisão própria.

Para atualizar as bibliotecas dentro dos limites do arquivo, pare o servidor e execute:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

Depois execute `prepare_local` e as [verificações e testes](#verificações-e-testes). Instalar sem `--upgrade` pode manter uma versão já instalada que ainda satisfaça os limites do arquivo.

## Fazer a primeira chamada

1. **Confira a instituição:** entre no painel administrativo, abra **Instituições** e confira latitude, longitude e raio do campus. A AEMS é criada na aplicação inicial das migrações; se não estiver no banco, cadastre a instituição do teste. Uma instituição nova precisa de confirmação administrativa da localização antes de abrir chamadas.
2. **Cadastre o professor:** na tela de cadastro, escolha o perfil de professor e uma instituição ativa. Também é possível adicionar uma nova instituição nessa tela.
3. **Prepare a aula:** no painel do professor, crie matéria, turma e aula. Compartilhe o **código de 8 caracteres da turma** com o aluno.
4. **Cadastre o aluno:** informe a matrícula, faça login e use **Entrar na turma** com o código recebido.
5. **Abra a chamada:** no painel do professor, selecione a aula e inicie a chamada para exibir o QR Code.
6. **Confirme a presença:** o aluno lê o QR com a câmera do celular, abre o link no navegador em que está logado e permite a localização.
7. **Confira e encerre:** acompanhe o resultado no painel do professor e encerre a chamada para incluí-la no cálculo da frequência.

A distância é calculada a partir das coordenadas da instituição, não da posição do notebook. Para testar em casa, use uma instituição de teste com as coordenadas reais desse local. Uma chamada vinculada à AEMS deve rejeitar quem estiver fora do raio do campus.

### Teste pelo celular

Antes da apresentação, faça este ensaio com contas e uma instituição de teste:

1. Abra o mesmo endereço HTTPS do túnel no computador e no celular. Entre como professor no computador e como aluno no celular.
2. Confira as coordenadas reais do local, a matrícula do aluno na turma e a permissão de localização no navegador.
3. Inicie a chamada, leia o QR Code atual e confirme que a presença aparece uma única vez no painel do professor.
4. Negue a localização e confira a mensagem de erro. Depois permita o acesso e tente novamente com um QR válido.
5. Teste fora do raio: a tentativa deve ser rejeitada sem gravar presença. Dentro do raio, uma nova tentativa válida deve confirmar.
6. Abra um link de QR depois dos 30 segundos de validade e confira a rejeição. Leia o código atualizado para continuar. Quando a leitura já foi validada, o prazo para concluir a localização é de 120 segundos, desde que a chamada permaneça aberta.
7. Se houver dois celulares disponíveis, confirme com dois alunos ao mesmo tempo e confira os dois registros.
8. Encerre a chamada e recarregue os relatórios. Confira as presenças e faltas; novas confirmações nessa chamada devem ser rejeitadas.

O ensaio no aparelho é necessário para validar câmera, permissões e localização reais; os testes automatizados não substituem essa etapa.

## Conta e foto de perfil

O acesso aceita nome de usuário, inclusive com espaços, ou e-mail. A comparação do e-mail ignora maiúsculas e minúsculas. O cadastro exige matrícula para alunos e ao menos uma instituição para professores.

Em **Meu perfil**, é possível alterar o nome exibido, enviar uma foto, ajustar seu enquadramento e removê-la. O nome usado para entrar na conta permanece o mesmo. São aceitas fotos JPG, PNG e WebP de até 5 MB e 20 megapixels; o servidor reduz a imagem e remove seus metadados.

As fotos são privadas e ficam em `backend/media/`. Inclua essa pasta nas cópias de segurança junto com `backend/db.sqlite3`. O sistema ainda não oferece recuperação de senha nem confirmação de e-mail.

## Problemas comuns

- **`manage.py` não reconhecido:** dentro de `backend`, com a `.venv` ativada, execute `python manage.py runserver 127.0.0.1:8000`. Copie o comando completo, incluindo `python`.
- **`python` não reconhecido:** confira a instalação do Python e a opção de adicioná-lo ao `PATH`; tente `py --version` e reabra o terminal.
- **`.venv` não encontra o Python:** ambientes virtuais dependem da instalação original. Se mudou de máquina ou removeu essa versão do Python, recrie o ambiente e reinstale `requirements.txt`.
- **`ModuleNotFoundError` ou Django não encontrado:** execute a instalação com `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` e use esse mesmo Python para iniciar o servidor.
- **`no such table` ou migrações pendentes:** pare o servidor e execute `.\.venv\Scripts\python.exe backend/manage.py prepare_local`.
- **`cloudflared` não reconhecido:** instale o executável e reabra o terminal. Se foi instalado em `C:\Program Files (x86)\cloudflared`, use `& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://127.0.0.1:8000`.
- **`DisallowedHost` no túnel:** confira o nome atual do servidor em `ALLOWED_HOSTS` e reinicie o Django.
- **Página sem estilos:** confirme `DEBUG=True` para o servidor de desenvolvimento, confira se o terminal está sobrescrevendo essa variável e reinicie o Django.
- **Erro CSRF/403 ao entrar ou enviar formulário:** confira a URL HTTPS em `CSRF_TRUSTED_ORIGINS`, reinicie o Django e recarregue a página pelo endereço do túnel.
- **Login não permanece ao acessar `127.0.0.1` ou `localhost`:** abra o endereço HTTPS do Cloudflare. O projeto usa cookies seguros e o fluxo de acesso deve passar pelo túnel.
- **Celular não abre o link ou não solicita GPS:** use a URL HTTPS do túnel nos dois aparelhos, mantenha os dois processos abertos e confira as permissões de localização do navegador e do aparelho.
- **Chamada bloqueada ou presença fora do raio:** confira as coordenadas e o raio da instituição no admin. O GPS pode oscilar; uma tentativa fora do raio não grava presença e permite tentar novamente.

## Verificações e testes

Na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe backend/manage.py check
.\.venv\Scripts\python.exe backend/manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe backend/manage.py migrate --check
.\.venv\Scripts\python.exe backend/manage.py test accounts attendance courses --testrunner accounts.browser_profiles.BrowserTestRunner --noinput
```

A suíte usa SQLite em arquivo temporário, sem preencher ou alterar o banco local. Inclui cadastro, autenticação, perfil, chamadas, frequência e o comando de demonstração. O nome `BrowserTestRunner` identifica o executor que isola o banco; esse comando não exige abrir o Chrome.

`makemigrations --check --dry-run` confere se os modelos correspondem aos arquivos de migração. `migrate --check` confere se o banco local recebeu essas migrações; se falhar, execute `prepare_local` antes de iniciar o sistema.

Se tiver Node.js instalado, execute também os testes de confirmação, renovação do QR e autenticação do navegador:

```powershell
node --test frontend/tests/attendance-flow.test.cjs frontend/tests/browser-auth.test.cjs
```

Os testes opcionais em Chrome verificam o navegador de fato. Com o Chrome instalado:

```powershell
.\.venv\Scripts\python.exe -m pip install playwright
.\.venv\Scripts\python.exe backend/manage.py test accounts.browser_layout accounts.browser_profiles --testrunner accounts.browser_profiles.BrowserTestRunner --noinput
```

Eles também usam banco temporário, criam capturas locais em `output/` e configuram cookies para HTTP apenas no processo de teste. Não precisam de túnel nem alteram o `.env`.

Os testes automatizados complementam o [roteiro manual no celular](#teste-pelo-celular), que deve ser executado nos aparelhos usados na apresentação.

## Tecnologias e estrutura

Servidor com Django 5.2 LTS, Django REST Framework, Simple JWT, CORS, `python-dotenv`, `requests` para geocodificação e `drf-spectacular` para OpenAPI. O QR é gerado localmente em SVG com `qrcode`. O tratamento das fotos de perfil usa Pillow.

```text
backend/
  accounts/       usuários, autenticação, perfil e rotas do aluno
  courses/        instituições, matérias, turmas e aulas
  attendance/     sessões de chamada, presença, frequência e geolocalização
  backend/        configurações, rotas e APIs dos painéis
  manage.py       comandos de administração do Django
frontend/
  templates/
    layouts/      base HTML e estruturas de autenticação e painéis
    pages/        login, cadastro, professor, aluno e confirmação de presença
    includes/     componentes compartilhados e seções de aluno/professor
  static/
    css/          estilos da interface
    js/           scripts das páginas e componentes
    images/       marca, ícones e ilustrações
    fonts/        fonte local e licença
  tests/          testes JavaScript
docs/             guia técnico da aplicação
.env.example      modelo das variáveis de ambiente
requirements.txt  bibliotecas Python
```

Os HTMLs são templates renderizados pelo Django; acesse as páginas pelo servidor, não abrindo os arquivos diretamente. As URLs continuam `/login.html`, `/register.html`, `/professor.html`, `/aluno.html` e `/confirmar-presenca.html`. Veja [como editar o frontend](frontend/README.md).

Detalhes de arquitetura, contratos da API e regras de negócio estão no [Guia técnico](docs/GUIA_TECNICO.md).

## Começar com um banco vazio

O Git não contém usuários, senhas, fotos ou o banco de dados. Depois de uma limpeza completa, recrie o administrador com `createsuperuser`, cadastre uma instituição pelo admin (ou pelo cadastro de professor) e confirme sua localização. Em seguida, cadastre professor e aluno e prepare as turmas.

`prepare_local` atualiza a estrutura e faz uma cópia de segurança; não é um comando para zerar ou restaurar dados. Uma limpeza não exige apagar migrações. As cópias do banco ficam em `backend/backups/`; para recuperar também fotos, é necessária uma cópia correspondente de `backend/media/`.

## Dados de demonstração

Para preencher as telas com dados fictícios e fazer capturas de tela, após aplicar as migrações execute:

```powershell
.\.venv\Scripts\python.exe backend/manage.py seed_demo
```

O comando cria professores, alunos, matérias, turmas, aulas e um histórico de frequência. Ele exibe no terminal os acessos e a senha das contas novas; guarde essa senha para entrar. Para explorar as telas, use **Mariana Costa** como professora ou **Lucas Martins** como aluno.

Executar novamente preserva os cadastros e as senhas existentes. O comando não cria administrador. Nomes, endereços e registros são fictícios; para testar GPS com aparelhos, configure uma instituição com as coordenadas reais do ensaio.

## O que fica fora do Git

O `.gitignore` exclui `.env`, ambientes virtuais, bancos SQLite, fotos enviadas, caches, logs, `backend/backups/`, `output/` e `.agents/skill-backups/`. A pasta `output/` guarda capturas e arquivos temporários de verificações e pode ser excluída se esses registros não forem mais necessários. O sistema não depende dela; os testes que geram capturas recriam a pasta. Os arquivos usados pelo site ficam em `frontend/`.

Mantenha versionados `.env.example`, `requirements.txt`, código, migrações, testes, documentação e o comando `seed_demo`. Os dados criados por esse comando permanecem apenas no banco de cada instalação.

## Estado do projeto e dados

Para preencher as telas com usuários, turmas e frequências fictícias, consulte [Dados de demonstração](#dados-de-demonstração).

O projeto está em fase de validação final do MVP e **ainda não está homologado para uso institucional**. A localização do navegador pode ser imprecisa ou manipulada; o sistema não garante presença física nem elimina fraude. Não há biometria, verificação de Wi-Fi/IP institucional ou notificações push com a página fechada.

O sistema armazena cadastro, matrícula, presença e coordenadas recebidas. Antes de usar dados reais, definir responsáveis pelo acesso, retenção, exclusão e recuperação por backup. Professores com várias instituições ainda não escolhem o campus por aula; confira a instituição usada na chamada.

Na revisão de 12/10/2026, foram reproduzidas duas falhas que ainda precisam de correção no código:

- Alterar a turma de uma aula com chamadas transfere seu histórico e muda os relatórios das duas turmas. Preserve a turma das aulas que já tiveram chamada.
- Desativar uma instituição não impede todas as novas chamadas: o vínculo antigo do professor ainda pode usá-la como referência.

Esses pontos não são corrigidos pela instalação das dependências nem pela preparação do banco.

## Autoria

Desenvolvido como TCC por **Paulo Amaral** ([GitHub](https://github.com/PauloKT)) e **Heitor Cortes** ([GitHub](https://github.com/heitorpcrl)). Projeto destinado a fins acadêmicos.
