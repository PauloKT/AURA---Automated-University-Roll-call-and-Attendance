document.addEventListener('DOMContentLoaded', function() {
  const form = document.getElementById('login-form');
  const errorDiv = document.getElementById('error-message');

  form.addEventListener('submit', async function(e) {
    e.preventDefault();

    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    errorDiv.textContent = '';
    errorDiv.classList.remove('show');
    if (!username || !password) {
      errorDiv.textContent = 'Por favor, preencha todos os campos';
      errorDiv.classList.add('show');
      return;
    }

    try {
      const button = form.querySelector('button[type="submit"]');
      if (button) { button.disabled = true; button.textContent = 'Entrando…'; }
      const data = await Aura.json('/api/auth/login/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: username,
          password: password
        })
      });

      const requested = new URLSearchParams(window.location.search).get('next');
      if (requested) {
        const destination = new URL(requested, window.location.origin);
        if (destination.origin === window.location.origin &&
            ['/aluno.html', '/confirmar-presenca.html'].includes(destination.pathname) &&
            data.user?.role === 'aluno') {
          window.location.href = destination.pathname + destination.search;
          return;
        }
      }
      window.location.href = data.user.role === 'professor' ? 'professor.html' : 'aluno.html';

    } catch (error) {
      errorDiv.textContent = error.message || 'Erro ao fazer login';
      errorDiv.classList.add('show');
    } finally {
      const button = form.querySelector('button[type="submit"]');
      if (button) { button.disabled = false; button.textContent = 'Entrar na minha conta'; }
    }
  });
});
