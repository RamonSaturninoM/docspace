const pinBtn = document.getElementById("pinBtn");
let pinned = false;

pinBtn.addEventListener("click", () => {
  pinned = !pinned;
  pinBtn.textContent = pinned ? "Unpin Document" : "Pin Document";
  alert(pinned ? "Document pinned!" : "Document unpinned!");
});

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

const params = new URLSearchParams(window.location.search);
const docTitle = params.get("doc");
if (docTitle) {
  document.getElementById("docTitle").textContent = docTitle;
}
