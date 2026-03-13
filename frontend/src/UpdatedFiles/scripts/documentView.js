const API_BASE = "http://127.0.0.1:8000";

// Auth helper
function getToken() {
  return localStorage.getItem("access_token");
}

// UI elements
const pinBtn = document.getElementById("pinBtn");
const docTitleEl = document.getElementById("docTitle");
const docFrame = document.getElementById("docFrame");
const viewerPlaceholder = document.getElementById("viewerPlaceholder");

// Comments
const commentForm = document.getElementById("commentForm");
const commentAuthor = document.getElementById("commentAuthor");
const commentInput = document.getElementById("commentInput");
const docFrame = document.getElementById("docFrame");
const openFileBtn = document.getElementById("openFileBtn");
const pageStatus = document.getElementById("pageStatus");

let currentDocument = null;

const setStatus = (message, isError = false) => {
  pageStatus.textContent = message;
  pageStatus.dataset.error = isError ? "true" : "false";
};

const renderComments = (comments) => {
  if (!comments.length) {
    commentsList.innerHTML = '<div class="comment muted">No comments yet.</div>';
    return;
  }
  commentsList.innerHTML = comments
    .map(
      (comment) => `
        <div class="comment">
          <strong>${comment.author}:</strong> ${comment.body}
          <div class="comment-meta">${formatDate(comment.created_at)}</div>
        </div>
      `
    )
    .join("");
};

// Current doc state
let currentDocId = null;
let isPinned = false;

// Track iframe object URL so we can revoke it
let currentObjectUrl = null;

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

  // If title not provided in URL, set it from backend response
  if (docTitleEl && doc && doc.filename) {
    const params = new URLSearchParams(window.location.search);
    if (!params.get("doc")) {
      docTitleEl.textContent = doc.filename;
    }
  }
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

  const res = await fetch(
    `${API_BASE}/documents/${encodeURIComponent(currentDocId)}/${endpoint}`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }
  );

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
    if (viewerPlaceholder) viewerPlaceholder.textContent = "Missing document id in URL.";
    return;
  }

  currentDocId = docId;

  // Show placeholder while loading
  if (viewerPlaceholder) viewerPlaceholder.style.display = "";
  if (docFrame) docFrame.style.display = "";

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

    if (currentObjectUrl) {
      URL.revokeObjectURL(currentObjectUrl);
      currentObjectUrl = null;
    }

    const objectUrl = URL.createObjectURL(blob);
    currentObjectUrl = objectUrl;

    if (docFrame) {
      docFrame.style.width = "100%";
      docFrame.style.minHeight = "70vh";

      // Hide placeholder once iframe actually loads the blob URL
      docFrame.onload = () => {
        if (viewerPlaceholder) viewerPlaceholder.style.display = "none";
      };

      docFrame.src = objectUrl;
    } else {
      if (viewerPlaceholder) viewerPlaceholder.textContent = "Viewer iframe not found on page.";
    }
  } catch (err) {
    console.error(err);
    if (viewerPlaceholder) {
      viewerPlaceholder.textContent = "Error loading document. Please try again.";
      viewerPlaceholder.style.display = "";
    }
    alert("Error loading document viewer");
  }
}

// Basic HTML escape
function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

document.addEventListener("DOMContentLoaded", loadDocumentIntoViewer);

// Cleanup on leaving page
window.addEventListener("beforeunload", () => {
  if (currentObjectUrl) {
    URL.revokeObjectURL(currentObjectUrl);
    currentObjectUrl = null;
  }
});
