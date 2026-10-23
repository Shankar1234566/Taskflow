/**
 * Keyboard Shortcuts and Command Palette Manager.
 * Handles key bindings, chord sequences, and accessible modal navigation.
 */

class TaskflowShortcutsManager {
  constructor() {
    this.shortcuts = new Map();
    this.isEnabled = true;
    this.bindGlobalListener();
  }

  register(keyCombo, description, action) {
    this.shortcuts.set(keyCombo.toLowerCase(), { description, action });
  }

  bindGlobalListener() {
    window.addEventListener("keydown", (e) => {
      if (!this.isEnabled) return;

      // Do not trigger shortcuts when typing inside form inputs
      const tag = document.activeElement ? document.activeElement.tagName.toLowerCase() : "";
      if (tag === "input" || tag === "textarea" || tag === "select") {
        if (e.key === "Escape") {
          document.activeElement.blur();
        }
        return;
      }

      let combo = [];
      if (e.ctrlKey) combo.push("ctrl");
      if (e.altKey) combo.push("alt");
      if (e.shiftKey && e.key.length > 1) combo.push("shift");
      combo.push(e.key.toLowerCase());

      const comboStr = combo.join("+");
      if (this.shortcuts.has(comboStr)) {
        e.preventDefault();
        this.shortcuts.get(comboStr).action();
      } else if (this.shortcuts.has(e.key.toLowerCase())) {
        e.preventDefault();
        this.shortcuts.get(e.key.toLowerCase()).action();
      }
    });
  }

  showCheatSheet() {
    console.info("Keyboard Shortcuts Active:", Array.from(this.shortcuts.entries()));
  }
}

window.TaskflowShortcutsManager = TaskflowShortcutsManager;
