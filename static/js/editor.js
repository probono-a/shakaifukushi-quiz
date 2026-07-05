/* ── 問題入力フォームの状態 ── */
const OPTION_COUNT = 5;

const draft = {
  options: Array(OPTION_COUNT).fill(''),
  correct_options: [],
  keywords: [],
};

document.addEventListener('DOMContentLoaded', async () => {
  await loadSubjects();
  renderOptions();
  renderKeywords();
  attachListeners();
});

async function loadSubjects() {
  const sel = document.getElementById('f-subject');
  try {
    const subjects = await API.get('/api/subjects');
    subjects.forEach(s => sel.add(new Option(s, s)));
  } catch (e) {
    console.error(e);
    showToast('科目一覧の読み込みに失敗しました。ページを再読み込みしてください', 'error');
  }
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

function buildExplanationPrompt(questionText, caseText, options) {
  const lines = [
    '社会福祉士国家試験の次の問題について、各選択肢がなぜ正しい／誤りなのかを解説してください。',
    '',
    '- 出力は Markdown 形式で、そのままコピーできるようにコードブロックに入れてください。',
    '- 冒頭に正解を「**正解: n**」のように太字で示してください。',
    '- 「### 選択肢 1」のように選択肢ごとに見出しを付けて解説してください。',
    '',
  ];
  if (caseText) lines.push('【事例文】', caseText, '');
  lines.push('【問題文】', questionText, '', '【選択肢】');
  options.forEach((opt, i) => lines.push(`${i + 1}. ${opt}`));
  if (draft.correct_options.length) {
    lines.push('', `【正解】${draft.correct_options.join('、')}`);
  }
  return lines.join('\n');
}

async function copyExplanationPrompt() {
  const questionText = document.getElementById('f-question-text').value.trim();
  const options = draft.options.map(o => o.trim()).filter(o => o);

  if (!questionText) { showToast('先に問題文を入力してください', 'error'); return; }
  if (options.length < 2) { showToast('先に選択肢を 2 つ以上入力してください', 'error'); return; }

  const caseText = document.getElementById('f-case').value.trim();
  const prompt = buildExplanationPrompt(questionText, caseText, options);

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
  if (!explanation) { showToast('解説を入力してください', 'error'); return; }

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
    reference_links: [],
  };

  try {
    const res = await API.post('/api/questions', body);
    showToast(`保存しました（ID: ${res.id}）`, 'success');
    resetForm();
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
