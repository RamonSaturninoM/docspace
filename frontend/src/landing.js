const fileInput = document.getElementById("file-input");
const fileList = document.getElementById("file-list");
const ingestBtn = document.getElementById("ingest-btn");
const clearBtn = document.getElementById("clear-btn");
const statusBox = document.getElementById("status");
const dropzone = document.getElementById("dropzone");

let files = [];

const setStatus = (title, message) => {
  statusBox.innerHTML = `<strong>${title}</strong>${message}`;
};

const refreshList = () => {
  fileList.innerHTML = "";
  if (!files.length) {
    fileList.innerHTML = "<em>No files selected yet.</em>";
    ingestBtn.disabled = true;
    clearBtn.disabled = true;
    return;
  }

  files.forEach((file) => {
    const row = document.createElement("div");
    row.className = "file";
    row.innerHTML = `<span>${file.name}</span><small>${(file.size / 1024).toFixed(1)} KB</small>`;
    fileList.appendChild(row);
  });

  ingestBtn.disabled = false;
  clearBtn.disabled = false;
};

const addFiles = (incoming) => {
  const allowed = [".md", ".markdown", ".txt", ".rst"];
  const added = Array.from(incoming).filter((file) =>
    allowed.some((ext) => file.name.toLowerCase().endsWith(ext))
  );
  if (!added.length) {
    setStatus("No supported files", "Please upload .md, .markdown, .txt, or .rst files.");
    return;
  }
  files = files.concat(added);
  refreshList();
  setStatus("Ready", `${files.length} file(s) queued for ingestion.`);
};

fileInput.addEventListener("change", (event) => {
  addFiles(event.target.files);
  fileInput.value = "";
});

dropzone.addEventListener("dragover", (event) => {
  event.preventDefault();
  dropzone.classList.add("dragover");
});

dropzone.addEventListener("dragleave", () => {
  dropzone.classList.remove("dragover");
});

dropzone.addEventListener("drop", (event) => {
  event.preventDefault();
  dropzone.classList.remove("dragover");
  addFiles(event.dataTransfer.files);
});

clearBtn.addEventListener("click", () => {
  files = [];
  refreshList();
  setStatus("Cleared", "Waiting for files. Files will be uploaded to <code>/api/ingest</code>.");
});

ingestBtn.addEventListener("click", async () => {
  if (!files.length) return;
  ingestBtn.disabled = true;
  setStatus("Uploading", "Sending files to the ingestion pipeline...");

  const formData = new FormData();
  files.forEach((file) => formData.append("files", file, file.name));

  try {
    const response = await fetch("/api/ingest", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText || "Ingestion failed");
    }

    const payload = await response.json().catch(() => ({}));
    files = [];
    refreshList();
    const detail = payload.message
      ? `Pipeline response: ${payload.message}`
      : "Files accepted. Check pipeline logs for progress.";
    setStatus("Ingestion started", detail);
  } catch (error) {
    setStatus("Upload failed", `Error: ${error.message}. Verify the ingestion endpoint is running.`);
    ingestBtn.disabled = false;
  }
});

refreshList();
