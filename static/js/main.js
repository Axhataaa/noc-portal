/* ============================================================
   NOC Portal — Main JavaScript
   ============================================================ */

// ── Theme System ──
const THEME_KEY = 'noc-theme';

function getTheme() {
  return localStorage.getItem(THEME_KEY) || 'dark';
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem(THEME_KEY, theme);

  const icon = document.getElementById('themeIcon');
  if (icon) {
    icon.innerHTML = theme === 'dark'
      ? `<path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>`
      : `<circle cx="12" cy="12" r="5" stroke="currentColor" stroke-width="2"/>
         <line x1="12" y1="1" x2="12" y2="3" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
         <line x1="12" y1="21" x2="12" y2="23" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
         <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
         <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
         <line x1="1" y1="12" x2="3" y2="12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
         <line x1="21" y1="12" x2="23" y2="12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>`;
  }
}

function toggleTheme() {
  const current = getTheme();
  applyTheme(current === 'dark' ? 'light' : 'dark');
}

// Initialize theme immediately (avoid flash)
(function () {
  applyTheme(getTheme());
})();

// ── Sidebar Toggle ──
function openSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  if (sidebar) sidebar.classList.add('open');
  if (overlay) overlay.classList.add('visible');
  document.body.style.overflow = 'hidden';
}

function closeSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  if (sidebar) sidebar.classList.remove('open');
  if (overlay) overlay.classList.remove('visible');
  document.body.style.overflow = '';
}

function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  if (sidebar && sidebar.classList.contains('open')) {
    closeSidebar();
  } else {
    openSidebar();
  }
}

// Close sidebar on outside click (mobile) — handled by overlay now

// ── Modal System ──
function openModal(title, body, footer) {
  document.getElementById('modalTitle').innerHTML = title || '';
  document.getElementById('modalBody').innerHTML = body || '';
  document.getElementById('modalFooter').innerHTML = footer || '';
  document.getElementById('modalOverlay').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  document.getElementById('modalOverlay').classList.remove('open');
  document.body.style.overflow = '';
}

// Close modal on Escape key
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') closeModal();
});

// ── Password Toggle ──
function togglePassword(inputId) {
  const input = document.getElementById(inputId);
  if (input) {
    input.type = input.type === 'password' ? 'text' : 'password';
  }
}

// ── Auto-dismiss Flash Messages ──
function autoDismissFlash() {
  const flashes = document.querySelectorAll('.flash');
  flashes.forEach((flash, i) => {
    setTimeout(() => {
      flash.style.transition = 'all 0.4s ease';
      flash.style.opacity = '0';
      flash.style.transform = 'translateX(20px)';
      setTimeout(() => flash.remove(), 400);
    }, 4000 + i * 500);
  });
}

// ── Table Row Highlighting ──
function initTableHighlight() {
  const rows = document.querySelectorAll('.table-row');
  rows.forEach(row => {
    const status = row.dataset.status;
    if (status === 'pending') {
      row.style.setProperty('--row-accent', 'rgba(245,158,11,0.03)');
    }
  });
}

// ── Entrance Animations ──
function initAnimations() {
  const cards = document.querySelectorAll('.stat-card, .card, .feature-card');
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.animation = 'fadeInUp 0.4s ease both';
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  cards.forEach(card => observer.observe(card));
}

// Add fadeInUp animation
const style = document.createElement('style');
style.textContent = `
  @keyframes fadeInUp {
    from { opacity: 0; transform: translateY(16px); }
    to   { opacity: 1; transform: translateY(0); }
  }
`;
document.head.appendChild(style);

// ── Number Counter Animation ──
function animateCounters() {
  const counters = document.querySelectorAll('.stat-value');
  counters.forEach(counter => {
    const raw = counter.textContent.trim();
    // Extract numeric value including decimals
    const match = raw.match(/[\d.]+/);
    if (!match) return;
    const value = parseFloat(match[0]);
    if (isNaN(value) || value === 0) return;

    // Preserve suffix (%, text after number)
    const suffix = raw.replace(/^[\d.]+/, '').trim();
    const isDecimal = match[0].includes('.');
    const decimals  = isDecimal ? (match[0].split('.')[1] || '').length : 0;

    let start = 0;
    const duration = 800;
    const increment = value / (duration / (1000 / 60));

    const timer = setInterval(() => {
      start += increment;
      if (start >= value) {
        counter.textContent = value.toFixed(decimals) + (suffix ? ' ' + suffix : '');
        clearInterval(timer);
      } else {
        counter.textContent = start.toFixed(decimals) + (suffix ? ' ' + suffix : '');
      }
    }, 1000 / 60);
  });
}

// ── Search with debounce ──
function initLiveSearch() {
  const searchInput = document.querySelector('.search-input');
  if (!searchInput) return;

  let debounceTimer;
  searchInput.addEventListener('input', function () {
    clearTimeout(debounceTimer);
    const query = this.value.toLowerCase().trim();

    debounceTimer = setTimeout(() => {
      const rows = document.querySelectorAll('.table-row');
      rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = !query || text.includes(query) ? '' : 'none';
      });
    }, 200);
  });
}

// ── Form Validation Feedback ──
function initFormValidation() {
  const inputs = document.querySelectorAll('.form-input[required]');
  inputs.forEach(input => {
    input.addEventListener('blur', function () {
      if (!this.value.trim()) {
        this.style.borderColor = 'var(--color-rejected)';
      } else {
        this.style.borderColor = '';
      }
    });

    input.addEventListener('input', function () {
      if (this.value.trim()) {
        this.style.borderColor = '';
      }
    });
  });
}

// ── Topbar Scroll Effect ──
function initTopbarScroll() {
  const topbar = document.querySelector('.topbar');
  if (!topbar) return;
  window.addEventListener('scroll', () => {
    if (window.scrollY > 10) {
      topbar.style.boxShadow = 'var(--shadow-md)';
    } else {
      topbar.style.boxShadow = 'none';
    }
  }, { passive: true });
}

// ── Initialize Everything ──
document.addEventListener('DOMContentLoaded', function () {
  autoDismissFlash();
  initTableHighlight();
  initAnimations();
  animateCounters();
  initLiveSearch();
  initFormValidation();
  initTopbarScroll();
});
