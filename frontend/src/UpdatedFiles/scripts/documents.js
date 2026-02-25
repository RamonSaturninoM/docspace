const API_BASE = "http://127.0.0.1:8000";

// Get token from login
function getToken() {
  return localStorage.getItem("access_token");
}

// Get dropdown values 
function getFilterParams() {
  const selects = document.querySelectorAll(".documents-toolbar select");

  const viewSelect = selects[0]; // Showing
  const typeSelect = selects[1]; // Type
  const sortSelect = selects[2]; // Sort

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

// Load documents from backend with filters
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

    if (!res.ok) {
      throw new Error("Failed to load documents");
    }

    const docs = await res.json();


    renderGrid(docs);
    renderList(docs);
  } catch (err) {
    console.error(err);
    alert("Error loading documents");
  }
}


function renderGrid(docs) {
  const grid = document.querySelector(".documents-grid");
  if (!grid) return;

  grid.innerHTML = "";

  docs.forEach((doc) => {
    const card = document.createElement("div");
    card.className = "document-card";

    // Make card open viewer
    card.addEventListener("click", () => openDoc(doc));

    card.innerHTML = `
      <div class="doc-icon">D</div>
      <h3>${escapeHtml(doc.filename)}</h3>
      <div class="meta">${escapeHtml(doc.department)} • ${escapeHtml(doc.role)}</div>
    `;

    grid.appendChild(card);
  });
}


function renderList(docs) {
  const tbody = document.querySelector(".documents-list tbody");
  if (!tbody) return;

  tbody.innerHTML = "";

  docs.forEach((doc) => {
    const tr = document.createElement("tr");

    // Not in DB yet
    const ownerText = "—";
    const lastOpenedText = "—";
    const lastModifiedText = formatDate(doc.uploaded_at);
    const sizeText = "—";

    tr.innerHTML = `
      <td class="doc-name-cell">
        <span class="small-icon">D</span>
        ${escapeHtml(doc.filename)}
      </td>
      <td>${escapeHtml(ownerText)}</td>
      <td>${escapeHtml(doc.department)}</td>
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
      downloadDoc(doc.id);
    });

    tbody.appendChild(tr);
  });
}

// -open and download
function openDoc(doc) {
  const url = new URL("documentView.html", window.location.href);
  url.searchParams.set("id", doc.id);
  url.searchParams.set("doc", doc.filename);
  window.location.href = url.toString();
}

async function downloadDoc(docId) {
  const token = getToken();
  if (!token) {
    alert("You must log in first.");
    window.location.href = "login-signup.html";
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/documents/${encodeURIComponent(docId)}/download`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!res.ok) {
      throw new Error(`Download failed (${res.status})`);
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = `document-${docId}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    console.error(err);
    alert("Error downloading document");
  }
}

function setupViewToggle() {
  const gridEl = document.querySelector(".documents-grid");
  const listEl = document.querySelector(".documents-list");
  const toggle = document.querySelector(".view-toggle");
  if (!gridEl || !listEl || !toggle) return;

  const [gridBtn, listBtn] = toggle.querySelectorAll("button");

  function showGrid() {
    gridEl.style.display = "";
    listEl.style.display = "none";
    gridBtn.classList.add("active");
    listBtn.classList.remove("active");
  }

  function showList() {
    gridEl.style.display = "none";
    listEl.style.display = "";
    listBtn.classList.add("active");
    gridBtn.classList.remove("active");
  }

  // initial state based on HTML
  if (listBtn.classList.contains("active")) showList();
  else showGrid();

  gridBtn.addEventListener("click", showGrid);
  listBtn.addEventListener("click", showList);
}

// Attach dropdown change listeners 
function setupDropdownListeners() {
  const selects = document.querySelectorAll(".documents-toolbar select");
  selects.forEach((select) => select.addEventListener("change", loadDocuments));
}

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatDate(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString();
}

// Run when page loads
document.addEventListener("DOMContentLoaded", () => {
  setupViewToggle();
  setupDropdownListeners();
  loadDocuments();
});