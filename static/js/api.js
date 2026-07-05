/** レスポンスが失敗の場合、body の detail を含んだ Error を投げる */
async function throwIfNotOk(res, path) {
  if (res.ok) return;
  const detail = await res.json().then(d => d.detail).catch(() => null);
  throw new Error(detail || `API ${res.status}: ${path}`);
}

/** 共通 API クライアント */
const API = {
  async get(path) {
    const res = await fetch(path);
    await throwIfNotOk(res, path);
    return res.json();
  },
  async post(path, body) {
    const res = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    await throwIfNotOk(res, path);
    return res.json();
  },
  async put(path, body) {
    const res = await fetch(path, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    await throwIfNotOk(res, path);
    return res.json();
  },
  async patch(path, body = {}) {
    const res = await fetch(path, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    await throwIfNotOk(res, path);
    return res.json();
  },
};

/** 正答率に応じた CSS クラスを返す */
function accuracyClass(pct) {
  if (pct >= 80) return 'text-success';
  if (pct >= 60) return 'text-primary';
  if (pct >= 40) return 'text-warning';
  return 'text-danger';
}

/** 正答率に応じた棒グラフの色を返す */
function accuracyColor(pct) {
  if (pct >= 80) return '#34d399';
  if (pct >= 60) return '#818cf8';
  if (pct >= 40) return '#fbbf24';
  return '#f87171';
}

/** セッションモードの日本語ラベル */
const MODE_LABEL = {
  subject:    '科目指定',
  wrong_only: '間違えた問題',
  random:     'ランダム',
  edition:    '模擬受験',
};
