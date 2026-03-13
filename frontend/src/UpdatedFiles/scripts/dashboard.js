(() => {
const { apiFetch, formatBytes, formatDate } = window.DocspaceApi;

const dashboardStatus = document.getElementById("dashboardStatus");
const statsNodes = {
  documents: document.getElementById("documentsTotal"),
  pinned: document.getElementById("pinnedTotal"),
  comments: document.getElementById("commentsTotal"),
  storage: document.getElementById("storageTotal"),
};
const activityBody = document.getElementById("activityTableBody");

const setStatus = (message, isError = false) => {
  dashboardStatus.textContent = message;
  dashboardStatus.dataset.error = isError ? "true" : "false";
};

const loadDashboard = async () => {
  setStatus("Loading API metrics...");
  try {
    const payload = await apiFetch("/api/dashboard/stats");
    statsNodes.documents.textContent = payload.documents_total;
    statsNodes.pinned.textContent = payload.pinned_total;
    statsNodes.comments.textContent = payload.comments_total;
    statsNodes.storage.textContent = formatBytes(payload.storage_bytes);
    activityBody.innerHTML = (payload.recent_activity || [])
      .map(
        (item) => `
          <tr>
            <td>/api/documents/${item.document_id}</td>
            <td>${item.action}</td>
            <td class="status-success">OK</td>
            <td>-</td>
            <td>${formatDate(item.created_at)}</td>
          </tr>
        `
      )
      .join("");
    if (!activityBody.innerHTML) {
      activityBody.innerHTML = '<tr><td colspan="5">No activity yet.</td></tr>';
    }
    setStatus("Dashboard synced");
  } catch (error) {
    setStatus(error.message || "Unable to load dashboard", true);
  }
};

loadDashboard();
})();
