const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const page = document.body.dataset.page, GID = document.body.dataset.google;

const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
}[c]));

async function api(path, method = "GET", body) {
  const res = await fetch("/api" + path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined
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
  toastTimer = setTimeout(() => t.classList.remove("show"), 2800);
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
  $$(".tab").forEach(t => t.onclick = () => {
    mode = t.dataset.mode;
    $$(".tab").forEach(x => x.classList.toggle("active", x === t));
    $(".signup-only").hidden = mode !== "signup";
    $("#auth-submit").textContent = mode === "signup" ? "Create account" : "Log in";
    $("#auth-error").textContent = "";
  });
  if (form) {
    form.onsubmit = async e => {
      e.preventDefault();
      const d = Object.fromEntries(new FormData(form));
      try {
        await api("/auth/" + mode, "POST", d);
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
  tasks: [],
  selectedDate: null,
  editing: null,
  viewMode: localStorage.getItem("taskflow_view") || "list",
  selectedIds: new Set(),
  activeTab: "overview",
  lastDeletedTask: null
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

  if ($("#badge-today")) $("#badge-today").textContent = countToday;
  if ($("#badge-starred")) $("#badge-starred").textContent = countStarred;
  if ($("#badge-total")) $("#badge-total").textContent = countTotal;
}

/* ---------- Donut Chart ---------- */
function drawDonut(s) {
  const onTime = Math.max(0, s.in_progress - s.overdue), C = 2 * Math.PI * 46;
  const parts = [[s.completed, "#2E7D32"], [onTime, "#F2B84B"], [s.overdue, "#D9534F"]];
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
  if ($("#l-p")) $("#l-p").textContent = onTime;
  if ($("#l-o")) $("#l-o").textContent = s.overdue;
}

/* ---------- Stats & Assistant ---------- */
async function loadStats() {
  const s = await api("/dashboard/stats");
  if ($("#m-total")) $("#m-total").textContent = s.total;
  if ($("#m-progress")) $("#m-progress").textContent = s.in_progress;
  if ($("#m-completed")) $("#m-completed").textContent = s.completed;
  if ($("#m-overdue")) $("#m-overdue").textContent = s.overdue;
  if ($("#t-total")) $("#t-total").textContent = `↑ ${s.trends.total} this week`;
  if ($("#t-completed")) $("#t-completed").textContent = `↑ ${s.trends.completed} this week`;
  if ($("#t-progress")) $("#t-progress").textContent = `${Math.max(0, s.in_progress - s.overdue)} on schedule`;
  if ($("#t-overdue")) $("#t-overdue").textContent = s.overdue ? "Needs attention" : "All caught up";
  drawDonut(s);
  renderCategoryBreakdown(s.categories || []);
  return s;
}

function renderCategoryBreakdown(categories) {
  const grid = $("#categories-grid");
  if (!grid) return;
  if (!categories.length) {
    grid.innerHTML = `<div class="empty">No category data available yet. Add tasks to see breakdown.</div>`;
    return;
  }
  grid.innerHTML = categories.map(c => `
    <div class="cat-card">
      <h4>${esc(c.name)}</h4>
      <div class="cat-bar-wrap"><div class="cat-bar" style="width: ${c.percent}%"></div></div>
      <div class="cat-stats">
        <span>${c.completed} / ${c.total} completed</span>
        <b>${c.percent}%</b>
      </div>
    </div>
  `).join("");
}

function suggest(stats, upcoming) {
  const tips = [];
  const critical = state.tasks.filter(t => t.priority === "Critical" && !t.completed);
  const high = state.tasks.filter(t => t.priority === "High" && !t.completed);
  
  if (critical.length) tips.push(`CRITICAL: Finish urgent priority task “${critical[0].title}” immediately.`);
  if (stats.overdue) tips.push(`You have ${stats.overdue} overdue task${stats.overdue > 1 ? "s" : ""}. Reschedule or finish them first.`);
  if (high.length && !critical.length) tips.push(`Focus on high-priority task: “${high[0].title}”.`);
  const next = upcoming && upcoming[0];
  if (next && next.due_date !== localDateString(new Date())) tips.push(`Upcoming deadline: “${next.title}” due on ${fmtDate(next.due_date)}.`);
  if (!tips.length) tips.push(stats.total ? "All tasks are on track! Great momentum." : "Add your first task to activate AI productivity recommendations.");
  
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
    if (state.activeTab === "today" && (task.completed || task.due_date !== today)) return false;
    if (state.activeTab === "upcoming" && (task.completed || !task.due_date || task.due_date < today)) return false;
    if (state.activeTab === "starred" && !task.is_starred) return false;
    if (state.activeTab === "completed" && !task.completed) return false;

    // Search query (title, description, tags)
    if (search) {
      const matchText = `${task.title} ${task.description} ${task.tags}`.toLowerCase();
      if (!matchText.includes(search)) return false;
    }

    // Dropdown filters
    if (status && task.status.toLowerCase().replaceAll(" ", "_") !== status) return false;
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

  renderTaskList(tasks);
}

function renderTaskList(tasks) {
  const list = $("#task-list");
  if (!list) return;

  list.className = `task-list view-${state.viewMode}`;

  if (!tasks.length) {
    list.innerHTML = `<li class="empty">No tasks found. Use the quick-add bar above to create one!</li>`;
    return;
  }

  if (state.viewMode === "grid") {
    list.innerHTML = tasks.map(t => `
      <li class="task ${t.completed ? "done" : ""}" data-id="${t.id}">
        <div class="task-head">
          <input type="checkbox" class="task-chk" data-act="select" ${state.selectedIds.has(t.id) ? "checked" : ""}>
          <button class="star-btn ${t.is_starred ? "starred" : ""}" data-act="star" title="Star task">★</button>
          <span class="pill p-${esc(t.priority)}">${esc(t.priority)}</span>
          <div class="menu">
            <button aria-label="Task actions" data-act="menu">…</button>
          </div>
        </div>
        <div class="task-body">
          <div class="t-title" data-act="detail">${esc(t.title)}</div>
          <div class="t-desc">${esc(t.description || "No description")}</div>
          ${t.tags_list && t.tags_list.length ? `<div class="t-tags">${t.tags_list.map(tag => `<span class="tag-badge">#${esc(tag)}</span>`).join("")}</div>` : ""}
        </div>
        <div class="task-foot">
          <span class="due">${fmtDate(t.due_date)}${t.due_time ? " " + esc(t.due_time) : ""}</span>
          <span class="pill cat c-${esc(t.category)}">${esc(t.category)}</span>
          <button class="check" data-act="toggle" title="Toggle complete">${t.completed ? "✓" : ""}</button>
        </div>
      </li>
    `).join("");
  } else {
    list.innerHTML = tasks.map(t => `
      <li class="task ${t.completed ? "done" : ""}" data-id="${t.id}">
        <input type="checkbox" class="task-chk" data-act="select" ${state.selectedIds.has(t.id) ? "checked" : ""}>
        <button class="check" aria-label="Mark complete" data-act="toggle">${t.completed ? "✓" : ""}</button>
        <button class="star-btn ${t.is_starred ? "starred" : ""}" data-act="star" title="Star task">★</button>
        <div>
          <div class="t-title" data-act="detail">${esc(t.title)}</div>
          <div class="t-desc">${esc(t.description)}</div>
          ${t.tags_list && t.tags_list.length ? `<div class="t-tags">${t.tags_list.map(tag => `<span class="tag-badge">#${esc(tag)}</span>`).join("")}</div>` : ""}
        </div>
        <span class="pill p-${esc(t.priority)}">${esc(t.priority)}</span>
        <span class="pill cat c-${esc(t.category)}">${esc(t.category)}</span>
        <span class="due">${fmtDate(t.due_date)}${t.due_time ? " " + esc(t.due_time) : ""}</span>
        <span class="pill stat s-${t.status.split(" ")[0]}">${esc(t.status)}</span>
        <div class="menu"><button aria-label="Task actions" data-act="menu">…</button></div>
      </li>
    `).join("");
  }
}

async function loadTasks() {
  const { tasks } = await api("/tasks/");
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

/* ---------- Admin Dashboard ---------- */
async function loadAdminPortal() {
  if (!state.user || !state.user.is_admin) return;
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
          <td><span class="pill ${u.is_admin ? "p-Critical" : "s-In"}">${u.is_admin ? "Administrator" : "Standard"}</span></td>
          <td>${u.completed_count} / ${u.task_count}</td>
          <td>${u.created_at ? new Date(u.created_at).toLocaleDateString() : "–"}</td>
          <td>
            ${u.id !== state.user.id ? `
              <button class="btn btn-sm ghost" data-adm-act="toggle" data-uid="${u.id}">${u.is_admin ? "Demote" : "Promote"}</button>
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

/* ---------- Refresh View ---------- */
async function refresh() {
  await loadTasks();
  const [stats, upcoming] = await Promise.all([loadStats(), loadCalendar()]);
  suggest(stats, upcoming);
  loadActivity();
  if (state.user && state.user.is_admin) loadAdminPortal();
}

/* ---------- Task Dialog Modal ---------- */
function openDialog(task = null) {
  state.editing = task || null;
  const f = $("#task-form");
  if (!f) return;
  f.reset();
  $("#dlg-title").textContent = task ? "Edit Task" : "Add Task";
  if (task) {
    ["title", "description", "priority", "category", "due_date", "due_time", "tags"].forEach(k => {
      if (f.elements[k]) f.elements[k].value = task[k] || "";
    });
    if (f.elements["is_starred"]) f.elements["is_starred"].checked = Boolean(task.is_starred);
  }
  $("#task-error").textContent = "";
  $("#task-dialog").showModal();
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
  $("#det-status").className = `pill stat s-${task.status.split(" ")[0]}`;

  $("#det-due").textContent = fmtDate(task.due_date);
  $("#det-time").textContent = task.due_time || "Not specified";
  $("#det-created").textContent = task.created_at ? new Date(task.created_at).toLocaleString() : "–";
  $("#det-completed").textContent = task.completed_at ? new Date(task.completed_at).toLocaleString() : (task.completed ? "Yes" : "In Progress");

  const tagsWrap = $("#det-tags");
  tagsWrap.innerHTML = task.tags_list && task.tags_list.length
    ? task.tags_list.map(t => `<span class="tag-badge">#${esc(t)}</span>`).join("")
    : `<span style="color:var(--muted); font-size:12px;">No tags</span>`;

  $("#det-btn-edit").onclick = () => { d.close(); openDialog(task); };
  $("#det-btn-star").textContent = task.is_starred ? "Unstar Task" : "Star Task";
  $("#det-btn-star").onclick = async () => {
    await api(`/tasks/${task.id}/star`, "POST");
    d.close();
    await refresh();
  };
  $("#det-btn-dup").onclick = async () => {
    await api(`/tasks/${task.id}/duplicate`, "POST");
    d.close();
    toast("Task duplicated.");
    await refresh();
  };
  $("#det-btn-delete").onclick = async () => {
    if (confirm("Delete this task?")) {
      await api(`/tasks/${task.id}`, "DELETE");
      d.close();
      toast("Task deleted.");
      await refresh();
    }
  };

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

    // Populate profile inputs
    if ($("#prof-name")) $("#prof-name").value = user.name;
    if ($("#prof-email")) $("#prof-email").value = user.email;
    if ($("#prof-role")) $("#prof-role").value = user.is_admin ? "Administrator" : "Standard User";

    // Show Admin Link if user has admin rights
    if (user.is_admin && $("#nav-admin")) {
      $("#nav-admin").hidden = false;
    }
    refresh();
  }).catch(() => {
    location.href = "/";
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
        view.hidden = !views.includes(target);
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
      await api("/tasks/", "POST", { title, priority });
      $("#quick-title").value = "";
      toast("Task created!");
      await refresh();
    } catch (err) {
      toast(err.message);
    }
  });

  // Modal Dialogs
  $("#add-task")?.addEventListener("click", () => openDialog());
  $("#dlg-cancel")?.addEventListener("click", () => $("#task-dialog").close());
  $("#dlg-close")?.addEventListener("click", () => $("#task-dialog").close());
  $("#det-close")?.addEventListener("click", () => $("#task-detail-dialog").close());
  $("#btn-shortcuts")?.addEventListener("click", () => $("#shortcuts-dialog").showModal());
  $("#shortcuts-close")?.addEventListener("click", () => $("#shortcuts-dialog").close());

  // Task Form Submission (Detailed Add/Edit)
  $("#task-form")?.addEventListener("submit", async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const d = Object.fromEntries(fd);
    d.is_starred = Boolean(fd.get("is_starred"));
    try {
      const isEditing = Boolean(state.editing);
      if (isEditing) {
        await api("/tasks/" + state.editing.id, "PUT", d);
      } else {
        await api("/tasks/", "POST", d);
      }
      $("#task-dialog").close();
      toast(isEditing ? "Task updated." : "Task created.");
      await refresh();
    } catch (err) {
      $("#task-error").textContent = err.message;
    }
  });

  // Bulk Operations
  const updateBulkBar = () => {
    const bar = $("#bulk-bar");
    const countEl = $("#bulk-selected-count");
    if (!bar) return;
    if (state.selectedIds.size > 0) {
      bar.hidden = false;
      countEl.textContent = `${state.selectedIds.size} task${state.selectedIds.size > 1 ? "s" : ""} selected`;
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
      toast(`${ids.length} tasks completed.`);
      await refresh();
    } catch (err) {
      toast(err.message);
    }
  });

  $("#btn-bulk-delete")?.addEventListener("click", async () => {
    const ids = Array.from(state.selectedIds);
    if (!ids.length) return;
    if (confirm(`Delete ${ids.length} selected tasks?`)) {
      try {
        await api("/tasks/bulk-delete", "POST", { task_ids: ids });
        state.selectedIds.clear();
        updateBulkBar();
        toast(`${ids.length} tasks deleted.`);
        await refresh();
      } catch (err) {
        toast(err.message);
      }
    }
  });

  // Task List Delegation
  $("#task-list")?.addEventListener("click", async e => {
    const btn = e.target.closest("button[data-act], [data-act='detail'], input[data-act='select']");
    const li = e.target.closest(".task");
    $$(".menu-pop").forEach(m => m.remove());
    if (!btn || !li) return;

    const id = parseInt(li.dataset.id, 10);
    const task = state.tasks.find(t => t.id === id);
    if (!task) return;

    const act = btn.dataset.act;

    if (act === "select") {
      if (btn.checked) state.selectedIds.add(id);
      else state.selectedIds.delete(id);
      updateBulkBar();
    } else if (act === "toggle") {
      await api(`/tasks/${id}/complete`, "PATCH");
      await refresh();
    } else if (act === "star") {
      await api(`/tasks/${id}/star`, "POST");
      await refresh();
    } else if (act === "detail") {
      openDetail(task);
    } else if (act === "menu") {
      const pop = document.createElement("div");
      pop.className = "menu-pop";
      pop.innerHTML = `
        <button data-pop-act="edit">Edit</button>
        <button data-pop-act="star">${task.is_starred ? "Unstar" : "Star"}</button>
        <button data-pop-act="duplicate">Duplicate</button>
        <button data-pop-act="delete" class="danger">Delete</button>
      `;
      btn.parentElement.append(pop);
      e.stopPropagation();

      pop.onclick = async pe => {
        const pact = pe.target.dataset.popAct;
        pop.remove();
        if (pact === "edit") {
          openDialog(task);
        } else if (pact === "star") {
          await api(`/tasks/${id}/star`, "POST");
          await refresh();
        } else if (pact === "duplicate") {
          await api(`/tasks/${id}/duplicate`, "POST");
          toast("Task duplicated.");
          await refresh();
        } else if (pact === "delete" && confirm("Delete this task?")) {
          state.lastDeletedTask = task;
          await api(`/tasks/${id}`, "DELETE");
          toast("Task deleted.", async () => {
            if (state.lastDeletedTask) {
              await api("/tasks/", "POST", state.lastDeletedTask);
              refresh();
            }
          });
          await refresh();
        }
      };
    }
  });

  document.addEventListener("click", e => {
    if (!e.target.closest(".menu")) $$(".menu-pop").forEach(m => m.remove());
  });

  // Calendar click
  $("#mini-cal")?.addEventListener("click", e => {
    const b = e.target.closest("button[data-date]");
    if (!b) return;
    state.selectedDate = state.selectedDate === b.dataset.date ? null : b.dataset.date;
    $$("#mini-cal .sel").forEach(x => x.classList.remove("sel"));
    if (state.selectedDate) b.classList.add("sel");

    // Update calendar inspector
    const inspectorTitle = $("#cal-inspector-title");
    const inspectorList = $("#cal-inspector-list");
    if (inspectorTitle && inspectorList) {
      if (state.selectedDate) {
        const dayTasks = state.tasks.filter(t => t.due_date === state.selectedDate);
        inspectorTitle.textContent = `Tasks for ${fmtDate(state.selectedDate)} (${dayTasks.length})`;
        inspectorList.innerHTML = dayTasks.length
          ? dayTasks.map(t => `<li class="task" style="padding:8px 0;"><div><b>${esc(t.title)}</b> (${esc(t.priority)})</div></li>`).join("")
          : `<li class="empty" style="padding:12px 0;">No tasks scheduled on this date.</li>`;
      } else {
        inspectorTitle.textContent = "Select a day to inspect tasks";
        inspectorList.innerHTML = "";
      }
    }
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
    // Avoid triggering when in input or textarea
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
