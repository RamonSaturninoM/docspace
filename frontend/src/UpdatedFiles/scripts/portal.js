(() => {
const { apiFetch, formatDate } = window.DocspaceApi;

const searchBtn = document.getElementById("searchBtn");
const searchInput = document.getElementById("searchInput");
const pinnedList = document.getElementById("pinnedList");
const recentList = document.getElementById("docList");
const portalStatus = document.getElementById("portalStatus");

const detailUrl = (documentId) => `documentView.html?id=${encodeURIComponent(documentId)}`;

const setStatus = (message, isError = false) => {
  portalStatus.textContent = message;
  portalStatus.dataset.error = isError ? "true" : "false";
};

const renderList = (target, documents, emptyMessage) => {
  if (!documents.length) {
    target.innerHTML = `<li>${emptyMessage}</li>`;
    return;
  }
  target.innerHTML = documents
    .map(
      (document) => `
        <li>
          <a href="${detailUrl(document.id)}">${document.title}</a>
          <span class="muted"> · ${document.department} · ${formatDate(document.updated_at)}</span>
        </li>
      `
    )
    .join("");
};

const loadPortalData = async () => {
  setStatus("Loading documents...");
  try {
    const [pinnedPayload, recentPayload] = await Promise.all([
      apiFetch("/api/documents?pinned=true&limit=5"),
      apiFetch("/api/documents?limit=5"),
    ]);
    renderList(pinnedList, pinnedPayload.documents || [], "No pinned documents yet.");
    renderList(recentList, recentPayload.documents || [], "No recent uploads yet.");
    setStatus("Portal synced");
  } catch (error) {
    setStatus(error.message || "Unable to load portal data", true);
  }
};

searchBtn.addEventListener("click", () => {
  const query = searchInput.value.trim();
  window.location.href = query
    ? `documents.html?q=${encodeURIComponent(query)}`
    : "documents.html";
});

searchInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    searchBtn.click();
  }
});

loadPortalData();
})();
