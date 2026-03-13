const API_BASE = "http://127.0.0.1:8000";

let allDocs = [];

function getToken() {
  return localStorage.getItem("access_token");
}

function getSearchText() {
  const input = document.getElementById("searchInput");
  return (input ? input.value : "").trim().toLowerCase();
}

function getFilterParams() {
  const selects = document.querySelectorAll(".documents-toolbar select");
  const viewSelect = selects[0];
  const typeSelect = selects[1];
  const sortSelect = selects[2];

  const viewMap = {
    "All documents": "all",
    "My documents": "my",
    "Pinned only": "pinned",
    "Shared with me": "shared",
  };

  const typeMap = {
    "All types": "all",
    "PDF": "pdf",
    "Word / Docs": "docs",
    "Spreadsheet": "sheets",
    "Presentation": "slides",
  };

  const sortMap = {
    "Recently opened": "opened",
    "Recently modified": "modified",
    "Name (A–Z)": "name",
    "Owner": "owner",
  };

  return {
    view: viewMap[viewSelect.value] || "all",
    dtype: typeMap[typeSelect.value] || "all",
    sort: sortMap[sortSelect.value] || "modified",
  };
}

// fetch docs from backend, then apply search locally
async function loadDocuments() {
  const token = getToken();
  if (!token) {
    alert("You must log in first.");
    window.location.href = "login-signup.html";
    return;
  }

  const { view, dtype, sort } = getFilterParams();
  const url = `${API_BASE}/documents?view=${encodeURIComponent(view)}&dtype=${encodeURIComponent(dtype)}&sort=${encodeURIComponent(sort)}`;

  try {
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!res.ok) throw new Error(`Failed to load documents (${res.status})`);

    allDocs = await res.json();
    applySearchAndRender();
  } catch (err) {
    console.error(err);
    alert("Error loading documents");
  }
}

function applySearchAndRender() {
  const q = getSearchText();

  let docs = allDocs;

  if (q) {
    docs = allDocs.filter((d) => {
      const filename = (d.filename || "").toLowerCase();
      const owner = (d.owner_name || "").toLowerCase();
      const dept = (d.department || "").toLowerCase();
      return filename.includes(q) || owner.includes(q) || dept.includes(q);
    });
  }

  renderGrid(docs);
  renderList(docs);
}

function renderGrid(docs) {
  const grid = document.getElementById("documentsGrid");
  if (!grid) return;

  grid.innerHTML = "";

  docs.forEach((doc) => {
    const card = document.createElement("div");
    card.className = "document-card";
    card.addEventListener("click", () => openDoc(doc));

    const iconLetter = getIconLetter(doc.filename);
    const updatedText = formatDatePretty(doc.uploaded_at);
    const sizeText = formatBytes(doc.size_bytes);

    const pinnedPill = doc.pinned ? `<span class="label-pill">Pinned</span>` : "";
    const deptPill = `<span class="label-pill">${escapeHtml(doc.department || "—")}</span>`;

    card.innerHTML = `
      <div class="doc-icon">${escapeHtml(iconLetter)}</div>
      <h3>${escapeHtml(doc.filename || "Untitled")}</h3>
      <div class="meta">${escapeHtml(doc.department || "—")} • Updated ${escapeHtml(updatedText)} • ${escapeHtml(sizeText)}</div>
      <div class="labels">
        ${pinnedPill}
        ${deptPill}
      </div>
    `;

    grid.appendChild(card);
  });
}

function renderList(docs) {
  const tbody = document.getElementById("documentsTableBody");
  if (!tbody) return;

  tbody.innerHTML = "";

  docs.forEach((doc) => {
    const tr = document.createElement("tr");

    const iconLetter = getIconLetter(doc.filename);
    const ownerText = doc.owner_name || "Unknown";
    const lastOpenedText = formatDatePretty(doc.last_opened_at);
    const lastModifiedText = formatDatePretty(doc.uploaded_at);
    const sizeText = formatBytes(doc.size_bytes);

    tr.innerHTML = `
      <td class="doc-name-cell">
        <span class="small-icon">${escapeHtml(iconLetter)}</span>
        ${escapeHtml(doc.filename || "Untitled")}
      </td>
      <td>${escapeHtml(ownerText)}</td>
      <td>${escapeHtml(doc.department || "—")}</td>
      <td>${escapeHtml(lastOpenedText)}</td>
      <td>${escapeHtml(lastModifiedText)}</td>
      <td>${escapeHtml(sizeText)}</td>
      <td class="actions">
        <a href="#" class="open-link">Open</a>
        <a href="#" class="download-link">Download</a>
      </td>
    `;

    tr.querySelector(".open-link").addEventListener("click", (e) => {
      e.preventDefault();
      openDoc(doc);
    });

    tr.querySelector(".download-link").addEventListener("click", (e) => {
      e.preventDefault();
      downloadDoc(doc.id, doc.filename);
    });

    tbody.appendChild(tr);
  });
}

function openDoc(doc) {
  const url = new URL("documentView.html", window.location.href);
  url.searchParams.set("id", doc.id);
  url.searchParams.set("doc", doc.filename || "");
  window.location.href = url.toString();
}

async function downloadDoc(docId, filename) {
  const token = getToken();
  if (!token) {
    alert("You must log in first.");
    window.location.href = "login-signup.html";
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/documents/${docId}/download`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!res.ok) throw new Error("Download failed");

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = filename || `document-${docId}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    console.error(err);
    alert("Error downloading document");
  }
}

// Grid/List toggle
function setupViewToggle() {
  const gridEl = document.getElementById("documentsGrid");
  const listWrapper = document.querySelector(".documents-list");
  const toggle = document.querySelector(".view-toggle");
  if (!gridEl || !listWrapper || !toggle) return;

  const buttons = toggle.querySelectorAll("button");
  const gridBtn = buttons[0];
  const listBtn = buttons[1];

  function showGrid() {
    gridEl.style.display = "";
    listWrapper.style.display = "none";
    gridBtn.classList.add("active");
    listBtn.classList.remove("active");
  }

  function showList() {
    gridEl.style.display = "none";
    listWrapper.style.display = "";
    listBtn.classList.add("active");
    gridBtn.classList.remove("active");
  }

  showGrid();
  gridBtn.addEventListener("click", showGrid);
  listBtn.addEventListener("click", showList);
}

// Dropdown listeners should still fetch from backend
function setupDropdownListeners() {
  const selects = document.querySelectorAll(".documents-toolbar select");
  selects.forEach((select) => select.addEventListener("change", loadDocuments));
}

// Search listeners
function setupSearch() {
  const input = document.getElementById("searchInput");
  const btn = document.getElementById("searchBtn");

  if (btn) {
    btn.addEventListener("click", () => applySearchAndRender());
  }

  if (input) {
    // Enter key triggers search
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        applySearchAndRender();
      }
    });

    // live search while typing
    input.addEventListener("input", () => applySearchAndRender());
  }
}

// Helpers
function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function getIconLetter(filename) {
  const name = (filename || "").trim();
  return name ? name[0].toUpperCase() : "D";
}

function formatDatePretty(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function formatBytes(bytes) {
  const n = Number(bytes);
  if (!Number.isFinite(n) || n <= 0) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = n;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  const decimals = i === 0 ? 0 : 1;
  return `${value.toFixed(decimals)} ${units[i]}`;
}

document.addEventListener("DOMContentLoaded", () => {
  setupViewToggle();
  setupDropdownListeners();
  setupSearch();
  loadDocuments();
});
