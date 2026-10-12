# Dados para demonstração e prints

Revisado em **12/10/2026**.

O comando `seed_demo` cria um cenário fictício no banco configurado do AURA. Ele usa os modelos e os cálculos normais do sistema; os indicadores das telas vêm dos registros de chamadas e presenças.

## Cenário

- 3 instituições: Centro Universitário Horizonte, Instituto Superior Vale Verde e Faculdade Nova Aurora.
- 4 professores e 24 alunos, com nomes completos e matrículas.
- 6 matérias: Banco de Dados II, Desenvolvimento Web, Engenharia de Software, Redes de Computadores, Interação Humano-Computador e Algoritmos e Programação.
- 8 turmas, 122 vínculos, 72 aulas, 56 chamadas encerradas e 714 presenças.
- Oito semanas de histórico, encontros futuros e uma oficina sem chamadas.

Os nomes, endereços e coordenadas são fictícios. Os e-mails usam `@demo.aura.test`, os códigos das matérias começam com `DEMO-` e as instituições usam a origem `aura-demo-v1`. Esses identificadores permitem distinguir a demonstração dos cadastros reais. As contas não têm acesso administrativo.

## Contas para os prints

**Mariana Costa** (`mariana-costa@demo.aura.test`) é a professora principal. Ela tem três matérias, cinco turmas e relatórios com alunos regulares, alunos em atenção e uma turma sem chamadas. Os demais professores são Rafael Almeida, Camila Rocha e André Nogueira.

**Lucas Martins** (`lucas-martins@demo.aura.test`) é o aluno principal. Seu painel mostra 100% em Banco de Dados II, 87,5% em Desenvolvimento Web, 75% em Engenharia de Software e 50% em Redes de Computadores. A Oficina de Projetos aparece sem chamadas. A frequência geral inicial é 78,125%, exibida como **78,1%** na interface.

É possível entrar pelo nome completo ou pelo e-mail. A senha das contas novas é exibida no terminal ao executar `seed_demo`. Os cadastros e as senhas não acompanham o repositório: depois de clonar o projeto ou limpar o banco, execute o comando para recriar o cenário.

## Roteiro sugerido

1. Entre como Mariana Costa e capture o início com os indicadores e a agenda.
2. Abra **Matérias** e **Turmas** para mostrar os cadastros preenchidos.
3. Abra **Relatórios**, selecione uma turma e alterne entre **Todas**, **Regular** e **Atenção**.
4. Em uma turma, abra as abas **Alunos**, **Aulas** e **Frequência**.
5. Use **Exportar CSV** no relatório para apresentar as contagens de chamadas, presenças e faltas da turma.
6. Entre como Lucas Martins e capture **Início**, **Turmas** e **Frequência**, também no celular.
7. As instituições aparecem nas opções do cadastro e na administração, acessada com uma conta administrativa já existente.

As faltas aparecem nos relatórios por ausência de presença em chamadas encerradas. O carregamento não cria registros de GPS inválido para simular faltas e não deixa chamadas abertas. Para mostrar um QR ao vivo, inicie uma chamada de uma aula futura pelo fluxo normal. Para registrar presença pelo celular, configure antes as coordenadas reais do local na instituição usada pelo professor; as coordenadas fictícias servem para os dados da demonstração, não para validar a localização do seu aparelho.

Capturas, exportações e arquivos de acesso podem ser guardados em `output/demonstracao/`, que fica fora do Git. A pasta `output/` inteira contém artefatos locais e não é necessária para executar o site.

## Criar ou executar novamente

Na primeira instalação, prepare a `.venv`, as dependências e o `.env` conforme o [README](../README.md). O banco precisa estar migrado antes de carregar os dados. Na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe backend/manage.py prepare_local
.\.venv\Scripts\python.exe backend/manage.py seed_demo
```

`prepare_local` faz backup do banco existente e aplica migrations; `seed_demo` cria o cenário. Nenhum deles cria administrador: para acessar `/admin/`, use `.\.venv\Scripts\python.exe backend/manage.py createsuperuser` caso ainda não tenha uma conta administrativa.

O cenário usa datas relativas à primeira execução, com oito semanas de histórico e duas aulas futuras por turma. Reexecutar não desloca as datas existentes nem redefine senhas. O comando cria os cadastros previstos quando ausentes e preserva aulas que já possuem chamadas; não reconstrói presenças removidas dessas sessões. Se um nome, e-mail ou identificador reservado conflitar com outro cadastro nas verificações de propriedade, cancela toda a transação.

A senha é aleatória e exibida apenas para as contas novas. Opcionalmente, `AURA_DEMO_PASSWORD` pode definir a senha dessas novas contas no ambiente do processo; não é necessário alterar o `.env`. O comando não salva um arquivo de acessos nem gera backup automaticamente. Guarde a saída da primeira execução localmente; uma reexecução sem contas novas não exibirá as senhas anteriores.

O comando cria a demonstração no banco em uso. Ele não exclui os registros ao terminar e não é uma migração de banco.

## Validação

```powershell
.\.venv\Scripts\python.exe backend/manage.py test courses.test_demo attendance.test_frequency --testrunner accounts.browser_profiles.BrowserTestRunner --noinput
```

Os testes usam um banco temporário e verificam histórico, relatórios, frequências esperadas, repetição em outra data, preservação de senhas e cancelamento em caso de conflito com um cadastro existente.
