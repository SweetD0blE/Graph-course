// Автозаполнение формы регистрации по справочнику сотрудников.
// При вводе ФИО (>= 2 символов) подтягиваются подсказки из БД;
// выбор сотрудника заполняет остальные поля (редактируемые).

const fioInput = document.getElementById("full_name");
const fioList = document.getElementById("fioSuggestions");

if (fioInput && fioList) {
  const fields = {
    full_name: fioInput,
    staff_number: document.getElementById("staff_number"),
    email: document.getElementById("email"),
    department: document.getElementById("department"),
    position: document.getElementById("position"),
  };

  let items = [];
  let activeIndex = -1;
  let debounceTimer = null;

  function closeList() {
    fioList.hidden = true;
    fioList.innerHTML = "";
    items = [];
    activeIndex = -1;
  }

  function highlight(index) {
    const lis = fioList.querySelectorAll("li");
    lis.forEach((li, i) => li.classList.toggle("is-active", i === index));
    activeIndex = index;
  }

  function applyEmployee(emp) {
    Object.keys(fields).forEach((key) => {
      if (fields[key] && typeof emp[key] === "string") {
        fields[key].value = emp[key];
      }
    });
    closeList();
  }

  function render() {
    fioList.innerHTML = "";
    if (items.length === 0) {
      closeList();
      return;
    }
    items.forEach((emp, i) => {
      const li = document.createElement("li");
      const name = document.createElement("span");
      name.textContent = emp.full_name;
      const meta = document.createElement("small");
      meta.className = "autocomplete__meta";
      meta.textContent = [emp.position, emp.department]
        .filter(Boolean)
        .join(" · ");
      li.appendChild(name);
      if (meta.textContent) li.appendChild(meta);

      // mousedown, чтобы выбор сработал до blur инпута.
      li.addEventListener("mousedown", (e) => {
        e.preventDefault();
        applyEmployee(emp);
      });
      li.addEventListener("mouseenter", () => highlight(i));
      fioList.appendChild(li);
    });
    fioList.hidden = false;
    activeIndex = -1;
  }

  async function search(query) {
    try {
      const resp = await fetch(
        "/register/employees?q=" + encodeURIComponent(query)
      );
      if (!resp.ok) {
        closeList();
        return;
      }
      items = await resp.json();
      render();
    } catch (err) {
      closeList();
    }
  }

  fioInput.addEventListener("input", () => {
    const value = fioInput.value.trim();
    window.clearTimeout(debounceTimer);
    if (value.length < 2) {
      closeList();
      return;
    }
    debounceTimer = window.setTimeout(() => search(value), 200);
  });

  fioInput.addEventListener("keydown", (e) => {
    if (fioList.hidden || items.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      highlight((activeIndex + 1) % items.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      highlight((activeIndex - 1 + items.length) % items.length);
    } else if (e.key === "Enter") {
      if (activeIndex >= 0) {
        e.preventDefault();
        applyEmployee(items[activeIndex]);
      }
    } else if (e.key === "Escape") {
      closeList();
    }
  });

  document.addEventListener("click", (e) => {
    const box = document.getElementById("fioAutocomplete");
    if (box && !box.contains(e.target)) {
      closeList();
    }
  });
}
