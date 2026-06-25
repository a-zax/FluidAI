let state = {
    currentSessionId: null,
    messages: [],
    chatHistory: [],
    isLoading: false,
    apiEndpoint: localStorage.getItem("apiEndpoint") || "http://localhost:8001",
    showStats: localStorage.getItem("showStats") !== "false",
    theme: localStorage.getItem("theme") || "light",
};

document.addEventListener("DOMContentLoaded", () => {
    applyTheme(state.theme);
    generateNewSessionId();
    loadChatHistory();
    setupEventListeners();
    syncSettingsUI();
});

function generateNewSessionId() {
    state.currentSessionId = "session_" + Date.now() + "_" + Math.random().toString(36).slice(2, 11);
}

function setupEventListeners() {
    const inputBox = document.getElementById("input-box");
    inputBox.addEventListener("input", (event) => {
        const count = event.target.value.length;
        document.getElementById("char-count").textContent = `${count} / 2000`;
        event.target.style.height = "auto";
        event.target.style.height = Math.min(event.target.scrollHeight, 140) + "px";
    });
}

function syncSettingsUI() {
    document.getElementById("api-endpoint").value = state.apiEndpoint;
    document.getElementById("theme-select").value = state.theme;
    document.getElementById("show-stats").checked = state.showStats;
}

function sendMessage(message = null) {
    const inputBox = document.getElementById("input-box");
    const question = message || inputBox.value.trim();

    if (!question || state.isLoading) return;

    const welcome = document.querySelector(".welcome-screen");
    if (welcome) welcome.style.display = "none";

    addMessage(question, "user");
    inputBox.value = "";
    inputBox.style.height = "auto";
    document.getElementById("char-count").textContent = "0 / 2000";

    sendToAPI(question);
}

function addMessage(content, role, meta = null) {
    const messagesArea = document.getElementById("messages");
    const messageEl = document.createElement("div");
    messageEl.className = `message ${role}`;

    const contentEl = document.createElement("div");
    contentEl.className = "message-content";
    contentEl.innerHTML = role === "assistant" ? renderAssistantContent(content) : escapeHtml(content);
    messageEl.appendChild(contentEl);

    if (meta) {
        const metaEl = document.createElement("div");
        metaEl.className = "message-meta";
        metaEl.innerHTML = meta;
        messageEl.appendChild(metaEl);
    }

    messagesArea.appendChild(messageEl);
    messagesArea.scrollTop = messagesArea.scrollHeight;
    state.messages.push({ content, role, meta });
}

function addLoadingMessage() {
    const messagesArea = document.getElementById("messages");
    const messageEl = document.createElement("div");
    messageEl.className = "message assistant";
    messageEl.id = "loading-message";

    const contentEl = document.createElement("div");
    contentEl.className = "message-content loading";
    contentEl.innerHTML = "<span></span><span></span><span></span>";

    messageEl.appendChild(contentEl);
    messagesArea.appendChild(messageEl);
    messagesArea.scrollTop = messagesArea.scrollHeight;
}

function removeLoadingMessage() {
    const loadingEl = document.getElementById("loading-message");
    if (loadingEl) loadingEl.remove();
}

async function sendToAPI(question) {
    state.isLoading = true;
    document.getElementById("send-btn").disabled = true;
    addLoadingMessage();

    const enableActions = document.getElementById("enable-actions").checked;
    const startTime = performance.now();

    try {
        const response = await fetch(`${state.apiEndpoint}/ask`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                question,
                session_id: state.currentSessionId,
                enable_actions: enableActions,
            }),
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`API ${response.status}: ${errorText}`);
        }

        const data = await response.json();
        const latency = performance.now() - startTime;
        const meta = buildMessageMeta(data, latency);

        removeLoadingMessage();
        addMessage(data.answer, "assistant", meta);
        updateStats(data, latency);
        saveChatToHistory(question);
    } catch (error) {
        removeLoadingMessage();
        addMessage(`Error: ${error.message}`, "assistant");
    } finally {
        state.isLoading = false;
        document.getElementById("send-btn").disabled = false;
    }
}

function buildMessageMeta(data, latency) {
    const parts = [`<strong>${latency.toFixed(0)}ms</strong>`];
    if (data.retrieved_context && data.retrieved_context.length) {
        parts.push(`${data.retrieved_context.length} source${data.retrieved_context.length > 1 ? "s" : ""}`);
    }
    if (data.memory_used) {
        parts.push("memory");
    }
    if (data.action_performed) {
        const encoded = encodeURIComponent(JSON.stringify(data.action_result));
        const label = data.action_performed.replace(/_/g, " ");
        parts.push(`<span class="action-badge" onclick="showActionResult('${data.action_performed}', '${encoded}')">${label}</span>`);
    }
    if (data.pending_confirmation) {
        parts.push(
            `<button class="confirm-action-btn" onclick="confirmAction('${data.pending_confirmation.id}')">Confirm action</button>`
        );
    }
    return parts.join(" | ");
}

async function confirmAction(pendingActionId) {
    try {
        const response = await fetch(
            `${state.apiEndpoint}/actions/${pendingActionId}/confirm?session_id=${encodeURIComponent(state.currentSessionId)}`,
            { method: "POST" }
        );
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`API ${response.status}: ${errorText}`);
        }
        const result = await response.json();
        addMessage(
            `Confirmed ${result.pending_action_id}. Executed ${result.action_performed.replace(/_/g, " ")} and created ${result.action_result.id}.`,
            "assistant",
            `<span class="action-badge" onclick="showActionResult('${result.action_performed}', '${encodeURIComponent(JSON.stringify(result.action_result))}')">view result</span>`
        );
    } catch (error) {
        addMessage(`Error confirming action: ${error.message}`, "assistant");
    }
}

function updateStats(data, latency) {
    if (!state.showStats) return;

    document.getElementById("stats-panel").style.display = "grid";
    document.getElementById("stat-latency").textContent = latency.toFixed(0) + "ms";
    document.getElementById("stat-tokens").textContent = data.tokens_used;
    document.getElementById("stat-cached").textContent = data.cached ? "Yes" : "No";
    document.getElementById("stat-action").textContent = data.action_performed ? data.action_performed.replace(/_/g, " ") : "None";
}

function showActionResult(action, resultEncoded) {
    const result = JSON.parse(decodeURIComponent(resultEncoded));
    document.getElementById("action-title").textContent = action.replace(/_/g, " ").toUpperCase();
    document.getElementById("action-body").innerHTML = `<pre>${escapeHtml(JSON.stringify(result, null, 2))}</pre>`;
    document.getElementById("action-modal").style.display = "flex";
}

function closeActionModal() {
    document.getElementById("action-modal").style.display = "none";
}

function saveChatToHistory(question) {
    const chatItem = {
        id: state.currentSessionId,
        title: question.slice(0, 42) + (question.length > 42 ? "..." : ""),
        timestamp: new Date().toISOString(),
        messages: state.messages,
    };

    state.chatHistory = [chatItem, ...state.chatHistory.filter((chat) => chat.id !== state.currentSessionId)].slice(0, 12);
    localStorage.setItem("chatHistory", JSON.stringify(state.chatHistory));
    renderChatHistory();
}

function loadChatHistory() {
    const saved = localStorage.getItem("chatHistory");
    state.chatHistory = saved ? JSON.parse(saved) : [];
    renderChatHistory();
}

function renderChatHistory() {
    const chatList = document.getElementById("chat-list");
    chatList.innerHTML = "";

    state.chatHistory.forEach((chat) => {
        const btn = document.createElement("button");
        btn.className = "chat-item";
        btn.textContent = chat.title;
        btn.onclick = () => loadChat(chat);
        chatList.appendChild(btn);
    });
}

function loadChat(chat) {
    state.currentSessionId = chat.id;
    state.messages = [];

    const messagesArea = document.getElementById("messages");
    messagesArea.innerHTML = "";

    chat.messages.forEach((msg) => {
        addMessage(msg.content, msg.role, msg.meta || null);
    });
}

function startNewChat() {
    generateNewSessionId();
    state.messages = [];
    document.getElementById("stats-panel").style.display = "none";
    document.getElementById("messages").innerHTML = getWelcomeMarkup();
}

function getWelcomeMarkup() {
    return `
        <div class="welcome-screen">
            <div class="welcome-content">
                <h1>Good to see you, Aryan.</h1>
                <p>Ready when you are.</p>
                <div class="quick-prompts">
                    <div class="quick-prompts-title">Start with</div>
                    <div class="quick-prompt-grid">
                        <button class="prompt-btn" onclick="sendMessage('Who is employee EMP001?')">Find EMP001</button>
                        <button class="prompt-btn" onclick="sendMessage('Create a support ticket for database issues')">Create incident ticket</button>
                        <button class="prompt-btn" onclick="sendMessage('Generate a sales report')">Generate ops report</button>
                        <button class="prompt-btn" onclick="sendMessage('Explain the production incident workflow')">Search policy</button>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function toggleSettings() {
    const modal = document.getElementById("settings-modal");
    modal.style.display = modal.style.display === "none" ? "flex" : "none";
}

function toggleDocumentModal() {
    const modal = document.getElementById("document-modal");
    modal.style.display = modal.style.display === "none" ? "flex" : "none";
}

async function addKnowledgeDocument() {
    const title = document.getElementById("document-title").value.trim();
    const body = document.getElementById("document-body").value.trim();
    const source = document.getElementById("document-source").value.trim() || "manual";
    const status = document.getElementById("document-status");

    if (!title || !body) {
        status.textContent = "Add a title and at least 20 characters of content.";
        return;
    }

    try {
        const response = await fetch(`${state.apiEndpoint}/documents`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title, body, source }),
        });
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`API ${response.status}: ${errorText}`);
        }
        const addedDocument = await response.json();
        status.textContent = `Added ${addedDocument.id}. You can query it now.`;
        document.getElementById("document-title").value = "";
        document.getElementById("document-body").value = "";
    } catch (error) {
        status.textContent = `Error: ${error.message}`;
    }
}

function saveSettings() {
    state.apiEndpoint = document.getElementById("api-endpoint").value.trim() || "http://localhost:8001";
    localStorage.setItem("apiEndpoint", state.apiEndpoint);
    toggleSettings();
}

function toggleStats() {
    state.showStats = document.getElementById("show-stats").checked;
    document.getElementById("stats-panel").style.display = state.showStats ? "grid" : "none";
    localStorage.setItem("showStats", state.showStats);
}

function changeTheme() {
    const theme = document.getElementById("theme-select").value;
    applyTheme(theme);
    localStorage.setItem("theme", theme);
}

function applyTheme(theme) {
    state.theme = theme;
    document.body.classList.toggle("dark-mode", theme === "dark");
}

function handleKeyPress(event) {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
        sendMessage();
    }
}

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function renderAssistantContent(content) {
    if (window.marked && typeof window.marked.parse === "function") {
        return window.marked.parse(content);
    }
    return escapeHtml(content).replace(/\n/g, "<br>");
}

window.addEventListener("click", (event) => {
    const settingsModal = document.getElementById("settings-modal");
    const actionModal = document.getElementById("action-modal");
    const documentModal = document.getElementById("document-modal");
    if (event.target === settingsModal) settingsModal.style.display = "none";
    if (event.target === actionModal) actionModal.style.display = "none";
    if (event.target === documentModal) documentModal.style.display = "none";
});
