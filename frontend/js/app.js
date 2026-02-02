/**
 * Ito Merchandising App — Main application controller.
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
    btn.textContent = 'Sign In';
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

  // Show/hide admin tabs
  const role = getUserRole();
  document.querySelectorAll('[data-admin-only]').forEach(el => {
    el.style.display = role === 'admin' ? '' : 'none';
  });

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

  // Load page data
  switch (page) {
    case 'visit': loadVisitPage(); break;
    case 'history': loadHistoryPage(); break;
    case 'dashboard': loadDashboardPage(); break;
    case 'manage': loadManagePage(); break;
  }
}

// ── Store Visit Page ────────────────────────────────────────────────────
let visitState = { storeId: null, skuActions: {}, photos: [] };

async function loadVisitPage() {
  try {
    const stores = await apiGet('/stores/');
    const sel = document.getElementById('visit-store-select');
    sel.innerHTML = '<option value="">Select a store...</option>' +
      stores.map(s => `<option value="${s.id}">${s.name} (${s.region})</option>`).join('');
  } catch (err) {
    toast('Failed to load stores');
  }
  visitState = { storeId: null, skuActions: {}, photos: [] };
  document.getElementById('visit-sku-section').style.display = 'none';
  document.getElementById('visit-photo-section').style.display = 'none';
  document.getElementById('visit-submit-section').style.display = 'none';
  document.getElementById('photo-preview-list').innerHTML = '';
}

async function onStoreSelected() {
  const storeId = document.getElementById('visit-store-select').value;
  if (!storeId) return;
  visitState.storeId = parseInt(storeId);
  visitState.skuActions = {};

  try {
    // Load approved SKUs for this store
    const approvals = await apiGet(`/approvals/?store_id=${storeId}`);
    const skuList = document.getElementById('visit-sku-list');
    if (approvals.length === 0) {
      skuList.innerHTML = '<p class="meta">No approved SKUs for this store this quarter.</p>';
    } else {
      skuList.innerHTML = approvals.map(a => `
        <li class="sku-item" data-sku-id="${a.sku.id}">
          <span class="sku-name">${a.sku.name} <span class="meta">(${a.sku.brand})</span></span>
          <div class="action-chips">
            <span class="chip chip-refill" onclick="toggleAction(${a.sku.id},'needs_refill',this)">Needs Refill</span>
            <span class="chip chip-placed" onclick="toggleAction(${a.sku.id},'placed_on_shelf',this)">Placed</span>
            <span class="chip chip-order" onclick="toggleAction(${a.sku.id},'needs_order',this)">Order</span>
          </div>
        </li>
      `).join('');
    }
    document.getElementById('visit-sku-section').style.display = 'block';
    document.getElementById('visit-photo-section').style.display = 'block';
    document.getElementById('visit-submit-section').style.display = 'block';
  } catch (err) {
    toast('Failed to load SKUs');
  }
}

function toggleAction(skuId, action, el) {
  const key = `${skuId}`;
  if (!visitState.skuActions[key]) visitState.skuActions[key] = {};

  if (visitState.skuActions[key].action_type === action) {
    delete visitState.skuActions[key];
    el.classList.remove('selected');
  } else {
    // Deselect siblings
    el.parentElement.querySelectorAll('.chip').forEach(c => c.classList.remove('selected'));
    visitState.skuActions[key] = { sku_id: skuId, action_type: action };
    el.classList.add('selected');
  }
}

function onPhotosSelected(input) {
  const files = Array.from(input.files);
  visitState.photos = files.slice(0, 3); // Max 3 photos
  const preview = document.getElementById('photo-preview-list');
  preview.innerHTML = '';
  visitState.photos.forEach(file => {
    const img = document.createElement('img');
    img.src = URL.createObjectURL(file);
    preview.appendChild(img);
  });
}

async function submitVisit() {
  if (!visitState.storeId) { toast('Please select a store'); return; }

  const actions = Object.values(visitState.skuActions).filter(a => a.action_type);
  const btn = document.getElementById('btn-submit-visit');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Submitting...';

  try {
    // Get geolocation if available
    let lat = null, lng = null;
    try {
      const pos = await new Promise((resolve, reject) =>
        navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 })
      );
      lat = pos.coords.latitude;
      lng = pos.coords.longitude;
    } catch { /* geolocation unavailable — continue */ }

    const notes = document.getElementById('visit-notes').value || null;

    // Create the visit
    const visit = await apiPost('/visits/', {
      store_id: visitState.storeId,
      latitude: lat,
      longitude: lng,
      notes,
      sku_actions: actions,
    });

    // Upload photos
    for (const file of visitState.photos) {
      await apiUpload(`/visits/${visit.id}/photos`, file);
    }

    toast('Visit submitted successfully!');
    loadVisitPage();
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Submit Visit';
  }
}

// ── History Page ────────────────────────────────────────────────────────
async function loadHistoryPage() {
  const container = document.getElementById('history-list');
  container.innerHTML = '<p>Loading...</p>';
  try {
    const visits = await apiGet('/visits/?limit=30');
    if (visits.length === 0) {
      container.innerHTML = '<p class="meta">No visits yet.</p>';
      return;
    }
    container.innerHTML = visits.map(v => {
      const date = new Date(v.visited_at).toLocaleString();
      const storeName = v.store ? v.store.name : `Store #${v.store_id}`;
      const actionSummary = v.sku_actions.map(a => {
        const label = a.action_type.replace('_', ' ');
        const skuName = a.sku ? a.sku.name : `SKU #${a.sku_id}`;
        return `<span class="badge badge-${a.action_type === 'needs_refill' ? 'red' : a.action_type === 'needs_order' ? 'yellow' : 'green'}">${label}: ${skuName}</span>`;
      }).join(' ');
      const photoBadge = v.photos.length > 0 ? `<span class="meta">${v.photos.length} photo(s)</span>` : '';

      return `
        <div class="card" onclick="showVisitDetail(${v.id})">
          <h3>${storeName}</h3>
          <div class="meta">${date} ${photoBadge}</div>
          <div style="margin-top:6px">${actionSummary || '<span class="meta">No actions recorded</span>'}</div>
        </div>
      `;
    }).join('');
  } catch (err) {
    container.innerHTML = '<p>Failed to load visits.</p>';
  }
}

async function showVisitDetail(visitId) {
  try {
    const v = await apiGet(`/visits/${visitId}`);
    const date = new Date(v.visited_at).toLocaleString();
    const storeName = v.store ? v.store.name : `Store #${v.store_id}`;
    const userName = v.user ? v.user.full_name : `User #${v.user_id}`;

    let photosHtml = '';
    for (const photo of v.photos) {
      let cvHtml = '';
      if (photo.cv_processed && photo.cv_results) {
        const cv = JSON.parse(photo.cv_results);
        cvHtml = `
          <div style="margin-top:8px;">
            <strong>Void Score: ${(cv.void_space_score * 100).toFixed(1)}%</strong>
            — ${cv.void_regions.length} void region(s), ${cv.detected_products.length} product(s) detected
          </div>`;
      }
      photosHtml += `
        <div style="margin-top:12px;">
          <div class="cv-result-container">
            <img src="${photo.file_path}" style="max-width:100%;border-radius:8px;">
          </div>
          ${cvHtml}
        </div>`;
    }

    const actionsHtml = v.sku_actions.map(a => {
      const label = a.action_type.replace(/_/g, ' ');
      const skuName = a.sku ? a.sku.name : `SKU #${a.sku_id}`;
      const badgeClass = a.action_type === 'needs_refill' ? 'red' : a.action_type === 'needs_order' ? 'yellow' : 'green';
      return `<div><span class="badge badge-${badgeClass}">${label}</span> ${skuName} ${a.notes ? `— ${a.notes}` : ''}</div>`;
    }).join('');

    document.getElementById('history-list').innerHTML = `
      <div class="card">
        <button class="btn btn-outline btn-sm" onclick="loadHistoryPage()" style="margin-bottom:12px;">&larr; Back</button>
        <h3>${storeName}</h3>
        <div class="meta">${date} &middot; ${userName}</div>
        ${v.latitude ? `<div class="meta">Location: ${v.latitude.toFixed(5)}, ${v.longitude.toFixed(5)}</div>` : ''}
        ${v.notes ? `<div style="margin-top:8px;">${v.notes}</div>` : ''}
        <div style="margin-top:12px;"><strong>Actions:</strong></div>
        ${actionsHtml || '<div class="meta">No actions</div>'}
        ${photosHtml}
      </div>
    `;
  } catch (err) {
    toast('Failed to load visit details');
  }
}

// ── Dashboard Page ──────────────────────────────────────────────────────
async function loadDashboardPage() {
  const container = document.getElementById('dashboard-content');
  container.innerHTML = '<p>Loading dashboard...</p>';

  try {
    // Load filters data
    const regions = await apiGet('/dashboard/regions');
    const regionFilter = document.getElementById('filter-region');
    regionFilter.innerHTML = '<option value="">All Regions</option>' +
      regions.map(r => `<option value="${r}">${r}</option>`).join('');

    await refreshDashboard();
  } catch (err) {
    container.innerHTML = '<p>Failed to load dashboard.</p>';
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

    // Summary stats
    document.getElementById('stat-visits').textContent = summary.total_visits;
    document.getElementById('stat-coverage').textContent = `${(summary.coverage_rate * 100).toFixed(0)}%`;
    document.getElementById('stat-refills').textContent = summary.actions.needs_refill;
    document.getElementById('stat-orders').textContent = summary.actions.needs_order;
    document.getElementById('stat-placed').textContent = summary.actions.placed_on_shelf;
    document.getElementById('stat-photos').textContent = summary.cv_processed_photos;
    document.getElementById('stat-incidents-red').textContent = incidents.red_incidents;
    document.getElementById('stat-total-incidents').textContent = incidents.total_incidents;

    // By-store table
    const tableBody = document.getElementById('store-table-body');
    tableBody.innerHTML = byStore.map(s => `
      <tr>
        <td>${s.store_name}</td>
        <td>${s.region}</td>
        <td>${s.visit_count}</td>
        <td>${s.needs_refill}</td>
        <td>${s.placed_on_shelf}</td>
        <td>${s.needs_order}</td>
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
    toast('Failed to refresh dashboard');
  }
}

// ── Admin Manage Page ───────────────────────────────────────────────────
async function loadManagePage() {
  // Placeholder — load stores and SKUs for management
  try {
    const [stores, skus] = await Promise.all([
      apiGet('/stores/'),
      apiGet('/skus/'),
    ]);

    document.getElementById('manage-stores-list').innerHTML = stores.map(s =>
      `<div class="card"><h3>${s.name}</h3><div class="meta">${s.region} — ${s.address || 'No address'}</div></div>`
    ).join('');

    document.getElementById('manage-skus-list').innerHTML = skus.map(s =>
      `<div class="card"><h3>${s.name}</h3><div class="meta">${s.brand} — ${s.category || 'No category'} ${s.barcode ? '| ' + s.barcode : ''}</div></div>`
    ).join('');
  } catch (err) {
    toast('Failed to load management data');
  }
}
