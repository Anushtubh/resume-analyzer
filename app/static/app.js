/**
 * ============================================================================
 * TalentLens - Fully Interactive Client Application Logic
 * ============================================================================
 */

// ----------------------------------------------------------------------------
// 1. Core DOM Elements
// ----------------------------------------------------------------------------
const filesInput = document.querySelector('#file-input');
const fileList = document.querySelector('#file-list');
const processBtn = document.querySelector('#process-btn');
const analyzeBtn = document.querySelector('#analyze-btn');
const dropzone = document.querySelector('#dropzone');
const toastEl = document.querySelector('#toast');

let selectedFiles = [];
let results = [];
let candidatePool = [];

// Micro DOM selector helper
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => document.querySelectorAll(selector);

// HTML entity escaping helper to prevent XSS
const esc = (str) =>
  String(str ?? '').replace(
    /[&<>"']/g,
    (char) =>
      ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      }[char])
  );

function pct(value) {
  return `${Math.round(value * 100)}%`;
}

// ----------------------------------------------------------------------------
// 2. Preset Job Descriptions
// ----------------------------------------------------------------------------
const JD_PRESETS = {
  ml: {
    title: 'Machine Learning Engineer',
    desc: "We are looking for a Machine Learning Engineer with 2+ years of experience in Python, machine learning and deep learning. Experience with PyTorch or TensorFlow is preferred. Bachelor's degree in Computer Science is required. AWS and SQL are useful.",
  },
  backend: {
    title: 'Backend Engineer',
    desc: 'Seeking a backend engineer with 3+ years of experience in Python, FastAPI or Django, SQL, PostgreSQL, Docker and Git. A computer science degree is preferred.',
  },
  ds: {
    title: 'Data Scientist',
    desc: "We need a Data Scientist with 2+ years of experience in Python, machine learning, SQL, Pandas and NumPy. Experience with Tableau or Power BI and a bachelor's degree is preferred.",
  },
};

// ----------------------------------------------------------------------------
// 3. User Profile & Admin Customization
// ----------------------------------------------------------------------------
const DEFAULT_PROFILE = {
  name: 'Jordan Davis',
  role: 'Administrator',
  email: 'jordan@acmestudio.com',
  workspace: 'Acme Studio',
  defaultK: '5',
};

function getProfile() {
  try {
    const saved = localStorage.getItem('talentlens_profile');
    return saved ? { ...DEFAULT_PROFILE, ...JSON.parse(saved) } : DEFAULT_PROFILE;
  } catch {
    return DEFAULT_PROFILE;
  }
}

function saveProfile(data) {
  localStorage.setItem('talentlens_profile', JSON.stringify(data));
  applyProfile(data);
}

function getInitials(name) {
  if (!name || !name.trim()) return 'AD';
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

function applyProfile(profile) {
  const initials = getInitials(profile.name);
  const firstName = profile.name.trim().split(/\s+/)[0] || 'Admin';

  // Update avatars
  const sidebarAvatar = $('#sidebar-avatar');
  const topbarAvatar = $('#topbar-avatar');
  const modalAvatar = $('#modal-avatar-preview');
  if (sidebarAvatar) sidebarAvatar.textContent = initials;
  if (topbarAvatar) topbarAvatar.textContent = initials;
  if (modalAvatar) modalAvatar.textContent = initials;

  // Update names & roles
  const sidebarName = $('#sidebar-user-name');
  const sidebarRole = $('#sidebar-user-role');
  const headerName = $('#header-user-name');
  const modalAvatarName = $('#modal-avatar-name');
  const greetingHeader = $('#greeting-header');

  if (sidebarName) sidebarName.textContent = profile.name;
  if (sidebarRole) sidebarRole.textContent = profile.role;
  if (headerName) headerName.textContent = firstName;
  if (modalAvatarName) modalAvatarName.textContent = profile.name;
  if (greetingHeader) {
    greetingHeader.innerHTML = `${getGreeting()}, <span id="header-user-name">${esc(firstName)}</span> <span>✦</span>`;
  }

  // Update workspace
  const workspaceName = $('#workspace-name');
  const workspaceIcon = $('#workspace-icon');
  const breadcrumbOrg = $('#breadcrumb-org');
  if (workspaceName) workspaceName.textContent = profile.workspace;
  if (workspaceIcon) workspaceIcon.textContent = (profile.workspace || 'A')[0].toUpperCase();
  if (breadcrumbOrg) breadcrumbOrg.textContent = profile.workspace;

  // Populate form fields
  const inputName = $('#input-admin-name');
  const inputRole = $('#input-admin-role');
  const inputEmail = $('#input-admin-email');
  const inputWorkspace = $('#input-workspace-name');
  const inputDefaultK = $('#input-default-k');

  if (inputName) inputName.value = profile.name;
  if (inputRole) inputRole.value = profile.role;
  if (inputEmail) inputEmail.value = profile.email || '';
  if (inputWorkspace) inputWorkspace.value = profile.workspace;
  if (inputDefaultK) inputDefaultK.value = profile.defaultK || '5';
}

// ----------------------------------------------------------------------------
// 4. Activity Audit Trail & Notifications
// ----------------------------------------------------------------------------
const DEFAULT_ACTIVITIES = [
  {
    time: 'System Boot',
    text: 'Initialized sentence-transformers/all-MiniLM-L6-v2 vector pipeline',
    type: 'info',
  },
  {
    time: 'System Ready',
    text: 'FAISS IndexFlatIP cosine similarity engine standing by',
    type: 'success',
  },
];

function getActivityLog() {
  try {
    const saved = localStorage.getItem('talentlens_activity');
    return saved ? JSON.parse(saved) : DEFAULT_ACTIVITIES;
  } catch {
    return DEFAULT_ACTIVITIES;
  }
}

function logActivity(text, type = 'info') {
  const activities = getActivityLog();
  const now = new Date();
  const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  activities.unshift({ time: timeStr, text, type });
  if (activities.length > 50) activities.pop();

  localStorage.setItem('talentlens_activity', JSON.stringify(activities));
  renderActivityList();
  addNotification(text);
}

function renderActivityList() {
  const container = $('#activity-timeline');
  if (!container) return;
  const activities = getActivityLog();

  container.innerHTML = activities
    .map(
      (item) => `
      <div class="activity-row ${esc(item.type)}">
        <span class="activity-time">${esc(item.time)}</span>
        <span class="activity-text">${esc(item.text)}</span>
      </div>`
    )
    .join('');
}

// System notifications dropdown
let notifications = [
  'Welcome to TalentLens Resume Intelligence!',
  'Ready to screen PDF and DOCX candidate files.',
];

function addNotification(text) {
  notifications.unshift(text);
  if (notifications.length > 15) notifications.pop();
  renderNotifications();
}

function renderNotifications() {
  const list = $('#notification-list');
  if (!list) return;
  list.innerHTML = notifications
    .map((item) => `<div class="notification-item">${esc(item)}</div>`)
    .join('');
}

// ----------------------------------------------------------------------------
// 5. Toast Notifications
// ----------------------------------------------------------------------------
let toastTimer = null;
function showToast(message, type = 'success') {
  if (!toastEl) return;
  toastEl.textContent = message;
  toastEl.className = `toast show ${type}`;

  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toastEl.classList.remove('show');
  }, 3500);
}

function notice(message, ok = false) {
  const el = $('#status-message');
  if (!el) return;
  el.textContent = message;
  el.style.color = ok ? '#26946f' : '#d05c4c';
}

function busy(button, on, label) {
  if (!button) return;
  if (on) {
    button.dataset.wasDisabled = String(button.disabled);
    button.disabled = true;
    button.dataset.label = button.innerHTML;
    button.innerHTML = `<span class="spinner"></span> ${label}`;
  } else if (button.dataset.label) {
    button.innerHTML = button.dataset.label;
    button.disabled = button.dataset.wasDisabled === 'true';
    delete button.dataset.label;
    delete button.dataset.wasDisabled;
  }
}

// ----------------------------------------------------------------------------
// 6. Modal Management
// ----------------------------------------------------------------------------
function openModal(modalId) {
  const modal = $(`#${modalId}`);
  if (modal) {
    modal.classList.add('open');
    if (modalId === 'activity-modal') renderActivityList();
    if (modalId === 'talent-pool-modal') renderTalentPool();
  }
}

function closeModal(modalId) {
  const modal = $(`#${modalId}`);
  if (modal) modal.classList.remove('open');
}

function closeAllModals() {
  $$('.modal-backdrop').forEach((m) => m.classList.remove('open'));
  const dropdown = $('#ranking-context-menu');
  const notifDropdown = $('#notification-dropdown');
  if (dropdown) dropdown.classList.remove('open');
  if (notifDropdown) notifDropdown.classList.remove('open');
}

// Modal triggers
$$('[data-close]').forEach((btn) => {
  btn.onclick = () => closeModal(btn.dataset.close);
});

$$('.modal-backdrop').forEach((backdrop) => {
  backdrop.onclick = (e) => {
    if (e.target === backdrop) backdrop.classList.remove('open');
  };
});

window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeAllModals();
});

// ----------------------------------------------------------------------------
// 7. Navigation & Header Button Wiring
// ----------------------------------------------------------------------------
// User profile click
$('#profile-card')?.addEventListener('click', () => openModal('profile-modal'));
$('#topbar-avatar').onclick = () => openModal('profile-modal');

// Workspace click
$('#workspace-card').onclick = () => openModal('settings-modal');

// Nav items
$('#nav-overview').onclick = (e) => {
  e.preventDefault();
  window.scrollTo({ top: 0, behavior: 'smooth' });
};

$('#nav-screening').onclick = (e) => {
  e.preventDefault();
  $('#screening').scrollIntoView({ behavior: 'smooth' });
};

$('#nav-talent-pool').onclick = (e) => {
  e.preventDefault();
  openModal('talent-pool-modal');
};

$('#nav-job-descriptions').onclick = (e) => {
  e.preventDefault();
  openModal('jd-modal');
};

$('#nav-activity').onclick = (e) => {
  e.preventDefault();
  openModal('activity-modal');
};

$('#nav-settings').onclick = (e) => {
  e.preventDefault();
  openModal('settings-modal');
};

// Help & Documentation
$('#help-card-trigger').onclick = () => openModal('help-modal');
$('#help-link').onclick = (e) => {
  e.preventDefault();
  openModal('help-modal');
};

// Stat Card: Click Total Candidates to view pool
$('#stat-card-candidates').onclick = () => openModal('talent-pool-modal');

// Scoring Explanation link
$('#scoring-info-btn').onclick = (e) => {
  e.preventDefault();
  openModal('scoring-modal');
};

// Notifications button
$('#notification-btn').onclick = (e) => {
  e.stopPropagation();
  $('#notification-dropdown').classList.toggle('open');
};

$('#clear-notifications-btn').onclick = () => {
  notifications = [];
  renderNotifications();
};

document.addEventListener('click', (e) => {
  const notifDropdown = $('#notification-dropdown');
  const notifBtn = $('#notification-btn');
  if (notifDropdown && !notifDropdown.contains(e.target) && e.target !== notifBtn) {
    notifDropdown.classList.remove('open');
  }

  const rankingMenu = $('#ranking-context-menu');
  const rankingBtn = $('#ranking-options-btn');
  if (rankingMenu && !rankingMenu.contains(e.target) && e.target !== rankingBtn) {
    rankingMenu.classList.remove('open');
  }
});

// Ranking More Options (Export / Clear)
$('#ranking-options-btn').onclick = (e) => {
  e.stopPropagation();
  $('#ranking-context-menu').classList.toggle('open');
};

$('#export-json-btn').onclick = () => {
  $('#ranking-context-menu').classList.remove('open');
  if (!results.length) {
    showToast('No candidates currently ranked to export.', 'error');
    return;
  }
  const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `talentlens_rankings_${Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(url);
  showToast('✓ Exported rankings as JSON');
  logActivity('Exported ranked candidate results as JSON', 'info');
};

$('#export-csv-btn').onclick = () => {
  $('#ranking-context-menu').classList.remove('open');
  if (!results.length) {
    showToast('No candidates currently ranked to export.', 'error');
    return;
  }
  const headers = [
    'Rank',
    'Candidate',
    'FinalScore',
    'SemanticMatch',
    'SkillMatch',
    'ExperienceMatch',
    'EducationMatch',
    'MatchedSkills',
    'MissingSkills',
  ];
  const rows = results.map((r, i) => [
    i + 1,
    `"${r.candidate.filename}"`,
    (r.final_score * 100).toFixed(1) + '%',
    (r.match.semantic_similarity * 100).toFixed(1) + '%',
    (r.match.skill_match * 100).toFixed(1) + '%',
    (r.match.experience_match * 100).toFixed(1) + '%',
    (r.match.education_match * 100).toFixed(1) + '%',
    `"${(r.match.matched_skills || []).join('; ')}"`,
    `"${(r.match.missing_skills || []).join('; ')}"`,
  ]);
  const csvContent = [headers.join(','), ...rows.map((row) => row.join(','))].join('\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `talentlens_rankings_${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
  showToast('✓ Exported rankings as CSV');
  logActivity('Exported ranked candidate results as CSV', 'info');
};

$('#clear-results-btn').onclick = () => {
  $('#ranking-context-menu').classList.remove('open');
  results = [];
  $('#results-summary').innerHTML = '<span class="live-dot"></span> Waiting for your first analysis';
  $('#results-list').innerHTML = `
    <div class="empty-state">
      <div class="empty-illustration"><span>✳</span><i>↗</i><b>•••</b></div>
      <strong>Your shortlist starts here</strong>
      <p>Process a few resumes, add a job description, and your best-fit candidates will appear right here.</p>
      <button class="text-button" id="empty-upload">Upload resumes <span>→</span></button>
    </div>`;
  const emptyUploadBtn = $('#empty-upload');
  if (emptyUploadBtn) emptyUploadBtn.onclick = () => filesInput.click();
  $('#stat-score').textContent = '—';
  $('#stat-score-note').textContent = 'Run an analysis to see matches';
  showToast('Shortlist cleared');
};

// ----------------------------------------------------------------------------
// 8. Profile & Settings Form Submissions
// ----------------------------------------------------------------------------
$('#profile-form').onsubmit = (e) => {
  e.preventDefault();
  const profile = getProfile();
  const newName = $('#input-admin-name').value.trim();
  const newRole = $('#input-admin-role').value.trim();
  const newEmail = $('#input-admin-email').value.trim();

  if (!newName) {
    showToast('Name cannot be blank', 'error');
    return;
  }

  profile.name = newName;
  profile.role = newRole || 'Administrator';
  profile.email = newEmail;

  saveProfile(profile);
  closeModal('profile-modal');
  showToast(`✓ Admin profile updated to "${newName}"`);
  logActivity(`Updated Admin profile: ${newName} (${profile.role})`, 'success');
};

$('#settings-form').onsubmit = (e) => {
  e.preventDefault();
  const profile = getProfile();
  const newWorkspace = $('#input-workspace-name').value.trim();
  const newK = $('#input-default-k').value;

  if (newWorkspace) profile.workspace = newWorkspace;
  if (newK) {
    profile.defaultK = newK;
    $('#top-k').value = newK;
  }

  saveProfile(profile);
  closeModal('settings-modal');
  showToast('✓ Settings saved successfully');
  logActivity(`Saved workspace settings: ${profile.workspace}`, 'success');
};

$('#clear-activity-btn').onclick = () => {
  localStorage.setItem('talentlens_activity', JSON.stringify([]));
  renderActivityList();
  showToast('Activity log cleared');
};

// ----------------------------------------------------------------------------
// 9. Presets & Quick Fill Logic
// ----------------------------------------------------------------------------
function loadPreset(key) {
  const preset = JD_PRESETS[key];
  if (!preset) return;

  $('#job-title').value = preset.title;
  $('#job-description').value = preset.desc;
  $('#jd-count').textContent = `${preset.desc.length} characters`;

  $$('.preset-chip').forEach((c) => c.classList.remove('active'));
  const activeChip = $(`[data-preset="${key}"]`);
  if (activeChip) activeChip.classList.add('active');

  // Enable analyze button if resumes are ready
  if (candidatePool.length > 0) {
    analyzeBtn.disabled = false;
  }

  showToast(`Loaded preset: ${preset.title}`);
  logActivity(`Applied job description preset: "${preset.title}"`, 'info');
}

$$('.preset-chip').forEach((btn) => {
  btn.onclick = () => loadPreset(btn.dataset.preset);
});

$$('.load-jd-btn').forEach((btn) => {
  btn.onclick = () => {
    loadPreset(btn.dataset.role);
    closeModal('jd-modal');
    $('#screening').scrollIntoView({ behavior: 'smooth' });
  };
});

// ----------------------------------------------------------------------------
// 10. Talent Pool Renderer
// ----------------------------------------------------------------------------
function renderTalentPool(filter = '') {
  const list = $('#talent-pool-list');
  if (!list) return;

  const q = filter.trim().toLowerCase();
  const filtered = candidatePool.filter(
    (c) =>
      c.name.toLowerCase().includes(q) ||
      (c.preview && c.preview.toLowerCase().includes(q))
  );

  if (!filtered.length) {
    list.innerHTML = `<div class="empty-state" style="height: 180px;"><p>No matching candidates found.</p></div>`;
    return;
  }

  list.innerHTML = filtered
    .map(
      (c) => `
      <div class="pool-item">
        <div>
          <strong>${esc(c.name)}</strong>
          <small>${esc(c.preview.slice(0, 140))}…</small>
        </div>
        <span class="file-type">${c.name.toLowerCase().endsWith('.pdf') ? 'PDF' : 'DOCX'}</span>
      </div>`
    )
    .join('');
}

$('#pool-search-input').oninput = (e) => {
  renderTalentPool(e.target.value);
};

// ----------------------------------------------------------------------------
// 11. File Upload & Drag-and-Drop
// ----------------------------------------------------------------------------
function renderFiles() {
  fileList.innerHTML = selectedFiles
    .map(
      (file, index) => `
      <div class="file-row">
        <span class="file-type">${file.name.toLowerCase().endsWith('.pdf') ? 'PDF' : 'DOCX'}</span>
        <span>${esc(file.name)}</span>
        <span>${(file.size / 1024).toFixed(0)} KB</span>
        <button data-remove="${index}" aria-label="Remove">×</button>
      </div>`
    )
    .join('');

  $('#upload-hint').textContent = selectedFiles.length
    ? `${selectedFiles.length} queued · next batch processes ${Math.min(selectedFiles.length, 25)}`
    : 'No files selected';

  processBtn.disabled = !selectedFiles.length;

  fileList.querySelectorAll('[data-remove]').forEach((btn) => {
    btn.onclick = () => {
      selectedFiles.splice(+btn.dataset.remove, 1);
      renderFiles();
    };
  });
}

function addFiles(list) {
  for (const file of list) {
    if (!/\.(pdf|docx)$/i.test(file.name)) {
      notice(`${file.name}: only PDF and DOCX files are supported.`);
      showToast(`${file.name} is not a PDF or DOCX file`, 'error');
      continue;
    }
    if (!selectedFiles.some((x) => x.name === file.name && x.size === file.size)) {
      selectedFiles.push(file);
    }
  }
  renderFiles();
}

filesInput.onchange = () => addFiles(filesInput.files);

for (const event of ['dragenter', 'dragover']) {
  dropzone.addEventListener(event, (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });
}

for (const event of ['dragleave', 'drop']) {
  dropzone.addEventListener(event, (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
  });
}

dropzone.addEventListener('drop', (e) => addFiles(e.dataTransfer.files));
$('#empty-upload').onclick = () => filesInput.click();

// ----------------------------------------------------------------------------
// 12. API Wrapper
// ----------------------------------------------------------------------------
async function api(url, options = {}) {
  const response = await fetch(url, options);
  let data;
  try {
    data = await response.json();
  } catch {
    data = { detail: 'The server returned an unexpected response.' };
  }
  if (!response.ok) {
    if (response.status === 401 && !url.startsWith('/api/auth/')) {
      showAuthGate(false, 'Your session has expired. Please sign in again.');
    }
    throw new Error(data.detail || 'Request failed');
  }
  return data;
}

function setAuthError(message = '') {
  const banner = $('#auth-error-banner');
  const errorEl = $('#auth-error');
  if (!banner || !errorEl) return;
  if (message) {
    errorEl.textContent = message;
    banner.hidden = false;
    banner.classList.remove('shake');
    void banner.offsetWidth; // Trigger reflow
    banner.classList.add('shake');
  } else {
    errorEl.textContent = '';
    banner.hidden = true;
    banner.classList.remove('shake');
  }
}

function updatePasswordHints() {
  const isSetup = $('#auth-form')?.dataset.setup === 'true';
  if (!isSetup) return;

  const pwd = $('#auth-password')?.value || '';
  const confirm = $('#auth-confirm-password')?.value || '';

  const lenOk = pwd.length >= 12;
  const matchOk = pwd.length > 0 && pwd === confirm;

  const lenEl = $('#hint-len');
  const matchEl = $('#hint-match');

  if (lenEl) {
    lenEl.classList.toggle('valid', lenOk);
    const bullet = lenEl.querySelector('.hint-bullet');
    if (bullet) bullet.textContent = lenOk ? '✓' : '●';
  }
  if (matchEl) {
    matchEl.classList.toggle('valid', matchOk);
    const bullet = matchEl.querySelector('.hint-bullet');
    if (bullet) bullet.textContent = matchOk ? '✓' : '●';
  }
}

function setupPasswordToggle(btnId, inputId) {
  const btn = $(btnId);
  const input = $(inputId);
  if (!btn || !input) return;

  btn.onclick = () => {
    const isPassword = input.type === 'password';
    input.type = isPassword ? 'text' : 'password';
    btn.setAttribute('aria-label', isPassword ? 'Hide password' : 'Show password');
    btn.setAttribute('title', isPassword ? 'Hide password' : 'Show password');
    const eyeOpen = btn.querySelector('.pwd-eye-open');
    const eyeClosed = btn.querySelector('.pwd-eye-closed');
    if (eyeOpen && eyeClosed) {
      eyeOpen.hidden = isPassword;
      eyeClosed.hidden = !isPassword;
    }
  };
}

function showAuthGate(setupRequired, initialError = '', registrationMode = false) {
  const registering = setupRequired || registrationMode;
  document.body.classList.remove('authenticated');
  const gate = $('#auth-gate');
  if (gate) gate.hidden = false;

  const nameWrap = $('#auth-name-wrap');
  const nameInput = $('#auth-name');
  const confirmWrap = $('#auth-confirm-wrap');
  const confirmInput = $('#auth-confirm-password');
  const pwdHints = $('#auth-pwd-hints');
  const pwdHint = $('#auth-password-hint');
  const helpEl = $('#auth-help');
  const pwdInput = $('#auth-password');
  const submitBtn = $('#auth-submit');

  if (nameWrap) nameWrap.hidden = !registering;
  if (nameInput) {
    nameInput.required = registering;
    if (!registering) nameInput.value = '';
  }

  if (confirmWrap) confirmWrap.hidden = !registering;
  if (confirmInput) {
    confirmInput.required = registering;
    if (!registering) confirmInput.value = '';
  }

  if (pwdHints) pwdHints.hidden = !registering;
  if (pwdHint) pwdHint.hidden = !registering;
  if (helpEl) helpEl.hidden = !registering;

  $('#auth-eyebrow').textContent = setupRequired
    ? 'INITIAL WORKSPACE SETUP'
    : registering ? 'NEW RECRUITER ACCOUNT' : 'PRIVATE RECRUITER WORKSPACE';
  $('#auth-title').textContent = setupRequired ? 'Create your workspace' : registering ? 'Create your account' : 'Welcome back';
  $('#auth-description').textContent = registering
    ? 'Create the primary administrator account to secure this local resume database.'
    : 'Sign in to manage your saved candidate pool.';
  if (registering && !setupRequired) {
    $('#auth-description').textContent = 'Create an account to start your own private candidate workspace.';
  }
  if (helpEl) {
    helpEl.textContent = setupRequired
      ? 'The first account creates the local workspace. Each recruiter account keeps its own candidate pool.'
      : 'Your account and saved candidate pool are separate from other recruiters using this app.';
  }

  if (submitBtn) {
    submitBtn.innerHTML = registering
      ? '<span class="btn-text">Create account</span> <span class="btn-arrow" aria-hidden="true">→</span>'
      : '<span class="btn-text">Sign in</span> <span class="btn-arrow" aria-hidden="true">→</span>';
  }

  if (pwdInput) {
    pwdInput.autocomplete = registering ? 'new-password' : 'current-password';
    pwdInput.minLength = registering ? 12 : 1;
  }

  const modeSwitch = $('#auth-mode-switch');
  const modeToggle = $('#auth-mode-toggle');
  if (modeSwitch) modeSwitch.hidden = setupRequired;
  if ($('#auth-mode-prompt')) $('#auth-mode-prompt').textContent = registering ? 'Already have an account?' : 'New recruiter?';
  if (modeToggle) modeToggle.textContent = registering ? 'Sign in' : 'Create account';

  $('#auth-form').dataset.setup = String(registering);
  updatePasswordHints();
  setAuthError(initialError);
}

$('#auth-mode-toggle')?.addEventListener('click', () => {
  const registering = $('#auth-form').dataset.setup === 'true';
  showAuthGate(false, '', !registering);
});

function enterWorkspace(user) {
  const gate = $('#auth-gate');
  if (gate) gate.hidden = true;
  document.body.classList.add('authenticated');
  document.body.classList.remove('auth-loading');

  const profile = { ...getProfile(), name: user.display_name, email: user.email, role: 'Recruiter' };
  saveProfile(profile);
  api('/api/status').then(updateStatus).catch((error) => notice(error.message));
}

$('#auth-form').onsubmit = async (event) => {
  event.preventDefault();
  const setup = $('#auth-form').dataset.setup === 'true';
  const email = $('#auth-email').value.trim();
  const password = $('#auth-password').value;
  const name = $('#auth-name') ? $('#auth-name').value.trim() : '';
  const confirm = $('#auth-confirm-password') ? $('#auth-confirm-password').value : '';

  setAuthError('');

  // Validate inputs
  if (setup) {
    if (!name) {
      setAuthError('Please enter your full name for the administrator account.');
      $('#auth-name')?.focus();
      return;
    }
    if (password.length < 12) {
      setAuthError('Password must be at least 12 characters.');
      $('#auth-password')?.focus();
      return;
    }
    if (password !== confirm) {
      setAuthError('Passwords do not match. Please verify both password fields.');
      $('#auth-confirm-password')?.focus();
      return;
    }
  }

  if (!$('#auth-email').checkValidity()) {
    setAuthError('Please enter a valid email address.');
    $('#auth-email')?.focus();
    return;
  }

  if (!password) {
    setAuthError('Please enter your password.');
    $('#auth-password')?.focus();
    return;
  }

  const payload = { email, password };
  if (setup) payload.name = name;

  busy($('#auth-submit'), true, setup ? 'Creating account…' : 'Signing in…');
  try {
    const data = await api(setup ? '/api/auth/register' : '/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    enterWorkspace(data.user);
    $('#auth-form').reset();
    updatePasswordHints();
  } catch (error) {
    setAuthError(error.message);
  } finally {
    busy($('#auth-submit'), false);
  }
};

$('#top-k').addEventListener('input', () => {
  const input = $('#top-k');
  input.setCustomValidity(input.value.trim() && Number.isInteger(Number(input.value)) && Number(input.value) > 0
    ? '' : 'Enter a whole number greater than zero.');
});

$('#logout-btn').onclick = async () => {
  try { await api('/api/auth/logout', { method: 'POST' }); } catch {}

  // Clear in-memory candidate and results state to prevent data lingering
  selectedFiles = [];
  results = [];
  candidatePool = [];

  if (fileList) fileList.innerHTML = '';
  if (filesInput) filesInput.value = '';
  const resultsContainer = $('#results-container');
  if (resultsContainer) resultsContainer.innerHTML = '';
  const poolTableBody = $('#pool-table-body');
  if (poolTableBody) poolTableBody.innerHTML = '';
  const searchInput = $('#pool-search-input');
  if (searchInput) searchInput.value = '';

  showAuthGate(false);
  $('#auth-password').value = '';
  if ($('#auth-confirm-password')) $('#auth-confirm-password').value = '';
};

// Wire password visibility toggles and real-time validation
setupPasswordToggle('#auth-pwd-toggle', '#auth-password');
setupPasswordToggle('#auth-confirm-pwd-toggle', '#auth-confirm-password');

$('#auth-password')?.addEventListener('input', updatePasswordHints);
$('#auth-confirm-password')?.addEventListener('input', updatePasswordHints);

async function initializeAuth() {
  try {
    // A one-time local link lets the app owner return to the sign-in screen
    // even when a browser session cookie is already active.
    const url = new URL(window.location.href);
    if (url.searchParams.get('logout') === '1') {
      await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' });
      url.searchParams.delete('logout');
      window.history.replaceState({}, '', `${url.pathname}${url.search}${url.hash}`);
    }
    const data = await api('/api/auth/me');
    enterWorkspace(data.user);
  } catch {
    try {
      const setup = await api('/api/auth/setup-status');
      showAuthGate(setup.setup_required);
    } catch {
      showAuthGate(false, 'Could not reach the local server. Make sure it is running and refresh.');
    }
  } finally {
    document.body.classList.remove('auth-loading');
  }
}

function updateStatus(data, clearSelection = true) {
  $('#stat-processed').textContent = data.processed;
  $('#stat-failed').textContent = data.failed;
  $('#stat-candidates').textContent = data.processed || '—';
  $('#nav-screen-count').textContent = data.processed || '0';
  $('#nav-pool-count').textContent = data.processed || '0';

  $('#upload-check').classList.toggle('done', data.ready);
  $('#upload-check').textContent = data.ready ? '✓' : '1';

  candidatePool = data.files || [];
  renderTalentPool();

  const jdValue = $('#job-description').value.trim();
  analyzeBtn.disabled = !(data.ready && jdValue);

  if (clearSelection) {
    $('#file-list').innerHTML = '';
    selectedFiles = [];
    renderFiles();
  }

  if (data.failures?.length) {
    $('#file-list').innerHTML = data.failures
      .map(
        (f) => `
        <div class="warning-item">
          <strong>${esc(f.name)}</strong>: ${esc(f.error)}
        </div>`
      )
      .join('');
  }
  notice(`${data.processed} resumes active in talent pool · ${data.failed} failed`, true);
}

// ----------------------------------------------------------------------------
// 13. Pipeline Actions: Upload, Demo & Analysis
// ----------------------------------------------------------------------------
processBtn.onclick = async () => {
  if (!selectedFiles.length) return;
  const batchFiles = selectedFiles.slice(0, 25);
  const form = new FormData();
  batchFiles.forEach((file) => form.append('files', file));

  busy(processBtn, true, 'Processing resumes…');
  notice(
    'Extracting resume text, building profiles, and generating semantic embeddings…',
    true
  );

  try {
    const statusData = await api('/api/process', { method: 'POST', body: form });
    updateStatus(statusData, false);
    selectedFiles = selectedFiles.slice(batchFiles.length);
    renderFiles();
    showToast(`✓ Processed batch of ${batchFiles.length} resumes. ${selectedFiles.length} remain in the queue.`, 'success');
    logActivity(`Processed batch of ${batchFiles.length}; ${statusData.processed} resumes in the saved pool`, 'success');
  } catch (err) {
    notice(err.message);
    showToast(err.message, 'error');
    logActivity(`Resume ingestion failed: ${err.message}`, 'warning');
  } finally {
    busy(processBtn, false);
  }
};

$('#demo-btn').onclick = async (e) => {
  const btn = e.currentTarget;
  busy(btn, true, 'Loading demo…');
  notice(
    'Loading sample candidate resumes into FAISS vector index…',
    true
  );

  try {
    const statusData = await api('/api/demo', { method: 'POST' });
    updateStatus(statusData);
    showToast(`✓ ${statusData.processed} demo candidates are in your saved pool.`, 'success');
    logActivity(`Loaded demo candidates; ${statusData.processed} resumes in saved pool`, 'success');

    // Auto-populate default job description if empty for frictionless experience
    if (!$('#job-description').value.trim()) {
      loadPreset('ml');
    }
  } catch (err) {
    notice(err.message);
    showToast(err.message, 'error');
    logActivity(`Demo load failed: ${err.message}`, 'warning');
  } finally {
    busy(btn, false);
  }
};

$('#job-description').oninput = (e) => {
  const val = e.target.value;
  $('#jd-count').textContent = `${val.length} characters`;
  analyzeBtn.disabled = !(val.trim() && candidatePool.length > 0);
};

analyzeBtn.onclick = async () => {
  const description = $('#job-description').value.trim();
  if (!description) {
    notice('Add a job description before running candidate analysis.');
    showToast('Please add a job description first', 'error');
    return;
  }

  const form = new FormData();
  const title = $('#job-title').value || 'Role';
  form.append('title', title);
  form.append('job_description', description);
  const topK = Number($('#top-k').value);
  if (!Number.isSafeInteger(topK) || topK < 1) {
    $('#top-k').setCustomValidity('Enter a whole number greater than zero.');
    $('#top-k').reportValidity();
    $('#top-k').focus();
    return;
  }
  form.append('top_k', String(topK));

  busy(analyzeBtn, true, 'Finding top matches…');
  notice('Generating query embedding and computing multi-factor candidate scores…', true);

  try {
    const data = await api('/api/analyze', { method: 'POST', body: form });
    results = data.results;
    renderResults(data.title);

    const topScore = results.length ? Math.round(results[0].final_score * 100) : null;
    $('#stat-score').textContent = topScore !== null ? `${topScore}%` : '—';
    $('#stat-score-note').textContent = topScore !== null ? `Top candidate fit for "${title}"` : 'Run an analysis to see matches';

    notice(`Ranked ${results.length} candidates against “${data.title}”.`, true);
    showToast(`✓ Ranked ${results.length} candidates for "${title}"!`, 'success');
    logActivity(`Screened candidates for role "${title}" (Top score: ${topScore}%)`, 'info');
  } catch (err) {
    notice(err.message);
    showToast(err.message, 'error');
    logActivity(`Candidate screening failed: ${err.message}`, 'warning');
  } finally {
    busy(analyzeBtn, false);
  }
};

// ----------------------------------------------------------------------------
// 14. Candidate ranking, search, filters, details, and browser-local shortlist
// ----------------------------------------------------------------------------
function shortlistStorageKey() {
  return `talentlens_shortlist_v1:${encodeURIComponent(currentRecruiterKey)}`;
}

function isShortlisted(candidateId) {
  return shortlistIds.has(String(candidateId));
}

function toggleShortlist(candidateId) {
  const id = String(candidateId || '');
  if (!id) return;
  if (shortlistIds.has(id)) shortlistIds.delete(id);
  else shortlistIds.add(id);

  let persisted = true;
  try {
    localStorage.setItem(shortlistStorageKey(), JSON.stringify([...shortlistIds]));
  } catch {
    persisted = false;
  }

  renderResults(resultsTitle);
  renderTalentPool($('#pool-search-input')?.value || '');
  showToast(persisted
    ? (shortlistIds.has(id) ? 'Candidate shortlisted in this browser.' : 'Candidate removed from shortlist.')
    : 'Shortlist updated for this session; browser storage is unavailable.', persisted ? 'success' : 'error');
}

function rankingEntries() {
  const rankedIds = new Set(results.map((item) => String(item.candidate.candidate_id)));
  const entries = results.map((item, index) => ({
    candidate: item.candidate,
    match: item.match,
    finalScore: Number(item.final_score),
    rank: index + 1,
    analyzed: true,
  }));

  candidatePool.forEach((file) => {
    if (rankedIds.has(String(file.id))) return;
    entries.push({
      candidate: {
        candidate_id: file.id,
        filename: file.name,
        clean_text: file.preview || '',
        skills: [],
        experience: [],
        education: [],
        companies: [],
        job_roles: [],
        projects: [],
        certifications: [],
      },
      match: null,
      finalScore: null,
      rank: null,
      analyzed: false,
    });
  });
  return entries;
}

function renderRankingLoading() {
  $('#results-summary').innerHTML = '<span class="live-dot is-loading"></span><strong>Analyzing candidates…</strong>';
  $('#results-list').innerHTML = Array.from({ length: 3 }, () => `
    <div class="ranking-skeleton" aria-hidden="true">
      <span></span><div><i></i><i></i><i></i></div><b></b>
    </div>`).join('');
}

function bindRankingActions() {
  $('#results-list').querySelectorAll('[data-toggle-shortlist]').forEach((button) => {
    button.addEventListener('click', () => toggleShortlist(button.dataset.toggleShortlist));
  });
  $('#results-list').querySelectorAll('[data-toggle-detail]').forEach((button) => {
    button.addEventListener('click', () => {
      const detail = $(`#${button.getAttribute('aria-controls')}`);
      if (!detail) return;
      const open = detail.classList.toggle('open');
      button.setAttribute('aria-expanded', String(open));
      button.textContent = open ? 'Hide analysis' : 'View analysis';
    });
  });
  $('#results-list').querySelectorAll('.candidate-resume-link').forEach((link) => {
    link.addEventListener('click', (event) => event.stopPropagation());
  });
}

function renderEnhancedResults(title = '') {
  const entries = rankingEntries();
  const availableIds = new Set(entries.map(({ candidate }) => String(candidate.candidate_id)));
  const shortlistedCount = [...shortlistIds].filter((id) => availableIds.has(id)).length;
  const rankedCount = results.length;

  $('#results-summary').innerHTML = `
    <span class="live-dot ${rankedCount ? 'is-ready' : ''}"></span>
    <strong>${rankedCount} analyzed</strong>
    <span class="summary-secondary">${entries.length} in pool · ${shortlistedCount} shortlisted</span>
    ${resultsTitle ? `<span class="summary-role">Role: <b>${esc(resultsTitle)}</b></span>` : ''}
  `;

  const query = ($('#ranking-search')?.value || '').trim().toLowerCase();
  const status = $('#ranking-status-filter')?.value || 'all';
  const shortlistedOnly = Boolean($('#ranking-shortlisted-filter')?.checked);
  const sort = $('#ranking-sort')?.value || 'score-desc';
  let visible = entries.filter(({ candidate, match, analyzed }) => {
    if (status === 'analyzed' && !analyzed) return false;
    if (status === 'not-ranked' && analyzed) return false;
    if (shortlistedOnly && !isShortlisted(candidate.candidate_id)) return false;
    const searchable = [candidate.filename, ...(candidate.skills || []), ...(candidate.job_roles || []),
      ...(candidate.education || []), ...(candidate.experience || []), ...(match?.matched_skills || []),
      ...(match?.missing_skills || []), candidate.clean_text || ''].join(' ').toLowerCase();
    return !query || searchable.includes(query);
  });

  visible.sort((a, b) => {
    if (sort === 'name-asc') return a.candidate.filename.localeCompare(b.candidate.filename);
    if (!a.analyzed) return b.analyzed ? 1 : a.candidate.filename.localeCompare(b.candidate.filename);
    if (!b.analyzed) return -1;
    return sort === 'score-asc' ? a.finalScore - b.finalScore : b.finalScore - a.finalScore;
  });

  const errorBanner = rankingError ? `
    <div class="ranking-error" role="alert">
      <span>${esc(rankingError)}</span>
      <button type="button" class="button secondary" id="ranking-retry">Retry analysis</button>
    </div>` : '';
  if (rankingError) {
    const retry = () => analyzeBtn.click();
    queueMicrotask(() => $('#ranking-retry')?.addEventListener('click', retry));
  }

  if (!entries.length) {
    $('#results-list').innerHTML = `${errorBanner}
      <div class="ranking-empty">
        <div class="ranking-empty-icon" aria-hidden="true">⌕</div>
        <strong>${rankingError ? 'Analysis could not be completed' : 'No candidates yet'}</strong>
        <p>${rankingError ? 'Check the message above, then retry. Resume processing issues are shown beside the upload controls.' : 'Processed resumes and ranked matches will appear here. Upload resumes or load the demo candidates to begin.'}</p>
        ${!rankingError ? '<button class="button secondary" type="button" id="ranking-empty-upload">Upload resumes</button>' : ''}
      </div>`;
    $('#ranking-empty-upload')?.addEventListener('click', () => filesInput.click());
    return;
  }

  if (!visible.length) {
    const filterDescription = shortlistedOnly
      ? 'No shortlisted candidates match these filters.'
      : 'No candidates match these search or status filters.';
    $('#results-list').innerHTML = `${errorBanner}<div class="ranking-filter-empty">${esc(filterDescription)} <button type="button" id="ranking-clear-filters">Clear filters</button></div>`;
    $('#ranking-clear-filters').onclick = () => {
      $('#ranking-search').value = '';
      $('#ranking-status-filter').value = 'all';
      $('#ranking-shortlisted-filter').checked = false;
      renderResults(resultsTitle);
    };
    return;
  }

  $('#results-list').innerHTML = `${errorBanner}${visible.map((entry, visibleIndex) => {
    const { candidate, match, analyzed, finalScore, rank } = entry;
    const id = String(candidate.candidate_id);
    const safeId = `candidate-${visibleIndex}`;
    const filename = candidate.filename || 'Unnamed resume';
    const skills = [...new Set([...(candidate.skills || []), ...(match?.matched_skills || []), ...(match?.missing_skills || [])])];
    const experience = (candidate.experience || []).join(', ');
    const education = (candidate.education || []).join(', ');
    const roles = (candidate.job_roles || []).join(', ');
    const resumeUrl = `/api/resumes/by-candidate/${encodeURIComponent(id)}/file`;
    const isPdf = filename.toLowerCase().endsWith('.pdf');
    const saved = isShortlisted(id);
    const why = match
      ? (match.matched_skills.length
        ? `Matches ${match.matched_skills.slice(0, 3).join(', ')}${match.matched_skills.length > 3 ? ` and ${match.matched_skills.length - 3} more` : ''}.`
        : 'Retrieved as a semantic match; no required skills were matched by the current skill extractor.')
      : (resultsTitle
        ? 'Not scored because this resume was outside the selected top-K retrieval results.'
        : 'Not analyzed yet. Run candidate analysis to retrieve and score relevant resumes.');
    const evidence = (candidate.clean_text || '').trim().slice(0, 900);

    return `
      <article class="candidate-entry ${saved ? 'is-shortlisted' : ''}">
        <div class="candidate-row">
          <span class="rank-num" aria-label="${analyzed ? `Rank ${rank}` : 'Not ranked'}">${analyzed ? String(rank).padStart(2, '0') : '—'}</span>
          <div class="candidate-main">
            <div class="candidate-title-line">
              <h3 class="candidate-name" title="${esc(filename)}">${esc(filename)}</h3>
              <span class="analysis-status ${analyzed ? 'status-analyzed' : 'status-unranked'}">${analyzed ? 'Analyzed' : resultsTitle ? 'Not in top-K' : 'Not analyzed'}</span>
            </div>
            <div class="candidate-meta">
              ${[roles, experience, education].filter(Boolean).map(esc).join(' · ') || (analyzed ? 'No experience or education details detected' : 'Resume processed; matching score not calculated')}
            </div>
            ${skills.length ? `<div class="skill-chips">${skills.slice(0, 6).map((skill) => {
              const matched = match?.matched_skills?.some((value) => value.toLowerCase() === skill.toLowerCase());
              const missing = match?.missing_skills?.some((value) => value.toLowerCase() === skill.toLowerCase());
              return `<span class="chip ${matched ? 'matched' : missing ? 'missing' : ''}">${matched ? '✓ ' : missing ? '× ' : ''}${esc(skill)}</span>`;
            }).join('')}</div>` : ''}
            <p class="candidate-reason">${esc(why)}</p>
            <div class="candidate-actions">
              <button type="button" class="candidate-action-primary" data-toggle-detail aria-controls="${safeId}" aria-expanded="false">View analysis</button>
              <button type="button" class="shortlist-action ${saved ? 'is-shortlisted' : ''}" data-toggle-shortlist="${esc(id)}" aria-pressed="${saved}">${saved ? '★ Shortlisted' : '☆ Shortlist'}</button>
              <a class="candidate-resume-link" href="${resumeUrl}" target="_blank" rel="noopener noreferrer">${isPdf ? '↗ Original PDF' : '↗ Original DOCX'}</a>
            </div>
          </div>
          <div class="candidate-score-wrap">
            ${analyzed ? `<span class="score-badge" title="Job Match Score from the existing ranking service">${pct(finalScore)}</span>` : '<span class="score-unavailable">Not analyzed</span>'}
            <span class="score-label">JOB MATCH SCORE <button type="button" class="score-info" data-score-info aria-label="Explain job match score" title="Weighted fit score from semantic similarity, skills, experience, and education. It is not a hiring probability.">ⓘ</button></span>
          </div>
        </div>
        <section class="candidate-details" id="${safeId}" aria-label="Candidate analysis details">
          ${analyzed ? `<div class="detail-grid">
            <div><div class="detail-title">Score breakdown</div>
              Semantic similarity <b>${pct(match.semantic_similarity)}</b> (50%)<br>
              Skill match <b>${pct(match.skill_match)}</b> (30%)<br>
              Experience match <b>${pct(match.experience_match)}</b> (10%)<br>
              Education match <b>${pct(match.education_match)}</b> (10%)
            </div>
            <div><div class="detail-title">Matched job requirements</div>${esc(match.matched_skills.join(', ') || 'None detected')}
              <div class="detail-title">Missing or unverified requirements</div>${esc(match.missing_skills.join(', ') || 'None detected')}
            </div>
          </div>` : `<p class="detail-note">${resultsTitle ? 'This resume is in the processed talent pool but was outside the selected top-K retrieval results, so the matching service did not calculate a candidate score.' : 'This resume has been processed and stored, but candidate matching has not been run yet. No match score is available.'}</p>`}
          <div class="profile-facts">
            ${roles ? `<div><strong>Job roles</strong><span>${esc(roles)}</span></div>` : ''}
            ${experience ? `<div><strong>Experience</strong><span>${esc(experience)}</span></div>` : ''}
            ${education ? `<div><strong>Education</strong><span>${esc(education)}</span></div>` : ''}
            ${(candidate.companies || []).length ? `<div><strong>Companies</strong><span>${esc(candidate.companies.join(', '))}</span></div>` : ''}
            ${(candidate.projects || []).length ? `<div><strong>Projects</strong><span>${esc(candidate.projects.join(', '))}</span></div>` : ''}
            ${(candidate.certifications || []).length ? `<div><strong>Certifications</strong><span>${esc(candidate.certifications.join(', '))}</span></div>` : ''}
            ${candidate.skills?.length ? `<div><strong>Extracted skills</strong><span>${esc(candidate.skills.join(', '))}</span></div>` : ''}
          </div>
          ${evidence ? `<details class="resume-evidence"><summary>Resume text evidence</summary><p>${esc(evidence)}${candidate.clean_text.length > 900 ? '…' : ''}</p></details>` : ''}
          <div class="original-resume-actions">
            <a class="button secondary resume-open-button" href="${resumeUrl}" target="_blank" rel="noopener noreferrer">${isPdf ? 'View original PDF' : 'Open original DOCX'} <span aria-hidden="true">↗</span></a>
            <a class="resume-download-link" href="${resumeUrl}" download="${esc(filename)}">Download original file</a>
          </div>
        </section>
      </article>`;
  }).join('')}`;

  bindRankingActions();
  setupCardTilt();
}

// Restore the previous compact ranked shortlist renderer.
function renderResults(title) {
  $('#results-summary').innerHTML = `
    <span class="live-dot" style="background: #40b184"></span>
    <strong>${results.length} matches</strong>
    <span style="float: right">Role: <b>${esc(title)}</b></span>
  `;

  $('#results-list').innerHTML =
    results
      .map((item, index) => {
        const candidate = item.candidate;
        const match = item.match;
        const resumeUrl = `/api/resumes/by-candidate/${encodeURIComponent(candidate.candidate_id)}/file`;
        const isPdf = candidate.filename.toLowerCase().endsWith('.pdf');
        return `
          <div class="candidate-row" data-detail="${index}">
            <span class="rank-num">${String(index + 1).padStart(2, '0')}</span>
            <div>
              <div class="candidate-name">${esc(candidate.filename)}</div>
              <div class="candidate-meta">
                ${esc(candidate.experience?.join(', ') || 'Experience not detected')} · ${match.matched_skills.length} matched skills
              </div>
              <div class="skill-chips">
                ${match.matched_skills
                  .slice(0, 4)
                  .map((skill) => `<span class="chip matched">✓ ${esc(skill)}</span>`)
                  .join('')}
                ${match.missing_skills
                  .slice(0, 2)
                  .map((skill) => `<span class="chip missing">✕ ${esc(skill)}</span>`)
                  .join('')}
              </div>
              <a class="candidate-resume-link" href="${resumeUrl}" target="_blank" rel="noopener noreferrer" aria-label="Open original ${isPdf ? 'PDF' : 'DOCX'} resume for ${esc(candidate.filename)}">
                ${isPdf ? '↗ View original PDF' : '↗ Open original DOCX'}
              </a>
            </div>
            <div>
              <div class="score">${pct(item.final_score)}</div>
              <div class="score-label">MATCH SCORE</div>
            </div>
          </div>
          <div class="candidate-details" id="detail-${index}">
            <div class="detail-grid">
              <div>
                <div class="detail-title">Score breakdown</div>
                Semantic <b>${pct(match.semantic_similarity)}</b> (50%) · Skills <b>${pct(match.skill_match)}</b> (30%)<br>
                Experience <b>${pct(match.experience_match)}</b> (10%) · Education <b>${pct(match.education_match)}</b> (10%)
                <div class="detail-title">Matched skills (${match.matched_skills.length})</div>
                ${esc(match.matched_skills.join(', ') || 'None detected')}
              </div>
              <div>
                <div class="detail-title">Missing skills (${match.missing_skills.length})</div>
                ${esc(match.missing_skills.join(', ') || 'None detected')}
                <div class="detail-title">Education & projects</div>
                ${esc(
                  [...(candidate.education || []), ...(candidate.projects || [])]
                    .slice(0, 7)
                    .join(' · ') || 'No details detected'
                )}
              </div>
            </div>
            <div class="original-resume-actions">
              <a class="button secondary resume-open-button" href="${resumeUrl}" target="_blank" rel="noopener noreferrer">
                ${isPdf ? 'View original PDF' : 'Open original DOCX'} <span aria-hidden="true">↗</span>
              </a>
              <a class="resume-download-link" href="${resumeUrl}" download="${esc(candidate.filename)}">Download original file</a>
              ${isPdf ? '' : '<span class="resume-format-note">DOCX opens in a compatible document app.</span>'}
            </div>
            <details style="margin-top: 10px">
              <summary style="cursor: pointer; color: #4569e8; font-weight: 600;">View preprocessed resume text</summary>
              <p style="white-space: pre-wrap; margin-top: 6px; color: #475467;">${esc(candidate.clean_text)}</p>
            </details>
          </div>
        `;
      })
      .join('') || '<div class="empty-state"><strong>No results found</strong></div>';

  document.querySelectorAll('.candidate-row').forEach((row) => {
    row.onclick = () => {
      $('#detail-' + row.dataset.detail).classList.toggle('open');
    };
  });
  document.querySelectorAll('.candidate-resume-link').forEach((link) => {
    link.addEventListener('click', (event) => event.stopPropagation());
  });
}

// ----------------------------------------------------------------------------
// 15. Real-time Date & Initialization
// ----------------------------------------------------------------------------
function updateCurrentDate() {
  const dateEl = $('#current-date');
  if (!dateEl) return;
  const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
  dateEl.textContent = new Date().toLocaleDateString('en-US', options).toUpperCase();
}

function setupCardTilt() {
  if (!window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;

  const cards = document.querySelectorAll(
    '.main .stat-card, .main .content-grid > .panel, .main .weights-card, .main .jd-card, .main .candidate-row, .main .candidate-details'
  );

  cards.forEach((card) => {
    if (card.dataset.tiltInitialized === 'true') return;
    card.dataset.tiltInitialized = 'true';
    card.classList.add('tilt-card');
    card.addEventListener('pointermove', (event) => {
      const bounds = card.getBoundingClientRect();
      const x = (event.clientX - bounds.left) / bounds.width;
      const y = (event.clientY - bounds.top) / bounds.height;
      card.style.setProperty('--tilt-x', `${((0.5 - y) * 5).toFixed(2)}deg`);
      card.style.setProperty('--tilt-y', `${((x - 0.5) * 5).toFixed(2)}deg`);
    });
    card.addEventListener('pointerleave', () => {
      card.style.setProperty('--tilt-x', '0deg');
      card.style.setProperty('--tilt-y', '0deg');
    });
  });
}

// Initialize on page load cleanly without duplicate runs or premature status calls
function initializeApp() {
  if (window.__appInitialized) return;
  window.__appInitialized = true;

  const profile = getProfile();
  applyProfile(profile);
  updateCurrentDate();
  renderActivityList();
  renderNotifications();
  loadPreset('ml');
  setupCardTilt();
  initializeAuth();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeApp);
} else {
  initializeApp();
}

