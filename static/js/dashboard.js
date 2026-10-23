/**
 * Taskflow Dashboard & Widgets Module
 * Controls metric summaries, SVG donut chart, mini calendar, and navigation tabs.
 */

const TaskflowDashboard = {
  activeView: 'overview',
  statsData: null,

  async fetchStats(teamId = null) {
    try {
      const url = teamId ? `/api/dashboard/stats?team_id=${teamId}` : '/api/dashboard/stats';
      const res = await fetch(url);
      if (!res.ok) return null;
      const data = await res.json();
      this.statsData = data;
      this.renderMetrics(data);
      this.renderDonutChart(data);
      return data;
    } catch (err) {
      console.error('Failed to fetch stats:', err);
      return null;
    }
  },

  renderMetrics(stats) {
    if (!stats) return;

    const totalEl = document.getElementById('stat-total');
    const inProgEl = document.getElementById('stat-in-progress');
    const compEl = document.getElementById('stat-completed');
    const overdueEl = document.getElementById('stat-overdue');

    if (totalEl) totalEl.textContent = stats.total ?? 0;
    if (inProgEl) inProgEl.textContent = stats.in_progress ?? 0;
    if (compEl) compEl.textContent = stats.completed ?? 0;
    if (overdueEl) overdueEl.textContent = stats.overdue ?? 0;

    // Sidebar counter badges
    const badgeTotal = document.getElementById('badge-total');
    if (badgeTotal) badgeTotal.textContent = stats.total ?? 0;

    const badgeReview = document.getElementById('badge-review');
    if (badgeReview) badgeReview.textContent = stats.in_review ?? 0;
  },

  renderDonutChart(stats) {
    const total = stats?.total || 0;
    const completed = stats?.completed || 0;
    const inProgress = stats?.in_progress || 0;
    const inReview = stats?.in_review || 0;
    const overdue = stats?.overdue || 0;
    const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;

    const pctEl = document.getElementById('donut-percentage');
    if (pctEl) {
      pctEl.textContent = `${percentage}%`;
    }

    const circleEl = document.getElementById('donut-circle-progress');
    if (circleEl) {
      // Circumference for r=40 is ~251.32
      const circumference = 2 * Math.PI * 40;
      const offset = circumference - (percentage / 100) * circumference;
      circleEl.style.strokeDasharray = `${circumference}`;
      circleEl.style.strokeDashoffset = `${offset}`;
    }

    // Update legend values if present
    const legComp = document.getElementById('leg-completed');
    if (legComp) legComp.textContent = completed;
    const legProg = document.getElementById('leg-progress');
    if (legProg) legProg.textContent = inProgress;
    const legReview = document.getElementById('leg-review');
    if (legReview) legReview.textContent = inReview;
    const legOverdue = document.getElementById('leg-overdue');
    if (legOverdue) legOverdue.textContent = overdue;
  },

  renderMiniCalendar(tasks) {
    const calEl = document.getElementById('mini-calendar-days');
    const monthTitle = document.getElementById('mini-calendar-title');
    if (!calEl) return;

    const now = new Date();
    const year = now.getFullYear();
    const month = now.getMonth();

    const monthNames = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December'
    ];
    if (monthTitle) {
      monthTitle.textContent = `${monthNames[month]} ${year}`;
    }

    // Set of dates that have tasks due
    const taskDates = new Set();
    if (Array.isArray(tasks)) {
      tasks.forEach(t => {
        if (t.due_date) {
          const dateStr = t.due_date.substring(0, 10);
          taskDates.add(dateStr);
        }
      });
    }

    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const todayDate = now.getDate();

    let html = '';
    // Empty cells before month starts
    for (let i = 0; i < firstDay; i++) {
      html += `<div class="cal-day cal-empty"></div>`;
    }

    for (let d = 1; d <= daysInMonth; d++) {
      const isToday = d === todayDate;
      const monthStr = String(month + 1).padStart(2, '0');
      const dayStr = String(d).padStart(2, '0');
      const isoDate = `${year}-${monthStr}-${dayStr}`;
      const hasTask = taskDates.has(isoDate);

      let classes = ['cal-day'];
      if (isToday) classes.push('cal-today');
      if (hasTask) classes.push('cal-has-task');

      html += `
        <div class="${classes.join(' ')}" data-date="${isoDate}" title="${hasTask ? 'Deliverable deadline' : ''}">
          <span>${d}</span>
          ${hasTask ? '<span class="cal-dot"></span>' : ''}
        </div>
      `;
    }

    calEl.innerHTML = html;

    // Click handler on calendar day to filter tasks
    calEl.querySelectorAll('.cal-day[data-date]').forEach(day => {
      day.addEventListener('click', () => {
        const date = day.getAttribute('data-date');
        calEl.querySelectorAll('.cal-day').forEach(el => el.classList.remove('cal-selected'));
        day.classList.add('cal-selected');
        if (window.TaskflowTasks) {
          window.TaskflowTasks.filterByDate(date);
        }
      });
    });
  },

  initTabs() {
    const navLinks = document.querySelectorAll('.sidebar nav a[data-target]');
    navLinks.forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const target = link.getAttribute('data-target');
        this.switchView(target);
      });
    });
  },

  switchView(viewName) {
    this.activeView = viewName;

    // Update active nav link
    document.querySelectorAll('.sidebar nav a').forEach(a => {
      if (a.getAttribute('data-target') === viewName) {
        a.classList.add('active');
        a.setAttribute('aria-current', 'page');
      } else {
        a.classList.remove('active');
        a.removeAttribute('aria-current');
      }
    });

    // Toggle main view sections
    document.querySelectorAll('[data-view]').forEach(sec => {
      sec.hidden = sec.getAttribute('data-view') !== viewName;
    });

    // Update shell attribute for sidebar/right layout
    const shell = document.getElementById('app-shell');
    if (shell) {
      shell.setAttribute('data-active-view', viewName);
    }

    // View specific initialization
    if (viewName === 'overview' || viewName === 'my-tasks') {
      if (window.TaskflowTasks) {
        window.TaskflowTasks.applyFilters();
      }
    } else if (viewName === 'review-pipeline') {
      if (window.TaskflowTasks) {
        window.TaskflowTasks.renderReviewPipeline();
      }
    } else if (viewName === 'categories') {
      this.renderCategoriesView();
    } else if (viewName === 'team') {
      this.renderTeamView();
    } else if (viewName === 'calendar') {
      this.renderFullCalendarView();
    } else if (viewName === 'settings') {
      this.renderSettingsView();
    } else if (viewName === 'chat') {
      if (window.TaskflowChat) {
        window.TaskflowChat.loadChannels();
      }
    } else if (viewName === 'attendance') {
      if (window.TaskflowAttendance) {
        window.TaskflowAttendance.fetchTodayStatus();
        window.TaskflowAttendance.fetchLeaves();
        window.TaskflowAttendance.fetchPresenceMap();
      }
    }
  },

  renderCategoriesView() {
    const container = document.getElementById('categories-container');
    if (!container || !window.TaskflowTasks) return;

    const tasks = window.TaskflowTasks.allTasks || [];
    const catMap = {};

    tasks.forEach(t => {
      const cat = t.category || 'General';
      if (!catMap[cat]) catMap[cat] = { total: 0, completed: 0, inReview: 0, inProgress: 0 };
      catMap[cat].total++;
      if (t.completed || t.status === 'Completed') catMap[cat].completed++;
      else if (t.status === 'In Review') catMap[cat].inReview++;
      else catMap[cat].inProgress++;
    });

    let html = '';
    Object.keys(catMap).sort().forEach(cat => {
      const data = catMap[cat];
      const pct = data.total > 0 ? Math.round((data.completed / data.total) * 100) : 0;
      html += `
        <div class="cat-card">
          <div class="flex-between">
            <span class="pill c-${cat}">${cat}</span>
            <span class="text-sm font-semibold">${data.completed}/${data.total} Closed</span>
          </div>
          <div class="cat-bar-wrap">
            <div class="cat-bar" style="width: ${pct}%"></div>
          </div>
          <div class="cat-stats">
            <span>${pct}% Completed</span>
            <span>${data.inProgress} In Flight</span>
          </div>
        </div>
      `;
    });

    container.innerHTML = html || '<p class="empty">No category data available.</p>';
  },

  async renderTeamView() {
    const container = document.getElementById('team-members-container');
    if (!container) return;

    try {
      const res = await fetch('/api/teams/members');
      if (!res.ok) return;
      const data = await res.json();
      const members = data.members || [];

      let html = '';
      members.forEach(m => {
        const initials = (m.username || m.name || 'M').substring(0, 2).toUpperCase();
        html += `
          <div class="card member-card">
            <div class="member-head">
              <div class="avatar">${initials}</div>
              <div>
                <h4 style="margin: 0; font-size: 15px;">${m.username || m.name}</h4>
                <span class="text-sm text-muted">${m.email}</span>
              </div>
              <span class="role-badge role-${m.role}" style="margin-left: auto;">${m.role}</span>
            </div>
            <div class="member-meta" style="margin-top: 12px; font-size: 13px; color: var(--color-text-muted);">
              <span>Squad: <b>${m.team_name || 'Unassigned'}</b></span>
            </div>
          </div>
        `;
      });
      container.innerHTML = html || '<p class="empty">No team members found.</p>';
    } catch (err) {
      console.error('Failed to load team view:', err);
    }
  },

  fullCalDate: new Date(),

  initCalendarControls() {
    const prevBtn = document.getElementById('btn-cal-prev');
    const nextBtn = document.getElementById('btn-cal-next');
    const todayBtn = document.getElementById('btn-cal-today');

    if (prevBtn && !prevBtn._bound) {
      prevBtn._bound = true;
      prevBtn.addEventListener('click', () => {
        this.fullCalDate.setMonth(this.fullCalDate.getMonth() - 1);
        this.renderFullCalendarView();
      });
    }

    if (nextBtn && !nextBtn._bound) {
      nextBtn._bound = true;
      nextBtn.addEventListener('click', () => {
        this.fullCalDate.setMonth(this.fullCalDate.getMonth() + 1);
        this.renderFullCalendarView();
      });
    }

    if (todayBtn && !todayBtn._bound) {
      todayBtn._bound = true;
      todayBtn.addEventListener('click', () => {
        this.fullCalDate = new Date();
        this.renderFullCalendarView();
      });
    }
  },

  renderFullCalendarView() {
    this.initCalendarControls();
    const container = document.getElementById('calendar-full-view');
    const titleEl = document.getElementById('full-calendar-month-title');
    if (!container) return;

    const currentYear = this.fullCalDate.getFullYear();
    const currentMonth = this.fullCalDate.getMonth();

    const monthNames = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December'
    ];
    if (titleEl) {
      titleEl.textContent = `${monthNames[currentMonth]} ${currentYear}`;
    }

    const tasks = window.TaskflowTasks?.allTasks || [];

    // Group tasks by ISO date YYYY-MM-DD
    const tasksByDate = {};
    tasks.forEach(t => {
      if (t.due_date) {
        const d = t.due_date.substring(0, 10);
        if (!tasksByDate[d]) tasksByDate[d] = [];
        tasksByDate[d].push(t);
      }
    });

    const firstDayIndex = new Date(currentYear, currentMonth, 1).getDay(); // 0 is Sunday
    const daysInCurrentMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
    const daysInPrevMonth = new Date(currentYear, currentMonth, 0).getDate();

    const todayIso = new Date().toISOString().substring(0, 10);

    let html = '';

    // Previous month padding days
    for (let i = firstDayIndex - 1; i >= 0; i--) {
      const dayNum = daysInPrevMonth - i;
      html += `
        <div class="full-cal-day other-month">
          <div class="full-cal-day-head">
            <span class="full-cal-date-num">${dayNum}</span>
          </div>
        </div>
      `;
    }

    // Current month days
    for (let d = 1; d <= daysInCurrentMonth; d++) {
      const monthStr = String(currentMonth + 1).padStart(2, '0');
      const dayStr = String(d).padStart(2, '0');
      const isoDate = `${currentYear}-${monthStr}-${dayStr}`;
      const dayTasks = tasksByDate[isoDate] || [];
      const isToday = isoDate === todayIso;

      let tasksHtml = '';
      dayTasks.forEach(task => {
        const priorityClass = `p-${task.priority || 'Medium'}`;
        const escapedTitle = (task.title || '').replace(/"/g, '&quot;');
        tasksHtml += `
          <div class="full-cal-task-pill ${priorityClass}" onclick="event.stopPropagation(); window.TaskflowTasks.viewTaskDetail(${task.id})" title="${escapedTitle} (${task.priority})">
            <span>●</span>
            <span style="overflow: hidden; text-overflow: ellipsis;">${task.title}</span>
          </div>
        `;
      });

      html += `
        <div class="full-cal-day ${isToday ? 'today' : ''}" onclick="window.TaskflowDashboard.onCalendarDayClick('${isoDate}')" title="Click to filter overview by ${isoDate}">
          <div class="full-cal-day-head">
            <span class="full-cal-date-num">${d}</span>
            ${dayTasks.length > 0 ? `<span class="full-cal-count-badge">${dayTasks.length} due</span>` : ''}
          </div>
          <div class="full-cal-tasks">
            ${tasksHtml}
          </div>
        </div>
      `;
    }

    // Next month padding days to complete 7-column grid rows
    const totalRendered = firstDayIndex + daysInCurrentMonth;
    const remaining = (7 - (totalRendered % 7)) % 7;
    for (let d = 1; d <= remaining; d++) {
      html += `
        <div class="full-cal-day other-month">
          <div class="full-cal-day-head">
            <span class="full-cal-date-num">${d}</span>
          </div>
        </div>
      `;
    }

    container.innerHTML = html;
  },

  onCalendarDayClick(isoDate) {
    if (window.TaskflowTasks) {
      window.TaskflowTasks.filterByDate(isoDate);
      this.switchView('overview');
    }
  },

  async renderSettingsView() {
    let user = window.TaskflowAuth?.currentUser;
    if (!user) {
      user = await window.TaskflowAuth?.getCurrentUser();
    }
    if (!user) return;

    const nameInput = document.getElementById('settings-name');
    const emailInput = document.getElementById('settings-email');
    const themeSelect = document.getElementById('settings-theme');
    const displayName = document.getElementById('settings-display-name');
    const roleBadge = document.getElementById('settings-role-badge');
    const teamBadge = document.getElementById('settings-team-badge');
    const squadDisplay = document.getElementById('settings-squad-display');
    const avatarPreview = document.getElementById('settings-avatar-preview');

    const nameVal = user.name || user.username || '';
    if (nameInput) nameInput.value = nameVal;
    if (emailInput) emailInput.value = user.email || '';
    if (themeSelect) themeSelect.value = user.theme_preference || 'light';
    if (displayName) displayName.textContent = nameVal;
    if (roleBadge) {
      roleBadge.textContent = user.role || 'Member';
      roleBadge.className = `role-badge role-${user.role || 'Member'}`;
    }
    if (teamBadge) teamBadge.textContent = user.team_name ? `Squad: ${user.team_name}` : 'Unassigned Squad';
    if (squadDisplay) squadDisplay.value = user.team_name || 'Unassigned Squad';
    if (avatarPreview) {
      avatarPreview.textContent = (nameVal || 'U').substring(0, 2).toUpperCase();
    }
  },

  async saveSettings() {
    const nameInput = document.getElementById('settings-name');
    const themeSelect = document.getElementById('settings-theme');
    const statusMsg = document.getElementById('settings-status-msg');
    const saveBtn = document.getElementById('btn-save-settings');

    const newName = nameInput?.value.trim();
    const newTheme = themeSelect?.value || 'light';

    if (!newName) {
      alert('Full name cannot be blank.');
      return;
    }

    if (saveBtn) saveBtn.disabled = true;

    try {
      const res = await fetch('/api/auth/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newName,
          theme_preference: newTheme
        })
      });

      const data = await res.json();
      if (!res.ok) {
        alert(data.error || 'Failed to update preferences.');
        return;
      }

      // Update current user cache
      const updatedUser = data.user || {};
      if (window.TaskflowAuth) {
        window.TaskflowAuth.currentUser = updatedUser;
        window.TaskflowAuth.updateTopBar(updatedUser);
      }

      // Apply theme to document
      document.documentElement.setAttribute('data-theme', newTheme);
      localStorage.setItem('taskflow_theme', newTheme);

      // Refresh settings profile header
      this.renderSettingsView();

      if (statusMsg) {
        statusMsg.style.display = 'inline';
        statusMsg.style.color = 'var(--color-brand-primary)';
        statusMsg.textContent = 'Preferences saved successfully!';
        setTimeout(() => {
          statusMsg.style.display = 'none';
        }, 3000);
      }
    } catch (err) {
      console.error('Failed to save preferences:', err);
      alert('Network error while saving preferences.');
    } finally {
      if (saveBtn) saveBtn.disabled = false;
    }
  },

  async changePassword() {
    const curPw = document.getElementById('settings-current-password');
    const newPw = document.getElementById('settings-new-password');
    const msgEl = document.getElementById('password-status-msg');

    if (!curPw?.value || !newPw?.value) {
      alert('Please fill out both password fields.');
      return;
    }

    try {
      const res = await fetch('/api/auth/password', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          current_password: curPw.value,
          new_password: newPw.value
        })
      });

      const data = await res.json();
      if (!res.ok) {
        if (msgEl) {
          msgEl.style.display = 'inline';
          msgEl.style.color = 'var(--color-error-solid)';
          msgEl.textContent = data.error || 'Failed to update password.';
        }
        return;
      }

      curPw.value = '';
      newPw.value = '';
      if (msgEl) {
        msgEl.style.display = 'inline';
        msgEl.style.color = 'var(--color-brand-primary)';
        msgEl.textContent = 'Password updated successfully!';
        setTimeout(() => {
          msgEl.style.display = 'none';
        }, 3000);
      }
    } catch (err) {
      console.error('Error changing password:', err);
    }
  }
};

window.TaskflowDashboard = TaskflowDashboard;
