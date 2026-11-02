(function () {
  'use strict';

  const F = window.Kestrel;
  const { $, esc } = F;

  F.pages.team = async function () {
    const r = await F.api('/api/team');
    if (!r.ok) return F.toast(r.data.error || 'Could not load the calendar.', 'error');
    const t = r.data;
    const holidays = new Map(t.holidays.map((h) => [h.date, h.name]));
    const weekend = (iso) => [0, 6].includes(new Date(iso + 'T00:00:00Z').getUTCDay());
    $('#cal-head').innerHTML = '<th>Person</th>' + t.days.map((d) => {
      const [wd, day] = F.day(d).split(' ');
      return `<th class="cal-day${weekend(d) ? ' weekend' : ''}${d === t.today ? ' today' : ''}" title="${F.date(d)}"><span>${wd}</span>${day}</th>`;
    }).join('');
    $('#cal-rows').innerHTML = t.people.map((p) => `<tr><th scope="row"><span class="cal-name">${esc(p.name)}</span><span class="muted small">${esc(p.title)}</span></th>${t.days.map((d) => {
      const a = p.absences.find((x) => d >= x.start && d < x.end);
      let cls = weekend(d) ? 'weekend' : '';
      let label = '';
      if (holidays.has(d)) { cls += ' holiday'; label = holidays.get(d); }
      if (a && !weekend(d)) { cls += a.status === 'approved' ? ' away' : ' pending'; label = `${p.name}: ${a.status === 'approved' ? 'away' : 'leave requested'}`; }
      return `<td class="cal-cell ${cls.trim()}"${label ? ` title="${esc(label)}"` : ''}>${label ? `<span class="sr-only">${esc(label)}</span>` : ''}</td>`;
    }).join('')}</tr>`).join('');
  };
})();
