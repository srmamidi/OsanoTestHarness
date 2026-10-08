/* DEMO STUB — a tiny stand-in for a consent manager so the harness can be shown end to end
   without touching a real site. It is NOT Osano's code; it only mimics the public surface the
   harness reads (window.Osano.cm, the pre-load queue, the banner buttons). */
(function () {
  var CFG = window.__DEMO_CMP || {mode: 'permissive', consentModel: 'opt-in', honorGpc: false};
  var CATS = ['ANALYTICS', 'MARKETING', 'PERSONALIZATION'];
  var COOKIE = 'osano_consentmanager';
  var handlers = {};
  var queued = (window.Osano && window.Osano.data) || [];

  function on(name, fn) { (handlers[name] = handlers[name] || []).push(fn); }
  function emit(name, detail) { (handlers[name] || []).forEach(function (fn) { try { fn(detail); } catch (e) {} }); }
  queued.forEach(function (args) { if (typeof args[1] === 'function') on(args[0], args[1]); });

  function readStored() {
    var m = document.cookie.match(/(?:^|; )osano_consentmanager=([^;]*)/);
    if (!m) return null;
    try { return JSON.parse(atob(decodeURIComponent(m[1]))); } catch (e) { return null; }
  }
  function defaults() {
    var c = {ESSENTIAL: 'ACCEPT'};
    var allow = CFG.consentModel === 'opt-out';
    CATS.forEach(function (k) { c[k] = allow ? 'ACCEPT' : 'DENY'; });
    if (CFG.honorGpc && navigator.globalPrivacyControl) { c.MARKETING = 'DENY'; c['OPT-OUT'] = 'DENY'; }
    return c;
  }
  var stored = readStored();
  var consent = stored || defaults();

  function gtagPush() { window.dataLayer = window.dataLayer || []; window.dataLayer.push(arguments); }
  function googleUpdate() {
    var a = consent.ANALYTICS === 'ACCEPT' ? 'granted' : 'denied';
    var m = consent.MARKETING === 'ACCEPT' ? 'granted' : 'denied';
    gtagPush('consent', 'update', {analytics_storage: a, ad_storage: m, ad_user_data: m, ad_personalization: m});
  }
  function allowed(cat) { return cat === 'ESSENTIAL' || consent[cat] === 'ACCEPT'; }
  function activate() {
    document.querySelectorAll('script[type="text/plain"][data-oth-category]').forEach(function (s) {
      if (s.dataset.othDone) return;
      if (allowed(s.dataset.othCategory)) {
        s.dataset.othDone = '1';
        var n = document.createElement('script'); n.src = s.getAttribute('data-src'); n.async = true;
        document.head.appendChild(n);
      } else if (!s.dataset.othReported) {
        s.dataset.othReported = '1'; emit('onScriptBlocked', s.getAttribute('data-src'));
      }
    });
    document.querySelectorAll('iframe[data-oth-category][data-oth-src]').forEach(function (f) {
      if (f.getAttribute('src')) return;
      if (allowed(f.dataset.othCategory)) f.setAttribute('src', f.getAttribute('data-oth-src'));
      else if (!f.dataset.othReported) { f.dataset.othReported = '1'; emit('onIframeBlocked', f.getAttribute('data-oth-src')); }
    });
  }
  function save(c) {
    consent = c;
    var v = encodeURIComponent(btoa(JSON.stringify(c)));
    document.cookie = COOKIE + '=' + v + '; path=/; max-age=31536000; SameSite=Lax';
    if (!/osano_consentmanager_uuid=/.test(document.cookie))
      document.cookie = 'osano_consentmanager_uuid=' + Math.random().toString(36).slice(2) + '; path=/; max-age=31536000; SameSite=Lax';
    cm.dialogOpen = false;
    var w = document.querySelector('.osano-cm-window'); if (w) w.remove();
    googleUpdate(); activate();
    emit('onConsentSaved', c); emit('onConsentChanged', c);
  }
  function banner() {
    var w = document.createElement('div');
    w.className = 'osano-cm-window';
    w.innerHTML =
      '<div class="osano-cm-dialog" role="dialog" style="position:fixed;bottom:0;left:0;right:0;padding:16px;background:#1d2633;color:#fff;font:14px sans-serif;z-index:99">' +
      'DEMO consent banner — we use cookies for analytics and marketing. ' +
      '<button class="osano-cm-button osano-cm-accept-all">Accept all</button> ' +
      '<button class="osano-cm-button osano-cm-denyAll">Reject all</button> ' +
      '<button class="osano-cm-button osano-cm-manage">Manage preferences</button></div>' +
      '<div class="osano-cm-info-dialog" hidden style="position:fixed;top:20%;left:30%;padding:16px;background:#fff;color:#000;z-index:100">' +
      CATS.map(function (k) { return '<label style="display:block"><input type="checkbox" class="osano-cm-toggle__input" data-category="' + k + '"> ' + k + '</label>'; }).join('') +
      '<button class="osano-cm-button osano-cm-save">Save</button></div>';
    document.body.appendChild(w);
    cm.dialogOpen = true;
    w.querySelector('.osano-cm-accept-all').onclick = function () { save({ESSENTIAL: 'ACCEPT', ANALYTICS: 'ACCEPT', MARKETING: 'ACCEPT', PERSONALIZATION: 'ACCEPT', 'OPT-OUT': 'ACCEPT'}); };
    w.querySelector('.osano-cm-denyAll').onclick = function () { save({ESSENTIAL: 'ACCEPT', ANALYTICS: 'DENY', MARKETING: 'DENY', PERSONALIZATION: 'DENY', 'OPT-OUT': 'DENY'}); };
    w.querySelector('.osano-cm-manage').onclick = function () { cm.showDrawer(); };
    w.querySelector('.osano-cm-save').onclick = function () {
      var c = {ESSENTIAL: 'ACCEPT', 'OPT-OUT': 'DENY'};
      w.querySelectorAll('.osano-cm-toggle__input').forEach(function (i) { c[i.dataset.category] = i.checked ? 'ACCEPT' : 'DENY'; });
      save(c);
    };
  }
  var cm = {
    mode: CFG.mode, consentModel: CFG.consentModel, jurisdiction: 'us-tx', dialogOpen: false, cmpVersion: 'demo-stub',
    getConsent: function () { return JSON.parse(JSON.stringify(consent)); },
    addEventListener: function (n, fn) { on(n, fn); },
    showDrawer: function () { var d = document.querySelector('.osano-cm-info-dialog'); if (d) d.hidden = false; }
  };
  window.Osano = function (name, fn) { if (typeof fn === 'function') on(name, fn); };
  window.Osano.cm = cm;
  window.Osano.data = queued;
  if (stored) googleUpdate();
  function init() {
    activate();
    if (!stored) banner();
    emit('onInitialized', consent);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
