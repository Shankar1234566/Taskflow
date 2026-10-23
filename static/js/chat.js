/**
 * Taskflow Instant Messaging & Task Collaboration Module
 * Real-time WebSockets powered by Socket.IO with HTTP fallback.
 */

const TaskflowChat = {
  socket: null,
  activeChannel: null,
  channels: [],
  messages: [],
  unreadTotal: 0,

  async init() {
    this.initSocket();
    this.bindDOM();
    await this.loadChannels();
  },

  initSocket() {
    if (typeof io !== 'undefined') {
      try {
        this.socket = io({
          transports: ['websocket', 'polling'],
          reconnection: true,
          reconnectionAttempts: 5,
          timeout: 10000
        });

        this.socket.on('connect', () => {
          console.log('[Chat] Socket connected successfully');
          if (this.activeChannel) {
            this.socket.emit('join_room', {
              team_id: this.activeChannel.team_id,
              task_id: this.activeChannel.task_id
            });
          }
        });

        this.socket.on('new_message', (msg) => {
          this.handleIncomingMessage(msg);
        });

        this.socket.on('error', (err) => {
          console.warn('[Chat] Socket error:', err);
        });
      } catch (err) {
        console.warn('[Chat] Failed to initialize Socket.IO:', err);
      }
    } else {
      console.warn('[Chat] Socket.IO library not loaded, using HTTP fallback.');
    }
  },

  bindDOM() {
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input-text');
    const btnAttach = document.getElementById('btn-chat-attach');

    if (chatForm) {
      chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const text = chatInput?.value?.trim();
        if (!text) return;
        this.sendMessage(text);
        if (chatInput) chatInput.value = '';
      });
    }

    if (btnAttach) {
      btnAttach.addEventListener('click', () => {
        const url = prompt('Enter attachment URL (e.g. image link, document URL, Git commit):');
        if (url && url.trim()) {
          const text = chatInput?.value?.trim() || 'Attached file:';
          this.sendMessage(text, url.trim());
          if (chatInput) chatInput.value = '';
        }
      });
    }
  },

  async loadChannels() {
    try {
      const res = await fetch('/api/chat/channels');
      if (!res.ok) return;
      const data = await res.json();
      this.channels = data.channels || [];
      this.renderChannelList();

      // Automatically select first channel if none selected
      if (!this.activeChannel && this.channels.length > 0) {
        this.selectChannel(this.channels[0].id);
      }
    } catch (err) {
      console.error('[Chat] Failed to load channels:', err);
    }
  },

  renderChannelList() {
    const container = document.getElementById('chat-channels-container');
    if (!container) return;

    const teamChannels = this.channels.filter(c => c.type === 'team');
    const taskThreads = this.channels.filter(c => c.type === 'task');

    let html = '';

    // Team Channel section
    html += `<div class="channel-group-title">Channels</div>`;
    teamChannels.forEach(c => {
      const isActive = this.activeChannel && this.activeChannel.id === c.id;
      html += `
        <div class="channel-item ${isActive ? 'active' : ''}" onclick="TaskflowChat.selectChannel('${c.id}')">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="4" y1="9" x2="20" y2="9"/><line x1="4" y1="15" x2="20" y2="15"/>
            <line x1="10" y1="3" x2="8" y2="21"/><line x1="16" y1="3" x2="14" y2="21"/>
          </svg>
          <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${this.escapeHtml(c.title)}</span>
          ${c.unread_count > 0 ? `<span class="channel-unread-pill">${c.unread_count}</span>` : ''}
        </div>
      `;
    });

    // Task discussion threads
    if (taskThreads.length > 0) {
      html += `<div class="channel-group-title" style="margin-top: 10px;">Task Discussions</div>`;
      taskThreads.forEach(c => {
        const isActive = this.activeChannel && this.activeChannel.id === c.id;
        html += `
          <div class="channel-item ${isActive ? 'active' : ''}" onclick="TaskflowChat.selectChannel('${c.id}')" title="${this.escapeHtml(c.title)}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
            </svg>
            <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${this.escapeHtml(c.title)}</span>
            ${c.unread_count > 0 ? `<span class="channel-unread-pill">${c.unread_count}</span>` : ''}
          </div>
        `;
      });
    }

    container.innerHTML = html;
  },

  async selectChannel(channelId) {
    const channel = this.channels.find(c => c.id === channelId);
    if (!channel) return;

    // Leave old socket room
    if (this.socket && this.activeChannel) {
      this.socket.emit('leave_room', {
        team_id: this.activeChannel.team_id,
        task_id: this.activeChannel.task_id
      });
    }

    this.activeChannel = channel;
    channel.unread_count = 0;
    this.updateSidebarUnreadTotal();
    this.renderChannelList();

    // Update Header
    const titleEl = document.getElementById('chat-active-title');
    const descEl = document.getElementById('chat-active-desc');
    if (titleEl) titleEl.textContent = channel.title;
    if (descEl) descEl.textContent = channel.description || '';

    // Join new socket room
    if (this.socket && this.socket.connected) {
      this.socket.emit('join_room', {
        team_id: channel.team_id,
        task_id: channel.task_id
      });
    }

    // Fetch messages
    await this.fetchMessages(channel.team_id, channel.task_id);
  },

  async fetchMessages(teamId, taskId) {
    const stream = document.getElementById('chat-messages-stream');
    if (!stream) return;

    stream.innerHTML = `<div style="text-align: center; color: var(--color-text-muted); font-size: 13px; padding: 20px;">Loading message stream...</div>`;

    try {
      let url = `/api/chat/messages?team_id=${teamId || ''}`;
      if (taskId) url += `&task_id=${taskId}`;

      const res = await fetch(url);
      if (!res.ok) return;
      const data = await res.json();
      this.messages = data.messages || [];
      this.renderMessages();
    } catch (err) {
      console.error('[Chat] Failed to fetch messages:', err);
    }
  },

  renderMessages() {
    const stream = document.getElementById('chat-messages-stream');
    if (!stream) return;

    if (this.messages.length === 0) {
      stream.innerHTML = `
        <div style="text-align: center; color: var(--color-text-muted); padding: 40px 16px;">
          <h4 style="margin: 0 0 6px; color: var(--color-text-primary);">Start the conversation</h4>
          <p style="margin: 0; font-size: 13px;">No messages yet. Send a note to start collaborating with your team.</p>
        </div>
      `;
      return;
    }

    const currentUserId = window.TaskflowAuth?.currentUser?.id;

    let html = '';
    this.messages.forEach(m => {
      const isOutgoing = m.sender_id === currentUserId;
      html += `
        <div class="chat-bubble-row ${isOutgoing ? 'outgoing' : 'incoming'}">
          ${!isOutgoing ? `<div class="chat-avatar" title="${this.escapeHtml(m.sender_name)}">${this.escapeHtml(m.sender_initials || 'U')}</div>` : ''}
          <div class="chat-bubble-content">
            <div class="chat-sender-meta">
              ${!isOutgoing ? `<b>${this.escapeHtml(m.sender_name)}</b>` : ''}
              <span>${this.escapeHtml(m.formatted_time || '')}</span>
            </div>
            <div class="chat-bubble">
              ${this.escapeHtml(m.content)}
              ${m.attachment_url ? `
                <div>
                  <a href="${this.escapeHtml(m.attachment_url)}" target="_blank" rel="noopener" class="chat-attachment-link">
                    📎 View Attachment
                  </a>
                </div>
              ` : ''}
            </div>
          </div>
          ${isOutgoing ? `<div class="chat-avatar" style="background: var(--color-brand-soft); color: var(--color-brand-primary);">${this.escapeHtml(m.sender_initials || 'ME')}</div>` : ''}
        </div>
      `;
    });

    stream.innerHTML = html;
    stream.scrollTop = stream.scrollHeight;
  },

  async sendMessage(content, attachmentUrl = null) {
    if (!this.activeChannel) return;

    const payload = {
      team_id: this.activeChannel.team_id,
      task_id: this.activeChannel.task_id,
      content: content,
      attachment_url: attachmentUrl
    };

    // If socket is connected, emit send_message
    if (this.socket && this.socket.connected) {
      this.socket.emit('send_message', payload);
    } else {
      // Reliable REST HTTP fallback
      try {
        const res = await fetch('/api/chat/messages', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok && data.message) {
          this.handleIncomingMessage(data.message);
        }
      } catch (err) {
        console.error('[Chat] HTTP send failed:', err);
      }
    }
  },

  handleIncomingMessage(msg) {
    if (!msg) return;

    // Check if message belongs to active channel
    const isActiveChannel = this.activeChannel &&
      ((msg.task_id && msg.task_id === this.activeChannel.task_id) ||
       (!msg.task_id && !this.activeChannel.task_id && msg.team_id === this.activeChannel.team_id));

    if (isActiveChannel) {
      // Append to messages list if not duplicate
      if (!this.messages.some(m => m.id === msg.id)) {
        this.messages.push(msg);
        this.renderMessages();
      }
    } else {
      // Increment unread count for matching channel
      const ch = this.channels.find(c =>
        (msg.task_id && c.task_id === msg.task_id) ||
        (!msg.task_id && !c.task_id && c.team_id === msg.team_id)
      );
      if (ch) {
        ch.unread_count = (ch.unread_count || 0) + 1;
        this.renderChannelList();
      }
      this.unreadTotal++;
      this.updateSidebarUnreadTotal();
    }
  },

  updateSidebarUnreadTotal() {
    const badge = document.getElementById('badge-chat');
    if (badge) {
      const total = this.channels.reduce((sum, c) => sum + (c.unread_count || 0), 0);
      badge.textContent = total;
      badge.style.display = total > 0 ? 'inline-flex' : 'none';
    }
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

window.TaskflowChat = TaskflowChat;
