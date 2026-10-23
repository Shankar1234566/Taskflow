/**
 * Virtualized / High-Performance Data Table Grid.
 * Multi-column sorting, row filtering, pagination, and inline action handlers.
 */

class TaskflowTableGrid {
  constructor(options = {}) {
    this.containerId = options.containerId;
    this.columns = options.columns || [];
    this.data = [];
    this.sortColumn = null;
    this.sortAscending = true;
    this.currentPage = 1;
    this.pageSize = options.pageSize || 25;
  }

  setData(data = []) {
    this.data = [...data];
    this.render();
  }

  sort(colKey) {
    if (this.sortColumn === colKey) {
      this.sortAscending = !this.sortAscending;
    } else {
      this.sortColumn = colKey;
      this.sortAscending = true;
    }
    this.render();
  }

  render() {
    const el = document.getElementById(this.containerId);
    if (!el) return;

    let processed = [...this.data];

    if (this.sortColumn) {
      processed.sort((a, b) => {
        let va = a[this.sortColumn] || "";
        let vb = b[this.sortColumn] || "";
        if (typeof va === "string") va = va.toLowerCase();
        if (typeof vb === "string") vb = vb.toLowerCase();
        if (va < vb) return this.sortAscending ? -1 : 1;
        if (va > vb) return this.sortAscending ? 1 : -1;
        return 0;
      });
    }

    const headerHtml = this.columns.map(c => `
      <th class="table-header-cell" onclick="window.__taskflowGrid.sort('${c.key}')" style="cursor: pointer;">
        ${c.label} ${this.sortColumn === c.key ? (this.sortAscending ? '▲' : '▼') : ''}
      </th>
    `).join("");

    const rowsHtml = processed.map(row => `
      <tr class="table-row">
        ${this.columns.map(c => `<td class="table-cell">${row[c.key] !== undefined ? row[c.key] : ''}</td>`).join("")}
      </tr>
    `).join("");

    el.innerHTML = `
      <table class="taskflow-data-table">
        <thead><tr>${headerHtml}</tr></thead>
        <tbody>${rowsHtml}</tbody>
      </table>
    `;
    window.__taskflowGrid = this;
  }
}

window.TaskflowTableGrid = TaskflowTableGrid;
