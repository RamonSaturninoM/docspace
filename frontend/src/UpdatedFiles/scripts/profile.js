(() => {
  const { apiFetch, formatDate } = window.DocspaceApi;

  const profileName = document.getElementById("profileName");
  const profileRole = document.getElementById("profileRole");
  const profileMeta = document.getElementById("profileMeta");
  const profileAvatar = document.getElementById("profileAvatar");

  const activityGrid = document.getElementById("activityGrid");
  const pinnedGrid = document.getElementById("pinnedGrid");
  const permissionsGrid = document.getElementById("permissionsGrid");

  async function loadProfile() {
    try {
      const profile = await apiFetch("/api/user/me");
      profileName.textContent = profile.name;
      profileRole.textContent = profile.role;
      profileAvatar.src = profile.avatar || "images/random-profile-pic.jpg";

      profileMeta.innerHTML = `
        <p>Email: ${profile.email}</p>
        <p>Department: ${profile.department}</p>
        <p>Employee ID: ${profile.employeeId}</p>
        <p>Location: ${profile.location}</p>
      `;

      const activity = await apiFetch("/api/user/me/activity");
      activityGrid.innerHTML = activity.map(act => `
        <div class="activity-card">
          <h4>${act.title}</h4>
          <p>${act.status} — ${formatDate(act.time)}</p>
        </div>
      `).join("");

      const pinned = await apiFetch("/api/user/me/pinned");
      pinnedGrid.innerHTML = pinned.map(doc => `
        <div class="activity-card">
          <h4>${doc.title}</h4>
          <p>Pinned by You</p>
        </div>
      `).join("");

      const permissions = await apiFetch("/api/user/me/permissions");
      permissionsGrid.innerHTML = permissions.map(p => `
        <div class="activity-card">
          <h4>${p.title}</h4>
          ${p.details.map(d => `<p>${d}</p>`).join("")}
        </div>
      `).join("");

    } catch (err) {
      console.error("Failed to load profile:", err);
      profileName.textContent = "Unable to load profile";
      activityGrid.innerHTML = "<p>Error loading activity</p>";
    }
  }

  loadProfile();
})();

function showTab(tabId) {
  document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.add('hidden'));
  document.getElementById(tabId).classList.remove('hidden');
  document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
  event.target.classList.add('active');
}

function toggleSettingsMenu() {
  document.getElementById("settingsMenu").classList.toggle("hidden");
}