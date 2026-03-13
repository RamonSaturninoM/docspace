(() => {
  const DOCSPACE_API_BASE =
    localStorage.getItem("DOCSPACE_API_BASE") ||
    window.DOCSPACE_API_BASE ||
    "http://127.0.0.1:8000";

  const apiUrl = (path) => `${DOCSPACE_API_BASE}${path}`;

  const apiFetch = async (path, options = {}) => {
    const response = await fetch(apiUrl(path), options);
    if (!response.ok) {
      let message = "Request failed";
      try {
        const payload = await response.json();
        message = payload.detail || payload.message || JSON.stringify(payload);
      } catch (_error) {
        message = await response.text();
      }
      throw new Error(message || "Request failed");
    }
    if (response.status === 204) {
      return null;
    }
    return response.json();
  };

  const formatBytes = (bytes = 0) => {
    if (!bytes) return "0 B";
    const units = ["B", "KB", "MB", "GB"];
    let value = bytes;
    let unitIndex = 0;
    while (value >= 1024 && unitIndex < units.length - 1) {
      value /= 1024;
      unitIndex += 1;
    }
    const rounded = value >= 10 || unitIndex === 0 ? value.toFixed(0) : value.toFixed(1);
    return `${rounded} ${units[unitIndex]}`;
  };

  const formatDate = (value) => {
    if (!value) return "Unknown";
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    }).format(new Date(value));
  };

  window.DocspaceApi = {
    DOCSPACE_API_BASE,
    apiFetch,
    apiUrl,
    formatBytes,
    formatDate,
  };
})();
