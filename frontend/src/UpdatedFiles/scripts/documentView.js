(() => {
const { apiFetch, apiUrl, formatBytes, formatDate } = window.DocspaceApi;

const params = new URLSearchParams(window.location.search);
const documentId = params.get("id");

const docTitle = document.getElementById("docTitle");
const docMeta = document.getElementById("docMeta");
const docDescription = document.getElementById("docDescription");
const docIndexMeta = document.getElementById("docIndexMeta");
const pinBtn = document.getElementById("pinBtn");
const reindexBtn = document.getElementById("reindexBtn");
const deleteBtn = document.getElementById("deleteBtn");
const commentsList = document.getElementById("commentsList");
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

const renderDocument = (documentData) => {
  currentDocument = documentData;
  docTitle.textContent = documentData.title;
  docMeta.textContent = `${documentData.department} • ${documentData.owner} • ${formatBytes(documentData.size_bytes)} • Updated ${formatDate(documentData.updated_at)}`;
  docDescription.textContent = documentData.description || "No description added.";
  docIndexMeta.textContent = `Index: ${documentData.index_status}${documentData.chunk_count ? ` • ${documentData.chunk_count} chunks` : ""}${documentData.index_error ? ` • ${documentData.index_error}` : ""}`;
  pinBtn.textContent = documentData.pinned ? "Unpin Document" : "Pin Document";
  openFileBtn.href = apiUrl(documentData.download_url);
  docFrame.src = apiUrl(documentData.download_url);
  renderComments(documentData.comments || []);
};

const loadDocument = async () => {
  if (!documentId) {
    setStatus("Missing document id", true);
    return;
  }

  setStatus("Loading document...");
  try {
    const payload = await apiFetch(`/api/documents/${documentId}`);
    renderDocument(payload);
    setStatus("Document loaded");
  } catch (error) {
    setStatus(error.message || "Unable to load document", true);
  }
};

pinBtn.addEventListener("click", async () => {
  if (!currentDocument) return;
  setStatus("Updating document...");
  try {
    const payload = await apiFetch(`/api/documents/${currentDocument.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pinned: !currentDocument.pinned }),
    });
    renderDocument(payload);
    setStatus("Document updated");
  } catch (error) {
    setStatus(error.message || "Unable to update document", true);
  }
});

reindexBtn.addEventListener("click", async () => {
  if (!currentDocument) return;
  setStatus("Reindexing document...");
  try {
    await apiFetch(`/api/documents/${currentDocument.id}/index`, { method: "POST" });
    await loadDocument();
  } catch (error) {
    setStatus(error.message || "Unable to reindex document", true);
  }
});

deleteBtn.addEventListener("click", async () => {
  if (!currentDocument) return;
  const confirmed = window.confirm("Delete this document?");
  if (!confirmed) return;
  setStatus("Deleting document...");
  try {
    await apiFetch(`/api/documents/${currentDocument.id}`, { method: "DELETE" });
    window.location.href = "documents.html";
  } catch (error) {
    setStatus(error.message || "Unable to delete document", true);
  }
});

commentForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!currentDocument) return;
  const body = commentInput.value.trim();
  if (!body) {
    setStatus("Comment cannot be empty", true);
    return;
  }

  setStatus("Posting comment...");
  try {
    await apiFetch(`/api/documents/${currentDocument.id}/comments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        author: commentAuthor.value.trim() || "Anonymous",
        body,
      }),
    });
    commentInput.value = "";
    await loadDocument();
  } catch (error) {
    setStatus(error.message || "Unable to post comment", true);
  }
});

loadDocument();
})();
