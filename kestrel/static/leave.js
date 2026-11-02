(function () {
  'use strict';

  const F = window.Kestrel;
  const { $, $$, esc } = F;

  F.pages.leave = async function () {
    let data;
    let cancelling = null;

    const days = (n) => F.plural(n, 'day');
    const range = (r) => (r.start === r.end ? F.day(r.start) : `${F.day(r.start)} to ${F.day(r.end)}`);

    function draw() {
      const b = data.balance;
      $('#lv-balance').innerHTML = [
        ['Yearly allowance', days(b.allowance)], ['Carried over from last year', days(b.carried)],
        ['Booked and requested', days(b.used)], ['Available', days(b.available)],
      ].map(([k, v], i) => `<div${i === 3 ? ' class="total"' : ''}><dt>${k}</dt><dd>${v}</dd></div>`).join('');
      $('#lv-rows').innerHTML = data.requests.map((r) => {
        const upcoming = (r.status === 'pending' || r.status === 'approved') && r.start > data.today;
        return `<tr><td>${range(r)}${r.half ? ' <span class="muted small">(half day)</span>' : ''}${r.reason ? `<br><span class="muted small">${esc(r.reason)}</span>` : ''}</td>
          <td class="num">${r.days}</td><td>${F.status(r.status)}</td>
          <td>${upcoming ? `<button type="button" class="link" data-cancel="${r.id}">Cancel</button>` : ''}</td></tr>`;
      }).join('') || '<tr><td colspan="4" class="muted">No requests yet.</td></tr>';
      $('#lv-holidays').innerHTML = data.holidays.map((h) => `<li>${esc(h.name)} <span class="muted small">${F.date(h.date)}</span></li>`).join('');
      $('#lv-start').min = data.today;
      $('#lv-end').min = data.today;
    }

    function preview() {
      const start = $('#lv-start').value;
      const end = $('#lv-end').value || start;
      if (!start) return F.say($('#lv-preview'), '');
      if ($('#lv-half').checked) return F.say($('#lv-preview'), 'This request uses 0.5 days.');
      const n = Math.round((new Date(end) - new Date(start)) / 864e5) + 1;
      F.say($('#lv-preview'), n > 0 ? `This request uses ${days(n)}.` : '');
    }

    ['#lv-start', '#lv-end', '#lv-half'].forEach((s) => $(s).addEventListener('change', preview));
    $('#lv-form').addEventListener('submit', async () => {
      const msg = $('#lv-msg');
      const start = $('#lv-start').value;
      if (!start) return F.say(msg, 'Choose the first day.', 'error');
      const body = { start, end: $('#lv-end').value || start, half: $('#lv-half').checked, note: $('#lv-note').value };
      const r = await F.api('/api/leave', body);
      if (!r.ok) return F.say(msg, r.data.error || 'Could not send the request.', 'error');
      data = r.data;
      draw();
      $('#lv-form').reset();
      preview();
      F.say(msg, 'Request sent to your manager.', 'success');
    });
    $('#lv-rows').addEventListener('click', (e) => {
      const b = e.target.closest('[data-cancel]');
      if (!b) return;
      cancelling = Number(b.dataset.cancel);
      const r = data.requests.find((x) => x.id === cancelling);
      $('#lv-cancel-text').textContent = `${range(r)} (${days(r.days)}) will be cancelled.`;
      $('#lv-cancel').returnValue = '';
      $('#lv-cancel').showModal();
    });
    $$('#lv-cancel button').forEach((b) => b.addEventListener('click', () => $('#lv-cancel').close(b.dataset.value)));
    $('#lv-cancel').addEventListener('close', async () => {
      if ($('#lv-cancel').returnValue !== 'cancel' || !cancelling) return;
      const r = await F.api(`/api/leave/${cancelling}/cancel`, {});
      if (!r.ok) return F.toast(r.data.error || 'Could not cancel the leave.', 'error');
      data = r.data;
      draw();
      F.toast('Leave cancelled.');
    });

    const r = await F.api('/api/leave');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your leave.', 'error');
    data = r.data;
    draw();
    $('#loading').hidden = true;
    $('#leave').hidden = false;
  };
})();
