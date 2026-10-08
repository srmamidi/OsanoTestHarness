/* DEMO STUB of a Google tag: reads Consent Mode state from dataLayer and sends fake hits with
   gcs / gcd, setting cookies only when storage is granted. Every request it makes is answered
   locally by the harness; nothing reaches Google. */
(function () {
  var dl = window.dataLayer = window.dataLayer || [];
  var dflt = {}, upd = {};
  var KEYS = ['ad_storage', 'analytics_storage', 'ad_user_data', 'ad_personalization'];
  function apply(e) {
    if (!e || e[0] !== 'consent') return false;
    var o = e[2] || {};
    KEYS.forEach(function (k) { if (o[k]) { if (e[1] === 'default') dflt[k] = o[k]; else upd[k] = o[k]; } });
    return e[1] === 'update';
  }
  function eff(k) { return upd[k] || dflt[k] || null; }
  function letter(k) {
    var d = dflt[k], u = upd[k];
    if (!d && !u) return 'l';
    if (d === 'denied' && !u) return 'p';
    if (d === 'denied' && u === 'denied') return 'q';
    if (d === 'granted' && !u) return 't';
    if (d === 'denied' && u === 'granted') return 'r';
    if (!d && u === 'denied') return 'm';
    if (!d && u === 'granted') return 'n';
    if (d === 'granted' && u === 'denied') return 'u';
    return 'v';
  }
  function setCookie(n, v) { document.cookie = n + '=' + v + '; path=/; max-age=63072000; SameSite=Lax'; }
  function send(en) {
    var a = eff('analytics_storage'), ad = eff('ad_storage');
    var q = 'v=2&tid=G-DEMO123&en=' + en;
    if (a || ad) q += '&gcs=G1' + (ad === 'granted' ? 1 : 0) + (a === 'granted' ? 1 : 0);
    q += '&gcd=1' + '1' + letter('ad_storage') + '1' + letter('analytics_storage') + '1' + letter('ad_user_data') + '1' + letter('ad_personalization') + '5';
    if (a !== 'denied') { setCookie('_ga', 'GA1.1.' + Date.now()); setCookie('_ga_DEMO123', 'GS1.1.' + Date.now()); }
    new Image().src = 'https://region1.google-analytics.com/g/collect?' + q;
    if (ad !== 'denied') setCookie('_gcl_au', '1.1.' + Date.now());
    new Image().src = 'https://googleads.g.doubleclick.net/pagead/viewthroughconversion/987654/?' + q;
  }
  for (var i = 0; i < dl.length; i++) apply(dl[i]);
  var orig = dl.push;
  dl.push = function () {
    var r = orig.apply(dl, arguments);
    for (var j = 0; j < arguments.length; j++) {
      var e = arguments[j];
      if (apply(e)) send('consent_update');
      else if (e && e[0] === 'event') send(e[1]);
    }
    return r;
  };
  send('page_view');
})();
