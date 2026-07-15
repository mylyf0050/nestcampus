// Hide the loading overlay once the page is ready (masks font/map/cold-start flash)
window.addEventListener('load', function () {
  var loader = document.getElementById('page-loader');
  if (loader) {
    setTimeout(function () { loader.classList.add('hidden'); }, 250);
  }
});
// Fallback: never let the loader stay up more than 3s even if something hangs
setTimeout(function () {
  var loader = document.getElementById('page-loader');
  if (loader) loader.classList.add('hidden');
}, 3000);

// Prevent accidental double-submits (which can look like "duplicate" behavior)
document.addEventListener('submit', function (e) {
  var form = e.target;
  if (form.dataset.submitted === 'true') {
    e.preventDefault();
    return;
  }
  form.dataset.submitted = 'true';
  var btn = form.querySelector('button[type=submit]');
  if (btn) {
    setTimeout(function () { btn.disabled = true; }, 0);
  }
});
