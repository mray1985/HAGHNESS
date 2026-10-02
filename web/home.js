'use strict';
const menuButton = document.querySelector('.menu-button');
const navigation = document.getElementById('site-nav');
function closeMenu() {
  menuButton.setAttribute('aria-expanded', 'false');
  navigation.dataset.open = 'false';
}
menuButton.addEventListener('click', () => {
  const open = menuButton.getAttribute('aria-expanded') !== 'true';
  menuButton.setAttribute('aria-expanded', String(open));
  navigation.dataset.open = String(open);
});
navigation.addEventListener('click', event => { if (event.target.closest('a')) closeMenu(); });
document.addEventListener('keydown', event => { if (event.key === 'Escape') closeMenu(); });

const dialog = document.getElementById('preview-dialog');
const fallback = document.getElementById('previews');
// Clone the working no-JavaScript entrance into the dialog without duplicating IDs.
const options = fallback.querySelector('.preview-options').cloneNode(true);
document.getElementById('dialog-options').append(options);
const status = fallback.querySelector('.preview-status').cloneNode(true);
document.getElementById('dialog-options').append(status);
if (typeof dialog.showModal === 'function') {
  document.documentElement.classList.add('has-dialog');
  document.querySelectorAll('[data-open-previews]').forEach(link => {
    link.addEventListener('click', event => {
      event.preventDefault();
      closeMenu();
      if (!dialog.open) dialog.showModal();
    });
  });
  dialog.querySelector('.dialog-close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => {
    const rect = dialog.getBoundingClientRect();
    if (event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) dialog.close();
  });
}

const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(location.hostname);
function setLinks(selector, href) {
  document.querySelectorAll(selector).forEach(link => { link.href = href; });
}
function setNotes(selector, text) {
  document.querySelectorAll(selector).forEach(note => { note.textContent = text; });
}
function disableTax() {
  document.querySelectorAll('[data-tax-link]').forEach(link => {
    link.removeAttribute('href');
    link.setAttribute('aria-disabled', 'true');
    link.textContent = 'HATax integration coming';
  });
  setNotes('[data-tax-note]', 'The tax workspace is not connected to this hosted preview yet.');
}
// Default the bookkeeping entrance to the separate local service. Hosted pages
// only use same-origin destinations; no credentials or taxpayer facts are sent.
if (loopback) {
  const booksURL = new URL('/connected.html', location.href);
  booksURL.port = '8766';
  setLinks('[data-books-link]', booksURL.href);
}
fetch('/api/health', {credentials: 'same-origin', cache: 'no-store'})
  .then(response => { if (!response.ok) throw new Error('Preview status unavailable'); return response.json(); })
  .then(health => {
    if (health.connected) {
      setLinks('[data-books-link]', '/connected.html');
      setNotes('[data-books-note]', health.login_configured ? 'Opens protected sign-in on this server.' : 'Sign-in is not configured. You can view the locked entrance.');
      if (loopback) {
        const taxURL = new URL('/index.html', location.href);
        taxURL.port = '8765';
        setLinks('[data-tax-link]', taxURL.href);
        setNotes('[data-tax-note]', 'Start the tax server on port 8765 to use this preview.');
      } else disableTax();
    } else {
      setLinks('[data-tax-link]', '/index.html');
      setNotes('[data-tax-note]', 'Opens the local tax workspace on this server.');
      if (!loopback) {
        document.querySelectorAll('[data-books-link]').forEach(link => {link.removeAttribute('href');link.setAttribute('aria-disabled','true');link.textContent='Bookin’ integration coming';});
        setNotes('[data-books-note]', 'Protected bookkeeping is not connected to this server.');
      }
    }
  })
  .catch(() => {
    setNotes('.preview-status', 'Preview status could not be checked. Start the local servers and reload this page.');
    if (!loopback) {
      disableTax();
      document.querySelectorAll('[data-books-link]').forEach(link => {link.removeAttribute('href');link.setAttribute('aria-disabled','true');});
    }
  });
