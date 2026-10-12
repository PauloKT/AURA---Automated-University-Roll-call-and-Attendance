document.addEventListener('DOMContentLoaded', function() {
  const form = document.getElementById('register-form');
  const errorMessage = document.getElementById('error-message');
  const successMessage = document.getElementById('success-message');
  const roleSelect = document.getElementById('role');
  const matriculaGroup = document.getElementById('matricula-group');
  const institutionGroup = document.getElementById('institution-group');
  const institutionSelect = document.getElementById('instituicao');
  const newInstitutionToggle = document.getElementById('new-institution-toggle');
  const newInstitutionFields = document.getElementById('new-institution-fields');
  let addingInstitution = false;

  loadInstitutions();
  function updateFields() {
    const isTeacher = roleSelect.value === 'professor';
    const adding = isTeacher && addingInstitution;
    document.getElementById('matricula').required = !isTeacher;
    document.getElementById('matricula').disabled = isTeacher;
    matriculaGroup.hidden = isTeacher;
    institutionGroup.hidden = !isTeacher;
    institutionSelect.required = isTeacher && !adding;
    institutionSelect.disabled = !isTeacher || adding;
    newInstitutionFields.hidden = !adding;
    newInstitutionFields.disabled = !adding;
    newInstitutionToggle.setAttribute('aria-expanded', String(adding));
    newInstitutionToggle.textContent = adding ? 'Selecionar instituição existente' : 'Adicionar nova instituição';
  }
  roleSelect.addEventListener('change', updateFields);
  newInstitutionToggle.addEventListener('click', function() {
    addingInstitution = !addingInstitution;
    updateFields();
    (addingInstitution ? document.getElementById('institution-name') : institutionSelect).focus();
  });
  updateFields();

  form.addEventListener('submit', async function(e) {
    e.preventDefault();
    errorMessage.classList.remove('show');
    errorMessage.textContent = '';
    successMessage.classList.remove('show');
    successMessage.textContent = '';
    const formData = new FormData(form);
    const username = formData.get('username').trim();
    const email = formData.get('email').trim();
    const password = formData.get('password');
    const password2 = formData.get('password2');
    const role = formData.get('role');
    const matricula = role === 'aluno' ? formData.get('matricula').trim() : undefined;
    const adding = role === 'professor' && addingInstitution;
    const instituicoes = role === 'professor' && !adding
      ? Array.from(institutionSelect.selectedOptions)
        .map(option => Number(option.value))
        .filter(Boolean)
      : undefined;
    if (!username) {
      showError('Usuário é obrigatório');
      return;
    }

    if (!email) {
      showError('E-mail é obrigatório');
      return;
    }

    if (!password) {
      showError('Senha é obrigatória');
      return;
    }

    if (password !== password2) {
      showError('Senhas não coincidem');
      return;
    }

    if (role === 'aluno' && !matricula) {
      showError('Matrícula é obrigatória para alunos');
      return;
    }

    if (role === 'professor' && !adding && !instituicoes.length) {
      showError('Selecione ao menos uma instituição');
      return;
    }
    const data = {
      username: username,
      email: email,
      password: password,
      password2: password2,
      role: role
    };

    if (matricula !== undefined) {
      data.matricula = matricula;
    }


    if (instituicoes !== undefined) {
      data.instituicoes = instituicoes;
    }
    if (adding) {
      data.nova_instituicao = {};
      ['nome', 'logradouro', 'numero', 'bairro', 'cidade', 'estado'].forEach(field => {
        data.nova_instituicao[field] = (formData.get(`institution_${field}`) || '').trim();
      });
      data.nova_instituicao.estado = data.nova_instituicao.estado.toUpperCase();
    }

    try {
      const button = form.querySelector('button[type="submit"]');
      button.disabled = true;
      button.textContent = 'Criando conta…';
      const response = await Aura.request('/api/register/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const firstError =
          errorData.detail ||
          errorData.erro ||
          firstErrorMessage(errorData) ||
          'Erro ao cadastrar';
        throw new Error(firstError);
      }

      showSuccess(adding
        ? 'Conta e instituição cadastradas! Faça login. Para iniciar chamadas nesse campus, peça ao administrador que confirme a localização da instituição.'
        : 'Cadastro realizado com sucesso! Faça login.');
      if (!adding) {
        const next = new URLSearchParams(location.search).get('next');
        setTimeout(() => { window.location.href = '/login.html' + (next ? '?next=' + encodeURIComponent(next) : ''); }, 2000);
      } else {
        form.hidden = true;
      }
    } catch (error) {
      showError(error.message);
    } finally {
      const button = form.querySelector('button[type="submit"]');
      button.disabled = false;
      button.textContent = 'Criar minha conta';
    }
  });

  function showError(message) {
    errorMessage.textContent = message;
    errorMessage.classList.add('show');
  }

  function firstErrorMessage(value) {
    if (typeof value === 'string') return value;
    if (value && typeof value === 'object') {
      return Object.values(value).map(firstErrorMessage).find(Boolean);
    }
    return '';
  }

  function showSuccess(message) {
    successMessage.textContent = message;
    successMessage.classList.add('show');
  }

  async function loadInstitutions() {
    try {
      const response = await fetch('/api/instituicoes/catalogo/');
      if (!response.ok) throw new Error('Não foi possível carregar as instituições.');
      const data = await response.json();
      institutionSelect.innerHTML = '<option value="" disabled>Selecione uma instituição</option>';
      data.forEach(institution => {
        const option = document.createElement('option');
        option.value = institution.id;
        option.textContent = `${institution.nome} - ${institution.cidade}/${institution.estado}`;
        option.disabled = !institution.localizacao_confirmada;
        if (option.disabled) option.textContent += ' (localização pendente)';
        institutionSelect.appendChild(option);
      });
      if (!data.length) institutionSelect.innerHTML = '<option value="" disabled>Nenhuma instituição cadastrada. Adicione a sua abaixo.</option>';
    } catch (error) {
      institutionSelect.innerHTML = '<option value="">Erro ao carregar instituições</option>';
      showError(error.message);
    }
  }
});
