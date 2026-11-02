(function () {
  'use strict';

  const F = window.Kestrel;
  const { $ } = F;

  F.pages.payslips = async function () {
    const r = await F.api('/api/payslips');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your payslips.', 'error');
    $('#ps-rows').innerHTML = r.data.payslips.map((p) => `<tr><td><a href="/payslip?id=${p.id}">${F.month(p.period)}</a></td>
        <td>${F.date(p.paid)}</td><td class="num">${F.eur(p.gross)}</td><td class="num">${F.eur(p.net)}</td>
        <td><a href="/api/payslips/${p.id}.csv" download="payslip-${p.period.slice(0, 7)}.csv">Download CSV</a></td></tr>`).join('')
      || '<tr><td colspan="5" class="muted">No payslips yet.</td></tr>';
  };
})();
