const messages = document.getElementById("messages");
const composer = document.getElementById("composer");
const promptInput = document.getElementById("prompt");
const status = document.getElementById("status");
const clearBtn = document.getElementById("clear");

const addMessage = (text, role) => {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  wrapper.appendChild(bubble);
  messages.appendChild(wrapper);
  messages.scrollTop = messages.scrollHeight;
};

const setStatus = (text, ok = true) => {
  status.textContent = text;
  status.style.background = ok ? "rgba(255, 255, 255, 0.18)" : "rgba(255, 123, 58, 0.4)";
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

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || "Chat request failed");
    }

    const payload = await response.json();
    addMessage(payload.reply || "No response received.", "assistant");
    setStatus("Connected");
  } catch (error) {
    addMessage("Unable to reach the chat service. Check that the backend is running.", "system");
    setStatus("Offline", false);
  }
});
