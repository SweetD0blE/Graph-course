(function () {
  'use strict';

  function setResult(form, message, modifier) {
    var slot = form.querySelector('[data-practice-result]');
    if (!slot) { return; }
    slot.textContent = message || '';
    slot.className = 'minitest-result' +
      (modifier ? ' minitest-result--' + modifier : '');
  }

  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form.classList || !form.classList.contains('practice-form')) {
      return;
    }
    e.preventDefault();

    var btn = form.querySelector('button[type="submit"]');
    if (btn) { btn.disabled = true; }
    setResult(form, 'Проверяем…', '');

    fetch(form.action, {
      method: 'POST',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      body: new FormData(form),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        setResult(
          form, data.message,
          data.ok ? (data.passed ? 'ok' : 'bad') : 'bad'
        );
        if (btn) { btn.disabled = false; }
      })
      .catch(function () {
        setResult(form, 'Ошибка сети, попробуйте ещё раз.', 'bad');
        if (btn) { btn.disabled = false; }
      });
  });
})();
