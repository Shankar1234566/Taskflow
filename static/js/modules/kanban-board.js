/**
 * Taskflow Enterprise Kanban Board Controller.
 * Handles drag-and-drop task movements, WIP column limits, swimlanes, and rapid status updating.
 */

class TaskflowKanbanBoard {
  constructor(options = {}) {
    this.containerId = options.containerId || "kanban-board-container";
    this.columns = options.columns || [
      { id: "Pending", title: "Pending Backlog", limit: 10 },
      { id: "In Progress", title: "In Progress", limit: 5 },
      { id: "In Review", title: "Under Review", limit: 4 },
      { id: "Completed", title: "Completed / Done", limit: 0 }
    ];
    this.onTaskMove = options.onTaskMove || (() => {});
    this.tasks = [];
    this.draggedTaskId = null;
  }

  init(tasks = []) {
    this.tasks = [...tasks];
    this.render();
  }

  render() {
    const root = document.getElementById(this.containerId);
    if (!root) return;

    root.innerHTML = "";
    root.className = "kanban-board-grid";

    this.columns.forEach(col => {
      const colEl = document.createElement("div");
      colEl.className = "kanban-column";
      colEl.dataset.status = col.id;

      const colTasks = this.tasks.filter(t => (t.status || "Pending") === col.id);
      const isOverWip = col.limit > 0 && colTasks.length > col.limit;

      colEl.innerHTML = `
        <div class="kanban-column-header ${isOverWip ? 'wip-exceeded' : ''}">
          <div class="column-title-group">
            <span class="column-name">${col.title}</span>
            <span class="column-count">${colTasks.length}${col.limit ? ` / ${col.limit}` : ''}</span>
          </div>
        </div>
        <div class="kanban-cards-dropzone" data-status="${col.id}"></div>
      `;

      const dropzone = colEl.querySelector(".kanban-cards-dropzone");

      // Bind drag over events
      dropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropzone.classList.add("drag-hover");
      });

      dropzone.addEventListener("dragleave", () => {
        dropzone.classList.remove("drag-hover");
      });

      dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropzone.classList.remove("drag-hover");
        if (this.draggedTaskId) {
          this.handleDrop(this.draggedTaskId, col.id);
        }
      });

      colTasks.forEach(task => {
        const card = this.createCardElement(task);
        dropzone.appendChild(card);
      });

      root.appendChild(colEl);
    });
  }

  createCardElement(task) {
    const card = document.createElement("div");
    card.className = `kanban-card priority-${(task.priority || 'medium').toLowerCase()}`;
    card.draggable = true;
    card.dataset.id = task.id;

    card.innerHTML = `
      <div class="card-meta">
        <span class="card-category">${task.category || 'General'}</span>
        <span class="badge priority-${(task.priority || 'medium').toLowerCase()}">${task.priority}</span>
      </div>
      <div class="card-title">#${task.id} ${task.title}</div>
      <div class="card-footer">
        <span class="card-due">${task.due_date ? `📅 ${task.due_date}` : 'Flexible'}</span>
        ${task.is_starred ? '<span class="star-icon">★</span>' : ''}
      </div>
    `;

    card.addEventListener("dragstart", () => {
      this.draggedTaskId = task.id;
      card.classList.add("dragging");
    });

    card.addEventListener("dragend", () => {
      this.draggedTaskId = null;
      card.classList.remove("dragging");
    });

    return card;
  }

  handleDrop(taskId, newStatus) {
    const task = this.tasks.find(t => t.id === taskId);
    if (!task || task.status === newStatus) return;

    task.status = newStatus;
    this.render();
    this.onTaskMove(taskId, newStatus);
  }
}

window.TaskflowKanbanBoard = TaskflowKanbanBoard;
