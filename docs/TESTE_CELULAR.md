# Testar chamada pelo celular

Revisado em **06/10/2026**. Professor e aluno devem usar o mesmo endereço HTTPS. No teste local, o banco continua no computador que executa Django.

## Preparar o computador ou notebook

1. Em uma máquina nova, crie um ambiente virtual e instale `requirements.txt` e o executável `cloudflared`, seguindo o [README](../README.md). O fluxo do projeto usa sempre [Django e Cloudflare juntos](../README.md#rodar-o-projeto-com-django-e-cloudflare); o executável do túnel não é instalado pelo `pip`. Não copie `.venv` da outra máquina.
2. Configure `.env` com `DEBUG=True`. Na raiz do projeto, execute `.\.venv\Scripts\python.exe backend/manage.py prepare_local`: backup do SQLite existente e aplicação de migrations. Isso deve ser conferido em cada instalação.
3. Ainda na raiz, inicie `.\.venv\Scripts\python.exe backend/manage.py runserver 127.0.0.1:8000`. Se já estiver na pasta `backend` com a `.venv` ativada, use `python manage.py runserver 127.0.0.1:8000`. O Python faz parte do comando; não execute apenas `manage.py`.
4. Em outro terminal, execute o túnel:

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

Se não estiver no PATH, use o local em que foi instalado. Exemplo:

```powershell
& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url "http://127.0.0.1:8000"
```

O argumento é somente a URL: não copie colchetes nem sintaxe de link Markdown. Se o serviço responder com erro 409, tente novamente mais tarde; esse erro de provisionamento ocorre antes de o túnel alcançar o Django.

5. Adicione o hostname retornado (sem `https://`) a `ALLOWED_HOSTS` e a URL HTTPS completa a `CSRF_TRUSTED_ORIGINS`. Mantenha `SESSION_COOKIE_SECURE=True` e `CSRF_COOKIE_SECURE=True`. Reinicie o Django. Essas opções são necessárias também para login e formulários do sistema. Quando iniciar outro túnel, atualize os endereços no `.env` e reinicie o Django novamente.
6. Abra o endereço HTTPS no computador e no celular; mantenha servidor e túnel ligados. A rede da faculdade precisa permitir acesso ao domínio. O celular pode usar outra rede com internet.
7. Encerre servidor e túnel após o ensaio: o túnel torna o servidor de desenvolvimento acessível pela internet.

Se o professor abrir em `localhost` ou `127.0.0.1`, o QR apontará para o próprio celular. Por isso ele também precisa abrir o endereço HTTPS. GPS em celular requer contexto seguro, normalmente HTTPS.

## Professor

Se a instituição ainda não existir, no cadastro escolha **Sou professor → Adicionar nova instituição** e preencha o endereço do campus. Antes do ensaio, um administrador deve entrar em `/admin/courses/instituicao/`, abrir a instituição cadastrada, conferir as coordenadas e salvar latitude, longitude e raio. Sem essa confirmação, iniciar chamada continua bloqueado.

1. Entre pelo endereço HTTPS com uma conta de professor vinculada à instituição do teste.
2. Crie ou selecione matéria, turma e aula.
3. Mostre ao aluno o **código de 8 caracteres da turma**.
4. Inicie a chamada e mantenha o QR visível. Seu token dura 30 segundos e é renovado pelas consultas do painel.
5. Acompanhe os resultados abaixo do QR: nome, presente/falta, horário e quantidade aguardando.
6. Encerre a chamada ao terminar.

## Aluno

1. Faça login no mesmo endereço HTTPS, usando o navegador que será aberto pela câmera.
2. Selecione **Entrar em uma turma**, digite o código e confirme a matrícula.
3. O painel consulta chamadas disponíveis a cada cinco segundos enquanto está visível.
4. Leia o QR com a câmera e abra o link no mesmo navegador. Se abrir um navegador interno sem login, autentique-se; pode ser necessário ler o QR atual novamente.
5. Permita a localização e aguarde o resultado: presença dentro do raio ou erro com opção de tentar novamente fora dele.

Se negar GPS ou houver erro de captura, nada é registrado: corrija a permissão e tente novamente. Uma leitura validada pelo servidor dá 120 segundos para concluir GPS; depois disso, leia o QR atual. A chamada deve continuar aberta.

Fora do raio, nenhuma presença é gravada. Corrija a localização e tente novamente na mesma chamada; se o comprovante vencer, leia o QR atual. Depois de confirmada, a presença é mantida sem duplicação. Registros inválidos de versões anteriores também podem ser corrigidos enquanto a chamada estiver aberta.

## Conferir a localização

O raio é medido da coordenada institucional salva na abertura da sessão, não da posição do notebook. A migration já preenche coordenadas da AEMS; confira no admin se correspondem ao campus e se o raio atende à sala usada.

Em casa, uma chamada da AEMS deve rejeitar a tentativa por distância, sem gravar presença. Para testar em outro local, use uma instituição de teste com coordenadas reais desse local. Professores com várias instituições ainda não escolhem o campus ao iniciar a aula; confira qual foi usado.

## Roteiro de aceite

- [ ] Professor cria matéria, turma e aula; seleções e código correspondem à turma correta.
- [ ] Aluno entra por código; aluno de fora da turma não confirma presença.
- [ ] GPS dentro do raio registra presente e aparece no painel do professor.
- [ ] GPS fora do raio mostra erro sem gravar; uma nova tentativa dentro do raio confirma na mesma sessão.
- [ ] Negar GPS ou perder conexão não mostra falso sucesso nem falta automática.
- [ ] QR vencido pede nova leitura; rotação após leitura válida preserva o prazo do comprovante.
- [ ] Encerrar antes do processamento do registro impede a gravação. Em envios próximos ao encerramento, a ordem é definida pelo bloqueio no banco, não pela ordem visual dos cliques.
- [ ] Repetir envio não duplica nem altera uma presença já confirmada.
- [ ] QR gira automaticamente; ao perder conexão, a imagem vencida some e a renovação retoma após reconectar.
- [ ] Nenhuma requisição de imagem do QR vai para outro domínio.
- [ ] Conferir frequência e CSV manualmente com uma turma de dados conhecidos.
- [ ] Abrir uma chamada não altera a frequência; encerrá-la inclui as presenças e faltas dessa chamada nos relatórios.
- [ ] Fazer login novamente após a atualização; sair encerra a sessão, inclusive ao tentar reutilizar a página anterior.
- [ ] Cadastro aceita e-mail institucional e carrega instituições sem expor coordenadas na resposta pública.
- [ ] Testar Android/iPhone disponíveis, menu, formulários e páginas em tela pequena.
- [ ] Registrar data, dispositivo, navegador, rede, cenário e resultado real de cada ensaio.

O teste fora do raio relatado anteriormente usava a regra antiga de falta gravada. Repita o ensaio com a regra atual e documente o sucesso dentro do raio e a nova tentativa. A imagem do QR é gerada pelo próprio Django; os avisos não funcionam como push com navegador fechado.

## Ensaio de chamadas simultâneas

Use uma turma de teste, pois iniciar novas sessões influencia a frequência.

1. Abra o painel do mesmo professor em duas abas. Selecione a mesma aula e inicie nas duas: ambas devem usar a mesma sessão ativa.
2. Mantenha as duas abas abertas durante a troca do QR. Depois da renovação, ambas devem convergir para o mesmo token; o instante da atualização visual depende das consultas de cada aba.
3. Com alunos diferentes matriculados, leia o QR e confirme a localização em horários próximos. Confira um registro por aluno e os respectivos resultados.
4. Encerre a chamada em uma aba. A outra deve reconhecer o encerramento na próxima consulta, retirar o QR e manter os resultados finais.
5. Repita o envio de um aluno enquanto a sessão estiver aberta e o comprovante válido: a presença confirmada deve ser mantida, sem duplicação. Uma tentativa fora do raio deve permitir correção. Depois do encerramento, novos envios são rejeitados.
6. Encerre próximo ao envio de um aluno. Se o registro obtiver o bloqueio primeiro e passar nas validações, ele será salvo antes do encerramento; se o encerramento vencer, não haverá novo registro.
7. Troque rapidamente matéria, turma e aula durante carregamentos. Uma resposta antiga não deve substituir a seleção atual nem trazer de volta o QR anterior.

Registre o resultado do ensaio acima com os aparelhos reais que serão usados na apresentação. Para a configuração local, consulte o [Guia técnico](GUIA_TECNICO.md).
