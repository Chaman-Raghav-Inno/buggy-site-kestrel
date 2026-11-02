(function () {
  'use strict';

  const F = window.Kestrel;
  const { $, $$, esc } = F;
  const KIND = { timesheet: 'Timesheet', leave: 'Leave', expense: 'Expense' };

  F.pages.approvals = async function () {
    let items = [];
    let kind = '';
    const selected = new Set();
    const key = (i) => `${i.kind}|${i.id}`;
    const visible = () => items.filter((i) => !kind || i.kind === kind);

    function draw() {
      const rows = visible();
      $('#ap-rows').innerHTML = rows.map((i) => `<tr><td><label class="sr-only" for="c-${esc(key(i))}">Select ${esc(i.who)}'s ${KIND[i.kind].toLowerCase()}</label>
          <input type="checkbox" id="c-${esc(key(i))}" data-key="${esc(key(i))}"${selected.has(key(i)) ? ' checked' : ''}></td>
          <td>${esc(i.who)}</td><td>${KIND[i.kind]}</td><td>${esc(i.summary)}</td></tr>`).join('')
        || '<tr><td colspan="4" class="muted">Nothing waiting for you.</td></tr>';
      const checked = rows.filter((i) => selected.has(key(i))).length;
      $('#ap-all').checked = rows.length > 0 && checked === rows.length;
      $('#ap-count').textContent = checked ? `${checked} selected` : '';
    }

    async function decide(action, reason) {
      const picked = items.filter((i) => selected.has(key(i))).map((i) => ({ kind: i.kind, id: i.id }));
      if (!picked.length) return F.say($('#ap-msg'), 'Select at least one request.', 'error');
      const r = await F.api('/api/approvals', { action, reason, items: picked });
      if (!r.ok) return F.say($('#ap-msg'), r.data.error || 'Could not save your decision.', 'error');
      items = r.data.items;
      selected.clear();
      draw();
      F.say($('#ap-msg'), `${action === 'approve' ? 'Approved' : 'Rejected'} ${F.plural(r.data.done, 'request')}.`, 'success');
    }

    $$('.tabs [role="tab"]').forEach((t) => t.addEventListener('click', () => {
      kind = t.dataset.kind;
      $$('.tabs [role="tab"]').forEach((x) => x.setAttribute('aria-selected', String(x === t)));
      draw();
    }));
    $('#ap-rows').addEventListener('change', (e) => {
      const k = e.target.dataset.key;
      if (!k) return;
      if (e.target.checked) selected.add(k);
      else selected.delete(k);
      draw();
    });
    $('#ap-all').addEventListener('change', (e) => {
      items.forEach((i) => (e.target.checked ? selected.add(key(i)) : selected.delete(key(i))));
      draw();
    });
    $('#ap-approve').addEventListener('click', () => decide('approve', ''));
    $('#ap-reject').addEventListener('click', () => {
      if (!visible().some((i) => selected.has(key(i)))) return F.say($('#ap-msg'), 'Select at least one request.', 'error');
      $('#ap-reason').value = '';
      $('#ap-dialog').returnValue = '';
      $('#ap-dialog').showModal();
    });
    $$('#ap-dialog button').forEach((b) => b.addEventListener('click', () => $('#ap-dialog').close(b.dataset.value)));
    $('#ap-dialog').addEventListener('close', () => {
      if ($('#ap-dialog').returnValue === 'reject') decide('reject', $('#ap-reason').value.trim());
    });

    const r = await F.api('/api/approvals');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your approvals.', 'error');
    items = r.data.items;
    draw();
  };
})();
