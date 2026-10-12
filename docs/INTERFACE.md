# Interface do AURA

Revisado em **12/10/2026**.

A identidade mantém o azul `#153e56`, o verde `#007d68`, o logo e o globo. A fonte Manrope está em `frontend/fonts`, junto da licença; o navegador carrega a fonte pelo próprio AURA.

## Onde ajustar

O índice no começo de `frontend/app.css` aponta para cada seção:

- **01:** cores, fonte e largura máxima do conteúdo.
- **03:** cabeçalho, acesso ao perfil, saída da conta e navegação entre páginas.
- **07:** painéis, indicadores e cartões.
- **11:** filtros, tabelas e abas.
- **14:** login e cadastro.
- **17:** geolocalização e tamanho do globo no computador.
- **18:** telas de até 1050px, celular até 700px, telas estreitas até 360px e movimento reduzido. O tamanho do globo no celular também fica aqui.
- **19:** perfil e enquadramento da foto.
- **20:** ajustes do perfil em telas de até 600px e 480px, e estilos de impressão.
- **21:** foco do teclado e formulário de cadastro de instituição.

A mesma navegação fica abaixo do cabeçalho no computador e na parte inferior no celular. A altura da barra e a área segura do aparelho são compensadas no conteúdo. Em telas baixas, ela volta ao fluxo normal da página para liberar espaço para os formulários.

No computador, os links dividem a largura disponível e o botão **Sair da conta** fica à direita. No celular, a saída fica no cabeçalho, ao lado da foto, para preservar o espaço dos destinos na barra inferior. A foto abre **Meu perfil**. O menu hambúrguer foi removido para evitar navegação duplicada.

O item da página atual mostra o pin de `frontend/geo-pin.svg` no lugar do ícone da seção, tanto no computador quanto no celular. O indicador acompanha `aria-current="page"`, atualizado pela navegação; o tamanho e a máscara ficam na seção 03 do CSS, com o tamanho do celular na seção 18.

Os relatórios usam a tabela semântica de `UI.frequencyTable` em `frontend/ui.js`. No celular, cada registro é disposto verticalmente, com rótulos visíveis para as quantidades. Os dados e os cabeçalhos continuam sendo os mesmos da versão para computador.

Os ícones reutilizados pelos templates ficam em `backend/templates/includes/icon.html`; os criados pelo JavaScript usam `UI.icon` em `frontend/ui.js`. A marca é incluída por `backend/templates/includes/brand.html`, com os arquivos visuais publicados a partir de `frontend/`. A pasta `output/` guarda apenas capturas e propostas locais e não faz parte dos recursos carregados pelo site.

## Verificação no navegador

Com Playwright instalado no ambiente Python e Chrome disponível:

```powershell
.\.venv\Scripts\python.exe backend/manage.py test accounts.browser_layout accounts.browser_profiles --testrunner accounts.browser_profiles.BrowserTestRunner --noinput
```

Os testes usam banco temporário. Cobrem navegação por toque e teclado, nomes longos, relatórios, entrada em turma, criação de matéria em tela baixa e edição da foto. As larguras verificadas são 320, 390, 768 e 1366 pixels. A emulação de tela baixa não substitui uma conferência do teclado virtual em aparelho físico.

Para instalar o pacote de testes, use `.\.venv\Scripts\python.exe -m pip install playwright`. O Chrome deve estar instalado separadamente. Capturas produzidas pelos testes ficam em `output/`, fora do Git. Para preencher as telas do site com dados fictícios, consulte [Demonstração](DEMONSTRACAO.md).
