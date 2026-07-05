/* ── ヘルパー ── */
function escapeHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function renderMarkdown(text) {
  if (!text || !text.trim()) return '';
  const esc = text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  const lines = esc.split('\n');
  const out = []; let inUl = false, inOl = false;
  const closeList = () => {
    if (inUl) { out.push('</ul>'); inUl = false; }
    if (inOl) { out.push('</ol>'); inOl = false; }
  };
  const isTableRow = l => /^\|.+\|/.test(l.trim());
  const isSepRow   = l => /^\|[\s:|–-]+\|/.test(l.trim());
  const parseCells = l => l.trim().replace(/^\||\|$/g,'').split('|').map(c => c.trim());
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (isTableRow(line) && i+1 < lines.length && isSepRow(lines[i+1])) {
      closeList();
      const headers = parseCells(line); i += 2;
      let tbl = '<table><thead><tr>' + headers.map(h=>`<th>${h}</th>`).join('') + '</tr></thead><tbody>';
      while (i < lines.length && isTableRow(lines[i])) {
        tbl += '<tr>' + parseCells(lines[i]).map(c=>`<td>${c}</td>`).join('') + '</tr>'; i++;
      }
      out.push(tbl + '</tbody></table>'); continue;
    }
    if (/^### (.+)$/.test(line))      { closeList(); out.push(line.replace(/^### (.+)$/,'<h4>$1</h4>')); }
    else if (/^## (.+)$/.test(line))  { closeList(); out.push(line.replace(/^## (.+)$/,'<h3>$1</h3>')); }
    else if (/^# (.+)$/.test(line))   { closeList(); out.push(line.replace(/^# (.+)$/,'<h2>$1</h2>')); }
    else if (/^[-*] (.+)$/.test(line)){ if (inOl){out.push('</ol>');inOl=false;} if(!inUl){out.push('<ul>');inUl=true;} out.push(line.replace(/^[-*] (.+)$/,'<li>$1</li>')); }
    else if (/^\d+\. (.+)$/.test(line)){ if (inUl){out.push('</ul>');inUl=false;} if(!inOl){out.push('<ol>');inOl=true;} out.push(line.replace(/^\d+\. (.+)$/,'<li>$1</li>')); }
    else if (line.trim() === '')       { closeList(); out.push('<br>'); }
    else                               { closeList(); out.push('<p>' + line + '</p>'); }
    i++;
  }
  closeList();
  return out.join('\n')
    .replace(/\*\*\*(.+?)\*\*\*/g,'<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
    .replace(/\*(.+?)\*/g,'<em>$1</em>')
    .replace(/`(.+?)`/g,'<code>$1</code>')
    .replace(/\[(.+?)\]\((.+?)\)/g,'<a href="$2" target="_blank" rel="noopener">$1</a>');
}

/* 参考リンクを Notion ブックマーク風カードで表示 */
function renderBookmarkLinks(links, container) {
  const valid = (links || []).filter(l => l && l.trim());
  if (!valid.length) { container.style.display = 'none'; return; }
  container.style.display = '';

  // スケルトンを即表示
  container.innerHTML = valid.map((_, i) =>
    `<div class="ref-bookmark-skeleton" id="bm-skel-${i}">
      <div class="skel-line skel-icon"></div>
      <div class="skel-line skel-text"></div>
    </div>`
  ).join('');

  valid.forEach((url, i) => {
    const skelId = `bm-skel-${i}`;
    fetch(`/api/link-preview?url=${encodeURIComponent(url)}`)
      .then(r => r.ok ? r.json() : null)
      .then(meta => {
        const skel = document.getElementById(skelId);
        if (!skel) return;
        const title = meta && meta.title ? escapeHtml(meta.title) : escapeHtml(url);
        const desc  = meta && meta.description ? `<div class="ref-bookmark-desc">${escapeHtml(meta.description)}</div>` : '';
        const favicon = meta ? escapeHtml(meta.favicon) : `https://www.google.com/s2/favicons?domain=${encodeURIComponent(url)}&sz=32`;
        const domain  = meta ? escapeHtml(meta.domain) : escapeHtml(new URL(url).hostname);
        const thumb   = (meta && meta.image)
          ? `<div class="ref-bookmark-thumb"><img src="${escapeHtml(meta.image)}" alt="" loading="lazy"></div>`
          : '';
        skel.outerHTML = `
          <a href="${escapeHtml(url)}" target="_blank" rel="noopener" class="ref-bookmark">
            <div class="ref-bookmark-body">
              <div class="ref-bookmark-title">${title}</div>
              ${desc}
              <div class="ref-bookmark-footer">
                <img class="ref-bookmark-favicon" src="${favicon}" alt="">
                <span class="ref-bookmark-domain">${domain}</span>
              </div>
            </div>
            ${thumb}
          </a>`;
      })
      .catch(() => {
        const skel = document.getElementById(skelId);
        if (skel) skel.outerHTML =
          `<a href="${escapeHtml(url)}" target="_blank" rel="noopener" class="ref-bookmark">
            <div class="ref-bookmark-body">
              <div class="ref-bookmark-title">${escapeHtml(url)}</div>
              <div class="ref-bookmark-footer">
                <span class="ref-bookmark-domain">${escapeHtml(url)}</span>
              </div>
            </div>
          </a>`;
      });
  });
}

/* クイズ画面のステート */
const state = {
  sessionId: null,
  questions: [],
  idx: 0,
  answers: [],           // [{questionId, isCorrect, selected}]
  selected: [],          // 現在の問題で選んだ選択肢番号
  answered: false,
  mode: null,
  config: {},
  questionStartTime: null,  // 問題表示時刻（ms）
};

document.addEventListener('DOMContentLoaded', async () => {
  // ミュートボタン初期化
  const muteBtn = document.getElementById('btn-mute');
  if (muteBtn) {
    muteBtn.textContent = SoundManager.isMuted() ? '🔇' : '🔊';
    muteBtn.addEventListener('click', () => {
      muteBtn.textContent = SoundManager.toggleMute() ? '🔇' : '🔊';
    });
  }

  // URL パラメータからセットアップ自動起動を確認
  const params = new URLSearchParams(location.search);
  const mode    = params.get('mode');
  const subjects = params.get('subjects');
  const count    = params.get('count');

  const editId = params.get('editId');
  const ids    = params.get('ids');

  if (editId) {
    showScreen('loading');
    try {
      const q = await API.get(`/api/questions/${encodeURIComponent(editId)}`);
      state.questions = [q];
      state.idx = 0;
      showScreen('quiz');
      renderQuestion();
      openEditModal();
    } catch {
      alert(`ID "${editId}" の問題が見つかりませんでした`);
      location.href = '/';
    }
  } else if (ids) {
    // ダッシュボードから特定問題を指定
    state.mode = 'ids';
    state.config = { ids: ids.split(',') };
    await startSession();
  } else if (mode) {
    // おすすめカード・苦手問題ボタンからの遷移
    state.mode = mode;
    state.config = {
      subjects: subjects ? subjects.split(',') : [],
      count: count ? Number(count) : 20,
    };
    await startSession();
  } else {
    await initSetup();
    showScreen('setup');
  }
});

/* ── Setup screen ── */
async function initSetup() {
  const subjects = await API.get('/api/subjects');

  // モードカードのクリック
  document.querySelectorAll('.mode-card').forEach(card => {
    card.addEventListener('click', () => {
      document.querySelectorAll('.mode-card').forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
      state.mode = card.dataset.mode;
      updateSetupOptions();
    });
  });

  // 科目チェックリストを生成
  const grid = document.getElementById('subject-grid');
  grid.innerHTML = subjects.map(s => `
    <div class="check-item">
      <input type="checkbox" id="s_${s}" value="${s}">
      <label for="s_${s}">${s}</label>
    </div>`).join('');

  // 全選択ボタン
  document.getElementById('btn-all-subjects').addEventListener('click', () => {
    grid.querySelectorAll('input').forEach(i => i.checked = true);
  });
  document.getElementById('btn-clear-subjects').addEventListener('click', () => {
    grid.querySelectorAll('input').forEach(i => i.checked = false);
  });

  // エディション選択肢
  const editions = await API.get('/api/editions').catch(() => null);
  if (editions && editions.length) {
    const sel = document.getElementById('edition-select');
    editions.forEach(e => sel.add(new Option(`第 ${e} 回`, e)));
  }

  // スタートボタン
  document.getElementById('btn-start').addEventListener('click', startSession);

  // デフォルト選択
  document.querySelector('.mode-card[data-mode="random"]').click();
}

function updateSetupOptions() {
  const mode = state.mode;
  document.getElementById('opt-subjects').classList.toggle('hidden', !['subject','random','rare'].includes(mode));
  document.getElementById('opt-count').classList.toggle('hidden', !['random','rare'].includes(mode));
  document.getElementById('opt-edition').classList.toggle('hidden', mode !== 'edition');
  document.getElementById('info-wrong').classList.toggle('hidden', mode !== 'wrong_only');
  document.getElementById('info-rare').classList.toggle('hidden', mode !== 'rare');
}

/* ── セッション開始 ── */
async function startSession() {
  let config = state.config;

  // セットアップ画面からのスタート
  if (!Object.keys(config).length) {
    const mode = state.mode;
    if (!mode) { alert('モードを選択してください'); return; }

    if (mode === 'subject' || mode === 'random' || mode === 'rare') {
      const checked = [...document.querySelectorAll('#subject-grid input:checked')].map(i => i.value);
      if (mode === 'subject' && !checked.length) { alert('科目を 1 つ以上選択してください'); return; }
      config.subjects = checked;
    }
    if (mode === 'random' || mode === 'rare') {
      config.count = Number(document.getElementById('count-input').value) || 20;
    }
    if (mode === 'edition') {
      config.edition = Number(document.getElementById('edition-select').value);
    }
    state.config = config;
  }

  // 問題を取得
  const params = new URLSearchParams({ mode: state.mode });
  if (config.ids?.length)      config.ids.forEach(id => params.append('ids', id));
  if (config.subjects?.length) config.subjects.forEach(s => params.append('subjects', s));
  if (config.count)   params.set('count', config.count);
  if (config.edition) params.set('edition', config.edition);
  if (document.getElementById('filter-case-only')?.checked)     params.set('question_type', '事例');
  if (document.getElementById('filter-multiple-only')?.checked) params.set('multiple_only', 'true');

  showScreen('loading');
  try {
    const questions = await API.get('/api/questions?' + params.toString());
    if (!questions.length) {
      alert('対象の問題が見つかりませんでした。条件を変えてお試しください。');
      showScreen('setup');
      return;
    }
    state.questions = questions;
    state.idx = 0;
    state.answers = [];

    // セッション作成
    const sess = await API.post('/api/sessions', { mode: state.mode, config });
    state.sessionId = sess.id;

    showScreen('quiz');
    renderQuestion();
  } catch (e) {
    console.error(e);
    alert('エラーが発生しました: ' + e.message);
    showScreen('setup');
  }
}

/* ── 問題レンダリング ── */
function renderQuestion() {
  window.scrollTo({ top: 0, behavior: 'smooth' });
  SoundManager.play('start');
  state.questionStartTime = Date.now();
  const q = state.questions[state.idx];
  const total = state.questions.length;
  state.selected = [];
  state.answered = false;

  // プログレス
  const pct = (state.idx / total) * 100;
  document.getElementById('progress-fill').style.width = pct + '%';
  document.getElementById('progress-text').textContent = `${state.idx + 1} / ${total}`;

  // メタ情報
  document.getElementById('q-meta').innerHTML = [
    `<span class="badge bd-muted">第 ${q.edition} 回</span>`,
    `<span class="badge bd-primary">${q.subject_display || q.subject}</span>`,
    q.curriculum === 'new' ? '<span class="badge bd-teal">新カリキュラム</span>' : '<span class="badge bd-muted">旧カリキュラム</span>',
    q.question_type === '事例' ? '<span class="badge bd-warning">事例問題</span>' : '',
    q.is_multiple ? '<span class="badge bd-primary">2 つ選択</span>' : '',
    `<span class="badge bd-muted" style="font-family:monospace">${q.id}</span>`,
  ].filter(Boolean).join('');

  // 事例文
  const caseEl = document.getElementById('case-text');
  if (q.case_text) {
    caseEl.textContent = q.case_text;
    caseEl.classList.remove('hidden');
  } else {
    caseEl.classList.add('hidden');
  }

  // 問題文
  document.getElementById('q-text').textContent = q.question_text;
  document.getElementById('q-hint').textContent =
    q.is_multiple ? '2 つ選んでください（選んだ瞬間に判定）' : '1 つ選んでください';

  // 選択肢
  const optWrap = document.getElementById('options');
  optWrap.innerHTML = q.options.map((opt, i) => `
    <div class="option" data-idx="${i + 1}" onclick="selectOption(this, ${i + 1})">
      <div class="opt-num">${i + 1}</div>
      <div class="opt-text">${opt}</div>
    </div>`).join('');

  // フィードバック非表示
  document.getElementById('feedback').classList.add('hidden');
  document.getElementById('btn-next').classList.add('hidden');
}

/* ── 選択肢クリック ── */
function selectOption(el, num) {
  if (state.answered) return;
  const q = state.questions[state.idx];

  if (q.is_multiple) {
    // 2 択モード
    if (state.selected.includes(num)) {
      state.selected = state.selected.filter(n => n !== num);
      el.classList.remove('selected');
    } else if (state.selected.length < 2) {
      state.selected.push(num);
      el.classList.add('selected');
    }
    if (state.selected.length === 2) judgeAnswer();
  } else {
    // 1 択モード
    document.querySelectorAll('.option').forEach(o => o.classList.remove('selected'));
    el.classList.add('selected');
    state.selected = [num];
    judgeAnswer();
  }
}

/* ── 判定 ── */
function judgeAnswer() {
  state.answered = true;
  const q = state.questions[state.idx];
  const correct = q.correct_options.map(Number).sort().join(',');
  const selected = [...state.selected].sort().join(',');
  const isCorrect = correct === selected;

  // 選択肢に正誤クラスを付与
  document.querySelectorAll('.option').forEach(o => {
    const idx = Number(o.dataset.idx);
    o.classList.add('disabled');
    if (q.correct_options.map(Number).includes(idx)) {
      o.classList.add(state.selected.includes(idx) ? 'correct' : 'reveal-correct');
    } else if (state.selected.includes(idx) && !isCorrect) {
      o.classList.add('wrong');
    }
  });

  // 効果音
  SoundManager.play(isCorrect ? 'correct' : 'wrong');

  // フィードバック
  const fb = document.getElementById('feedback');
  fb.className = 'feedback-box ' + (isCorrect ? 'correct-fb' : 'wrong-fb');
  fb.classList.remove('hidden');
  const title = document.getElementById('fb-title');
  title.textContent = isCorrect ? '✓ 正解！' : '✗ 不正解';
  document.getElementById('fb-answer').textContent =
    `正解: ${q.correct_options.join('・')}`;

  // キーワード (Google リンク)
  const validKws = (q.keywords || []).filter(k => k && k.trim());
  document.getElementById('fb-keywords').innerHTML = validKws
    .map(k => `<a href="https://www.google.com/search?q=${encodeURIComponent(k)}" target="_blank" rel="noopener" class="kw-link">${escapeHtml(k)}</a>`)
    .join('');

  // 解説
  const explEl = document.getElementById('fb-explanation');
  if (q.explanation) {
    explEl.innerHTML = renderMarkdown(q.explanation);
    explEl.style.display = '';
  } else {
    explEl.style.display = 'none';
  }

  // 参考リンク
  renderBookmarkLinks(q.reference_links, document.getElementById('fb-links'));

  // 編集ボタン
  document.getElementById('fb-actions').innerHTML =
    '<button class="btn btn-secondary btn-sm" id="btn-edit-q">✏️ 編集</button>';
  document.getElementById('btn-edit-q').addEventListener('click', openEditModal);

  // 履歴を記録
  const time_sec = state.questionStartTime
    ? Math.round((Date.now() - state.questionStartTime) / 100) / 10  // 0.1秒単位
    : null;
  API.post('/api/history', {
    session_id: state.sessionId,
    question_id: q.id,
    is_correct: isCorrect,
    subject: q.subject,
    curriculum: q.curriculum,
    edition: q.edition,
    time_sec,
  }).catch(console.error);

  state.answers.push({ questionId: q.id, isCorrect, selected: state.selected });

  document.getElementById('btn-next').classList.remove('hidden');
  document.getElementById('btn-next').textContent =
    state.idx + 1 < state.questions.length ? '次の問題 →' : '結果を見る';
}

/* ── 次へ ── */
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('btn-next')?.addEventListener('click', async () => {
    state.idx++;
    if (state.idx < state.questions.length) {
      renderQuestion();
    } else {
      await finishSession();
    }
  });
});

/* ── セッション終了 ── */
async function finishSession() {
  if (state.sessionId) {
    await API.patch(`/api/sessions/${state.sessionId}`).catch(console.error);
  }
  const animateScore = renderResult();
  showScreen('result');
  SoundManager.play('results');
  animateScore(700);  // ドラムロールが盛り上がる頃にカウントアップ開始
}

/* ── 結果画面 ── */
function renderResult() {
  const total   = state.answers.length;
  const correct = state.answers.filter(a => a.isCorrect).length;
  const pct     = total ? Math.round(correct * 100 / total) : 0;

  // スコアは 0 から始める
  const scoreEl = document.getElementById('res-score');
  scoreEl.textContent = '0%';
  scoreEl.className = 'result-num';
  document.getElementById('res-label').textContent = `${correct} / ${total} 問正解`;

  // 科目別集計（テーブルは非表示で準備）
  const bySubj = {};
  state.answers.forEach((a, i) => {
    const q = state.questions[i];
    const subj = q.subject_display || q.subject;
    if (!bySubj[subj]) bySubj[subj] = { total: 0, correct: 0 };
    bySubj[subj].total++;
    if (a.isCorrect) bySubj[subj].correct++;
  });
  const rows = Object.entries(bySubj).map(([s, v]) => {
    const p = Math.round(v.correct * 100 / v.total);
    return `<tr>
      <td>${s}</td>
      <td>${v.correct}/${v.total}</td>
      <td><div class="acc-bar">
        <div class="acc-track"><div class="acc-fill" style="width:${p}%;background:${accuracyColor(p)}"></div></div>
        <span class="acc-val ${accuracyClass(p)}">${p}%</span>
      </div></td>
    </tr>`;
  }).join('');
  document.getElementById('res-subject-tbody').innerHTML = rows ||
    '<tr><td colspan="3" class="text-muted">データなし</td></tr>';
  document.getElementById('res-subject-section').style.opacity = '0';

  // ボタン
  document.getElementById('btn-retry').onclick = () => {
    state.sessionId = null;
    state.questions = [];
    state.answers = [];
    initSetup().then(() => showScreen('setup'));
  };
  document.getElementById('btn-dashboard').onclick = () => location.href = '/';

  // カウントアップアニメーション（呼び出し側でタイミングを制御）
  return function animateScore(delay = 600) {
    setTimeout(() => {
      const duration = 1800;
      let startTime = null;
      function step(ts) {
        if (!startTime) startTime = ts;
        const t = Math.min((ts - startTime) / duration, 1);
        const eased = 1 - Math.pow(1 - t, 3);   // ease-out cubic
        scoreEl.textContent = `${Math.round(pct * eased)}%`;
        if (t < 1) {
          requestAnimationFrame(step);
        } else {
          scoreEl.textContent = `${pct}%`;
          scoreEl.className = 'result-num ' + accuracyClass(pct) + ' score-pop';
          setTimeout(() => {
            document.getElementById('res-subject-section').style.opacity = '1';
          }, 400);
        }
      }
      requestAnimationFrame(step);
    }, delay);
  };
}

/* ── 画面切り替え ── */
function showScreen(name) {
  ['setup','loading','quiz','result'].forEach(s => {
    document.getElementById(`screen-${s}`).classList.toggle('hidden', s !== name);
  });
}

/* ── 編集モーダル ── */
let editDraft = null;

function openEditModal() {
  const q = state.questions[state.idx];
  editDraft = JSON.parse(JSON.stringify(q));
  document.getElementById('edit-modal-body').innerHTML = buildEditModalBody(editDraft);
  attachEditModalListeners();
  document.getElementById('edit-modal').classList.remove('hidden');
}

function closeEditModal() {
  document.getElementById('edit-modal').classList.add('hidden');
  editDraft = null;
}

function buildEditModalBody(draft) {
  const esc = s => escapeHtml(String(s ?? ''));

  const optionsHtml = (draft.options || []).map((opt, i) => {
    const num = i + 1;
    const isCorrect = (draft.correct_options || []).map(Number).includes(num);
    return `<div class="edit-opt-row">
      <button type="button" class="edit-opt-toggle${isCorrect ? ' correct' : ''}" data-optnum="${num}">${num}</button>
      <textarea class="edit-opt-textarea" data-optidx="${i}" rows="2">${esc(opt)}</textarea>
    </div>`;
  }).join('');

  const kwChips = (draft.keywords || []).map((k, i) =>
    `<span class="edit-kw-chip">${esc(k)}<button type="button" class="edit-kw-del-btn" data-kwidx="${i}">×</button></span>`
  ).join('');

  const linkRows = (draft.reference_links || []).filter(l => l).map((l, i) =>
    `<div class="edit-link-row">
      <input class="edit-input" type="url" value="${esc(l)}" data-linkidx="${i}" style="flex:1">
      <button type="button" class="edit-link-del-btn" data-linkidx="${i}">×</button>
    </div>`
  ).join('');

  return `
    <div class="edit-field-label">科目</div>
    <input class="edit-input" id="ed-subject" type="text" value="${esc(draft.subject)}">

    <div class="edit-field-label">問題種別</div>
    <select class="edit-input" id="ed-qtype">
      <option value="通常"   ${draft.question_type==='通常'  ?'selected':''}>通常</option>
      <option value="事例"   ${draft.question_type==='事例'  ?'selected':''}>事例</option>
      <option value="不適切" ${draft.question_type==='不適切'?'selected':''}>不適切（全員正解）</option>
    </select>

    <div class="edit-field-label">事例文</div>
    <textarea class="edit-input" id="ed-case" rows="3">${esc(draft.case_text)}</textarea>

    <div class="edit-field-label">問題文</div>
    <textarea class="edit-input" id="ed-qtext" rows="4">${esc(draft.question_text)}</textarea>

    <div class="edit-field-label">選択肢（番号クリックで正解切替）</div>
    <div id="ed-options">${optionsHtml}</div>

    <div class="edit-field-label">解説</div>
    <div class="edit-md-tabs">
      <button type="button" class="edit-md-tab active" data-tab="edit">編集 (MD)</button>
      <button type="button" class="edit-md-tab" data-tab="preview">プレビュー</button>
    </div>
    <textarea class="edit-input" id="ed-explanation" rows="8">${esc(draft.explanation)}</textarea>
    <div class="edit-md-preview" id="ed-expl-preview" style="display:none"></div>

    <div class="edit-field-label">キーワード</div>
    <div class="edit-kw-area" id="ed-kw-area">${kwChips}</div>
    <div class="edit-kw-input-row">
      <input class="edit-input" id="ed-kw-input" type="text" placeholder="新しいキーワード" style="flex:1;padding:.35rem .65rem">
      <button type="button" class="btn btn-secondary btn-sm" id="ed-kw-add">追加</button>
    </div>

    <div class="edit-field-label">参考リンク</div>
    <div id="ed-links">${linkRows}</div>
    <button type="button" class="edit-add-btn" id="ed-link-add">＋ URL を追加</button>
  `;
}

function refreshEditKeywords() {
  const chips = (editDraft.keywords || []).map((k, i) =>
    `<span class="edit-kw-chip">${escapeHtml(k)}<button type="button" class="edit-kw-del-btn" data-kwidx="${i}">×</button></span>`
  ).join('');
  document.getElementById('ed-kw-area').innerHTML = chips;
  document.querySelectorAll('.edit-kw-del-btn').forEach(btn =>
    btn.addEventListener('click', e => {
      editDraft.keywords.splice(parseInt(e.target.dataset.kwidx), 1);
      refreshEditKeywords();
    })
  );
}

function refreshEditLinks() {
  document.getElementById('ed-links').innerHTML = (editDraft.reference_links || []).map((l, i) =>
    `<div class="edit-link-row">
      <input class="edit-input" type="url" value="${escapeHtml(l)}" data-linkidx="${i}" style="flex:1">
      <button type="button" class="edit-link-del-btn" data-linkidx="${i}">×</button>
    </div>`
  ).join('');
  document.querySelectorAll('.edit-link-del-btn').forEach(btn =>
    btn.addEventListener('click', e => {
      editDraft.reference_links.splice(parseInt(e.target.dataset.linkidx), 1);
      refreshEditLinks();
    })
  );
  document.querySelectorAll('#ed-links input').forEach(inp =>
    inp.addEventListener('input', e => {
      editDraft.reference_links[parseInt(e.target.dataset.linkidx)] = e.target.value;
    })
  );
}

function attachEditModalListeners() {
  // テキストフィールド
  document.getElementById('ed-subject').addEventListener('input', e => editDraft.subject = e.target.value);
  document.getElementById('ed-qtype').addEventListener('change', e => editDraft.question_type = e.target.value);
  document.getElementById('ed-case').addEventListener('input', e => editDraft.case_text = e.target.value);
  document.getElementById('ed-qtext').addEventListener('input', e => editDraft.question_text = e.target.value);
  document.getElementById('ed-explanation').addEventListener('input', e => {
    editDraft.explanation = e.target.value;
    const prev = document.getElementById('ed-expl-preview');
    if (prev.style.display !== 'none') prev.innerHTML = renderMarkdown(e.target.value);
  });

  // 選択肢の正解トグル
  document.querySelectorAll('.edit-opt-toggle').forEach(btn =>
    btn.addEventListener('click', e => {
      const num = parseInt(e.target.dataset.optnum);
      const corrects = (editDraft.correct_options || []).map(Number);
      if (corrects.includes(num)) {
        editDraft.correct_options = corrects.filter(n => n !== num);
        e.target.classList.remove('correct');
      } else {
        editDraft.correct_options = [...corrects, num].sort((a,b) => a-b);
        e.target.classList.add('correct');
      }
    })
  );

  // 選択肢テキスト
  document.querySelectorAll('.edit-opt-textarea').forEach(ta =>
    ta.addEventListener('input', e => {
      editDraft.options[parseInt(e.target.dataset.optidx)] = e.target.value;
    })
  );

  // Markdown タブ切替
  document.querySelectorAll('.edit-md-tab').forEach(tab =>
    tab.addEventListener('click', e => {
      document.querySelectorAll('.edit-md-tab').forEach(t => t.classList.remove('active'));
      e.target.classList.add('active');
      const editor = document.getElementById('ed-explanation');
      const preview = document.getElementById('ed-expl-preview');
      if (e.target.dataset.tab === 'edit') {
        editor.style.display = ''; preview.style.display = 'none';
      } else {
        preview.innerHTML = renderMarkdown(editor.value);
        editor.style.display = 'none'; preview.style.display = '';
      }
    })
  );

  // キーワード
  document.querySelectorAll('.edit-kw-del-btn').forEach(btn =>
    btn.addEventListener('click', e => {
      editDraft.keywords.splice(parseInt(e.target.dataset.kwidx), 1);
      refreshEditKeywords();
    })
  );
  document.getElementById('ed-kw-add').addEventListener('click', () => {
    const inp = document.getElementById('ed-kw-input');
    if (inp.value.trim()) {
      if (!editDraft.keywords) editDraft.keywords = [];
      editDraft.keywords.push(inp.value.trim());
      inp.value = '';
      refreshEditKeywords();
    }
  });

  // 参考リンク
  refreshEditLinks();
  document.getElementById('ed-link-add').addEventListener('click', () => {
    if (!editDraft.reference_links) editDraft.reference_links = [];
    editDraft.reference_links.push('');
    refreshEditLinks();
  });

  // モーダル制御
  document.getElementById('edit-modal-close').addEventListener('click', closeEditModal);
  document.getElementById('edit-cancel-btn').addEventListener('click', closeEditModal);
  document.getElementById('edit-save-btn').addEventListener('click', saveEdit);
}

async function saveEdit() {
  const q = state.questions[state.idx];
  try {
    await API.put(`/api/questions/${q.id}`, editDraft);
    // state を更新
    Object.assign(state.questions[state.idx], editDraft);
    // フィードバック表示を更新
    reRenderFeedback();
    closeEditModal();
  } catch (e) {
    alert('保存に失敗しました: ' + e.message);
  }
}

function reRenderFeedback() {
  const q = state.questions[state.idx];

  // メタ更新
  document.getElementById('q-meta').innerHTML = [
    `<span class="badge bd-muted">第 ${q.edition} 回</span>`,
    `<span class="badge bd-primary">${q.subject_display || q.subject}</span>`,
    q.curriculum === 'new' ? '<span class="badge bd-teal">新カリキュラム</span>' : '<span class="badge bd-muted">旧カリキュラム</span>',
    q.question_type === '事例' ? '<span class="badge bd-warning">事例問題</span>' : '',
    q.is_multiple ? '<span class="badge bd-primary">2 つ選択</span>' : '',
    `<span class="badge bd-muted" style="font-family:monospace">${q.id}</span>`,
  ].filter(Boolean).join('');

  // キーワード
  const validKws = (q.keywords || []).filter(k => k && k.trim());
  document.getElementById('fb-keywords').innerHTML = validKws
    .map(k => `<a href="https://www.google.com/search?q=${encodeURIComponent(k)}" target="_blank" rel="noopener" class="kw-link">${escapeHtml(k)}</a>`)
    .join('');

  // 解説
  const explEl = document.getElementById('fb-explanation');
  if (q.explanation) { explEl.innerHTML = renderMarkdown(q.explanation); explEl.style.display = ''; }
  else explEl.style.display = 'none';

  // リンク
  renderBookmarkLinks(q.reference_links, document.getElementById('fb-links'));
}

