const messages = document.getElementById("messages");
const composer = document.getElementById("composer");
const promptInput = document.getElementById("prompt");
const status = document.getElementById("status");
const clearBtn = document.getElementById("clear");
const sendBtn = composer.querySelector("button[type='submit']");
const API_BASE =
  localStorage.getItem("DOCSPACE_API_BASE") ||
  window.DOCSPACE_API_BASE ||
  "http://127.0.0.1:8000";

const addMessage = (text, role, sources = []) => {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  wrapper.appendChild(bubble);
  if (sources.length) {
    const sourceList = document.createElement("div");
    sourceList.className = "source-list";
    sourceList.textContent = `Sources: ${sources.map((item) => item.title).join(", ")}`;
    wrapper.appendChild(sourceList);
  }
  messages.appendChild(wrapper);
  messages.scrollTop = messages.scrollHeight;
};

const setStatus = (text, ok = true) => {
  status.textContent = text;
  status.style.background = ok ? "rgba(255, 255, 255, 0.18)" : "rgba(255, 123, 58, 0.4)";
};

const setComposerBusy = (busy) => {
  promptInput.disabled = busy;
  sendBtn.disabled = busy;
  sendBtn.textContent = busy ? "Sending..." : "Send";
};

const addThinkingMessage = () => {
  const wrapper = document.createElement("div");
  wrapper.className = "message assistant thinking";
  wrapper.id = "thinkingMessage";
  wrapper.innerHTML = `
    <div class="bubble">
      <span class="thinking-label">Thinking</span>
      <span class="thinking-dots" aria-hidden="true">
        <span></span><span></span><span></span>
      </span>
    </div>
  `;
  messages.appendChild(wrapper);
  messages.scrollTop = messages.scrollHeight;
};

const removeThinkingMessage = () => {
  const thinking = document.getElementById("thinkingMessage");
  if (thinking) thinking.remove();
};

clearBtn.addEventListener("click", () => {
  messages.innerHTML = `
    <div class="message system">
      <div class="bubble">Upload docs, then ask anything. I will respond based on your indexed knowledge.</div>
    </div>
  `;
});

composer.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = promptInput.value.trim();
  if (!text) return;

  addMessage(text, "user");
  promptInput.value = "";
  setStatus("Thinking…");
  setComposerBusy(true);
  addThinkingMessage();

  try {
    const response = await fetch(`${API_BASE}/api/chat/respond`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || "Chat request failed");
    }

    const payload = await response.json();
    removeThinkingMessage();
    addMessage(payload.reply || "No response received.", "assistant", payload.sources || []);
    setStatus("Connected");
  } catch (error) {
    removeThinkingMessage();
    addMessage(
      `Unable to reach chat service at ${API_BASE}. ${error.message || ""}`.trim(),
      "system"
    );
    setStatus("Offline", false);
  } finally {
    setComposerBusy(false);
    promptInput.focus();
  }
});
