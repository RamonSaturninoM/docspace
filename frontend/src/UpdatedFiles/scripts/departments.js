(() => {
  const { apiFetch } = window.DocspaceApi;
  const deptGrid = document.getElementById("departmentGrid");
  const searchInput = document.getElementById("searchInput");
  const searchBtn = document.getElementById("searchBtn");

  const renderDepartments = (departments) => {
    if (!departments || !departments.length) {
      deptGrid.innerHTML = "<p>No departments found.</p>";
      return;
    }

    deptGrid.innerHTML = departments.map(d => `
      <a class="department-card" href="documents.html?department=${encodeURIComponent(d.name)}">
        <h3>${d.name}</h3>
        <p>${d.description}</p>
        <span>${d.documentCount} Documents</span>
      </a>
    `).join("");
  };

  const loadDepartments = async () => {
    deptGrid.innerHTML = "<p>Loading departments...</p>";
    try {
      const data = await apiFetch("/api/departments");
      renderDepartments(data.departments || []);
    } catch (err) {
      deptGrid.innerHTML = "<p>Unable to load departments.</p>";
      console.error("Failed to load departments:", err);
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

  loadDepartments();
})();