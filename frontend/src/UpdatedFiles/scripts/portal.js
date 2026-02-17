// This page only handles search functionality for now
const searchBtn = document.getElementById("searchBtn");
const searchInput = document.getElementById("searchInput");

searchBtn.addEventListener("click", () => {
  const query = searchInput.value.trim();
  if(!query) return alert("Enter a search term!");
  // Placeholder for redirect/search logic
  alert(`Search triggered for: "${query}"`);
});