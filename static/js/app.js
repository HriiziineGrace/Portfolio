/**
 * Government Job Deadline Guardian - Core Application Logic
 * Handles real-time countdown tickers, dark mode, reminder modals,
 * instant email simulations, and security link verification.
 */

document.addEventListener('DOMContentLoaded', () => {
  initThemeToggle();
  initLiveCountdownTimers();
  initReminderModal();
  initQuickEligibilityModal();
});

/* ----------------- THEME TOGGLE ----------------- */
function initThemeToggle() {
  const toggleBtn = document.getElementById('theme-toggle-btn');
  const storedTheme = localStorage.getItem('gov_job_theme') || 'light';
  
  if (storedTheme === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
    if (toggleBtn) toggleBtn.innerHTML = '☀️';
  } else {
    document.documentElement.removeAttribute('data-theme');
    if (toggleBtn) toggleBtn.innerHTML = '🌙';
  }

  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
      if (isDark) {
        document.documentElement.removeAttribute('data-theme');
        localStorage.setItem('gov_job_theme', 'light');
        toggleBtn.innerHTML = '🌙';
        showToast('Switched to Light Mode');
      } else {
        document.documentElement.setAttribute('data-theme', 'dark');
        localStorage.setItem('gov_job_theme', 'dark');
        toggleBtn.innerHTML = '☀️';
        showToast('Switched to Dark Mode');
      }
    });
  }
}

/* ----------------- LIVE COUNTDOWN TIMERS ----------------- */
function initLiveCountdownTimers() {
  const timerElements = document.querySelectorAll('[data-deadline]');
  if (!timerElements.length) return;

  function updateAllTimers() {
    // Anchor to 2026-10-20 system time plus elapsed real seconds
    const now = new Date();
    // Use data attribute if present or calculate from timestamp
    timerElements.forEach(el => {
      const deadlineStr = el.getAttribute('data-deadline');
      if (!deadlineStr) return;

      const deadline = new Date(deadlineStr.replace(' ', 'T'));
      const diffMs = deadline - now;

      if (diffMs <= 0) {
        el.textContent = 'Application Closed';
        el.classList.remove('timer-critical');
        el.classList.add('timer-closed');
        return;
      }

      const totalSeconds = Math.floor(diffMs / 1000);
      const days = Math.floor(totalSeconds / 86400);
      const hours = Math.floor((totalSeconds % 86400) / 3600);
      const minutes = Math.floor((totalSeconds % 3600) / 60);
      const seconds = totalSeconds % 60;

      if (days > 3) {
        el.textContent = `${days}d ${hours}h ${minutes}m left`;
      } else if (days > 0) {
        el.textContent = `${days}d ${hours}h ${minutes}m ${seconds}s`;
        el.classList.add('timer-critical');
      } else {
        el.textContent = `${hours}h ${minutes}m ${seconds}s`;
        el.classList.add('timer-critical');
      }
    });
  }

  updateAllTimers();
  setInterval(updateAllTimers, 1000);
}

/* ----------------- TOAST HELPER ----------------- */
function showToast(message, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>ℹ️</span> <div>${message}</div>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

/* ----------------- REMINDER & INSTANT ALERT MODAL ----------------- */
function initReminderModal() {
  const modal = document.getElementById('reminder-modal');
  if (!modal) return;

  const closeBtns = modal.querySelectorAll('[data-close-modal]');
  closeBtns.forEach(b => b.addEventListener('click', () => modal.classList.remove('active')));

  const reminderForm = document.getElementById('reminder-form');
  const btnInstantAlert = document.getElementById('btn-send-instant-alert');

  // Open modal handler
  document.addEventListener('click', (e) => {
    const trigger = e.target.closest('[data-open-reminder]');
    if (!trigger) return;

    const jobId = trigger.getAttribute('data-job-id');
    const jobTitle = trigger.getAttribute('data-job-title');
    const jobDeadline = trigger.getAttribute('data-job-deadline');

    document.getElementById('modal-job-id').value = jobId;
    document.getElementById('modal-job-title-display').textContent = jobTitle;
    document.getElementById('modal-job-deadline-display').textContent = jobDeadline;
    
    // Clear preview box
    const previewContainer = document.getElementById('email-preview-container');
    if (previewContainer) {
      previewContainer.style.display = 'none';
      previewContainer.innerHTML = '';
    }

    modal.classList.add('active');
  });

  // Subscribe submit handler
  if (reminderForm) {
    reminderForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = document.getElementById('reminder-email').value;
      const jobId = document.getElementById('modal-job-id').value;
      const days = document.getElementById('reminder-days').value;

      try {
        const res = await fetch('/api/subscribe-reminder', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, job_id: jobId, notify_before_days: days })
        });
        const data = await res.json();
        if (data.success) {
          showToast(data.message, 'success');
          modal.classList.remove('active');
        } else {
          showToast(data.error || 'Failed to save subscription', 'error');
        }
      } catch (err) {
        showToast('Network error while saving reminder.', 'error');
      }
    });
  }

  // Instant Alert Test trigger
  if (btnInstantAlert) {
    btnInstantAlert.addEventListener('click', async () => {
      const email = document.getElementById('reminder-email').value || 'aspirant@nic.in';
      const jobId = document.getElementById('modal-job-id').value;
      btnInstantAlert.disabled = true;
      btnInstantAlert.textContent = 'Generating Alert Preview...';

      try {
        const res = await fetch('/api/send-instant-alert', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, job_id: jobId })
        });
        const data = await res.json();
        if (data.success) {
          showToast('Live email preview generated!', 'success');
          const previewContainer = document.getElementById('email-preview-container');
          if (previewContainer) {
            previewContainer.style.display = 'block';
            previewContainer.innerHTML = `
              <div style="background: var(--bg-primary); padding: 10px; border-radius: 8px; margin-top: 15px; border: 1px dashed var(--border-color);">
                <div style="font-size: 0.8rem; font-weight: 700; color: var(--open); margin-bottom: 6px;">
                  ✓ Simulated Dispatch Successful to: ${data.recipient}
                </div>
                <iframe srcdoc="${data.html_preview.replace(/"/g, '&quot;')}" style="width: 100%; height: 380px; border: none; border-radius: 6px; background: white;"></iframe>
              </div>
            `;
          }
        }
      } catch (err) {
        showToast('Failed to trigger alert simulation.', 'error');
      } finally {
        btnInstantAlert.disabled = false;
        btnInstantAlert.textContent = '⚡ Test Instant Email Alert Preview';
      }
    });
  }
}

/* ----------------- QUICK ELIGIBILITY MODAL ----------------- */
function initQuickEligibilityModal() {
  const modal = document.getElementById('eligibility-quick-modal');
  if (!modal) return;

  const closeBtns = modal.querySelectorAll('[data-close-modal]');
  closeBtns.forEach(b => b.addEventListener('click', () => modal.classList.remove('active')));

  document.addEventListener('click', (e) => {
    const trigger = e.target.closest('[data-check-eligibility]');
    if (!trigger) return;

    const jobId = trigger.getAttribute('data-job-id');
    const jobTitle = trigger.getAttribute('data-job-title');
    const minAge = trigger.getAttribute('data-min-age');
    const maxAge = trigger.getAttribute('data-max-age');
    const minQual = trigger.getAttribute('data-min-qual');

    document.getElementById('quick-job-id').value = jobId;
    document.getElementById('quick-job-title').textContent = jobTitle;
    document.getElementById('quick-job-reqs').textContent = `Age: ${minAge} - ${maxAge} yrs | Min Qual: ${minQual}`;

    const resArea = document.getElementById('quick-eligibility-result');
    if (resArea) {
      resArea.style.display = 'none';
      resArea.innerHTML = '';
    }

    modal.classList.add('active');
  });

  const form = document.getElementById('quick-eligibility-form');
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const jobId = document.getElementById('quick-job-id').value;
      const dob = document.getElementById('quick-dob').value;
      const category = document.getElementById('quick-category').value;
      const qualification = document.getElementById('quick-qualification').value;
      const stream = document.getElementById('quick-stream').value;

      try {
        const res = await fetch('/api/check-eligibility', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ job_id: jobId, dob, category, qualification, stream })
        });
        const data = await res.json();
        if (data.success && data.results && data.results.length > 0) {
          const evalRes = data.results[0].eligibility;
          renderQuickResult(evalRes);
        } else {
          showToast(data.error || 'Evaluation error', 'error');
        }
      } catch (err) {
        showToast('Error checking eligibility.', 'error');
      }
    });
  }
}

function renderQuickResult(evalRes) {
  const resArea = document.getElementById('quick-eligibility-result');
  if (!resArea) return;

  resArea.style.display = 'block';
  const isOk = evalRes.eligible;

  let badge = isOk ? 
    `<span style="background: var(--open); color: white; padding: 4px 10px; border-radius: 20px; font-weight: 700;">✓ ELIGIBLE TO APPLY</span>` :
    `<span style="background: var(--critical); color: white; padding: 4px 10px; border-radius: 20px; font-weight: 700;">✕ NOT ELIGIBLE</span>`;

  let reasonsHtml = evalRes.reasons.map(r => `<li>${r}</li>`).join('');

  resArea.innerHTML = `
    <div style="background: ${isOk ? 'var(--open-bg)' : 'var(--critical-bg)'}; border: 1px solid ${isOk ? 'var(--open-border)' : 'var(--critical-border)'}; border-radius: 8px; padding: 14px; margin-top: 14px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
        <span style="font-weight: 700; color: ${isOk ? 'var(--open)' : 'var(--critical)'};">${evalRes.summary}</span>
        ${badge}
      </div>
      <div style="font-size: 0.84rem; color: var(--text-main); margin-bottom: 8px;">
        <strong>Calculated Age:</strong> ${evalRes.candidate_age_formatted} | <strong>Max Allowed Limit (with ${evalRes.category} relaxation):</strong> ${evalRes.effective_max_age} yrs
      </div>
      <ul style="font-size: 0.82rem; padding-left: 20px; color: var(--text-muted); line-height: 1.5;">
        ${reasonsHtml}
      </ul>
    </div>
  `;
}
