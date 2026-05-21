(function () {
  'use strict';

  function setResult(form, message, modifier) {
    var slot = form.querySelector('[data-minitest-result]');
    if (!slot) { return; }
    slot.textContent = message || '';
    slot.className = 'minitest-result' +
      (modifier ? ' minitest-result--' + modifier : '');
  }

  function refreshBlocks() {
    var y = window.scrollY;
    fetch(window.location.href.split('#')[0], {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
      .then(function (r) { return r.text(); })
      .then(function (html) {
        var doc = new DOMParser().parseFromString(html, 'text/html');
        var fresh = doc.getElementById('topic-blocks');
        var container = document.getElementById('topic-blocks');
        if (!fresh || !container) { return; }
        container.innerHTML = fresh.innerHTML;
        window.scrollTo(0, y);
      });
  }

  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form.classList || !form.classList.contains('minitest-form')) {
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
        setResult(form, data.message, data.passed ? 'ok' : 'bad');
        if (data.passed) {
          refreshBlocks();
        } else if (btn) {
          btn.disabled = false;
        }
      })
      .catch(function () {
        setResult(form, 'Ошибка сети, попробуйте ещё раз.', 'bad');
        if (btn) { btn.disabled = false; }
      });
  });
})();
