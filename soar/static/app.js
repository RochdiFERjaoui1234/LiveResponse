// Live Response — Client-Side Application Logic

let playbooks = [];
let selectedPlaybook = null;
let currentFilter = 'all';

document.addEventListener('DOMContentLoaded', () => {
  initApp();
  setupEventListeners();
  // Polling loop for live incident telemetry
  setInterval(refreshTelemetry, 5000);
  refreshTunnelStatus();
});

async function initApp() {
  await Promise.all([
    fetchStats(),
    fetchPlaybooks(),
    fetchApprovals(),
    fetchExecutions(),
    fetchAuditLogs(),
  ]);
}

function setupEventListeners() {
  // Refresh button
  document.getElementById('btn-refresh').addEventListener('click', () => {
    refreshTelemetry();
  });

  // Dry-run mode toggle
  const dryRunCheckbox = document.getElementById('dry-run-checkbox');
  dryRunCheckbox.addEventListener('change', async (e) => {
    const isDryRun = e.target.checked;
    try {
      const res = await fetch('/api/config/dry_run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: isDryRun }),
      });
      const data = await res.json();
      updateDryRunUI(data.dry_run);
    } catch (err) {
      console.error('Failed to toggle dry-run mode', err);
    }
  });

  // Scenario Filter Buttons
  document.querySelectorAll('.btn-filter').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      document.querySelectorAll('.btn-filter').forEach((b) => b.classList.remove('active'));
      e.target.classList.add('active');
      currentFilter = e.target.dataset.filter;
      renderPlaybooksGrid();
    });
  });

  // Modal Close buttons
  document.getElementById('btn-close-modal').addEventListener('click', closeModal);
  document.getElementById('btn-cancel-modal').addEventListener('click', closeModal);
  document.getElementById('btn-close-details').addEventListener('click', closeDetailsModal);

  // Playbook Studio controls
  document.getElementById('btn-open-studio').addEventListener('click', openStudioModal);
  document.getElementById('btn-close-studio').addEventListener('click', closeStudioModal);
  document.getElementById('btn-cancel-studio').addEventListener('click', closeStudioModal);

  document.getElementById('studio-template-select').addEventListener('change', (e) => {
    loadStudioTemplate(e.target.value);
  });

  document.getElementById('studio-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('btn-deploy-custom-playbook');
    btn.disabled = true;
    btn.innerText = 'Compiling & Validating...';

    const filename = document.getElementById('studio-filename').value.trim();
    const code = document.getElementById('studio-code-editor').value;

    try {
      const res = await fetch('/api/custom-playbooks/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename, code }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Compilation failed');
      }

      alert(`Custom playbook '${data.playbook.name}' was compiled and deployed successfully.`);
      closeStudioModal();
      await fetchPlaybooks();
      await refreshTelemetry();
    } catch (err) {
      alert(`Validation / Compilation Error:\n${err.message}`);
    } finally {
      btn.disabled = false;
      btn.innerText = 'Compile & Deploy';
    }
  });

  // Encrypted tunnel controls (Cloudflare WARP)
  document.getElementById('btn-tunnel-up').addEventListener('click', () => tunnelOperation('up'));
  document.getElementById('btn-tunnel-down').addEventListener('click', () => tunnelOperation('down'));

  // Settings (bring-your-own-keys) controls
  document.getElementById('btn-open-settings').addEventListener('click', openSettingsModal);
  document.getElementById('btn-close-settings').addEventListener('click', closeSettingsModal);
  document.getElementById('btn-cancel-settings').addEventListener('click', closeSettingsModal);

  document.getElementById('settings-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('btn-save-settings');
    btn.disabled = true;
    btn.innerText = 'Saving...';

    const values = {};
    const mapping = {
      'settings-cf-token': 'cloudflare_api_token',
      'settings-cf-zone': 'cloudflare_zone_id',
      'settings-vt': 'vt_api_key',
      'settings-abuseipdb': 'abuseipdb_key',
      'settings-slack': 'slack_webhook',
    };
    for (const [elId, key] of Object.entries(mapping)) {
      const v = document.getElementById(elId).value.trim();
      if (v) {
        values[key] = v;
        document.getElementById(elId).value = '';
      }
    }

    try {
      const res = await fetch('/api/secrets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ values }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to save keys');
      }
      alert('Integration keys saved. New values are used on enrichment and notification actions.');
      closeSettingsModal();
      await refreshTelemetry();
    } catch (err) {
      alert('Failed to save keys: ' + err.message);
    } finally {
      btn.disabled = false;
      btn.innerText = 'Save Keys';
    }
  });

  // Trigger Form Submission
  document.getElementById('trigger-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!selectedPlaybook) return;

    const btn = document.getElementById('btn-run-scenario');
    btn.disabled = true;
    btn.innerText = 'Executing Actions...';

    const payload = {
      src_ip: document.getElementById('trigger-src-ip').value.trim(),
      target_host: document.getElementById('trigger-target-host').value.trim(),
      target_user: document.getElementById('trigger-target-user').value.trim(),
      file_path: document.getElementById('trigger-file-path').value.trim(),
      custom_params: {
        target_contract: document.getElementById('trigger-target-contract').value.trim(),
      },
    };

    try {
      const res = await fetch(`/api/playbooks/${encodeURIComponent(selectedPlaybook.name)}/trigger`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      closeModal();
      await refreshTelemetry();

      if (data.execution) {
        showExecutionDetails(data.execution);
      }
    } catch (err) {
      alert('Error triggering scenario: ' + err.message);
    } finally {
      btn.disabled = false;
      btn.innerText = 'Execute Response';
    }
  });
}

// Tunnel management
async function refreshTunnelStatus() {
  const dot = document.getElementById('tunnel-status-dot');
  const label = document.getElementById('tunnel-status-text');
  try {
    const res = await fetch('/api/tunnel/status');
    if (!res.ok) throw new Error('status unavailable');
    const data = await res.json();
    const connected = data.connected;
    label.innerText = 'TUNNEL: ' + (connected ? 'SECURED' : 'CLOSED');
    dot.style.background = connected ? 'var(--success)' : 'var(--text-dim)';
    dot.style.boxShadow = connected ? '0 0 6px var(--success)' : 'none';
  } catch (err) {
    label.innerText = 'TUNNEL: N/A';
    dot.style.background = 'var(--text-dim)';
    dot.style.boxShadow = 'none';
  }
}

async function tunnelOperation(op) {
  const label = document.getElementById('tunnel-status-text');
  label.innerText = 'TUNNEL: WORKING...';
  try {
    const res = await fetch(`/api/tunnel/${op}`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok || !data.success) {
      alert(data.error ? `Tunnel operation failed: ${data.error}` : `Tunnel ${op} failed (${res.status}).`);
    }
  } catch (err) {
    alert('Tunnel operation failed: ' + err.message);
  } finally {
    await refreshTunnelStatus();
  }
}

// Settings modal (integration keys)
async function openSettingsModal() {
  try {
    const res = await fetch('/api/secrets');
    if (res.ok) {
      const secrets = await res.json();
      const cells = {
        cloudflare_api_token: 'current-cf-token',
        cloudflare_zone_id: 'current-cf-zone',
        vt_api_key: 'current-vt',
        abuseipdb_key: 'current-abuseipdb',
        slack_webhook: 'current-slack',
      };
      for (const [key, cellId] of Object.entries(cells)) {
        const v = secrets[key];
        document.getElementById(cellId).innerText = v ? `masked (${v})` : 'not configured';
      }
    }
  } catch (err) {
    console.error('Failed to load secret status', err);
  }
  document.getElementById('settings-modal').style.display = 'flex';
}

function closeSettingsModal() {
  document.getElementById('settings-modal').style.display = 'none';
}

async function refreshTelemetry() {
  await Promise.all([
    fetchStats(),
    fetchApprovals(),
    fetchExecutions(),
    fetchAuditLogs(),
  ]);
}

async function fetchStats() {
  try {
    const res = await fetch('/api/stats');
    if (!res.ok) return;
    const stats = await res.json();

    document.getElementById('stat-playbooks').innerText = stats.playbooks_count || 0;
    document.getElementById('stat-total-executions').innerText = stats.total_executions || 0;
    document.getElementById('stat-success-executions').innerText = stats.successful_executions || 0;
    document.getElementById('stat-pending-approvals').innerText = stats.pending_approvals || 0;

    const card = document.getElementById('card-pending-approvals');
    if (stats.pending_approvals > 0) {
      card.classList.add('highlight-metric');
    } else {
      card.classList.remove('highlight-metric');
    }

    updateDryRunUI(stats.dry_run);

    const statusText = document.getElementById('system-status-text');
    statusText.innerText = stats.dry_run ? 'ARMED (DRY-RUN)' : 'ARMED (LIVE RESPONDER)';
  } catch (err) {
    console.error('Error fetching stats:', err);
  }
}

function updateDryRunUI(isDryRun) {
  const checkbox = document.getElementById('dry-run-checkbox');
  const label = document.getElementById('dry-run-label');
  const modalIndicator = document.getElementById('modal-mode-indicator');

  checkbox.checked = isDryRun;
  if (isDryRun) {
    label.innerText = 'Dry-Run (Safe Simulation)';
    label.style.color = 'var(--warning)';
    modalIndicator.innerText = 'Simulated (Dry-Run Mode)';
    modalIndicator.className = 'badge badge-warning';
  } else {
    label.innerText = 'LIVE Execution (Armed)';
    label.style.color = 'var(--danger)';
    modalIndicator.innerText = 'LIVE PRODUCTION EXECUTION';
    modalIndicator.className = 'badge badge-critical';
  }
}

async function fetchPlaybooks() {
  try {
    const res = await fetch('/api/playbooks');
    if (!res.ok) return;
    playbooks = await res.json();
    renderPlaybooksGrid();
  } catch (err) {
    console.error('Error fetching playbooks:', err);
  }
}

function renderPlaybooksGrid() {
  const container = document.getElementById('scenarios-grid');
  container.innerHTML = '';

  const filtered = currentFilter === 'all'
    ? playbooks
    : playbooks.filter((p) => p.category === currentFilter);

  if (filtered.length === 0) {
    container.innerHTML = '<p class="text-muted">No scenario plugins match this category.</p>';
    return;
  }

  filtered.forEach((pb) => {
    const card = document.createElement('div');
    card.className = 'scenario-card';

    const severityClass = pb.severity === 'critical' ? 'badge-critical' : (pb.severity === 'high' ? 'badge-high' : 'badge-medium');

    const actionsHtml = pb.actions
      .map(
        (a) => `<li>
          <span class="action-badge ${a.type}">${a.type.toUpperCase()}</span>
          <span>${escapeHtml(a.name)}</span>
          ${a.requires_approval ? '<span class="badge badge-warning" style="font-size:0.65rem;">APPROVAL</span>' : ''}
        </li>`
      )
      .join('');

    card.innerHTML = `
      <div class="scenario-card-header">
        <span class="scenario-category">${escapeHtml(pb.category || 'General')}</span>
        <span class="badge ${severityClass}">${escapeHtml(pb.severity)}</span>
      </div>
      <h3 class="scenario-title">${escapeHtml(pb.name.replace(/_/g, ' ').toUpperCase())}</h3>
      <p class="scenario-description">${escapeHtml(pb.description)}</p>
      
      <div class="scenario-actions-preview">
        <div class="preview-title">Automated Action Sequence (${pb.actions.length} steps)</div>
        <ul class="actions-list">
          ${actionsHtml}
        </ul>
      </div>

      <div class="scenario-card-footer">
        <button class="btn btn-primary btn-sm btn-block btn-trigger-scenario" style="width: 100%;">
          Execute Scenario
        </button>
      </div>
    `;

    card.querySelector('.btn-trigger-scenario').addEventListener('click', () => {
      openTriggerModal(pb);
    });

    container.appendChild(card);
  });
}

function openTriggerModal(pb) {
  selectedPlaybook = pb;
  const modal = document.getElementById('trigger-modal');
  document.getElementById('modal-title').innerText = `Trigger Response: ${pb.name.replace(/_/g, ' ')}`;
  document.getElementById('modal-desc').innerText = pb.description;

  // Toggle specific field visibility
  const filePathGroup = document.getElementById('group-file-path');
  const userGroup = document.getElementById('group-target-user');
  const contractGroup = document.getElementById('group-target-contract');

  if (pb.name.includes('php') || pb.name.includes('webshell') || pb.name.includes('file')) {
    filePathGroup.style.display = 'block';
  } else {
    filePathGroup.style.display = 'none';
  }

  if (pb.name.includes('user') || pb.name.includes('privilege') || pb.name.includes('account')) {
    userGroup.style.display = 'block';
  } else {
    userGroup.style.display = 'none';
  }

  if (pb.category === 'On-Chain & Web3 Security' || pb.name.includes('onchain') || pb.name.includes('contract')) {
    contractGroup.style.display = 'block';
  } else {
    contractGroup.style.display = 'none';
  }

  modal.style.display = 'flex';
}

function closeModal() {
  document.getElementById('trigger-modal').style.display = 'none';
  selectedPlaybook = null;
}

let cachedTemplates = null;

async function openStudioModal() {
  const modal = document.getElementById('studio-modal');
  if (!cachedTemplates) {
    try {
      const res = await fetch('/api/sdk/templates');
      if (res.ok) {
        cachedTemplates = await res.json();
      }
    } catch (e) {
      console.error('Failed to load SDK templates', e);
    }
  }

  const select = document.getElementById('studio-template-select');
  loadStudioTemplate(select.value);
  modal.style.display = 'flex';
}

function loadStudioTemplate(key) {
  if (!cachedTemplates || !cachedTemplates[key]) return;
  const tmpl = cachedTemplates[key];
  document.getElementById('studio-filename').value = tmpl.filename || 'custom_playbook.py';
  document.getElementById('studio-code-editor').value = tmpl.code || '';
}

function closeStudioModal() {
  document.getElementById('studio-modal').style.display = 'none';
}

async function fetchApprovals() {
  try {
    const res = await fetch('/api/approvals/pending');
    if (!res.ok) return;
    const approvals = await res.json();

    const container = document.getElementById('pending-approvals-container');
    const list = document.getElementById('approval-cards-list');

    if (approvals.length === 0) {
      container.style.display = 'none';
      list.innerHTML = '';
      return;
    }

    container.style.display = 'block';
    list.innerHTML = '';

    approvals.forEach((appr) => {
      const card = document.createElement('div');
      card.className = 'approval-card';
      const timeAgo = Math.round(Date.now() / 1000 - appr.created_at);

      card.innerHTML = `
        <div class="approval-info">
          <h4>Playbook: <code>${escapeHtml(appr.playbook)}</code></h4>
          <div class="approval-meta">
            Sensitive Action: <strong>${escapeHtml(appr.action_name)}</strong> • 
            Alert ID: <code>${escapeHtml(appr.alert_id.slice(0, 8))}</code> • 
            Requested: ${timeAgo}s ago
          </div>
        </div>
        <div class="approval-actions">
          <button class="btn btn-success btn-sm btn-approve" data-id="${appr.id}">
            Approve Action
          </button>
          <button class="btn btn-danger btn-sm btn-reject" data-id="${appr.id}">
            Reject Action
          </button>
        </div>
      `;

      card.querySelector('.btn-approve').addEventListener('click', async () => {
        await resolveApproval(appr.id, 'approve');
      });

      card.querySelector('.btn-reject').addEventListener('click', async () => {
        await resolveApproval(appr.id, 'reject');
      });

      list.appendChild(card);
    });
  } catch (err) {
    console.error('Error fetching approvals:', err);
  }
}

async function resolveApproval(id, decision) {
  try {
    const endpoint = decision === 'approve' ? `/api/approvals/${id}/approve` : `/api/approvals/${id}/reject`;
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ resolved_by: 'soc_analyst_dashboard' }),
    });
    if (res.ok) {
      await refreshTelemetry();
    }
  } catch (err) {
    alert('Failed to resolve approval: ' + err.message);
  }
}

async function fetchExecutions() {
  try {
    const res = await fetch('/api/executions?limit=15');
    if (!res.ok) return;
    const execs = await res.json();

    const tbody = document.getElementById('executions-tbody');
    if (execs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No incident responses executed yet. Click a scenario to test!</td></tr>';
      return;
    }

    tbody.innerHTML = '';
    execs.forEach((ex) => {
      const tr = document.createElement('tr');
      const statusBadge = getStatusBadge(ex.status);
      const actionCount = ex.actions ? ex.actions.length : 0;
      const dateStr = new Date(ex.started_at * 1000).toLocaleTimeString();

      tr.innerHTML = `
        <td>${statusBadge}</td>
        <td><strong>${escapeHtml(ex.playbook)}</strong></td>
        <td><code>${escapeHtml(ex.alert_id.slice(0, 8))}...</code></td>
        <td>${dateStr}</td>
        <td><span class="badge badge-mono">${actionCount} actions</span></td>
        <td><button class="btn btn-secondary btn-sm btn-view-details">Inspect</button></td>
      `;

      tr.querySelector('.btn-view-details').addEventListener('click', () => {
        showExecutionDetails(ex);
      });

      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Error fetching executions:', err);
  }
}

function getStatusBadge(status) {
  switch (status) {
    case 'success':
      return '<span class="badge badge-success">SUCCESS</span>';
    case 'simulated':
      return '<span class="badge badge-simulated">SIMULATED</span>';
    case 'failed':
      return '<span class="badge badge-critical">FAILED</span>';
    case 'awaiting_approval':
      return '<span class="badge badge-warning">AWAITING APPROVAL</span>';
    default:
      return `<span class="badge">${escapeHtml(status.toUpperCase())}</span>`;
  }
}

function showExecutionDetails(ex) {
  const modal = document.getElementById('details-modal');
  const body = document.getElementById('details-modal-body');

  const actionsList = (ex.actions || [])
    .map(
      (a) => `
    <div class="detail-action">
      <div style="display:flex; justify-content:space-between; margin-bottom:0.3rem;">
        <strong>${escapeHtml(a.action_name || a.action)}</strong>
        <div>
          ${a.simulated ? '<span class="badge badge-simulated">SIMULATED</span>' : ''}
          ${a.success ? '<span class="badge badge-success">PASS</span>' : '<span class="badge badge-critical">FAIL</span>'}
          <span style="font-size:0.75rem; color:var(--text-dim); margin-left:0.5rem;">${a.duration_ms}ms</span>
        </div>
      </div>
      ${a.output ? `<pre class="detail-output">${escapeHtml(a.output)}</pre>` : ''}
      ${a.error ? `<pre class="detail-error">${escapeHtml(a.error)}</pre>` : ''}
    </div>
  `
    )
    .join('');

  body.innerHTML = `
    <div style="margin-bottom:1rem;">
      <h4>Execution: <code>${escapeHtml(ex.id || ex.execution_id)}</code></h4>
      <p class="text-muted text-sm">Playbook: <strong>${escapeHtml(ex.playbook)}</strong> • Status: ${getStatusBadge(ex.status)}</p>
    </div>
    <h5 style="margin-bottom:0.6rem; color:var(--text-dim); text-transform:uppercase; font-size:0.75rem;">Action Drilldown</h5>
    <div>${actionsList || '<p class="text-muted">No individual actions recorded.</p>'}</div>
  `;

  modal.style.display = 'flex';
}

function closeDetailsModal() {
  document.getElementById('details-modal').style.display = 'none';
}

async function fetchAuditLogs() {
  try {
    const res = await fetch('/api/audit?limit=25');
    if (!res.ok) return;
    const logs = await res.json();

    const terminal = document.getElementById('audit-terminal-body');
    if (logs.length === 0) {
      terminal.innerHTML = '<pre class="terminal-output">[SYSTEM] Audit trail initialized. Awaiting events...</pre>';
      return;
    }

    const outputText = logs
      .map((entry) => `[${entry.ts}] ${entry.event.toUpperCase()} — ${JSON.stringify(entry.payload)}`)
      .join('\n');

    terminal.innerHTML = `<pre class="terminal-output">${escapeHtml(outputText)}</pre>`;
  } catch (err) {
    console.error('Error fetching audit logs:', err);
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
