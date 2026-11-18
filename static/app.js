const $ = id => document.getElementById(id);
const csrf = document.querySelector('meta[name="csrf-token"]').content;
let job = null, page = 1, matched = 0, busy = false, timer;
function message(text) { $('message').textContent = text; $('message').hidden = false; clearTimeout(timer); timer = setTimeout(() => $('message').hidden = true, 12000); }
async function api(url, options = {}) {
  const response = await fetch(url, {...options, headers: {...options.headers, 'X-CSRF-Token': csrf}});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Something went wrong. Please try again.');
  return data;
}
$('login-form').addEventListener('submit', async event => {
  event.preventDefault(); const button = event.submitter; button.disabled = true;
  try { await api('/api/login', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({password:$('password').value})}); location.reload(); }
  catch(error) { message(error.message); button.disabled = false; }
});
$('logout').addEventListener('click', async () => { try { await api('/api/logout', {method:'POST'}); location.reload(); } catch(error) { message(error.message); } });
function selected() { $('file-label').textContent = $('file').files[0]?.name || 'Choose a file or drop it here'; }
$('file').addEventListener('change', selected);
for (const event of ['dragover', 'dragleave', 'drop']) $('drop-zone').addEventListener(event, e => {
  e.preventDefault(); $('drop-zone').classList.toggle('drag', event === 'dragover');
  if (event === 'drop' && !busy && e.dataTransfer.files.length) { const dt = new DataTransfer(); dt.items.add(e.dataTransfer.files[0]); $('file').files = dt.files; selected(); }
});
function setBusy(value) { busy = value; $('validate').disabled = value; $('file').disabled = value; $('validate').textContent = value ? 'Validating…' : 'Validate emails →'; }
$('upload-form').addEventListener('submit', async event => {
  event.preventDefault(); const file = $('file').files[0]; if (!file) return;
  if (file.size > 20 * 1024 * 1024) return message('File too large. Maximum upload size is 20 MB.');
  setBusy(true); $('results').hidden = true; $('progress-panel').hidden = false; $('progress').value = 0; $('percent').textContent = '0%'; $('stage').textContent = 'Uploading your file…';
  const form = new FormData(); form.append('file', file);
  try { const data = await api('/api/jobs', {method:'POST', body:form}); job = data.id; page = 1; $('filter').value = 'all'; await poll(); }
  catch(error) { message(error.message); $('stage').textContent = 'Could not complete validation'; setBusy(false); }
});
async function poll() {
  const data = await api(`/api/jobs/${job}`);
  $('stage').textContent = data.stage; $('progress').value = data.progress; $('percent').textContent = data.progress + '%';
  if (data.state === 'error') throw new Error(data.error);
  if (data.state === 'done') { setBusy(false); render(data); return; }
  await new Promise(resolve => setTimeout(resolve, 1000)); return poll();
}
function render(data) {
  $('results').hidden = false; $('result-title').textContent = data.total ? 'Your results are ready.' : 'No email addresses found.';
  $('result-description').textContent = `${data.name} · ${data.total.toLocaleString()} candidates processed`;
  for (const status of ['clean', 'rejected', 'review', 'duplicate']) $('count-' + status).textContent = (data.counts[status] || 0).toLocaleString();
  $('clean-download').href = `/api/jobs/${job}/download/clean`; $('excel-download').href = `/api/jobs/${job}/download/excel`; $('all-download').href = `/api/jobs/${job}/download/all`;
  $('rows').replaceChildren(); matched = data.matched;
  for (const row of data.rows) {
    const tr = document.createElement('tr');
    for (const field of ['email','status','reason','source']) {
      const td = document.createElement('td');
      if (field === 'status') { const badge = document.createElement('span'); badge.className = 'badge ' + row.status; badge.textContent = row.status === 'review' ? 'Needs review' : row.status[0].toUpperCase() + row.status.slice(1); td.append(badge); }
      else td.textContent = row[field];
      tr.append(td);
    }
    $('rows').append(tr);
  }
  if (!data.rows.length) { const tr = document.createElement('tr'); const td = document.createElement('td'); td.colSpan = 4; td.textContent = data.total ? 'No results in this category.' : 'No candidates found. Use an Email column in Excel or visible email addresses in Word.'; tr.append(td); $('rows').append(tr); }
  $('page-info').textContent = matched ? `${(page-1)*50+1}–${Math.min(page*50, matched)} of ${matched.toLocaleString()} results` : '0 results';
  $('previous').disabled = page <= 1; $('next').disabled = page * 50 >= matched;
}
async function loadPage() { try { render(await api(`/api/jobs/${job}?status=${encodeURIComponent($('filter').value)}&page=${page}`)); } catch(error) { message(error.message); } }
$('filter').addEventListener('change', () => { page = 1; loadPage(); });
$('previous').addEventListener('click', () => { page = Math.max(1, page-1); loadPage(); });
$('next').addEventListener('click', () => { if(page*50 < matched) { page++; loadPage(); } });
