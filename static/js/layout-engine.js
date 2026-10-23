/**
 * TASKFLOW LAYOUT RESILIENCE & ACCESSIBILITY CONTROLLER
 * static/js/layout-engine.js
 *
 * Enterprise client-side layout management:
 * 1. Modal & slide-over drawer focus trapping and keyboard navigation (Tab, Shift+Tab, Escape).
 * 2. Dynamic scrollbar gutter compensation preventing body layout jump.
 * 3. Text truncation tooltip observer (scrollWidth > clientWidth detection).
 * 4. Table density mode controller (compact vs comfortable) with localStorage persistence.
 * 5. Safe mobile drawer navigation controller (isolated backdrop outside grid).
 */

(function () {
  'use strict';

  const LayoutEngine = {
    activeModal: null,
    lastFocusedElement: null,
    tooltipElement: null,
    densityStorageKey: 'taskflow_table_density',

    init() {
      this.initScrollbarCompensation();
      this.initModalFocusTrapping();
      this.initTruncationObserver();
      this.initTableDensityController();
      this.initMobileDrawer();
    },

    /* ==========================================================================
       1. DYNAMIC SCROLLBAR GUTTER COMPENSATION
       ========================================================================== */
    initScrollbarCompensation() {
      this.createGlobalTooltip();
    },

    lockBodyScroll() {
      const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth;
      if (scrollbarWidth > 0) {
        document.documentElement.style.setProperty('--scrollbar-compensation', `${scrollbarWidth}px`);
      }
      document.body.classList.add('scroll-locked');
    },

    unlockBodyScroll() {
      document.body.classList.remove('scroll-locked');
      document.documentElement.style.setProperty('--scrollbar-compensation', '0px');
    },

    /* ==========================================================================
       2. MODAL & DRAWER FOCUS TRAPPING & KEYBOARD ACCESSIBILITY
       ========================================================================== */
    initModalFocusTrapping() {
      const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
          if (mutation.type === 'attributes' && mutation.attributeName === 'open') {
            const target = mutation.target;
            if (target.tagName === 'DIALOG') {
              if (target.hasAttribute('open')) {
                this.onModalOpened(target);
              } else {
                this.onModalClosed(target);
              }
            }
          }
        });
      });

      document.querySelectorAll('dialog').forEach((dialog) => {
        observer.observe(dialog, { attributes: true });

        // Native backdrop click to close
        dialog.addEventListener('click', (e) => {
          const rect = dialog.getBoundingClientRect();
          const isInDialog = (
            rect.top <= e.clientY &&
            e.clientY <= rect.top + rect.height &&
            rect.left <= e.clientX &&
            e.clientX <= rect.left + rect.width
          );
          if (!isInDialog) {
            dialog.close();
          }
        });
      });

      // Global keyboard navigation trap
      document.addEventListener('keydown', (e) => {
        if (!this.activeModal) return;

        if (e.key === 'Escape') {
          e.preventDefault();
          this.activeModal.close();
          return;
        }

        if (e.key === 'Tab') {
          this.trapFocus(e, this.activeModal);
        }
      });
    },

    onModalOpened(dialog) {
      this.activeModal = dialog;
      this.lastFocusedElement = document.activeElement;
      this.lockBodyScroll();

      // Focus first actionable element
      const focusable = dialog.querySelectorAll(
        'button, [href], input:not([type="hidden"]), select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      if (focusable.length > 0) {
        setTimeout(() => focusable[0].focus(), 50);
      }
    },

    onModalClosed(dialog) {
      if (this.activeModal === dialog) {
        this.activeModal = null;
      }
      this.unlockBodyScroll();

      // Return focus to previous trigger
      if (this.lastFocusedElement && typeof this.lastFocusedElement.focus === 'function') {
        this.lastFocusedElement.focus();
      }
    },

    trapFocus(e, dialog) {
      const focusableElements = dialog.querySelectorAll(
        'button:not([disabled]), [href], input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      );
      if (focusableElements.length === 0) return;

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === firstElement) {
          e.preventDefault();
          lastElement.focus();
        }
      } else {
        if (document.activeElement === lastElement) {
          e.preventDefault();
          firstElement.focus();
        }
      }
    },

    /* ==========================================================================
       3. TEXT TRUNCATION OBSERVER & DYNAMIC TOOLTIPS
       ========================================================================== */
    createGlobalTooltip() {
      let tip = document.getElementById('taskflow-global-tooltip');
      if (!tip) {
        tip = document.createElement('div');
        tip.id = 'taskflow-global-tooltip';
        tip.className = 'taskflow-tooltip';
        tip.setAttribute('role', 'tooltip');
        tip.setAttribute('aria-hidden', 'true');
        document.body.appendChild(tip);

        // Inject tooltip styles
        const style = document.createElement('style');
        style.textContent = `
          .taskflow-tooltip {
            position: fixed;
            background: #1F2937;
            color: #FFFFFF;
            font-size: 12px;
            font-weight: 500;
            line-height: 1.4;
            padding: 6px 10px;
            border-radius: 6px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            pointer-events: none;
            z-index: 900;
            max-width: 340px;
            word-wrap: break-word;
            opacity: 0;
            transform: translateY(4px);
            transition: opacity 120ms ease, transform 120ms ease;
          }
          .taskflow-tooltip.tooltip-visible {
            opacity: 1;
            transform: translateY(0);
          }
        `;
        document.head.appendChild(style);
      }
      this.tooltipElement = tip;
    },

    initTruncationObserver() {
      // Event delegation for truncated title and description hover
      document.addEventListener('mouseover', (e) => {
        const target = e.target.closest('.task-title-text, .task-desc-text, [data-truncate-inspect]');
        if (!target) return;

        // Auto-detect truncation
        if (target.scrollWidth > target.clientWidth) {
          const text = target.getAttribute('data-full-text') || target.innerText;
          this.showTooltip(target, text);
        }
      });

      document.addEventListener('mouseout', (e) => {
        const target = e.target.closest('.task-title-text, .task-desc-text, [data-truncate-inspect]');
        if (target) {
          this.hideTooltip();
        }
      });
    },

    showTooltip(target, text) {
      if (!this.tooltipElement || !text) return;
      this.tooltipElement.textContent = text;

      const rect = target.getBoundingClientRect();
      let top = rect.bottom + 6;
      let left = rect.left;

      // Viewport collision detection
      const tipWidth = Math.min(340, window.innerWidth - 32);
      if (left + tipWidth > window.innerWidth - 16) {
        left = window.innerWidth - tipWidth - 16;
      }
      if (top + 40 > window.innerHeight) {
        top = rect.top - 36;
      }

      this.tooltipElement.style.top = `${top}px`;
      this.tooltipElement.style.left = `${Math.max(16, left)}px`;
      this.tooltipElement.classList.add('tooltip-visible');
      this.tooltipElement.setAttribute('aria-hidden', 'false');
    },

    hideTooltip() {
      if (this.tooltipElement) {
        this.tooltipElement.classList.remove('tooltip-visible');
        this.tooltipElement.setAttribute('aria-hidden', 'true');
      }
    },

    /* ==========================================================================
       4. TABLE COLUMN RESIZER & VIEW DENSITY CONTROLLER
       ========================================================================== */
    initTableDensityController() {
      const toggleBtn = document.getElementById('btn-toggle-density');
      const savedDensity = localStorage.getItem(this.densityStorageKey) || 'comfortable';
      this.applyDensity(savedDensity);

      if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
          const current = localStorage.getItem(this.densityStorageKey) || 'comfortable';
          const next = current === 'comfortable' ? 'dense' : 'comfortable';
          this.applyDensity(next);
        });
      }
    },

    applyDensity(mode) {
      const tableContainers = document.querySelectorAll('.task-table-wrap, .task-table-container');
      tableContainers.forEach((container) => {
        container.classList.remove('table-comfortable', 'table-dense');
        container.classList.add(`table-${mode}`);
      });
      localStorage.setItem(this.densityStorageKey, mode);

      const densityBtn = document.getElementById('btn-toggle-density');
      if (densityBtn) {
        const span = densityBtn.querySelector('span');
        if (span) {
          span.textContent = mode === 'dense' ? 'Compact' : 'Comfortable';
        }
      }
    },

    /* ==========================================================================
       5. SAFE MOBILE OFF-CANVAS DRAWER CONTROLLER
       ========================================================================== */
    initMobileDrawer() {
      const toggleBtn = document.getElementById('btn-mobile-menu');
      const sidebar = document.getElementById('sidebar');

      // CRITICAL: Append backdrop to document.body, NOT inside the .shell CSS Grid!
      let backdrop = document.querySelector('.sidebar-backdrop');
      if (!backdrop) {
        backdrop = document.createElement('div');
        backdrop.className = 'sidebar-backdrop';
        document.body.appendChild(backdrop);
      }

      const openDrawer = () => {
        if (!sidebar) return;
        sidebar.classList.add('mobile-open');
        document.body.classList.add('drawer-open');
        this.lockBodyScroll();
      };

      const closeDrawer = () => {
        if (!sidebar) return;
        sidebar.classList.remove('mobile-open');
        document.body.classList.remove('drawer-open');
        this.unlockBodyScroll();
      };

      if (toggleBtn) {
        toggleBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          if (sidebar && sidebar.classList.contains('mobile-open')) {
            closeDrawer();
          } else {
            openDrawer();
          }
        });
      }

      if (backdrop) {
        backdrop.addEventListener('click', closeDrawer);
      }

      // Close on Escape key
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && sidebar && sidebar.classList.contains('mobile-open')) {
          closeDrawer();
        }
      });
    }
  };

  // Expose to window and initialize
  window.TaskflowLayout = LayoutEngine;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => LayoutEngine.init());
  } else {
    LayoutEngine.init();
  }
})();
