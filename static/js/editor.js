/* ── 問題入力フォームの状態 ── */
const OPTION_COUNT = 5;

const draft = {
  options: Array(OPTION_COUNT).fill(''),
  correct_options: [],
  keywords: [],
  reference_links: [],
};

/* 編集モード時は対象の問題 ID が入る（?id= 付きで開かれた場合） */
let editingId = null;

document.addEventListener('DOMContentLoaded', async () => {
  await loadSubjects();

  const id = new URLSearchParams(location.search).get('id');
  if (id) {
    try {
      const q = await API.get(`/api/questions/${encodeURIComponent(id)}`);
      enterEditMode(q);
    } catch {
      alert(`ID "${id}" の問題が見つかりませんでした`);
      location.href = '/';
      return;
    }
  }

  renderOptions();
  renderKeywords();
  renderLinks();
  attachListeners();
});

/* 取得した既存問題をフォームに反映し、編集モードに切り替える */
function enterEditMode(q) {
  editingId = q.id;
  document.title = '問題編集 — 社会福祉士過去問アプリ';
  document.querySelector('.card-title').textContent = '問題編集';
  document.getElementById('btn-save').textContent = '更新する';

  // 回次・問題番号は ID を構成するため編集不可
  const editionEl = document.getElementById('f-edition');
  editionEl.value = q.edition;
  editionEl.disabled = true;
  const numEl = document.getElementById('f-question-number');
  numEl.value = q.question_number;
  numEl.disabled = true;

  // カリキュラムを先に反映してから、DB の生の subject 値を選択する
  // （subject_display を使うと保存時に変換された名前で上書きされてしまう）
  document.getElementById('f-curriculum').value = q.curriculum || 'new';
  renderSubjectOptions(q.subject);

  document.getElementById('f-qtype').value = q.question_type || '通常';
  document.getElementById('f-case').value = q.case_text || '';
  document.getElementById('f-question-text').value = q.question_text || '';
  document.getElementById('f-explanation').value = q.explanation || '';

  draft.options = [...(q.options || [])];
  while (draft.options.length < OPTION_COUNT) draft.options.push('');
  draft.correct_options = (q.correct_options || []).map(Number);
  draft.keywords = (q.keywords || []).filter(k => k && k.trim());
  draft.reference_links = (q.reference_links || []).filter(l => l && l.trim());
}

/* カリキュラム別の科目リスト（起動時に両方取得しておく） */
const subjectLists = { new: [], old: [] };

async function loadSubjects() {
  try {
    [subjectLists.new, subjectLists.old] = await Promise.all([
      API.get('/api/subjects'),
      API.get('/api/subjects/old'),
    ]);
    renderSubjectOptions();
    document.getElementById('f-curriculum').addEventListener('change', () => renderSubjectOptions());
  } catch (e) {
    console.error(e);
    showToast('科目一覧の読み込みに失敗しました。ページを再読み込みしてください', 'error');
  }
}

/* カリキュラムの値に応じて科目プルダウンの選択肢を出し分ける。
   selected を渡すとその値を選択状態にする（リストに無い場合も選択肢として追加し、
   既存レコードの subject がそのまま書き戻されるようにする） */
function renderSubjectOptions(selected) {
  const sel = document.getElementById('f-subject');
  const curriculum = document.getElementById('f-curriculum').value;
  const list = [...subjectLists[curriculum] || []];
  if (selected && !list.includes(selected)) list.unshift(selected);
  sel.innerHTML = '';
  list.forEach(s => sel.add(new Option(s, s)));
  if (selected) sel.value = selected;
}

function renderOptions() {
  const esc = s => escapeHtml(String(s ?? ''));
  document.getElementById('f-options').innerHTML = draft.options.map((opt, i) => {
    const num = i + 1;
    const isCorrect = draft.correct_options.includes(num);
    return `<div class="edit-opt-row">
      <button type="button" class="edit-opt-toggle${isCorrect ? ' correct' : ''}" data-optnum="${num}">${num}</button>
      <textarea class="edit-opt-textarea" data-optidx="${i}" rows="2" placeholder="選択肢 ${num}">${esc(opt)}</textarea>
    </div>`;
  }).join('');

  document.querySelectorAll('#f-options .edit-opt-toggle').forEach(btn =>
    btn.addEventListener('click', e => {
      const num = parseInt(e.currentTarget.dataset.optnum);
      if (draft.correct_options.includes(num)) {
        draft.correct_options = draft.correct_options.filter(n => n !== num);
      } else {
        draft.correct_options = [...draft.correct_options, num].sort((a, b) => a - b);
      }
      renderOptions();
    })
  );
  document.querySelectorAll('#f-options .edit-opt-textarea').forEach(ta =>
    ta.addEventListener('input', e => {
      draft.options[parseInt(e.target.dataset.optidx)] = e.target.value;
    })
  );
}

function renderKeywords() {
  document.getElementById('f-kw-area').innerHTML = draft.keywords.map((k, i) =>
    `<span class="edit-kw-chip">${escapeHtml(k)}<button type="button" class="edit-kw-del-btn" data-kwidx="${i}">×</button></span>`
  ).join('');
  document.querySelectorAll('#f-kw-area .edit-kw-del-btn').forEach(btn =>
    btn.addEventListener('click', e => {
      draft.keywords.splice(parseInt(e.currentTarget.dataset.kwidx), 1);
      renderKeywords();
    })
  );
}

function renderLinks() {
  document.getElementById('f-links').innerHTML = draft.reference_links.map((l, i) =>
    `<div class="edit-link-row">
      <input class="edit-input" type="url" value="${escapeHtml(l)}" data-linkidx="${i}" style="flex:1">
      <button type="button" class="edit-link-del-btn" data-linkidx="${i}">×</button>
    </div>`
  ).join('');
  document.querySelectorAll('#f-links .edit-link-del-btn').forEach(btn =>
    btn.addEventListener('click', e => {
      draft.reference_links.splice(parseInt(e.currentTarget.dataset.linkidx), 1);
      renderLinks();
    })
  );
  document.querySelectorAll('#f-links input').forEach(inp =>
    inp.addEventListener('input', e => {
      draft.reference_links[parseInt(e.target.dataset.linkidx)] = e.target.value;
    })
  );
}

function addKeywordFromInput() {
  const inp = document.getElementById('f-kw-input');
  const v = inp.value.trim();
  if (v) {
    draft.keywords.push(v);
    inp.value = '';
    renderKeywords();
  }
}

function attachListeners() {
  document.getElementById('f-link-add').addEventListener('click', () => {
    draft.reference_links.push('');
    renderLinks();
  });

  document.getElementById('f-kw-add').addEventListener('click', addKeywordFromInput);
  document.getElementById('f-kw-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); addKeywordFromInput(); }
  });

  document.getElementById('f-explanation').addEventListener('input', e => {
    const prev = document.getElementById('f-expl-preview');
    if (prev.style.display !== 'none') prev.innerHTML = renderMarkdown(e.target.value);
  });

  document.querySelectorAll('.edit-md-tab').forEach(tab =>
    tab.addEventListener('click', e => {
      document.querySelectorAll('.edit-md-tab').forEach(t => t.classList.remove('active'));
      e.target.classList.add('active');
      const editorEl = document.getElementById('f-explanation');
      const preview = document.getElementById('f-expl-preview');
      if (e.target.dataset.tab === 'edit') {
        editorEl.style.display = ''; preview.style.display = 'none';
      } else {
        preview.innerHTML = renderMarkdown(editorEl.value);
        editorEl.style.display = 'none'; preview.style.display = '';
      }
    })
  );

  document.getElementById('btn-save').addEventListener('click', saveQuestion);
  document.getElementById('btn-copy-prompt').addEventListener('click', copyExplanationPrompt);
}

async function copyExplanationPrompt() {
  const questionText = document.getElementById('f-question-text').value.trim();
  const options = draft.options.map(o => o.trim()).filter(o => o);

  if (!questionText) { showToast('先に問題文を入力してください', 'error'); return; }
  if (options.length < 2) { showToast('先に選択肢を 2 つ以上入力してください', 'error'); return; }

  const caseText = document.getElementById('f-case').value.trim();
  const prompt = buildExplanationPrompt(questionText, caseText, options, draft.correct_options);

  try {
    await navigator.clipboard.writeText(prompt);
    showToast('AI 解説依頼文をコピーしました', 'success');
  } catch (e) {
    showToast('コピーに失敗しました。手動でコピーしてください', 'error');
  }
}

function resetForm() {
  draft.options = Array(OPTION_COUNT).fill('');
  draft.correct_options = [];
  draft.keywords = [];
  draft.reference_links = [];
  document.getElementById('f-edition').value = '';
  document.getElementById('f-curriculum').value = 'new';
  document.getElementById('f-subject').selectedIndex = 0;
  document.getElementById('f-question-number').value = '';
  document.getElementById('f-qtype').value = '通常';
  document.getElementById('f-case').value = '';
  document.getElementById('f-question-text').value = '';
  document.getElementById('f-explanation').value = '';
  document.getElementById('f-expl-preview').innerHTML = '';
  document.getElementById('f-kw-input').value = '';
  document.querySelectorAll('.edit-md-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === 'edit'));
  document.getElementById('f-explanation').style.display = '';
  document.getElementById('f-expl-preview').style.display = 'none';
  renderOptions();
  renderKeywords();
  renderLinks();
}

async function saveQuestion() {
  const edition = Number(document.getElementById('f-edition').value);
  const questionNumber = Number(document.getElementById('f-question-number').value);
  const questionText = document.getElementById('f-question-text').value.trim();
  const explanation = document.getElementById('f-explanation').value.trim();

  // 末尾の空欄は落として保存する（途中に空欄があると正答肢の番号がずれるためエラー）
  const options = draft.options.map(o => o.trim());
  while (options.length && !options[options.length - 1]) options.pop();

  if (!edition || !questionNumber) { showToast('回次と問題番号を入力してください', 'error'); return; }
  if (!questionText) { showToast('問題文を入力してください', 'error'); return; }
  if (options.length < 2) { showToast('選択肢を 2 つ以上入力してください', 'error'); return; }
  if (options.some(o => !o)) { showToast('選択肢は上から詰めて入力してください（途中に空欄があります）', 'error'); return; }
  if (!draft.correct_options.length) { showToast('正答肢を 1 つ以上選択してください', 'error'); return; }
  if (draft.correct_options.some(n => n > options.length)) { showToast('空欄の選択肢が正答肢に指定されています', 'error'); return; }

  const body = {
    edition,
    curriculum: document.getElementById('f-curriculum').value,
    subject: document.getElementById('f-subject').value,
    question_number: questionNumber,
    question_type: document.getElementById('f-qtype').value,
    case_text: document.getElementById('f-case').value.trim(),
    question_text: questionText,
    options,
    correct_options: draft.correct_options,
    explanation,
    keywords: draft.keywords,
    reference_links: draft.reference_links.filter(l => l.trim()),
  };

  try {
    if (editingId) {
      await API.put(`/api/questions/${encodeURIComponent(editingId)}`, body);
      showToast('更新しました', 'success');
      // クイズ画面から別タブで開かれた場合はタブを閉じて元の画面に戻す。
      // ダッシュボードから同一タブで来た場合はダッシュボードへ戻る。
      setTimeout(() => {
        if (window.opener) window.close();
        else location.href = '/';
      }, 1000);
    } else {
      const res = await API.post('/api/questions', body);
      showToast(`保存しました（ID: ${res.id}）`, 'success');
      resetForm();
    }
  } catch (e) {
    showToast('保存に失敗しました: ' + e.message, 'error');
  }
}

let toastTimer = null;
function showToast(message, type) {
  const el = document.getElementById('toast');
  el.textContent = message;
  el.className = `toast show ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 3200);
}
