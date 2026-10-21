const $ = (s, r = document) => r.querySelector(s);
const page = document.body.dataset.page, GID = document.body.dataset.google;
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, method = "GET", body) {
  const res = await fetch("/api" + path, { method, headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && page === "dashboard") location.href = "/";
  if (!res.ok) throw new Error(data.error || "Something went wrong.");
  return data;
}
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.add("show"); setTimeout(() => t.classList.remove("show"), 2200); }

function initGoogle(onDone) {
  const btn = $("#google-btn");
  if (!GID) { const f = $("#google-fallback"); if (f) { f.hidden = false; f.onclick = () => alert("Google sign-in needs GOOGLE_CLIENT_ID set on the server."); } return; }
  const wait = setInterval(() => {
    if (!window.google?.accounts) return;
    clearInterval(wait);
    google.accounts.id.initialize({ client_id: GID, callback: async r => { try { await api("/auth/google", "POST", { credential: r.credential }); onDone(); } catch (e) { alert(e.message); } } });
    google.accounts.id.renderButton(btn, { theme: "outline", size: "large", text: "continue_with" });
  }, 100);
}

/* ---------- Landing ---------- */
function landing() {
  let mode = "login";
  const form = $("#auth-form");
  document.querySelectorAll(".tab").forEach(t => t.onclick = () => {
    mode = t.dataset.mode;
    document.querySelectorAll(".tab").forEach(x => x.classList.toggle("active", x === t));
    $(".signup-only").hidden = mode !== "signup";
    $("#auth-submit").textContent = mode === "signup" ? "Create account" : "Log in";
    $("#auth-error").textContent = "";
  });
  form.onsubmit = async e => {
    e.preventDefault();
    const d = Object.fromEntries(new FormData(form));
    try { await api("/auth/" + mode, "POST", d); location.href = "/dashboard"; }
    catch (err) { $("#auth-error").textContent = err.message; }
  };
  initGoogle(() => location.href = "/dashboard");
}

/* ---------- Dashboard ---------- */
const state = { selectedDate: null, editing: null, tasks: [] };

function greeting(name) {
  const h = new Date().getHours();
  $("#greeting").textContent = `Good ${h < 12 ? "morning" : h < 18 ? "afternoon" : "evening"}, ${name}`;
  $("#avatar").textContent = name.slice(0, 1).toUpperCase();
}

async function loadStats() {
  const s = await api("/dashboard/stats");
  $("#m-total").textContent = s.total; $("#m-progress").textContent = s.in_progress;
  $("#m-completed").textContent = s.completed; $("#m-overdue").textContent = s.overdue;
  $("#t-total").textContent = `↑ ${s.trends.total} this week`;
  $("#t-completed").textContent = `↑ ${s.trends.completed} this week`;
  $("#t-progress").textContent = `${s.in_progress - s.overdue} on schedule`;
  $("#t-overdue").textContent = s.overdue ? "Needs attention" : "All caught up";
  drawDonut(s);
  return s;
}

function drawDonut(s) {
  const onTime = s.in_progress - s.overdue, C = 2 * Math.PI * 46;
  const parts = [[s.completed, "#2E7D32"], [onTime, "#F2B84B"], [s.overdue, "#D9534F"]];
  let off = 0, out = `<circle cx="60" cy="60" r="46" fill="none" stroke="#EEF0F2" stroke-width="14"/>`;
  parts.forEach(([n, col]) => {
    if (!n || !s.total) return;
    const len = n / s.total * C;
    out += `<circle cx="60" cy="60" r="46" fill="none" stroke="${col}" stroke-width="14" stroke-dasharray="${len} ${C - len}" stroke-dashoffset="${-off}" transform="rotate(-90 60 60)"/>`;
    off += len;
  });
  out += `<text x="60" y="66" text-anchor="middle" font-size="22" font-weight="700" fill="#1F2933">${s.percent_complete}%</text>`;
  $("#donut").innerHTML = out;
  $("#l-c").textContent = s.completed; $("#l-p").textContent = onTime; $("#l-o").textContent = s.overdue;
}

function fmtDate(d) { return d ? new Date(d + "T00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "No date"; }

function populateCategories() {
  const categories = [...new Set(state.tasks.map(task => task.category).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
  const select = $("#f-category"), selected = select.value;
  select.replaceChildren(new Option("All categories", ""), ...categories.map(category => new Option(category, category)));
  if (categories.includes(selected)) select.value = selected;
  $("#category-list").innerHTML = categories.length
    ? categories.map(category => `<li>${esc(category)}</li>`).join("")
    : `<li class="empty">No categories yet.</li>`;
}

function localDateString(date) {
  const year = date.getFullYear(), month = String(date.getMonth() + 1).padStart(2, "0");
  return `${year}-${month}-${String(date.getDate()).padStart(2, "0")}`;
}

function filterTasks() {
  const search = $("#f-search").value.trim().toLowerCase();
  const status = $("#f-status").value;
  const priority = $("#f-priority").value;
  const category = $("#f-category").value;
  const due = $("#f-due").value;
  const today = localDateString(new Date());
  const weekEnd = new Date();
  weekEnd.setDate(weekEnd.getDate() + 7);
  const endOfWeek = localDateString(weekEnd);
  const tasks = state.tasks.filter(task => {
    if (search && !`${task.title} ${task.description}`.toLowerCase().includes(search)) return false;
    if (status && task.status.toLowerCase().replaceAll(" ", "_") !== status) return false;
    if (priority && task.priority !== priority) return false;
    if (category && task.category !== category) return false;
    if (state.selectedDate && task.due_date !== state.selectedDate) return false;
    if (due === "today" && task.due_date !== today) return false;
    if (due === "week" && (!task.due_date || task.due_date < today || task.due_date > endOfWeek)) return false;
    return true;
  });
  const list = $("#task-list");
  if (!tasks.length) { list.innerHTML = `<li class="empty">No tasks match. Add a task to get started.</li>`; return; }
  list.innerHTML = tasks.map(t => `
    <li class="task ${t.completed ? "done" : ""}" data-id="${t.id}">
      <button class="check" aria-label="Mark complete" data-act="toggle">${t.completed ? "✓" : ""}</button>
      <div><div class="t-title">${esc(t.title)}</div><div class="t-desc">${esc(t.description)}</div></div>
      <span class="pill p-${esc(t.priority)}">${esc(t.priority)}</span>
      <span class="pill cat c-${esc(t.category)}">${esc(t.category)}</span>
      <span class="due">${fmtDate(t.due_date)}</span>
      <span class="pill stat s-${t.status.split(" ")[0]}">${esc(t.status)}</span>
      <div class="menu"><button aria-label="Task actions" data-act="menu">…</button></div>
    </li>`).join("");
}

async function loadTasks() {
  const { tasks } = await api("/tasks/");
  state.tasks = tasks;
  populateCategories();
  filterTasks();
}

async function loadCalendar() {
  const { due_dates, upcoming } = await api("/dashboard/upcoming");
  const now = new Date(), y = now.getFullYear(), m = now.getMonth();
  $("#cal-title").textContent = now.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  const first = new Date(y, m, 1).getDay(), days = new Date(y, m + 1, 0).getDate();
  let h = "SMTWTFS".split("").map(d => `<b>${d}</b>`).join("") + "<span></span>".repeat(first);
  for (let d = 1; d <= days; d++) {
    const iso = `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    h += `<button data-date="${iso}" class="${d === now.getDate() ? "today" : ""} ${due_dates.includes(iso) ? "has" : ""} ${state.selectedDate === iso ? "sel" : ""}">${d}</button>`;
  }
  $("#mini-cal").innerHTML = h;
  return upcoming;
}

function suggest(stats, upcoming) {
  const tips = [], high = state.tasks.filter(t => t.priority === "High" && !t.completed);
  if (stats.overdue) tips.push(`Reschedule or finish your ${stats.overdue} overdue task${stats.overdue > 1 ? "s" : ""} first.`);
  if (high.length) tips.push(`Finish your high-priority tasks: start with “${high[0].title}”.`);
  const next = upcoming[0];
  if (next && next.due_date !== new Date().toISOString().slice(0, 10)) tips.push(`Consider moving “${next.title}” to today.`);
  if (!tips.length) tips.push(stats.total ? "You're on track. Add your next task when ready." : "Add your first task to get suggestions.");
  $("#suggestions").innerHTML = tips.map(t => `<li>${esc(t)}</li>`).join("");
}

async function refresh() {
  await loadTasks();
  const [stats, upcoming] = await Promise.all([loadStats(), loadCalendar()]);
  suggest(stats, upcoming);
}

function openDialog(task) {
  state.editing = task || null;
  const f = $("#task-form"); f.reset();
  $("#dlg-title").textContent = task ? "Edit task" : "Add task";
  if (task) ["title", "description", "priority", "category", "due_date"].forEach(k => f.elements[k].value = task[k] || "");
  $("#task-error").textContent = "";
  $("#task-dialog").showModal();
}

function dashboard() {
  const shell = $(".shell");
  document.querySelectorAll("[data-target]").forEach(link => link.onclick = e => {
    e.preventDefault();
    const target = link.dataset.target;
    shell.dataset.activeView = target;
    document.querySelectorAll("[data-target]").forEach(item => {
      const active = item === link;
      item.classList.toggle("active", active);
      if (active) item.setAttribute("aria-current", "page");
      else item.removeAttribute("aria-current");
    });
    document.querySelectorAll("[data-view]").forEach(view => {
      view.hidden = !view.dataset.view.split(/\s+/).includes(target);
    });
  });
  api("/auth/me").then(({ user }) => greeting(user.username));
  refresh();
  let timer;
  ["#f-search"].forEach(s => $(s).oninput = () => { clearTimeout(timer); timer = setTimeout(filterTasks, 250); });
  ["#f-status", "#f-priority", "#f-category", "#f-due"].forEach(s => $(s).onchange = filterTasks);
  $("#add-task").onclick = () => openDialog();
  $("#dlg-cancel").onclick = () => $("#task-dialog").close();
  $("#avatar").onclick = async () => { await api("/auth/logout", "POST"); location.href = "/"; };
  document.querySelectorAll("[data-soon]").forEach(a => a.onclick = e => { e.preventDefault(); toast("Coming soon."); });

  $("#task-form").onsubmit = async e => {
    e.preventDefault();
    const d = Object.fromEntries(new FormData(e.target));
    try {
      const editing = Boolean(state.editing);
      editing ? await api("/tasks/" + state.editing.id, "PUT", d) : await api("/tasks/", "POST", d);
      $("#task-dialog").close(); toast(editing ? "Task saved." : "Task added."); await refresh();
    } catch (err) { $("#task-error").textContent = err.message; }
  };

  $("#mini-cal").onclick = e => {
    const b = e.target.closest("button[data-date]"); if (!b) return;
    state.selectedDate = state.selectedDate === b.dataset.date ? null : b.dataset.date;
    document.querySelectorAll("#mini-cal .sel").forEach(x => x.classList.remove("sel"));
    if (state.selectedDate) b.classList.add("sel");
    filterTasks();
  };

  $("#task-list").onclick = async e => {
    const btn = e.target.closest("button[data-act]"), li = e.target.closest(".task");
    document.querySelectorAll(".menu-pop").forEach(m => m.remove());
    if (!btn || !li) return;
    const id = li.dataset.id;
    if (btn.dataset.act === "toggle") { await api(`/tasks/${id}/complete`, "PATCH"); refresh(); }
    else if (btn.dataset.act === "menu") {
      const pop = document.createElement("div"); pop.className = "menu-pop";
      pop.innerHTML = `<button data-act="edit">Edit</button><button data-act="delete">Delete</button>`;
      btn.parentElement.append(pop); e.stopPropagation();
    } else if (btn.dataset.act === "edit") openDialog(state.tasks.find(t => t.id == id));
    else if (btn.dataset.act === "delete" && confirm("Delete this task?")) { await api("/tasks/" + id, "DELETE"); toast("Task deleted."); await refresh(); }
  };
  document.addEventListener("click", e => { if (!e.target.closest(".menu")) document.querySelectorAll(".menu-pop").forEach(m => m.remove()); });
  initGoogle(() => location.reload());
}

page === "landing" ? landing() : dashboard();
