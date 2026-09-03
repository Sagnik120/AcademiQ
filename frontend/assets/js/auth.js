/**
 * AcademiQ — Authentication & Route Guard Engine
 */

const Auth = {
  getCurrentUser() {
    try {
      const u = localStorage.getItem('academiq_user');
      return u ? JSON.parse(u) : null;
    } catch {
      return null;
    }
  },

  isAuthenticated() {
    return !!localStorage.getItem('academiq_access_token');
  },

  saveSession(token, user) {
    localStorage.setItem('academiq_access_token', token);
    localStorage.setItem('academiq_user', JSON.stringify(user));
  },

  clearSession() {
    localStorage.removeItem('academiq_access_token');
    localStorage.removeItem('academiq_user');
  },

  async login(email, password) {
    const data = await api.post('/auth/login', { email, password });
    this.saveSession(data.access_token, data.user);
    return data.user;
  },

  async register(registrationData) {
    const data = await api.post('/auth/register', registrationData);
    if (data.access_token && data.user) {
      this.saveSession(data.access_token, data.user);
    }
    return data;
  },

  logout() {
    this.clearSession();
    window.location.href = '/index.html';
  },

  requireAuth(allowedRoles = []) {
    if (!this.isAuthenticated()) {
      window.location.href = '/auth/learner-login.html';
      return null;
    }

    const user = this.getCurrentUser();
    if (allowedRoles.length > 0 && user && !allowedRoles.includes(user.role)) {
      alert('Access Denied: You do not have permission to view this page.');
      window.location.href = user.role === 'educator' ? '/educator/dashboard.html' : '/learner/dashboard.html';
      return null;
    }

    return user;
  },

  updateNavbarAuthUI() {
    const authNav = document.getElementById('navbar-auth-section');
    if (!authNav) return;

    const user = this.getCurrentUser();
    if (user && this.isAuthenticated()) {
      const dashboardUrl = user.role === 'educator' 
        ? '/educator/dashboard.html' 
        : (user.role === 'admin' ? '/admin/dashboard.html' : '/learner/dashboard.html');

      authNav.innerHTML = `
        <div style="display: flex; align-items: center; gap: 1rem;">
          <a href="${dashboardUrl}" class="btn btn-outline btn-sm">
            <span>Dashboard</span>
          </a>
          <div style="display: flex; align-items: center; gap: 0.5rem;">
            <span style="font-size: 0.85rem; font-weight: 600; color: var(--text-primary);">${escapeHtml(user.first_name)}</span>
            <button onclick="Auth.logout()" class="btn btn-ghost btn-sm" title="Sign Out">
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      `;
    } else {
      authNav.innerHTML = `
        <div style="display: flex; align-items: center; gap: 0.75rem;">
          <a href="/auth/learner-login.html" class="btn btn-ghost btn-sm">Sign In</a>
          <a href="/auth/learner-signup.html" class="btn btn-primary btn-sm">Get Started</a>
        </div>
      `;
    }
  }
};

document.addEventListener('DOMContentLoaded', () => {
  Auth.updateNavbarAuthUI();
});
