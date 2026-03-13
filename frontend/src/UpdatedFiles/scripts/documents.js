(() => {
const { apiFetch, apiUrl, formatBytes, formatDate } = window.DocspaceApi;

const grid = document.getElementById("documentsGrid");
const tableBody = document.getElementById("documentsTableBody");
const emptyState = document.getElementById("emptyState");
const statusNode = document.getElementById("documentsStatus");
const searchInput = document.getElementById("documentsSearch");
const departmentFilter = document.getElementById("departmentFilter");
const kindFilter = document.getElementById("kindFilter");
const pinnedFilter = document.getElementById("pinnedFilter");
const uploadForm = document.getElementById("uploadForm");

const setStatus = (message, isError = false) => {
  statusNode.textContent = message;
  statusNode.dataset.error = isError ? "true" : "false";
};

const detailUrl = (documentId) => `documentView.html?id=${encodeURIComponent(documentId)}`;

const iconLetter = (title = "") => title.trim().charAt(0).toUpperCase() || "F";

const renderCard = (document) => `
  <article class="document-card" data-id="${document.id}">
    <div class="doc-icon">${iconLetter(document.title)}</div>
    <h3>${document.title}</h3>
    <div class="meta">${document.department} • Updated ${formatDate(document.updated_at)} • ${formatBytes(document.size_bytes)}</div>
    <div class="labels">
      ${document.pinned ? '<span class="label-pill">Pinned</span>' : ""}
      <span class="label-pill">${document.kind}</span>
      <span class="label-pill">${document.department}</span>
      <span class="label-pill">${document.index_status}</span>
    </div>
    <div class="card-actions">
      <a class="action-link" href="${detailUrl(document.id)}">Open</a>
      <a class="action-link" href="${apiUrl(document.download_url)}" target="_blank" rel="noreferrer">View file</a>
    </div>
  </article>
`;

const renderRow = (document) => `
  <tr>
    <td class="doc-name-cell">
      <span class="small-icon">${iconLetter(document.title)}</span>
      ${document.title}
    </td>
    <td>${document.owner}</td>
    <td>${document.department}</td>
    <td>${document.comments.length}</td>
    <td>${formatDate(document.updated_at)}</td>
    <td>${formatBytes(document.size_bytes)}</td>
    <td class="actions">
      <a href="${detailUrl(document.id)}">Open</a>
      <a href="${apiUrl(document.download_url)}" target="_blank" rel="noreferrer">View</a>
      ${
        document.index_status === "failed"
          ? `<a href="#" data-index-id="${document.id}">Reindex</a>`
          : ""
      }
      <a href="#" data-delete-id="${document.id}">Delete</a>
    </td>
  </tr>
`;

const readFilters = () => {
  const q = searchInput.value.trim();
  const department = departmentFilter.value;
  const kind = kindFilter.value;
  const pinned = pinnedFilter.value;
  const query = new URLSearchParams();
  if (q) query.set("q", q);
  if (department) query.set("department", department);
  if (kind) query.set("kind", kind);
  if (pinned === "true") query.set("pinned", "true");
  return query;
};

const syncQuery = (query) => {
  const next = `${window.location.pathname}?${query.toString()}`;
  window.history.replaceState({}, "", next);
};

const applyInitialSearch = () => {
  const params = new URLSearchParams(window.location.search);
  searchInput.value = params.get("q") || "";
};

const renderDocuments = (documents) => {
  grid.innerHTML = documents.map(renderCard).join("");
  tableBody.innerHTML = documents.map(renderRow).join("");
  emptyState.hidden = documents.length > 0;
};

const loadDocuments = async () => {
  const query = readFilters();
  syncQuery(query);
  setStatus("Loading documents...");

  try {
    const payload = await apiFetch(`/api/documents?${query.toString()}`);
    const documents = payload.documents || [];
    renderDocuments(documents);
    setStatus(`${documents.length} document${documents.length === 1 ? "" : "s"} loaded`);
  } catch (error) {
    grid.innerHTML = "";
    tableBody.innerHTML = "";
    emptyState.hidden = false;
    setStatus(error.message || "Unable to load documents", true);
  }
};

const deleteDocument = async (documentId) => {
  const confirmed = window.confirm("Delete this document and its comments?");
  if (!confirmed) return;
  setStatus("Deleting document...");
  try {
    await apiFetch(`/api/documents/${documentId}`, { method: "DELETE" });
    await loadDocuments();
  } catch (error) {
    setStatus(error.message || "Unable to delete document", true);
  }
};

const reindexDocument = async (documentId) => {
  setStatus("Reindexing document...");
  try {
    await apiFetch(`/api/documents/${documentId}/index`, { method: "POST" });
    await loadDocuments();
  } catch (error) {
    setStatus(error.message || "Unable to reindex document", true);
  }
};

grid.addEventListener("click", (event) => {
  const card = event.target.closest(".document-card");
  const action = event.target.closest(".action-link");
  if (!card || action) return;
  window.location.href = detailUrl(card.dataset.id);
});

tableBody.addEventListener("click", (event) => {
  const deleteLink = event.target.closest("[data-delete-id]");
  if (deleteLink) {
    event.preventDefault();
    deleteDocument(deleteLink.dataset.deleteId);
    return;
  }
  const reindexLink = event.target.closest("[data-index-id]");
  if (reindexLink) {
    event.preventDefault();
    reindexDocument(reindexLink.dataset.indexId);
  }
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(uploadForm);
  const file = formData.get("file");
  if (!(file instanceof File) || !file.name) {
    setStatus("Choose a file before uploading", true);
    return;
  }

  setStatus("Uploading document...");
  try {
    await fetch(apiUrl("/api/documents"), {
      method: "POST",
      body: formData,
    }).then(async (response) => {
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "Upload failed");
      }
      return response.json();
    });
    uploadForm.reset();
    await loadDocuments();
  } catch (error) {
    setStatus(error.message || "Upload failed", true);
  }
});

[searchInput, departmentFilter, kindFilter, pinnedFilter].forEach((node) => {
  node.addEventListener(node.tagName === "INPUT" ? "input" : "change", loadDocuments);
});

applyInitialSearch();
loadDocuments();
})();
