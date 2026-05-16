const themeToggle = document.getElementById("themeToggle");
const themeText = document.getElementById("themeText");
const themeIcon = document.getElementById("themeIcon");

const THEME_KEY = "graph-course-theme";

function applyTheme(theme) {
  const isLight = theme === "light";

  document.body.classList.toggle("light-theme", isLight);

  if (themeText && themeIcon) {
    themeText.textContent = isLight ? "Тёмный фон" : "Светлый фон";
    themeIcon.textContent = isLight ? "🌙" : "☀️";
  }
}

const savedTheme = localStorage.getItem(THEME_KEY) || "dark";
applyTheme(savedTheme);

themeToggle?.addEventListener("click", () => {
  const nextTheme = document.body.classList.contains("light-theme") ? "dark" : "light";

  localStorage.setItem(THEME_KEY, nextTheme);
  applyTheme(nextTheme);
});

document.querySelectorAll(".graph-node").forEach((node) => {
  node.addEventListener("click", () => {
    document.querySelectorAll(".graph-node").forEach((item) => item.classList.remove("is-selected"));
    node.classList.add("is-selected");
  });
});
