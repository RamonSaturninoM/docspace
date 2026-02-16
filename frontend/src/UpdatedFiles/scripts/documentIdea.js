// Example: pin/unpin functionality
const pinBtn = document.getElementById("pinBtn");
let pinned = false;

pinBtn.addEventListener("click", () => {
  pinned = !pinned;
  pinBtn.textContent = pinned ? "Unpin Document" : "Pin Document";
  alert(pinned ? "Document pinned!" : "Document unpinned!");
});

// Comments section
const commentForm = document.getElementById("commentForm");
const commentInput = document.getElementById("commentInput");
const commentsList = document.getElementById("commentsList");

commentForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const commentText = commentInput.value.trim();
  if (!commentText) return;

  const newComment = document.createElement("div");
  newComment.classList.add("comment");
  newComment.innerHTML = `<strong>You:</strong> ${commentText}`;
  commentsList.appendChild(newComment);

  commentInput.value = "";
  commentsList.scrollTop = commentsList.scrollHeight;
});

// Placeholder: Load document title from URL
const params = new URLSearchParams(window.location.search);
const docTitle = params.get("doc");
if (docTitle) {
  document.getElementById("docTitle").textContent = docTitle;
  // For actual implementation: load the document in iframe here
}
