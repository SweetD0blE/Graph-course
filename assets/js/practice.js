(function () {
  'use strict';

  function setResult(form, message, modifier) {
    var slot = form.querySelector('[data-practice-result]');
    if (!slot) { return; }
    slot.textContent = message || '';
    slot.className = 'minitest-result' +
      (modifier ? ' minitest-result--' + modifier : '');
  }

  function lockCell(form) {
    var nbAnswer = form.querySelector('.nb-answer');
    if (!nbAnswer) { return; }
    var label = nbAnswer.querySelector('.card-label');
    var labelText = label ? label.outerHTML : '';
    form.outerHTML =
      '<div class="nb-answer">' + labelText +
      '<p style="margin-top:8px">' +
      '<span class="tag tag--success">✓ Ответ принят</span>' +
      '</p></div>';
  }

  function showCompletion(nextUrl) {
    var card = document.querySelector('[data-topic-done-card]');
    if (!card) { return; }
    card.hidden = false;
    if (nextUrl) {
      var link = card.querySelector('[data-next-topic]');
      if (link) { link.setAttribute('href', nextUrl); }
    }
  }

  function handleResponse(form, data) {
    setResult(
      form, data.message,
      data.ok ? (data.passed ? 'ok' : 'bad') : 'bad'
    );
    if (data.topic_done) {
      showCompletion(data.next_url);
    }
    if (data.cell_done) {
      lockCell(form);
    }
  }

  function submitForm(form, ok, beforeRequest) {
    var btn = form.querySelector('button[type="submit"]');
    if (btn) { btn.disabled = true; }
    if (beforeRequest) { beforeRequest(); }
    fetch(form.action, {
      method: 'POST',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      body: new FormData(form),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        ok(data);
        if (btn && !data.cell_done) { btn.disabled = false; }
      })
      .catch(function () {
        setResult(form, 'Ошибка сети, попробуйте ещё раз.', 'bad');
        if (btn) { btn.disabled = false; }
      });
  }

  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form.classList) { return; }

    if (form.classList.contains('practice-form')) {
      e.preventDefault();
      submitForm(form, function (data) {
        handleResponse(form, data);
      }, function () { setResult(form, 'Проверяем…', ''); });
      return;
    }

    if (form.classList.contains('practice-read-form')) {
      e.preventDefault();
      submitForm(form, function (data) {
        if (data.topic_done) {
          showCompletion(data.next_url);
          form.hidden = true;
        } else {
          setResult(form, data.message || 'Не удалось отметить.', 'bad');
        }
      }, function () { setResult(form, 'Отмечаем…', ''); });
    }
  });
})();
