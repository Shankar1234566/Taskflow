/**
 * Taskflow Tasks & Review Pipeline Module
 * Manages task fetching, 250ms debounced search, filtering, table rendering,
 * modals (Add Task, Submit Proof), Lead Review Drawer, and status transitions.
 */

const TaskflowTasks = {
  allTasks: [],
  filteredTasks: [],
  debounceTimer: null,
  activeDateFilter: null,

  async init() {
    this.bindSearchAndFilters();
    this.bindModals();
    await this.fetchTasks();
  },

  async fetchTasks() {
    try {
      const res = await fetch('/api/tasks');
      if (!res.ok) {
        if (res.status === 401) {
          window.location.href = '/login';
          return;
        }
        return;
      }
      const data = await res.json();
      this.allTasks = data.tasks || [];
      this.applyFilters();

      // Update calendar dots & dashboard metrics
      if (window.TaskflowDashboard) {
        window.TaskflowDashboard.renderMiniCalendar(this.allTasks);
        window.TaskflowDashboard.fetchStats();
      }
    } catch (err) {
      console.error('Failed to fetch tasks:', err);
    }
  },

  bindSearchAndFilters() {
    const searchInput = document.getElementById('task-search');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(() => {
          this.applyFilters();
        }, 250); // 250ms debounce
      });
    }

    const catFilter = document.getElementById('filter-category');
    if (catFilter) {
      catFilter.addEventListener('change', () => this.applyFilters());
    }

    const prioFilter = document.getElementById('filter-priority');
    if (prioFilter) {
      prioFilter.addEventListener('change', () => this.applyFilters());
    }

    const statusFilter = document.getElementById('filter-status');
    if (statusFilter) {
      statusFilter.addEventListener('change', () => this.applyFilters());
    }

    const teamFilter = document.getElementById('filter-team');
    if (teamFilter) {
      teamFilter.addEventListener('change', () => {
        const teamId = teamFilter.value;
        if (window.TaskflowDashboard) {
          window.TaskflowDashboard.fetchStats(teamId || null);
        }
        this.applyFilters();
      });
    }
  },

  filterByDate(dateStr) {
    this.activeDateFilter = dateStr;
    this.applyFilters();
  },

  clearDateFilter() {
    this.activeDateFilter = null;
    this.applyFilters();
  },

  applyFilters() {
    const searchVal = (document.getElementById('task-search')?.value || '').toLowerCase().trim();
    const catVal = document.getElementById('filter-category')?.value || '';
    const prioVal = document.getElementById('filter-priority')?.value || '';
    const statusVal = document.getElementById('filter-status')?.value || '';
    const teamVal = document.getElementById('filter-team')?.value || '';
    const activeView = window.TaskflowDashboard?.activeView || 'overview';

    let result = [...this.allTasks];

    // Filter by view
    const currentUserId = window.TaskflowAuth?.currentUser?.id;
    if (activeView === 'my-tasks' && currentUserId) {
      result = result.filter(t => t.assigned_to_id === currentUserId || t.user_id === currentUserId);
    } else if (activeView === 'today') {
      const today = new Date().toISOString().substring(0, 10);
      result = result.filter(t => t.due_date && t.due_date.substring(0, 10) === today);
    } else if (activeView === 'upcoming') {
      const today = new Date().toISOString().substring(0, 10);
      result = result.filter(t => t.due_date && t.due_date.substring(0, 10) >= today && !t.completed);
    } else if (activeView === 'starred') {
      result = result.filter(t => t.is_starred);
    } else if (activeView === 'completed') {
      result = result.filter(t => t.completed || t.status === 'Completed');
    }

    // Search query (title, description, tags)
    if (searchVal) {
      result = result.filter(t =>
        (t.title && t.title.toLowerCase().includes(searchVal)) ||
        (t.description && t.description.toLowerCase().includes(searchVal)) ||
        (t.tags && t.tags.toLowerCase().includes(searchVal))
      );
    }

    // Category filter
    if (catVal) {
      result = result.filter(t => t.category === catVal);
    }

    // Priority filter
    if (prioVal) {
      result = result.filter(t => t.priority === prioVal);
    }

    // Status filter
    if (statusVal) {
      if (statusVal === 'Overdue') {
        result = result.filter(t => t.is_overdue || t.computed_status === 'Overdue');
      } else {
        result = result.filter(t => t.status === statusVal);
      }
    }

    // Team filter (Admin / Lead view)
    if (teamVal) {
      result = result.filter(t => String(t.team_id) === String(teamVal));
    }

    // Calendar date filter
    if (this.activeDateFilter) {
      result = result.filter(t => t.due_date && t.due_date.substring(0, 10) === this.activeDateFilter);
    }

    this.filteredTasks = result;
    this.renderTaskTable(result);
  },

  renderTaskTable(tasks) {
    const tbody = document.getElementById('task-table-body');
    if (!tbody) return;

    if (!tasks || tasks.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" class="empty">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="margin: 0 auto 12px; color: var(--muted); display: block;">
              <path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>
            </svg>
            <strong style="display:block; color: var(--ink); margin-bottom: 4px;">No tasks found</strong>
            <span>Try adjusting your search criteria or create a new deliverable.</span>
          </td>
        </tr>
      `;
      return;
    }

    const currentUser = window.TaskflowAuth?.currentUser || {};
    const isLeadOrAdmin = currentUser.role === 'Admin' || currentUser.role === 'Lead' || currentUser.is_admin;

    let html = '';
    tasks.forEach(task => {
      const isAssignee = currentUser.id === task.assigned_to_id || currentUser.id === task.user_id;
      const isCompleted = task.completed || task.status === 'Completed';
      const isOverdue = task.is_overdue || task.computed_status === 'Overdue';

      // Status pill styling with SVGs
      let statusClass = `s-${task.status ? task.status.replace(/\s+/g, '-') : 'Pending'}`;
      let statusLabel = task.status || 'Pending';
      let statusIconSvg = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
        </svg>
      `;

      if (task.status === 'In Progress') {
        statusIconSvg = `
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/>
            <line x1="4.93" y1="4.93" x2="7.76" y2="7.76"/><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"/>
            <line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/>
          </svg>
        `;
      } else if (task.status === 'In Review') {
        statusIconSvg = `
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
          </svg>
        `;
      } else if (isCompleted) {
        statusIconSvg = `
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
        `;
      }

      if (isOverdue && !isCompleted && task.status !== 'In Review') {
        statusClass = 's-Overdue';
        statusLabel = 'Overdue';
        statusIconSvg = `
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
        `;
      }

      // Assignee Avatar
      const assigneeName = task.assignee_name || 'Unassigned';
      const assigneeInitials = assigneeName.substring(0, 2).toUpperCase();

      // Horizontal Pipeline Stepper
      const pipelineStepperHtml = `
        <div class="pipeline-stepper" title="Dependency Pipeline">
          <span class="step-node completed" title="Prerequisite Specification: Verified">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
            <span>Spec</span>
          </span>
          <span class="step-arrow">&#10142;</span>
          <span class="step-node ${isCompleted ? 'completed' : (task.status === 'In Review' || task.status === 'In Progress' ? 'in-progress' : (isOverdue ? 'blocked' : ''))}" title="Build Implementation">
            ${isCompleted ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>' : (task.status === 'In Progress' ? '<span class="pulse-dot"></span>' : (isOverdue ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>' : ''))}
            <span>Build</span>
          </span>
          <span class="step-arrow">&#10142;</span>
          <span class="step-node ${isCompleted ? 'completed' : (task.status === 'In Review' ? 'in-progress' : '')}" title="QA & Lead Review">
            ${isCompleted ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>' : (task.status === 'In Review' ? '<span class="pulse-dot"></span>' : '')}
            <span>QA</span>
          </span>
        </div>
      `;

      // Action buttons based on status & role
      let actionButtons = '';

      // 1. If Pending and assignee/lead/admin -> "Start"
      if (task.status === 'Pending' && (isAssignee || isLeadOrAdmin)) {
        actionButtons += `
          <button class="btn btn-sm" onclick="TaskflowTasks.transitionStatus(${task.id}, 'In Progress')" title="Move to In Progress">
            Start
          </button>
        `;
      }

      // 2. If In Progress and isAssignee -> "Submit Proof"
      if (task.status === 'In Progress' && isAssignee) {
        actionButtons += `
          <button class="btn btn-sm primary" onclick="TaskflowTasks.openProofModal(${task.id})" title="Submit Proof of Work">
            Submit Proof
          </button>
        `;
      }

      // 3. If In Review and isLeadOrAdmin -> "Review"
      if (task.status === 'In Review' && isLeadOrAdmin) {
        actionButtons += `
          <button class="btn btn-sm proof-tag-btn" onclick="TaskflowTasks.openReviewDrawer(${task.id})" title="Inspect Proof & Review">
            Review
          </button>
        `;
      }

      // 4. Delete button (Lead / Admin only)
      if (isLeadOrAdmin) {
        actionButtons += `
          <button class="btn-close" onclick="TaskflowTasks.deleteTask(${task.id})" title="Delete Task" style="font-size: 16px;">
            &times;
          </button>
        `;
      }

      html += `
        <tr class="task-row ${isCompleted ? 'task-done' : ''} ${isOverdue ? 'task-blocked' : ''}" data-task-id="${task.id}">
          <td class="col-select">
            <input type="checkbox" class="task-chk" ${isCompleted ? 'checked' : ''} 
                   ${isAssignee || isLeadOrAdmin ? `onclick="TaskflowTasks.toggleComplete(${task.id}, this.checked)"` : 'disabled'} />
          </td>
          <td class="col-title">
            <div class="task-title-wrap">
              <div style="display: flex; align-items: center; gap: 8px;">
                <strong class="task-title-text" data-truncate-inspect onclick="TaskflowTasks.viewTaskDetail(${task.id})">${this.escapeHtml(task.title)}</strong>
                ${isOverdue && !isCompleted ? '<span class="badge-blocked">⚠️ Blocked</span>' : ''}
              </div>
              ${task.description ? `<p class="task-desc-text" data-truncate-inspect>${this.escapeHtml(task.description)}</p>` : ''}
              ${task.git_repo_link ? `<a href="${task.git_repo_link}" target="_blank" rel="noopener" class="git-link-chip" style="margin-top: 4px; padding: 2px 8px; font-size: 11px;">Git PR</a>` : ''}
            </div>
          </td>
          <td class="col-pipeline">
            ${pipelineStepperHtml}
          </td>
          <td class="col-priority">
            <span class="pill p-${task.priority || 'Medium'}">${task.priority || 'Medium'}</span>
          </td>
          <td class="col-category">
            <span class="pill c-${task.category || 'Frontend'}">${task.category || 'Frontend'}</span>
          </td>
          <td class="col-due">
            <span class="due-text ${isOverdue ? 'down font-bold' : ''}">
              ${task.due_date || 'No deadline'}
            </span>
          </td>
          <td class="col-status">
            <span class="pill ${statusClass}">
              ${statusIconSvg}
              <span>${statusLabel}</span>
            </span>
          </td>
          <td class="col-assignee">
            <div class="assignee-wrap" title="${assigneeName}">
              <div class="avatar avatar-sm">${assigneeInitials}</div>
              <span class="assignee-name" data-truncate-inspect>${assigneeName}</span>
            </div>
          </td>
          <td class="col-actions">
            <div class="task-action-btns">
              ${actionButtons}
            </div>
          </td>
        </tr>
      `;
    });

    tbody.innerHTML = html;
  },

  async transitionStatus(taskId, newStatus) {
    try {
      const res = await fetch(`/api/tasks/${taskId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus })
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.error || 'Failed to update task status.');
        return;
      }
      await this.fetchTasks();
    } catch (err) {
      console.error('Error transitioning status:', err);
    }
  },

  async toggleComplete(taskId, isChecked) {
    try {
      const res = await fetch(`/api/tasks/${taskId}/complete`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ completed: isChecked })
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.error || 'Failed to update task.');
        await this.fetchTasks();
        return;
      }
      await this.fetchTasks();
    } catch (err) {
      console.error('Error completing task:', err);
    }
  },

  async deleteTask(taskId) {
    if (!confirm('Are you sure you want to permanently delete this task?')) return;
    try {
      const res = await fetch(`/api/tasks/${taskId}`, { method: 'DELETE' });
      const data = await res.json();
      if (!res.ok) {
        alert(data.error || 'Failed to delete task.');
        return;
      }
      await this.fetchTasks();
    } catch (err) {
      console.error('Error deleting task:', err);
    }
  },

  bindModals() {
    // Add Task Button & Modal
    const addTaskBtn = document.getElementById('btn-add-task');
    const addTaskModal = document.getElementById('modal-add-task');
    const addTaskForm = document.getElementById('form-add-task');
    const closeAddModal = document.getElementById('btn-close-add-modal');

    if (addTaskBtn && addTaskModal) {
      addTaskBtn.addEventListener('click', async () => {
        await this.populateAssigneeDropdown();
        addTaskModal.showModal();
      });
    }

    if (closeAddModal && addTaskModal) {
      closeAddModal.addEventListener('click', () => addTaskModal.close());
    }

    if (addTaskForm && addTaskModal) {
      addTaskForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(addTaskForm);
        const payload = {
          title: formData.get('title'),
          description: formData.get('description'),
          category: formData.get('category'),
          priority: formData.get('priority'),
          due_date: formData.get('due_date'),
          assigned_to_id: formData.get('assigned_to_id') ? parseInt(formData.get('assigned_to_id')) : null,
          team_id: formData.get('team_id') ? parseInt(formData.get('team_id')) : null
        };

        try {
          const res = await fetch('/api/tasks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          const data = await res.json();
          if (!res.ok) {
            alert(data.error || 'Failed to create task.');
            return;
          }
          addTaskForm.reset();
          addTaskModal.close();
          await this.fetchTasks();
        } catch (err) {
          console.error('Error adding task:', err);
        }
      });
    }

    // Submit Proof of Work Modal
    const proofModal = document.getElementById('modal-submit-proof');
    const proofForm = document.getElementById('form-submit-proof');
    const closeProofModal = document.getElementById('btn-close-proof-modal');

    if (closeProofModal && proofModal) {
      closeProofModal.addEventListener('click', () => proofModal.close());
    }

    if (proofForm && proofModal) {
      proofForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const taskId = proofForm.getAttribute('data-task-id');
        if (!taskId) return;

        const formData = new FormData(proofForm);
        try {
          const res = await fetch(`/api/tasks/${taskId}/submit-proof`, {
            method: 'POST',
            body: formData
          });
          const data = await res.json();
          if (!res.ok) {
            alert(data.error || 'Failed to submit proof of work.');
            return;
          }
          proofForm.reset();
          proofModal.close();
          await this.fetchTasks();
          alert('Proof of work submitted! The deliverable is now In Review.');
        } catch (err) {
          console.error('Error submitting proof:', err);
        }
      });
    }

    // Lead Review Drawer / Modal
    const reviewDrawer = document.getElementById('drawer-lead-review');
    const closeReviewDrawer = document.getElementById('btn-close-review-drawer');

    if (closeReviewDrawer && reviewDrawer) {
      closeReviewDrawer.addEventListener('click', () => reviewDrawer.close());
    }

    const btnApprove = document.getElementById('btn-review-approve');
    const btnReject = document.getElementById('btn-review-reject');

    if (btnApprove) {
      btnApprove.addEventListener('click', () => this.handleReviewAction('approve'));
    }
    if (btnReject) {
      btnReject.addEventListener('click', () => this.handleReviewAction('reject'));
    }
  },

  async populateAssigneeDropdown() {
    const selectEl = document.getElementById('add-task-assignee');
    if (!selectEl) return;

    try {
      const res = await fetch('/api/teams/members');
      if (!res.ok) return;
      const data = await res.json();
      const members = data.members || [];

      let html = '<option value="">Select Assignee...</option>';
      members.forEach(m => {
        html += `<option value="${m.id}">${m.username || m.name} (${m.role} • ${m.team_name || 'No Squad'})</option>`;
      });
      selectEl.innerHTML = html;
    } catch (err) {
      console.error('Failed to populate assignees:', err);
    }
  },

  openProofModal(taskId) {
    const modal = document.getElementById('modal-submit-proof');
    const form = document.getElementById('form-submit-proof');
    const task = this.allTasks.find(t => t.id === taskId);
    if (!modal || !form || !task) return;

    form.setAttribute('data-task-id', taskId);
    const titleEl = document.getElementById('proof-task-title');
    if (titleEl) titleEl.textContent = task.title;

    modal.showModal();
  },

  openReviewDrawer(taskId) {
    const drawer = document.getElementById('drawer-lead-review');
    const task = this.allTasks.find(t => t.id === taskId);
    if (!drawer || !task) return;

    drawer.setAttribute('data-task-id', taskId);

    document.getElementById('review-task-title').textContent = task.title;
    document.getElementById('review-task-assignee').textContent = task.assignee_name || 'Unassigned';
    document.getElementById('review-task-submitted-at').textContent = task.submitted_at ? new Date(task.submitted_at).toLocaleString() : 'Recently';

    // Git Repo Link
    const gitLinkEl = document.getElementById('review-git-link');
    if (gitLinkEl) {
      if (task.git_repo_link) {
        gitLinkEl.href = task.git_repo_link;
        gitLinkEl.textContent = task.git_repo_link;
        gitLinkEl.parentElement.style.display = 'block';
      } else {
        gitLinkEl.parentElement.style.display = 'none';
      }
    }

    // Proof file attachment link
    const proofFileEl = document.getElementById('review-proof-file');
    if (proofFileEl) {
      if (task.proof_file_path) {
        proofFileEl.href = task.proof_file_path;
        proofFileEl.textContent = 'Download Attached Proof Document';
        proofFileEl.parentElement.style.display = 'block';
      } else {
        proofFileEl.parentElement.style.display = 'none';
      }
    }

    // Submission notes
    const notesEl = document.getElementById('review-submission-notes');
    if (notesEl) {
      notesEl.textContent = task.submission_notes || 'No implementation notes provided.';
    }

    // Clear feedback input
    const feedbackInput = document.getElementById('review-feedback-input');
    if (feedbackInput) feedbackInput.value = '';

    drawer.showModal();
  },

  async handleReviewAction(action) {
    const drawer = document.getElementById('drawer-lead-review');
    const taskId = drawer?.getAttribute('data-task-id');
    const feedback = document.getElementById('review-feedback-input')?.value || '';

    if (!taskId) return;

    try {
      const res = await fetch(`/api/tasks/${taskId}/review`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, feedback })
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.error || 'Failed to record review decision.');
        return;
      }
      drawer.close();
      await this.fetchTasks();
    } catch (err) {
      console.error('Error reviewing task:', err);
    }
  },

  viewTaskDetail(taskId) {
    const task = this.allTasks.find(t => t.id === taskId);
    if (!task) return;
    const detailDialog = document.getElementById('modal-task-detail');
    if (!detailDialog) return;

    document.getElementById('detail-title').textContent = task.title;
    document.getElementById('detail-desc').textContent = task.description || 'No description provided.';
    document.getElementById('detail-priority').textContent = task.priority;
    document.getElementById('detail-category').textContent = task.category;
    document.getElementById('detail-due').textContent = task.due_date || 'None';
    document.getElementById('detail-status').textContent = task.status;
    document.getElementById('detail-assignee').textContent = task.assignee_name || 'Unassigned';
    document.getElementById('detail-team').textContent = task.team_name || 'General';

    detailDialog.showModal();
  },

  renderReviewPipeline() {
    const container = document.getElementById('review-pipeline-container');
    if (!container) return;

    const inReviewTasks = this.allTasks.filter(t => t.status === 'In Review');
    if (inReviewTasks.length === 0) {
      container.innerHTML = `
        <div class="card empty" style="grid-column: 1 / -1;">
          <h3 style="margin-bottom: 6px;">Zero Pending Reviews</h3>
          <p style="margin: 0; color: var(--muted);">All pull requests and deliverables have been inspected.</p>
        </div>
      `;
      return;
    }

    let html = '';
    inReviewTasks.forEach(t => {
      html += `
        <div class="review-card">
          <div class="review-card-head">
            <span class="pill c-${t.category}">${t.category}</span>
            <span class="pill s-In-Review">In Review</span>
          </div>
          <h4 style="margin: 0; font-size: 16px;">${this.escapeHtml(t.title)}</h4>
          <p class="text-sm text-muted" style="margin: 0;">${this.escapeHtml(t.description || '')}</p>
          
          <div class="review-notes-box">
            <strong style="display:block; font-size: 11px; text-transform: uppercase; color: var(--muted); margin-bottom: 4px;">Developer Notes</strong>
            <span>${this.escapeHtml(t.submission_notes || 'No notes provided.')}</span>
          </div>

          ${t.git_repo_link ? `<a href="${t.git_repo_link}" target="_blank" rel="noopener" class="git-link-chip">View Git PR</a>` : ''}
          ${t.proof_file_path ? `<a href="${t.proof_file_path}" target="_blank" class="git-link-chip">Attached Proof File</a>` : ''}

          <div class="flex-between" style="border-top: 1px solid var(--line); padding-top: 12px; margin-top: auto;">
            <div class="text-sm text-muted">
              Assignee: <b>${t.assignee_name || 'Member'}</b>
            </div>
            <button class="btn btn-sm primary" onclick="TaskflowTasks.openReviewDrawer(${t.id})">
              Inspect & Approve
            </button>
          </div>
        </div>
      `;
    });
    container.innerHTML = html;
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

window.TaskflowTasks = TaskflowTasks;
