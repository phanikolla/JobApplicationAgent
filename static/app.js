/**
 * AI Job Application Agent - Dashboard v2.0
 * Tab-based navigation, dual input modes, resume picker, auto-apply
 */

const API_BASE = '';
let pollInterval = null;
let applyPollInterval = null;
let currentInputMode = 'url';

// ===== INIT =====
document.addEventListener('DOMContentLoaded', () => {
    loadConfig();
    loadRuns();
    loadResumes();
    checkStatus();
    positionTabIndicator();
});

// ===== TAB NAVIGATION =====
function switchTab(tabName) {
    // Update buttons
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

    // Update panels
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    document.getElementById(`panel-${tabName}`).classList.add('active');

    // Move indicator
    positionTabIndicator();

    // Load resumes when switching to apply tab
    if (tabName === 'apply') loadResumes();
}

function positionTabIndicator() {
    const activeBtn = document.querySelector('.tab-btn.active');
    const nav = document.getElementById('tabNav');
    const indicator = document.getElementById('tabIndicator');
    if (!activeBtn || !nav || !indicator) return;

    const navRect = nav.getBoundingClientRect();
    const btnRect = activeBtn.getBoundingClientRect();
    const offset = btnRect.left - navRect.left;
    indicator.style.transform = `translateX(${offset - 5}px)`;
    indicator.style.width = `${btnRect.width}px`;
}

window.addEventListener('resize', positionTabIndicator);

// ===== INPUT MODE TOGGLE =====
function setInputMode(mode) {
    currentInputMode = mode;
    document.getElementById('modeUrl').classList.toggle('active', mode === 'url');
    document.getElementById('modeText').classList.toggle('active', mode === 'text');
    document.getElementById('urlInputArea').classList.toggle('hidden', mode !== 'url');
    document.getElementById('textInputArea').classList.toggle('hidden', mode !== 'text');
}

// ===== CONFIG =====
async function loadConfig() {
    try {
        const res = await fetch(`${API_BASE}/api/config`);
        const cfg = await res.json();

        document.getElementById('cfgGeminiModel').value = cfg.llm?.gemini_model || '';
        document.getElementById('cfgOpenaiModel').value = cfg.llm?.openai_model || '';
        document.getElementById('cfgTemperature').value = cfg.llm?.default_temperature ?? 0.7;
        document.getElementById('cfgKeywords').value = (cfg.job_search?.search_keywords || []).join('\n');
        document.getElementById('cfgLocation').value = cfg.job_search?.search_location || '';
        document.getElementById('cfgJobLimit').value = cfg.job_search?.job_limit ?? 3;
        document.getElementById('cfgTimeFilter').value = cfg.job_search?.time_filter || 'past_24_hours';
        document.getElementById('cfgArchitectKeywords').value = (cfg.role_filter?.architect_keywords || []).join(', ');
        document.getElementById('cfgExcludedKeywords').value = (cfg.role_filter?.excluded_keywords || []).join(', ');
        document.getElementById('cfgTopTier').checked = cfg.role_filter?.top_tier_only ?? true;
        document.getElementById('cfgResumePath').value = cfg.profile?.resume_path || '';
        document.getElementById('cfgLinkedin').value = cfg.profile?.linkedin_url || '';
        document.getElementById('cfgGithub').value = cfg.profile?.github_url || '';
        document.getElementById('cfgReceiverEmail').value = cfg.notification?.receiver_email || '';
        document.getElementById('cfgEmailSubject').value = cfg.notification?.email_subject || '';
        document.getElementById('cfgSmtpServer').value = cfg.notification?.smtp_server || '';
        document.getElementById('cfgSmtpPort').value = cfg.notification?.smtp_port ?? 587;
        document.getElementById('cfgPdfFormat').value = cfg.pdf?.page_format || 'A4';
        document.getElementById('cfgPdfMargin').value = cfg.pdf?.margin || '0.75in';
    } catch (err) {
        // silent load failure
    }
}

async function saveConfig() {
    const keywords = document.getElementById('cfgKeywords').value.split('\n').map(k => k.trim()).filter(Boolean);
    const archKw = document.getElementById('cfgArchitectKeywords').value.split(',').map(k => k.trim()).filter(Boolean);
    const exclKw = document.getElementById('cfgExcludedKeywords').value.split(',').map(k => k.trim()).filter(Boolean);

    const cfg = {
        llm: {
            gemini_model: document.getElementById('cfgGeminiModel').value,
            openai_model: document.getElementById('cfgOpenaiModel').value,
            default_temperature: parseFloat(document.getElementById('cfgTemperature').value)
        },
        job_search: {
            search_keywords: keywords,
            search_location: document.getElementById('cfgLocation').value,
            job_limit: parseInt(document.getElementById('cfgJobLimit').value),
            time_filter: document.getElementById('cfgTimeFilter').value
        },
        role_filter: {
            architect_keywords: archKw,
            excluded_keywords: exclKw,
            top_tier_only: document.getElementById('cfgTopTier').checked
        },
        profile: {
            resume_path: document.getElementById('cfgResumePath').value,
            linkedin_url: document.getElementById('cfgLinkedin').value,
            github_url: document.getElementById('cfgGithub').value
        },
        notification: {
            receiver_email: document.getElementById('cfgReceiverEmail').value,
            email_subject: document.getElementById('cfgEmailSubject').value,
            smtp_server: document.getElementById('cfgSmtpServer').value,
            smtp_port: parseInt(document.getElementById('cfgSmtpPort').value)
        },
        pdf: {
            page_format: document.getElementById('cfgPdfFormat').value,
            margin: document.getElementById('cfgPdfMargin').value
        }
    };

    try {
        const res = await fetch(`${API_BASE}/api/config`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(cfg)
        });
        if (res.ok) showToast('Configuration saved!', 'success');
        else showToast('Failed to save config', 'error');
    } catch (err) {
        showToast('Failed to save config', 'error');
    }
}

// ===== PIPELINE ACTIONS =====
async function runFullPipeline() {
    const btn = document.getElementById('runAgentBtn');
    btn.disabled = true;

    try {
        const res = await fetch(`${API_BASE}/api/run`, { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
            showToast('Pipeline started', 'info');
            startPolling();
        } else {
            showToast(data.detail || 'Failed to start pipeline', 'error');
            btn.disabled = false;
        }
    } catch (err) {
        showToast('Failed to start pipeline', 'error');
        btn.disabled = false;
    }
}

async function runSingleJob() {
    const jobUrl = document.getElementById('jobUrlInput').value.trim();
    const jobText = document.getElementById('jobTextInput').value.trim();

    const isUrlMode = currentInputMode === 'url';
    const input = isUrlMode ? jobUrl : jobText;

    if (!input) {
        showToast(isUrlMode ? 'Please enter a job URL' : 'Please paste a job description', 'error');
        return;
    }

    // Disable both buttons
    const urlBtn = document.getElementById('quickTailorBtn');
    const textBtn = document.getElementById('quickTailorTextBtn');
    [urlBtn, textBtn].forEach(btn => {
        btn.disabled = true;
        btn.querySelector('.btn-text').textContent = 'Processing...';
        btn.querySelector('.btn-spinner').classList.remove('hidden');
    });
    document.getElementById('quickTailorResult').classList.add('hidden');

    try {
        const body = isUrlMode
            ? { job_url: jobUrl, job_text: '' }
            : { job_url: '', job_text: jobText };

        const res = await fetch(`${API_BASE}/api/run-single`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });

        const data = await res.json();
        if (res.ok) {
            showToast('Processing...', 'info');
            startPolling();
        } else {
            showToast(data.detail || 'Failed to process', 'error');
            resetTailorBtns();
        }
    } catch (err) {
        showToast('Failed to process', 'error');
        resetTailorBtns();
    }
}

function resetTailorBtns() {
    ['quickTailorBtn', 'quickTailorTextBtn'].forEach(id => {
        const btn = document.getElementById(id);
        if (btn) {
            btn.disabled = false;
            btn.querySelector('.btn-text').textContent = '\u2728 Tailor Resume';
            btn.querySelector('.btn-spinner').classList.add('hidden');
        }
    });
}

// ===== STATUS POLLING =====
function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(checkStatus, 2000);
}

function stopPolling() {
    if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
}

async function checkStatus() {
    try {
        const res = await fetch(`${API_BASE}/api/status`);
        const data = await res.json();
        updateStatusUI(data);

        if (data.status === 'completed' || data.status === 'failed') {
            stopPolling();
            document.getElementById('runAgentBtn').disabled = false;
            resetTailorBtns();
            loadRuns();

            if (data.status === 'completed' && data.result) {
                handleCompletion(data.result);
            } else if (data.status === 'failed') {
                showToast('Pipeline failed. Check logs.', 'error');
            }
        }
    } catch (err) { /* silent */ }
}

function updateStatusUI(data) {
    const indicator = document.getElementById('statusIndicator');
    const statusText = indicator.querySelector('.status-text');
    indicator.className = 'status-indicator ' + data.status;
    statusText.textContent = data.status.charAt(0).toUpperCase() + data.status.slice(1);

    const logsContainer = document.getElementById('logsContainer');
    if (data.logs && data.logs.length > 0) {
        logsContainer.innerHTML = data.logs.map(line => escapeHtml(line)).join('\n');
        logsContainer.scrollTop = logsContainer.scrollHeight;
    }
}

function handleCompletion(result) {
    if (result.type === 'single' && result.success) {
        const resultSection = document.getElementById('quickTailorResult');
        resultSection.classList.remove('hidden');
        document.getElementById('resultJobTitle').textContent = result.job_title || 'Unknown Title';
        document.getElementById('resultCompany').textContent = result.company || 'Unknown Company';

        const pdfPath = result.pdf_path || result.md_path;
        if (pdfPath) {
            const filename = pdfPath.split('/').pop().split('\\').pop();
            document.getElementById('downloadPdfBtn').href = `${API_BASE}/api/download/${encodeURIComponent(filename)}`;

            // Store for potential auto-apply
            window._lastTailoredPdf = pdfPath;
        }

        showToast('Resume tailored successfully!', 'success');

        // Refresh resume list
        loadResumes();
    } else if (result.type === 'full') {
        showToast(result.message || 'Pipeline completed!', 'success');
        loadResumes();
    } else if (!result.success) {
        showToast(result.error || 'Pipeline failed', 'error');
    }
}

// ===== RESUME PICKER =====
async function loadResumes() {
    try {
        const res = await fetch(`${API_BASE}/api/resumes`);
        const files = await res.json();
        const select = document.getElementById('resumeSelect');

        if (!files || files.length === 0) {
            select.innerHTML = '<option value="">-- No resumes yet --</option>';
            return;
        }

        select.innerHTML = '<option value="">-- Select a resume --</option>';
        files.forEach(f => {
            const icon = f.is_pdf ? '\uD83D\uDCC4' : '\uD83D\uDCDD';
            const opt = document.createElement('option');
            opt.value = f.path;
            opt.textContent = `${icon} ${f.filename} (${f.size_kb} KB)`;
            select.appendChild(opt);
        });
    } catch (err) {
        document.getElementById('resumeSelect').innerHTML = '<option value="">-- Error loading --</option>';
    }
}

// ===== AUTO-APPLY =====
async function startAutoApply() {
    const resumePath = document.getElementById('resumeSelect').value;
    const applyUrl = document.getElementById('applyUrlInput').value.trim();

    if (!resumePath) {
        showToast('Please select a resume first', 'error');
        return;
    }
    if (!applyUrl) {
        showToast('Please enter the application URL', 'error');
        return;
    }

    const btn = document.getElementById('startApplyBtn');
    btn.disabled = true;

    document.getElementById('applyStatusSection').classList.remove('hidden');
    document.getElementById('applyConfirmSection').classList.add('hidden');
    document.getElementById('applyScreenshot').classList.add('hidden');
    updateApplyBadge('Running');
    document.getElementById('applyMessage').textContent = 'Starting auto-apply...';

    try {
        const res = await fetch(`${API_BASE}/api/apply`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ application_url: applyUrl, resume_pdf_path: resumePath })
        });

        const data = await res.json();
        if (res.ok) {
            showToast('Auto-apply started', 'info');
            startApplyPolling();
        } else {
            showToast(data.detail || 'Failed to start', 'error');
            btn.disabled = false;
        }
    } catch (err) {
        showToast('Failed to start auto-apply', 'error');
        btn.disabled = false;
    }
}

function startApplyPolling() {
    if (applyPollInterval) clearInterval(applyPollInterval);
    applyPollInterval = setInterval(pollApplyStatus, 2000);
}

function stopApplyPolling() {
    if (applyPollInterval) { clearInterval(applyPollInterval); applyPollInterval = null; }
}

async function pollApplyStatus() {
    try {
        const res = await fetch(`${API_BASE}/api/apply/status`);
        const data = await res.json();

        updateApplyBadge(data.status);
        document.getElementById('applyMessage').textContent = data.message || '';

        if (data.screenshots && data.screenshots.length > 0) {
            const lastShot = data.screenshots[data.screenshots.length - 1];
            const filename = lastShot.split('/').pop().split('\\').pop();
            document.getElementById('applyScreenshotImg').src = `${API_BASE}/api/apply/screenshot/${filename}`;
            document.getElementById('applyScreenshot').classList.remove('hidden');
        }

        if (data.status === 'waiting_approval') {
            stopApplyPolling();
            document.getElementById('applyConfirmSection').classList.remove('hidden');
            showToast('Review the form and confirm', 'info');
        } else if (data.status === 'completed') {
            stopApplyPolling();
            document.getElementById('startApplyBtn').disabled = false;
            showToast('Application submitted!', 'success');
        } else if (data.status === 'failed') {
            stopApplyPolling();
            document.getElementById('startApplyBtn').disabled = false;
            showToast(data.error || 'Auto-apply failed', 'error');
        }
    } catch (err) { /* silent */ }
}

function updateApplyBadge(status) {
    const badge = document.getElementById('applyStatusBadge');
    const label = status.replace('_', ' ');
    badge.textContent = label.charAt(0).toUpperCase() + label.slice(1);
    badge.className = 'status-badge';
    if (status === 'completed') badge.classList.add('completed');
    else if (status === 'failed') badge.classList.add('failed');
}

async function confirmApply() {
    const btn = document.getElementById('confirmSubmitBtn');
    btn.disabled = true;
    btn.textContent = 'Submitting...';

    try {
        const res = await fetch(`${API_BASE}/api/apply/confirm`, { method: 'POST' });
        if (res.ok) {
            showToast('Submitting application...', 'info');
            document.getElementById('applyConfirmSection').classList.add('hidden');
            startApplyPolling();
        } else {
            const data = await res.json();
            showToast(data.detail || 'Failed to confirm', 'error');
            btn.disabled = false;
            btn.textContent = '\u2705 Confirm & Submit';
        }
    } catch (err) {
        showToast('Failed to confirm', 'error');
        btn.disabled = false;
        btn.textContent = '\u2705 Confirm & Submit';
    }
}

function cancelApply() {
    stopApplyPolling();
    document.getElementById('applyStatusSection').classList.add('hidden');
    document.getElementById('startApplyBtn').disabled = false;
    showToast('Auto-apply cancelled', 'info');
}

// ===== RUN HISTORY =====
async function loadRuns() {
    try {
        const res = await fetch(`${API_BASE}/api/runs`);
        const runs = await res.json();
        renderRuns(runs);
    } catch (err) { /* silent */ }
}

function renderRuns(runs) {
    const container = document.getElementById('runsContainer');
    if (!runs || runs.length === 0) {
        container.innerHTML = '<p class="empty-state">No runs yet.</p>';
        return;
    }

    container.innerHTML = runs.slice(0, 15).map(run => {
        const time = run.started_at ? new Date(run.started_at).toLocaleString() : 'Unknown';
        const task = run.task || 'Pipeline Run';
        const status = run.status || 'unknown';

        return `
            <div class="run-item">
                <div class="run-item-left">
                    <span class="run-item-task">${escapeHtml(task)}</span>
                    <span class="run-item-time">${escapeHtml(time)}</span>
                </div>
                <span class="run-item-status ${status}">${status}</span>
            </div>
        `;
    }).join('');
}

// ===== UTILS =====
function clearLogs() {
    document.getElementById('logsContainer').innerHTML = '<p class="empty-state">Logs cleared.</p>';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('removing');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}
