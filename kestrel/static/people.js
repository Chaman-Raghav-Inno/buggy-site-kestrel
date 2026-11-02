(function () {
  'use strict';

  const F = window.Kestrel;
  const { $, esc } = F;

  F.pages.people = async function () {
    let page = 1;

    async function load() {
      const q = new URLSearchParams({ q: $('#pp-q').value.trim(), department: $('#pp-dept').value, sort: $('#pp-sort').value, page });
      const r = await F.api('/api/people?' + q.toString());
      if (!r.ok) return F.toast(r.data.error || 'Could not load the directory.', 'error');
      const d = r.data;
      $('#pp-count').textContent = d.total ? F.plural(d.total, 'person', 'people') : 'Nobody matches. Try another name.';
      $('#pp-list').innerHTML = d.people.map((p) => `<article class="card person">
          <span class="avatar" aria-hidden="true">${esc(p.name.split(' ').map((x) => x[0]).join(''))}</span>
          <div><h2>${esc(p.name)}</h2><p class="muted">${esc(p.title)} · ${esc(p.department)}</p>
          <p class="small"><a href="mailto:${esc(p.email)}">${esc(p.email)}</a><br>${esc(p.phone)}<br><span class="muted">Joined ${esc(p.start_label)}</span></p></div>
        </article>`).join('');
      $('#pp-page').textContent = `Page ${page} of ${d.pages}`;
      $('#pp-prev').disabled = page <= 1;
    }

    let timer;
    $('#pp-q').addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(() => { page = 1; load(); }, 250); });
    ['#pp-dept', '#pp-sort'].forEach((s) => $(s).addEventListener('change', () => { page = 1; load(); }));
    $('#pp-prev').addEventListener('click', () => { page -= 1; load(); });
    $('#pp-next').addEventListener('click', () => { page += 1; load(); });
    await load();
  };
})();
