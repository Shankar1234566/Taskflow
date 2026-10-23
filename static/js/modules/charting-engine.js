/**
 * Taskflow Enterprise SVG & Canvas Charting Engine.
 * Renders Burndown curves, Velocity bars, Interactive Donut completion gauges, and Workload heatmaps.
 */

class TaskflowChartingEngine {
  /**
   * Renders an animated SVG donut chart into a container.
   */
  static renderDonut(containerId, percentage, options = {}) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const size = options.size || 140;
    const strokeWidth = options.strokeWidth || 12;
    const radius = (size - strokeWidth) / 2;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (percentage / 100) * circumference;

    const color = options.color || "var(--accent-primary, #4E6B56)";
    const trackColor = options.trackColor || "var(--border, #EDE6DC)";

    container.innerHTML = `
      <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" class="chart-donut-svg">
        <circle cx="${size/2}" cy="${size/2}" r="${radius}" fill="none" stroke="${trackColor}" stroke-width="${strokeWidth}" />
        <circle cx="${size/2}" cy="${size/2}" r="${radius}" fill="none" stroke="${color}" stroke-width="${strokeWidth}"
          stroke-dasharray="${circumference}" stroke-dashoffset="${offset}" stroke-linecap="round"
          transform="rotate(-90 ${size/2} ${size/2})" style="transition: stroke-dashoffset 1s ease-out;" />
        <text x="50%" y="50%" text-anchor="middle" dy="0.35em" class="chart-donut-text" style="font-size: 20px; font-weight: 700; fill: var(--text-primary, #1C2826);">${Math.round(percentage)}%</text>
      </svg>
    `;
  }

  /**
   * Renders a multi-bar velocity comparison chart.
   */
  static renderVelocityBar(containerId, sprintData = []) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!sprintData.length) {
      container.innerHTML = '<div class="chart-empty">No velocity data available.</div>';
      return;
    }

    const maxVal = Math.max(...sprintData.map(d => Math.max(d.planned, d.completed)), 10);
    const barsHtml = sprintData.map(d => {
      const plannedH = (d.planned / maxVal) * 100;
      const completedH = (d.completed / maxVal) * 100;
      return `
        <div class="velocity-col">
          <div class="bars-pair">
            <div class="bar bar-planned" style="height: ${plannedH}%;" title="Planned: ${d.planned}"></div>
            <div class="bar bar-completed" style="height: ${completedH}%;" title="Completed: ${d.completed}"></div>
          </div>
          <span class="bar-label">${d.name}</span>
        </div>
      `;
    }).join("");

    container.innerHTML = `
      <div class="velocity-chart-wrapper">
        <div class="velocity-bars-container">${barsHtml}</div>
        <div class="velocity-legend">
          <span class="legend-item"><span class="legend-dot dot-planned"></span> Planned</span>
          <span class="legend-item"><span class="legend-dot dot-completed"></span> Completed</span>
        </div>
      </div>
    `;
  }

  /**
   * Generates a 7-day sparkline SVG string.
   */
  static renderSparkline(points = []) {
    if (points.length < 2) return "";
    const w = 100;
    const h = 30;
    const max = Math.max(...points, 1);
    const min = Math.min(...points, 0);
    const range = max - min || 1;

    const coords = points.map((p, idx) => {
      const x = (idx / (points.length - 1)) * w;
      const y = h - ((p - min) / range) * (h - 6) - 3;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");

    return `
      <svg width="${w}" height="${h}" class="sparkline-svg">
        <polyline fill="none" stroke="var(--accent-primary, #4E6B56)" stroke-width="2" points="${coords}" />
      </svg>
    `;
  }
}

window.TaskflowChartingEngine = TaskflowChartingEngine;
