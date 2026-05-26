(function () {
  'use strict';

  function storageKey(id) { return 'gc.section.' + id + '.opened'; }

  function openSection(id) {
    var grid = document.querySelector(
      '.section-grid[data-section-id="' + id + '"]'
    );
    if (grid && grid.getAttribute('data-section-state') !== 'locked') {
      grid.setAttribute('data-section-state', 'opened');
    }
    var btn = document.querySelector(
      '.section-cta[data-open-section="' + id + '"]'
    );
    if (btn) { btn.hidden = true; }
  }

  // Восстанавливаем сохранённое состояние при загрузке
  document.querySelectorAll('.section-grid[data-section-id]')
    .forEach(function (grid) {
      if (grid.getAttribute('data-section-state') !== 'collapsed') return;
      var id = grid.getAttribute('data-section-id');
      try {
        if (localStorage.getItem(storageKey(id)) === '1') {
          openSection(id);
        }
      } catch (_) { /* localStorage недоступен */ }
    });

  // Клик по CTA — раскрыть и запомнить
  document.addEventListener('click', function (e) {
    var btn = e.target.closest && e.target.closest('[data-open-section]');
    if (!btn) { return; }
    e.preventDefault();
    var id = btn.getAttribute('data-open-section');
    try { localStorage.setItem(storageKey(id), '1'); } catch (_) {}
    openSection(id);
  });
})();
