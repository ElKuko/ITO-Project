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
  const navChat = document.getElementById('nav-chat');

  if (navRouteHistory) navRouteHistory.style.display = isAdmin ? 'block' : 'none';
  if (navDashboard) navDashboard.style.display = isAdmin ? 'block' : 'none';
  if (navAdmin) navAdmin.style.display = isAdmin ? 'block' : 'none';

  // Show chat tab for merchandisers (admins have chat in Por Ruta)
  if (navChat) navChat.style.display = !isAdmin ? 'block' : 'none';

  // Restore last active tab or default to 'visit'
  const lastTab = localStorage.getItem('activeTab') || 'visit';
  navigateTo(lastTab);
}

// ── Navigation ──────────────────────────────────────────────────────────
function navigateTo(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-tabs button').forEach(b => b.classList.remove('active'));

  const pageEl = document.getElementById(`page-${page}`);
  const tabEl = document.querySelector(`[data-page="${page}"]`);
  if (pageEl) pageEl.classList.add('active');
  if (tabEl) tabEl.classList.add('active');

  // Remember active tab for page refresh
  localStorage.setItem('activeTab', page);

  switch (page) {
    case 'visit': loadVisitPage(); break;
    case 'chat': loadMerchandiserChatPage(); break;
    case 'route-history': loadRouteHistoryPage(); break;
    case 'dashboard': loadDashboardPage(); break;
    case 'approvals': loadApprovalsPage(); break;
    case 'admin': loadAdminPage(); break;
  }
}

// ══════════════════════════════════════════════════════════════════════════
// ═══ STORE VISIT — 4-Step Workflow (v2) ═══════════════════════════════════
// ══════════════════════════════════════════════════════════════════════════

// Section definitions for the 3-area workflow
const SECTIONS = ['produce', 'provisiones', 'congelados'];
const SECTION_LABELS = {
  produce: 'Produce',
  provisiones: 'Provisiones',
  congelados: 'Congelados',
};

let visitState = {
  step: 0,
  visitId: null,
  storeId: null,
  storeName: '',
  approvedSkus: [],          // All approved SKUs for the store
  skusBySection: {},         // { section: [skus] }
  skuActions: {},            // { skuId: Set of actions }
  ordenQuantities: {},       // { skuId: quantity } for orden actions
  // Per-section state
  selectedSkus: {            // { section: Set of skuIds }
    produce: new Set(),
    provisiones: new Set(),
    congelados: new Set(),
  },
  gondolaGroups: {           // { section: Array of groups }
    produce: [],
    provisiones: [],
    congelados: [],
  },
  // Per-section conditions
  sectionConditions: {
    produce: { prices: null, pop: null, presentable: null, notes: '' },
    provisiones: { prices: null, pop: null, presentable: null, notes: '' },
    congelados: { prices: null, pop: null, presentable: null, notes: '' },
  },
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
    skusBySection: {},
    skuActions: {},
    ordenQuantities: {},
    selectedSkus: {
      produce: new Set(),
      provisiones: new Set(),
      congelados: new Set(),
    },
    gondolaGroups: {
      produce: [],
      provisiones: [],
      congelados: [],
    },
    sectionConditions: {
      produce: { prices: null, pop: null, presentable: null, notes: '' },
      provisiones: { prices: null, pop: null, presentable: null, notes: '' },
      congelados: { prices: null, pop: null, presentable: null, notes: '' },
    },
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

  // Reset bulk toolbar for all sections
  SECTIONS.forEach(section => {
    updateBulkToolbar(section);
    updatePendingWarning(section);
    updateGondolaGroupsSummary(section);
  });

  // Disable step 1 next button
  const btn1 = document.getElementById('btn-step1-next');
  if (btn1) btn1.disabled = true;
}

function showStep(stepNum) {
  visitState.step = stepNum;

  // Hide all steps
  document.querySelectorAll('.visit-step').forEach(el => el.classList.remove('active'));

  // Show current step
  const stepEl = document.getElementById(`visit-step-${stepNum}`);
  if (stepEl) stepEl.classList.add('active');

  // Update step indicator (5 steps)
  document.querySelectorAll('.step-indicator .step').forEach(el => {
    const s = parseInt(el.dataset.step);
    el.classList.remove('active', 'completed');
    if (s < stepNum) el.classList.add('completed');
    else if (s === stepNum) el.classList.add('active');
  });

  // Load step-specific data
  // Steps 2, 3, 4 are section-based SKU steps
  if (stepNum === 2) loadSKUListForSection('produce');
  if (stepNum === 3) loadSKUListForSection('provisiones');
  if (stepNum === 4) loadSKUListForSection('congelados');
  if (stepNum === 5) showVisitSummary();
}

function nextStep() {
  showStep(visitState.step + 1);
}

function prevStep() {
  if (visitState.step > 0) {
    showStep(visitState.step - 1);
  }
}

function validateStep2AndNext() {
  // Legacy function - now use validateSectionAndNext
  validateSectionAndNext('produce');
}

function validateSectionAndNext(section) {
  // Check if there are any gondola groups with missing after photos for this section
  const pendingGroups = visitState.gondolaGroups[section].filter(g => !g.afterPhoto);

  if (pendingGroups.length > 0) {
    toast(`Faltan ${pendingGroups.length} foto(s) DESPUÉS en ${SECTION_LABELS[section]}. Complete todos los grupos antes de continuar.`);
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

// Track current section for photo capture
let currentPhotoSection = null;

function captureGondolaBefore(section) {
  currentPhotoSection = section;
  if (visitState.selectedSkus[section].size === 0) {
    toast('Seleccione SKUs primero');
    return;
  }
  const input = document.getElementById(`camera-gondola-before-${section}`);
  input.onchange = (e) => onGondolaBeforeSelected(e.target, section);
  input.click();
}

async function onGondolaBeforeSelected(input, section) {
  const file = input.files[0];
  if (!file) return;

  // Generate a new gondola group ID
  const groupId = crypto.randomUUID ? crypto.randomUUID() : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0;
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });

  // Get selected SKU IDs
  const skuIds = Array.from(visitState.selectedSkus[section]);

  // Create local gondola group record
  const group = {
    groupId: groupId,
    section: section,
    skuIds: [...skuIds],
    beforePhoto: URL.createObjectURL(file),
    afterPhoto: null,
  };
  visitState.gondolaGroups[section].push(group);

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
    clearSkuSelection(section);

    // Update UI
    updatePendingWarning(section);
    updateGondolaGroupsSummary(section);
  } catch (err) {
    toast('Error subiendo foto: ' + err.message);
    // Remove the group on error
    visitState.gondolaGroups[section].pop();
  }
}

function captureGondolaAfter(section) {
  currentPhotoSection = section;
  // Find groups that need after photos
  const pendingGroups = visitState.gondolaGroups[section].filter(g => !g.afterPhoto);
  if (pendingGroups.length === 0) {
    toast('No hay fotos ANTES pendientes');
    return;
  }

  // If only one pending group, take photo directly
  if (pendingGroups.length === 1) {
    triggerAfterPhotoCapture(pendingGroups[0].groupId, section);
    return;
  }

  // Multiple pending groups: show picker
  showGondolaPicker(pendingGroups, section);
}

function showGondolaPicker(pendingGroups, section) {
  const grid = document.getElementById('gondola-picker-grid');

  grid.innerHTML = pendingGroups.map((group, idx) => {
    const skuNames = group.skuIds.map(id => {
      const sku = visitState.approvedSkus.find(s => s.id === id);
      return sku ? sku.name : `SKU #${id}`;
    }).slice(0, 2).join(', ') + (group.skuIds.length > 2 ? ` (+${group.skuIds.length - 2})` : '');

    return `
      <div class="gondola-picker-item" onclick="selectGondolaForAfter('${group.groupId}', '${section}')">
        <img class="picker-thumbnail" src="${group.beforePhoto}" alt="Antes">
        <div class="picker-label">Grupo ${visitState.gondolaGroups[section].indexOf(group) + 1}</div>
        <div class="picker-skus">${skuNames}</div>
      </div>
    `;
  }).join('');

  document.getElementById('modal-gondola-picker').style.display = 'flex';
}

function selectGondolaForAfter(groupId, section) {
  closeModal('modal-gondola-picker');
  triggerAfterPhotoCapture(groupId, section);
}

function triggerAfterPhotoCapture(groupId, section) {
  const input = document.getElementById(`camera-gondola-after-${section}`);
  input.dataset.groupId = groupId;
  input.dataset.section = section;
  input.onchange = (e) => onGondolaAfterSelected(e.target, groupId, section);
  input.click();
}

async function onGondolaAfterSelected(input, groupId, section) {
  const file = input.files[0];
  if (!file) return;

  // Find the group
  const group = visitState.gondolaGroups[section].find(g => g.groupId === groupId);
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
    updatePendingWarning(section);
    updateGondolaGroupsSummary(section);
  } catch (err) {
    toast('Error subiendo foto: ' + err.message);
    group.afterPhoto = null;
  }
}

// ── Step 5: Condition Checks ────────────────────────────────────────────

// ── Section Conditions ──────────────────────────────────────────────────

function setSectionCondition(section, field, value, btn) {
  visitState.sectionConditions[section][field] = value;

  // Update button styles
  btn.parentElement.querySelectorAll('.toggle-btn').forEach(b => {
    b.classList.remove('selected-yes', 'selected-no');
  });
  btn.classList.add(value ? 'selected-yes' : 'selected-no');

  // Show notes field if any "No" in this section
  const cond = visitState.sectionConditions[section];
  const anyNo = cond.prices === false || cond.pop === false || cond.presentable === false;
  const notesGroup = document.getElementById(`condition-notes-group-${section}`);
  if (notesGroup) {
    notesGroup.style.display = anyNo ? 'block' : 'none';
  }
}

function updateSectionConditionNotes(section, notes) {
  visitState.sectionConditions[section].notes = notes;
}

// ── Section-based SKU List with Checkboxes ──────────────────────────────

// Get current section based on step number
function getCurrentSection() {
  switch (visitState.step) {
    case 2: return 'produce';
    case 3: return 'provisiones';
    case 4: return 'congelados';
    default: return null;
  }
}

async function loadSKUListForSection(section) {
  try {
    // Load all approvals once and cache them
    if (visitState.approvedSkus.length === 0) {
      const approvals = await apiGet(`/approvals/?store_id=${visitState.storeId}`);
      visitState.approvedSkus = approvals.map(a => a.sku);

      // Group SKUs by section
      visitState.skusBySection = {
        produce: [],
        provisiones: [],
        congelados: [],
      };
      for (const sku of visitState.approvedSkus) {
        const sec = sku.section || 'provisiones'; // default to provisiones if no section
        if (visitState.skusBySection[sec]) {
          visitState.skusBySection[sec].push(sku);
        }
      }
    }

    const sectionSkus = visitState.skusBySection[section] || [];
    const skuList = document.getElementById(`visit-sku-list-${section}`);

    if (sectionSkus.length === 0) {
      skuList.innerHTML = `<p class="meta">No hay SKUs de ${SECTION_LABELS[section]} aprobados para esta tienda.</p>`;
    } else {
      skuList.innerHTML = sectionSkus.map(sku => `
        <li class="sku-item" data-sku-id="${sku.id}" data-section="${section}" id="sku-item-${section}-${sku.id}">
          <input type="checkbox" class="sku-checkbox" id="sku-check-${section}-${sku.id}"
                 onchange="toggleSkuSelection('${section}', ${sku.id}, this.checked)">
          <div class="sku-info">
            <span class="sku-name">${sku.name}</span>
            <span class="sku-meta">${sku.brand}${sku.category ? ' · ' + sku.category : ''}</span>
          </div>
          <div class="action-chips" id="chips-${sku.id}">
            <span class="chip chip-llena" data-action="gondola_llena" onclick="toggleAction(${sku.id},'gondola_llena',this)">Llena</span>
            <span class="chip chip-relleno" data-action="se_relleno" onclick="toggleAction(${sku.id},'se_relleno',this)">Rellenó</span>
            <span class="chip chip-orden" data-action="orden" onclick="toggleAction(${sku.id},'orden',this)">Orden</span>
            <span class="chip chip-agotado" data-action="agotado" onclick="toggleAction(${sku.id},'agotado',this)">Agotado</span>
          </div>
        </li>
      `).join('');
    }

    // Restore saved state for this section
    restoreSectionState(section);

    // Update UI for this section
    updateBulkToolbar(section);
    updatePendingWarning(section);
    updateGondolaGroupsSummary(section);
  } catch (err) {
    toast('Error cargando SKUs');
  }
}

function restoreSectionState(section) {
  // Restore checkbox selections
  visitState.selectedSkus[section].forEach(skuId => {
    const checkbox = document.getElementById(`sku-check-${section}-${skuId}`);
    if (checkbox) {
      checkbox.checked = true;
      document.getElementById(`sku-item-${section}-${skuId}`)?.classList.add('selected');
    }
  });

  // Restore action chip states
  const sectionSkus = visitState.skusBySection[section] || [];
  sectionSkus.forEach(sku => {
    const actions = visitState.skuActions[`${sku.id}`];
    if (actions && actions.size > 0) {
      const chipsContainer = document.getElementById(`chips-${sku.id}`);
      if (chipsContainer) {
        // Apply selected state to active chips
        actions.forEach(action => {
          const chip = chipsContainer.querySelector(`[data-action="${action}"]`);
          if (chip) chip.classList.add('selected');
        });

        // If agotado is selected, disable llena/relleno
        if (actions.has('agotado')) {
          disableChips(chipsContainer, ['gondola_llena', 'se_relleno']);
        }
      }
    }

    // Restore orden quantity display
    const qty = visitState.ordenQuantities[sku.id];
    if (qty && qty > 0) {
      const chipsContainer = document.getElementById(`chips-${sku.id}`);
      if (chipsContainer) {
        const ordenChip = chipsContainer.querySelector('[data-action="orden"]');
        if (ordenChip) {
          ordenChip.classList.add('selected');
          ordenChip.textContent = `Orden (${qty})`;
        }
      }
    }
  });

  // Restore condition button states
  const cond = visitState.sectionConditions[section];
  ['prices', 'pop', 'presentable'].forEach(field => {
    const value = cond[field];
    if (value !== null) {
      const btns = document.querySelectorAll(`.toggle-btn[data-section="${section}"][data-field="${field}"]`);
      btns.forEach(btn => {
        btn.classList.remove('selected-yes', 'selected-no');
        const btnValue = btn.textContent.trim() === 'Sí';
        if (btnValue === value) {
          btn.classList.add(value ? 'selected-yes' : 'selected-no');
        }
      });
    }
  });

  // Show notes field if any "No"
  const anyNo = cond.prices === false || cond.pop === false || cond.presentable === false;
  const notesGroup = document.getElementById(`condition-notes-group-${section}`);
  if (notesGroup) {
    notesGroup.style.display = anyNo ? 'block' : 'none';
    const notesTextarea = document.getElementById(`condition-notes-${section}`);
    if (notesTextarea && cond.notes) {
      notesTextarea.value = cond.notes;
    }
  }
}

// Legacy function for backwards compatibility
async function loadSKUList() {
  const section = getCurrentSection();
  if (section) {
    await loadSKUListForSection(section);
  }
}

// ── SKU Selection for Bulk Actions ──────────────────────────────────────

function toggleSkuSelection(section, skuId, selected) {
  if (selected) {
    visitState.selectedSkus[section].add(skuId);
    document.getElementById(`sku-item-${section}-${skuId}`)?.classList.add('selected');
  } else {
    visitState.selectedSkus[section].delete(skuId);
    document.getElementById(`sku-item-${section}-${skuId}`)?.classList.remove('selected');
  }
  updateBulkToolbar(section);
}

function clearSkuSelection(section) {
  visitState.selectedSkus[section].forEach(skuId => {
    const checkbox = document.getElementById(`sku-check-${section}-${skuId}`);
    if (checkbox) checkbox.checked = false;
    document.getElementById(`sku-item-${section}-${skuId}`)?.classList.remove('selected');
  });
  visitState.selectedSkus[section].clear();
  updateBulkToolbar(section);
}

function updateBulkToolbar(section) {
  const count = visitState.selectedSkus[section].size;
  const countEl = document.getElementById(`selected-count-${section}`);
  if (countEl) countEl.textContent = count;

  // Enable/disable bulk action buttons
  const hasSelection = count > 0;
  const beforeBtn = document.getElementById(`btn-gondola-before-${section}`);
  const clearBtn = document.getElementById(`btn-clear-selection-${section}`);
  if (beforeBtn) beforeBtn.disabled = !hasSelection;
  if (clearBtn) clearBtn.disabled = !hasSelection;

  // After photo button enabled only if there are pending groups
  const pendingGroups = visitState.gondolaGroups[section].filter(g => !g.afterPhoto);
  const afterBtn = document.getElementById(`btn-gondola-after-${section}`);
  if (afterBtn) afterBtn.disabled = pendingGroups.length === 0;
}

function updatePendingWarning(section) {
  const pendingGroups = visitState.gondolaGroups[section].filter(g => !g.afterPhoto);
  const warningEl = document.getElementById(`pending-warning-${section}`);
  const countEl = document.getElementById(`pending-count-${section}`);

  if (warningEl && countEl) {
    if (pendingGroups.length > 0) {
      countEl.textContent = pendingGroups.length;
      warningEl.style.display = 'flex';
    } else {
      warningEl.style.display = 'none';
    }
  }
}

function updateGondolaGroupsSummary(section) {
  const container = document.getElementById(`gondola-groups-summary-${section}`);
  if (!container) return;

  const groups = visitState.gondolaGroups[section];
  if (groups.length === 0) {
    container.innerHTML = '';
    return;
  }

  container.innerHTML = '<h4 style="margin-bottom:8px;font-size:14px;">Grupos de Góndola</h4>' +
    groups.map((group, idx) => {
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

// ── Step 5: Summary & Submit ────────────────────────────────────────────

function showVisitSummary() {
  // Count actions from Sets (multi-select)
  const actionCounts = { gondola_llena: 0, se_relleno: 0, orden: 0, agotado: 0 };
  Object.values(visitState.skuActions).forEach(actionsSet => {
    actionsSet.forEach(action => {
      if (actionCounts[action] !== undefined) actionCounts[action]++;
    });
  });

  // Calculate total boxes ordered
  const totalBoxesOrdered = Object.values(visitState.ordenQuantities).reduce((sum, qty) => sum + qty, 0);

  // Count photos across all sections: 1 arrival + gondola groups (before + after)
  const arrivalCount = visitState.photos.arrival ? 1 : 0;
  let gondolaBeforeCount = 0;
  let gondolaAfterCount = 0;
  let totalGroups = 0;

  SECTIONS.forEach(section => {
    const groups = visitState.gondolaGroups[section] || [];
    totalGroups += groups.length;
    gondolaBeforeCount += groups.filter(g => g.beforePhoto).length;
    gondolaAfterCount += groups.filter(g => g.afterPhoto).length;
  });

  const totalPhotos = arrivalCount + gondolaBeforeCount + gondolaAfterCount;
  const pendingAfter = gondolaBeforeCount - gondolaAfterCount;

  // Build conditions summary per section
  const condIcon = (val) => val === true ? '✓' : val === false ? '✗' : '—';
  const condClass = (val) => val === true ? 'cond-ok' : val === false ? 'cond-no' : 'cond-na';

  let conditionsHtml = '';
  SECTIONS.forEach(section => {
    const cond = visitState.sectionConditions[section];
    const label = SECTION_LABELS[section];
    conditionsHtml += `
      <div class="summary-section-conditions">
        <strong>${label}:</strong>
        <span class="${condClass(cond.prices)}">Precios ${condIcon(cond.prices)}</span>
        <span class="${condClass(cond.pop)}">PoP ${condIcon(cond.pop)}</span>
        <span class="${condClass(cond.presentable)}">Presentable ${condIcon(cond.presentable)}</span>
        ${cond.notes ? `<span class="cond-notes">(${cond.notes})</span>` : ''}
      </div>
    `;
  });

  const summaryEl = document.getElementById('visit-summary');
  summaryEl.innerHTML = `
    <div class="summary-item"><span>Tienda:</span><span>${visitState.storeName}</span></div>
    <div class="summary-item"><span>Fotos:</span><span>${totalPhotos} (${arrivalCount} llegada, ${gondolaBeforeCount} antes, ${gondolaAfterCount} después)</span></div>
    <div class="summary-item"><span>Grupos Góndola:</span><span>${totalGroups}${pendingAfter > 0 ? ` (${pendingAfter} pendiente)` : ''}</span></div>
    <div class="summary-item"><span>Góndola Llena:</span><span>${actionCounts.gondola_llena}</span></div>
    <div class="summary-item"><span>Se Rellenó:</span><span>${actionCounts.se_relleno}</span></div>
    <div class="summary-item"><span>Orden:</span><span>${actionCounts.orden} SKU(s)${totalBoxesOrdered > 0 ? ` — ${totalBoxesOrdered} cajas` : ''}</span></div>
    <div class="summary-item"><span>Agotado:</span><span>${actionCounts.agotado}</span></div>
    <div class="summary-divider"></div>
    <div class="summary-conditions-header">Condiciones por Sección:</div>
    ${conditionsHtml}
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
      section_conditions: visitState.sectionConditions,
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

async function showVisitDetail(visitId, highlightGroupId = null, highlightPhotoType = null) {
  try {
    const v = await apiGet(`/visits/${visitId}`);
    const date = new Date(v.start_time).toLocaleString();
    const storeName = v.store ? v.store.name : `Tienda #${v.store_id}`;
    const storeId = v.store_id;
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
        const isHighlighted = highlightGroupId === groupId;

        // Build comment button for before photo
        const beforeCommentBtn = group.before ? `
          <button class="photo-action-btn" onclick="event.stopPropagation(); commentOnImage(
            ${visitId}, ${storeId}, '${storeName.replace(/'/g, "\\'")}',
            ${group.before.id}, 'BEFORE', '${groupId}',
            '${group.before.file_path}', '${group.before.captured_at || ''}'
          )">
            <span>💬</span> Comentar
          </button>
        ` : '';

        // Build annotate button for before photo
        const beforeAnnotateBtn = group.before ? `
          <button class="photo-action-btn btn-annotate" onclick="event.stopPropagation(); openAnnotationEditor({
            visitId: ${visitId},
            storeId: ${storeId},
            storeName: '${storeName.replace(/'/g, "\\'")}',
            photoId: ${group.before.id},
            photoType: 'BEFORE',
            gondolaGroupId: '${groupId}',
            photoUrl: '${group.before.file_path}',
            capturedAt: '${group.before.captured_at || ''}',
            routeId: chatState.routeId
          })">
            <span>✏️</span> Anotar
          </button>
        ` : '';

        // Build comment button for after photo
        const afterCommentBtn = group.after ? `
          <button class="photo-action-btn" onclick="event.stopPropagation(); commentOnImage(
            ${visitId}, ${storeId}, '${storeName.replace(/'/g, "\\'")}',
            ${group.after.id}, 'AFTER', '${groupId}',
            '${group.after.file_path}', '${group.after.captured_at || ''}'
          )">
            <span>💬</span> Comentar
          </button>
        ` : '';

        // Build annotate button for after photo
        const afterAnnotateBtn = group.after ? `
          <button class="photo-action-btn btn-annotate" onclick="event.stopPropagation(); openAnnotationEditor({
            visitId: ${visitId},
            storeId: ${storeId},
            storeName: '${storeName.replace(/'/g, "\\'")}',
            photoId: ${group.after.id},
            photoType: 'AFTER',
            gondolaGroupId: '${groupId}',
            photoUrl: '${group.after.file_path}',
            capturedAt: '${group.after.captured_at || ''}',
            routeId: chatState.routeId
          })">
            <span>✏️</span> Anotar
          </button>
        ` : '';

        gondolaHtml += `
          <div class="photo-compare-group ${isHighlighted ? 'highlighted' : ''}" style="margin-top:12px;" data-group-id="${groupId}">
            <div class="compare-header meta">Grupo ${idx + 1}</div>
            <div class="photo-compare-row">
              <div class="photo-compare-col ${isHighlighted && highlightPhotoType === 'BEFORE' ? 'photo-highlighted' : ''}">
                <div class="compare-label">ANTES</div>
                ${group.before
                  ? `<img src="${group.before.file_path}" class="compare-img">
                     <div class="photo-card-actions">${beforeCommentBtn}${beforeAnnotateBtn}</div>`
                  : '<div class="compare-placeholder">Sin foto</div>'}
              </div>
              <div class="photo-compare-col ${isHighlighted && highlightPhotoType === 'AFTER' ? 'photo-highlighted' : ''}">
                <div class="compare-label">DESPUÉS</div>
                ${group.after
                  ? `<img src="${group.after.file_path}" class="compare-img">
                     <div class="photo-card-actions">${afterCommentBtn}${afterAnnotateBtn}</div>`
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

    // Scroll to highlighted group if navigating from chat
    if (highlightGroupId) {
      setTimeout(() => {
        const highlightedGroup = detailContainer.querySelector(`[data-group-id="${highlightGroupId}"]`);
        if (highlightedGroup) {
          highlightedGroup.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }, 100);
    }
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

    // Group SKUs by section
    const sections = ['produce', 'provisiones', 'congelados'];
    const grouped = { produce: [], provisiones: [], congelados: [] };

    allSkus.forEach(sku => {
      const section = sku.section || 'provisiones';
      if (grouped[section]) {
        grouped[section].push(sku);
      } else {
        grouped.provisiones.push(sku);
      }
    });

    const skuList = document.getElementById('approval-sku-list');
    skuList.innerHTML = sections.map(section => {
      const sectionSkus = grouped[section];
      if (sectionSkus.length === 0) return '';

      return `
        <li class="approval-section-header">${SECTION_LABELS[section]}</li>
        ${sectionSkus.map(sku => `
          <li class="approval-item">
            <input type="checkbox" id="sku-${sku.id}" value="${sku.id}" ${approvedIds.has(sku.id) ? 'checked' : ''}>
            <label for="sku-${sku.id}">${sku.name} <span class="meta">(${sku.brand})</span></label>
          </li>
        `).join('')}
      `;
    }).join('');

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
  else if (tab === 'routes') loadAdminRoutes();
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
  const container = document.getElementById('admin-skus-container');

  // Group SKUs by section
  const sections = ['produce', 'provisiones', 'congelados'];
  const grouped = {
    produce: [],
    provisiones: [],
    congelados: []
  };

  skus.forEach(s => {
    const section = s.section || 'provisiones';
    if (grouped[section]) {
      grouped[section].push(s);
    } else {
      grouped.provisiones.push(s);
    }
  });

  // Render each section
  container.innerHTML = sections.map(section => {
    const sectionSkus = grouped[section];
    if (sectionSkus.length === 0) return '';

    return `
      <div class="sku-section-group">
        <h4 class="sku-section-title">${SECTION_LABELS[section]}</h4>
        <div class="table-wrapper">
          <table>
            <thead>
              <tr>
                <th>Nombre</th><th>Marca</th><th>Categoría</th><th>Código</th><th>Estado</th><th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              ${sectionSkus.map(s => `
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
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }).join('');
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

// ── Route Assignment Management ──────────────────────────────────────────

let adminRoutes = {
  routes: [],
  merchandisers: [],
};

async function loadAdminRoutes() {
  try {
    // Load routes and merchandisers in parallel
    const [routes, merchandisers] = await Promise.all([
      apiGet('/routes/'),
      apiGet('/users/?role=merchandiser'),
    ]);

    adminRoutes.routes = routes;
    adminRoutes.merchandisers = merchandisers;

    renderRoutesTable();
  } catch (err) {
    toast('Error cargando rutas');
  }
}

function renderRoutesTable() {
  const tbody = document.getElementById('admin-routes-table');
  if (!tbody) return;

  tbody.innerHTML = adminRoutes.routes.map(r => {
    const merchandiserOptions = adminRoutes.merchandisers.map(m => {
      const selected = r.merchandiser?.id === m.id ? 'selected' : '';
      return `<option value="${m.id}" ${selected}>${m.full_name}</option>`;
    }).join('');

    return `
      <tr>
        <td><strong>${r.name}</strong></td>
        <td>${r.store_count} tiendas</td>
        <td>
          <select class="route-assign-select" onchange="assignMerchandiserToRoute(${r.id}, this.value)">
            <option value="">-- Sin asignar --</option>
            ${merchandiserOptions}
          </select>
        </td>
        <td>
          ${r.merchandiser ? `<span class="status-active">Asignado</span>` : `<span class="status-inactive">Sin asignar</span>`}
        </td>
      </tr>
    `;
  }).join('');
}

async function assignMerchandiserToRoute(routeId, merchandiserId) {
  try {
    const merchId = merchandiserId ? parseInt(merchandiserId) : null;
    await api(`/routes/${routeId}/assign?merchandiser_id=${merchId || ''}`, { method: 'PUT' });
    toast(merchId ? 'Merchandiser asignado' : 'Asignación removida');
    loadAdminRoutes();
  } catch (err) {
    toast('Error: ' + err.message);
    loadAdminRoutes(); // Reload to reset select
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
  isLoading: false,   // Guard against concurrent loads
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

  // Only re-render if user is on the route-history page
  const pageEl = document.getElementById('page-route-history');
  if (pageEl && pageEl.classList.contains('active')) {
    renderAllNotificationPanels();
    updateUnreadBadges();
  }
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

  // Prevent concurrent loads - abort if already loading
  if (notificationState.isLoading) {
    console.log('loadNotificationPanels already in progress, skipping');
    return;
  }
  notificationState.isLoading = true;

  grid.innerHTML = '<p class="meta">Cargando rutas...</p>';

  try {
    // Load routes and notification counts
    const [routes, countsData] = await Promise.all([
      apiGet('/routes/'),
      apiGet('/notifications/counts'),
    ]);

    // Guard: check if we're still on the route-history page
    const pageEl = document.getElementById('page-route-history');
    if (!pageEl || !pageEl.classList.contains('active')) {
      console.log('User navigated away during load, aborting');
      notificationState.isLoading = false;
      return;
    }

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

    // Initialize WebSocket for notifications
    initNotificationWebSocket();

    // Initialize route chat
    initRouteChat();

  } catch (err) {
    console.error('Error loading notification panels:', err);
    grid.innerHTML = '<p class="meta" style="color:var(--danger);">Error cargando notificaciones.</p>';
  } finally {
    notificationState.isLoading = false;
  }
}

async function loadAllRouteNotifications() {
  // Load recent notifications (both read and unread to preserve history)
  try {
    const notifications = await apiGet('/notifications/?limit=100');
    notificationState.notifications = notifications;

    if (notifications.length > 0) {
      notificationState.lastEventId = Math.max(...notifications.map(n => n.id));
    }

    renderAllNotificationPanels();
  } catch (err) {
    console.error('Error loading notifications:', err);
    // Re-render panels with empty state rather than leaving "Cargando..."
    notificationState.notifications = [];
    renderAllNotificationPanels();
  }
}

function renderAllNotificationPanels() {
  // Safety check: don't render if routes array is empty
  if (!notificationState.routes || notificationState.routes.length === 0) {
    console.warn('No routes available for rendering notification panels');
    return;
  }

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
  if (!listEl) {
    // DOM element not found - may occur during rapid tab switching
    console.warn(`notification-list-${routeId} not found, skipping render`);
    return;
  }

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

// ══════════════════════════════════════════════════════════════════════════
// ═══ ROUTE CHAT (Real-time messaging) ═════════════════════════════════════
// ══════════════════════════════════════════════════════════════════════════

/**
 * Chat state management for route chat panel
 */
let chatState = {
  ws: null,
  connected: false,
  routeId: null,  // Current route ID (Norte)
  messages: [],
  lastMessageId: null,
  taggedReference: null,  // Reference to attach to next message
  reconnectAttempts: 0,
  maxReconnectAttempts: 5,
};

/**
 * Initialize chat WebSocket when user navigates to Por Ruta page
 */
function initChatWebSocket(routeId) {
  if (getUserRole() !== 'admin') return;
  if (chatState.ws && chatState.connected && chatState.routeId === routeId) return;

  // Disconnect previous if different route
  if (chatState.ws && chatState.routeId !== routeId) {
    closeChatWebSocket();
  }

  chatState.routeId = routeId;

  const token = getToken();
  if (!token) return;

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  let wsUrl = `${protocol}//${host}/api/chat/ws/${routeId}?token=${token}`;

  if (chatState.lastMessageId) {
    wsUrl += `&last_message_id=${chatState.lastMessageId}`;
  }

  try {
    chatState.ws = new WebSocket(wsUrl);

    chatState.ws.onopen = () => {
      chatState.connected = true;
      chatState.reconnectAttempts = 0;
      updateChatWsStatus('connected', 'Conectado');
      console.log(`Chat WebSocket connected for route ${routeId}`);
    };

    chatState.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleChatWebSocketMessage(msg);
      } catch (e) {
        console.error('Error parsing chat WebSocket message:', e);
      }
    };

    chatState.ws.onclose = (event) => {
      chatState.connected = false;
      updateChatWsStatus('disconnected', 'Desconectado');
      console.log('Chat WebSocket closed:', event.code, event.reason);

      // Auto-reconnect if not intentional close
      if (event.code !== 1000 && chatState.reconnectAttempts < chatState.maxReconnectAttempts) {
        const delay = Math.min(1000 * Math.pow(2, chatState.reconnectAttempts), 30000);
        chatState.reconnectAttempts++;
        setTimeout(() => {
          if (document.getElementById('page-route-history')?.classList.contains('active')) {
            initChatWebSocket(routeId);
          }
        }, delay);
      }
    };

    chatState.ws.onerror = (error) => {
      console.error('Chat WebSocket error:', error);
      updateChatWsStatus('error', 'Error');
    };

  } catch (e) {
    console.error('Failed to create chat WebSocket:', e);
  }
}

function closeChatWebSocket() {
  if (chatState.ws) {
    chatState.ws.close(1000, 'User navigated away');
    chatState.ws = null;
  }
  chatState.connected = false;
}

function updateChatWsStatus(status, text) {
  const statusEl = document.getElementById('chat-ws-status');
  if (statusEl) {
    statusEl.textContent = text;
    statusEl.className = 'chat-ws-status ' + status;
  }
}

/**
 * Handle incoming WebSocket messages
 */
function handleChatWebSocketMessage(msg) {
  switch (msg.type) {
    case 'connected':
      console.log('Chat connected:', msg.data);
      break;

    case 'chat_message':
      handleIncomingChatMessage(msg.data);
      break;

    case 'chat_sync':
      // Sync missed messages on reconnect
      if (msg.data.messages && msg.data.messages.length > 0) {
        msg.data.messages.forEach(m => {
          if (!chatState.messages.find(existing => existing.id === m.id)) {
            chatState.messages.push(m);
          }
        });
        chatState.messages.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
        renderChatMessages();
      }
      break;

    case 'pong':
      // Keepalive response
      break;

    default:
      console.log('Unknown chat message type:', msg.type);
  }
}

/**
 * Handle incoming chat message
 */
function handleIncomingChatMessage(message) {
  // Add to state
  chatState.messages.push(message);
  chatState.lastMessageId = message.id;

  // Render the new message
  renderNewChatMessage(message);

  // Mark as read if from other user
  const currentUserId = getUserId();
  if (message.sender_user_id !== currentUserId) {
    markChatMessagesRead([message.id]);
  }
}

/**
 * Load chat messages for current route
 */
async function loadChatMessages(routeId) {
  try {
    const messages = await apiGet(`/chat/routes/${routeId}/messages?limit=50`);
    chatState.messages = messages.reverse();  // API returns newest first
    if (messages.length > 0) {
      chatState.lastMessageId = Math.max(...messages.map(m => m.id));
    }
    renderChatMessages();
  } catch (e) {
    console.error('Error loading chat messages:', e);
  }
}

/**
 * Render all chat messages
 */
function renderChatMessages() {
  const container = document.getElementById('chat-messages');
  if (!container) return;

  const currentUserId = getUserId();

  if (chatState.messages.length === 0) {
    container.innerHTML = `
      <div class="chat-empty-state">
        <p>No hay mensajes aún</p>
        <p class="meta">Los mensajes aparecerán aquí en tiempo real</p>
      </div>
    `;
    return;
  }

  let html = '';
  let lastDate = null;

  chatState.messages.forEach(msg => {
    const msgDate = new Date(msg.created_at).toLocaleDateString();
    if (msgDate !== lastDate) {
      html += `<div class="chat-date-separator"><span>${msgDate}</span></div>`;
      lastDate = msgDate;
    }
    html += renderChatMessage(msg, currentUserId);
  });

  container.innerHTML = html;

  // Scroll to bottom
  container.scrollTop = container.scrollHeight;
}

/**
 * Render a single chat message
 */
function renderChatMessage(msg, currentUserId) {
  const isSent = msg.sender_user_id === currentUserId;
  const time = new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  let referenceHtml = '';
  if (msg.message_type === 'TAGGED_REFERENCE' && msg.ref_photo_url) {
    referenceHtml = `
      <div class="chat-message-reference" onclick="navigateToTaggedPhoto(${msg.ref_visit_id}, '${msg.ref_gondola_group_id || ''}', '${msg.ref_photo_type || ''}')">
        <div class="reference-preview-row">
          <img class="reference-preview-thumbnail" src="${msg.ref_photo_url}" alt="Reference">
          <div class="reference-preview-info">
            <span class="reference-preview-store">${msg.ref_store_name || 'Tienda'}</span>
            <span class="reference-preview-meta">${msg.ref_photo_type || 'Photo'}</span>
            <span class="reference-preview-badge">${msg.ref_photo_type === 'BEFORE' ? 'Antes' : 'Después'}</span>
          </div>
        </div>
      </div>
    `;
  }

  // Handle annotated reference messages
  if (msg.message_type === 'ANNOTATED_REFERENCE') {
    const previewUrl = msg.ref_annotation_preview_url || msg.ref_photo_url;
    referenceHtml = `
      <div class="chat-message-annotation" onclick="navigateToTaggedPhoto(${msg.ref_visit_id}, '${msg.ref_gondola_group_id || ''}', '${msg.ref_photo_type || ''}')">
        <div class="reference-preview-row">
          <img class="reference-preview-thumbnail" src="${previewUrl}" alt="Annotated" style="max-height:150px;object-fit:contain;">
          <div class="reference-preview-info">
            <span class="reference-preview-store">${msg.ref_store_name || 'Tienda'}</span>
            <span class="reference-preview-meta">Imagen Anotada</span>
            <span class="reference-preview-badge" style="background:#ef4444;">${msg.ref_photo_type === 'BEFORE' ? 'Antes' : 'Después'}</span>
          </div>
        </div>
      </div>
    `;
  }

  return `
    <div class="chat-message ${isSent ? 'sent' : 'received'}" data-message-id="${msg.id}">
      ${!isSent ? `<div class="chat-message-sender">${msg.sender_name || 'Usuario'}</div>` : ''}
      <div class="chat-message-bubble">
        ${referenceHtml}
        ${escapeHtml(msg.text)}
      </div>
      <div class="chat-message-meta">${time}</div>
    </div>
  `;
}

/**
 * Render a new message (append to list)
 */
function renderNewChatMessage(msg) {
  const container = document.getElementById('chat-messages');
  if (!container) return;

  // Remove empty state if present
  const emptyState = container.querySelector('.chat-empty-state');
  if (emptyState) emptyState.remove();

  const currentUserId = getUserId();
  const html = renderChatMessage(msg, currentUserId);

  const wrapper = document.createElement('div');
  wrapper.innerHTML = html;
  const newEl = wrapper.firstElementChild;

  container.appendChild(newEl);

  // Scroll to bottom
  container.scrollTop = container.scrollHeight;
}

/**
 * Send a chat message
 */
async function sendChatMessage() {
  const input = document.getElementById('chat-input');
  const text = input?.value?.trim();

  if (!text) return;
  if (!chatState.routeId) {
    toast('No hay ruta seleccionada');
    return;
  }

  const messageData = {
    route_id: chatState.routeId,
    text: text,
    message_type: chatState.taggedReference ? 'TAGGED_REFERENCE' : 'TEXT',
  };

  if (chatState.taggedReference) {
    messageData.reference = chatState.taggedReference;
  }

  // Send via WebSocket if connected, otherwise via REST
  if (chatState.ws && chatState.connected) {
    chatState.ws.send(JSON.stringify({
      type: 'send_message',
      data: messageData
    }));
    // Clear input immediately (message will appear via WebSocket)
    input.value = '';
    clearTaggedReference();
  } else {
    // Fallback to REST API
    try {
      const response = await apiPost(`/chat/routes/${chatState.routeId}/messages`, messageData);
      input.value = '';
      clearTaggedReference();
      // Manually add message to state and render
      handleIncomingChatMessage(response);
    } catch (e) {
      toast('Error al enviar mensaje');
    }
  }
}

/**
 * Mark messages as read
 */
async function markChatMessagesRead(messageIds) {
  if (!chatState.routeId || messageIds.length === 0) return;

  if (chatState.ws && chatState.connected) {
    chatState.ws.send(JSON.stringify({
      type: 'mark_read',
      data: { message_ids: messageIds }
    }));
  } else {
    try {
      await apiPost(`/chat/routes/${chatState.routeId}/messages/mark-read`, {
        message_ids: messageIds
      });
    } catch (e) {
      // Ignore errors
    }
  }
}

// ── Tagged Reference (Image Tagging) ──────────────────────────────────────

/**
 * Set a tagged reference to attach to the next message
 * Called from the Visit Detail view when user clicks "Comentar en chat"
 */
function setTaggedReference(reference) {
  chatState.taggedReference = reference;

  // Show reference preview in composer
  const previewEl = document.getElementById('chat-reference-preview');
  const thumbnailEl = document.getElementById('reference-thumbnail');
  const storeEl = document.getElementById('reference-store');
  const metaEl = document.getElementById('reference-meta');

  if (previewEl && thumbnailEl && storeEl && metaEl) {
    thumbnailEl.src = reference.photo_url || '';
    storeEl.textContent = reference.store_name || 'Tienda';
    metaEl.textContent = `${reference.photo_type === 'BEFORE' ? 'Foto Antes' : 'Foto Después'}`;
    previewEl.style.display = 'block';
  }

  // Focus on chat input
  const input = document.getElementById('chat-input');
  if (input) input.focus();
}

/**
 * Remove the tagged reference from the composer
 */
function removeTaggedReference() {
  clearTaggedReference();
}

function clearTaggedReference() {
  chatState.taggedReference = null;
  const previewEl = document.getElementById('chat-reference-preview');
  if (previewEl) previewEl.style.display = 'none';
}

/**
 * Navigate to a tagged photo in visit detail
 */
function navigateToTaggedPhoto(visitId, gondolaGroupId, photoType) {
  // Show visit detail and scroll to the specific photo
  showVisitDetail(visitId, gondolaGroupId, photoType);
}

/**
 * Called from Visit Detail when user clicks "Comentar en chat" on an image
 */
function commentOnImage(visitId, storeId, storeName, photoId, photoType, gondolaGroupId, photoUrl, capturedAt) {
  const reference = {
    visit_id: visitId,
    store_id: storeId,
    store_name: storeName,
    photo_id: photoId,
    photo_type: photoType,
    gondola_group_id: gondolaGroupId,
    photo_url: photoUrl,
    captured_at: capturedAt,
  };

  setTaggedReference(reference);

  // Navigate back to Por Ruta page
  navigateTo('route-history');

  toast('Referencia agregada. Escribe tu mensaje.');
}

// ── Chat Initialization ───────────────────────────────────────────────────

/**
 * Initialize chat when loading route history page
 */
function initRouteChat() {
  // Find Norte route ID from notification state
  const norteRoute = notificationState.routes?.find(r => r.name === 'Norte');
  if (!norteRoute) {
    console.log('Norte route not found, cannot initialize chat');
    return;
  }

  chatState.routeId = norteRoute.id;

  // Load existing messages
  loadChatMessages(norteRoute.id);

  // Connect WebSocket
  initChatWebSocket(norteRoute.id);

  // Setup input handling
  setupChatInput();
}

/**
 * Setup chat input event handlers
 */
function setupChatInput() {
  const input = document.getElementById('chat-input');
  if (!input) return;

  // Send on Enter (but not Shift+Enter)
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage();
    }
  });

  // Auto-resize textarea
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 100) + 'px';
  });
}

/**
 * Utility: Get current user ID from auth
 */
function getUserId() {
  try {
    const auth = JSON.parse(localStorage.getItem('auth') || '{}');
    return auth.user_id;
  } catch {
    return null;
  }
}

/**
 * Utility: Escape HTML to prevent XSS
 */
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ══════════════════════════════════════════════════════════════════════════
// ═══ MERCHANDISER CHAT ════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════════════════

/**
 * Merchandiser chat state (separate from admin chat)
 */
let merchChatState = {
  ws: null,
  connected: false,
  routeId: null,
  messages: [],
  lastMessageId: null,
  taggedReference: null,
  reconnectAttempts: 0,
  maxReconnectAttempts: 5,
};

/**
 * Load merchandiser chat page
 */
async function loadMerchandiserChatPage() {
  if (getUserRole() === 'admin') return;

  // Find the merchandiser's assigned route
  try {
    const myRoute = await apiGet('/routes/my-route');

    if (!myRoute) {
      const container = document.getElementById('merch-chat-messages');
      if (container) {
        container.innerHTML = `
          <div class="chat-empty-state">
            <p>No tienes una ruta asignada</p>
            <p class="meta">Contacta a tu supervisor para ser asignado a una ruta</p>
          </div>
        `;
      }
      updateMerchChatWsStatus('', 'Sin ruta');
      return;
    }

    merchChatState.routeId = myRoute.id;

    // Update header
    const header = document.querySelector('.chat-page-header h2');
    if (header) header.textContent = `Chat - Ruta ${myRoute.name}`;

    // Load existing messages
    await loadMerchChatMessages(myRoute.id);

    // Connect WebSocket
    initMerchChatWebSocket(myRoute.id);

    // Setup input handlers
    setupMerchChatInput();

  } catch (e) {
    console.error('Error loading merchandiser chat:', e);
  }
}

/**
 * Initialize merchandiser chat WebSocket
 */
function initMerchChatWebSocket(routeId) {
  if (merchChatState.ws && merchChatState.connected && merchChatState.routeId === routeId) return;

  if (merchChatState.ws && merchChatState.routeId !== routeId) {
    closeMerchChatWebSocket();
  }

  merchChatState.routeId = routeId;

  const token = getToken();
  if (!token) return;

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  let wsUrl = `${protocol}//${host}/api/chat/ws/${routeId}?token=${token}`;

  if (merchChatState.lastMessageId) {
    wsUrl += `&last_message_id=${merchChatState.lastMessageId}`;
  }

  try {
    merchChatState.ws = new WebSocket(wsUrl);

    merchChatState.ws.onopen = () => {
      merchChatState.connected = true;
      merchChatState.reconnectAttempts = 0;
      updateMerchChatWsStatus('connected', 'Conectado');
    };

    merchChatState.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleMerchChatMessage(msg);
      } catch (e) {
        console.error('Error parsing merch chat message:', e);
      }
    };

    merchChatState.ws.onclose = (event) => {
      merchChatState.connected = false;
      updateMerchChatWsStatus('disconnected', 'Desconectado');

      // Auto-reconnect
      if (event.code !== 1000 && merchChatState.reconnectAttempts < merchChatState.maxReconnectAttempts) {
        const delay = Math.min(1000 * Math.pow(2, merchChatState.reconnectAttempts), 30000);
        merchChatState.reconnectAttempts++;
        setTimeout(() => {
          if (document.getElementById('page-chat')?.classList.contains('active')) {
            initMerchChatWebSocket(routeId);
          }
        }, delay);
      }
    };

    merchChatState.ws.onerror = () => {
      updateMerchChatWsStatus('error', 'Error');
    };

  } catch (e) {
    console.error('Failed to create merch chat WebSocket:', e);
  }
}

function closeMerchChatWebSocket() {
  if (merchChatState.ws) {
    merchChatState.ws.close(1000, 'User navigated away');
    merchChatState.ws = null;
  }
  merchChatState.connected = false;
}

function updateMerchChatWsStatus(status, text) {
  const statusEl = document.getElementById('merch-chat-ws-status');
  if (statusEl) {
    statusEl.textContent = text;
    statusEl.className = 'chat-ws-status ' + status;
  }
}

/**
 * Handle incoming merchandiser chat messages
 */
function handleMerchChatMessage(msg) {
  switch (msg.type) {
    case 'connected':
      console.log('Merch chat connected:', msg.data);
      break;

    case 'chat_message':
      handleIncomingMerchChatMessage(msg.data);
      break;

    case 'chat_sync':
      if (msg.data.messages && msg.data.messages.length > 0) {
        msg.data.messages.forEach(m => {
          if (!merchChatState.messages.find(existing => existing.id === m.id)) {
            merchChatState.messages.push(m);
          }
        });
        merchChatState.messages.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
        renderMerchChatMessages();
      }
      break;

    case 'pong':
      break;
  }
}

function handleIncomingMerchChatMessage(message) {
  merchChatState.messages.push(message);
  merchChatState.lastMessageId = message.id;
  renderNewMerchChatMessage(message);

  // Mark as read if from other user
  const currentUserId = getUserId();
  if (message.sender_user_id !== currentUserId) {
    markMerchChatMessagesRead([message.id]);
  }
}

/**
 * Load chat messages for merchandiser's route
 */
async function loadMerchChatMessages(routeId) {
  try {
    const messages = await apiGet(`/chat/routes/${routeId}/messages?limit=50`);
    merchChatState.messages = messages.reverse();
    if (messages.length > 0) {
      merchChatState.lastMessageId = Math.max(...messages.map(m => m.id));
    }
    renderMerchChatMessages();
  } catch (e) {
    console.error('Error loading merch chat messages:', e);
  }
}

/**
 * Render all merchandiser chat messages
 */
function renderMerchChatMessages() {
  const container = document.getElementById('merch-chat-messages');
  if (!container) return;

  const currentUserId = getUserId();

  if (merchChatState.messages.length === 0) {
    container.innerHTML = `
      <div class="chat-empty-state">
        <p>No hay mensajes aún</p>
        <p class="meta">Los mensajes del supervisor aparecerán aquí</p>
      </div>
    `;
    return;
  }

  let html = '';
  let lastDate = null;

  merchChatState.messages.forEach(msg => {
    const msgDate = new Date(msg.created_at).toLocaleDateString();
    if (msgDate !== lastDate) {
      html += `<div class="chat-date-separator"><span>${msgDate}</span></div>`;
      lastDate = msgDate;
    }
    html += renderMerchChatMessage(msg, currentUserId);
  });

  container.innerHTML = html;
  container.scrollTop = container.scrollHeight;
}

function renderMerchChatMessage(msg, currentUserId) {
  const isSent = msg.sender_user_id === currentUserId;
  const time = new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  let referenceHtml = '';
  if (msg.message_type === 'TAGGED_REFERENCE' && msg.ref_photo_url) {
    referenceHtml = `
      <div class="chat-message-reference" onclick="navigateToTaggedPhotoMerch(${msg.ref_visit_id}, '${msg.ref_gondola_group_id || ''}', '${msg.ref_photo_type || ''}')">
        <div class="reference-preview-row">
          <img class="reference-preview-thumbnail" src="${msg.ref_photo_url}" alt="Reference">
          <div class="reference-preview-info">
            <span class="reference-preview-store">${msg.ref_store_name || 'Tienda'}</span>
            <span class="reference-preview-meta">${msg.ref_photo_type || 'Photo'}</span>
            <span class="reference-preview-badge">${msg.ref_photo_type === 'BEFORE' ? 'Antes' : 'Después'}</span>
          </div>
        </div>
      </div>
    `;
  }

  // Handle annotated reference messages
  if (msg.message_type === 'ANNOTATED_REFERENCE') {
    const previewUrl = msg.ref_annotation_preview_url || msg.ref_photo_url;
    referenceHtml = `
      <div class="chat-message-annotation" onclick="navigateToTaggedPhotoMerch(${msg.ref_visit_id}, '${msg.ref_gondola_group_id || ''}', '${msg.ref_photo_type || ''}')">
        <div class="reference-preview-row">
          <img class="reference-preview-thumbnail" src="${previewUrl}" alt="Annotated" style="max-height:150px;object-fit:contain;">
          <div class="reference-preview-info">
            <span class="reference-preview-store">${msg.ref_store_name || 'Tienda'}</span>
            <span class="reference-preview-meta">Imagen Anotada</span>
            <span class="reference-preview-badge" style="background:#ef4444;">${msg.ref_photo_type === 'BEFORE' ? 'Antes' : 'Después'}</span>
          </div>
        </div>
      </div>
    `;
  }

  return `
    <div class="chat-message ${isSent ? 'sent' : 'received'}" data-message-id="${msg.id}">
      ${!isSent ? `<div class="chat-message-sender">${msg.sender_name || 'Supervisor'}</div>` : ''}
      <div class="chat-message-bubble">
        ${referenceHtml}
        ${escapeHtml(msg.text)}
      </div>
      <div class="chat-message-meta">${time}</div>
    </div>
  `;
}

function renderNewMerchChatMessage(msg) {
  const container = document.getElementById('merch-chat-messages');
  if (!container) return;

  const emptyState = container.querySelector('.chat-empty-state');
  if (emptyState) emptyState.remove();

  const currentUserId = getUserId();
  const html = renderMerchChatMessage(msg, currentUserId);

  const wrapper = document.createElement('div');
  wrapper.innerHTML = html;
  container.appendChild(wrapper.firstElementChild);
  container.scrollTop = container.scrollHeight;
}

/**
 * Send merchandiser chat message
 */
async function sendMerchChatMessage() {
  const input = document.getElementById('merch-chat-input');
  const text = input?.value?.trim();

  if (!text) return;
  if (!merchChatState.routeId) {
    toast('No hay ruta asignada');
    return;
  }

  const messageData = {
    route_id: merchChatState.routeId,
    text: text,
    message_type: merchChatState.taggedReference ? 'TAGGED_REFERENCE' : 'TEXT',
  };

  if (merchChatState.taggedReference) {
    messageData.reference = merchChatState.taggedReference;
  }

  if (merchChatState.ws && merchChatState.connected) {
    merchChatState.ws.send(JSON.stringify({
      type: 'send_message',
      data: messageData
    }));
    input.value = '';
    clearMerchTaggedReference();
  } else {
    try {
      const response = await apiPost(`/chat/routes/${merchChatState.routeId}/messages`, messageData);
      input.value = '';
      clearMerchTaggedReference();
      handleIncomingMerchChatMessage(response);
    } catch (e) {
      toast('Error al enviar mensaje');
    }
  }
}

function markMerchChatMessagesRead(messageIds) {
  if (!merchChatState.routeId || messageIds.length === 0) return;

  if (merchChatState.ws && merchChatState.connected) {
    merchChatState.ws.send(JSON.stringify({
      type: 'mark_read',
      data: { message_ids: messageIds }
    }));
  }
}

// ── Merchandiser Tagged Reference ─────────────────────────────────────────

function setMerchTaggedReference(reference) {
  merchChatState.taggedReference = reference;

  const previewEl = document.getElementById('merch-chat-reference-preview');
  const thumbnailEl = document.getElementById('merch-reference-thumbnail');
  const storeEl = document.getElementById('merch-reference-store');
  const metaEl = document.getElementById('merch-reference-meta');

  if (previewEl && thumbnailEl && storeEl && metaEl) {
    thumbnailEl.src = reference.photo_url || '';
    storeEl.textContent = reference.store_name || 'Tienda';
    metaEl.textContent = `${reference.photo_type === 'BEFORE' ? 'Foto Antes' : 'Foto Después'}`;
    previewEl.style.display = 'block';
  }

  const input = document.getElementById('merch-chat-input');
  if (input) input.focus();
}

function removeMerchTaggedReference() {
  clearMerchTaggedReference();
}

function clearMerchTaggedReference() {
  merchChatState.taggedReference = null;
  const previewEl = document.getElementById('merch-chat-reference-preview');
  if (previewEl) previewEl.style.display = 'none';
}

function navigateToTaggedPhotoMerch(visitId, gondolaGroupId, photoType) {
  // For merchandisers, we could show a simple photo modal or navigate to history
  toast('Ver foto en detalles de visita');
}

/**
 * Setup merchandiser chat input handlers
 */
function setupMerchChatInput() {
  const input = document.getElementById('merch-chat-input');
  if (!input) return;

  // Remove existing listeners by cloning
  const newInput = input.cloneNode(true);
  input.parentNode.replaceChild(newInput, input);

  newInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMerchChatMessage();
    }
  });

  newInput.addEventListener('input', () => {
    newInput.style.height = 'auto';
    newInput.style.height = Math.min(newInput.scrollHeight, 100) + 'px';
  });
}

// ══════════════════════════════════════════════════════════════════════════
// ═══ IMAGE ANNOTATION EDITOR ══════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════════════════

const annotationState = {
  // Context
  visitId: null,
  storeId: null,
  storeName: '',
  photoId: null,
  photoType: '',  // BEFORE | AFTER
  gondolaGroupId: null,
  originalPhotoUrl: '',
  capturedAt: null,
  routeId: null,

  // Canvas
  canvas: null,
  ctx: null,
  image: null,
  imageLoaded: false,

  // Drawing state
  isDrawing: false,
  currentTool: 'pen',
  currentColor: '#ff0000',
  currentStroke: 4,
  startX: 0,
  startY: 0,

  // History for undo/redo
  shapes: [],      // Committed shapes
  undoStack: [],   // For redo
  currentPath: [], // Current freehand path being drawn

  // Scale factor for canvas
  scale: 1,
  offsetX: 0,
  offsetY: 0,
};

/**
 * Open the annotation editor for a specific photo.
 */
function openAnnotationEditor(photoData) {
  // Store context
  annotationState.visitId = photoData.visitId;
  annotationState.storeId = photoData.storeId;
  annotationState.storeName = photoData.storeName || '';
  annotationState.photoId = photoData.photoId;
  annotationState.photoType = photoData.photoType;
  annotationState.gondolaGroupId = photoData.gondolaGroupId;
  annotationState.originalPhotoUrl = photoData.photoUrl;
  annotationState.capturedAt = photoData.capturedAt;
  annotationState.routeId = photoData.routeId;

  // Reset state
  annotationState.shapes = [];
  annotationState.undoStack = [];
  annotationState.currentPath = [];
  annotationState.isDrawing = false;
  annotationState.currentTool = 'pen';
  annotationState.currentColor = '#ff0000';
  annotationState.currentStroke = 4;

  // Update UI
  document.getElementById('annotation-photo-type').textContent = photoData.photoType;
  document.getElementById('annotation-store-name').textContent = photoData.storeName || '';

  // Reset tool buttons
  document.querySelectorAll('.tool-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelector('.tool-btn[data-tool="pen"]').classList.add('active');
  document.querySelectorAll('.color-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelector('.color-btn[data-color="#ff0000"]').classList.add('active');
  document.querySelectorAll('.stroke-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelector('.stroke-btn[data-stroke="4"]').classList.add('active');

  // Show modal
  document.getElementById('modal-annotation').style.display = 'flex';

  // Initialize canvas
  initAnnotationCanvas(photoData.photoUrl);
}

/**
 * Initialize the annotation canvas with the image.
 */
function initAnnotationCanvas(imageUrl) {
  const container = document.getElementById('annotation-canvas-container');
  const canvas = document.getElementById('annotation-canvas');
  const ctx = canvas.getContext('2d');

  annotationState.canvas = canvas;
  annotationState.ctx = ctx;
  annotationState.imageLoaded = false;

  // Load image
  const img = new Image();
  img.crossOrigin = 'anonymous';
  img.onload = () => {
    annotationState.image = img;
    annotationState.imageLoaded = true;

    // Calculate size to fit container
    const containerWidth = container.clientWidth;
    const containerHeight = container.clientHeight;

    let scale = Math.min(
      containerWidth / img.width,
      containerHeight / img.height,
      1 // Don't upscale
    );

    const displayWidth = img.width * scale;
    const displayHeight = img.height * scale;

    // Set canvas size to match image display size
    canvas.width = img.width;
    canvas.height = img.height;
    canvas.style.width = displayWidth + 'px';
    canvas.style.height = displayHeight + 'px';

    annotationState.scale = scale;

    // Draw initial image
    redrawAnnotationCanvas();

    // Setup event listeners
    setupAnnotationEvents();
  };

  img.onerror = () => {
    toast('Error cargando imagen');
    closeAnnotationEditor();
  };

  img.src = imageUrl;
}

/**
 * Set up touch and mouse events for drawing.
 */
function setupAnnotationEvents() {
  const canvas = annotationState.canvas;

  // Remove existing listeners
  canvas.onmousedown = null;
  canvas.onmousemove = null;
  canvas.onmouseup = null;
  canvas.ontouchstart = null;
  canvas.ontouchmove = null;
  canvas.ontouchend = null;

  // Mouse events
  canvas.onmousedown = handleAnnotationStart;
  canvas.onmousemove = handleAnnotationMove;
  canvas.onmouseup = handleAnnotationEnd;
  canvas.onmouseleave = handleAnnotationEnd;

  // Touch events
  canvas.ontouchstart = (e) => {
    e.preventDefault();
    const touch = e.touches[0];
    handleAnnotationStart(touch);
  };
  canvas.ontouchmove = (e) => {
    e.preventDefault();
    const touch = e.touches[0];
    handleAnnotationMove(touch);
  };
  canvas.ontouchend = (e) => {
    e.preventDefault();
    handleAnnotationEnd();
  };
}

/**
 * Get canvas coordinates from event.
 */
function getAnnotationCoords(e) {
  const canvas = annotationState.canvas;
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;

  const clientX = e.clientX !== undefined ? e.clientX : e.pageX;
  const clientY = e.clientY !== undefined ? e.clientY : e.pageY;

  return {
    x: (clientX - rect.left) * scaleX,
    y: (clientY - rect.top) * scaleY,
  };
}

/**
 * Handle drawing start.
 */
function handleAnnotationStart(e) {
  if (!annotationState.imageLoaded) return;

  const coords = getAnnotationCoords(e);
  annotationState.isDrawing = true;
  annotationState.startX = coords.x;
  annotationState.startY = coords.y;

  if (annotationState.currentTool === 'pen') {
    annotationState.currentPath = [{x: coords.x, y: coords.y}];
  }
}

/**
 * Handle drawing move.
 */
function handleAnnotationMove(e) {
  if (!annotationState.isDrawing || !annotationState.imageLoaded) return;

  const coords = getAnnotationCoords(e);

  if (annotationState.currentTool === 'pen') {
    // Add point to path
    annotationState.currentPath.push({x: coords.x, y: coords.y});
    // Redraw with current path
    redrawAnnotationCanvas();
    drawCurrentPath();
  } else {
    // Preview shape
    redrawAnnotationCanvas();
    drawShapePreview(coords.x, coords.y);
  }
}

/**
 * Handle drawing end.
 */
function handleAnnotationEnd() {
  if (!annotationState.isDrawing) return;

  annotationState.isDrawing = false;

  if (annotationState.currentTool === 'pen' && annotationState.currentPath.length > 1) {
    // Commit freehand path
    annotationState.shapes.push({
      type: 'pen',
      points: [...annotationState.currentPath],
      color: annotationState.currentColor,
      stroke: annotationState.currentStroke,
    });
    annotationState.currentPath = [];
    annotationState.undoStack = []; // Clear redo on new action
  } else if (annotationState.currentTool !== 'pen') {
    // Commit shape (using last mouse position - we need to get it somehow)
    // Actually, for shapes we commit on mouseup with the final position
    // The shape was drawn in preview, now we commit it
  }

  redrawAnnotationCanvas();
  updateUndoRedoButtons();
}

/**
 * Draw current freehand path (while drawing).
 */
function drawCurrentPath() {
  const ctx = annotationState.ctx;
  const path = annotationState.currentPath;

  if (path.length < 2) return;

  ctx.strokeStyle = annotationState.currentColor;
  ctx.lineWidth = annotationState.currentStroke;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  ctx.beginPath();
  ctx.moveTo(path[0].x, path[0].y);
  for (let i = 1; i < path.length; i++) {
    ctx.lineTo(path[i].x, path[i].y);
  }
  ctx.stroke();
}

/**
 * Draw shape preview while dragging.
 */
function drawShapePreview(endX, endY) {
  const ctx = annotationState.ctx;
  const startX = annotationState.startX;
  const startY = annotationState.startY;
  const tool = annotationState.currentTool;

  ctx.strokeStyle = annotationState.currentColor;
  ctx.lineWidth = annotationState.currentStroke;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  if (tool === 'circle') {
    const radiusX = Math.abs(endX - startX) / 2;
    const radiusY = Math.abs(endY - startY) / 2;
    const centerX = (startX + endX) / 2;
    const centerY = (startY + endY) / 2;

    ctx.beginPath();
    ctx.ellipse(centerX, centerY, radiusX, radiusY, 0, 0, Math.PI * 2);
    ctx.stroke();
  } else if (tool === 'rect') {
    ctx.strokeRect(startX, startY, endX - startX, endY - startY);
  } else if (tool === 'arrow') {
    drawArrow(ctx, startX, startY, endX, endY);
  }

  // We'll commit the shape here instead of in handleAnnotationEnd
  // Store end coordinates for commit
  annotationState.endX = endX;
  annotationState.endY = endY;
}

/**
 * Draw an arrow from (x1,y1) to (x2,y2).
 */
function drawArrow(ctx, x1, y1, x2, y2) {
  const headLen = 15;
  const angle = Math.atan2(y2 - y1, x2 - x1);

  // Line
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.stroke();

  // Arrowhead
  ctx.beginPath();
  ctx.moveTo(x2, y2);
  ctx.lineTo(
    x2 - headLen * Math.cos(angle - Math.PI / 6),
    y2 - headLen * Math.sin(angle - Math.PI / 6)
  );
  ctx.moveTo(x2, y2);
  ctx.lineTo(
    x2 - headLen * Math.cos(angle + Math.PI / 6),
    y2 - headLen * Math.sin(angle + Math.PI / 6)
  );
  ctx.stroke();
}

/**
 * Commit shape when mouse up (for non-pen tools).
 */
function handleAnnotationEnd() {
  if (!annotationState.isDrawing) return;
  annotationState.isDrawing = false;

  const tool = annotationState.currentTool;

  if (tool === 'pen' && annotationState.currentPath.length > 1) {
    annotationState.shapes.push({
      type: 'pen',
      points: [...annotationState.currentPath],
      color: annotationState.currentColor,
      stroke: annotationState.currentStroke,
    });
    annotationState.currentPath = [];
  } else if (tool !== 'pen' && annotationState.endX !== undefined) {
    const startX = annotationState.startX;
    const startY = annotationState.startY;
    const endX = annotationState.endX;
    const endY = annotationState.endY;

    // Only commit if there's actual movement
    if (Math.abs(endX - startX) > 5 || Math.abs(endY - startY) > 5) {
      annotationState.shapes.push({
        type: tool,
        startX, startY, endX, endY,
        color: annotationState.currentColor,
        stroke: annotationState.currentStroke,
      });
    }

    annotationState.endX = undefined;
    annotationState.endY = undefined;
  }

  annotationState.undoStack = []; // Clear redo on new action
  redrawAnnotationCanvas();
  updateUndoRedoButtons();
}

/**
 * Redraw the canvas with image and all shapes.
 */
function redrawAnnotationCanvas() {
  const ctx = annotationState.ctx;
  const canvas = annotationState.canvas;
  const img = annotationState.image;

  if (!img) return;

  // Clear and draw image
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, 0, 0);

  // Draw all committed shapes
  for (const shape of annotationState.shapes) {
    ctx.strokeStyle = shape.color;
    ctx.lineWidth = shape.stroke;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    if (shape.type === 'pen') {
      if (shape.points.length < 2) continue;
      ctx.beginPath();
      ctx.moveTo(shape.points[0].x, shape.points[0].y);
      for (let i = 1; i < shape.points.length; i++) {
        ctx.lineTo(shape.points[i].x, shape.points[i].y);
      }
      ctx.stroke();
    } else if (shape.type === 'circle') {
      const radiusX = Math.abs(shape.endX - shape.startX) / 2;
      const radiusY = Math.abs(shape.endY - shape.startY) / 2;
      const centerX = (shape.startX + shape.endX) / 2;
      const centerY = (shape.startY + shape.endY) / 2;
      ctx.beginPath();
      ctx.ellipse(centerX, centerY, radiusX, radiusY, 0, 0, Math.PI * 2);
      ctx.stroke();
    } else if (shape.type === 'rect') {
      ctx.strokeRect(shape.startX, shape.startY, shape.endX - shape.startX, shape.endY - shape.startY);
    } else if (shape.type === 'arrow') {
      drawArrow(ctx, shape.startX, shape.startY, shape.endX, shape.endY);
    }
  }
}

/**
 * Set the current drawing tool.
 */
function setAnnotationTool(tool) {
  annotationState.currentTool = tool;
  document.querySelectorAll('.tool-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelector(`.tool-btn[data-tool="${tool}"]`).classList.add('active');
}

/**
 * Set the current drawing color.
 */
function setAnnotationColor(color) {
  annotationState.currentColor = color;
  document.querySelectorAll('.color-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelector(`.color-btn[data-color="${color}"]`).classList.add('active');
}

/**
 * Set the current stroke width.
 */
function setAnnotationStroke(width) {
  annotationState.currentStroke = width;
  document.querySelectorAll('.stroke-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelector(`.stroke-btn[data-stroke="${width}"]`).classList.add('active');
}

/**
 * Undo the last drawing action.
 */
function annotationUndo() {
  if (annotationState.shapes.length === 0) return;

  const shape = annotationState.shapes.pop();
  annotationState.undoStack.push(shape);
  redrawAnnotationCanvas();
  updateUndoRedoButtons();
}

/**
 * Redo the last undone action.
 */
function annotationRedo() {
  if (annotationState.undoStack.length === 0) return;

  const shape = annotationState.undoStack.pop();
  annotationState.shapes.push(shape);
  redrawAnnotationCanvas();
  updateUndoRedoButtons();
}

/**
 * Clear all annotations.
 */
function annotationClear() {
  if (annotationState.shapes.length === 0) return;

  if (confirm('¿Borrar todas las anotaciones?')) {
    annotationState.undoStack.push(...annotationState.shapes);
    annotationState.shapes = [];
    redrawAnnotationCanvas();
    updateUndoRedoButtons();
  }
}

/**
 * Update undo/redo button states.
 */
function updateUndoRedoButtons() {
  const undoBtn = document.getElementById('btn-annotation-undo');
  const redoBtn = document.getElementById('btn-annotation-redo');

  undoBtn.disabled = annotationState.shapes.length === 0;
  redoBtn.disabled = annotationState.undoStack.length === 0;
}

/**
 * Close the annotation editor.
 */
function closeAnnotationEditor() {
  document.getElementById('modal-annotation').style.display = 'none';
  annotationState.canvas = null;
  annotationState.ctx = null;
  annotationState.image = null;
}

/**
 * Show the share dialog with preview.
 */
function showAnnotationShareDialog() {
  if (annotationState.shapes.length === 0) {
    toast('Agregue anotaciones antes de compartir');
    return;
  }

  // Generate preview image
  const previewDataUrl = annotationState.canvas.toDataURL('image/png');
  document.getElementById('annotation-share-preview-img').src = previewDataUrl;
  document.getElementById('annotation-share-badge').textContent = annotationState.photoType;
  document.getElementById('annotation-share-message').value = '';

  document.getElementById('modal-annotation-share').style.display = 'flex';
}

/**
 * Send the annotated image to chat.
 */
async function sendAnnotationToChat() {
  const message = document.getElementById('annotation-share-message').value.trim();

  if (!message) {
    toast('Por favor escriba un mensaje');
    return;
  }

  try {
    // 1. Save annotation to backend
    const annotationData = JSON.stringify(annotationState.shapes);
    const annotation = await apiPost('/annotations/', {
      photo_id: annotationState.photoId,
      visit_id: annotationState.visitId,
      photo_type: annotationState.photoType,
      gondola_group_id: annotationState.gondolaGroupId,
      annotation_data: annotationData,
    });

    // 2. Save preview image
    const previewDataUrl = annotationState.canvas.toDataURL('image/png');
    await apiPost(`/annotations/${annotation.id}/preview`, {
      image_data: previewDataUrl,
    });

    // Get updated annotation with preview path
    const updatedAnnotation = await apiGet(`/annotations/${annotation.id}`);

    // 3. Send chat message with annotation reference
    const routeId = annotationState.routeId;
    if (!routeId) {
      toast('No se puede determinar la ruta para el chat');
      return;
    }

    const chatMessage = {
      route_id: routeId,
      text: message,
      message_type: 'ANNOTATED_REFERENCE',
      annotated_reference: {
        annotation_id: annotation.id,
        visit_id: annotationState.visitId,
        store_id: annotationState.storeId,
        store_name: annotationState.storeName,
        photo_id: annotationState.photoId,
        photo_type: annotationState.photoType,
        gondola_group_id: annotationState.gondolaGroupId,
        original_photo_url: annotationState.originalPhotoUrl,
        annotation_preview_url: updatedAnnotation.preview_path,
        captured_at: annotationState.capturedAt,
      },
    };

    await apiPost(`/chat/routes/${routeId}/messages`, chatMessage);

    toast('Anotación enviada al chat');
    closeModal('modal-annotation-share');
    closeAnnotationEditor();

  } catch (err) {
    console.error('Error sending annotation:', err);
    toast('Error al enviar anotación: ' + err.message);
  }
}
