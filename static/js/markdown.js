/* ── ヘルパー（quiz.js / editor.js 共通） ── */
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
    .replace(/\[(.+?)\]\((.+?)\)/g, (m, label, url) =>
      /^https?:\/\//i.test(url) ? `<a href="${url}" target="_blank" rel="noopener">${label}</a>` : m);
}
