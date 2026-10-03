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
function disableLink(selector, noteSelector, message) {
  document.querySelectorAll(selector).forEach(link => {
    link.removeAttribute('href');
    link.setAttribute('aria-disabled', 'true');
  });
  setNotes(noteSelector, message);
}
// Destinations remain same-origin except the explicitly described local-only
// Bookin service. Never send a hosted visitor to their own localhost.
if (loopback) {
  const booksURL = new URL('/connected.html', location.href);
  booksURL.port = '8766';
  setLinks('[data-books-link]', booksURL.href);
}
fetch('/api/health', {credentials: 'same-origin', cache: 'no-store'})
  .then(response => { if (!response.ok) throw new Error('Preview status unavailable'); return response.json(); })
  .then(health => {
    if (health.tax_workspace === true) {
      setLinks('[data-tax-link]', '/tax');
      setNotes('[data-tax-note]', health.connected
        ? 'Use your current sign-in to save permitted drafts. Complete filing is unavailable.'
        : 'Entries clear on refresh in this standalone preview. Complete filing is unavailable.');
    } else disableLink('[data-tax-link]', '[data-tax-note]', 'This server has not confirmed a tax workspace.');
    if (health.connected === true) {
      setLinks('[data-books-link]', '/connected.html');
      setNotes('[data-books-note]', health.login_configured
        ? 'Opens protected Bookin access using your current sign-in.'
        : 'Sign-in is not configured. You can view the locked entrance.');
    } else if (loopback) {
      setNotes('[data-books-note]', 'Start the separate connected service on port 8766 to use Bookin.');
    } else disableLink('[data-books-link]', '[data-books-note]', 'Protected Bookin is not connected to this server.');
  })
  .catch(() => {
    setNotes('.preview-status', 'Workspace status could not be checked. Check the service and reload this page.');
    disableLink('[data-tax-link]', '[data-tax-note]', 'Workspace availability could not be confirmed.');
    disableLink('[data-books-link]', '[data-books-note]', 'Workspace availability could not be confirmed.');
  });
