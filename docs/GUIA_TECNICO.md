# Guia técnico do AURA

Referência da implementação em **01/10/2026**.

## 1. Arquitetura

Django 5.2 LTS e DRF no backend; templates Django, HTML/CSS/JavaScript puro no frontend. Sem React, Bootstrap, Celery ou biometria. SQLite é o banco local do projeto. O fluxo de execução usa sempre Django e Cloudflare Tunnel juntos, com acesso pelo endereço HTTPS do túnel no computador e no celular.

- `backend/backend/settings.py`: ambiente, SQLite, JWT e CORS.
- `backend/backend/urls.py`: páginas explícitas (inclusive com `DEBUG=False`), APIs e OpenAPI.
- `backend/backend/ui_api.py`: perfil e dados dos painéis; contagem de presenças agregada no banco e agrupamento de relatórios em uma passagem.
- `backend/accounts/`: usuário, cadastro, login e frequência.
- `backend/courses/`: instituição, matéria, turma, matrícula e aula.
- `backend/attendance/`: sessão de chamada, resultado e geofence.
- `backend/templates/`: bases e includes compartilhados.
- `frontend/`: cinco páginas, `app.css`, marca, componentes e scripts.

Dentro de `backend`, com a `.venv` ativada, inicie o Django com `python manage.py runserver 127.0.0.1:8000`. Em outro terminal, execute `cloudflared tunnel --url http://127.0.0.1:8000`. A configuração da URL e os comandos completos estão no [README](../README.md#rodar-o-projeto-com-django-e-cloudflare). Não há armazenamento de uploads implementado no fluxo atual.

## 2. Autenticação e permissões

O navegador usa `POST /api/auth/login/` e sessão Django com cookie `HttpOnly`, `SameSite=Lax` e duração de um dia desde o login. A resposta traz apenas o perfil; o JavaScript não recebe a credencial de sessão. `POST /api/auth/logout/` apaga a sessão no servidor. Sessão expirada leva a um novo login, preservando o destino do QR. O frontend remove JWTs legados do `localStorage` ao carregar, sem ler ou gravar novas credenciais ali.

Login e logout exigem CSRF inclusive para visitantes; demais operações por sessão usam a [proteção CSRF do DRF](https://www.django-rest-framework.org/api-guide/authentication/#sessionauthentication). O template inicial gera o token e o frontend envia `X-CSRFToken` nas operações de escrita, lendo o cookie atualizado após login. O cookie de CSRF é legível pelo JavaScript; ele não é uma credencial de autenticação. Cookies `HttpOnly` limitam a extração da credencial, mas não tornam a aplicação imune a ações via XSS.

Clientes da API podem continuar usando `POST /api/login/`, que devolve JWT `access`, `refresh` e perfil, e `/api/token/refresh/`. Access dura 60 minutos; refresh, um dia, sem rotação ou blacklist. Esse contrato é independente da sessão do navegador: sair do navegador não revoga JWTs emitidos separadamente a clientes da API. Não há opção inoperante `BLACKLIST_AFTER_ROTATION`.

Professor altera apenas seus recursos. Aluno consulta turmas em que está matriculado e registra sua própria presença. O catálogo `/api/materias/` ainda permite leitura de todas as matérias por alunos autenticados. A API dos painéis limita dados ao professor responsável ou aluno matriculado.

O cadastro público permite escolher professor ou aluno. Aluno informa matrícula; professor seleciona instituições ativas. O campo de e-mail usa a validação de formato do DRF e aceita domínios pessoais ou institucionais; não há verificação de e-mail, recuperação de senha ou aprovação de professor. Senha exige 5 caracteres, maiúscula, número e símbolo; não utiliza os validadores globais de senha do Django. Essas são limitações a resolver antes de uso institucional.

## 3. Instituição e turma

`GET /api/instituicoes/catalogo/` é público para viabilizar o cadastro e retorna somente `id`, `nome`, `cidade`, `estado` e `localizacao_confirmada`. A lista completa e o detalhe `/api/instituicoes/{id}/` exigem autenticação; geocodificação e confirmação de localização continuam exclusivas do administrador.

No cadastro de professor, é possível escolher instituições existentes ou usar **Adicionar nova instituição**. O campo opcional `nova_instituicao` em `POST /api/register/` recebe nome, logradouro, número, bairro, cidade e UF brasileira. Conta e instituição são criadas na mesma transação. Alunos não podem usar esse campo e não é permitido combinar instituição nova e existentes no mesmo envio.

A instituição nova fica ativa no catálogo, mas com localização pendente (latitude/longitude vazias e raio inicial de 100 m); campos de coordenadas e raio enviados no cadastro público não são aceitos como configuração. Ela é vinculada ao professor e não permite iniciar chamadas até a confirmação administrativa. Nomes repetidos, inclusive com diferença apenas de maiúsculas, são rejeitados.

O administrador pode acessar `/admin/courses/instituicao/`, conferir endereço, preencher latitude/longitude e raio e salvar. O formulário administrativo valida limites e o preenchimento das duas coordenadas juntas; registra data e fonte da confirmação. A ação administrativa da API continua disponível. Não há migration nova para esse fluxo.

O professor pode vincular múltiplas instituições. Ao abrir uma sessão, o backend usa a primeira instituição ativa da relação; se nenhuma for encontrada, usa o vínculo singular legado e, por último, as coordenadas legadas do professor. A interface ainda não escolhe campus por aula. O fallback singular não revalida o campo `ativa`.

A migration `courses/0004_confirm_aems_coordinates.py` grava a AEMS em latitude `-20.786820236467992`, longitude `-51.668829782798554`. Isso descreve o código de inicialização, não comprova a localização física de cada instalação; confira o banco e o raio antes do teste.

A turma possui código aleatório único de **8 caracteres**, exibido ao professor. O aluno envia `codigo_acesso` para entrar. `link_acesso` e a compatibilidade com convite antigo permanecem no backend para instalações existentes. Código da turma é diferente do token de uma chamada: não substitui o QR para registrar presença.

## 4. Fluxo de chamada

1. Professor cria matéria, turma e aula; inicia sessão da própria aula.
2. A sessão copia a localização e o raio da instituição. Alterações posteriores na instituição não mudam essa referência.
3. O token expira após 30 segundos. O painel consulta o token ao abrir a chamada e ao expirar; a API renova apenas tokens vencidos. O painel retira a imagem vencida e repete consultas com falha após três segundos. O contador usa o horário do servidor, descontando o tempo da requisição, e consulta novamente ao voltar à aba. Não há tarefa agendada.
4. O endpoint de token, restrito ao professor dono da chamada, devolve `qr_image` como SVG em uma data URL, gerado em memória por `qrcode`, e `servidor_agora`. Nada é enviado a um gerador externo. O painel informa `origin` para preservar HTTPS atrás do túnel; o backend só aceita HTTP/HTTPS no mesmo host da requisição. Token e imagem correspondem ao mesmo estado da sessão e a resposta usa `Cache-Control: no-store`. A biblioteca usa a [fábrica SVG oficial](https://github.com/lincolnloop/python-qrcode#svg), sem precisar de Pillow.
5. Aluno matriculado lê o QR. `/api/sessoes/{id}/preparar/` valida sessão/token e devolve comprovante assinado para aquele aluno e sessão, válido por 120 segundos.
6. A página solicita localização e envia comprovante e coordenadas a `/api/presenca/registrar/`. A API também aceita token atual diretamente.
7. Coordenadas válidas dentro do raio geram `valida=True` e HTTP 201. Fora do raio retorna HTTP 400 sem gravar. Nova tentativa pode confirmar na mesma sessão com token/comprovante válido. Reenvio de presença confirmada retorna HTTP 200 sem duplicar nem alterar coordenadas/horário. Um registro inválido de versões anteriores pode ser corrigido na sessão ainda aberta; a API atualiza esse registro e retorna HTTP 200.
8. Apenas presença válida deixa de aparecer nas chamadas pendentes. A lista do aluno contém metadados, sem token ou imagem do QR. O frontend só exibe sucesso com `presenca.valida === true`; qualquer outro resultado permite nova tentativa. Professor consulta os resultados a cada cinco segundos enquanto a tela está aberta.

Token inválido, comprovante expirado, coordenadas inválidas, falta de matrícula ou sessão encerrada são rejeitados. Negar GPS ou falhar na captura não envia resultado nem grava falta.

### Operações simultâneas

`attendance/transactions.py` centraliza transações curtas. Registro, leitura validada do QR, renovação e encerramento recarregam a mesma sessão dentro de uma transação. No registro, matrícula, estado da sessão, token/comprovante e prazo são verificados novamente depois de reservar a escrita, antes de gravar.

- Se o registro obtiver o bloqueio primeiro, ele termina e o encerramento ocorre depois; o resultado é preservado.
- Se o encerramento obtiver o bloqueio primeiro, o registro encontra a sessão fechada e é rejeitado. A ordem relevante é a do banco, não a hora em que o usuário clicou.
- Duas telas consultando um token vencido não o renovam de maneira independente: a segunda lê o token que a primeira já renovou. Token válido não é trocado antecipadamente. Respostas de token e comprovante usam `Cache-Control: no-store`.
- A abertura bloqueia a aula e consulta a sessão ativa com bloqueio, evitando sessões duplicadas criadas simultaneamente pela API. Não foi adicionada restrição nova para dados históricos nem alterada a regra de reabrir após encerramento.
- PATCH/PUT de sessão recarrega seu estado sob bloqueio para não restaurar acidentalmente um estado antigo. Exclusão da sessão usa o mesmo bloqueio.
- Envios repetidos preservam a primeira presença válida por aluno/sessão. Falhas não consomem a tentativa; matrícula, sessão, token/comprovante e GPS são revalidados antes da gravação. Encerrar uma chamada já fechada continua retornando HTTP 400, sem mudar a data de encerramento.

No painel, respostas de seleções antigas são descartadas. Início, encerramento e renovação têm proteção contra envios sobrepostos; os resultados informam o estado da sessão para reconhecer encerramentos em outra aba. Essa coordenação não se estende a qualquer edição administrativa: trocar a turma de uma aula durante a chamada ainda exige revisão específica do CRUD.

O SQLite usa `transaction_mode=IMMEDIATE` e espera de até 20 segundos para reservar a escrita. Isso serializa transações de escrita do banco local e não transforma SQLite em um banco de alta concorrência. Saturação de bloqueio nas operações protegidas retorna HTTP 503 com orientação para tentar novamente; outros erros de banco não são ocultados. Não há repetição automática do envio.

As transações não aguardam GPS, serviços externos ou interação humana. O limite de 120 segundos continua sendo o prazo do comprovante, não a duração de uma transação. Fundamentação: [transações SQLite no Django](https://docs.djangoproject.com/en/5.2/ref/databases/#transactions-behavior) e [select_for_update](https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update).

`attendance/geolocation.py` valida coordenadas finitas, raio de 1 a 10.000 m e aplica pré-filtro geográfico seguido de Haversine. A referência é a instituição, não a posição do computador. Não há prova de autenticidade das coordenadas fornecidas pelo navegador nem validação de Wi-Fi/IP.

## 5. Frequência e histórico

A frequência é **presenças válidas em sessões encerradas / quantidade de sessões encerradas da turma × 100**. O filtro é `ativa=False` em ambos os termos. O status é `sem_dados` sem sessões encerradas, `aprovado` a partir do mínimo da matéria e `reprovado` abaixo dele. Isso vale para a consulta individual, lista de turmas, painéis e dados usados pelo CSV.

Chamadas em andamento continuam no painel ao vivo, mas não alteram a frequência. Sessões encerradas anteriores à matrícula e sessões diferentes da mesma aula ainda entram no cálculo. Reabrir uma aula com sessão ativa a reutiliza; iniciar após encerrar cria outra sessão. O campo chamado `aulas` nos relatórios representa sessões encerradas de chamada.

As faltas do relatório são total de sessões encerradas menos presenças válidas nessas sessões; incluem quem não enviou resultado. A lista abaixo do QR contém presenças confirmadas e eventuais registros inválidos de versões anteriores. Tentativas rejeitadas por GPS não entram nessa lista. Não é a mesma lista de faltas calculadas no relatório.

Exclusões de matéria, turma, aula ou sessão podem apagar o histórico relacionado por cascata. Não há justificativa de falta, alteração auditada de presença ou arquivamento acadêmico implementados.

## 6. Rotas principais

- Cadastro: `POST /api/register/`. Navegador: `POST /api/auth/login/` e `/api/auth/logout/`. Clientes JWT: `POST /api/login/` e `/api/token/refresh/`.
- Instituições: catálogo público `GET /api/instituicoes/catalogo/`; lista autenticada `GET /api/instituicoes/`; ações administrativas `POST /api/instituicoes/{id}/geocodificar/` e `/confirmar-localizacao/`.
- CRUD do professor: `/api/materias/`, `/api/turmas/`, `/api/aulas/`, `/api/turma-aluno/` e respectivos detalhes `{id}/`.
- Sessões: `POST /api/sessoes/`; `GET /api/sessoes/{id}/token/` e `/resultados/`; `POST /api/sessoes/{id}/encerrar/`.
- Aluno: `GET /api/sessoes/ativas/`; `POST /api/sessoes/{id}/preparar/`; `POST /api/presenca/registrar/`.
- Turmas/frequência do aluno: `GET /api/aluno/turmas/`, `/api/aluno/minha-frequencia/`; `POST /api/aluno/entrar-turma/`.
- Interface: `GET /api/interface/perfil/` e `/api/interface/painel/`.
- Documentação gerada: `/api/schema/`, `/api/schema/swagger-ui/`, `/api/schema/redoc/`. APIs personalizadas ainda precisam de anotações para um schema completo.

## 7. Configuração e manutenção

Use `.env.example` como referência e mantenha `DEBUG=True` no uso local. Quando o Cloudflare Tunnel retornar um hostname, inclua-o em `ALLOWED_HOSTS` e a URL HTTPS completa em `CSRF_TRUSTED_ORIGINS`. Defina `SESSION_COOKIE_SECURE=True` e `CSRF_COOKIE_SECURE=True` no acesso HTTPS. Em HTTP local, ambas precisam ser `False`; se omitidas, o padrão é `not DEBUG`. O cadastro público e as APIs JWT não substituem a configuração CSRF necessária ao login do navegador.

O cadastro usa instituições e não aceita CEP como configuração de localização. A geocodificação automática de usuários por CEP e sua thread foram removidas. Campos legados de CEP/coordenadas permanecem no modelo para preservar dados antigos; salvar um usuário não faz consultas de rede. A busca administrativa de coordenadas da instituição continua disponível.

Migrations antigas de WebAuthn precisam permanecer para atualizar bancos existentes; `attendance/0005_remove_webauthn.py` remove as estruturas de biometria. Não apagar migrations nem banco para limpar o projeto.

## 8. Verificação antes da apresentação

No diretório `backend`, executar `python manage.py check` e `python manage.py makemigrations --check --dry-run`.

O banco de apresentação mantém somente as instituições cadastradas; professores, alunos, matérias, turmas, aulas, sessões e presenças devem ser criados durante o ensaio ou demonstração.

Execute o roteiro de [TESTE_CELULAR.md](TESTE_CELULAR.md) para validar navegação, câmera, GPS, QR Code e chamada antes da banca.
