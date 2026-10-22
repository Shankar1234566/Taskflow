const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const page = document.body.dataset.page, GID = document.body.dataset.google;

const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
}[c]));

async function api(path, method = "GET", body) {
  const isFormData = body instanceof FormData;
  const headers = isFormData ? {} : { "Content-Type": "application/json" };
  const res = await fetch("/api" + path, {
    method,
    headers,
    body: isFormData ? body : (body ? JSON.stringify(body) : undefined)
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && page === "dashboard") {
    location.href = "/";
  }
  if (!res.ok) {
    throw new Error(data.error || "Something went wrong.");
  }
  return data;
}

let toastTimer;
function toast(msg, undoFn = null) {
  const t = $("#toast"), text = $("#toast-text"), undoBtn = $("#toast-undo");
  if (!t) return;
  text.textContent = msg;
  if (undoFn && undoBtn) {
    undoBtn.hidden = false;
    undoBtn.onclick = () => {
      undoFn();
      t.classList.remove("show");
    };
  } else if (undoBtn) {
    undoBtn.hidden = true;
  }
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 3200);
}

/* ---------- Theme Engine ---------- */
function initTheme(userTheme = null) {
  const saved = userTheme || localStorage.getItem("taskflow_theme") || "light";
  document.documentElement.setAttribute("data-theme", saved);
  const toggleBtn = $("#theme-toggle");
  if (toggleBtn) {
    toggleBtn.onclick = async () => {
      const current = document.documentElement.getAttribute("data-theme");
      const next = current === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("taskflow_theme", next);
      if (page === "dashboard") {
        api("/auth/profile", "PUT", { theme_preference: next }).catch(() => {});
      }
    };
  }
}

/* ---------- Google OAuth ---------- */
function initGoogle(onDone) {
  const btn = $("#google-btn");
  if (!btn) return;
  if (!GID) {
    const f = $("#google-fallback");
    if (f) {
      f.hidden = false;
      f.onclick = () => alert("Google sign-in requires GOOGLE_CLIENT_ID configured in .env.");
    }
    return;
  }
  const wait = setInterval(() => {
    if (!window.google?.accounts) return;
    clearInterval(wait);
    google.accounts.id.initialize({
      client_id: GID,
      callback: async r => {
        try {
          await api("/auth/google", "POST", { credential: r.credential });
          onDone();
        } catch (e) {
          alert(e.message);
        }
      }
    });
    google.accounts.id.renderButton(btn, { theme: "outline", size: "large", text: "continue_with" });
  }, 100);
}

/* ---------- Landing Page ---------- */
function landing() {
  initTheme();
  let mode = "login";
  const form = $("#auth-form");
  const roleSelect = $("#signup-role");
  const teamWrap = $("#signup-team-wrap");
  const teamSelect = $("#signup-team");

  // Fetch squads for registration dropdown
  const loadSignupTeams = async () => {
    try {
      const res = await api("/teams");
      if (res.teams && res.teams.length && teamSelect) {
        teamSelect.innerHTML = `<option value="">Select your Squad...</option>` +
          res.teams.map(t => `<option value="${t.id}">${esc(t.name)}</option>`).join("");
      }
    } catch (e) {}
  };

  if (roleSelect && teamWrap) {
    roleSelect.onchange = () => {
      const isManager = roleSelect.value === "Admin";
      teamWrap.hidden = isManager;
    };
  }

  $$(".tab").forEach(t => t.onclick = () => {
    mode = t.dataset.mode;
    $$(".tab").forEach(x => x.classList.toggle("active", x === t));
    $$(".signup-only").forEach(el => {
      el.hidden = mode !== "signup";
    });
    if (mode === "signup" && roleSelect && roleSelect.value === "Admin" && teamWrap) {
      teamWrap.hidden = true;
    }
    $("#auth-submit").textContent = mode === "signup" ? "Create account" : "Log in";
    $("#auth-error").textContent = "";
    if (mode === "signup") loadSignupTeams();
  });

  if (form) {
    form.onsubmit = async e => {
      e.preventDefault();
      const d = Object.fromEntries(new FormData(form));
      if (mode === "signup" && d.team_id) {
        d.team_id = parseInt(d.team_id, 10);
      }
      try {
        const res = await api("/auth/" + mode, "POST", d);
        if (res.user) {
          localStorage.setItem("taskflow_user", JSON.stringify(res.user));
        }
        location.href = "/dashboard";
      } catch (err) {
        $("#auth-error").textContent = err.message;
      }
    };
  }
  initGoogle(() => location.href = "/dashboard");
}

/* ---------- Dashboard State ---------- */
const state = {
  user: null,
  teams: [],
  members: [],
  selectedTeamId: null,
  tasks: [],
  selectedDate: null,
  editing: null,
  viewMode: localStorage.getItem("taskflow_view") || "list",
  selectedIds: new Set(),
  activeTab: "overview",
  lastDeletedTask: null,
  employeeScope: "my" // "my" | "team"
};

function fmtDate(d) {
  return d ? new Date(d + "T00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "No date";
}

function localDateString(date) {
  const year = date.getFullYear(), month = String(date.getMonth() + 1).padStart(2, "0");
  return `${year}-${month}-${String(date.getDate()).padStart(2, "0")}`;
}

function updateBreadcrumbs(viewName) {
  const titleMap = {
    overview: "Overview",
    "my-tasks": "My Tasks",
    "review-pipeline": "Review Pipeline",
    today: "Today's Tasks",
    upcoming: "Upcoming Tasks",
    starred: "Important / Starred",
    completed: "Completed Archive",
    categories: "Categories",
    calendar: "Calendar",
    activity: "Activity History",
    settings: "Settings",
    admin: "Admin Portal"
  };
  const label = titleMap[viewName] || "Tasks";
  const crumb = $("#crumb-current");
  if (crumb) crumb.textContent = label;
}

function updateBadges() {
  const today = localDateString(new Date());
  const countToday = state.tasks.filter(t => !t.completed && t.due_date === today).length;
  const countStarred = state.tasks.filter(t => t.is_starred && !t.completed).length;
  const countTotal = state.tasks.filter(t => !t.completed).length;
  const countReview = state.tasks.filter(t => t.status === "In Review").length;

  if ($("#badge-today")) $("#badge-today").textContent = countToday;
  if ($("#badge-starred")) $("#badge-starred").textContent = countStarred;
  if ($("#badge-total")) $("#badge-total").textContent = countTotal;
  if ($("#badge-review")) $("#badge-review").textContent = countReview;
}

/* ---------- Donut Chart ---------- */
function drawDonut(s) {
  const onTime = Math.max(0, s.in_progress - s.overdue), C = 2 * Math.PI * 46;
  const inReview = s.in_review || 0;
  const parts = [[s.completed, "#2E7D32"], [inReview, "#7E22CE"], [onTime, "#0369A1"], [s.overdue, "#D9534F"]];
  let off = 0, out = `<circle cx="60" cy="60" r="46" fill="none" stroke="var(--line)" stroke-width="14"/>`;
  parts.forEach(([n, col]) => {
    if (!n || !s.total) return;
    const len = n / s.total * C;
    out += `<circle cx="60" cy="60" r="46" fill="none" stroke="${col}" stroke-width="14" stroke-dasharray="${len} ${C - len}" stroke-dashoffset="${-off}" transform="rotate(-90 60 60)"/>`;
    off += len;
  });
  out += `<text x="60" y="66" text-anchor="middle" font-size="22" font-weight="700" fill="var(--ink)">${s.percent_complete}%</text>`;
  const donut = $("#donut");
  if (donut) donut.innerHTML = out;
  if ($("#l-c")) $("#l-c").textContent = s.completed;
  if ($("#l-p")) $("#l-p").textContent = s.in_progress;
  if ($("#l-o")) $("#l-o").textContent = s.overdue;
}

/* ---------- Stats & Assistant ---------- */
async function loadStats() {
  const teamParam = state.selectedTeamId ? `?team_id=${state.selectedTeamId}` : "";
  const s = await api("/dashboard/stats" + teamParam);
  if ($("#m-total")) $("#m-total").textContent = s.total;
  if ($("#m-progress")) $("#m-progress").textContent = s.in_progress;
  if ($("#m-completed")) $("#m-completed").textContent = s.completed;
  if ($("#m-overdue")) $("#m-overdue").textContent = s.overdue;
  if ($("#t-total")) $("#t-total").textContent = `↑ ${s.trends.total} this week`;
  if ($("#t-completed")) $("#t-completed").textContent = `↑ ${s.trends.completed} this week`;
  if ($("#t-progress")) $("#t-progress").textContent = `${s.in_review || 0} in review pipeline`;
  if ($("#t-overdue")) $("#t-overdue").textContent = s.overdue ? "Needs attention" : "All caught up";
  drawDonut(s);
  renderCategoryBreakdown(s.categories || []);
  renderSquadPerformances(s.departments || []);
  return s;
}

function renderSquadPerformances(departments) {
  const containers = [$("#overview-squad-cards"), $("#admin-squad-cards")].filter(Boolean);
  if (!containers.length) return;

  if (!departments || !departments.length) {
    containers.forEach(c => {
      c.innerHTML = `<div class="empty" style="grid-column: 1 / -1;">No squad performance metrics available yet.</div>`;
    });
    return;
  }

  const html = departments.map(d => {
    return `
      <div class="squad-card" data-team-id="${d.team_id}">
        <div class="squad-card-head">
          <div>
            <h4 class="squad-title">${esc(d.team_name)}</h4>
            <div class="squad-lead-meta">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
              <span>Lead: <b>${esc(d.lead_name)}</b></span>
            </div>
          </div>
          <span class="pill stat ${d.velocity >= 70 ? 's-Completed' : d.velocity >= 40 ? 's-In' : 's-Pending'}">${d.velocity}% Velocity</span>
        </div>

        <div class="squad-metrics-row">
          <span class="squad-metric-badge total" title="Total Tasks">${d.total} Total</span>
          <span class="squad-metric-badge progress" title="In Progress">${d.in_progress} Active</span>
          <span class="squad-metric-badge review" title="Awaiting Review">${d.in_review} Review</span>
          <span class="squad-metric-badge completed" title="Completed Tasks">${d.completed} Done</span>
          ${d.overdue ? `<span class="squad-metric-badge overdue" title="Overdue Deliverables">${d.overdue} Overdue</span>` : ""}
        </div>

        <div class="squad-velocity-bar-wrap">
          <div class="squad-velocity-label">
            <span>Sprint Completion</span>
            <span>${d.completed} / ${d.total} tasks</span>
          </div>
          <div class="squad-progress-track">
            <div class="squad-progress-fill" style="width: ${d.velocity}%"></div>
          </div>
        </div>

        <div class="squad-actions">
          <button type="button" class="btn btn-sm primary" data-act="assign-lead" data-team-id="${d.team_id}" data-lead-id="${d.lead_id || ''}" data-lead-name="${esc(d.lead_name || '')}" data-team-name="${esc(d.team_name)}" title="Assign a direct task to the team lead">
            + Assign to Lead
          </button>
          <button type="button" class="btn btn-sm ghost" data-act="filter-squad" data-team-id="${d.team_id}" title="Inspect this squad's workspace">
            Filter Squad
          </button>
        </div>
      </div>
    `;
  }).join("");

  containers.forEach(c => {
    c.innerHTML = html;
  });
}

function renderCategoryBreakdown(categories) {
  const grid = $("#categories-grid");
  if (!grid) return;
  if (!categories.length) {
    grid.innerHTML = `<div class="empty">No category data available yet. Add deliverables to see breakdown.</div>`;
    return;
  }
  grid.innerHTML = categories.map(c => `
    <div class="cat-card">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <h4>${esc(c.name)}</h4>
        <span class="pill cat c-${esc(c.name)}">${c.total} items</span>
      </div>
      <div class="cat-bar-wrap"><div class="cat-bar" style="width: ${c.percent}%"></div></div>
      <div class="cat-stats" style="display:flex; justify-content:space-between; font-size:12px; color:var(--muted);">
        <span>${c.completed} completed ${c.in_review ? `• ${c.in_review} in review` : ""}</span>
        <b>${c.percent}%</b>
      </div>
    </div>
  `).join("");
}

function suggest(stats, upcoming) {
  const tips = [];
  const inReviewTasks = state.tasks.filter(t => t.status === "In Review");
  const critical = state.tasks.filter(t => t.priority === "Critical" && !t.completed);
  const high = state.tasks.filter(t => t.priority === "High" && !t.completed);

  if (state.user && (state.user.role === "Admin" || state.user.role === "Lead") && inReviewTasks.length) {
    tips.push(`PIPELINE ALERT: ${inReviewTasks.length} deliverable${inReviewTasks.length > 1 ? "s are" : " is"} awaiting your sign-off in the Review Pipeline.`);
  }
  if (critical.length) tips.push(`CRITICAL: Focus on urgent priority deliverable “${critical[0].title}”.`);
  if (stats.overdue) tips.push(`You have ${stats.overdue} overdue deliverable${stats.overdue > 1 ? "s" : ""}. Review bottleneck with squad.`);
  if (high.length && !critical.length) tips.push(`High priority item in sprint: “${high[0].title}”.`);
  const next = upcoming && upcoming[0];
  if (next && next.due_date !== localDateString(new Date())) tips.push(`Next squad deadline: “${next.title}” due on ${fmtDate(next.due_date)}.`);
  if (!tips.length) tips.push(stats.total ? "All squad deliverables are on schedule! High sprint velocity." : "Create your first task deliverable to activate AI recommendations.");

  const suggEl = $("#suggestions");
  if (suggEl) suggEl.innerHTML = tips.map(t => `<li>${esc(t)}</li>`).join("");
}

/* ---------- Populate Categories Filter ---------- */
function populateCategories() {
  const categories = [...new Set(state.tasks.map(t => t.category).filter(Boolean))].sort((a, b) => a.localeCompare(b));
  const select = $("#f-category");
  if (!select) return;
  const current = select.value;
  select.replaceChildren(new Option("All categories", ""), ...categories.map(c => new Option(c, c)));
  if (categories.includes(current)) select.value = current;
}

/* ---------- Filter and Render Tasks ---------- */
function filterTasks() {
  const search = $("#f-search")?.value.trim().toLowerCase() || "";
  const status = $("#f-status")?.value || "";
  const priority = $("#f-priority")?.value || "";
  const category = $("#f-category")?.value || "";
  const due = $("#f-due")?.value || "";
  const sort = $("#f-sort")?.value || "";
  const today = localDateString(new Date());

  const weekEnd = new Date();
  weekEnd.setDate(weekEnd.getDate() + 7);
  const endOfWeek = localDateString(weekEnd);

  // Active filters bar
  const activeChips = [];
  if (state.selectedTeamId) {
    const tm = state.teams.find(t => t.id === state.selectedTeamId);
    if (tm) activeChips.push(`Squad: ${tm.name}`);
  }
  if (search) activeChips.push(`Search: "${search}"`);
  if (status) activeChips.push(`Status: ${status}`);
  if (priority) activeChips.push(`Priority: ${priority}`);
  if (category) activeChips.push(`Category: ${category}`);
  if (due) activeChips.push(`Due: ${due}`);

  const activeBar = $("#active-filters-bar");
  const activeList = $("#active-tags-list");
  if (activeBar && activeList) {
    if (activeChips.length) {
      activeBar.hidden = false;
      activeList.innerHTML = activeChips.map(c => `<span class="filter-chip">${esc(c)}</span>`).join("");
    } else {
      activeBar.hidden = true;
    }
  }

  let tasks = state.tasks.filter(task => {
    // Nav view filters
    if (state.activeTab === "review-pipeline" && task.status !== "In Review") return false;
    if (state.activeTab === "today" && (task.completed || task.due_date !== today)) return false;
    if (state.activeTab === "upcoming" && (task.completed || !task.due_date || task.due_date < today)) return false;
    if (state.activeTab === "starred" && !task.is_starred) return false;
    if (state.activeTab === "completed" && !task.completed && task.status !== "Completed") return false;

    // Search query (title, description, tags, assignee)
    if (search) {
      const matchText = `${task.title} ${task.description} ${task.tags} ${task.assignee_name || ""}`.toLowerCase();
      if (!matchText.includes(search)) return false;
    }

    // Dropdown filters
    if (status) {
      const tStat = (task.status || "Pending").toLowerCase().replace(" ", "_");
      if (tStat !== status) return false;
    }
    if (priority && task.priority !== priority) return false;
    if (category && task.category !== category) return false;
    if (state.selectedDate && task.due_date !== state.selectedDate) return false;

    if (due === "today" && task.due_date !== today) return false;
    if (due === "week" && (!task.due_date || task.due_date < today || task.due_date > endOfWeek)) return false;

    return true;
  });

  // Client-side sorting
  if (sort === "due_date") {
    tasks.sort((a, b) => (a.due_date || "9999").localeCompare(b.due_date || "9999"));
  } else if (sort === "priority") {
    const order = { Critical: 1, High: 2, Medium: 3, Low: 4 };
    tasks.sort((a, b) => (order[a.priority] || 5) - (order[b.priority] || 5));
  } else if (sort === "title") {
    tasks.sort((a, b) => a.title.localeCompare(b.title));
  } else if (sort === "created_at") {
    tasks.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
  }

  // Employee Workspace Scoping: update badges & filter by scope tab
  const isLeadOrAdminUser = state.user && (state.user.role === "Admin" || state.user.role === "Lead" || state.user.is_admin);
  if (state.user && !isLeadOrAdminUser) {
    const myCount = state.tasks.filter(t => t.assigned_to_id === state.user.id || t.user_id === state.user.id).length;
    const teamCount = state.tasks.length;
    const bMy = $("#badge-my-deliverables");
    const bTeam = $("#badge-team-deliverables");
    if (bMy) bMy.textContent = myCount;
    if (bTeam) bTeam.textContent = teamCount;

    if (state.employeeScope === "my") {
      tasks = tasks.filter(t => t.assigned_to_id === state.user.id || t.user_id === state.user.id);
    }
  }

  renderTaskList(tasks);
  renderReviewPipeline();
}

function getStatusPill(task) {
  const stat = task.status || (task.completed ? "Completed" : "Pending");
  let cls = "s-Pending";
  if (stat === "Completed") cls = "s-Completed";
  else if (stat === "In Review") cls = "s-In-Review";
  else if (stat === "In Progress") cls = "s-In";
  else if (stat === "Overdue" || (task.due_date && task.due_date < localDateString(new Date()) && !task.completed)) cls = "s-Overdue";

  return `<span class="pill stat ${cls}">${esc(stat)}</span>`;
}

function renderTaskList(tasks) {
  const list = $("#task-list");
  if (!list) return;

  list.className = `task-list view-${state.viewMode}`;

  if (!tasks.length) {
    list.innerHTML = `<li class="empty">No deliverables found matching current view and filters.</li>`;
    return;
  }

  const isLeadOrAdmin = state.user && (state.user.role === "Admin" || state.user.role === "Lead" || state.user.is_admin);

  if (state.viewMode === "grid") {
    list.innerHTML = tasks.map(t => {
      const isDone = t.completed || t.status === "Completed";
      const isInReview = t.status === "In Review";
      const isPending = t.status === "Pending";
      const isInProgress = t.status === "In Progress";
      const hasFeedback = Boolean(t.feedback_notes && t.status === "In Progress");
      const canEdit = isLeadOrAdmin || Boolean(t.can_edit) || (state.user && (t.assigned_to_id === state.user.id || t.user_id === state.user.id));

      return `
        <li class="task ${isDone ? "done" : ""} ${!canEdit ? "task-row-locked" : ""}" data-id="${t.id}">
          <div class="task-head">
            ${canEdit 
              ? `<input type="checkbox" class="task-chk" data-act="select" ${state.selectedIds.has(t.id) ? "checked" : ""}>`
              : `<span class="read-only-chip" title="Teammate Deliverable (View Only)">🔒</span>`
            }
            ${canEdit 
              ? `<button class="star-btn ${t.is_starred ? "starred" : ""}" data-act="star" title="Star deliverable">★</button>`
              : `<span style="color:var(--muted); font-size:13px; margin: 0 4px;">★</span>`
            }
            <span class="pill p-${esc(t.priority)}">${esc(t.priority)}</span>
            ${getStatusPill(t)}
            <div class="menu">
              <button aria-label="Task actions" data-act="menu">…</button>
            </div>
          </div>
          <div class="task-body">
            <div class="t-title" data-act="detail">${esc(t.title)}</div>
            <div class="t-desc">${esc(t.description || "No technical description")}</div>
            ${t.assignee_name ? `<div style="font-size:12px; color:var(--muted); margin-top:4px;">👤 <b>${esc(t.assignee_name)}</b> ${t.team_name ? `• ${esc(t.team_name)}` : ""} ${!canEdit ? `<span class="read-only-chip" style="margin-left:4px;">Teammate</span>` : ""}</div>` : ""}
            ${t.tags_list && t.tags_list.length ? `<div class="t-tags">${t.tags_list.map(tag => `<span class="tag-badge">#${esc(tag)}</span>`).join("")}</div>` : ""}
            
            ${hasFeedback ? `
              <div class="feedback-box error" style="margin-top:8px; font-size:11px; padding:6px 10px;">
                <b>Revision requested:</b> ${esc(t.feedback_notes)}
              </div>
            ` : ""}

            ${isInReview && t.git_repo_link ? `
              <div style="margin-top:8px;">
                <a href="${esc(t.git_repo_link)}" target="_blank" class="git-link-chip" style="font-size:11px; padding:3px 8px;">
                  PR Submitted ↗
                </a>
              </div>
            ` : ""}
          </div>
          <div class="task-foot">
            <span class="due">${fmtDate(t.due_date)}${t.due_time ? " " + esc(t.due_time) : ""}</span>
            <span class="pill cat c-${esc(t.category)}">${esc(t.category)}</span>
            
            <div style="margin-left:auto; display:flex; gap:6px;">
              ${canEdit ? `
                ${isPending ? `<button class="btn btn-sm ghost" data-act="start" title="Start Progress">Start</button>` : ""}
                ${(isInProgress || hasFeedback) ? `<button class="btn btn-sm primary" data-act="proof" title="Submit Proof of Work">Submit PR</button>` : ""}
                ${isInReview && isLeadOrAdmin ? `<button class="btn btn-sm primary" data-act="review" title="Review PR and Deliverable">Review</button>` : ""}
                <button class="check" data-act="toggle" title="Toggle complete">${isDone ? "✓" : ""}</button>
              ` : `
                <span class="read-only-chip" title="Assigned to teammate (View-only)">View Only</span>
              `}
            </div>
          </div>
        </li>
      `;
    }).join("");
  } else {
    list.innerHTML = tasks.map(t => {
      const isDone = t.completed || t.status === "Completed";
      const isInReview = t.status === "In Review";
      const isPending = t.status === "Pending";
      const isInProgress = t.status === "In Progress";
      const hasFeedback = Boolean(t.feedback_notes && t.status === "In Progress");
      const canEdit = isLeadOrAdmin || Boolean(t.can_edit) || (state.user && (t.assigned_to_id === state.user.id || t.user_id === state.user.id));

      return `
        <li class="task ${isDone ? "done" : ""} ${!canEdit ? "task-row-locked" : ""}" data-id="${t.id}">
          ${canEdit 
            ? `<input type="checkbox" class="task-chk" data-act="select" ${state.selectedIds.has(t.id) ? "checked" : ""}>`
            : `<span class="read-only-chip" title="Teammate Deliverable (View Only)">🔒</span>`
          }
          ${canEdit 
            ? `<button class="check" aria-label="Mark complete" data-act="toggle">${isDone ? "✓" : ""}</button>`
            : `<span style="width:20px; text-align:center; color:var(--muted);">${isDone ? "✓" : "–"}</span>`
          }
          ${canEdit
            ? `<button class="star-btn ${t.is_starred ? "starred" : ""}" data-act="star" title="Star deliverable">★</button>`
            : `<span style="color:var(--muted); font-size:13px; margin: 0 4px;">★</span>`
          }
          <div>
            <div class="t-title" data-act="detail">${esc(t.title)}</div>
            <div class="t-desc">${esc(t.description)}</div>
            <div style="display:flex; align-items:center; gap:8px; margin-top:4px;">
              ${t.assignee_name ? `<span style="font-size:11px; color:var(--muted);">👤 ${esc(t.assignee_name)}</span>` : ""}
              ${t.team_name ? `<span style="font-size:11px; color:var(--muted);">[${esc(t.team_name)}]</span>` : ""}
              ${!canEdit ? `<span class="read-only-chip">Teammate</span>` : ""}
              ${t.tags_list && t.tags_list.length ? `<div class="t-tags">${t.tags_list.map(tag => `<span class="tag-badge">#${esc(tag)}</span>`).join("")}</div>` : ""}
              ${hasFeedback ? `<span class="pill p-High" style="font-size:10px; padding:1px 6px;">Changes Requested</span>` : ""}
            </div>
          </div>
          <span class="pill p-${esc(t.priority)}">${esc(t.priority)}</span>
          <span class="pill cat c-${esc(t.category)}">${esc(t.category)}</span>
          <span class="due">${fmtDate(t.due_date)}${t.due_time ? " " + esc(t.due_time) : ""}</span>
          ${getStatusPill(t)}
          
          <div style="display:flex; align-items:center; gap:6px;">
            ${canEdit ? `
              ${isPending ? `<button class="btn btn-sm ghost" data-act="start">Start</button>` : ""}
              ${(isInProgress || hasFeedback) ? `<button class="btn btn-sm primary" data-act="proof">Submit PR</button>` : ""}
              ${isInReview && isLeadOrAdmin ? `<button class="btn btn-sm primary" data-act="review">Review</button>` : ""}
              <div class="menu"><button aria-label="Task actions" data-act="menu">…</button></div>
            ` : `
              <span class="read-only-chip">View Only</span>
              <div class="menu"><button aria-label="Task actions" data-act="menu">…</button></div>
            `}
          </div>
        </li>
      `;
    }).join("");
  }
}

/* ---------- Review Pipeline View ---------- */
function renderReviewPipeline() {
  const container = $("#review-pipeline-grid");
  if (!container) return;

  const reviewItems = state.tasks.filter(t => t.status === "In Review");
  if (!reviewItems.length) {
    container.innerHTML = `
      <div class="empty" style="grid-column: 1 / -1;">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color:var(--green); margin-bottom:8px;"><circle cx="12" cy="12" r="10"/><path d="M9 12l2 2 4-4"/></svg>
        <h3>Review Pipeline is Clean!</h3>
        <p>No deliverables are currently awaiting review sign-off. When engineers submit PR proof of work, they will appear here.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = reviewItems.map(t => `
    <div class="review-card" data-id="${t.id}">
      <div class="review-card-head">
        <span class="pill p-${esc(t.priority)}">${esc(t.priority)}</span>
        <span class="pill cat c-${esc(t.category)}">${esc(t.category)}</span>
        <span class="pill s-In-Review">In Review</span>
      </div>
      <h4 style="margin:0; font-size:15px; cursor:pointer;" data-act="review">${esc(t.title)}</h4>
      <div style="font-size:12px; color:var(--muted);">
        👤 <b>${esc(t.assignee_name || "Engineer")}</b> ${t.team_name ? `• ${esc(t.team_name)}` : ""}
        ${t.submitted_at ? `<div style="margin-top:2px;">Submitted: ${new Date(t.submitted_at).toLocaleString()}</div>` : ""}
      </div>

      ${t.git_repo_link ? `
        <div>
          <a href="${esc(t.git_repo_link)}" target="_blank" rel="noopener" class="git-link-chip" style="font-size:12px;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 7h3a5 5 0 015 5 5 5 0 01-5 5h-3m-6 0H6a5 5 0 01-5-5 5 5 0 015-5h3"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
            ${esc(t.git_repo_link)}
          </a>
        </div>
      ` : ""}

      ${t.submission_notes ? `
        <div class="review-notes-box">
          <small style="display:block; font-weight:700; color:var(--muted); margin-bottom:2px;">Engineer's Notes:</small>
          ${esc(t.submission_notes)}
        </div>
      ` : ""}

      ${t.proof_file_path ? `
        <div>
          <a href="${esc(t.proof_file_path)}" target="_blank" download class="btn btn-sm" style="font-size:11px;">
            Download Attachment
          </a>
        </div>
      ` : ""}

      <div style="display:flex; justify-content:flex-end; gap:8px; margin-top:auto; padding-top:10px; border-top:1px solid var(--line);">
        <button class="btn btn-sm primary" data-act="review" style="width:100%;">
          Inspect & Review Deliverable
        </button>
      </div>
    </div>
  `).join("");
}

async function loadTasks() {
  const teamParam = state.selectedTeamId ? `?team_id=${state.selectedTeamId}` : "";
  const { tasks } = await api("/tasks/" + teamParam);
  state.tasks = tasks;
  populateCategories();
  updateBadges();
  filterTasks();
}

/* ---------- Calendar ---------- */
async function loadCalendar() {
  const { due_dates, upcoming } = await api("/dashboard/upcoming");
  const now = new Date(), y = now.getFullYear(), m = now.getMonth();
  const calTitle = $("#cal-title");
  if (calTitle) calTitle.textContent = now.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  
  const first = new Date(y, m, 1).getDay(), days = new Date(y, m + 1, 0).getDate();
  let h = "SMTWTFS".split("").map(d => `<b>${d}</b>`).join("") + "<span></span>".repeat(first);
  for (let d = 1; d <= days; d++) {
    const iso = `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    h += `<button data-date="${iso}" class="${d === now.getDate() ? "today" : ""} ${due_dates.includes(iso) ? "has" : ""} ${state.selectedDate === iso ? "sel" : ""}">${d}</button>`;
  }
  const miniCal = $("#mini-cal");
  if (miniCal) miniCal.innerHTML = h;
  return upcoming;
}

/* ---------- Activity History ---------- */
async function loadActivity() {
  const { activities } = await api("/activity");
  const fullList = $("#activity-list");
  const miniList = $("#mini-activity-list");

  if (fullList) {
    if (!activities.length) {
      fullList.innerHTML = `<li class="empty">No recent activity recorded.</li>`;
    } else {
      fullList.innerHTML = activities.map(a => `
        <li class="activity-item">
          <div class="act-dot">●</div>
          <div class="act-body">
            <span class="act-time">${new Date(a.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
            <strong>${esc(a.action.toUpperCase())}</strong>: “${esc(a.task_title)}”
            ${a.details ? `<small style="display:block; color:var(--muted);">${esc(a.details)}</small>` : ""}
          </div>
        </li>
      `).join("");
    }
  }

  if (miniList) {
    miniList.innerHTML = activities.slice(0, 4).map(a => `
      <li class="mini-activity-item">
        <span>•</span>
        <div><b>${esc(a.action)}</b>: “${esc(a.task_title)}”</div>
      </li>
    `).join("") || `<li class="empty">No activity yet.</li>`;
  }
}

/* ---------- Admin Dashboard & Company Command Center ---------- */
async function loadAdminPortal() {
  if (!state.user || (!state.user.is_admin && state.user.role !== "Admin")) return;
  try {
    const stats = await api("/admin/stats");
    if ($("#adm-users")) $("#adm-users").textContent = stats.total_users;
    if ($("#adm-tasks")) $("#adm-tasks").textContent = stats.total_tasks;
    if ($("#adm-completed")) $("#adm-completed").textContent = stats.completed_tasks;
    if ($("#adm-rate")) $("#adm-rate").textContent = `${stats.completion_rate}%`;

    const { users } = await api("/admin/users");
    const tbody = $("#admin-user-tbody");
    if (tbody) {
      tbody.innerHTML = users.map(u => `
        <tr>
          <td>#${u.id}</td>
          <td><b>${esc(u.name)}</b></td>
          <td>${esc(u.email)}</td>
          <td>
            <span class="role-badge role-${u.role || (u.is_admin ? "Admin" : "Member")}">
              ${esc(u.role || (u.is_admin ? "Admin" : "Member"))}
            </span>
          </td>
          <td>${u.completed_count} / ${u.task_count}</td>
          <td>${u.created_at ? new Date(u.created_at).toLocaleDateString() : "–"}</td>
          <td>
            ${u.id !== state.user.id ? `
              <button class="btn btn-sm ghost" data-adm-act="toggle" data-uid="${u.id}">${u.is_admin ? "Demote" : "Promote Admin"}</button>
              <button class="btn btn-sm danger" data-adm-act="delete" data-uid="${u.id}">Delete</button>
            ` : `<span style="color:var(--muted); font-size:12px;">(Current Account)</span>`}
          </td>
        </tr>
      `).join("");
    }
  } catch (e) {
    console.error("Admin load error:", e);
  }
}

/* ---------- Load Teams & Members ---------- */
async function loadTeamsAndMembers() {
  try {
    const [teamsRes, membersRes] = await Promise.all([
      api("/teams"),
      api("/teams/members")
    ]);
    state.teams = teamsRes.teams || [];
    state.members = membersRes.members || [];

    // Populate Admin Team filter select
    const teamFilter = $("#admin-team-filter");
    if (teamFilter && (state.user?.role === "Admin" || state.user?.is_admin)) {
      teamFilter.hidden = false;
      const opts = [`<option value="">All Squads (Company-Wide)</option>`];
      state.teams.forEach(t => {
        opts.push(`<option value="${t.id}" ${state.selectedTeamId === t.id ? "selected" : ""}>${esc(t.name)} (${t.member_count} engineers)</option>`);
      });
      teamFilter.innerHTML = opts.join("");
    }
  } catch (err) {
    console.error("Teams load error:", err);
  }
}

/* ---------- Refresh View ---------- */
async function refresh() {
  await loadTeamsAndMembers();
  await loadTasks();
  const [stats, upcoming] = await Promise.all([loadStats(), loadCalendar()]);
  suggest(stats, upcoming);
  loadActivity();
  if (state.user && (state.user.is_admin || state.user.role === "Admin")) loadAdminPortal();
}

/* ---------- Task Dialog Modal (+ Add Task) ---------- */
function openDialog(task = null, preselectAssigneeId = null, preselectTeamId = null) {
  state.editing = task || null;
  const f = $("#task-form");
  if (!f) return;
  f.reset();
  $("#dlg-title").textContent = task ? "Edit Deliverable" : "Add Deliverable";

  const isAdmin = Boolean(state.user?.role === "Admin" || state.user?.is_admin);
  const isLead = state.user?.role === "Lead";

  // Populate Assignee Select
  const assigneeSelect = $("#task-assignee");
  const teamSelect = $("#task-team");

  if (assigneeSelect) {
    const opts = [];
    if (isAdmin) {
      opts.push(`<option value="">Assign to Me (Admin — ${esc(state.user.name)})</option>`);
      const leads = state.members.filter(m => m.role === "Lead" && m.id !== state.user.id);
      const engineers = state.members.filter(m => m.role !== "Lead" && m.id !== state.user.id);

      if (leads.length) {
        opts.push(`<optgroup label="🌟 Team Leads (Squad Leadership)">`);
        leads.forEach(m => {
          opts.push(`<option value="${m.id}" data-team-id="${m.team_id || ''}">${esc(m.name)} — Lead (${esc(m.team_name)})</option>`);
        });
        opts.push(`</optgroup>`);
      }

      if (engineers.length) {
        opts.push(`<optgroup label="💻 Squad Engineers & Employees">`);
        engineers.forEach(m => {
          opts.push(`<option value="${m.id}" data-team-id="${m.team_id || ''}">${esc(m.name)} — ${esc(m.role)} (${esc(m.team_name)})</option>`);
        });
        opts.push(`</optgroup>`);
      }
    } else if (isLead) {
      opts.push(`<option value="">Assign to Me (Lead — ${esc(state.user.name)})</option>`);
      const squadEmployees = state.members.filter(m => m.id !== state.user.id);
      if (squadEmployees.length) {
        opts.push(`<optgroup label="👥 Employees in Your Squad (${esc(state.user.team_name || 'Designated Squad')})">`);
        squadEmployees.forEach(m => {
          opts.push(`<option value="${m.id}" data-team-id="${m.team_id || ''}">${esc(m.name)} — ${esc(m.role)}</option>`);
        });
        opts.push(`</optgroup>`);
      }
    } else {
      opts.push(`<option value="">Assign to Me (${esc(state.user.name)})</option>`);
      const teammates = state.members.filter(m => m.id !== state.user.id);
      if (teammates.length) {
        opts.push(`<optgroup label="Squad Teammates">`);
        teammates.forEach(m => {
          opts.push(`<option value="${m.id}" data-team-id="${m.team_id || ''}">${esc(m.name)} — ${esc(m.role)}</option>`);
        });
        opts.push(`</optgroup>`);
      }
    }
    assigneeSelect.innerHTML = opts.join("");

    if (preselectAssigneeId) {
      assigneeSelect.value = String(preselectAssigneeId);
    } else if (task && task.assigned_to_id) {
      assigneeSelect.value = String(task.assigned_to_id);
    } else {
      assigneeSelect.value = "";
    }
  }

  // Populate Squad Select
  if (teamSelect) {
    const opts = [`<option value="">Auto-assign Squad</option>`];
    state.teams.forEach(t => {
      opts.push(`<option value="${t.id}">${esc(t.name)}</option>`);
    });
    teamSelect.innerHTML = opts.join("");

    if (preselectTeamId) {
      teamSelect.value = String(preselectTeamId);
    } else if (task && task.team_id) {
      teamSelect.value = String(task.team_id);
    } else if (isLead && state.user.team_id) {
      teamSelect.value = String(state.user.team_id);
    } else if (preselectAssigneeId) {
      const assignedMember = state.members.find(m => String(m.id) === String(preselectAssigneeId));
      if (assignedMember?.team_id) teamSelect.value = String(assignedMember.team_id);
    } else if (!task && state.user.team_id) {
      teamSelect.value = String(state.user.team_id);
    }

    if (assigneeSelect) {
      assigneeSelect.onchange = () => {
        const val = assigneeSelect.value;
        if (!val) {
          if (state.user?.team_id) teamSelect.value = String(state.user.team_id);
          return;
        }
        const m = state.members.find(mem => String(mem.id) === String(val));
        if (m && m.team_id) {
          teamSelect.value = String(m.team_id);
        }
      };
    }
  }

  if (task) {
    ["title", "description", "priority", "category", "due_date", "due_time", "tags"].forEach(k => {
      if (f.elements[k]) f.elements[k].value = task[k] || "";
    });
    if (f.elements["is_starred"]) f.elements["is_starred"].checked = Boolean(task.is_starred);
  } else {
    if (f.elements["category"]) f.elements["category"].value = "Frontend";
    if (f.elements["priority"]) f.elements["priority"].value = "Medium";
  }
  $("#task-error").textContent = "";
  $("#task-dialog").showModal();
}

/* ---------- Submit Proof of Work Modal ---------- */
function openProofDialog(task) {
  const dlg = $("#proof-dialog");
  const form = $("#proof-form");
  if (!dlg || !form || !task) return;

  form.reset();
  $("#proof-task-id").value = task.id;
  $("#proof-dlg-title").textContent = `Submit Proof: ${task.title}`;
  $("#proof-task-sub").textContent = `Deliverable assigned to you • ${task.category || "Engineering"}`;
  
  if (task.feedback_notes) {
    $("#proof-changes-alert").hidden = false;
    $("#proof-changes-text").textContent = task.feedback_notes;
  } else {
    $("#proof-changes-alert").hidden = true;
  }

  $("#proof-git-link").value = task.git_repo_link || "";
  $("#proof-notes").value = task.submission_notes || "";
  $("#proof-file-label").textContent = task.proof_file_path ? `Current: ${task.proof_file_path.split("/").pop()} (Click to replace)` : "Click or drag & drop proof file (PNG, JPG, PDF, LOG, ZIP)";
  $("#proof-error").textContent = "";

  dlg.showModal();
}

/* ---------- Lead Review Drawer / Modal ---------- */
function openReviewDialog(task) {
  const dlg = $("#review-dialog");
  if (!dlg || !task) return;

  $("#rev-task-id").value = task.id;
  $("#rev-title").textContent = task.title;
  $("#rev-desc").textContent = task.description || "No technical description specified.";
  $("#rev-priority").textContent = task.priority;
  $("#rev-priority").className = `pill p-${esc(task.priority)}`;
  $("#rev-category").textContent = task.category;
  $("#rev-category").className = `pill cat c-${esc(task.category)}`;
  $("#rev-assignee").textContent = `${task.assignee_name || "Engineer"} (${task.team_name || "Squad"})`;
  $("#rev-submitted").textContent = task.submitted_at ? new Date(task.submitted_at).toLocaleString() : "Just now";

  // Git PR link
  const gitWrap = $("#rev-git-wrap");
  const gitLink = $("#rev-git-link");
  const gitText = $("#rev-git-text");
  if (task.git_repo_link) {
    gitWrap.hidden = false;
    gitLink.href = task.git_repo_link;
    gitText.textContent = task.git_repo_link;
  } else {
    gitWrap.hidden = true;
  }

  // Proof file attachment
  const fileWrap = $("#rev-file-wrap");
  const fileLink = $("#rev-file-link");
  const fileName = $("#rev-file-name");
  if (task.proof_file_path) {
    fileWrap.hidden = false;
    fileLink.href = task.proof_file_path;
    fileName.textContent = `Download: ${task.proof_file_path.split("/").pop()}`;
  } else {
    fileWrap.hidden = true;
  }

  $("#rev-notes").textContent = task.submission_notes || "No notes submitted.";
  $("#rev-feedback").value = "";

  // Review handlers
  $("#rev-btn-approve").onclick = async () => {
    try {
      const feedback = $("#rev-feedback").value.trim();
      await api(`/tasks/${task.id}/review`, "PATCH", { action: "approve", feedback });
      dlg.close();
      toast("Deliverable approved and marked Completed!");
      await refresh();
    } catch (err) {
      alert(err.message);
    }
  };

  $("#rev-btn-reject").onclick = async () => {
    const feedback = $("#rev-feedback").value.trim();
    if (!feedback) {
      alert("Please provide revision instructions in the Reviewer Comments textarea so the engineer knows what to change.");
      $("#rev-feedback").focus();
      return;
    }
    try {
      await api(`/tasks/${task.id}/review`, "PATCH", { action: "reject", feedback });
      dlg.close();
      toast("Revision requested. Deliverable reverted to In Progress with comments.");
      await refresh();
    } catch (err) {
      alert(err.message);
    }
  };

  dlg.showModal();
}

/* ---------- Task Detail Drawer ---------- */
function openDetail(task) {
  if (!task) return;
  const d = $("#task-detail-dialog");
  if (!d) return;

  $("#det-title").textContent = task.title;
  $("#det-desc").textContent = task.description || "No additional description provided.";
  $("#det-priority").textContent = task.priority;
  $("#det-priority").className = `pill p-${esc(task.priority)}`;
  $("#det-category").textContent = task.category;
  $("#det-category").className = `pill cat c-${esc(task.category)}`;
  $("#det-status").textContent = task.status;
  $("#det-status").className = `pill stat s-${(task.status || "Pending").split(" ")[0]}`;

  $("#det-assignee").textContent = task.assignee_name || "Unassigned";
  $("#det-squad").textContent = task.team_name || "General";
  $("#det-due").textContent = fmtDate(task.due_date);
  $("#det-created").textContent = task.created_at ? new Date(task.created_at).toLocaleString() : "–";

  const tagsWrap = $("#det-tags");
  tagsWrap.innerHTML = task.tags_list && task.tags_list.length
    ? task.tags_list.map(t => `<span class="tag-badge">#${esc(t)}</span>`).join("")
    : `<span style="color:var(--muted); font-size:12px;">No tags</span>`;

  // Proof Section
  const proofSection = $("#det-proof-section");
  const gitWrap = $("#det-git-wrap");
  const fileWrap = $("#det-file-wrap");
  const notesWrap = $("#det-notes-wrap");

  if (task.git_repo_link || task.proof_file_path || task.submission_notes) {
    proofSection.hidden = false;
    if (task.git_repo_link) {
      gitWrap.hidden = false;
      $("#det-git-link").href = task.git_repo_link;
      $("#det-git-text").textContent = task.git_repo_link;
    } else {
      gitWrap.hidden = true;
    }
    if (task.proof_file_path) {
      fileWrap.hidden = false;
      $("#det-file-link").href = task.proof_file_path;
    } else {
      fileWrap.hidden = true;
    }
    if (task.submission_notes) {
      notesWrap.hidden = false;
      $("#det-notes").textContent = task.submission_notes;
    } else {
      notesWrap.hidden = true;
    }
  } else {
    proofSection.hidden = true;
  }

  // Feedback note if revision requested
  const feedbackWrap = $("#det-feedback-wrap");
  if (task.feedback_notes && task.status === "In Progress") {
    feedbackWrap.hidden = false;
    $("#det-feedback").textContent = task.feedback_notes;
  } else {
    feedbackWrap.hidden = true;
  }

  // Action buttons
  const isLeadOrAdmin = state.user && (state.user.role === "Admin" || state.user.role === "Lead" || state.user.is_admin);
  const isAssignee = state.user && (task.assigned_to_id === state.user.id || task.user_id === state.user.id);

  const btnProof = $("#det-btn-proof");
  const btnReview = $("#det-btn-review");
  const btnStart = $("#det-btn-start");

  btnStart.hidden = !(task.status === "Pending" && (isAssignee || isLeadOrAdmin));
  btnStart.onclick = async () => {
    await api(`/tasks/${task.id}/status`, "PATCH", { status: "In Progress" });
    d.close();
    toast("Deliverable started! Status moved to In Progress.");
    await refresh();
  };

  btnProof.hidden = !(task.status === "In Progress" && isAssignee);
  btnProof.onclick = () => {
    d.close();
    openProofDialog(task);
  };

  btnReview.hidden = !(task.status === "In Review" && isLeadOrAdmin);
  btnReview.onclick = () => {
    d.close();
    openReviewDialog(task);
  };

  const canEdit = isLeadOrAdmin || isAssignee || Boolean(task.can_edit);

  const btnEdit = $("#det-btn-edit");
  const btnDelete = $("#det-btn-delete");
  const btnStar = $("#det-btn-star");
  const btnDup = $("#det-btn-dup");

  if (btnEdit) btnEdit.hidden = !canEdit;
  if (btnDelete) btnDelete.hidden = !canEdit;
  if (btnStar) btnStar.hidden = !canEdit;
  if (btnDup) btnDup.hidden = !canEdit;

  if (btnEdit) btnEdit.onclick = () => { d.close(); openDialog(task); };
  if (btnStar) {
    btnStar.textContent = task.is_starred ? "Unstar" : "Star";
    btnStar.onclick = async () => {
      await api(`/tasks/${task.id}/star`, "POST");
      d.close();
      await refresh();
    };
  }
  if (btnDup) {
    btnDup.onclick = async () => {
      await api(`/tasks/${task.id}/duplicate`, "POST");
      d.close();
      toast("Deliverable duplicated.");
      await refresh();
    };
  }
  if (btnDelete) {
    btnDelete.onclick = async () => {
      if (confirm("Delete this deliverable?")) {
        await api(`/tasks/${task.id}`, "DELETE");
        d.close();
        toast("Deliverable deleted.");
        await refresh();
      }
    };
  }

  d.showModal();
}

/* ---------- Main Dashboard Init ---------- */
function dashboard() {
  const shell = $("#app-shell");
  const sidebar = $("#sidebar");

  // Load User Info
  api("/auth/me").then(({ user }) => {
    state.user = user;
    const h = new Date().getHours();
    $("#greeting").textContent = `Good ${h < 12 ? "morning" : h < 18 ? "afternoon" : "evening"}, ${user.name}`;
    $("#avatar").textContent = user.name.slice(0, 1).toUpperCase();
    initTheme(user.theme_preference);

    // Render Role Badge in Top Header
    const roleBadge = $("#user-role-badge");
    if (roleBadge) {
      if (user.role === "Admin" || user.is_admin) {
        roleBadge.textContent = "Admin / Engineering Manager";
        roleBadge.className = "role-badge role-Admin";
      } else if (user.role === "Lead" || user.role === "Team Lead") {
        roleBadge.textContent = `[Team Lead • ${user.team_name || "Squad"}]`;
        roleBadge.className = "role-badge role-Lead";
      } else {
        roleBadge.textContent = `[Employee • ${user.team_name || "Squad"}]`;
        roleBadge.className = "role-badge role-Member";
      }
    }

    // Role-based visibility
    const isLeadOrAdmin = user.role === "Admin" || user.role === "Lead" || user.is_admin;
    const isAdmin = Boolean(user.role === "Admin" || user.is_admin);
    if ($("#nav-review")) $("#nav-review").hidden = !isLeadOrAdmin;
    if ($("#nav-admin")) $("#nav-admin").hidden = !isAdmin;
    if ($("#overview-squad-monitor")) $("#overview-squad-monitor").hidden = !isAdmin;

    // Employee Workspace Toggle Setup
    const empToggleBar = $("#employee-toggle-bar");
    if (empToggleBar) {
      empToggleBar.hidden = isLeadOrAdmin;
      if (!isLeadOrAdmin) {
        const teamMeta = $("#team-meta-name");
        if (teamMeta) teamMeta.textContent = `${user.team_name || "Assigned Squad"}`;
      }
    }

    // Populate profile inputs
    if ($("#prof-name")) $("#prof-name").value = user.name;
    if ($("#prof-email")) $("#prof-email").value = user.email;
    if ($("#prof-role")) $("#prof-role").value = user.role || (user.is_admin ? "Admin" : "Member");

    refresh();
  }).catch(() => {
    location.href = "/";
  });

  // Employee Scope Tabs Listeners
  $("#tab-my-tasks")?.addEventListener("click", () => {
    state.employeeScope = "my";
    $("#tab-my-tasks")?.classList.add("active");
    $("#tab-team-board")?.classList.remove("active");
    filterTasks();
  });
  $("#tab-team-board")?.addEventListener("click", () => {
    state.employeeScope = "team";
    $("#tab-team-board")?.classList.add("active");
    $("#tab-my-tasks")?.classList.remove("active");
    filterTasks();
  });

  // Admin Team Filter Select Change
  $("#admin-team-filter")?.addEventListener("change", e => {
    state.selectedTeamId = e.target.value ? parseInt(e.target.value, 10) : null;
    refresh();
  });

  // Sidebar Collapse Toggle
  const isCollapsed = localStorage.getItem("taskflow_sidebar_collapsed") === "true";
  if (isCollapsed) {
    shell?.classList.add("sidebar-collapsed");
    sidebar?.classList.add("collapsed");
  }
  $("#sidebar-toggle")?.addEventListener("click", () => {
    const collapsed = shell.classList.toggle("sidebar-collapsed");
    sidebar.classList.toggle("collapsed", collapsed);
    localStorage.setItem("taskflow_sidebar_collapsed", collapsed);
  });

  // Mobile Menu Toggle
  $("#mobile-toggle")?.addEventListener("click", () => {
    sidebar.classList.toggle("mobile-open");
  });

  // Navigation Click Handler
  $$("[data-target]").forEach(link => {
    link.onclick = e => {
      e.preventDefault();
      const target = link.dataset.target;
      state.activeTab = target;
      shell.dataset.activeView = target;

      $$("[data-target]").forEach(item => {
        const active = item === link;
        item.classList.toggle("active", active);
        if (active) item.setAttribute("aria-current", "page");
        else item.removeAttribute("aria-current");
      });

      $$("[data-view]").forEach(view => {
        const views = view.dataset.view.split(/\s+/);
        let show = views.includes(target);
        if (view.id === "overview-squad-monitor" && !(state.user?.role === "Admin" || state.user?.is_admin)) {
          show = false;
        }
        view.hidden = !show;
      });

      sidebar.classList.remove("mobile-open");
      updateBreadcrumbs(target);
      filterTasks();
    };
  });

  // View Switcher (List vs Grid)
  const setViewMode = mode => {
    state.viewMode = mode;
    localStorage.setItem("taskflow_view", mode);
    $("#btn-view-list")?.classList.toggle("active", mode === "list");
    $("#btn-view-grid")?.classList.toggle("active", mode === "grid");
    filterTasks();
  };
  $("#btn-view-list")?.addEventListener("click", () => setViewMode("list"));
  $("#btn-view-grid")?.addEventListener("click", () => setViewMode("grid"));
  if (state.viewMode === "grid") setViewMode("grid");

  // Search & Filter Listeners
  let searchTimer;
  $("#f-search")?.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(filterTasks, 200);
  });
  ["#f-status", "#f-priority", "#f-category", "#f-due", "#f-sort"].forEach(s => {
    $(s)?.addEventListener("change", filterTasks);
  });

  // Clear filters button
  $("#btn-clear-filters")?.addEventListener("click", () => {
    if ($("#f-search")) $("#f-search").value = "";
    if ($("#f-status")) $("#f-status").value = "";
    if ($("#f-priority")) $("#f-priority").value = "";
    if ($("#f-category")) $("#f-category").value = "";
    if ($("#f-due")) $("#f-due").value = "";
    if ($("#f-sort")) $("#f-sort").value = "";
    state.selectedDate = null;
    filterTasks();
  });

  // Quick Add Task Form
  $("#quick-add-form")?.addEventListener("submit", async e => {
    e.preventDefault();
    const title = $("#quick-title").value.trim();
    const priority = $("#quick-priority").value;
    if (!title) return;
    try {
      await api("/tasks/", "POST", {
        title,
        priority,
        category: "Frontend",
        team_id: state.selectedTeamId || state.user?.team_id
      });
      $("#quick-title").value = "";
      toast("Deliverable created!");
      await refresh();
    } catch (err) {
      toast(err.message);
    }
  });

  // Modal Dialog Triggers
  $("#add-task")?.addEventListener("click", () => openDialog());
  $("#dlg-cancel")?.addEventListener("click", () => $("#task-dialog").close());
  $("#dlg-close")?.addEventListener("click", () => $("#task-dialog").close());
  $("#det-close")?.addEventListener("click", () => $("#task-detail-dialog").close());
  $("#proof-cancel")?.addEventListener("click", () => $("#proof-dialog").close());
  $("#proof-dlg-close")?.addEventListener("click", () => $("#proof-dialog").close());
  $("#rev-close")?.addEventListener("click", () => $("#review-dialog").close());
  $("#btn-shortcuts")?.addEventListener("click", () => $("#shortcuts-dialog").showModal());
  $("#shortcuts-close")?.addEventListener("click", () => $("#shortcuts-dialog").close());

  // Task Form Submission (Detailed Add/Edit)
  $("#task-form")?.addEventListener("submit", async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const d = Object.fromEntries(fd);
    d.is_starred = Boolean(fd.get("is_starred"));
    if (d.assigned_to_id) d.assigned_to_id = parseInt(d.assigned_to_id, 10);
    if (d.team_id) d.team_id = parseInt(d.team_id, 10);
    else if (state.user?.team_id) d.team_id = state.user.team_id;

    try {
      const isEditing = Boolean(state.editing);
      if (isEditing) {
        await api("/tasks/" + state.editing.id, "PUT", d);
      } else {
        await api("/tasks/", "POST", d);
      }
      $("#task-dialog").close();
      toast(isEditing ? "Deliverable updated." : "Deliverable created.");
      await refresh();
    } catch (err) {
      $("#task-error").textContent = err.message;
    }
  });

  // File Drop Area Handlers for Submit Proof Modal
  const dropArea = $("#proof-drop-area");
  const fileInput = $("#proof-file-input");
  const fileLabel = $("#proof-file-label");

  dropArea?.addEventListener("click", () => fileInput?.click());
  fileInput?.addEventListener("change", () => {
    if (fileInput.files.length) {
      fileLabel.textContent = `Attached: ${fileInput.files[0].name} (${Math.round(fileInput.files[0].size / 1024)} KB)`;
    }
  });
  dropArea?.addEventListener("dragover", e => {
    e.preventDefault();
    dropArea.style.borderColor = "var(--green)";
  });
  dropArea?.addEventListener("dragleave", () => {
    dropArea.style.borderColor = "";
  });
  dropArea?.addEventListener("drop", e => {
    e.preventDefault();
    dropArea.style.borderColor = "";
    if (e.dataTransfer.files.length) {
      fileInput.files = e.dataTransfer.files;
      fileLabel.textContent = `Attached: ${fileInput.files[0].name} (${Math.round(fileInput.files[0].size / 1024)} KB)`;
    }
  });

  // Proof Form Submit Handler (Multipart Form Data)
  $("#proof-form")?.addEventListener("submit", async e => {
    e.preventDefault();
    const taskId = $("#proof-task-id").value;
    const gitLink = $("#proof-git-link").value.trim();
    const notes = $("#proof-notes").value.trim();

    if (!gitLink) {
      $("#proof-error").textContent = "Git PR or commit URL is required.";
      return;
    }
    if (!notes) {
      $("#proof-error").textContent = "Implementation notes are required.";
      return;
    }

    const fd = new FormData();
    fd.append("git_link", gitLink);
    fd.append("notes", notes);
    if (fileInput?.files[0]) {
      fd.append("proof_file", fileInput.files[0]);
    }

    try {
      await api(`/tasks/${taskId}/submit-proof`, "POST", fd);
      $("#proof-dialog").close();
      toast("Proof of work submitted! Deliverable is now In Review.");
      await refresh();
    } catch (err) {
      $("#proof-error").textContent = err.message;
    }
  });

  // Delegate Click Events on Task List & Review Pipeline
  const handleTaskAction = async (act, tid) => {
    const task = state.tasks.find(t => t.id === tid);
    if (!task) return;

    const isLeadOrAdmin = state.user && (state.user.role === "Admin" || state.user.role === "Lead" || state.user.is_admin);
    const canEdit = isLeadOrAdmin || Boolean(task.can_edit) || (state.user && (task.assigned_to_id === state.user.id || task.user_id === state.user.id));

    if (["start", "proof", "toggle", "star"].includes(act) && !canEdit) {
      toast("This deliverable is assigned to a teammate. View-only access.");
      return;
    }

    if (act === "detail") {
      openDetail(task);
    } else if (act === "start") {
      await api(`/tasks/${tid}/status`, "PATCH", { status: "In Progress" });
      toast("Deliverable started! Moved to In Progress.");
      await refresh();
    } else if (act === "proof") {
      openProofDialog(task);
    } else if (act === "review") {
      openReviewDialog(task);
    } else if (act === "toggle") {
      await api(`/tasks/${tid}/complete`, "PATCH");
      await refresh();
    } else if (act === "star") {
      await api(`/tasks/${tid}/star`, "POST");
      await refresh();
    } else if (act === "select") {
      if (state.selectedIds.has(tid)) state.selectedIds.delete(tid);
      else state.selectedIds.add(tid);
      updateBulkBar();
    } else if (act === "menu") {
      openDetail(task);
    }
  };

  $("#task-list")?.addEventListener("click", e => {
    const target = e.target.closest("[data-act]");
    if (!target) return;
    const li = e.target.closest("li[data-id]");
    if (!li) return;
    const tid = parseInt(li.dataset.id, 10);
    const act = target.dataset.act;
    handleTaskAction(act, tid);
  });

  $("#review-pipeline-grid")?.addEventListener("click", e => {
    const target = e.target.closest("[data-act]");
    const card = e.target.closest(".review-card");
    if (!card) return;
    const tid = parseInt(card.dataset.id, 10);
    openReviewDialog(state.tasks.find(t => t.id === tid));
  });

  // Squad Performance Card Action Delegation (Overview & Admin Portal)
  document.addEventListener("click", e => {
    const assignBtn = e.target.closest('[data-act="assign-lead"]');
    if (assignBtn) {
      const teamId = assignBtn.dataset.teamId ? parseInt(assignBtn.dataset.teamId, 10) : null;
      let leadId = assignBtn.dataset.leadId ? parseInt(assignBtn.dataset.leadId, 10) : null;
      if (!leadId && teamId) {
        const leadMember = state.members.find(m => m.team_id === teamId && m.role === "Lead");
        if (leadMember) {
          leadId = leadMember.id;
        } else {
          const t = state.teams.find(tm => tm.id === teamId);
          if (t && t.lead_id) leadId = t.lead_id;
        }
      }
      openDialog(null, leadId, teamId);
      return;
    }

    const filterBtn = e.target.closest('[data-act="filter-squad"]');
    if (filterBtn) {
      const teamId = filterBtn.dataset.teamId ? parseInt(filterBtn.dataset.teamId, 10) : null;
      if (teamId) {
        state.selectedTeamId = teamId;
        const sel = $("#admin-team-filter");
        if (sel) sel.value = String(teamId);
        
        const tasksNav = $('[data-target="tasks"]');
        if (tasksNav) {
          tasksNav.click();
        } else {
          refresh();
        }
      }
      return;
    }
  });

  // Bulk Operations
  const updateBulkBar = () => {
    const bar = $("#bulk-bar");
    const countEl = $("#bulk-selected-count");
    if (!bar) return;
    if (state.selectedIds.size > 0) {
      bar.hidden = false;
      countEl.textContent = `${state.selectedIds.size} deliverable${state.selectedIds.size > 1 ? "s" : ""} selected`;
    } else {
      bar.hidden = true;
    }
  };

  $("#chk-select-all")?.addEventListener("change", e => {
    if (e.target.checked) {
      state.tasks.forEach(t => state.selectedIds.add(t.id));
    } else {
      state.selectedIds.clear();
    }
    filterTasks();
    updateBulkBar();
  });

  $("#btn-bulk-cancel")?.addEventListener("click", () => {
    state.selectedIds.clear();
    const chk = $("#chk-select-all");
    if (chk) chk.checked = false;
    filterTasks();
    updateBulkBar();
  });

  $("#btn-bulk-complete")?.addEventListener("click", async () => {
    const ids = Array.from(state.selectedIds);
    if (!ids.length) return;
    try {
      await api("/tasks/bulk-complete", "POST", { task_ids: ids });
      state.selectedIds.clear();
      updateBulkBar();
      toast(`${ids.length} deliverables completed.`);
      await refresh();
    } catch (err) {
      toast(err.message);
    }
  });

  $("#btn-bulk-delete")?.addEventListener("click", async () => {
    const ids = Array.from(state.selectedIds);
    if (!ids.length) return;
    if (confirm(`Delete ${ids.length} selected deliverables?`)) {
      try {
        await api("/tasks/bulk-delete", "POST", { task_ids: ids });
        state.selectedIds.clear();
        updateBulkBar();
        toast(`${ids.length} deliverables deleted.`);
        await refresh();
      } catch (err) {
        toast(err.message);
      }
    }
  });

  // Calendar click
  $("#mini-cal")?.addEventListener("click", e => {
    const btn = e.target.closest("button[data-date]");
    if (!btn) return;
    state.selectedDate = state.selectedDate === btn.dataset.date ? null : btn.dataset.date;
    loadCalendar();
    filterTasks();
  });

  // Clear Activity
  $("#btn-clear-activity")?.addEventListener("click", async () => {
    if (confirm("Clear all activity history?")) {
      await api("/activity", "DELETE");
      loadActivity();
      toast("Activity history cleared.");
    }
  });

  // Profile update form
  $("#form-profile")?.addEventListener("submit", async e => {
    e.preventDefault();
    const name = $("#prof-name").value.trim();
    if (!name) return;
    try {
      const { user } = await api("/auth/profile", "PUT", { name });
      state.user = user;
      $("#greeting").textContent = `Hello, ${user.name}`;
      $("#avatar").textContent = user.name.slice(0, 1).toUpperCase();
      toast("Profile updated!");
    } catch (err) {
      toast(err.message);
    }
  });

  // Password change form
  $("#form-password")?.addEventListener("submit", async e => {
    e.preventDefault();
    const current = $("#pass-current").value;
    const next = $("#pass-new").value;
    const confirmVal = $("#pass-confirm").value;
    const errEl = $("#pass-error");

    if (next !== confirmVal) {
      errEl.textContent = "New passwords do not match.";
      return;
    }
    try {
      await api("/auth/password", "PUT", { current_password: current, new_password: next });
      $("#form-password").reset();
      errEl.textContent = "";
      toast("Password changed successfully!");
    } catch (err) {
      errEl.textContent = err.message;
    }
  });

  // Admin user table delegation
  $("#admin-user-table")?.addEventListener("click", async e => {
    const btn = e.target.closest("button[data-adm-act]");
    if (!btn) return;
    const uid = btn.dataset.uid;
    const act = btn.dataset.admAct;

    if (act === "toggle") {
      try {
        const res = await api(`/admin/users/${uid}/toggle-admin`, "POST");
        toast(res.message);
        loadAdminPortal();
      } catch (err) {
        toast(err.message);
      }
    } else if (act === "delete") {
      if (confirm(`Are you sure you want to delete user #${uid}? This will delete all their tasks.`)) {
        try {
          const res = await api(`/admin/users/${uid}`, "DELETE");
          toast(res.message);
          loadAdminPortal();
        } catch (err) {
          toast(err.message);
        }
      }
    }
  });

  // Logout
  const doLogout = async () => {
    await api("/auth/logout", "POST");
    location.href = "/";
  };
  $("#btn-logout")?.addEventListener("click", doLogout);
  $("#avatar")?.addEventListener("click", () => {
    const settingsLink = $("a[data-target='settings']");
    if (settingsLink) settingsLink.click();
  });

  // Keyboard Shortcuts
  document.addEventListener("keydown", e => {
    if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) {
      if (e.key === "Escape") document.activeElement.blur();
      return;
    }
    if (e.key === "/") {
      e.preventDefault();
      $("#f-search")?.focus();
    } else if (e.key === "n" || e.key === "N") {
      e.preventDefault();
      openDialog();
    } else if (e.key === "t" || e.key === "T") {
      $("#theme-toggle")?.click();
    } else if (e.key === "[") {
      $("#sidebar-toggle")?.click();
    } else if (e.key === "?") {
      $("#btn-shortcuts")?.click();
    } else if (e.key === "Escape") {
      $$("dialog[open]").forEach(d => d.close());
    }
  });
}

page === "landing" ? landing() : dashboard();
