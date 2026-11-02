(function () {
  'use strict';

  const F = window.Kestrel;
  const { $, esc } = F;

  F.pages.timesheet = async function () {
    let ts;

    const parse = (v) => {
      const s = String(v).trim();
      if (!s) return 0;
      return Number(s.replace(':', '.'));
    };
    const shown = (h) => (h ? String(h) : '');
    const editable = () => ts.status === 'draft' || ts.status === 'rejected';

    function grid() {
      const hours = {};
      ts.projects.forEach((p, r) => {
        hours[p] = ts.days.map((_, d) => parse($(`#h-${r}-${d}`).value));
      });
      return hours;
    }

    function totals() {
      const hours = grid();
      const daily = ts.days.map((_, d) => ts.projects.reduce((s, p) => s + (hours[p][d] || 0), 0));
      ts.projects.forEach((p, r) => {
        $(`#row-${r}`).textContent = F.hours(hours[p].reduce((s, h) => s + (h || 0), 0));
      });
      daily.forEach((h, d) => { $(`#day-${d}`).textContent = F.hours(h); });
      let week = 0;
      for (let d = 0; d < 6; d++) week += daily[d];
      $('#ts-total').textContent = F.hours(week);
    }

    function draw() {
      document.title = `Week of ${F.date(ts.week)} · Kestrel Works`;
      $('#ts-title').textContent = `Week of ${F.date(ts.week)}`;
      $('#ts-prev').href = `/timesheet?week=${ts.prev}`;
      $('#ts-next').href = `/timesheet?week=${ts.next}`;
      $('#ts-this').href = `/timesheet?week=${ts.this}`;
      $('#ts-status').innerHTML = F.status(ts.status);
      $('#ts-hint').textContent = editable() ? 'Use decimals (7.5) or hours and minutes (7:30).' : 'This week is locked.';
      if (ts.status === 'submitted' && ts.comment) {
        $('#ts-comment').hidden = false;
        $('#ts-comment').textContent = `Your manager: ${ts.comment}`;
      } else {
        $('#ts-comment').hidden = true;
      }
      $('#ts-head').innerHTML = '<th>Project</th>' + ts.days.map((d) => `<th class="num">${F.day(d)}</th>`).join('') + '<th class="num">Total</th>';
      $('#ts-rows').innerHTML = ts.projects.map((p, r) => `<tr><th scope="row">${esc(p)}</th>${ts.days.map((d, i) =>
        `<td><label class="sr-only" for="h-${r}-${i}">${esc(p)}, ${F.day(d)}</label><input id="h-${r}-${i}" class="hrs" inputmode="decimal" autocomplete="off" value="${shown(ts.hours[p][i])}"${editable() ? '' : ' disabled'}></td>`).join('')}<td class="num" id="row-${r}"></td></tr>`).join('');
      $('#ts-foot').innerHTML = '<th>Day total</th>' + ts.days.map((_, d) => `<td class="num" id="day-${d}"></td>`).join('') + '<td></td>';
      $('#ts-overtime').textContent = F.hours(ts.overtime);
      $('#ts-save').disabled = !editable();
      $('#ts-submit').disabled = !editable();
      totals();
    }

    async function save(hours) {
      const r = await F.api(`/api/timesheet/${ts.week}`, { hours });
      if (!r.ok) {
        F.say($('#ts-msg'), r.data.error || 'Could not save the week.', 'error');
        return false;
      }
      ts = r.data;
      draw();
      return true;
    }

    $('#ts-form').addEventListener('input', (e) => { if (e.target.matches('.hrs')) totals(); });
    $('#ts-form').addEventListener('submit', async () => {
      const hours = grid();
      if (Object.values(hours).flat().some((h) => Number.isNaN(h))) return F.say($('#ts-msg'), 'Enter hours as numbers, like 7.5 or 7:30.', 'error');
      if (await save(hours)) F.say($('#ts-msg'), 'Saved.', 'success');
    });
    $('#ts-submit').addEventListener('click', async () => {
      const hours = grid();
      if (Object.values(hours).flat().some((h) => Number.isNaN(h))) return F.say($('#ts-msg'), 'Enter hours as numbers, like 7.5 or 7:30.', 'error');
      if (!(await save(hours))) return;
      const r = await F.api(`/api/timesheet/${ts.week}/submit`, {});
      if (!r.ok) return F.say($('#ts-msg'), r.data.error || 'Could not submit the week.', 'error');
      ts = r.data;
      draw();
      F.say($('#ts-msg'), 'Submitted to your manager.', 'success');
    });
    $('#ts-copy').addEventListener('click', async () => {
      const r = await F.api(`/api/timesheet?week=${ts.prev}`);
      if (!r.ok) return F.say($('#ts-msg'), r.data.error || 'Could not load last week.', 'error');
      if (await save(r.data.hours)) F.say($('#ts-msg'), 'Copied last week\'s hours.', 'success');
    });

    const week = F.params.get('week') || '';
    const r = await F.api('/api/timesheet' + (week ? `?week=${encodeURIComponent(week)}` : ''));
    if (!r.ok) {
      $('#loading').textContent = r.data.error || 'We couldn\'t open that week.';
      return;
    }
    ts = r.data;
    draw();
    $('#loading').hidden = true;
    $('#ts-form').hidden = false;
  };
})();
