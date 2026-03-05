/**
 * Ito Merchandising App — Main application controller.
 * 4-Step Visit Workflow (v2).
 */

document.addEventListener('DOMContentLoaded', () => {
  if (!isLoggedIn()) {
    showLogin();
  } else {
    showApp();
  }
});

// ── Toast notification ──────────────────────────────────────────────────
function toast(msg, duration = 3000) {
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), duration);
}

// ── Login ───────────────────────────────────────────────────────────────
function showLogin() {
  document.getElementById('app').style.display = 'none';
  document.getElementById('login-page').style.display = 'flex';
}

async function handleLogin(e) {
  e.preventDefault();
  const username = document.getElementById('login-user').value;
  const password = document.getElementById('login-pass').value;
  const btn = e.target.querySelector('button');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>';
  try {
    const data = await apiPost('/auth/login', { username, password });
    setAuth(data);
    showApp();
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Iniciar Sesión';
  }
}

function handleLogout() {
  clearAuth();
  showLogin();
}

// ── App shell ───────────────────────────────────────────────────────────
function showApp() {
  document.getElementById('login-page').style.display = 'none';
  document.getElementById('app').style.display = 'block';
  document.getElementById('header-name').textContent = getUserName();

  const isAdmin = getUserRole() === 'admin';

  // Show admin-only tabs (Por Ruta, Dashboard, Admin)
  const navRouteHistory = document.getElementById('nav-route-history');
  const navDashboard = document.getElementById('nav-dashboard');
  const navAdmin = document.getElementById('nav-admin');

  if (navRouteHistory) navRouteHistory.style.display = isAdmin ? 'block' : 'none';
  if (navDashboard) navDashboard.style.display = isAdmin ? 'block' : 'none';
  if (navAdmin) navAdmin.style.display = isAdmin ? 'block' : 'none';

  navigateTo('visit');
}

// ── Navigation ──────────────────────────────────────────────────────────
function navigateTo(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-tabs button').forEach(b => b.classList.remove('active'));

  const pageEl = document.getElementById(`page-${page}`);
  const tabEl = document.querySelector(`[data-page="${page}"]`);
  if (pageEl) pageEl.classList.add('active');
  if (tabEl) tabEl.classList.add('active');

  switch (page) {
    case 'visit': loadVisitPage(); break;
    case 'route-history': loadRouteHistoryPage(); break;
    case 'dashboard': loadDashboardPage(); break;
    case 'approvals': loadApprovalsPage(); break;
    case 'admin': loadAdminPage(); break;
  }
}

// ══════════════════════════════════════════════════════════════════════════
// ═══ STORE VISIT — 4-Step Workflow (v2) ═══════════════════════════════════
// ══════════════════════════════════════════════════════════════════════════

let visitState = {
  step: 0,
  visitId: null,
  storeId: null,
  storeName: '',
  approvedSkus: [],
  skuActions: {},            // { skuId: Set of actions }
  ordenQuantities: {},       // { skuId: quantity } for orden actions
  selectedSkus: new Set(),   // Currently selected SKU IDs for bulk actions
  gondolaGroups: [],         // Array of { groupId, skuIds, beforePhoto, afterPhoto }
  conditions: { prices: null, pop: null, clean: null },
  conditionNotes: '',
  photos: { arrival: null },
  gps: { lat: null, lng: null, accuracy: null },
};

function resetVisitState() {
  visitState = {
    step: 0,
    visitId: null,
    storeId: null,
    storeName: '',
    approvedSkus: [],
    skuActions: {},
    ordenQuantities: {},
    selectedSkus: new Set(),
    gondolaGroups: [],
    conditions: { prices: null, pop: null, clean: null },
    conditionNotes: '',
    photos: { arrival: null },
    gps: { lat: null, lng: null, accuracy: null },
  };
}

async function loadVisitPage() {
  resetVisitState();
  showStep(0);

  try {
    const stores = await apiGet('/stores/');
    const sel = document.getElementById('visit-store-select');
    sel.innerHTML = '<option value="">Seleccione una tienda...</option>' +
      stores.map(s => `<option value="${s.id}" data-name="${s.name}">${s.name} (${s.region})</option>`).join('');
  } catch (err) {
    toast('Error cargando tiendas');
  }

  // Clear arrival preview
  const arrivalPreview = document.getElementById('arrival-preview');
  if (arrivalPreview) arrivalPreview.innerHTML = '';

  // Reset condition buttons
  document.querySelectorAll('.toggle-btn').forEach(btn => {
    btn.classList.remove('selected-yes', 'selected-no');
  });
  document.getElementById('condition-notes-group').style.display = 'none';
  document.getElementById('condition-notes').value = '';
  document.getElementById('visit-notes').value = '';

  // Reset bulk toolbar
  updateBulkToolbar();
  updatePendingWarning();
  updateGondolaGroupsSummary();

  // Disable step 1 next button
  const btn1 = document.getElementById('btn-step1-next');
  if (btn1) btn1.disabled = true;

  // Disable step 3 next button
  const btn3 = document.getElementById('btn-step3-next');
  if (btn3) btn3.disabled = true;
}

function showStep(stepNum) {
  visitState.step = stepNum;

  // Hide all steps
  document.querySelectorAll('.visit-step').forEach(el => el.classList.remove('active'));

  // Show current step
  const stepEl = document.getElementById(`visit-step-${stepNum}`);
  if (stepEl) stepEl.classList.add('active');

  // Update step indicator (4 steps)
  document.querySelectorAll('.step-indicator .step').forEach(el => {
    const s = parseInt(el.dataset.step);
    el.classList.remove('active', 'completed');
    if (s < stepNum) el.classList.add('completed');
    else if (s === stepNum) el.classList.add('active');
  });

  // Load step-specific data
  if (stepNum === 2) loadSKUList();
  if (stepNum === 4) showVisitSummary();
}

function nextStep() {
  showStep(visitState.step + 1);
}

function validateStep2AndNext() {
  // Check if there are any gondola groups with missing after photos
  const pendingGroups = visitState.gondolaGroups.filter(g => !g.afterPhoto);

  if (pendingGroups.length > 0) {
    toast(`Faltan ${pendingGroups.length} foto(s) DESPUÉS. Complete todos los grupos antes de continuar.`);
    return;
  }

  // All groups complete (or no groups created), proceed to next step
  nextStep();
}

// ── Step 0 → 1: Start Visit ─────────────────────────────────────────────

async function startVisit() {
  const sel = document.getElementById('visit-store-select');
  const storeId = sel.value;
  if (!storeId) { toast('Seleccione una tienda'); return; }

  visitState.storeId = parseInt(storeId);
  visitState.storeName = sel.options[sel.selectedIndex].dataset.name || sel.options[sel.selectedIndex].text;

  // Get GPS
  try {
    const pos = await new Promise((resolve, reject) =>
      navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 10000, enableHighAccuracy: true })
    );
    visitState.gps = {
      lat: pos.coords.latitude,
      lng: pos.coords.longitude,
      accuracy: pos.coords.accuracy,
    };
  } catch { /* GPS unavailable */ }

  // Create visit on server
  try {
    const resp = await apiPost('/visits/start', {
      store_id: visitState.storeId,
      latitude: visitState.gps.lat,
      longitude: visitState.gps.lng,
      gps_accuracy: visitState.gps.accuracy,
    });
    visitState.visitId = resp.visit_id;
    showStep(1);
  } catch (err) {
    toast('Error iniciando visita: ' + err.message);
  }
}

// ── Photo Capture ───────────────────────────────────────────────────────

function capturePhoto(photoType) {
  const input = document.getElementById('camera-arrival');
  input.dataset.photoType = photoType;
  input.onchange = (e) => onArrivalPhotoSelected(e.target);
  input.click();
}

async function onArrivalPhotoSelected(input) {
  const file = input.files[0];
  if (!file) return;

  visitState.photos.arrival = file;

  // Show preview
  const preview = document.getElementById('arrival-preview');
  preview.innerHTML = `<img src="${URL.createObjectURL(file)}">`;

  // Upload to server
  try {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('photo_type', 'arrival_proof');
    formData.append('latitude', visitState.gps.lat || '');
    formData.append('longitude', visitState.gps.lng || '');
    formData.append('gps_accuracy', visitState.gps.accuracy || '');
    formData.append('captured_at', new Date().toISOString());
    formData.append('run_cv', 'false');

    await api(`/visits/${visitState.visitId}/photos`, { method: 'POST', body: formData });
    toast('Foto guardada');

    // Enable next button
    document.getElementById('btn-step1-next').disabled = false;
  } catch (err) {
    toast('Error subiendo foto: ' + err.message);
  }
}

// ── Gondola Photo Capture (Before/After) ────────────────────────────────

function captureGondolaBefore() {
  if (visitState.selectedSkus.size === 0) {
    toast('Seleccione SKUs primero');
    return;
  }
  const input = document.getElementById('camera-gondola-before');
  input.onchange = (e) => onGondolaBeforeSelected(e.target);
  input.click();
}

async function onGondolaBeforeSelected(input) {
  const file = input.files[0];
  if (!file) return;

  // Generate a new gondola group ID
  const groupId = crypto.randomUUID ? crypto.randomUUID() : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0;
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });

  // Get selected SKU IDs
  const skuIds = Array.from(visitState.selectedSkus);

  // Create local gondola group record
  const group = {
    groupId: groupId,
    skuIds: [...skuIds],
    beforePhoto: URL.createObjectURL(file),
    afterPhoto: null,
  };
  visitState.gondolaGroups.push(group);

  // Upload to server
  try {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('photo_type', 'gondola_before');
    formData.append('gondola_group_id', groupId);
    formData.append('sku_ids', skuIds.join(','));
    formData.append('latitude', visitState.gps.lat || '');
    formData.append('longitude', visitState.gps.lng || '');
    formData.append('gps_accuracy', visitState.gps.accuracy || '');
    formData.append('captured_at', new Date().toISOString());
    formData.append('run_cv', 'false');  // Disabled for MVP

    await api(`/visits/${visitState.visitId}/photos`, { method: 'POST', body: formData });
    toast('Foto ANTES guardada');

    // Clear selection after taking before photo
    clearSkuSelection();

    // Update UI
    updatePendingWarning();
    updateGondolaGroupsSummary();
  } catch (err) {
    toast('Error subiendo foto: ' + err.message);
    // Remove the group on error
    visitState.gondolaGroups.pop();
  }
}

function captureGondolaAfter() {
  // Find groups that need after photos
  const pendingGroups = visitState.gondolaGroups.filter(g => !g.afterPhoto);
  if (pendingGroups.length === 0) {
    toast('No hay fotos ANTES pendientes');
    return;
  }

  // If only one pending group, take photo directly
  if (pendingGroups.length === 1) {
    triggerAfterPhotoCapture(pendingGroups[0].groupId);
    return;
  }

  // Multiple pending groups: show picker
  showGondolaPicker(pendingGroups);
}

function showGondolaPicker(pendingGroups) {
  const grid = document.getElementById('gondola-picker-grid');

  grid.innerHTML = pendingGroups.map((group, idx) => {
    const skuNames = group.skuIds.map(id => {
      const sku = visitState.approvedSkus.find(s => s.id === id);
      return sku ? sku.name : `SKU #${id}`;
    }).slice(0, 2).join(', ') + (group.skuIds.length > 2 ? ` (+${group.skuIds.length - 2})` : '');

    return `
      <div class="gondola-picker-item" onclick="selectGondolaForAfter('${group.groupId}')">
        <img class="picker-thumbnail" src="${group.beforePhoto}" alt="Antes">
        <div class="picker-label">Grupo ${visitState.gondolaGroups.indexOf(group) + 1}</div>
        <div class="picker-skus">${skuNames}</div>
      </div>
    `;
  }).join('');

  document.getElementById('modal-gondola-picker').style.display = 'flex';
}

function selectGondolaForAfter(groupId) {
  closeModal('modal-gondola-picker');
  triggerAfterPhotoCapture(groupId);
}

function triggerAfterPhotoCapture(groupId) {
  const input = document.getElementById('camera-gondola-after');
  input.dataset.groupId = groupId;
  input.onchange = (e) => onGondolaAfterSelected(e.target, groupId);
  input.click();
}

async function onGondolaAfterSelected(input, groupId) {
  const file = input.files[0];
  if (!file) return;

  // Find the group
  const group = visitState.gondolaGroups.find(g => g.groupId === groupId);
  if (!group) return;

  group.afterPhoto = URL.createObjectURL(file);

  // Upload to server
  try {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('photo_type', 'gondola_after');
    formData.append('gondola_group_id', groupId);
    formData.append('sku_ids', group.skuIds.join(','));
    formData.append('latitude', visitState.gps.lat || '');
    formData.append('longitude', visitState.gps.lng || '');
    formData.append('gps_accuracy', visitState.gps.accuracy || '');
    formData.append('captured_at', new Date().toISOString());
    formData.append('run_cv', 'false');  // Disabled for MVP

    await api(`/visits/${visitState.visitId}/photos`, { method: 'POST', body: formData });
    toast('Foto DESPUÉS guardada');

    // Update UI
    updatePendingWarning();
    updateGondolaGroupsSummary();
  } catch (err) {
    toast('Error subiendo foto: ' + err.message);
    group.afterPhoto = null;
  }
}

// ── Step 3: Condition Checks ────────────────────────────────────────────

function setCondition(field, value, btn) {
  visitState.conditions[field] = value;

  // Update button styles
  btn.parentElement.querySelectorAll('.toggle-btn').forEach(b => {
    b.classList.remove('selected-yes', 'selected-no');
  });
  btn.classList.add(value ? 'selected-yes' : 'selected-no');

  // Show notes field if any "No"
  const anyNo = Object.values(visitState.conditions).some(v => v === false);
  document.getElementById('condition-notes-group').style.display = anyNo ? 'block' : 'none';

  // Enable next if all answered
  const allAnswered = Object.values(visitState.conditions).every(v => v !== null);
  document.getElementById('btn-step3-next').disabled = !allAnswered;
}

// ── Step 2: SKU List with Checkboxes ────────────────────────────────────

async function loadSKUList() {
  try {
    const approvals = await apiGet(`/approvals/?store_id=${visitState.storeId}`);
    visitState.approvedSkus = approvals.map(a => a.sku);

    const skuList = document.getElementById('visit-sku-list');
    if (approvals.length === 0) {
      skuList.innerHTML = '<p class="meta">No hay SKUs aprobados para esta tienda.</p>';
    } else {
      skuList.innerHTML = approvals.map(a => `
        <li class="sku-item" data-sku-id="${a.sku.id}" id="sku-item-${a.sku.id}">
          <input type="checkbox" class="sku-checkbox" id="sku-check-${a.sku.id}"
                 onchange="toggleSkuSelection(${a.sku.id}, this.checked)">
          <div class="sku-info">
            <span class="sku-name">${a.sku.name}</span>
            <span class="sku-meta">${a.sku.brand}${a.sku.category ? ' · ' + a.sku.category : ''}</span>
          </div>
          <div class="action-chips" id="chips-${a.sku.id}">
            <span class="chip chip-llena" data-action="gondola_llena" onclick="toggleAction(${a.sku.id},'gondola_llena',this)">Llena</span>
            <span class="chip chip-relleno" data-action="se_relleno" onclick="toggleAction(${a.sku.id},'se_relleno',this)">Rellenó</span>
            <span class="chip chip-orden" data-action="orden" onclick="toggleAction(${a.sku.id},'orden',this)">Orden</span>
            <span class="chip chip-agotado" data-action="agotado" onclick="toggleAction(${a.sku.id},'agotado',this)">Agotado</span>
          </div>
        </li>
      `).join('');
    }

    // Reset selection state
    visitState.selectedSkus.clear();
    updateBulkToolbar();
    updatePendingWarning();
    updateGondolaGroupsSummary();
  } catch (err) {
    toast('Error cargando SKUs');
  }
}

// ── SKU Selection for Bulk Actions ──────────────────────────────────────

function toggleSkuSelection(skuId, selected) {
  if (selected) {
    visitState.selectedSkus.add(skuId);
    document.getElementById(`sku-item-${skuId}`)?.classList.add('selected');
  } else {
    visitState.selectedSkus.delete(skuId);
    document.getElementById(`sku-item-${skuId}`)?.classList.remove('selected');
  }
  updateBulkToolbar();
}

function clearSkuSelection() {
  visitState.selectedSkus.forEach(skuId => {
    const checkbox = document.getElementById(`sku-check-${skuId}`);
    if (checkbox) checkbox.checked = false;
    document.getElementById(`sku-item-${skuId}`)?.classList.remove('selected');
  });
  visitState.selectedSkus.clear();
  updateBulkToolbar();
}

function updateBulkToolbar() {
  const count = visitState.selectedSkus.size;
  document.getElementById('selected-count').textContent = count;

  // Enable/disable bulk action buttons
  const hasSelection = count > 0;
  document.getElementById('btn-gondola-before').disabled = !hasSelection;
  document.getElementById('btn-clear-selection').disabled = !hasSelection;

  // After photo button enabled only if there are pending groups
  const pendingGroups = visitState.gondolaGroups.filter(g => !g.afterPhoto);
  document.getElementById('btn-gondola-after').disabled = pendingGroups.length === 0;
}

function updatePendingWarning() {
  const pendingGroups = visitState.gondolaGroups.filter(g => !g.afterPhoto);
  const warningEl = document.getElementById('pending-warning');
  const countEl = document.getElementById('pending-count');

  if (pendingGroups.length > 0) {
    countEl.textContent = pendingGroups.length;
    warningEl.style.display = 'flex';
  } else {
    warningEl.style.display = 'none';
  }
}

function updateGondolaGroupsSummary() {
  const container = document.getElementById('gondola-groups-summary');
  if (visitState.gondolaGroups.length === 0) {
    container.innerHTML = '';
    return;
  }

  container.innerHTML = '<h4 style="margin-bottom:8px;font-size:14px;">Grupos de Góndola</h4>' +
    visitState.gondolaGroups.map((group, idx) => {
      const isPending = !group.afterPhoto;
      const skuNames = group.skuIds.map(id => {
        const sku = visitState.approvedSkus.find(s => s.id === id);
        return sku ? sku.name : `SKU #${id}`;
      }).slice(0, 3).join(', ') + (group.skuIds.length > 3 ? ` (+${group.skuIds.length - 3})` : '');

      return `
        <div class="gondola-group-card ${isPending ? 'pending' : 'complete'}">
          <div class="gondola-group-header">
            <span class="group-label">Grupo ${idx + 1}</span>
            <span class="group-status ${isPending ? 'pending' : 'complete'}">
              ${isPending ? 'Pendiente DESPUÉS' : 'Completo'}
            </span>
          </div>
          <div class="gondola-group-skus">${skuNames}</div>
          <div class="gondola-group-photos">
            ${group.beforePhoto ? `<img src="${group.beforePhoto}" alt="Antes">` : '<div class="photo-placeholder">ANTES</div>'}
            ${group.afterPhoto ? `<img src="${group.afterPhoto}" alt="Después">` : '<div class="photo-placeholder">DESPUÉS</div>'}
          </div>
        </div>
      `;
    }).join('');
}

/**
 * Toggle SKU action with multi-select and business rules:
 * Rule 1: Llena, Rellenó, Orden can be combined freely
 * Rule 2: Agotado disables Llena/Rellenó, only allows Orden
 */
function toggleAction(skuId, action, el) {
  const key = `${skuId}`;

  // Initialize actions set for this SKU if needed
  if (!visitState.skuActions[key]) {
    visitState.skuActions[key] = new Set();
  }

  const actions = visitState.skuActions[key];
  const chipsContainer = document.getElementById(`chips-${skuId}`);

  if (action === 'agotado') {
    if (actions.has('agotado')) {
      // Deselecting Agotado - remove and re-enable Llena/Rellenó
      actions.delete('agotado');
      el.classList.remove('selected');
      enableChips(chipsContainer, ['gondola_llena', 'se_relleno']);
    } else {
      // Selecting Agotado - disable Llena/Rellenó
      actions.add('agotado');
      el.classList.add('selected');
      // Remove and disable Llena/Rellenó
      actions.delete('gondola_llena');
      actions.delete('se_relleno');
      disableChips(chipsContainer, ['gondola_llena', 'se_relleno']);
    }
  } else if (action === 'gondola_llena' || action === 'se_relleno') {
    // Can't select if Agotado is active
    if (actions.has('agotado')) return;
    // Toggle
    if (actions.has(action)) {
      actions.delete(action);
      el.classList.remove('selected');
    } else {
      actions.add(action);
      el.classList.add('selected');
    }
  } else if (action === 'orden') {
    // Orden shows a quantity picker modal
    showOrdenQtyModal(skuId);
    return; // Don't do the cleanup below, modal handles it
  }

  // Clean up empty sets
  if (actions.size === 0) {
    delete visitState.skuActions[key];
  }
}

function enableChips(container, actionTypes) {
  actionTypes.forEach(action => {
    const chip = container.querySelector(`[data-action="${action}"]`);
    if (chip) chip.classList.remove('disabled');
  });
}

function disableChips(container, actionTypes) {
  actionTypes.forEach(action => {
    const chip = container.querySelector(`[data-action="${action}"]`);
    if (chip) {
      chip.classList.remove('selected');
      chip.classList.add('disabled');
    }
  });
}

// ── Orden Quantity Modal ─────────────────────────────────────────────────

function showOrdenQtyModal(skuId) {
  const sku = visitState.approvedSkus.find(s => s.id === skuId);
  const skuName = sku ? sku.name : `SKU #${skuId}`;

  document.getElementById('orden-sku-id').value = skuId;
  document.getElementById('orden-sku-name').textContent = skuName;

  // Set current quantity if exists, otherwise default to 1
  const currentQty = visitState.ordenQuantities[skuId] || 0;
  document.getElementById('orden-qty-select').value = currentQty > 0 ? currentQty : 1;

  document.getElementById('modal-orden-qty').style.display = 'flex';
}

function confirmOrdenQty() {
  const skuId = parseInt(document.getElementById('orden-sku-id').value);
  const qty = parseInt(document.getElementById('orden-qty-select').value);

  const key = `${skuId}`;
  const chipsContainer = document.getElementById(`chips-${skuId}`);
  const ordenChip = chipsContainer.querySelector('[data-action="orden"]');

  // Initialize actions set if needed
  if (!visitState.skuActions[key]) {
    visitState.skuActions[key] = new Set();
  }
  const actions = visitState.skuActions[key];

  if (qty === 0) {
    // Remove orden action
    actions.delete('orden');
    delete visitState.ordenQuantities[skuId];
    ordenChip.classList.remove('selected', 'has-qty');
    ordenChip.innerHTML = 'Orden';
  } else {
    // Set orden action with quantity
    actions.add('orden');
    visitState.ordenQuantities[skuId] = qty;
    ordenChip.classList.add('selected', 'has-qty');
    ordenChip.innerHTML = `Orden <span class="chip-qty-badge">${qty}</span>`;
  }

  // Clean up empty sets
  if (actions.size === 0) {
    delete visitState.skuActions[key];
  }

  closeModal('modal-orden-qty');
}

// ── Step 4: Summary & Submit ────────────────────────────────────────────

function showVisitSummary() {
  visitState.conditionNotes = document.getElementById('condition-notes').value;

  // Count actions from Sets (multi-select)
  const actionCounts = { gondola_llena: 0, se_relleno: 0, orden: 0, agotado: 0 };
  Object.values(visitState.skuActions).forEach(actionsSet => {
    actionsSet.forEach(action => {
      if (actionCounts[action] !== undefined) actionCounts[action]++;
    });
  });

  // Calculate total boxes ordered
  const totalBoxesOrdered = Object.values(visitState.ordenQuantities).reduce((sum, qty) => sum + qty, 0);

  // Count photos: 1 arrival + gondola groups (before + after)
  const arrivalCount = visitState.photos.arrival ? 1 : 0;
  const gondolaBeforeCount = visitState.gondolaGroups.filter(g => g.beforePhoto).length;
  const gondolaAfterCount = visitState.gondolaGroups.filter(g => g.afterPhoto).length;
  const totalPhotos = arrivalCount + gondolaBeforeCount + gondolaAfterCount;
  const pendingAfter = gondolaBeforeCount - gondolaAfterCount;

  const summaryEl = document.getElementById('visit-summary');
  summaryEl.innerHTML = `
    <div class="summary-item"><span>Tienda:</span><span>${visitState.storeName}</span></div>
    <div class="summary-item"><span>Fotos:</span><span>${totalPhotos} (${arrivalCount} llegada, ${gondolaBeforeCount} antes, ${gondolaAfterCount} después)</span></div>
    <div class="summary-item"><span>Grupos Góndola:</span><span>${visitState.gondolaGroups.length}${pendingAfter > 0 ? ` (${pendingAfter} pendiente)` : ''}</span></div>
    <div class="summary-item"><span>Góndola Llena:</span><span>${actionCounts.gondola_llena}</span></div>
    <div class="summary-item"><span>Se Rellenó:</span><span>${actionCounts.se_relleno}</span></div>
    <div class="summary-item"><span>Orden:</span><span>${actionCounts.orden} SKU(s)${totalBoxesOrdered > 0 ? ` — ${totalBoxesOrdered} cajas` : ''}</span></div>
    <div class="summary-item"><span>Agotado:</span><span>${actionCounts.agotado}</span></div>
    <div class="summary-item"><span>Precios OK:</span><span>${visitState.conditions.prices ? 'Sí' : 'No'}</span></div>
    <div class="summary-item"><span>PoP OK:</span><span>${visitState.conditions.pop ? 'Sí' : 'No'}</span></div>
    <div class="summary-item"><span>Presentable:</span><span>${visitState.conditions.clean ? 'Sí' : 'No'}</span></div>
  `;
}

async function submitVisit() {
  const btn = document.getElementById('btn-submit-visit');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Enviando...';

  try {
    // Convert Set-based actions to array of action objects
    // Each SKU can have multiple actions now
    // For 'orden' actions, include the quantity
    const actions = [];
    Object.entries(visitState.skuActions).forEach(([skuId, actionsSet]) => {
      actionsSet.forEach(actionType => {
        const action = { sku_id: parseInt(skuId), action_type: actionType };
        if (actionType === 'orden' && visitState.ordenQuantities[skuId]) {
          action.quantity = visitState.ordenQuantities[skuId];
        }
        actions.push(action);
      });
    });

    const notes = document.getElementById('visit-notes').value;

    await apiPut(`/visits/${visitState.visitId}/complete`, {
      prices_on_gondola: visitState.conditions.prices,
      pop_material_present: visitState.conditions.pop,
      product_presentable: visitState.conditions.clean,
      condition_notes: visitState.conditionNotes,
      sku_actions: actions,
      notes: notes,
    });

    toast('¡Visita enviada exitosamente!');
    loadVisitPage();
  } catch (err) {
    toast('Error: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = '✓ Enviar Visita';
  }
}

// ══════════════════════════════════════════════════════════════════════════
// ═══ HISTORY PAGE ════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════════════════

async function loadHistoryPage() {
  const container = document.getElementById('history-list');
  container.innerHTML = '<p>Cargando...</p>';
  try {
    const visits = await apiGet('/visits/?limit=30');
    if (visits.length === 0) {
      container.innerHTML = '<p class="meta">No hay visitas aún.</p>';
      return;
    }
    container.innerHTML = visits.map(v => {
      const date = new Date(v.start_time).toLocaleString();
      const storeName = v.store ? v.store.name : `Tienda #${v.store_id}`;
      const photoCount = v.photos ? v.photos.length : 0;
      const actionCount = v.sku_actions ? v.sku_actions.length : 0;

      return `
        <div class="card" onclick="showVisitDetail(${v.id})">
          <h3>${storeName}</h3>
          <div class="meta">${date}</div>
          <div class="meta">${photoCount} foto(s) · ${actionCount} SKU(s) · ${v.status}</div>
        </div>
      `;
    }).join('');
  } catch (err) {
    container.innerHTML = '<p>Error cargando visitas.</p>';
  }
}

async function showVisitDetail(visitId) {
  try {
    const v = await apiGet(`/visits/${visitId}`);
    const date = new Date(v.start_time).toLocaleString();
    const storeName = v.store ? v.store.name : `Tienda #${v.store_id}`;
    const userName = v.user ? v.user.full_name : `Usuario #${v.user_id}`;

    const actionLabels = {
      'gondola_llena': 'Góndola Llena',
      'se_relleno': 'Se Rellenó',
      'orden': 'Orden',
      'agotado': 'Agotado',
      'unknown': 'Desconocido',
    };

    // Separate arrival photos from gondola photos
    const arrivalPhotos = (v.photos || []).filter(p => p.photo_type === 'arrival_proof');
    const gondolaPhotos = (v.photos || []).filter(p => p.photo_type !== 'arrival_proof');

    // Group gondola photos by gondola_group_id
    const gondolaGroups = {};
    for (const photo of gondolaPhotos) {
      const groupId = photo.gondola_group_id || 'ungrouped';
      if (!gondolaGroups[groupId]) {
        gondolaGroups[groupId] = { before: null, after: null };
      }
      if (photo.photo_type === 'gondola_before') {
        gondolaGroups[groupId].before = photo;
      } else if (photo.photo_type === 'gondola_after') {
        gondolaGroups[groupId].after = photo;
      }
    }

    // Build arrival photos HTML
    let arrivalHtml = '';
    for (const photo of arrivalPhotos) {
      arrivalHtml += `
        <div class="photo-single" style="margin-top:12px;">
          <div class="meta">Foto de Llegada</div>
          <img src="${photo.file_path}" style="max-width:100%;border-radius:8px;">
        </div>`;
    }

    // Build side-by-side gondola groups HTML
    let gondolaHtml = '';
    const groupIds = Object.keys(gondolaGroups).filter(id => id !== 'ungrouped');
    if (groupIds.length > 0) {
      gondolaHtml = '<div class="gondola-compare-section" style="margin-top:16px;"><strong>Fotos de Góndola</strong></div>';
      groupIds.forEach((groupId, idx) => {
        const group = gondolaGroups[groupId];
        gondolaHtml += `
          <div class="photo-compare-group" style="margin-top:12px;">
            <div class="compare-header meta">Grupo ${idx + 1}</div>
            <div class="photo-compare-row">
              <div class="photo-compare-col">
                <div class="compare-label">ANTES</div>
                ${group.before
                  ? `<img src="${group.before.file_path}" class="compare-img">`
                  : '<div class="compare-placeholder">Sin foto</div>'}
              </div>
              <div class="photo-compare-col">
                <div class="compare-label">DESPUÉS</div>
                ${group.after
                  ? `<img src="${group.after.file_path}" class="compare-img">`
                  : '<div class="compare-placeholder">Sin foto</div>'}
              </div>
            </div>
          </div>`;
      });
    }

    const photosHtml = arrivalHtml + gondolaHtml;

    const actionsHtml = (v.sku_actions || []).map(a => {
      const label = actionLabels[a.action_type] || a.action_type;
      const skuName = a.sku ? a.sku.name : `SKU #${a.sku_id}`;
      let badgeClass = 'yellow';
      if (a.action_type === 'orden') badgeClass = 'yellow';
      else if (a.action_type === 'agotado') badgeClass = 'red';
      else if (a.action_type === 'se_relleno') badgeClass = 'green';
      else if (a.action_type === 'gondola_llena') badgeClass = 'green';
      return `<div><span class="badge badge-${badgeClass}">${label}</span> ${skuName}</div>`;
    }).join('');

    // Show visit detail in a modal-like overlay or replace the current route queue content
    const detailContainer = document.getElementById('visit-detail-container') || createVisitDetailContainer();
    detailContainer.innerHTML = `
      <div class="card">
        <button class="btn btn-outline btn-sm" onclick="closeVisitDetail()" style="margin-bottom:12px;">← Atrás</button>
        <h3>${storeName}</h3>
        <div class="meta">${date} · ${userName}</div>
        ${v.latitude ? `<div class="meta">GPS: ${v.latitude.toFixed(5)}, ${v.longitude.toFixed(5)}</div>` : ''}
        <div style="margin-top:12px;">
          <div><strong>Precios:</strong> ${v.prices_on_gondola ? 'Sí' : 'No'}</div>
          <div><strong>PoP:</strong> ${v.pop_material_present ? 'Sí' : 'No'}</div>
          <div><strong>Presentable:</strong> ${v.product_presentable ? 'Sí' : 'No'}</div>
          ${v.condition_notes ? `<div class="meta">${v.condition_notes}</div>` : ''}
        </div>
        <div style="margin-top:12px;"><strong>SKUs:</strong></div>
        ${actionsHtml || '<div class="meta">Sin acciones</div>'}
        ${photosHtml}
      </div>
    `;
    detailContainer.style.display = 'block';
  } catch (err) {
    toast('Error cargando detalles');
  }
}

function createVisitDetailContainer() {
  const container = document.createElement('div');
  container.id = 'visit-detail-container';
  container.className = 'visit-detail-overlay';
  document.getElementById('page-route-history').appendChild(container);
  return container;
}

function closeVisitDetail() {
  const container = document.getElementById('visit-detail-container');
  if (container) {
    container.style.display = 'none';
    container.innerHTML = '';
  }
}

// ══════════════════════════════════════════════════════════════════════════
// ═══ ROUTE HISTORY PAGE (Admin only - Notifications Queue) ════════════════
// ══════════════════════════════════════════════════════════════════════════

async function loadRouteHistoryPage() {
  // Load notification panels for admins (notifications serve as the visit queue)
  if (getUserRole() === 'admin') {
    loadNotificationPanels();
  }
}

// ══════════════════════════════════════════════════════════════════════════
// ═══ DASHBOARD PAGE ══════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════════════════

async function loadDashboardPage() {
  try {
    const regions = await apiGet('/dashboard/regions');
    const regionFilter = document.getElementById('filter-region');
    regionFilter.innerHTML = '<option value="">Todas las Regiones</option>' +
      regions.map(r => `<option value="${r}">${r}</option>`).join('');
    await refreshDashboard();
  } catch (err) {
    toast('Error cargando dashboard');
  }
}

async function refreshDashboard() {
  const region = document.getElementById('filter-region').value;
  const dateFrom = document.getElementById('filter-date-from').value;
  const dateTo = document.getElementById('filter-date-to').value;

  let params = [];
  if (region) params.push(`region=${region}`);
  if (dateFrom) params.push(`date_from=${dateFrom}`);
  if (dateTo) params.push(`date_to=${dateTo}`);
  const qs = params.length > 0 ? '?' + params.join('&') : '';

  try {
    const [summary, byStore] = await Promise.all([
      apiGet(`/dashboard/summary${qs}`),
      apiGet(`/dashboard/by-store${qs}`),
    ]);

    document.getElementById('stat-visits').textContent = summary.total_visits;
    document.getElementById('stat-coverage').textContent = `${(summary.coverage_rate * 100).toFixed(0)}%`;

    // Action type stats
    const gondolaLlena = document.getElementById('stat-gondola-llena');
    const seRelleno = document.getElementById('stat-se-relleno');
    const orden = document.getElementById('stat-orden');
    const agotado = document.getElementById('stat-agotado');

    if (gondolaLlena) gondolaLlena.textContent = summary.actions?.gondola_llena || 0;
    if (seRelleno) seRelleno.textContent = summary.actions?.se_relleno || 0;
    if (orden) orden.textContent = summary.actions?.orden || 0;
    if (agotado) agotado.textContent = summary.actions?.agotado || 0;

    // By-store table
    const tableBody = document.getElementById('store-table-body');
    tableBody.innerHTML = byStore.map(s => `
      <tr>
        <td>${s.store_name}</td>
        <td>${s.region}</td>
        <td>${s.visit_count}</td>
        <td>${s.gondola_llena || 0}</td>
        <td>${s.se_relleno || 0}</td>
        <td>${s.orden || 0}</td>
        <td>${s.agotado || 0}</td>
      </tr>
    `).join('');

  } catch (err) {
    toast('Error actualizando dashboard');
  }
}

// ══════════════════════════════════════════════════════════════════════════
// ═══ APPROVALS PAGE (Workflow A) ═════════════════════════════════════════
// ══════════════════════════════════════════════════════════════════════════

let approvalsState = { storeId: null, allSkus: [], currentApprovals: [] };

async function loadApprovalsPage() {
  try {
    const stores = await apiGet('/stores/');
    const sel = document.getElementById('approval-store-select');
    sel.innerHTML = '<option value="">Seleccione una tienda...</option>' +
      stores.map(s => `<option value="${s.id}">${s.name} (${s.region})</option>`).join('');
    document.getElementById('approval-editor').style.display = 'none';
  } catch (err) {
    toast('Error cargando tiendas');
  }
}

async function loadStoreApprovals() {
  const storeId = document.getElementById('approval-store-select').value;
  if (!storeId) {
    document.getElementById('approval-editor').style.display = 'none';
    return;
  }

  approvalsState.storeId = parseInt(storeId);

  try {
    const [allSkus, approvals] = await Promise.all([
      apiGet('/skus/'),
      apiGet(`/approvals/?store_id=${storeId}`),
    ]);

    approvalsState.allSkus = allSkus;
    approvalsState.currentApprovals = approvals;

    const approvedIds = new Set(approvals.map(a => a.sku_id));

    const skuList = document.getElementById('approval-sku-list');
    skuList.innerHTML = allSkus.map(sku => `
      <li class="approval-item">
        <input type="checkbox" id="sku-${sku.id}" value="${sku.id}" ${approvedIds.has(sku.id) ? 'checked' : ''}>
        <label for="sku-${sku.id}">${sku.name} <span class="meta">(${sku.brand})</span></label>
      </li>
    `).join('');

    document.getElementById('approval-editor').style.display = 'block';
  } catch (err) {
    toast('Error cargando SKUs aprobados');
  }
}

async function saveApprovals() {
  const checkboxes = document.querySelectorAll('#approval-sku-list input[type="checkbox"]');
  const selectedIds = Array.from(checkboxes).filter(cb => cb.checked).map(cb => parseInt(cb.value));

  // Get current quarter (e.g., "2026-Q1")
  const now = new Date();
  const quarter = `${now.getFullYear()}-Q${Math.ceil((now.getMonth() + 1) / 3)}`;

  try {
    await apiPut('/approvals/bulk', {
      store_id: approvalsState.storeId,
      quarter: quarter,
      sku_ids: selectedIds,
    });
    toast('Cambios guardados');
  } catch (err) {
    toast('Error guardando: ' + err.message);
  }
}

// ══════════════════════════════════════════════════════════════════════════
// ═══ ADMIN CONSOLE ════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════════════════

let adminData = {
  users: [],
  skus: [],
  stores: [],
};

function loadAdminPage() {
  // Show admin tab only for admin users
  const navAdmin = document.getElementById('nav-admin');
  if (navAdmin && getUserRole() === 'admin') {
    navAdmin.style.display = 'block';
  }

  showAdminTab('users');
  loadAdminUsers();
  loadRegionFilters();
}

function showAdminTab(tab) {
  // Update tab buttons
  document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
  document.querySelector(`[data-admin-tab="${tab}"]`)?.classList.add('active');

  // Show corresponding panel
  document.querySelectorAll('.admin-panel').forEach(p => p.classList.remove('active'));
  document.getElementById(`admin-tab-${tab}`)?.classList.add('active');

  // Load data
  if (tab === 'users') loadAdminUsers();
  else if (tab === 'skus') loadAdminSkus();
  else if (tab === 'stores') loadAdminStores();
}

// ── User Management ──────────────────────────────────────────────────────

async function loadAdminUsers() {
  const role = document.getElementById('admin-users-role')?.value || '';
  const includeInactive = document.getElementById('admin-users-inactive')?.checked || false;

  try {
    let url = `/users/?include_inactive=${includeInactive}`;
    if (role) url += `&role=${role}`;
    const users = await apiGet(url);
    adminData.users = users;

    const tbody = document.getElementById('admin-users-table');
    tbody.innerHTML = users.map(u => `
      <tr class="${!u.is_active ? 'inactive-row' : ''}">
        <td>${u.full_name}</td>
        <td>${u.username}</td>
        <td>${u.role}</td>
        <td>${u.region || '-'}</td>
        <td><span class="${u.is_active ? 'status-active' : 'status-inactive'}">${u.is_active ? 'Activo' : 'Inactivo'}</span></td>
        <td class="action-btns">
          <button class="btn-edit" onclick="editUser(${u.id})">Editar</button>
          ${u.is_active
            ? `<button class="btn-deactivate" onclick="toggleUserStatus(${u.id}, false)">Desactivar</button>`
            : `<button class="btn-activate" onclick="toggleUserStatus(${u.id}, true)">Activar</button>`
          }
        </td>
      </tr>
    `).join('');
  } catch (err) {
    toast('Error cargando usuarios');
  }
}

function showUserModal(userId = null) {
  const modal = document.getElementById('modal-user');
  const title = document.getElementById('modal-user-title');
  const hint = document.getElementById('user-pwd-hint');

  document.getElementById('form-user').reset();
  document.getElementById('user-id').value = '';

  if (userId) {
    const user = adminData.users.find(u => u.id === userId);
    if (user) {
      title.textContent = 'Editar Usuario';
      hint.textContent = '(dejar en blanco para mantener)';
      document.getElementById('user-id').value = user.id;
      document.getElementById('user-fullname').value = user.full_name;
      document.getElementById('user-username').value = user.username;
      document.getElementById('user-username').disabled = true; // Can't change username
      document.getElementById('user-role').value = user.role;
      document.getElementById('user-region').value = user.region || '';
    }
  } else {
    title.textContent = 'Nuevo Usuario';
    hint.textContent = '(requerido)';
    document.getElementById('user-username').disabled = false;
  }

  modal.style.display = 'flex';
}

function editUser(userId) {
  showUserModal(userId);
}

async function saveUser(e) {
  e.preventDefault();

  const id = document.getElementById('user-id').value;
  const data = {
    full_name: document.getElementById('user-fullname').value,
    role: document.getElementById('user-role').value,
    region: document.getElementById('user-region').value || null,
  };

  const password = document.getElementById('user-password').value;

  try {
    if (id) {
      // Update existing user
      if (password) data.password = password;
      await apiPut(`/users/${id}`, data);
      toast('Usuario actualizado');
    } else {
      // Create new user
      data.username = document.getElementById('user-username').value;
      data.password = password;
      if (!password) {
        toast('Contraseña requerida');
        return;
      }
      await apiPost('/users/', data);
      toast('Usuario creado');
    }

    closeModal('modal-user');
    loadAdminUsers();
  } catch (err) {
    toast('Error: ' + err.message);
  }
}

async function toggleUserStatus(userId, activate) {
  try {
    if (activate) {
      await api(`/users/${userId}/activate`, { method: 'POST' });
      toast('Usuario activado');
    } else {
      await apiDelete(`/users/${userId}`);
      toast('Usuario desactivado');
    }
    loadAdminUsers();
  } catch (err) {
    toast('Error: ' + err.message);
  }
}

// ── SKU Management ───────────────────────────────────────────────────────

async function loadAdminSkus() {
  const includeInactive = document.getElementById('admin-skus-inactive')?.checked || false;

  try {
    const skus = await apiGet(`/skus/?include_inactive=${includeInactive}`);
    adminData.skus = skus;
    renderSkuTable(skus);
  } catch (err) {
    toast('Error cargando SKUs');
  }
}

function renderSkuTable(skus) {
  const tbody = document.getElementById('admin-skus-table');
  tbody.innerHTML = skus.map(s => `
    <tr class="${!s.is_active ? 'inactive-row' : ''}">
      <td>${s.name}</td>
      <td>${s.brand}</td>
      <td>${s.category || '-'}</td>
      <td>${s.barcode || '-'}</td>
      <td><span class="${s.is_active ? 'status-active' : 'status-inactive'}">${s.is_active ? 'Activo' : 'Inactivo'}</span></td>
      <td class="action-btns">
        <button class="btn-edit" onclick="editSku(${s.id})">Editar</button>
        ${s.is_active
          ? `<button class="btn-deactivate" onclick="toggleSkuStatus(${s.id}, false)">Desactivar</button>`
          : `<button class="btn-activate" onclick="toggleSkuStatus(${s.id}, true)">Activar</button>`
        }
      </td>
    </tr>
  `).join('');
}

function filterSkuTable() {
  const search = (document.getElementById('admin-skus-search')?.value || '').toLowerCase();
  const filtered = adminData.skus.filter(s =>
    s.name.toLowerCase().includes(search) ||
    s.brand.toLowerCase().includes(search) ||
    (s.barcode && s.barcode.includes(search))
  );
  renderSkuTable(filtered);
}

function showSkuModal(skuId = null) {
  const modal = document.getElementById('modal-sku');
  const title = document.getElementById('modal-sku-title');

  document.getElementById('form-sku').reset();
  document.getElementById('sku-id').value = '';
  document.getElementById('sku-brand').value = 'Ito';

  if (skuId) {
    const sku = adminData.skus.find(s => s.id === skuId);
    if (sku) {
      title.textContent = 'Editar SKU';
      document.getElementById('sku-id').value = sku.id;
      document.getElementById('sku-name').value = sku.name;
      document.getElementById('sku-brand').value = sku.brand;
      document.getElementById('sku-category').value = sku.category || '';
      document.getElementById('sku-barcode').value = sku.barcode || '';
      document.getElementById('sku-image').value = sku.image_url || '';
    }
  } else {
    title.textContent = 'Nuevo SKU';
  }

  modal.style.display = 'flex';
}

function editSku(skuId) {
  showSkuModal(skuId);
}

async function saveSku(e) {
  e.preventDefault();

  const id = document.getElementById('sku-id').value;
  const data = {
    name: document.getElementById('sku-name').value,
    brand: document.getElementById('sku-brand').value,
    category: document.getElementById('sku-category').value || null,
    barcode: document.getElementById('sku-barcode').value || null,
    image_url: document.getElementById('sku-image').value || null,
  };

  try {
    if (id) {
      await apiPut(`/skus/${id}`, data);
      toast('SKU actualizado');
    } else {
      await apiPost('/skus/', data);
      toast('SKU creado');
    }

    closeModal('modal-sku');
    loadAdminSkus();
  } catch (err) {
    toast('Error: ' + err.message);
  }
}

async function toggleSkuStatus(skuId, activate) {
  try {
    if (activate) {
      await api(`/skus/${skuId}/activate`, { method: 'POST' });
      toast('SKU activado');
    } else {
      await apiDelete(`/skus/${skuId}`);
      toast('SKU desactivado');
    }
    loadAdminSkus();
  } catch (err) {
    toast('Error: ' + err.message);
  }
}

// ── Store Management ─────────────────────────────────────────────────────

async function loadAdminStores() {
  const region = document.getElementById('admin-stores-region')?.value || '';
  const includeInactive = document.getElementById('admin-stores-inactive')?.checked || false;

  try {
    let url = `/stores/?include_inactive=${includeInactive}`;
    if (region) url += `&region=${region}`;
    const stores = await apiGet(url);
    adminData.stores = stores;

    const tbody = document.getElementById('admin-stores-table');
    tbody.innerHTML = stores.map(s => `
      <tr class="${!s.is_active ? 'inactive-row' : ''}">
        <td>${s.name}</td>
        <td>${s.chain || '-'}</td>
        <td>${s.region}</td>
        <td>${s.address || '-'}</td>
        <td><span class="${s.is_active ? 'status-active' : 'status-inactive'}">${s.is_active ? 'Activa' : 'Inactiva'}</span></td>
        <td class="action-btns">
          <button class="btn-edit" onclick="editStore(${s.id})">Editar</button>
          ${s.is_active
            ? `<button class="btn-deactivate" onclick="toggleStoreStatus(${s.id}, false)">Desactivar</button>`
            : `<button class="btn-activate" onclick="toggleStoreStatus(${s.id}, true)">Activar</button>`
          }
        </td>
      </tr>
    `).join('');
  } catch (err) {
    toast('Error cargando tiendas');
  }
}

async function loadRegionFilters() {
  try {
    const regions = await apiGet('/dashboard/regions');
    const sel = document.getElementById('admin-stores-region');
    if (sel) {
      sel.innerHTML = '<option value="">Todas las Regiones</option>' +
        regions.map(r => `<option value="${r}">${r}</option>`).join('');
    }
  } catch (err) {
    // Ignore - regions filter is optional
  }
}

function showStoreModal(storeId = null) {
  const modal = document.getElementById('modal-store');
  const title = document.getElementById('modal-store-title');

  document.getElementById('form-store').reset();
  document.getElementById('store-id').value = '';

  if (storeId) {
    const store = adminData.stores.find(s => s.id === storeId);
    if (store) {
      title.textContent = 'Editar Tienda';
      document.getElementById('store-id').value = store.id;
      document.getElementById('store-name').value = store.name;
      document.getElementById('store-chain').value = store.chain || '';
      document.getElementById('store-region').value = store.region;
      document.getElementById('store-address').value = store.address || '';
      document.getElementById('store-lat').value = store.latitude || '';
      document.getElementById('store-lng').value = store.longitude || '';
      document.getElementById('store-notes').value = store.notes || '';
    }
  } else {
    title.textContent = 'Nueva Tienda';
  }

  modal.style.display = 'flex';
}

function editStore(storeId) {
  showStoreModal(storeId);
}

async function saveStore(e) {
  e.preventDefault();

  const id = document.getElementById('store-id').value;
  const data = {
    name: document.getElementById('store-name').value,
    chain: document.getElementById('store-chain').value || null,
    region: document.getElementById('store-region').value,
    address: document.getElementById('store-address').value || null,
    latitude: document.getElementById('store-lat').value ? parseFloat(document.getElementById('store-lat').value) : null,
    longitude: document.getElementById('store-lng').value ? parseFloat(document.getElementById('store-lng').value) : null,
    notes: document.getElementById('store-notes').value || null,
  };

  try {
    if (id) {
      await apiPut(`/stores/${id}`, data);
      toast('Tienda actualizada');
    } else {
      await apiPost('/stores/', data);
      toast('Tienda creada');
    }

    closeModal('modal-store');
    loadAdminStores();
  } catch (err) {
    toast('Error: ' + err.message);
  }
}

async function toggleStoreStatus(storeId, activate) {
  try {
    if (activate) {
      await api(`/stores/${storeId}/activate`, { method: 'POST' });
      toast('Tienda activada');
    } else {
      await apiDelete(`/stores/${storeId}`);
      toast('Tienda desactivada');
    }
    loadAdminStores();
  } catch (err) {
    toast('Error: ' + err.message);
  }
}

// ── Modal Helpers ────────────────────────────────────────────────────────

function closeModal(modalId) {
  document.getElementById(modalId).style.display = 'none';
}

// Close modal on backdrop click
document.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal')) {
    e.target.style.display = 'none';
  }
});


// ══════════════════════════════════════════════════════════════════════════
// ═══ REAL-TIME NOTIFICATIONS (WebSocket) ══════════════════════════════════
// ══════════════════════════════════════════════════════════════════════════

let notificationState = {
  ws: null,
  connected: false,
  reconnectAttempts: 0,
  maxReconnectAttempts: 10,
  reconnectDelay: 2000,
  lastEventId: null,
  notifications: [],  // All notifications
  unreadCounts: {},   // { routeId: count }
  routes: [],         // Route list for display
};

/**
 * Initialize WebSocket connection for real-time notifications.
 * Called when admin navigates to route-history page.
 */
function initNotificationWebSocket() {
  if (getUserRole() !== 'admin') return;
  if (notificationState.ws && notificationState.connected) return;

  const token = getToken();
  if (!token) return;

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  let wsUrl = `${protocol}//${host}/api/notifications/ws?token=${token}`;

  if (notificationState.lastEventId) {
    wsUrl += `&last_event_id=${notificationState.lastEventId}`;
  }

  try {
    notificationState.ws = new WebSocket(wsUrl);

    notificationState.ws.onopen = () => {
      notificationState.connected = true;
      notificationState.reconnectAttempts = 0;
      updateWsStatus('connected');
      console.log('WebSocket connected for notifications');
    };

    notificationState.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        handleWebSocketMessage(message);
      } catch (e) {
        console.error('Error parsing WebSocket message:', e);
      }
    };

    notificationState.ws.onclose = (event) => {
      notificationState.connected = false;
      updateWsStatus('disconnected');
      console.log('WebSocket disconnected:', event.code, event.reason);

      // Attempt reconnection
      if (notificationState.reconnectAttempts < notificationState.maxReconnectAttempts) {
        const delay = notificationState.reconnectDelay * Math.pow(1.5, notificationState.reconnectAttempts);
        notificationState.reconnectAttempts++;
        console.log(`Reconnecting in ${delay}ms (attempt ${notificationState.reconnectAttempts})`);
        setTimeout(initNotificationWebSocket, delay);
      }
    };

    notificationState.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      updateWsStatus('error');
    };

  } catch (e) {
    console.error('Failed to create WebSocket:', e);
    updateWsStatus('error');
  }
}

function closeNotificationWebSocket() {
  if (notificationState.ws) {
    notificationState.ws.close();
    notificationState.ws = null;
    notificationState.connected = false;
  }
}

function updateWsStatus(status) {
  const statusEl = document.getElementById('ws-status');
  if (!statusEl) return;

  switch (status) {
    case 'connected':
      statusEl.textContent = '● Conectado';
      statusEl.className = 'ws-status connected';
      break;
    case 'disconnected':
      statusEl.textContent = '○ Desconectado';
      statusEl.className = 'ws-status disconnected';
      break;
    case 'error':
      statusEl.textContent = '✕ Error';
      statusEl.className = 'ws-status error';
      break;
    default:
      statusEl.textContent = '◌ Conectando...';
      statusEl.className = 'ws-status connecting';
  }
}

function handleWebSocketMessage(message) {
  switch (message.type) {
    case 'connected':
      console.log('WebSocket auth confirmed:', message.data);
      break;

    case 'notification':
      handleNewNotification(message.data);
      break;

    case 'sync':
      handleSyncNotifications(message.data);
      break;

    case 'pong':
      // Keepalive response
      break;

    case 'error':
      console.error('WebSocket error from server:', message.data?.message);
      break;
  }
}

function handleNewNotification(notification) {
  // Add to local state
  notificationState.notifications.unshift(notification);
  notificationState.lastEventId = notification.id;

  // Update unread count for route
  const routeId = notification.route_id || 'unassigned';
  notificationState.unreadCounts[routeId] = (notificationState.unreadCounts[routeId] || 0) + 1;

  // Update UI
  renderNotificationInPanel(notification);
  updateUnreadBadges();

  // Show toast and play sound
  showNotificationToast(notification);
  playNotificationSound();
}

function handleSyncNotifications(data) {
  const notifications = data.notifications || [];
  console.log(`Syncing ${notifications.length} missed notifications`);

  // Add to local state (oldest first to maintain order)
  notifications.reverse().forEach(n => {
    if (!notificationState.notifications.find(existing => existing.id === n.id)) {
      notificationState.notifications.unshift(n);
      if (n.id > (notificationState.lastEventId || 0)) {
        notificationState.lastEventId = n.id;
      }
    }
  });

  // Re-render all panels
  renderAllNotificationPanels();
  updateUnreadBadges();
}

function showNotificationToast(notification) {
  const summary = notification.summary_data ? JSON.parse(notification.summary_data) : {};
  const msg = `✓ ${notification.merchandiser_name} completó visita en ${notification.store_name}`;

  // Create enhanced toast
  const el = document.createElement('div');
  el.className = 'toast notification-toast';
  el.innerHTML = `
    <div class="toast-icon">📋</div>
    <div class="toast-content">
      <div class="toast-title">Nueva Visita Completada</div>
      <div class="toast-body">${notification.store_name}</div>
      <div class="toast-meta">${notification.merchandiser_name} · ${notification.route_name || 'Sin ruta'}</div>
    </div>
  `;
  el.onclick = () => {
    el.remove();
    showVisitDetail(notification.visit_id);
  };
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 5000);
}

function playNotificationSound() {
  // Simple beep using Web Audio API
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = ctx.createOscillator();
    const gain = ctx.createGain();
    oscillator.connect(gain);
    gain.connect(ctx.destination);
    oscillator.frequency.value = 800;
    oscillator.type = 'sine';
    gain.gain.value = 0.1;
    oscillator.start();
    oscillator.stop(ctx.currentTime + 0.1);
  } catch (e) {
    // Audio not supported
  }
}

// ── Notification Panel Rendering ──────────────────────────────────────────

async function loadNotificationPanels() {
  const grid = document.getElementById('route-notification-grid');
  if (!grid) return;

  grid.innerHTML = '<p class="meta">Cargando rutas...</p>';

  try {
    // Load routes and notification counts
    const [routes, countsData] = await Promise.all([
      apiGet('/routes/'),
      apiGet('/notifications/counts'),
    ]);

    notificationState.routes = routes;

    // Store unread counts
    countsData.by_route?.forEach(rc => {
      notificationState.unreadCounts[rc.route_id || 'unassigned'] = rc.unread_count;
    });

    // Filter to only show Norte route
    const norteRoute = routes.find(r => r.name === 'Norte');
    const filteredRoutes = norteRoute ? [norteRoute] : routes.slice(0, 1);
    notificationState.routes = filteredRoutes;

    // Render single Norte panel
    grid.innerHTML = filteredRoutes.map(r => `
      <div class="notification-panel notification-panel-single" id="notification-panel-${r.id}">
        <div class="notification-panel-header">
          <div class="panel-route-name">${r.name}</div>
          <span class="notification-badge" id="badge-${r.id}" style="display:none;">0</span>
        </div>
        <div class="notification-panel-actions">
          <button class="btn btn-xs" onclick="markRouteNotificationsRead(${r.id})">Marcar leídas</button>
        </div>
        <div class="notification-list" id="notification-list-${r.id}">
          <p class="meta">Cargando...</p>
        </div>
      </div>
    `).join('');

    // Load notifications for each route
    await loadAllRouteNotifications();

    // Update badges
    updateUnreadBadges();

    // Initialize WebSocket
    initNotificationWebSocket();

  } catch (err) {
    console.error('Error loading notification panels:', err);
    grid.innerHTML = '<p class="meta" style="color:var(--danger);">Error cargando notificaciones.</p>';
  }
}

async function loadAllRouteNotifications() {
  // Load recent notifications
  try {
    const notifications = await apiGet('/notifications/?limit=100&is_read=false');
    notificationState.notifications = notifications;

    if (notifications.length > 0) {
      notificationState.lastEventId = Math.max(...notifications.map(n => n.id));
    }

    renderAllNotificationPanels();
  } catch (err) {
    console.error('Error loading notifications:', err);
  }
}

function renderAllNotificationPanels() {
  // Group notifications by route
  const byRoute = {};

  notificationState.notifications.forEach(n => {
    const key = n.route_id || 'unassigned';
    if (!byRoute[key]) byRoute[key] = [];
    byRoute[key].push(n);
  });

  // Render each route's notifications (Norte only)
  notificationState.routes.forEach(r => {
    const notifications = byRoute[r.id] || [];
    renderNotificationList(r.id, notifications);
  });
}

function renderNotificationList(routeId, notifications) {
  const listEl = document.getElementById(`notification-list-${routeId}`);
  if (!listEl) return;

  if (notifications.length === 0) {
    listEl.innerHTML = '<p class="meta notification-empty">Sin notificaciones nuevas</p>';
    return;
  }

  listEl.innerHTML = notifications.slice(0, 20).map(n => renderNotificationItem(n)).join('');
}

function renderNotificationItem(n) {
  const summary = n.summary_data ? JSON.parse(n.summary_data) : {};
  const time = n.event_time ? formatTimeAgo(new Date(n.event_time)) : '';
  const isNew = !n.is_read;

  return `
    <div class="notification-item ${isNew ? 'unread' : ''}" data-notification-id="${n.id}" onclick="viewNotification(${n.id}, ${n.visit_id})">
      <div class="notification-item-header">
        <span class="notification-store">${n.store_name}</span>
        <span class="notification-time">${time}</span>
      </div>
      <div class="notification-merchandiser">${n.merchandiser_name}</div>
      <div class="notification-summary">
        ${summary.photo_count ? `📷 ${summary.photo_count}` : ''}
        ${summary.sku_actions_count ? `· 📦 ${summary.sku_actions_count} SKUs` : ''}
      </div>
    </div>
  `;
}

function renderNotificationInPanel(notification) {
  const routeId = notification.route_id || 'unassigned';
  const listEl = document.getElementById(`notification-list-${routeId}`);
  if (!listEl) return;

  // Remove empty message if present
  const emptyMsg = listEl.querySelector('.notification-empty');
  if (emptyMsg) emptyMsg.remove();

  // Insert at top with animation
  const html = renderNotificationItem(notification);
  const wrapper = document.createElement('div');
  wrapper.innerHTML = html;
  const newItem = wrapper.firstElementChild;
  newItem.classList.add('notification-new');

  listEl.insertBefore(newItem, listEl.firstChild);

  // Remove animation class after animation
  setTimeout(() => newItem.classList.remove('notification-new'), 500);
}

function updateUnreadBadges() {
  let totalUnread = 0;

  // Update each route badge (Norte only)
  notificationState.routes.forEach(r => {
    const count = notificationState.unreadCounts[r.id] || 0;
    totalUnread += count;
    const badge = document.getElementById(`badge-${r.id}`);
    if (badge) {
      badge.textContent = count;
      badge.style.display = count > 0 ? 'inline-flex' : 'none';
    }
  });

  // Update total badge
  const totalBadge = document.getElementById('total-unread-badge');
  const markAllBtn = document.getElementById('btn-mark-all-read');
  if (totalBadge) {
    totalBadge.textContent = `${totalUnread} nueva${totalUnread !== 1 ? 's' : ''}`;
    totalBadge.style.display = totalUnread > 0 ? 'inline-flex' : 'none';
  }
  if (markAllBtn) {
    markAllBtn.style.display = totalUnread > 0 ? 'inline-block' : 'none';
  }
}

// ── Notification Actions ──────────────────────────────────────────────────

async function viewNotification(notificationId, visitId) {
  // Mark as read
  try {
    await apiPost('/notifications/mark-read', { notification_ids: [notificationId] });

    // Update local state
    const notification = notificationState.notifications.find(n => n.id === notificationId);
    if (notification && !notification.is_read) {
      notification.is_read = true;
      const routeId = notification.route_id || 'unassigned';
      notificationState.unreadCounts[routeId] = Math.max(0, (notificationState.unreadCounts[routeId] || 0) - 1);
      updateUnreadBadges();

      // Update UI
      const item = document.querySelector(`[data-notification-id="${notificationId}"]`);
      if (item) item.classList.remove('unread');
    }
  } catch (e) {
    // Continue even if mark-read fails
  }

  // Show visit detail
  showVisitDetail(visitId);
}

async function markRouteNotificationsRead(routeId) {
  try {
    const url = routeId !== null
      ? `/notifications/mark-all-read?route_id=${routeId}`
      : '/notifications/mark-all-read';
    await apiPost(url, {});

    // Update local state
    const key = routeId || 'unassigned';
    notificationState.notifications.forEach(n => {
      if ((n.route_id || 'unassigned') === key) {
        n.is_read = true;
      }
    });
    notificationState.unreadCounts[key] = 0;

    // Update UI
    const listEl = document.getElementById(`notification-list-${key}`);
    if (listEl) {
      listEl.querySelectorAll('.notification-item').forEach(el => {
        el.classList.remove('unread');
      });
    }

    updateUnreadBadges();
    toast('Notificaciones marcadas como leídas');
  } catch (e) {
    toast('Error al marcar notificaciones');
  }
}

async function markAllNotificationsRead() {
  try {
    await apiPost('/notifications/mark-all-read', {});

    // Update local state
    notificationState.notifications.forEach(n => n.is_read = true);
    Object.keys(notificationState.unreadCounts).forEach(k => {
      notificationState.unreadCounts[k] = 0;
    });

    // Update UI
    document.querySelectorAll('.notification-item').forEach(el => {
      el.classList.remove('unread');
    });

    updateUnreadBadges();
    toast('Todas las notificaciones marcadas como leídas');
  } catch (e) {
    toast('Error al marcar notificaciones');
  }
}

// ── Utility Functions ─────────────────────────────────────────────────────

function formatTimeAgo(date) {
  const now = new Date();
  const diff = Math.floor((now - date) / 1000);

  if (diff < 60) return 'ahora';
  if (diff < 3600) return `hace ${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `hace ${Math.floor(diff / 3600)}h`;
  return date.toLocaleDateString();
}
