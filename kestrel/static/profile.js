(function () {
  'use strict';

  const F = window.Kestrel;
  const { $, esc } = F;
  const IBAN = /^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$/;

  F.pages.profile = async function () {
    let p;

    function draw() {
      $('#pf-name').textContent = p.name;
      $('#pf-role').textContent = `${p.title} · ${p.department}`;
      $('#pf-facts').innerHTML = [['Work email', esc(p.email)], ['Joined', F.date(p.start)], ['Phone', esc(p.phone)], ['IBAN', esc(p.iban || 'Not set')]]
        .map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('');
      const e = p.emergency;
      $('#em-view').textContent = e.name ? `${e.name}, ${e.phone}` : 'No emergency contact yet.';
    }

    function editing(on) {
      $('#em-edit').hidden = !on;
      $('#em-open').hidden = on;
      if (on) {
        $('#em-name').value = p.emergency.name;
        $('#em-phone').value = p.emergency.phone;
        $('#em-name').focus();
      }
    }

    $('#pf-form').addEventListener('submit', async () => {
      const msg = $('#pf-msg');
      const iban = $('#pf-iban').value.trim().toUpperCase();
      if (!IBAN.test(iban)) return F.say(msg, 'Enter a valid IBAN, like GB82WEST12345698765432.', 'error');
      const r = await F.api('/api/profile', { phone_number: $('#pf-phone').value.trim(), iban });
      if (!r.ok) return F.say(msg, r.data.error || 'Could not save your details.', 'error');
      p = r.data;
      draw();
      $('#pf-iban').value = p.iban;
      F.say(msg, 'Saved.', 'success');
    });
    $('#em-open').addEventListener('click', () => editing(true));
    $('#em-cancel').addEventListener('click', () => editing(false));
    $('#em-form').addEventListener('submit', async () => {
      const r = await F.api('/api/profile/emergency', { name: $('#em-name').value.trim(), phone: $('#em-phone').value.trim() });
      if (!r.ok) return F.say($('#em-msg'), r.data.error || 'Could not save the contact.', 'error');
      p = r.data;
      draw();
      editing(false);
      F.say($('#em-msg'), 'Emergency contact saved.', 'success');
    });

    const r = await F.api('/api/profile');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your profile.', 'error');
    p = r.data;
    draw();
    $('#pf-phone').value = p.phone;
    $('#pf-iban').value = p.iban;
    $('#loading').hidden = true;
    $('#profile').hidden = false;
  };
})();
