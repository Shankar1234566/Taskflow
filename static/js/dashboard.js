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
            <div class="member-meta" style="margin-top: 12px; font-size: 13px; color: var(--muted);">
              <span>Squad: <b>${m.team_name || 'Unassigned'}</b></span>
            </div>
          </div>
        `;
      });
      container.innerHTML = html || '<p class="empty">No team members found.</p>';
    } catch (err) {
      console.error('Failed to load team view:', err);
    }
  }
};

window.TaskflowDashboard = TaskflowDashboard;
