/**
 * Taskflow AI Productivity Assistant Module
 * Handles query execution, pre-configured chips, dynamic response badge rendering,
 * and clean markdown formatting.
 */

const TaskflowAssistant = {
  isQuerying: false,

  init() {
    this.bindChips();
    this.bindInputForm();
  },

  bindChips() {
    const chips = document.querySelectorAll('.assistant-chip');
    chips.forEach(chip => {
      chip.addEventListener('click', () => {
        const queryText = chip.getAttribute('data-query') || chip.textContent.trim();
        const inputEl = document.getElementById('assistant-input');
        if (inputEl) inputEl.value = queryText;
        this.submitQuery(queryText);
      });
    });
  },

  bindInputForm() {
    const form = document.getElementById('assistant-form');
    if (form) {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
        const inputEl = document.getElementById('assistant-input');
        const text = inputEl ? inputEl.value.trim() : '';
        if (text) {
          this.submitQuery(text);
        }
      });
    }
  },

  async submitQuery(queryText) {
    if (this.isQuerying || !queryText) return;
    this.isQuerying = true;

    const responseContainer = document.getElementById('assistant-response');
    const badgeEl = document.getElementById('assistant-model-badge');
    const submitBtn = document.getElementById('assistant-submit-btn');

    if (badgeEl) badgeEl.style.display = 'none';

    if (responseContainer) {
      responseContainer.innerHTML = `
        <div class="assistant-loading">
          <div class="loading-spinner"></div>
          <span>Analyzing team workspace and synthesizing insights...</span>
        </div>
      `;
    }

    if (submitBtn) submitBtn.disabled = true;

    try {
      const res = await fetch('/api/assistant/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: queryText })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Assistant service failed.');
      }

      // Update badge
      if (badgeEl) {
        badgeEl.textContent = data.model_badge || (data.source === 'ai' ? '🤖 AI-Generated' : '⚡ Rule-Based Summary');
        badgeEl.className = `model-badge badge-${data.source || 'rule_based'}`;
        badgeEl.style.display = 'inline-flex';
      }

      // Render markdown response
      if (responseContainer) {
        responseContainer.innerHTML = this.renderMarkdown(data.response || 'No response generated.');
      }
    } catch (err) {
      console.error('Assistant query error:', err);
      if (responseContainer) {
        responseContainer.innerHTML = `
          <div class="assistant-error" style="color: var(--danger); font-size: 13px;">
            ⚠️ Unable to process query. Please check your connectivity and try again.
          </div>
        `;
      }
    } finally {
      this.isQuerying = false;
      if (submitBtn) submitBtn.disabled = false;
    }
  },

  renderMarkdown(text) {
    if (!text) return '';

    let out = text;

    // Headings
    out = out.replace(/^### (.*$)/gim, '<h4 class="md-h4">$1</h4>');
    out = out.replace(/^## (.*$)/gim, '<h3 class="md-h3">$1</h3>');
    out = out.replace(/^# (.*$)/gim, '<h2 class="md-h2">$1</h2>');

    // Bold & italic
    out = out.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    out = out.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // Inline code
    out = out.replace(/`([^`]+)`/g, '<code class="md-code">$1</code>');

    // Blockquotes
    out = out.replace(/^> (.*$)/gim, '<blockquote class="md-quote">$1</blockquote>');

    // Bullet lists
    out = out.replace(/^\s*-\s+(.*$)/gim, '<li class="md-li">$1</li>');
    out = out.replace(/(<li class="md-li">.*<\/li>)/gims, '<ul class="md-ul">$1</ul>');

    // Numbered lists
    out = out.replace(/^\s*\d+\.\s+(.*$)/gim, '<li class="md-oli">$1</li>');
    out = out.replace(/(<li class="md-oli">.*<\/li>)/gims, '<ol class="md-ol">$1</ol>');

    // Paragraph breaks
    out = out.replace(/\n\n+/g, '</p><p class="md-p">');
    out = `<p class="md-p">${out}</p>`;

    // Clean up empty paragraphs
    out = out.replace(/<p class="md-p">\s*<\/p>/g, '');
    out = out.replace(/<p class="md-p">(<h[234]>)/g, '$1');
    out = out.replace(/(<\/h[234]>)<\/p>/g, '$1');
    out = out.replace(/<p class="md-p">(<(?:ul|ol|blockquote)>)/g, '$1');
    out = out.replace(/(<\/(?:ul|ol|blockquote)>)<\/p>/g, '$1');

    return out;
  }
};

window.TaskflowAssistant = TaskflowAssistant;
