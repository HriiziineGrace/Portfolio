/**
 * Government Job Deadline Guardian - Dedicated Eligibility Checker
 * Interactive calculator for age relaxation and qualification matching across all postings.
 */

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('full-eligibility-form');
  const dobInput = document.getElementById('cand-dob');
  const ageDisplay = document.getElementById('live-age-display');

  // Pre-fill default sample date for quick testing if empty (e.g. 28 years old)
  if (dobInput && !dobInput.value) {
    dobInput.value = '1998-05-15';
    updateLiveAge();
  }

  if (dobInput) {
    dobInput.addEventListener('input', updateLiveAge);
  }

  function updateLiveAge() {
    if (!dobInput.value) return;
    const refDate = new Date('2026-10-20');
    const birthDate = new Date(dobInput.value);
    
    let years = refDate.getFullYear() - birthDate.getFullYear();
    let months = refDate.getMonth() - birthDate.getMonth();
    let days = refDate.getDate() - birthDate.getDate();

    if (days < 0) {
      months--;
      days += 30;
    }
    if (months < 0) {
      years--;
      months += 12;
    }

    if (ageDisplay) {
      if (years < 0) {
        ageDisplay.textContent = 'Invalid Future Date';
        ageDisplay.style.color = 'var(--critical)';
      } else {
        ageDisplay.textContent = `${years} Years, ${months} Months, ${days} Days`;
        ageDisplay.style.color = 'var(--primary)';
      }
    }
  }

  if (form) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      runEligibilityScan();
    });

    // Auto-run on initial load
    runEligibilityScan();
  }

  // Filter tabs
  const tabBtns = document.querySelectorAll('[data-eligibility-tab]');
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      filterRenderedJobs(btn.getAttribute('data-eligibility-tab'));
    });
  });
});

let currentResults = [];

async function runEligibilityScan() {
  const dob = document.getElementById('cand-dob').value;
  const category = document.getElementById('cand-category').value;
  const qualification = document.getElementById('cand-qualification').value;
  const stream = document.getElementById('cand-stream').value;

  const resultsArea = document.getElementById('eligibility-results-grid');
  const summaryBox = document.getElementById('eligibility-summary-stats');

  if (resultsArea) {
    resultsArea.innerHTML = '<div style="text-align: center; padding: 40px; grid-column: 1/-1;"><span class="spinner">⏳</span> Evaluating official eligibility criteria across all active government postings...</div>';
  }

  try {
    const res = await fetch('/api/check-eligibility', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dob, category, qualification, stream })
    });

    const data = await res.json();
    if (!data.success) {
      alert(data.error || 'Evaluation failed.');
      return;
    }

    currentResults = data.results || [];

    // Render stats
    if (summaryBox) {
      const eligibleCount = currentResults.filter(j => j.eligibility.eligible).length;
      const relaxedCount = currentResults.filter(j => j.eligibility.status_type === 'ELIGIBLE_RELAXED').length;
      const ineligibleCount = currentResults.length - eligibleCount;

      summaryBox.innerHTML = `
        <div class="stats-grid" style="margin-top: 10px;">
          <div class="stat-card" style="border-left: 4px solid var(--open);">
            <div class="stat-label">Eligible Positions</div>
            <div class="stat-value" style="color: var(--open);">${eligibleCount}</div>
            <div class="stat-meta">Matches your qualifications & age</div>
          </div>
          <div class="stat-card" style="border-left: 4px solid var(--extended);">
            <div class="stat-label">Category Relaxation Benefit</div>
            <div class="stat-value" style="color: var(--extended);">${relaxedCount}</div>
            <div class="stat-meta">Eligible due to ${category} age extension</div>
          </div>
          <div class="stat-card" style="border-left: 4px solid var(--critical);">
            <div class="stat-label">Ineligible Postings</div>
            <div class="stat-value" style="color: var(--critical);">${ineligibleCount}</div>
            <div class="stat-meta">Over-age / Under-age or qual mismatch</div>
          </div>
        </div>
      `;
    }

    renderJobsList(currentResults);
  } catch (err) {
    if (resultsArea) {
      resultsArea.innerHTML = '<div style="color: red; text-align: center; padding: 20px;">Failed to evaluate eligibility. Please check network connection.</div>';
    }
  }
}

function filterRenderedJobs(filterType) {
  if (filterType === 'all') {
    renderJobsList(currentResults);
  } else if (filterType === 'eligible') {
    renderJobsList(currentResults.filter(j => j.eligibility.eligible));
  } else if (filterType === 'relaxed') {
    renderJobsList(currentResults.filter(j => j.eligibility.status_type === 'ELIGIBLE_RELAXED'));
  } else if (filterType === 'ineligible') {
    renderJobsList(currentResults.filter(j => !j.eligibility.eligible));
  }
}

function renderJobsList(jobs) {
  const container = document.getElementById('eligibility-results-grid');
  if (!container) return;

  if (jobs.length === 0) {
    container.innerHTML = `
      <div class="empty-state-box">
        <div class="empty-icon">📂</div>
        <h3>No jobs match this filter criteria</h3>
        <p style="color: var(--text-muted); margin-top: 6px;">Try adjusting your qualification, category, or DOB above.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = jobs.map(job => {
    const el = job.eligibility;
    const isEligible = el.eligible;
    const isRelaxed = el.status_type === 'ELIGIBLE_RELAXED';

    let badgeClass = isEligible ? (isRelaxed ? 'urgency-extended' : 'urgency-open') : 'urgency-critical';
    let badgeText = isEligible ? (isRelaxed ? '🛡️ Eligible (Category Relaxed)' : '✓ Fully Eligible') : '✕ Not Eligible';

    let reasonsList = el.reasons.map(r => `<li>${r}</li>`).join('');

    return `
      <div class="job-card" style="border-top: 4px solid ${isEligible ? (isRelaxed ? 'var(--extended)' : 'var(--open)') : 'var(--critical)'};">
        <div class="job-card-top">
          <span class="dept-pill">${job.category}</span>
          <span class="urgency-badge ${badgeClass}">${badgeText}</span>
        </div>

        <a href="/job/${job.id}" class="job-title-link">${job.title}</a>
        <div class="job-org-meta">
          <span>${job.organization}</span>
          <span class="advt-tag">${job.advt_no}</span>
        </div>

        <div style="background: ${isEligible ? (isRelaxed ? 'var(--extended-bg)' : 'var(--open-bg)') : 'var(--critical-bg)'}; border-radius: 8px; padding: 12px; margin-bottom: 14px; border: 1px solid ${isEligible ? (isRelaxed ? 'var(--extended-border)' : 'var(--open-border)') : 'var(--critical-border)'};">
          <div style="font-size: 0.84rem; font-weight: 700; color: ${isEligible ? (isRelaxed ? 'var(--extended)' : 'var(--open)') : 'var(--critical)'}; margin-bottom: 6px;">
            ${el.summary}
          </div>
          <div style="font-size: 0.78rem; color: var(--text-main); margin-bottom: 6px;">
            Age Requirement: <strong>${el.min_age} - ${el.base_max_age} yrs</strong> (Max with relaxation: <strong>${el.effective_max_age} yrs</strong>)
          </div>
          <ul style="font-size: 0.78rem; padding-left: 18px; color: var(--text-muted); line-height: 1.4;">
            ${reasonsList}
          </ul>
        </div>

        <div class="job-specs-grid">
          <div class="spec-item">
            <span class="spec-title">Vacancies</span>
            <span class="spec-value">${job.vacancies.toLocaleString()}</span>
          </div>
          <div class="spec-item">
            <span class="spec-title">Required Qual</span>
            <span class="spec-value">${job.min_qualification}</span>
          </div>
          <div class="spec-item">
            <span class="spec-title">Pay Scale</span>
            <span class="spec-value">${job.salary_pay ? job.salary_pay.substring(0, 22) + '...' : 'Govt standard'}</span>
          </div>
          <div class="spec-item">
            <span class="spec-title">Deadline</span>
            <span class="spec-value" style="color: ${job.urgency === 'CRITICAL' ? 'var(--critical)' : 'inherit'};">${job.deadline.substring(0, 10)}</span>
          </div>
        </div>

        <div class="card-actions-row">
          <a href="/job/${job.id}" class="btn-primary-apply">
            View Details & Apply ↗
          </a>
          <button class="btn-secondary-action" data-open-reminder data-job-id="${job.id}" data-job-title="${job.title}" data-job-deadline="${job.deadline}">
            🔔 Reminder
          </button>
        </div>
      </div>
    `;
  }).join('');
}
