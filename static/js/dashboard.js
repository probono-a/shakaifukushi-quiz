let subjectChart = null;
let trendChart   = null;
let lastStats    = null;

function chartColors() {
  const light = document.documentElement.getAttribute('data-theme') === 'light';
  return {
    grid:  light ? 'rgba(0,0,0,0.07)'   : 'rgba(255,255,255,0.05)',
    tick:  light ? '#64748b'             : '#64748b',
    label: light ? '#475569'             : '#94a3b8',
  };
}

document.addEventListener('DOMContentLoaded', async () => {
  await loadDashboard();
  document.getElementById('form-edit-id').addEventListener('submit', () => {
    const id = document.getElementById('input-edit-id').value.trim();
    if (id) location.href = `/quiz.html?editId=${encodeURIComponent(id)}`;
  });

  document.getElementById('btn-export').addEventListener('click', () => {
    window.location.href = '/api/history/export';
  });

  document.getElementById('btn-reset-history').addEventListener('click', async () => {
    if (!confirm('解答履歴をすべて削除します。この操作は取り消せません。\nよろしいですか？')) return;
    try {
      await fetch('/api/history', { method: 'DELETE' });
      await loadDashboard();
    } catch (e) {
      alert('リセットに失敗しました: ' + e.message);
    }
  });
});

async function loadDashboard() {
  showLoading(true);
  try {
    const [stats, rec] = await Promise.all([
      API.get('/api/stats'),
      API.get('/api/recommend'),
    ]);
    lastStats = stats;
    renderRecommend(rec);
    renderOverview(stats);
    renderExamPrediction(stats.overall);
    renderSubjectChart(stats.by_subject);
    renderTrendChart(stats.daily_trend);
    renderWeakTable(stats.weak_questions);
    renderSessionTable(stats.recent_sessions);
    renderCurriculumBadges(stats.by_curriculum);
  } catch (e) {
    console.error(e);
  }
  showLoading(false);
}

function showLoading(on) {
  document.getElementById('loading-overlay').classList.toggle('hidden', !on);
  document.getElementById('dashboard-body').classList.toggle('hidden', on);
}

/* ── Recommend ── */
function renderRecommend(rec) {
  const el = document.getElementById('rec-section');
  if (!rec.available) { el.classList.add('hidden'); return; }
  el.classList.remove('hidden');
  document.getElementById('rec-subjects').innerHTML =
    rec.subjects.map(s => `<span class="badge bd-primary">${s}</span>`).join('');
  const stats = rec.subject_stats.map(s =>
    `${s.subject} ${s.accuracy}%`).join('　');
  document.getElementById('rec-stats').textContent = stats;

  document.getElementById('btn-rec-start').onclick = () => {
    const cfg = rec.suggested_session;
    const p = new URLSearchParams({
      mode: cfg.mode,
      count: cfg.config.count,
      subjects: cfg.config.subjects.join(','),
    });
    location.href = '/quiz.html?' + p.toString();
  };
}

/* ── Overview stats ── */
function renderOverview(stats) {
  const o = stats.overall;
  setEl('stat-total',    o.total.toLocaleString());
  setEl('stat-correct',  o.correct.toLocaleString());
  setEl('stat-accuracy', o.accuracy + '%');
  document.getElementById('stat-accuracy').className =
    'stat-value ' + accuracyClass(o.accuracy);

  const cur = stats.by_curriculum;
  const newC = cur.find(c => c.curriculum === 'new');
  const oldC = cur.find(c => c.curriculum === 'old');
  setEl('stat-new-cur', newC ? newC.accuracy + '%' : '—');
  setEl('stat-old-cur', oldC ? oldC.accuracy + '%' : '—');
}

/* ── Exam prediction ── */
function renderExamPrediction(overall) {
  const avg = overall.avg_time_sec;
  const card = document.getElementById('exam-pred-card');
  if (!avg) { card.style.display = 'none'; return; }
  card.style.display = '';

  const totalSec = Math.round(avg * 129);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;

  const avgStr = avg >= 60
    ? `${Math.floor(avg / 60)}分${Math.round(avg % 60)} 秒`
    : `${avg} 秒`;
  const totalStr = h > 0 ? `${h} 時間 ${m} 分` : `${m} 分 ${s} 秒`;

  document.getElementById('pred-avg-time').textContent = avgStr;
  const totalEl = document.getElementById('pred-total-time');
  totalEl.textContent = totalStr;

  // 社会福祉士: 午前67問140分 + 午後62問85分 = 計225分
  const allowedMin = 225;
  const predictedMin = totalSec / 60;
  if (predictedMin <= allowedMin * 0.8) {
    totalEl.style.color = 'var(--success)';
    document.getElementById('pred-comment').innerHTML =
      `試験時間 (計 225 分) に対して余裕あり。<br>見直し時間も十分取れそうです。`;
  } else if (predictedMin <= allowedMin) {
    totalEl.style.color = 'var(--warning)';
    document.getElementById('pred-comment').innerHTML =
      `試験時間 (計 225 分) 内に収まる見込み。<br>本番は見直し時間を意識して。`;
  } else {
    totalEl.style.color = 'var(--danger)';
    document.getElementById('pred-comment').innerHTML =
      `このペースだと試験時間 (計 225 分) を超過。<br>１問あたりのスピードアップを意識しましょう。`;
  }
}

/* ── Subject chart ── */
function renderSubjectChart(data) {
  if (subjectChart) { subjectChart.destroy(); subjectChart = null; }
  if (!data.length) {
    document.getElementById('chart-subject').parentElement.innerHTML =
      '<div class="empty"><div class="empty-icon">📊</div><div>学習を始めるとグラフが表示されます</div></div>';
    return;
  }
  const cc  = chartColors();
  const ctx = document.getElementById('chart-subject').getContext('2d');

  const hasTime = data.some(d => d.avg_time_sec != null);
  const maxTime = hasTime ? Math.max(...data.map(d => d.avg_time_sec || 0)) * 1.2 : 60;

  const datasets = [{
    type: 'bar',
    data: data.map(d => d.accuracy),
    backgroundColor: data.map(d => accuracyColor(d.accuracy) + 'cc'),
    borderColor:     data.map(d => accuracyColor(d.accuracy)),
    borderWidth: 1,
    borderRadius: 4,
    xAxisID: 'xAcc',
    label: '正答率',
    order: 2,
    datalabels: {
      anchor: 'end',
      align: 'start',
      color: '#fff',
      font: { size: 10, weight: '600' },
      formatter: (_, ctx) => `${data[ctx.dataIndex].correct}/${data[ctx.dataIndex].total}`,
    },
  }];

  if (hasTime) {
    datasets.push({
      type: 'line',
      data: data.map(d => d.avg_time_sec ?? null),
      backgroundColor: '#f59e0b',
      borderColor: '#f59e0b',
      pointStyle: 'rectRot',
      pointRadius: 6,
      pointHoverRadius: 8,
      showLine: false,
      xAxisID: 'xTime',
      label: '平均回答時間(秒)',
      order: 1,
      datalabels: {
        display: ctx => ctx.dataset.data[ctx.dataIndex] != null,
        anchor: 'center',
        align: 'bottom',
        color: '#f59e0b',
        font: { size: 10, weight: '600' },
        formatter: v => v != null ? `${v}s` : '',
      },
    });
  }

  subjectChart = new Chart(ctx, {
    type: 'bar',
    data: { labels: data.map(d => d.subject), datasets },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: hasTime, labels: { color: cc.label, font: { size: 11 }, usePointStyle: true } },
        tooltip: {
          callbacks: {
            label: c => {
              if (c.dataset.xAxisID === 'xTime') return ` ⏱ ${c.raw}秒`;
              return ` ${c.raw}%  (${data[c.dataIndex].total}問)`;
            },
          },
        },
      },
      scales: {
        xAcc: {
          position: 'bottom', min: 0, max: 100,
          ticks: { color: cc.tick, callback: v => v + '%' },
          grid: { color: cc.grid },
        },
        xTime: {
          position: 'top', min: 0, max: maxTime,
          display: hasTime,
          ticks: { color: '#f59e0b', callback: v => v + 's' },
          grid: { display: false },
        },
        y: {
          ticks: { color: cc.label, font: { size: 11 } },
          grid: { display: false },
        },
      },
    },
  });
}

/* ── Trend chart ── */
function renderTrendChart(data) {
  const ctx = document.getElementById('chart-trend').getContext('2d');
  if (trendChart) trendChart.destroy();
  if (!data.length) {
    document.getElementById('chart-trend').parentElement.innerHTML =
      '<div class="empty"><div class="empty-icon">📈</div><div>学習を始めるとグラフが表示されます</div></div>';
    return;
  }
  const cc = chartColors();
  trendChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.map(d => d.date),
      datasets: [{
        label: '正答率',
        data: data.map(d => d.accuracy),
        borderColor: '#818cf8',
        backgroundColor: 'rgba(129,140,248,0.1)',
        fill: true,
        tension: 0.4,
        pointBackgroundColor: '#818cf8',
        pointRadius: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false },
        tooltip: { callbacks: { label: ctx => ` ${ctx.raw}%` } } },
      scales: {
        y: { min: 0, max: 100, ticks: { color: cc.tick, callback: v => v + '%' },
             grid: { color: cc.grid } },
        x: { ticks: { color: cc.label, font: { size: 11 } },
             grid: { display: false } },
      },
    },
  });
}

/* ── Weak questions table ── */
function renderWeakTable(data) {
  const tbody  = document.getElementById('weak-tbody');
  const weakBtn = document.getElementById('btn-weak-session');
  if (!data.length) {
    tbody.innerHTML = '<tr><td colspan="4"><div class="empty"><div class="empty-icon">✨</div>3 回以上解いた問題が揃うと表示されます</div></td></tr>';
    if (weakBtn) weakBtn.classList.add('hidden');
    return;
  }
  if (weakBtn) weakBtn.classList.remove('hidden');
  tbody.innerHTML = data.map(q => `
    <tr>
      <td><a href="/quiz.html?ids=${encodeURIComponent(q.question_id)}" class="badge bd-muted" style="text-decoration:none">${q.question_id}</a></td>
      <td class="text-muted" style="font-size:.75rem">${q.subject}</td>
      <td style="max-width:280px;color:var(--text)">${q.question_text || '—'}</td>
      <td>
        <div class="acc-bar">
          <div class="acc-track"><div class="acc-fill" style="width:${q.accuracy}%;background:${accuracyColor(q.accuracy)}"></div></div>
          <span class="acc-val ${accuracyClass(q.accuracy)}">${q.accuracy}%</span>
        </div>
        <div class="text-muted" style="font-size:.72rem;margin-top:.2rem">${q.correct}/${q.total}問</div>
      </td>
    </tr>`).join('');
}

/* ── Session table ── */
function renderSessionTable(data) {
  const tbody = document.getElementById('session-tbody');
  if (!data.length) {
    tbody.innerHTML = '<tr><td colspan="4"><div class="empty"><div class="empty-icon">📚</div>学習を始めるとここに履歴が表示されます</div></td></tr>';
    return;
  }
  tbody.innerHTML = data.map(s => {
    const dt = s.started_at ? new Date(s.started_at).toLocaleString('ja-JP',
      { month:'numeric', day:'numeric', hour:'2-digit', minute:'2-digit' }) : '—';
    const cls = s.accuracy >= 60 ? 'bd-success' : s.accuracy >= 40 ? 'bd-warning' : 'bd-danger';
    return `<tr>
      <td>${dt}</td>
      <td><span class="badge bd-primary">${MODE_LABEL[s.mode] || s.mode}</span></td>
      <td class="text-muted">${s.answered_count}問</td>
      <td><span class="badge ${cls}">${s.accuracy}%</span></td>
    </tr>`;
  }).join('');
}

/* ── Curriculum badges ── */
function renderCurriculumBadges(data) {
  const newC = data.find(c => c.curriculum === 'new');
  const oldC = data.find(c => c.curriculum === 'old');
  document.getElementById('stat-new-cur').textContent = newC ? newC.accuracy + '%' : '—';
  document.getElementById('stat-old-cur').textContent = oldC ? oldC.accuracy + '%' : '—';
  if (newC) document.getElementById('stat-new-cur').className = 'stat-value ' + accuracyClass(newC.accuracy);
  if (oldC) document.getElementById('stat-old-cur').className = 'stat-value ' + accuracyClass(oldC.accuracy);
}

function setEl(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

// テーマ切り替え時にグラフ再描画
document.addEventListener('themechange', () => {
  if (lastStats) {
    renderSubjectChart(lastStats.by_subject);
    renderTrendChart(lastStats.daily_trend);
  }
});
