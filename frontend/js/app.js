/**
 * Ito Merchandising App — Main application controller.
 * 6-Step Visit Workflow.
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
    case 'history': loadHistoryPage(); break;
    case 'dashboard': loadDashboardPage(); break;
    case 'approvals': loadApprovalsPage(); break;
  }
}

// ══════════════════════════════════════════════════════════════════════════
// ═══ STORE VISIT — 6-Step Workflow ═══════════════════════════════════════
// ══════════════════════════════════════════════════════════════════════════

let visitState = {
  step: 0,
  visitId: null,
  storeId: null,
  storeName: '',
  approvedSkus: [],
  skuActions: {},
  conditions: { prices: null, pop: null, clean: null },
  conditionNotes: '',
  photos: { arrival: null, before: null, after: null },
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
    conditions: { prices: null, pop: null, clean: null },
    conditionNotes: '',
    photos: { arrival: null, before: null, after: null },
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

  // Clear all previews
  ['arrival', 'before', 'after'].forEach(type => {
    const preview = document.getElementById(`${type}-preview`);
    if (preview) preview.innerHTML = '';
  });

  // Reset condition buttons
  document.querySelectorAll('.toggle-btn').forEach(btn => {
    btn.classList.remove('selected-yes', 'selected-no');
  });
  document.getElementById('condition-notes-group').style.display = 'none';
  document.getElementById('condition-notes').value = '';
  document.getElementById('visit-notes').value = '';

  // Disable next buttons
  ['btn-step1-next', 'btn-step2-next', 'btn-step3-next', 'btn-step5-next'].forEach(id => {
    const btn = document.getElementById(id);
    if (btn) btn.disabled = true;
  });
}

function showStep(stepNum) {
  visitState.step = stepNum;

  // Hide all steps
  document.querySelectorAll('.visit-step').forEach(el => el.classList.remove('active'));

  // Show current step
  const stepEl = document.getElementById(`visit-step-${stepNum}`);
  if (stepEl) stepEl.classList.add('active');

  // Update step indicator
  document.querySelectorAll('.step-indicator .step').forEach(el => {
    const s = parseInt(el.dataset.step);
    el.classList.remove('active', 'completed');
    if (s < stepNum) el.classList.add('completed');
    else if (s === stepNum) el.classList.add('active');
  });

  // Load step-specific data
  if (stepNum === 4) loadSKUList();
  if (stepNum === 6) showVisitSummary();
}

function nextStep() {
  showStep(visitState.step + 1);
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
  const inputMap = {
    'arrival_proof': 'camera-arrival',
    'shelf_before': 'camera-before',
    'shelf_after': 'camera-after',
  };
  const input = document.getElementById(inputMap[photoType]);
  input.dataset.photoType = photoType;
  input.onchange = (e) => onPhotoSelected(e.target, photoType);
  input.click();
}

async function onPhotoSelected(input, photoType) {
  const file = input.files[0];
  if (!file) return;

  // Store locally
  const keyMap = { 'arrival_proof': 'arrival', 'shelf_before': 'before', 'shelf_after': 'after' };
  visitState.photos[keyMap[photoType]] = file;

  // Show preview
  const previewMap = { 'arrival_proof': 'arrival-preview', 'shelf_before': 'before-preview', 'shelf_after': 'after-preview' };
  const preview = document.getElementById(previewMap[photoType]);
  preview.innerHTML = `<img src="${URL.createObjectURL(file)}">`;

  // Upload to server
  try {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('photo_type', photoType);
    formData.append('latitude', visitState.gps.lat || '');
    formData.append('longitude', visitState.gps.lng || '');
    formData.append('gps_accuracy', visitState.gps.accuracy || '');
    formData.append('captured_at', new Date().toISOString());
    formData.append('run_cv', photoType !== 'arrival_proof' ? 'true' : 'false');

    await api(`/visits/${visitState.visitId}/photos`, { method: 'POST', body: formData });
    toast('Foto guardada');

    // Enable next button
    const btnMap = { 'arrival_proof': 'btn-step1-next', 'shelf_before': 'btn-step2-next', 'shelf_after': 'btn-step5-next' };
    const btn = document.getElementById(btnMap[photoType]);
    if (btn) btn.disabled = false;
  } catch (err) {
    toast('Error subiendo foto: ' + err.message);
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

// ── Step 4: SKU Actions ─────────────────────────────────────────────────

async function loadSKUList() {
  try {
    const approvals = await apiGet(`/approvals/?store_id=${visitState.storeId}`);
    visitState.approvedSkus = approvals.map(a => a.sku);

    const skuList = document.getElementById('visit-sku-list');
    if (approvals.length === 0) {
      skuList.innerHTML = '<p class="meta">No hay SKUs aprobados para esta tienda.</p>';
    } else {
      skuList.innerHTML = approvals.map(a => `
        <li class="sku-item" data-sku-id="${a.sku.id}">
          <span class="sku-name">${a.sku.name} <span class="meta">(${a.sku.brand})</span></span>
          <div class="action-chips">
            <span class="chip chip-llena" onclick="toggleAction(${a.sku.id},'gondola_llena',this)">Llena</span>
            <span class="chip chip-relleno" onclick="toggleAction(${a.sku.id},'se_relleno',this)">Rellenó</span>
            <span class="chip chip-orden" onclick="toggleAction(${a.sku.id},'orden',this)">Orden</span>
          </div>
        </li>
      `).join('');
    }
  } catch (err) {
    toast('Error cargando SKUs');
  }
}

function toggleAction(skuId, action, el) {
  const key = `${skuId}`;

  if (visitState.skuActions[key]?.action_type === action) {
    delete visitState.skuActions[key];
    el.classList.remove('selected');
  } else {
    el.parentElement.querySelectorAll('.chip').forEach(c => c.classList.remove('selected'));
    visitState.skuActions[key] = { sku_id: skuId, action_type: action };
    el.classList.add('selected');
  }
}

// ── Step 6: Summary & Submit ────────────────────────────────────────────

function showVisitSummary() {
  visitState.conditionNotes = document.getElementById('condition-notes').value;

  const actionCounts = { gondola_llena: 0, se_relleno: 0, orden: 0 };
  Object.values(visitState.skuActions).forEach(a => {
    if (actionCounts[a.action_type] !== undefined) actionCounts[a.action_type]++;
  });

  const summaryEl = document.getElementById('visit-summary');
  summaryEl.innerHTML = `
    <div class="summary-item"><span>Tienda:</span><span>${visitState.storeName}</span></div>
    <div class="summary-item"><span>Fotos:</span><span>${Object.values(visitState.photos).filter(p => p).length} de 3</span></div>
    <div class="summary-item"><span>Góndola Llena:</span><span>${actionCounts.gondola_llena}</span></div>
    <div class="summary-item"><span>Se Rellenó:</span><span>${actionCounts.se_relleno}</span></div>
    <div class="summary-item"><span>Orden:</span><span>${actionCounts.orden}</span></div>
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
    const actions = Object.values(visitState.skuActions);
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
      'unknown': 'Desconocido',
    };

    let photosHtml = '';
    for (const photo of (v.photos || [])) {
      let cvHtml = '';
      if (photo.cv_processed && photo.cv_results) {
        const cv = JSON.parse(photo.cv_results);
        cvHtml = `<div class="meta" style="margin-top:4px;">Void: ${(cv.void_space_score * 100).toFixed(1)}% · ${cv.void_regions.length} vacíos · ${cv.detected_products.length} productos</div>`;
      }
      const typeLabel = { 'arrival_proof': 'Llegada', 'shelf_before': 'Antes', 'shelf_after': 'Después' }[photo.photo_type] || photo.photo_type;
      photosHtml += `
        <div style="margin-top:12px;">
          <div class="meta">${typeLabel}</div>
          <img src="${photo.file_path}" style="max-width:100%;border-radius:8px;">
          ${cvHtml}
        </div>`;
    }

    const actionsHtml = (v.sku_actions || []).map(a => {
      const label = actionLabels[a.action_type] || a.action_type;
      const skuName = a.sku ? a.sku.name : `SKU #${a.sku_id}`;
      const badgeClass = a.action_type === 'orden' ? 'red' : a.action_type === 'se_relleno' ? 'green' : 'yellow';
      return `<div><span class="badge badge-${badgeClass}">${label}</span> ${skuName}</div>`;
    }).join('');

    document.getElementById('history-list').innerHTML = `
      <div class="card">
        <button class="btn btn-outline btn-sm" onclick="loadHistoryPage()" style="margin-bottom:12px;">← Atrás</button>
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
  } catch (err) {
    toast('Error cargando detalles');
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
    const [summary, byStore, incidents] = await Promise.all([
      apiGet(`/dashboard/summary${qs}`),
      apiGet(`/dashboard/by-store${qs}`),
      apiGet(`/dashboard/incidents${qs}`),
    ]);

    document.getElementById('stat-visits').textContent = summary.total_visits;
    document.getElementById('stat-coverage').textContent = `${(summary.coverage_rate * 100).toFixed(0)}%`;

    // New action types
    const gondolaLlena = document.getElementById('stat-gondola-llena');
    const seRelleno = document.getElementById('stat-se-relleno');
    const orden = document.getElementById('stat-orden');

    if (gondolaLlena) gondolaLlena.textContent = summary.actions?.gondola_llena || 0;
    if (seRelleno) seRelleno.textContent = summary.actions?.se_relleno || 0;
    if (orden) orden.textContent = summary.actions?.orden || 0;

    document.getElementById('stat-photos').textContent = summary.cv_processed_photos || summary.total_photos || 0;
    document.getElementById('stat-incidents-red').textContent = incidents.red_incidents;
    document.getElementById('stat-total-incidents').textContent = incidents.total_incidents;

    // By-store table
    const tableBody = document.getElementById('store-table-body');
    tableBody.innerHTML = byStore.map(s => `
      <tr>
        <td>${s.store_name}</td>
        <td>${s.region}</td>
        <td>${s.visit_count}</td>
        <td>${s.gondola_llena || s.needs_refill || 0}</td>
        <td>${s.se_relleno || s.placed_on_shelf || 0}</td>
        <td>${s.orden || s.needs_order || 0}</td>
      </tr>
    `).join('');

    // Incidents table
    const incBody = document.getElementById('incidents-table-body');
    incBody.innerHTML = incidents.incidents.map(i => `
      <tr>
        <td>${i.store_name}</td>
        <td>${i.sku_name}</td>
        <td>${i.action_type.replace(/_/g, ' ')}</td>
        <td><span class="badge badge-${i.severity}">${i.age_days}d</span></td>
        <td>${i.merchandiser}</td>
        <td>${new Date(i.reported_at).toLocaleDateString()}</td>
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
