window.Profile = (() => {
  let current = null;
  let previewUrl = null;
  let draft = { x: 50, y: 50, zoom: 1 };
  let dragging = null;
  let saving = false;
  const byId = id => document.getElementById(id);
  const initials = name => name.trim().split(/\s+/).map(word => word[0]).filter(Boolean).slice(0, 2).join('').toUpperCase();

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
  const defaultCrop = () => ({ x: 50, y: 50, zoom: 1 });
  function cropFrom(profile) {
    const number = (value, fallback, min, max) => Number.isFinite(Number(value)) ? clamp(Number(value), min, max) : fallback;
    return { x: number(profile.foto_posicao_x ?? 50, 50, 0, 100),
      y: number(profile.foto_posicao_y ?? 50, 50, 0, 100), zoom: number(profile.foto_zoom ?? 1, 1, 1, 3) };
  }
  function applyCrop(element, crop) {
    if (!element) return;
    element.style.setProperty('--photo-x', `${crop.x}%`);
    element.style.setProperty('--photo-y', `${crop.y}%`);
    element.style.setProperty('--photo-zoom', crop.zoom);
  }
  function avatar(element, name, source, crop = defaultCrop()) {
    if (!element) return;
    applyCrop(element, crop);
    element.textContent = initials(name);
    if (!source) return;
    const image = document.createElement('img');
    image.alt = '';
    image.draggable = false;
    image.src = source;
    image.addEventListener('error', () => { element.textContent = initials(name); });
    element.replaceChildren(image);
  }
  function releasePreview() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
  }
  function feedback(message = '', error = false) {
    const region = byId('profile-feedback');
    if (region) { region.textContent = message; region.dataset.kind = error ? 'error' : 'success'; }
  }
  function updateCrop(announce = false) {
    applyCrop(byId('profile-avatar'), draft);
    applyCrop(byId('profile-crop-stage'), draft);
    if (byId('profile-photo-zoom')) byId('profile-photo-zoom').value = draft.zoom;
    if (byId('profile-zoom-value')) byId('profile-zoom-value').textContent = `${Math.round(draft.zoom * 100)}%`;
    if (announce) feedback('Prévia do enquadramento. Clique em Salvar alterações para confirmar.');
  }
  function showCrop(open) {
    const editor = byId('profile-crop-editor');
    const button = byId('profile-photo-adjust');
    if (!editor || !button) return;
    editor.hidden = !open;
    button.setAttribute('aria-expanded', String(open));
    button.textContent = open ? 'Ocultar ajuste' : 'Ajustar enquadramento';
    if (open) {
      avatar(byId('profile-crop-stage'), current.nome, previewUrl || current.foto_url, draft);
      updateCrop();
    }
  }
  function stopDrag() {
    const stage = byId('profile-crop-stage');
    if (dragging && stage?.hasPointerCapture(dragging.id)) stage.releasePointerCapture(dragging.id);
    dragging = null;
    if (stage) stage.dataset.dragging = 'false';
  }
  function movePhoto(dx, dy) {
    const stage = byId('profile-crop-stage');
    const image = stage?.querySelector('img');
    if (!image?.naturalWidth || !image.naturalHeight || !stage.clientWidth || !stage.clientHeight) return;
    // O mesmo recorte proporcional é aplicado no editor, no perfil e no cabeçalho.
    const scale = Math.max(stage.clientWidth / image.naturalWidth, stage.clientHeight / image.naturalHeight) * draft.zoom;
    const overflowX = image.naturalWidth * scale - stage.clientWidth;
    const overflowY = image.naturalHeight * scale - stage.clientHeight;
    if (overflowX > 0.5) draft.x = clamp(draft.x - dx / overflowX * 100, 0, 100);
    if (overflowY > 0.5) draft.y = clamp(draft.y - dy / overflowY * 100, 0, 100);
    updateCrop();
  }
  function render(profile) {
    stopDrag();
    current = profile;
    draft = cropFrom(profile);
    releasePreview();
    if (byId('user-name')) byId('user-name').textContent = profile.nome;
    avatar(byId('user-avatar'), profile.nome, profile.foto_url, draft);
    avatar(byId('profile-avatar'), profile.nome, profile.foto_url, draft);
    const form = byId('profile-form');
    if (!form) return;
    form.hidden = false;
    byId('profile-name').value = profile.nome;
    byId('profile-photo').value = '';
    byId('profile-photo-remove').hidden = !profile.foto_url;
    byId('profile-photo-adjust').hidden = !profile.foto_url;
    showCrop(false);
    byId('profile-crop-stage').replaceChildren();
    updateCrop();
    const details = { Usuário: profile.username, 'E-mail': profile.email, Perfil: profile.role === 'professor' ? 'Professor' : 'Aluno',
      ...(profile.role === 'aluno' ? {'Matrícula': profile.matricula} : {'Instituições': profile.instituicoes.join(', ')}) };
    byId('profile-details').innerHTML = Object.entries(details).map(([key, value]) => `<dt>${UI.escape(key)}</dt><dd>${UI.escape(value || 'Não informado')}</dd>`).join('');
  }
  function busy(value) {
    saving = value;
    stopDrag();
    byId('profile-form').setAttribute('aria-busy', String(value));
    byId('profile-form').querySelectorAll('button, input').forEach(control => { control.disabled = value; });
    byId('profile-crop-stage').tabIndex = value ? -1 : 0;
    byId('profile-crop-stage').setAttribute('aria-disabled', String(value));
  }

  document.addEventListener('DOMContentLoaded', () => {
    const form = byId('profile-form');
    if (!form) return;
    const photoInput = byId('profile-photo');
    photoInput.addEventListener('change', () => {
      stopDrag();
      releasePreview();
      feedback();
      const photo = photoInput.files[0];
      if (photo && (photo.size > 5 * 1024 * 1024 || !['image/jpeg', 'image/png', 'image/webp'].includes(photo.type))) {
        photoInput.value = '';
        draft = cropFrom(current);
        avatar(byId('profile-avatar'), current.nome, current.foto_url, draft);
        byId('profile-photo-adjust').hidden = !current.foto_url;
        showCrop(false);
        updateCrop();
        feedback('Escolha uma foto JPG, PNG ou WebP de até 5 MB.', true);
        return;
      }
      previewUrl = photo ? URL.createObjectURL(photo) : null;
      draft = photo ? defaultCrop() : cropFrom(current);
      avatar(byId('profile-avatar'), current.nome, previewUrl || current.foto_url, draft);
      byId('profile-photo-adjust').hidden = !(previewUrl || current.foto_url);
      showCrop(Boolean(photo));
      updateCrop();
      if (photo) feedback('Prévia da nova foto. Clique em Salvar alterações para confirmar.');
    });
    byId('profile-photo-adjust').addEventListener('click', () => {
      showCrop(byId('profile-crop-editor').hidden);
    });
    byId('profile-photo-zoom').addEventListener('input', event => {
      draft.zoom = Number(event.target.value);
      updateCrop(true);
    });
    byId('profile-crop-reset').addEventListener('click', () => {
      draft = defaultCrop();
      updateCrop(true);
    });
    const stage = byId('profile-crop-stage');
    stage.addEventListener('pointerdown', event => {
      if (saving || dragging || event.button !== 0 || event.isPrimary === false) return;
      if (!stage.querySelector('img')?.naturalWidth) return;
      event.preventDefault();
      stage.focus({ preventScroll: true });
      stage.setPointerCapture(event.pointerId);
      dragging = { id: event.pointerId, x: event.clientX, y: event.clientY };
      stage.dataset.dragging = 'true';
    });
    stage.addEventListener('pointermove', event => {
      if (!dragging || dragging.id !== event.pointerId || saving) return;
      movePhoto(event.clientX - dragging.x, event.clientY - dragging.y);
      dragging.x = event.clientX;
      dragging.y = event.clientY;
    });
    stage.addEventListener('pointerup', event => {
      if (dragging?.id !== event.pointerId) return;
      stopDrag();
      updateCrop(true);
    });
    stage.addEventListener('pointercancel', stopDrag);
    stage.addEventListener('lostpointercapture', stopDrag);
    stage.addEventListener('keydown', event => {
      const step = event.shiftKey ? 20 : 5;
      const movement = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[event.key];
      if (!movement || saving) return;
      event.preventDefault();
      movePhoto(...movement);
      updateCrop(true);
    });
    byId('profile-cancel').addEventListener('click', () => { if (current) render(current); feedback(); });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const body = new FormData();
      body.append('nome', byId('profile-name').value.trim());
      if (photoInput.files[0]) body.append('foto', photoInput.files[0]);
      if (photoInput.files[0] || current.foto_url) {
        body.append('foto_posicao_x', draft.x);
        body.append('foto_posicao_y', draft.y);
        body.append('foto_zoom', draft.zoom);
      }
      busy(true); feedback('Salvando…');
      try {
        const profile = await Aura.json('/api/interface/perfil/', { method: 'PATCH', body });
        render(profile); feedback('Perfil atualizado.');
      } catch (error) { feedback(error.message, true); }
      finally { busy(false); }
    });
    byId('profile-photo-remove').addEventListener('click', async () => {
      const name = byId('profile-name').value;
      busy(true); feedback('Removendo foto…');
      try {
        render(await Aura.json('/api/interface/perfil/foto/', { method: 'DELETE' }));
        byId('profile-name').value = name;
        feedback('Foto removida.');
      } catch (error) { feedback(error.message, true); }
      finally { busy(false); }
    });
    window.addEventListener('pagehide', releasePreview);
  });
  return { render };
})();
