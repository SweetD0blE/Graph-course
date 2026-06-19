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

/**
 * Универсальная отрисовка SVG-связей между HTML-узлами.
 *
 * Зачем так:
 * - узлы позиционируются CSS-ом;
 * - JS берёт их реальные координаты;
 * - SVG-линии рисуются от границы карточки до границы карточки;
 * - при resize всё пересчитывается.
 */
function getLocalRect(element, parentRect) {
  const rect = element.getBoundingClientRect();

  return {
    left: rect.left - parentRect.left,
    top: rect.top - parentRect.top,
    right: rect.right - parentRect.left,
    bottom: rect.bottom - parentRect.top,
    width: rect.width,
    height: rect.height,
    centerX: rect.left - parentRect.left + rect.width / 2,
    centerY: rect.top - parentRect.top + rect.height / 2,
  };
}

function getRectEdgePoint(rect, targetPoint) {
  const dx = targetPoint.x - rect.centerX;
  const dy = targetPoint.y - rect.centerY;

  if (dx === 0 && dy === 0) {
    return {
      x: rect.centerX,
      y: rect.centerY,
    };
  }

  const halfWidth = rect.width / 2;
  const halfHeight = rect.height / 2;
  const scale = 1 / Math.max(Math.abs(dx) / halfWidth, Math.abs(dy) / halfHeight);

  return {
    x: rect.centerX + dx * scale,
    y: rect.centerY + dy * scale,
  };
}

function createSvgLine(svg, start, end) {
  const line = document.createElementNS("http://www.w3.org/2000/svg", "line");

  line.setAttribute("x1", start.x.toFixed(2));
  line.setAttribute("y1", start.y.toFixed(2));
  line.setAttribute("x2", end.x.toFixed(2));
  line.setAttribute("y2", end.y.toFixed(2));

  svg.appendChild(line);
}

function drawConnectedGraph({ mapSelector, svgSelector, nodeSelector, nodeDataKey, connections }) {
  const graphMap = document.querySelector(mapSelector);
  const svg = document.querySelector(svgSelector);

  if (!graphMap || !svg) {
    return;
  }

  const mapRect = graphMap.getBoundingClientRect();

  if (!mapRect.width || !mapRect.height) {
    return;
  }

  svg.setAttribute("viewBox", `0 0 ${mapRect.width} ${mapRect.height}`);
  svg.innerHTML = "";

  const nodes = new Map();

  graphMap.querySelectorAll(nodeSelector).forEach((node) => {
    nodes.set(node.dataset[nodeDataKey], getLocalRect(node, mapRect));
  });

  connections.forEach(([fromId, toId]) => {
    const fromRect = nodes.get(fromId);
    const toRect = nodes.get(toId);

    if (!fromRect || !toRect) {
      return;
    }

    const fromCenter = {
      x: fromRect.centerX,
      y: fromRect.centerY,
    };

    const toCenter = {
      x: toRect.centerX,
      y: toRect.centerY,
    };

    const start = getRectEdgePoint(fromRect, toCenter);
    const end = getRectEdgePoint(toRect, fromCenter);

    createSvgLine(svg, start, end);
  });
}

const graphConnections = [
  ["basics", "metrics"],
  ["basics", "practice"],
  ["practice", "metrics"],
  ["metrics", "algorithms"],
  ["metrics", "test"],
];

function drawAllGraphs() {
  // На главной граф убран — дерево курса не требует SVG-линий.
  // Декоративный граф остался только на странице входа (auth).
  drawConnectedGraph({
    mapSelector: "[data-auth-graph-map]",
    svgSelector: "[data-auth-graph-lines]",
    nodeSelector: "[data-auth-node]",
    nodeDataKey: "authNode",
    connections: graphConnections,
  });
}

function scheduleGraphDraw() {
  window.requestAnimationFrame(drawAllGraphs);
}

scheduleGraphDraw();
window.addEventListener("load", scheduleGraphDraw);
window.addEventListener("resize", scheduleGraphDraw);

if ("ResizeObserver" in window) {
  const observer = new ResizeObserver(scheduleGraphDraw);

  document.querySelectorAll("[data-auth-graph-map], [data-auth-node]").forEach((element) => {
    observer.observe(element);
  });
}

// Табельный номер: только цифры (ввод и вставка), максимум 8 знаков.
document.addEventListener("input", (e) => {
  const el = e.target;
  if (!el || el.name !== "staff_number") return;
  const digits = el.value.replace(/\D/g, "").slice(0, 8);
  if (el.value !== digits) el.value = digits;
});
