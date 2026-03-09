function showSignup() {
  document.getElementById("loginForm").classList.add("hidden");
  document.getElementById("signupForm").classList.remove("hidden");
}

function showLogin() {
  document.getElementById("signupForm").classList.add("hidden");
  document.getElementById("loginForm").classList.remove("hidden");
}

const API_BASE = "http://127.0.0.1:8000";

function showMessage(formEl, message, isError = false) {
  const old = formEl.querySelector(".api-message");
  if (old) old.remove();

  const div = document.createElement("div");
  div.className = "api-message";
  div.style.marginTop = "12px";
  div.style.padding = "10px";
  div.style.borderRadius = "8px";
  div.style.fontSize = "14px";
  div.style.border = "1px solid";
  div.style.background = isError ? "#ffe6e6" : "#e6ffed";
  div.style.borderColor = isError ? "#ff4d4d" : "#2ecc71";
  div.style.color = isError ? "#b30000" : "#0f5132";
  div.textContent = message;

  formEl.appendChild(div);
}

async function apiPost(path, bodyObj) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(bodyObj),
  });

  let data = null;
  try {
    data = await res.json();
  } catch {
    // ignore non-json response
  }

  if (!res.ok) {
    const msg =
      (data && (data.detail || data.message)) ||
      `Request failed (${res.status})`;
    throw new Error(msg);
  }

  return data;
}

async function loadDepartmentsForSignup() {
  const departmentSelect = document.getElementById("department");
  if (!departmentSelect) return;

  try {
    departmentSelect.innerHTML = `<option value="">Loading departments...</option>`;

    const res = await fetch(`${API_BASE}/departments`);

    if (!res.ok) {
      throw new Error(`Failed to load departments (${res.status})`);
    }

    const departments = await res.json();

    departmentSelect.innerHTML = "";

    if (!Array.isArray(departments) || departments.length === 0) {
      departmentSelect.innerHTML = `<option value="">No departments available</option>`;
      return;
    }

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Select a department";
    departmentSelect.appendChild(placeholder);

    departments.forEach((dept) => {
      const option = document.createElement("option");
      option.value = dept.name;
      option.textContent = dept.name;
      departmentSelect.appendChild(option);
    });
  } catch (err) {
    console.error(err);
    departmentSelect.innerHTML = `<option value="">Could not load departments</option>`;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const loginForm = document.getElementById("loginFormElement");
  const signupForm = document.getElementById("signupFormElement");

  loadDepartmentsForSignup();

  if (loginForm) {
    loginForm.addEventListener("submit", async function (e) {
      e.preventDefault();

      const email = document.getElementById("loginEmail").value.trim();
      const password = document.getElementById("loginPassword").value;

      try {
        const data = await apiPost("/auth/login", { email, password });

        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("token_type", data.token_type);

        showMessage(loginForm, data.message || "Login successful", false);

        setTimeout(() => {
          window.location.href = "documents.html";
        }, 300);
      } catch (err) {
        showMessage(loginForm, err.message, true);
      }
    });
  }

  if (signupForm) {
    signupForm.addEventListener("submit", async function (e) {
      e.preventDefault();

      const full_name = document.getElementById("name").value.trim();
      const email = document.getElementById("signupEmail").value.trim();
      const department = document.getElementById("department").value;
      const password = document.getElementById("signupPassword").value;

      if (!department) {
        showMessage(signupForm, "Please select a department", true);
        return;
      }

      try {
        await apiPost("/auth/signup", { full_name, email, password, department });

        showMessage(signupForm, "Account created", false);

        setTimeout(() => {
          showLogin();
        }, 800);
      } catch (err) {
        showMessage(signupForm, err.message, true);
      }
    });
  }
});