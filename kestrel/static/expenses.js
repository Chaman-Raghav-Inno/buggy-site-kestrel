(function () {
  'use strict';

  const F = window.Kestrel;
  const { $, esc } = F;

  F.pages.expenses = async function () {
    let data;

    const original = (c) => (c.category === 'Mileage' ? `${c.km.toLocaleString('en-GB')} km`
      : c.currency === 'EUR' ? F.eur(c.amount) : `${c.amount.toLocaleString('en-GB')} ${esc(c.currency)}`);

    function draw() {
      const s = data.summary;
      $('#ex-pending').textContent = F.eur(s.pending);
      $('#ex-approved').textContent = F.eur(s.approved);
      $('#ex-mileage').textContent = `${s.mileage_km.toLocaleString('en-GB')} km`;
      $('#ex-rows').innerHTML = data.claims.map((c) => `<tr><td>${F.date(c.date)}</td>
          <td>${esc(c.category)}: ${esc(c.description)}${c.receipt ? ' <span class="muted small">· receipt</span>' : ''}${c.reason ? `<br><span class="muted small">${esc(c.reason)}</span>` : ''}</td>
          <td class="num">${original(c)}</td><td class="num">${F.eur(c.reimbursable)}</td><td>${F.status(c.status)}</td></tr>`).join('')
        || '<tr><td colspan="5" class="muted">No claims yet.</td></tr>';
      $('#ex-date').max = data.today;
    }

    function mode() {
      const mileage = $('#ex-category').value === 'Mileage';
      $('#ex-money').hidden = mileage;
      $('#ex-receipt-field').hidden = mileage;
      $('#ex-distance').hidden = !mileage;
      preview();
    }

    function preview() {
      if ($('#ex-category').value === 'Mileage') return F.say($('#ex-preview'), 'Mileage is paid per km; see the policies.');
      const amount = parseFloat($('#ex-amount').value);
      const cur = $('#ex-currency').value;
      if (!(amount > 0) || cur === 'EUR') return F.say($('#ex-preview'), '');
      F.say($('#ex-preview'), `About ${F.eur(amount * data.rates[cur])} at today's rate.`);
    }

    $('#ex-category').addEventListener('change', mode);
    $('#ex-currency').addEventListener('change', preview);
    $('#ex-amount').addEventListener('input', preview);
    $('#ex-form').addEventListener('submit', async () => {
      const msg = $('#ex-msg');
      const category = $('#ex-category').value;
      const body = { date: $('#ex-date').value, category, description: $('#ex-description').value.trim() };
      if (!body.date) return F.say(msg, 'Choose the date of the expense.', 'error');
      if (!body.description) return F.say(msg, 'Describe the expense.', 'error');
      if (category === 'Mileage') {
        body.km = Number($('#ex-km').value.replace(/,/g, ''));
        if (!(body.km > 0)) return F.say(msg, 'Enter the distance in km.', 'error');
      } else {
        body.currency = $('#ex-currency').value;
        body.amount = parseFloat($('#ex-amount').value);
        if (!(body.amount > 0)) return F.say(msg, 'Enter the amount.', 'error');
        const file = $('#ex-receipt').files[0];
        body.receipt = file ? file.name : '';
      }
      const r = await F.api('/api/expenses', body);
      if (!r.ok) return F.say(msg, r.data.error || 'Could not submit the claim.', 'error');
      data = r.data;
      draw();
      const added = data.claims.reduce((a, c) => (c.id > a.id ? c : a));
      $('#ex-form').reset();
      mode();
      F.say(msg, `Claim submitted: ${F.eur(added.reimbursable)} to be reimbursed.`, 'success');
    });

    const r = await F.api('/api/expenses');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your claims.', 'error');
    data = r.data;
    draw();
    mode();
    $('#loading').hidden = true;
    $('#expenses').hidden = false;
  };
})();
