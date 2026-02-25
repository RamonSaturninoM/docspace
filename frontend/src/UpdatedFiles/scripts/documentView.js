const API_BASE = "http://127.0.0.1:8000";

// Auth helper
function getToken() {
  return localStorage.getItem("access_token");
}

// UI elements
const pinBtn = document.getElementById("pinBtn");
const docTitleEl = document.getElementById("docTitle");
const docFrame = document.getElementById("docFrame");

// Comments
const commentForm = document.getElementById("commentForm");
const commentInput = document.getElementById("commentInput");
const commentsList = document.getElementById("commentsList");

// Current doc state
let currentDocId = null;
let isPinned = false;


if (commentForm && commentInput && commentsList) {
  commentForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const commentText = commentInput.value.trim();
    if (!commentText) return;

    const newComment = document.createElement("div");
    newComment.classList.add("comment");
    newComment.innerHTML = `<strong>You:</strong> ${escapeHtml(commentText)}`;
    commentsList.appendChild(newComment);

    commentInput.value = "";
    commentsList.scrollTop = commentsList.scrollHeight;
  });
}


function updatePinButtonText() {
  if (!pinBtn) return;
  pinBtn.textContent = isPinned ? "Unpin Document" : "Pin Document";
}

async function fetchPinnedState() {
  const token = getToken();
  if (!token || !currentDocId) return;

  const res = await fetch(`${API_BASE}/documents/${encodeURIComponent(currentDocId)}`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) return;

  const doc = await res.json();
  isPinned = !!doc.pinned;
  updatePinButtonText();
}

async function setPinnedOnServer(pinned) {
  const token = getToken();
  if (!token) {
    alert("You must log in first.");
    window.location.href = "login-signup.html";
    return;
  }
  if (!currentDocId) return;

  const endpoint = pinned ? "pin" : "unpin";

  const res = await fetch(`${API_BASE}/documents/${encodeURIComponent(currentDocId)}/${endpoint}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Pin update failed (${res.status}): ${text}`);
  }

  const data = await res.json();
  isPinned = !!data.pinned;
  updatePinButtonText();
}

if (pinBtn) {
  pinBtn.addEventListener("click", async () => {
    try {
      await setPinnedOnServer(!isPinned);
    } catch (err) {
      console.error(err);
      alert("Could not update pin status");
    }
  });
}

async function loadDocumentIntoViewer() {
  const token = getToken();
  if (!token) {
    alert("You must log in first.");
    window.location.href = "login-signup.html";
    return;
  }

  const params = new URLSearchParams(window.location.search);

  const docTitle = params.get("doc");
  if (docTitle && docTitleEl) {
    docTitleEl.textContent = docTitle;
  }

  const docId = params.get("id");
  if (!docId) {
    console.warn("Missing ?id= in URL");
    return;
  }

  currentDocId = docId;

  await fetchPinnedState();


  try {
    const res = await fetch(`${API_BASE}/documents/${encodeURIComponent(docId)}/file`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`Failed to load document file (${res.status}): ${text}`);
    }

    const blob = await res.blob();
    const objectUrl = URL.createObjectURL(blob);

    if (docFrame) {
      // ensure iframe is visible
      docFrame.style.width = "100%";
      docFrame.style.minHeight = "70vh";
      docFrame.src = objectUrl;
    }
  } catch (err) {
    console.error(err);
    alert("Error loading document viewer");
  }
}

// Basic HTML escape
function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

document.addEventListener("DOMContentLoaded", loadDocumentIntoViewer);