/* ============================================================
   HATax — browser client.
   Talks only to the local server on 127.0.0.1. No external
   requests, no CDN, no analytics, no fonts from the network.
   ============================================================ */
'use strict';

const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

/* ---------------------------------------------------------- state */
const State = {
  screenName: 'taxpayer',
  connected: false,
  sound: true,
  away: '',
  year: '2025',
  status: 'single',
  years: [],
  statuses: {},
  jurisdictions: [],
  context: {},
};

/* ---------------------------------------------------------- audio */
/* Synthesized with WebAudio: no audio files, no network fetch. */
const Chime = (() => {
  let ctx = null;
  function ensure() {
    if (!ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return null;
      ctx = new AC();
    }
    if (ctx.state === 'suspended') ctx.resume();
    return ctx;
  }
  function tone(freq, start, dur, gain) {
    const ac = ensure();
    if (!ac) return;
    const osc = ac.createOscillator();
    const amp = ac.createGain();
    osc.type = 'sine';
    osc.frequency.value = freq;
    amp.gain.setValueAtTime(0, ac.currentTime + start);
    amp.gain.linearRampToValueAtTime(gain, ac.currentTime + start + 0.012);
    amp.gain.exponentialRampToValueAtTime(0.0001, ac.currentTime + start + dur);
    osc.connect(amp).connect(ac.destination);
    osc.start(ac.currentTime + start);
    osc.stop(ac.currentTime + start + dur + 0.02);
  }
  return {
    /* the two-note "you have a message" chime */
    message() { if (State.sound) { tone(880, 0, 0.13, 0.06); tone(1174, 0.10, 0.20, 0.06); } },
    /* the descending "signed off" tone */
    away()    { if (State.sound) { tone(660, 0, 0.12, 0.05); tone(440, 0.09, 0.18, 0.05); } },
    connect() { if (State.sound) { tone(523, 0, 0.10, 0.05); tone(784, 0.08, 0.14, 0.05); tone(1046, 0.16, 0.22, 0.05); } },
  };
})();

/* ---------------------------------------------------------- helpers */
function usd(n) {
  const v = Number(n);
  if (!isFinite(v)) return '—';
  return v.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
}
function pct(n) { return (Number(n) * 100).toFixed(2).replace(/\.00$/, '') + '%'; }
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function say(msg) { $('#sb-msg').textContent = msg; }

async function api(path, body) {
  const opts = { method: body ? 'POST' : 'GET' };
  if (body) {
    opts.headers = { 'Content-Type': 'application/json' };
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({ error: 'bad JSON from server' }));
  if (!res.ok) throw Object.assign(new Error(data.error || res.statusText), { payload: data });
  return data;
}

/* ---------------------------------------------------------- chat log */
function addMsg(who, body, kind, opts = {}) {
  const log = $('#chat-log');
  const el = document.createElement('div');
  el.className = `msg ${kind}${opts.flag ? ' flag' : ''}`;
  el.innerHTML =
    `<span class="who">${esc(who)}:</span><span class="body">${esc(opts.cite ? body.replace(/^Source: .+$/gm,'').trim() : body)}</span>` +
    (opts.cite ? `<span class="cite">Source: ${esc(opts.cite)}</span>` : '');
  log.appendChild(el);
  log.scrollTop = log.scrollHeight;
  return el;
}

/* ---------------------------------------------------------- buddies */
const BUDDIES = [
  { name: 'HATax Assistant',       icon: '◆', topic: 'tax rules',     online: true,  bot: true },
  { name: 'Brackets',         icon: '▦', topic: '1040 rates',    online: true,  bot: true },
  { name: 'Credits',          icon: '★', topic: 'CTC · EITC',    online: true,  bot: true },
  { name: 'Deadlines',        icon: '⏱', topic: 'filing dates',  online: true,  bot: true },
  { name: 'State Desk',       icon: '▤', topic: '50 states + DC',online: true,  bot: true },
  { name: 'Compliance',       icon: '⚖', topic: 'limits',        online: true,  bot: true },
  { name: 'Forms & Notices',  icon: '▦', topic: 'CP2000 · 1099', online: true,  bot: true },
  { name: 'Deduction Order',  icon: '⇅', topic: 'which first',   online: true,  bot: true },
];

function renderBuddies() {
  const ul = $('#buddy-list');
  ul.innerHTML = '';
  BUDDIES.forEach(b => {
    const away = !b.online || (b.name === State.screenName && State.away);
    const li = document.createElement('li');
    li.className = `buddy ${away ? 'away' : 'online'}`;
    li.innerHTML =
      `<span class="dot ${away ? 'away' : 'online'}"></span>` +
      `<span class="buddy-icon">${b.icon}</span>` +
      `<span class="buddy-name">${esc(b.name)}</span>` +
      `<span class="buddy-topic">${esc(b.topic)}</span>`;
    li.addEventListener('click', () => {
      const topic = b.name === 'State Desk'
        ? 'Which states have no income tax?'
        : b.name === 'Compliance'
          ? 'what can you calculate'
          : b.name === 'Credits'
            ? 'is the child tax credit refundable'
            : b.name === 'Deadlines'
              ? 'what is the filing deadline'
              : b.name === 'Deduction Order'
                ? 'what order should i make deductions'
                : b.name === 'Forms & Notices'
                  ? 'do i have to report all my 1099s'
                  : 'what is the standard deduction';
      $('#chat-input').value = topic;
      $('#chat-form').requestSubmit();
    });
    ul.appendChild(li);
  });
  $('#buddy-count').textContent = `${BUDDIES.filter(b => b.online).length} online`;
}

/* ---------------------------------------------------------- clock */
setInterval(() => {
  const s = Math.floor(Date.now() / 1000);
  $('#foot-uptime').textContent =
    String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0');
}, 1000);

/* ---------------------------------------------------------- chat */
const SUGGESTIONS = [
  'what is the standard deduction',
  'show me the 2026 brackets',
  'is the child tax credit refundable',
  'does agi or wages matter for the eitc',
  'what is the filing deadline',
  'which states have no income tax',
  'why can\'t you calculate my state tax',
  'what order should i make deductions',
  'what is the best cryptocurrency to buy',
];

function renderSuggestions() {
  const box = $('#chat-suggest');
  box.innerHTML = '';
  SUGGESTIONS.forEach(q => {
    const b = document.createElement('button');
    b.className = 'sugg';
    b.textContent = q;
    b.addEventListener('click', () => {
      $('#chat-input').value = q;
      $('#chat-form').requestSubmit();
    });
    box.appendChild(b);
  });
}

function buildContext() {
  return {
    tax_year: $('#c-year').value || State.year,
    filing_status: $('#c-status').value || State.status,
    agi: numOrNull($('#c-agi').value),
    net_capital_gain: numOrNull($('#c-gain').value) ?? 0,
    qualifying_children: numOrNull($('#c-kids').value) ?? 0,
    investment_income: numOrNull($('#c-inv').value) ?? 0,
    earned_income: numOrNull($('#c-earned').value),
  };
}
function numOrNull(v) {
  if (v === '' || v === null || v === undefined) return null;
  const n = Number(v);
  return isFinite(n) ? n : null;
}

async function sendChat(text) {
  const q = text.trim();
  if (!q) return;
  addMsg(State.screenName, q, 'me');
  say('HATax Assistant is typing...');
  try {
    const r = await api('/api/chat', { question: q, context: buildContext() });
    const flag = !r.verified || !!r.refused || !!r.uncovered;
    addMsg('HATax Assistant', r.answer, 'bot', {
      cite: (r.citations || []).join(' · '),
      flag,
    });
    if (r.table) renderBrackets(r.table);
    if (r.state) renderStateDetail(r.state);
    Chime.message();
    say(`answered from ${r.cards?.length || (r.computed ? 'engine' : 0)} source(s)`);
  } catch (err) {
    addMsg('HATax Assistant', 'Error: ' + err.message, 'sys', { flag: true });
    say('error');
  }
}

/* ---------------------------------------------------------- output */
function verificationBlock(v) {
  if (!v) return '';
  const blockers = (v.blockers || []).map(b => `<li>${esc(b)}</li>`).join('');
  const unverified = (v.unverified_items || []).filter(x => x !== '_year_block');
  const cls = v.may_prepare_return ? 'green' : 'red';
  return `<div class="note ${cls}">
    <h4>${v.may_prepare_return
      ? '✓ Reportable (still requires a human signer)'
      : '⛔ Not reportable'}</h4>
    <div>Year status: <strong>${esc(v.year_status || '—')}</strong> ·
         Human-verified: <strong>${v.human_checked ? 'yes' : 'no'}</strong>
         ${v.checked_by ? `by ${esc(v.checked_by)}` : ''}</div>
    ${blockers ? `<ul>${blockers}</ul>` : ''}
    ${unverified.length ? `<div>Unverified sub-rules: <code>${esc(unverified.join(', '))}</code></div>` : ''}
  </div>`;
}

function renderResult(r) {
  const L = r.lines, C = r.credits;
  const rows = [
    ['Standard deduction', L.standard_deduction],
    ['Taxable income', L.taxable_income],
  ];
  if (r.capital_gains_detail.net_capital_gain > 0) {
    rows.push(['Ordinary taxable income', L.ordinary_taxable_income]);
  }
  rows.push(['Tax before credits', L.tax_before_credits]);
  if (r.capital_gains_detail.net_capital_gain > 0) {
    const g = r.capital_gains_detail;
    rows.push(['↳ gain at 0%', null, g.zero_rate_amount]);
    rows.push(['↳ gain at 15%', null, g.fifteen_rate_amount]);
    rows.push(['↳ gain at 20%', null, g.twenty_rate_amount]);
  }

  const table = rows.map(([label, val, gval]) => `
    <tr>
      <td>${esc(label)}</td>
      <td class="num">${gval !== undefined ? usd(gval) : (val === null ? '—' : usd(val))}</td>
    </tr>`).join('');

  const credits = `
    <tr class="credit"><td>Child tax credit (${C.child_tax_credit.children} child${C.child_tax_credit.children === 1 ? '' : 'ren'})</td>
        <td class="num">−${usd(C.child_tax_credit.used_against_tax)}</td></tr>
    <tr class="credit"><td>EITC formula estimate · eligibility and official table pending</td><td class="num">−${usd(C.eitc.credit)}</td></tr>
    ${C.child_tax_credit.unused_overpayment > 0
      ? `<tr><td><small>CTC carryforward (not a refund)</small></td>
              <td class="num"><small>${usd(C.child_tax_credit.unused_overpayment)}</small></td></tr>` : ''}
  `;

  $('#calc-output').innerHTML = `
    ${verificationBlock(r.verification)}
    <div class="note">
      <h4>TY${esc(r.tax_year)} · ${esc(r.filing_status)} · marginal rate ${pct(L.marginal_rate_on_last_dollar)}</h4>
      <div>${esc(r.citation || '')}</div>
    </div>
    <table class="res">
      <thead><tr><th>Line</th><th class="num">Amount</th></tr></thead>
      <tbody>
        ${table}
        ${credits}
        <tr class="total"><td>Tax after credits</td><td class="num">${usd(r.result.tax_after_credits)}</td></tr>
      </tbody>
    </table>
    <div class="note red">
      <strong>Scope.</strong> 1040 core only. AGI was supplied by you and is not
      derived here. Excluded: Schedules 1–4, itemized deductions, AMT (Form 6251),
      NIIT, Section 199A, Form 8962, and every state and local tax.
      This is not a return and is not a filing.
    </div>`;
  say('calculated');
}

function renderBrackets(t) {
  const rows = t.brackets.map(b => `
    <tr>
      <td>${b.rate_label}</td>
      <td class="num">${b.from === 0 ? usd(0) : 'Over '+usd(b.from)}</td>
      <td class="num">${b.to === null ? 'No upper limit' : usd(b.to)}</td>
    </tr>`).join('');
  $('#bracket-output').innerHTML = `
    ${t.year_status === 'final' ? '' :
      `<div class="note red"><h4>⚠ Projected figures</h4>
        These are IRS estimates, not final law. Not usable for a return.</div>`}
    <div class="note"><h4>TY${esc(t.tax_year)} · ${esc(t.filing_status)}</h4>
      <div>Standard deduction: <strong>${usd(t.standard_deduction)}</strong></div>
      <div>Source: ${esc(t.citation || '')}</div>
      ${(t.unverified_items || []).length
        ? `<div>Unverified: <code>${esc(t.unverified_items.join(', '))}</code></div>` : ''}
    </div>
    <table class="res">
      <caption>Marginal rates on taxable income after deductions</caption>
      <thead><tr><th scope="col">Rate</th><th scope="col" class="num">Income above</th><th scope="col" class="num">Up to and including</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
  show('brackets');
}

function renderStateDetail(s) {
  if (s.state_tax === 0 && s.computable !== false) {
    $('#calc-output').insertAdjacentHTML('afterbegin',
      `<div class="note green"><h4>${esc(s.name)} — no individual income tax</h4>
        <div>${esc(s.explanation || '')}</div></div>`);
  } else if (s.state_tax === null) {
    const must = (s.must_check || []).map(f => `<li>${esc(f)}</li>`).join('');
    $('#calc-output').insertAdjacentHTML('afterbegin',
      `<div class="note red"><h4>${esc(s.name)} — no figure returned</h4>
        <div>${esc(s.explanation || '')}</div>
        ${must ? `<div>What a preparer must check:</div><ul>${must}</ul>` : ''}
        ${s.source_url ? `<div>Verify at: <a href="${esc(s.source_url)}" target="_blank" rel="noopener">${esc(s.source_url)}</a></div>` : ''}
      </div>`);
  }
  say(`${s.name} state lookup`);
}

function renderAttestation(a) {
  const years = Object.entries(a.provenance.federal).map(([y, v]) => `
    <tr>
      <td>${esc(y)}</td>
      <td>${esc(v.status || '—')}</td>
      <td>${v.human_checked ? '✓' : '✗'}</td>
      <td>${esc(v.checked_by || '—')}</td>
      <td>${esc(v.citation || '')}</td>
    </tr>`).join('');

  const checklist = a.checklist.map(c => `
    <tr><td>${esc(c.check)}<br><small style="color:#4a5160">${esc(c.how)}</small></td></tr>`).join('');

  $('#attest-output').innerHTML = `
    <div style="padding:14px 14px 0">
      <div class="note red"><h4>Limited status</h4><pre class="raw">${esc(a.disclaimer_full)}</pre></div>
      <div class="note"><h4>Coverage</h4>
        <div>Tax years: ${esc(a.coverage.tax_years.join(', '))} ·
             final: ${esc(a.coverage.final_years.join(', ') || 'none')} ·
             projected: ${esc(a.coverage.projected_years.join(', ') || 'none')}</div>
        <div>States: ${a.coverage.states.computable} computable ·
             ${a.coverage.states.partial} investment-income-only ·
             ${a.coverage.states.refused} refused pending data</div>
        <div>Federal scope: ${esc(a.coverage.federal_scope)}</div>
        <div>Files or transmits: <strong>${a.filestransmits ? 'YES' : 'no'}</strong> ·
             May prepare a return by default: <strong>${a.may_prepare_return_default ? 'yes' : 'no'}</strong></div>
      </div>
      <h3 style="font-size:13px;margin:18px 0 6px">Rule provenance &amp; verification</h3>
      <table class="res">
        <thead><tr><th>Year</th><th>Status</th><th>Checked</th><th>By</th><th>Authority</th></tr></thead>
        <tbody>${years}</tbody>
      </table>
      <h3 style="font-size:13px;margin:18px 0 6px">Pre-filing review checklist</h3>
      <table class="res"><tbody>${checklist}</tbody></table>
    </div>`;
  show('attestation');
}

/* ---------------------------------------------------------- wiring */
function show(name) {
  $$('.panel').forEach(p => p.classList.remove('minimized'));
  $$('.panel').forEach(p => { p.hidden = p.id !== name; });
  $$('.sb-tab').forEach(t => t.classList.toggle('active', t.dataset.open === name));
  $$('.sb-tab').forEach(t => {t.setAttribute('aria-selected',String(t.dataset.open===name));t.tabIndex=t.dataset.open===name?0:-1;});
}

function fillSelects() {
  const ys = $('#c-year');
  ys.innerHTML = State.years.map(y => {
    return `<option value="${y}">${y}</option>`;
  }).join('');
  ys.value = State.year;

  const ss = $('#c-status');
  ss.innerHTML = Object.entries(State.statuses)
    .map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join('');
  ss.value = State.status;

  const st = $('#c-state');
  st.innerHTML = '<option value="">— none —</option>' + State.jurisdictions.map(j => {
    const tag = j.computable ? 'no income tax' : (j.partial ? 'invest. income only' : 'refused');
    return `<option value="${j.code}">${esc(j.name)} — ${tag}</option>`;
  }).join('');
}

async function boot2() {
  try {
    const health = await api('/api/health');
    $('#tb-version').textContent = 'v' + health.version;
    $('#tb-warn').addEventListener('click', async () => {
      renderAttestation(await api('/api/attestation'));
    });

    const y = await api('/api/years');
    State.years = y.years; State.statuses = y.statuses;
    State.year = y.years.includes('2025') ? '2025' : y.years[0];

    const s = await api('/api/states');
    State.jurisdictions = s.jurisdictions;
    fillSelects();
    say(`ready · ${s.jurisdictions.length} jurisdictions loaded`);
  } catch (err) {
    say('cannot reach local server: ' + err.message);
    addMsg('HATax Assistant', 'Cannot reach the local server. Is `python ha/server.py` running?',
      'sys', { flag: true });
  }
}

async function doCalculate() {
  const ctx = buildContext();
  if (ctx.agi === null) {
    $('#calc-output').innerHTML =
      `<div class="note red"><h4>AGI required</h4>
       This engine deliberately does not derive AGI. Above-the-line adjustments
       are where returns go wrong, so AGI is an input you supply.</div>`;
    return;
  }
  say('calculating...');
  try {
    const r = await api('/api/calculate', {
      tax_year: ctx.tax_year,
      filing_status: ctx.filing_status,
      agi: ctx.agi,
      net_capital_gain: ctx.net_capital_gain,
      qualifying_children: ctx.qualifying_children,
      investment_income: ctx.investment_income,
      earned_income: ctx.earned_income,
    });
    renderResult(r);

    const code = $('#c-state').value;
    if (code) {
      const s = await api('/api/state', {
        jurisdiction: code, tax_year: ctx.tax_year,
        filing_status: ctx.filing_status, agi: ctx.agi,
      });
      renderStateDetail(s);
    }
  } catch (err) {
    $('#calc-output').innerHTML =
      `<div class="note red"><h4>Error</h4>${esc(err.message)}</div>`;
    say('error');
  }
}

async function doBrackets() {
  try {
    const t = await api(`/api/brackets?year=${$('#c-year').value}&status=${$('#c-status').value}`);
    renderBrackets(t);
  } catch (err) {
    say('error: ' + err.message);
  }
}

function connect() {
  State.connected = !State.connected;
  State.screenName = $('#signin-name').value.trim() || 'taxpayer';
  const st = $('#ms-status');
  if (State.connected) {
    st.textContent = `Local session: ${State.screenName}`;
    st.classList.add('online');
    addMsg('HATax', `Welcome, ${State.screenName}.`, 'sys');
    addMsg('HATax Assistant',
      'Ask a tax question, or enter your figures in the Calculator. Answers ' +
      'depend on available sources and the selected tax year. This session runs locally.', 'bot');
    Chime.connect();
  } else {
    st.textContent = 'Offline';
    st.classList.remove('online');
    addMsg('HATax', 'Local session ended.', 'sys');
    Chime.away();
  }
  renderBuddies();
  say(State.connected ? 'online' : 'offline');
}

document.addEventListener('DOMContentLoaded', () => {
  renderBuddies();
  renderSuggestions();
  boot2();

  $('#btn-boot').addEventListener('click', () => $('#boot').classList.add('hidden'));

  $('#btn-connect').addEventListener('click', connect);
  $('#signin-name').addEventListener('keydown', e => { if (e.key === 'Enter') connect(); });
  $('#away-msg').addEventListener('input', e => { State.away = e.target.value; renderBuddies(); });

  $('#chat-form').addEventListener('submit', e => {
    e.preventDefault();
    const input = $('#chat-input');
    const text = input.value;
    input.value = '';
    sendChat(text);
  });

  $('#btn-sound').addEventListener('click', () => {
    State.sound = !State.sound;
    $('#btn-sound').textContent = State.sound ? '🔊' : '🔇';
    say(State.sound ? 'sound on' : 'sound off');
  });
  $('#btn-clear').addEventListener('click', () => { $('#chat-log').innerHTML = ''; });

  $('#btn-calc').addEventListener('click', doCalculate);
  $('#btn-brackets').addEventListener('click', doBrackets);
  $('#btn-clearout').addEventListener('click', () => { $('#calc-output').innerHTML = ''; say('cleared'); });

  $$('.sb-tab').forEach(t => t.addEventListener('click', () => {show(t.dataset.open);if(t.dataset.open==='brackets')doBrackets();}));
  $('#statusbar').setAttribute('role','tablist');$('#statusbar').setAttribute('aria-label','Tax workspace');
  const tabs=$$('.sb-tab');tabs.forEach((tab,index)=>{tab.id='tab-'+tab.dataset.open;tab.setAttribute('role','tab');tab.setAttribute('aria-controls',tab.dataset.open);tab.setAttribute('aria-selected',String(index===0));tab.tabIndex=index===0?0:-1;
    const panel=$('#'+tab.dataset.open);panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',tab.id);panel.tabIndex=0;
    tab.addEventListener('keydown',event=>{let target;if(event.key==='ArrowRight')target=(index+1)%tabs.length;if(event.key==='ArrowLeft')target=(index+tabs.length-1)%tabs.length;if(event.key==='Home')target=0;if(event.key==='End')target=tabs.length-1;if(target!==undefined){event.preventDefault();tabs[target].focus();}});
  });
  $$('[data-close]').forEach(x => x.addEventListener('click', () => show('messenger')));

  $('#btn-close').addEventListener('click', () => show('messenger'));
  $('#btn-min').addEventListener('click', () => {$$('.panel').filter(p=>!p.hidden).forEach(p=>p.classList.add('minimized'));say('Workspace collapsed. Choose a tab to reopen.');});
  $('#btn-max').addEventListener('click', () => {document.body.classList.toggle('focus-mode');say(document.body.classList.contains('focus-mode')?'Focus view':'Standard view');});
});
