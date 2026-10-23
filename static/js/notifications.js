/**
 * Taskflow Enterprise — Notification Center & Issue Routing Module
 * Mirroring Jira Software's Notification & Subscription Architecture.
 *
 * Provides:
 * - Header bell trigger with pulsing unread badge
 * - Animated dropdown/slide-out drawer
 * - Categorized notification items with event icons
 * - Mark as read, mark all read, delete/dismiss actions
 * - Deep linking: clicking a notification marks as read and navigates to/highlights the task
 * - Deliverable Watching/Subscription toggle and watcher count
 * - 15-second lightweight background polling loop
 */

const TaskflowNotifications = {
  notifications: [],
  unreadCount: 0,
  activeFilter: 'all', // 'all' | 'unread'
  isOpen: false,
  pollingTimer: null,
  isFetching: false,

  /**
   * Initializes the Notification Center
   */
  async init() {
    this.createHeaderBellTrigger();
    this.createDrawerDOM();
    this.bindEvents();
    await this.fetchNotifications();
    this.startPolling();
  },

  /**
   * Injects the bell button into the topbar action cluster if not statically present.
   */
  createHeaderBellTrigger() {
    if (document.getElementById('notif-bell-btn')) return;

    const topActions = document.querySelector('.top-actions');
    if (!topActions) return;

    const bellBtn = document.createElement('button');
    bellBtn.id = 'notif-bell-btn';
    bellBtn.className = 'notif-bell-btn';
    bellBtn.setAttribute('aria-label', 'Open notification center');
    bellBtn.setAttribute('title', 'Notifications');
    bellBtn.innerHTML = `
      <svg class="notif-bell-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
        <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
      </svg>
      <span class="notif-badge hidden" id="notif-badge-count">0</span>
    `;

    // Insert bell before user avatar
    const avatar = document.getElementById('user-avatar');
    if (avatar) {
      topActions.insertBefore(bellBtn, avatar);
    } else {
      topActions.appendChild(bellBtn);
    }
  },

  /**
   * Creates the dropdown drawer and backdrop in the document body.
   */
  createDrawerDOM() {
    if (document.getElementById('notif-drawer-root')) return;

    const container = document.createElement('div');
    container.id = 'notif-drawer-root';
    container.innerHTML = `
      <div class="notif-drawer-backdrop" id="notif-backdrop"></div>
      <aside class="notif-drawer" id="notif-drawer" role="dialog" aria-label="Notifications Center">
        <header class="notif-header">
          <div class="notif-title-area">
            <h3 class="notif-title">Notifications</h3>
            <span class="notif-count-pill" id="notif-unread-pill">0 new</span>
          </div>
          <div class="notif-header-actions">
            <button class="notif-mark-all-btn" id="notif-mark-all-btn" title="Mark all notifications as read">
              Mark all as read
            </button>
            <button class="notif-close-btn" id="notif-close-btn" aria-label="Close notifications">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
        </header>

        <nav class="notif-tabs" aria-label="Notification filters">
          <button class="notif-tab active" data-filter="all" id="notif-tab-all">All</button>
          <button class="notif-tab" data-filter="unread" id="notif-tab-unread">Unread Only</button>
        </nav>

        <ul class="notif-list" id="notif-list" role="list">
          <!-- Rendered dynamically -->
        </ul>
      </aside>
    `;

    document.body.appendChild(container);
  },

  /**
   * Binds UI events for bell, backdrop, tabs, and escape key
   */
  bindEvents() {
    const bellBtn = document.getElementById('notif-bell-btn');
    if (bellBtn) {
      bellBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.toggleDrawer();
      });
    }

    const closeBtn = document.getElementById('notif-close-btn');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => this.closeDrawer());
    }

    const backdrop = document.getElementById('notif-backdrop');
    if (backdrop) {
      backdrop.addEventListener('click', () => this.closeDrawer());
    }

    const markAllBtn = document.getElementById('notif-mark-all-btn');
    if (markAllBtn) {
      markAllBtn.addEventListener('click', () => this.markAllAsRead());
    }

    const tabAll = document.getElementById('notif-tab-all');
    const tabUnread = document.getElementById('notif-tab-unread');
    if (tabAll && tabUnread) {
      tabAll.addEventListener('click', () => this.setFilter('all'));
      tabUnread.addEventListener('click', () => this.setFilter('unread'));
    }

    // Keyboard support: Escape closes drawer
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.isOpen) {
        this.closeDrawer();
      }
    });

    // Close on click outside drawer
    document.addEventListener('click', (e) => {
      const drawer = document.getElementById('notif-drawer');
      const bell = document.getElementById('notif-bell-btn');
      if (this.isOpen && drawer && !drawer.contains(e.target) && !bell.contains(e.target)) {
        this.closeDrawer();
      }
    });
  },

  /**
   * Fetches latest notifications from server
   */
  async fetchNotifications() {
    if (this.isFetching) return;
    this.isFetching = true;

    try {
      const unreadParam = this.activeFilter === 'unread' ? '?unread_only=true' : '';
      const res = await fetch(`/api/notifications${unreadParam}`, {
        headers: { 'Accept': 'application/json' }
      });

      if (!res.ok) {
        if (res.status === 401) {
          this.stopPolling();
        }
        return;
      }

      const data = await res.json();
      this.notifications = data.notifications || [];
      this.unreadCount = typeof data.unread_count === 'number' ? data.unread_count : 0;

      this.updateBadge();
      this.renderList();
    } catch (err) {
      console.warn('Failed to fetch notifications:', err);
    } finally {
      this.isFetching = false;
    }
  },

  /**
   * Lightweight background polling: updates unread count badge every 15s
   */
  startPolling() {
    if (this.pollingTimer) clearInterval(this.pollingTimer);
    this.pollingTimer = setInterval(async () => {
      try {
        const res = await fetch('/api/notifications?limit=1');
        if (res.ok) {
          const data = await res.json();
          const prevCount = this.unreadCount;
          this.unreadCount = data.unread_count || 0;
          this.updateBadge();

          // If count increased and drawer is open, refresh entire list
          if (this.isOpen && this.unreadCount !== prevCount) {
            this.fetchNotifications();
          }
        }
      } catch (err) {
        // Silently handle transient polling errors
      }
    }, 15000); // 15-second loop
  },

  stopPolling() {
    if (this.pollingTimer) {
      clearInterval(this.pollingTimer);
      this.pollingTimer = null;
    }
  },

  /**
   * Updates bell badge and unread pills in UI
   */
  updateBadge() {
    const badge = document.getElementById('notif-badge-count');
    const pill = document.getElementById('notif-unread-pill');

    if (badge) {
      if (this.unreadCount > 0) {
        badge.textContent = this.unreadCount > 99 ? '99+' : this.unreadCount;
        badge.classList.remove('hidden');
      } else {
        badge.textContent = '0';
        badge.classList.add('hidden');
      }
    }

    if (pill) {
      pill.textContent = `${this.unreadCount} new`;
    }
  },

  /**
   * Renders the notification items into the drawer
   */
  renderList() {
    const list = document.getElementById('notif-list');
    if (!list) return;

    if (!this.notifications || this.notifications.length === 0) {
      list.innerHTML = `
        <li class="notif-empty">
          <svg class="notif-empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
            <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
          </svg>
          <h4 class="notif-empty-title">All Caught Up!</h4>
          <p class="notif-empty-desc">${this.activeFilter === 'unread' ? 'Zero unread notifications waiting for review.' : 'You have no alerts at this time.'}</p>
        </li>
      `;
      return;
    }

    let html = '';
    this.notifications.forEach((n) => {
      const isUnread = !n.is_read;
      const isUrgent = (n.priority || '').toLowerCase() === 'urgent';
      const iconSvg = this.getEventIconSvg(n.event_type);

      html += `
        <li class="notif-item ${isUnread ? 'unread' : ''} ${isUrgent ? 'urgent' : ''}" 
            data-notif-id="${n.id}" 
            onclick="TaskflowNotifications.handleNotificationClick(${n.id}, ${n.task_id || 'null'})">
          <span class="notif-unread-dot" title="Unread notification"></span>
          
          <div class="notif-icon-wrap ${n.event_type}">
            ${iconSvg}
          </div>

          <div class="notif-content">
            <h4 class="notif-item-title">
              <span>${this.escapeHtml(n.title)}</span>
              ${isUrgent ? '<span class="notif-urgent-pill">Urgent</span>' : ''}
            </h4>
            <p class="notif-item-msg">${this.escapeHtml(n.message)}</p>
            <div class="notif-item-meta">
              <span class="notif-item-sender">${this.escapeHtml(n.sender_name || 'System')}</span>
              <span>•</span>
              <time datetime="${n.created_at || ''}">${n.time_ago || 'recent'}</time>
            </div>
          </div>

          <div class="notif-item-actions">
            ${isUnread ? `
              <button class="notif-action-btn read" 
                      title="Mark as read" 
                      onclick="event.stopPropagation(); TaskflowNotifications.markAsRead(${n.id})">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
              </button>
            ` : ''}
            <button class="notif-action-btn delete" 
                    title="Dismiss notification" 
                    onclick="event.stopPropagation(); TaskflowNotifications.deleteNotification(${n.id})">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
        </li>
      `;
    });

    list.innerHTML = html;
  },

  /**
   * Helper to return Jira-style SVG icons according to event type
   */
  getEventIconSvg(eventType) {
    switch (eventType) {
      case 'BUG_ROUTED':
      case 'HIGH_PRIORITY_BUG':
        return `
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect width="8" height="14" x="8" y="6" rx="4"/>
            <path d="m19 7-3 2"/><path d="m5 7 3 2"/><path d="m19 19-3-2"/><path d="m5 19 3-2"/>
            <path d="M20 13h-4"/><path d="M4 13h4"/><path d="m10 4 1 2"/><path d="m14 4-1 2"/>
          </svg>
        `;
      case 'STATUS_CHANGED':
        return `
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="16 3 21 3 21 8"/><line x1="4" y1="20" x2="21" y2="3"/>
            <polyline points="21 16 21 21 16 21"/><line x1="15" y1="15" x2="21" y2="21"/>
            <line x1="4" y1="4" x2="9" y2="9"/>
          </svg>
        `;
      case 'BLOCKER_RESOLVED':
        return `
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
            <path d="M7 11V7a5 5 0 0 1 9.9-1"/>
          </svg>
        `;
      case 'TASK_ASSIGNED':
        return `
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/>
            <circle cx="12" cy="7" r="4"/>
          </svg>
        `;
      case 'REVIEW_REQUESTED':
        return `
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <polyline points="12 6 12 12 16 14"/>
          </svg>
        `;
      case 'FEEDBACK_SUBMITTED':
        return `
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
        `;
      default:
        return `
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
        `;
    }
  },

  /**
   * Toggle Notification Drawer open/closed
   */
  toggleDrawer() {
    if (this.isOpen) {
      this.closeDrawer();
    } else {
      this.openDrawer();
    }
  },

  openDrawer() {
    this.isOpen = true;
    const drawer = document.getElementById('notif-drawer');
    const backdrop = document.getElementById('notif-backdrop');
    const bellBtn = document.getElementById('notif-bell-btn');

    if (drawer) drawer.classList.add('open');
    if (backdrop) backdrop.classList.add('open');
    if (bellBtn) bellBtn.classList.add('active');

    this.fetchNotifications();
  },

  closeDrawer() {
    this.isOpen = false;
    const drawer = document.getElementById('notif-drawer');
    const backdrop = document.getElementById('notif-backdrop');
    const bellBtn = document.getElementById('notif-bell-btn');

    if (drawer) drawer.classList.remove('open');
    if (backdrop) backdrop.classList.remove('open');
    if (bellBtn) bellBtn.classList.remove('active');
  },

  /**
   * Filter between "All" and "Unread Only"
   */
  setFilter(filterType) {
    this.activeFilter = filterType;
    const tabAll = document.getElementById('notif-tab-all');
    const tabUnread = document.getElementById('notif-tab-unread');

    if (tabAll && tabUnread) {
      tabAll.classList.toggle('active', filterType === 'all');
      tabUnread.classList.toggle('active', filterType === 'unread');
    }

    this.fetchNotifications();
  },

  /**
   * Marks a single notification as read
   */
  async markAsRead(notifId) {
    try {
      const res = await fetch(`/api/notifications/${notifId}/read`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' }
      });
      if (res.ok) {
        const item = this.notifications.find(n => n.id === notifId);
        if (item) item.is_read = true;
        this.unreadCount = Math.max(0, this.unreadCount - 1);
        this.updateBadge();
        this.renderList();
      }
    } catch (err) {
      console.error('Failed to mark notification as read:', err);
    }
  },

  /**
   * Marks all unread notifications as read
   */
  async markAllAsRead() {
    try {
      const res = await fetch('/api/notifications/read-all', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' }
      });
      if (res.ok) {
        this.notifications.forEach(n => { n.is_read = true; });
        this.unreadCount = 0;
        this.updateBadge();
        this.renderList();
      }
    } catch (err) {
      console.error('Failed to mark all notifications as read:', err);
    }
  },

  /**
   * Deletes / dismisses a notification
   */
  async deleteNotification(notifId) {
    try {
      const res = await fetch(`/api/notifications/${notifId}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        const idx = this.notifications.findIndex(n => n.id === notifId);
        if (idx !== -1) {
          if (!this.notifications[idx].is_read) {
            this.unreadCount = Math.max(0, this.unreadCount - 1);
          }
          this.notifications.splice(idx, 1);
        }
        this.updateBadge();
        this.renderList();
      }
    } catch (err) {
      console.error('Failed to delete notification:', err);
    }
  },

  /**
   * When user clicks a notification item:
   * 1. Marks as read
   * 2. Closes drawer
   * 3. Jumps to and highlights target deliverable in workspace table / opens detail modal
   */
  async handleNotificationClick(notifId, taskId) {
    await this.markAsRead(notifId);
    this.closeDrawer();

    if (!taskId) return;

    // Switch view to Overview / All Tasks if not currently visible
    if (window.TaskflowDashboard && typeof window.TaskflowDashboard.switchView === 'function') {
      window.TaskflowDashboard.switchView('overview');
    }

    // Attempt to locate task in table
    setTimeout(() => {
      const row = document.querySelector(`tr[data-task-id="${taskId}"]`);
      if (row) {
        row.scrollIntoView({ behavior: 'smooth', block: 'center' });
        row.classList.remove('task-row-highlight');
        void row.offsetWidth; // Trigger reflow
        row.classList.add('task-row-highlight');
      }

      // Also trigger detail modal view
      if (window.TaskflowTasks && typeof window.TaskflowTasks.viewTaskDetail === 'function') {
        window.TaskflowTasks.viewTaskDetail(taskId);
      }
    }, 200);
  },

  /**
   * Deliverable Watcher Feature:
   * Toggles watch subscription for current user
   */
  async toggleWatch(taskId) {
    if (!taskId) return;
    try {
      const res = await fetch(`/api/tasks/${taskId}/watch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      if (!res.ok) return;

      const data = await res.json();
      this.updateWatchButtonUI(taskId, data.is_watching, data.watcher_count);
    } catch (err) {
      console.error('Error toggling watch subscription:', err);
    }
  },

  /**
   * Fetches watch status and updates the button in detail modal
   */
  async loadWatchStatus(taskId) {
    if (!taskId) return;
    try {
      const res = await fetch(`/api/tasks/${taskId}/watch-status`);
      if (!res.ok) return;

      const data = await res.json();
      this.updateWatchButtonUI(taskId, data.is_watching, data.watcher_count);
    } catch (err) {
      console.error('Error fetching watch status:', err);
    }
  },

  /**
   * Updates watch button DOM in Task Detail Modal
   */
  updateWatchButtonUI(taskId, isWatching, watcherCount) {
    const btn = document.getElementById('btn-watch-task');
    if (!btn) return;

    btn.setAttribute('data-task-id', taskId);
    btn.classList.toggle('watching', isWatching);

    const countText = watcherCount > 0 ? ` (${watcherCount})` : '';
    if (isWatching) {
      btn.innerHTML = `
        <svg viewBox="0 0 24 24" fill="currentColor" stroke="none">
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
          <circle cx="12" cy="12" r="3" fill="#FFFFFF"></circle>
        </svg>
        <span>Watching${countText}</span>
      `;
      btn.title = "You are watching this deliverable. Click to unsubscribe.";
    } else {
      btn.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
          <circle cx="12" cy="12" r="3"></circle>
        </svg>
        <span>Watch Deliverable${countText}</span>
      `;
      btn.title = "Subscribe to deliverable status updates and review alerts.";
    }
  },

  escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
};

window.TaskflowNotifications = TaskflowNotifications;
