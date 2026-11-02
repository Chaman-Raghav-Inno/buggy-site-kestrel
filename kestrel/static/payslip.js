(function () {
  'use strict';

  const F = window.Kestrel;
  const { $ } = F;

  F.pages.payslip = async function () {
    const id = Number(F.params.get('id'));
    const r = await F.api(`/api/payslips/${id}`);
    const p = r.data;
    document.title = `Payslip ${F.month(p.period)} · Kestrel Works`;
    $('#p-month').textContent = F.month(p.period);
    $('#p-who').textContent = `${p.name} · ${p.title}`;
    $('#p-meta').innerHTML = [
      ['Paid on', F.date(p.paid)], ['Annual salary', F.eur(p.salary)], ['Hourly rate', F.eur(p.hourly)],
      ['Gross pay this year', F.eur(p.ytd_gross)],
    ].map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('');
    const lines = [
      ['Salary', p.base], [`Overtime (${p.overtime_hours} h)`, p.overtime], ['Expenses repaid', p.expenses],
      ['Gross pay', p.gross, 'sub'], [`Income tax (20% of ${F.eur(p.taxable)})`, -p.tax], ['Pension (5% of salary)', -p.pension],
      ['Net pay', p.net, 'total'],
    ];
    $('#p-lines').innerHTML = lines.map(([k, v, cls]) => `<tr${cls ? ` class="${cls}"` : ''}><td>${k}</td><td class="num">${F.eur(v)}</td></tr>`).join('');
    $('#p-csv').href = `/api/payslips/${p.id}.csv`;
    $('#p-csv').setAttribute('download', `payslip-${p.period.slice(0, 7)}.csv`);
    $('#p-print').addEventListener('click', () => window.print());
    $('#loading').hidden = true;
    $('#payslip').hidden = false;
  };
})();
