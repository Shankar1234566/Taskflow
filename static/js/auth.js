/**
 * Taskflow Authentication Module
 * Manages user session, login, logout, profile data, and role personas.
 */

const TaskflowAuth = {
  currentUser: null,

  async getCurrentUser() {
    try {
      const res = await fetch('/api/auth/me');
      if (!res.ok) {
        this.currentUser = null;
        return null;
      }
      const data = await res.json();
      this.currentUser = data.user;
      return this.currentUser;
    } catch (err) {
      console.error('Failed to get current user:', err);
      this.currentUser = null;
      return null;
    }
  },

  async login(email, password) {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || 'Login failed.');
    }
    this.currentUser = data.user;
    return data.user;
  },

  async logout() {
    try {
      await fetch('/api/auth/logout', { method: 'POST' });
    } catch (err) {
      console.error('Logout error:', err);
    }
    this.currentUser = null;
    window.location.href = '/login';
  },

  async demoLogin(roleEmail) {
    return this.login(roleEmail, 'password123');
  },

  getGreeting() {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  },

  updateTopBar(user) {
    if (!user) return;
    const greetingEl = document.getElementById('user-greeting');
    if (greetingEl) {
      greetingEl.textContent = `${this.getGreeting()}, ${user.username || user.name}`;
    }

    const roleBadgeEl = document.getElementById('user-role-badge');
    if (roleBadgeEl) {
      const teamLabel = user.team_name ? ` • ${user.team_name}` : '';
      roleBadgeEl.textContent = `${user.role || 'Member'}${teamLabel}`;
      roleBadgeEl.className = `role-badge role-${user.role || 'Member'}`;
    }

    const avatarEl = document.getElementById('user-avatar');
    if (avatarEl) {
      const initials = (user.username || user.name || 'U').substring(0, 2).toUpperCase();
      avatarEl.textContent = initials;
      avatarEl.title = `${user.username || user.name} (${user.email})`;
    }

    // Role-dependent UI visibility
    const isLeadOrAdmin = user.role === 'Admin' || user.role === 'Lead' || user.is_admin;
    const isAdmin = user.role === 'Admin' || user.is_admin;

    // Show/hide "+ Add Task" button if role allows
    const addTaskBtn = document.getElementById('btn-add-task');
    if (addTaskBtn) {
      addTaskBtn.style.display = isLeadOrAdmin ? 'inline-flex' : 'none';
    }

    // Show/hide Lead Review nav badge/item
    const navReview = document.getElementById('nav-review');
    if (navReview) {
      navReview.hidden = !isLeadOrAdmin;
    }

    // Show/hide Admin portal nav
    const navAdmin = document.getElementById('nav-admin');
    if (navAdmin) {
      navAdmin.hidden = !isAdmin;
    }

    // Team selector dropdown for Admin
    const teamFilterWrap = document.getElementById('admin-team-selector-wrap');
    if (teamFilterWrap) {
      teamFilterWrap.style.display = isAdmin ? 'block' : 'none';
    }
  }
};

window.TaskflowAuth = TaskflowAuth;
