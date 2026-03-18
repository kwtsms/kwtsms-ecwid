'use strict';

// ============================================================
// Safe DOM helpers
// ============================================================
function el(tag, attrs, children) {
  var node = document.createElement(tag);
  if (attrs) {
    Object.keys(attrs).forEach(function (k) {
      if (k === 'className') node.className = attrs[k];
      else if (k === 'style') node.setAttribute('style', attrs[k]);
      else node.setAttribute(k, attrs[k]);
    });
  }
  if (children) {
    if (!Array.isArray(children)) children = [children];
    children.forEach(function (c) {
      if (c === null || c === undefined) return;
      if (typeof c === 'string') node.appendChild(document.createTextNode(c));
      else node.appendChild(c);
    });
  }
  return node;
}

function text(str) { return document.createTextNode(String(str || '')); }

function clearEl(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

// ============================================================
// API helper
// ============================================================
var API = (function () {
  function request(method, path, data) {
    var opts = {
      method: method,
      headers: { 'Content-Type': 'application/json' }
    };
    if (data !== undefined) opts.body = JSON.stringify(data);

    return fetch(path, opts)
      .then(function (res) {
        return res.json().then(function (json) {
          if (!res.ok) throw new Error(json.message || 'Request failed');
          return json;
        });
      })
      .catch(function (err) {
        Toast.show(err.message || i18n('common.error'), 'error');
        throw err;
      });
  }

  return {
    get: function (path) { return request('GET', path); },
    post: function (path, data) { return request('POST', path, data); },
    put: function (path, data) { return request('PUT', path, data); },
    del: function (path) { return request('DELETE', path); }
  };
})();

// ============================================================
// Toast notifications
// ============================================================
var Toast = (function () {
  function show(msg, type) {
    type = type || 'success';
    var container = document.getElementById('toast-container');
    var node = el('div', { className: 'toast toast-' + type }, String(msg));
    container.appendChild(node);
    setTimeout(function () { if (node.parentNode) node.parentNode.removeChild(node); }, 3500);
  }
  return { show: show };
})();

// ============================================================
// i18n
// ============================================================
var _i18nData = {};

function i18n(key) { return _i18nData[key] || key; }

function applyI18n() {
  document.querySelectorAll('[data-i18n]').forEach(function (node) {
    var val = _i18nData[node.getAttribute('data-i18n')];
    if (val) node.textContent = val;
  });
}

// ============================================================
// App - Core
// ============================================================
var App = (function () {
  var _lang = 'en';

  function init() {
    var params = new URLSearchParams(window.location.search);
    var payload = params.get('payload');

    if (typeof EcwidApp !== 'undefined') {
      EcwidApp.init({ app_id: '', autoloadedflag: true, autoheight: true });
    }

    loadI18n(_lang).then(function () {
      if (payload) {
        API.post('/api/settings/init', { payload: payload })
          .then(function (res) {
            if (res.data && res.data.lang) switchLang(res.data.lang === 'ar' ? 'ar' : 'en');
            showApp();
            Settings.load();
            Gateway.loadSenderIDs();
            Logs.loadStats();
          })
          .catch(function () { showApp(); Settings.load(); });
      } else {
        showApp();
        Settings.load();
        Gateway.loadSenderIDs();
        Logs.loadStats();
      }
    });
  }

  function showApp() {
    document.getElementById('app-loading').style.display = 'none';
    document.getElementById('app-root').style.display = 'block';
  }

  function switchTab(name) {
    document.querySelectorAll('.tab-btn').forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-tab') === name);
    });
    document.querySelectorAll('.tab-content').forEach(function (c) {
      c.classList.toggle('active', c.id === 'tab-' + name);
    });
    if (name === 'templates') Templates.load();
    if (name === 'logs') { Logs.load(); Logs.loadStats(); }
    if (name === 'integrations') Integrations.load();
    if (name === 'gateway') Gateway.loadCoverage();
  }

  function switchLang(lang) {
    _lang = lang;
    document.documentElement.setAttribute('lang', lang);
    document.documentElement.setAttribute('dir', lang === 'ar' ? 'rtl' : 'ltr');
    document.getElementById('btn-lang-en').classList.toggle('active', lang === 'en');
    document.getElementById('btn-lang-ar').classList.toggle('active', lang === 'ar');
    loadI18n(lang);
  }

  function loadI18n(lang) {
    return fetch('/static/i18n/' + lang + '.json')
      .then(function (r) { return r.json(); })
      .then(function (d) { _i18nData = d; applyI18n(); })
      .catch(function () {});
  }

  function getCurrentLang() { return _lang; }

  return { init: init, switchTab: switchTab, switchLang: switchLang, loadI18n: loadI18n, getCurrentLang: getCurrentLang };
})();

// ============================================================
// Settings
// ============================================================
var Settings = (function () {
  function load() {
    API.get('/api/settings').then(function (res) {
      var s = {};
      (res.settings || []).forEach(function (item) { s[item.key] = item.value; });
      setField('plugin_enabled', s.plugin_enabled === '1' || s.plugin_enabled === 'true');
      setField('test_mode', s.test_mode !== '0');
      setField('default_language', s.default_language || 'en');
      setField('admin_phones', s.admin_phones || '');
      setField('debug_enabled', s.debug_enabled === '1');
      if (s.kwtsms_username) showGatewayConnected();
    }).catch(function () {});
  }

  function save() {
    API.put('/api/settings', {
      settings: [
        { key: 'plugin_enabled', value: getField('plugin_enabled') ? '1' : '0' },
        { key: 'test_mode', value: getField('test_mode') ? '1' : '0' },
        { key: 'default_language', value: getField('default_language') },
        { key: 'admin_phones', value: getField('admin_phones') }
      ]
    }).then(function () { Toast.show(i18n('common.success')); });
  }

  function saveSenderID() {
    var val = document.getElementById('kwtsms_sender_id').value;
    if (!val) return;
    API.put('/api/settings/kwtsms_sender_id', { value: val })
      .then(function () { Toast.show(i18n('common.success')); });
  }

  function showGatewayConnected() {
    var form = document.getElementById('gateway-form');
    var conn = document.getElementById('gateway-connected');
    if (form) form.style.display = 'none';
    if (conn) conn.style.display = 'flex';
  }

  function showGatewayForm() {
    var form = document.getElementById('gateway-form');
    var conn = document.getElementById('gateway-connected');
    if (form) form.style.display = 'block';
    if (conn) conn.style.display = 'none';
  }

  return { load: load, save: save, saveSenderID: saveSenderID, showGatewayForm: showGatewayForm };
})();

// ============================================================
// Gateway
// ============================================================
var Gateway = (function () {
  function login() {
    var username = document.getElementById('kwtsms_username').value.trim();
    var password = document.getElementById('kwtsms_password').value;
    if (!username || !password) { showError('Please enter both username and password.'); return; }

    var btn = document.getElementById('btn-login');
    btn.disabled = true;
    btn.textContent = i18n('common.loading');

    API.post('/api/gateway/login', { username: username, password: password })
      .then(function (res) {
        if (res.success) {
          populateSenderIDs(res.sender_ids || []);
          updateBalance(res.balance);
          // Clear credential fields so username is not left visible in plain text (OBS-001)
          document.getElementById('kwtsms_username').value = '';
          document.getElementById('kwtsms_password').value = '';
          Settings.load();
          loadCoverage();
          hideError();
          Toast.show(res.message || 'Connected');
        } else {
          showError(res.message || i18n('common.error'));
        }
      })
      .finally(function () {
        btn.disabled = false;
        btn.textContent = i18n('gateway.login');
      });
  }

  function disconnect() {
    if (!confirm(i18n('common.confirm_delete'))) return;
    API.put('/api/settings/kwtsms_username', { value: '' })
      .then(function () { return API.put('/api/settings/kwtsms_password', { value: '' }); })
      .then(function () { Settings.showGatewayForm(); Toast.show('Disconnected'); });
  }

  function loadSenderIDs() {
    API.get('/api/gateway/senderids').then(function (res) {
      if (res.success && res.data) populateSenderIDs(res.data.sender_ids || []);
    }).catch(function () {});
  }

  function populateSenderIDs(ids) {
    var sel = document.getElementById('kwtsms_sender_id');
    if (!sel) return;
    clearEl(sel);
    sel.appendChild(el('option', { value: '' }, '-- Select Sender ID --'));
    ids.forEach(function (id) {
      sel.appendChild(el('option', { value: id }, String(id)));
    });
  }

  function refreshBalance() {
    API.get('/api/gateway/balance').then(function (res) {
      if (res.balance !== undefined) updateBalance(res.balance);
    }).catch(function () {});
  }

  function updateBalance(bal) {
    var displays = ['balance-display', 'gateway-balance-display'];
    displays.forEach(function (id) {
      var node = document.getElementById(id);
      if (node) node.textContent = bal !== undefined ? bal + ' credits' : '--';
    });
  }

  function loadCoverage() {
    API.get('/api/gateway/coverage').then(function (res) {
      var container = document.getElementById('coverage-list');
      if (!container) return;
      clearEl(container);
      if (!res.success || !res.data || !res.data.coverage) {
        container.appendChild(text('Not loaded yet. Please verify gateway credentials.'));
        return;
      }
      var items = res.data.coverage;
      if (!items.length) {
        container.appendChild(text('No coverage data available for this account. Contact kwtSMS support to activate international coverage.'));
        return;
      }
      items.slice(0, 50).forEach(function (c) {
        var name = c.name || c.country || '';
        var cost = c.cost || c.price || '';
        var row = el('div', { className: 'coverage-item' }, [
          el('span', null, String(name)),
          cost ? el('span', null, String(cost)) : null
        ]);
        container.appendChild(row);
      });
    }).catch(function () {});
  }

  function testSMS() {
    var phone = document.getElementById('test_sms_phone').value.trim();
    var message = document.getElementById('test_sms_message').value.trim();
    var senderEl = document.getElementById('kwtsms_sender_id');
    var sender_id = senderEl ? senderEl.value : '';
    if (!phone || !message || !sender_id) { Toast.show('Please fill in phone, message, and select a Sender ID.', 'error'); return; }

    var resultEl = document.getElementById('test-sms-result');
    clearEl(resultEl);
    resultEl.appendChild(text('Sending...'));

    API.post('/api/gateway/test-sms', { phone: phone, message: message, sender_id: sender_id })
      .then(function (res) {
        clearEl(resultEl);
        var msg = res.success ? 'Sent successfully (test mode)' : 'Failed: ' + res.message;
        var span = el('span', { style: 'color:' + (res.success ? 'green' : 'red') }, msg);
        resultEl.appendChild(span);
      });
  }

  function showError(msg) {
    var node = document.getElementById('gateway-error');
    if (node) { node.textContent = msg; node.style.display = 'block'; }
  }
  function hideError() {
    var node = document.getElementById('gateway-error');
    if (node) node.style.display = 'none';
  }

  return { login: login, disconnect: disconnect, loadSenderIDs: loadSenderIDs, refreshBalance: refreshBalance, loadCoverage: loadCoverage, testSMS: testSMS };
})();

// ============================================================
// Templates
// ============================================================
var Templates = (function () {
  var _currentLang = 'en';
  var _currentTemplateId = null;

  function load() {
    var eventType = document.getElementById('template-event-type').value;
    API.get('/api/templates?event_type=' + encodeURIComponent(eventType) + '&lang=' + _currentLang)
      .then(function (res) {
        var tpl = (res.templates || []).find(function (t) { return t.lang === _currentLang; });
        _currentTemplateId = tpl ? tpl.id : null;
        var ta = document.getElementById('template-body');
        ta.value = tpl ? tpl.body : '';
        updateCounter();
        document.getElementById('template-preview').style.display = 'none';
      }).catch(function () {});
  }

  function switchLang(lang) {
    _currentLang = lang;
    document.getElementById('tmpl-lang-en').classList.toggle('active', lang === 'en');
    document.getElementById('tmpl-lang-ar').classList.toggle('active', lang === 'ar');
    document.getElementById('template-body').setAttribute('dir', lang === 'ar' ? 'rtl' : 'ltr');
    load();
  }

  function save() {
    var eventType = document.getElementById('template-event-type').value;
    var body = document.getElementById('template-body').value;
    var fn = _currentTemplateId
      ? API.put('/api/templates/' + _currentTemplateId, { body: body })
      : API.post('/api/templates', { event_type: eventType, lang: _currentLang, body: body });
    fn.then(function (res) {
      if (res.success !== false) { Toast.show(i18n('common.success')); load(); }
    });
  }

  function preview() {
    var body = document.getElementById('template-body').value;
    API.post('/api/templates/preview', { body: body, lang: _currentLang }).then(function (res) {
      var previewEl = document.getElementById('template-preview');
      var previewText = document.getElementById('preview-text');
      previewText.textContent = res.preview || '';
      previewEl.style.display = 'block';
    });
  }

  function insertPlaceholder(ph) {
    var ta = document.getElementById('template-body');
    var s = ta.selectionStart, e = ta.selectionEnd, v = ta.value;
    ta.value = v.slice(0, s) + ph + v.slice(e);
    ta.selectionStart = ta.selectionEnd = s + ph.length;
    ta.focus();
    updateCounter();
  }

  function updateCounter() {
    var text = document.getElementById('template-body').value;
    var isAr = _currentLang === 'ar' || /[\u0600-\u06FF]/.test(text);
    var first = isAr ? 70 : 160;
    var concat = isAr ? 67 : 153;
    var len = text.length;
    var pages = len <= first ? (len > 0 ? 1 : 0) : Math.ceil(len / concat);
    var remaining = len <= first ? (first - len) : (concat - (len % concat)) % concat;

    var counterEl = document.getElementById('char-counter');
    counterEl.textContent = len + '/' + (pages <= 1 ? first : pages * concat) + ' ' +
      i18n('templates.chars') + ' (' + (pages || 1) + ' ' + i18n('templates.pages') + ')';
    counterEl.className = 'char-counter' + (remaining <= 10 && remaining > 0 ? ' near-limit' : '') +
      (pages > 7 ? ' over-limit' : '');
  }

  return { load: load, switchLang: switchLang, save: save, preview: preview, insertPlaceholder: insertPlaceholder, updateCounter: updateCounter };
})();

// ============================================================
// Integrations
// ============================================================
var Integrations = (function () {
  var _events = [
    { key: 'order.created', label: 'integrations.order_created' },
    { key: 'order.payment_updated', label: 'integrations.payment_updated' },
    { key: 'order.fulfillment_updated', label: 'integrations.fulfillment_updated' }
  ];
  var _configs = {};

  function load() {
    API.get('/api/settings').then(function (res) {
      var s = {};
      (res.settings || []).forEach(function (item) { s[item.key] = item.value; });
      _events.forEach(function (ev) {
        try { _configs[ev.key] = s['integration_' + ev.key] ? JSON.parse(s['integration_' + ev.key]) : {}; }
        catch (e) { _configs[ev.key] = {}; }
      });
      render();
    });
  }

  function makeRecipientSelect(evKey, current) {
    var opts = [
      { value: 'customer', label: 'integrations.recipient_customer' },
      { value: 'admin', label: 'integrations.recipient_admin' },
      { value: 'both', label: 'integrations.recipient_both' }
    ];
    var sel = el('select', { className: 'field-select', id: 'int-recipient-' + evKey });
    opts.forEach(function (o) {
      var opt = el('option', { value: o.value }, i18n(o.label));
      if (o.value === current) opt.setAttribute('selected', '');
      sel.appendChild(opt);
    });
    return sel;
  }

  function render() {
    var container = document.getElementById('integrations-list');
    if (!container) return;
    clearEl(container);

    _events.forEach(function (ev) {
      var cfg = _configs[ev.key] || {};
      var enabled = cfg.enabled !== false;
      var recipient = cfg.recipient || 'both';

      var checkbox = el('input', { type: 'checkbox', id: 'int-enabled-' + ev.key });
      if (enabled) checkbox.setAttribute('checked', '');

      var toggle = el('label', { className: 'toggle-switch' }, [checkbox, el('span', { className: 'toggle-slider' })]);

      var header = el('div', { className: 'integration-card-header' }, [
        el('span', { className: 'integration-title' }, i18n(ev.label)),
        toggle
      ]);

      var recipientRow = el('div', { className: 'fieldset-row' }, [
        el('label', { className: 'field-label' }, i18n('integrations.recipient')),
        makeRecipientSelect(ev.key, recipient)
      ]);

      container.appendChild(el('div', { className: 'integration-card' }, [header, recipientRow]));
    });
  }

  function save() {
    Promise.all(_events.map(function (ev) {
      var enabledEl = document.getElementById('int-enabled-' + ev.key);
      var recipientEl = document.getElementById('int-recipient-' + ev.key);
      var config = JSON.stringify({
        enabled: enabledEl ? enabledEl.checked : true,
        recipient: recipientEl ? recipientEl.value : 'both'
      });
      return API.put('/api/settings/integration_' + ev.key, { value: config });
    })).then(function () { Toast.show(i18n('common.success')); });
  }

  return { load: load, save: save };
})();

// ============================================================
// Logs
// ============================================================
var Logs = (function () {
  var _offset = 0;
  var _limit = 25;

  function load(reset) {
    if (reset !== false) _offset = 0;
    var status = document.getElementById('filter-status').value;
    var evType = document.getElementById('filter-event').value;
    var params = '?limit=' + _limit + '&offset=' + _offset;
    if (status) params += '&status=' + encodeURIComponent(status);
    if (evType) params += '&event_type=' + encodeURIComponent(evType);

    API.get('/api/logs' + params).then(function (res) {
      var logs = res.logs || [];
      var total = res.total || 0;
      var tbody = document.getElementById('logs-tbody');

      if (_offset === 0) clearEl(tbody);
      if (!logs.length && _offset === 0) {
        document.getElementById('logs-empty').style.display = 'block';
        document.getElementById('btn-load-more').style.display = 'none';
        return;
      }
      document.getElementById('logs-empty').style.display = 'none';
      logs.forEach(function (log) { tbody.appendChild(buildRow(log)); });

      _offset += logs.length;
      document.getElementById('btn-load-more').style.display = _offset < total ? 'block' : 'none';
    });
  }

  function buildRow(log) {
    var badge = el('span', { className: 'badge badge-' + (log.status || 'pending') }, String(log.status || ''));
    var date = String(log.created_at || '').slice(0, 16);
    var msg = String(log.message || '');
    if (msg.length > 50) msg = msg.slice(0, 50) + '...';

    var tr = el('tr', { style: 'cursor:pointer' }, [
      el('td', null, date),
      el('td', null, String(log.recipient || '')),
      el('td', null, String(log.event_type || '')),
      el('td', null, [badge]),
      el('td', null, msg)
    ]);
    tr.addEventListener('click', function () { expand(log); });
    return tr;
  }

  function expand(log) {
    var info = 'Message:\n' + (log.message || '') +
      '\n\nAPI Response:\n' + (log.api_response || 'N/A') +
      '\n\nMessage ID: ' + (log.msg_id || 'N/A') +
      '\nPoints charged: ' + (log.points_charged || 0) +
      '\nBalance after: ' + (log.balance_after || 0);
    alert(info);
  }

  function loadMore() { load(false); }

  function loadStats() {
    API.get('/api/logs/stats').then(function (res) {
      var container = document.getElementById('logs-stats');
      if (!container) return;
      clearEl(container);
      [
        { label: 'Total', val: res.total },
        { label: 'Sent', val: res.sent },
        { label: 'Test', val: res.test },
        { label: 'Failed', val: res.failed },
        { label: 'Today', val: res.today }
      ].forEach(function (s) {
        container.appendChild(el('div', { className: 'stat-item' }, [
          el('span', { className: 'stat-value' }, String(s.val)),
          el('span', { className: 'stat-label' }, s.label)
        ]));
      });
    }).catch(function () {});
  }

  function clear() {
    if (!confirm(i18n('common.confirm_delete'))) return;
    API.del('/api/logs?older_than_days=0').then(function () {
      Toast.show('Logs cleared');
      load();
      loadStats();
    });
  }

  function toggleDebug() {
    var enabled = document.getElementById('debug_enabled').checked;
    API.put('/api/settings/debug_enabled', { value: enabled ? '1' : '0' })
      .then(function () { Toast.show(i18n('common.success')); });
  }

  return { load: load, loadMore: loadMore, loadStats: loadStats, clear: clear, expand: expand, toggleDebug: toggleDebug };
})();

// ============================================================
// Help
// ============================================================
var Help = (function () {
  function toggle(id) {
    var body = document.getElementById('acc-' + id);
    if (body) body.classList.toggle('open');
  }
  return { toggle: toggle };
})();

// ============================================================
// Field helpers
// ============================================================
function getField(id) {
  var node = document.getElementById(id);
  if (!node) return '';
  return node.type === 'checkbox' ? node.checked : (node.value || '');
}

function setField(id, val) {
  var node = document.getElementById(id);
  if (!node) return;
  if (node.type === 'checkbox') node.checked = !!val;
  else node.value = val || '';
}
