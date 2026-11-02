(function () {
  'use strict';

  const F = window.Kestrel;
  const { $, esc } = F;

  F.pages.home = async function () {
    const r = await F.api('/api/home');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your home page.', 'error');
    const h = r.data;
    $('#h-hello').textContent = `Hello, ${h.name}`;
    $('#h-hours').textContent = F.hours(h.week.total);
    $('#h-week').textContent = `Week of ${F.date(h.week.week)} · ${h.week.status}`;
    $('#h-leave').textContent = h.leave_left;
    $('#h-claims').textContent = F.eur(h.claims.pending);
    if (h.payslip) {
      $('#h-pay').textContent = F.eur(h.payslip.net);
      $('#h-pay-month').textContent = F.month(h.payslip.period);
    }
    $('#h-holidays').innerHTML = h.holidays.map((x) => `<li>${esc(x.name)} <span class="muted small">${F.day(x.date)}</span></li>`).join('') || '<li class="muted">No public holidays coming up.</li>';
    if (h.approvals != null) {
      $('#h-manager').hidden = false;
      $('#h-approvals').textContent = h.approvals ? `${F.plural(h.approvals, 'request')} waiting for you.` : 'Nothing waiting for you.';
    }
  };
})();
