const API_BASE = "http://127.0.0.1:8000";

let allDepartments = [];
let currentUser = null;

function getToken() {
  return localStorage.getItem("access_token");
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

function isAdmin() {
  return currentUser && currentUser.role === "admin";
}

function showAdminMessage(message, isError = false) {
  const box = document.getElementById("adminMessage");
  if (!box) return;

  box.textContent = message;
  box.classList.remove("hidden", "success", "error");
  box.classList.add(isError ? "error" : "success");
}

function clearAdminMessage() {
  const box = document.getElementById("adminMessage");
  if (!box) return;

  box.textContent = "";
  box.classList.add("hidden");
  box.classList.remove("success", "error");
}

async function loadCurrentUser() {
  const token = getToken();
  if (!token) {
    alert("You must log in first.");
    window.location.href = "login-signup.html";
    return;
  }

  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    localStorage.removeItem("access_token");
    localStorage.removeItem("token_type");
    alert("Your session expired. Please log in again.");
    window.location.href = "login-signup.html";
    return;
  }

  currentUser = await res.json();

  const adminControls = document.getElementById("adminControls");
  if (adminControls && isAdmin()) {
    adminControls.classList.remove("hidden");
  }
}

function buildDepartmentCard(department) {
  const card = document.createElement("div");
  card.className = "department-card";

  const link = document.createElement("a");
  link.className = "department-card-link";
  link.href = `department-documents.html?dept=${encodeURIComponent(department.name)}`;

  const title = document.createElement("h3");
  title.textContent = department.name || "Unnamed Department";

  const description = document.createElement("p");
  description.textContent =
    department.description && department.description.trim()
      ? department.description
      : "No description provided.";

  const actionText = document.createElement("span");
  const count = Number(department.document_count) || 0;
  actionText.textContent = count === 1 ? "1 document" : `${count} documents`;

  link.appendChild(title);
  link.appendChild(description);
  link.appendChild(actionText);

  card.appendChild(link);

  if (isAdmin()) {
    const actions = document.createElement("div");
    actions.className = "department-card-actions";

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "delete-department-btn";
    deleteBtn.textContent = "Delete";

    deleteBtn.addEventListener("click", async () => {
      const confirmed = window.confirm(
        `Delete "${department.name}"?\n\nThis will only work if no users or documents use that department.`
      );

      if (!confirmed) return;

      await deleteDepartment(department.id);
    });

    actions.appendChild(deleteBtn);
    card.appendChild(actions);
  }

  return card;
}

function getSearchText() {
  const input = document.getElementById("departmentSearchInput");
  return (input ? input.value : "").trim().toLowerCase();
}

function renderDepartments() {
  const grid = document.getElementById("departmentGrid");
  if (!grid) return;

  const q = getSearchText();

  let departments = allDepartments;

  if (q) {
    departments = departments.filter((dept) => {
      const name = (dept.name || "").toLowerCase();
      const description = (dept.description || "").toLowerCase();
      return name.includes(q) || description.includes(q);
    });
  }

  grid.innerHTML = "";

  if (!Array.isArray(departments) || departments.length === 0) {
    const empty = document.createElement("p");
    empty.textContent = q
      ? "No departments match your search."
      : "No departments found yet.";
    grid.appendChild(empty);
    return;
  }

  departments.forEach((department) => {
    const card = buildDepartmentCard(department);
    grid.appendChild(card);
  });
}

async function loadDepartments() {
  const grid = document.getElementById("departmentGrid");
  const status = document.getElementById("departmentsStatus");

  if (!grid) return;

  try {
    const res = await fetch(`${API_BASE}/departments`);

    if (!res.ok) {
      throw new Error(`Failed to load departments (${res.status})`);
    }

    allDepartments = await res.json();
    renderDepartments();
  } catch (err) {
    console.error(err);

    if (status) {
      status.textContent = "Error loading departments.";
    } else {
      grid.innerHTML = "<p>Error loading departments.</p>";
    }
  }
}

async function createDepartment(name, description) {
  const token = getToken();
  if (!token) {
    alert("You must log in first.");
    window.location.href = "login-signup.html";
    return;
  }

  const res = await fetch(`${API_BASE}/departments`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      name,
      description,
    }),
  });

  const data = await res.json().catch(() => null);

  if (!res.ok) {
    const message =
      (data && (data.detail || data.message)) ||
      `Failed to create department (${res.status})`;
    throw new Error(message);
  }

  return data;
}

async function deleteDepartment(departmentId) {
  clearAdminMessage();

  const token = getToken();
  if (!token) {
    alert("You must log in first.");
    window.location.href = "login-signup.html";
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/departments/${departmentId}`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    const data = await res.json().catch(() => null);

    if (!res.ok) {
      const message =
        (data && (data.detail || data.message)) ||
        `Failed to delete department (${res.status})`;
      throw new Error(message);
    }

    showAdminMessage(`Department "${data.name}" deleted successfully.`);
    await loadDepartments();
  } catch (err) {
    console.error(err);
    showAdminMessage(err.message, true);
  }
}

function setupSearch() {
  const input = document.getElementById("departmentSearchInput");
  if (!input) return;

  input.addEventListener("input", renderDepartments);
}

function setupAdminForm() {
  const form = document.getElementById("addDepartmentForm");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAdminMessage();

    const nameInput = document.getElementById("departmentNameInput");
    const descriptionInput = document.getElementById("departmentDescriptionInput");

    const name = nameInput ? nameInput.value.trim() : "";
    const description = descriptionInput ? descriptionInput.value.trim() : "";

    if (!name) {
      showAdminMessage("Department name is required.", true);
      return;
    }

    try {
      await createDepartment(name, description);
      showAdminMessage(`Department "${name}" created successfully.`);

      form.reset();
      await loadDepartments();
    } catch (err) {
      console.error(err);
      showAdminMessage(err.message, true);
    }
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  setupSearch();
  setupAdminForm();
  await loadCurrentUser();
  await loadDepartments();
});