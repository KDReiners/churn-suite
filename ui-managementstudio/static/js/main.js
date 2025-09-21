(function() {
  let dataTable = null;
  let currentViewName = '';

  function showError(msg) {
    const box = document.getElementById('errorBox');
    box.textContent = msg || '';
    box.classList.toggle('d-none', !msg);
  }

  async function fetchJSON(url, options) {
    const resp = await fetch(url, options || {});
    if (!resp.ok) {
      let errText = `HTTP ${resp.status}`;
      try {
        const body = await resp.json();
        if (body && body.error) errText = body.error;
      } catch(e) {}
      throw new Error(errText);
    }
    return resp.json();
  }

  function renderTablesList(tables) {
    const list = document.getElementById('tablesList');
    list.innerHTML = '';
    tables.forEach(t => {
      const li = document.createElement('li');
      li.className = 'list-group-item d-flex justify-content-between align-items-center';
      li.innerHTML = `<span class="table-link" data-name="${t.table}">${t.table}</span><span class="badge bg-secondary rounded-pill">${t.records}</span>`;
      li.querySelector('.table-link').addEventListener('click', () => loadSchema(t.table));
      list.appendChild(li);
    });
  }

  function renderViewsList(views) {
    const list = document.getElementById('viewsList');
    if (!list) return;
    list.innerHTML = '';
    (views || []).forEach(v => {
      const name = v.name || '';
      const query = v.query || '';
      const li = document.createElement('li');
      li.className = 'list-group-item d-flex justify-content-between align-items-center';
      li.innerHTML = `
        <span class="view-link" data-name="${name}">${name}</span>
        <div>
          <button class="btn btn-sm btn-outline-danger btn-delete-view" title="View löschen" data-name="${name}">−</button>
        </div>`;
      const link = li.querySelector('.view-link');
      link.addEventListener('click', () => {
        const editor = document.getElementById('sqlEditor');
        editor.value = query || `SELECT * FROM ${name} LIMIT 50;`;
        editor.focus();
        currentViewName = name;
      });
      const delBtn = li.querySelector('.btn-delete-view');
      delBtn.addEventListener('click', async () => {
        if (!confirm(`View '${name}' löschen?`)) return;
        const pw = prompt('Admin-Passwort für Löschung:');
        if (!pw) return;
        try {
          await fetchJSON(`/sql/views/${encodeURIComponent(name)}`, {
            method: 'DELETE',
            headers: { 'X-Admin-Password': pw }
          });
          await loadViews();
          if (currentViewName === name) currentViewName = '';
        } catch (e) {
          showError(String(e.message || e));
        }
      });
      list.appendChild(li);
    });
  }

  function renderSchemaBox(data) {
    const box = document.getElementById('schemaBox');
    const fields = data.schema || [];
    const rows = fields.map(f => `<tr>
      <td class="fw-semibold">${f.name}</td>
      <td><code>${f.display_type}</code></td>
      <td>${f.description || ''}</td>
    </tr>`).join('');
    box.innerHTML = `
      <div class="mb-2 small text-muted">Quelle: <code>${data.source || ''}</code></div>
      <div class="mb-2 small">${data.description || ''}</div>
      <div class="table-responsive">
        <table class="table table-sm table-striped">
          <thead><tr><th>Feld</th><th>Typ</th><th>Beschreibung</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
  }

  async function loadTables() {
    try {
      const data = await fetchJSON('/sql/tables');
      renderTablesList(data.tables || []);
    } catch(e) {
      showError(String(e.message || e));
    }
  }

  async function loadViews() {
    try {
      const data = await fetchJSON('/sql/views');
      renderViewsList(data.views || []);
    } catch(e) {
      showError(String(e.message || e));
    }
  }

  async function loadSchema(tableName) {
    try {
      const data = await fetchJSON(`/sql/schema/${encodeURIComponent(tableName)}`);
      renderSchemaBox(data);
      // Prepare example query
      const editor = document.getElementById('sqlEditor');
      editor.value = `SELECT * FROM ${tableName} LIMIT 50;`;
      editor.focus();
      // Auto-Ausführung, damit Ergebnisse im Grid erscheinen
      try { await runQuery(); } catch(e) { showError(String(e.message || e)); }
    } catch(e) {
      showError(String(e.message || e));
    }
  }

  function renderResult(columns, rows) {
    const container = document.getElementById('resultContainer');

    // Vorherige DataTable-Instanz sicher zerstören
    if (dataTable) {
      try { dataTable.destroy(true); } catch(e) {}
      dataTable = null;
    }

    // Table-Element vollständig ersetzen, um Residuen zu vermeiden
    container.innerHTML = '<table id="resultTable" class="table table-striped table-sm" style="width:100%"><thead></thead><tbody></tbody></table>';
    const table = document.getElementById('resultTable');
    const thead = table.querySelector('thead');
    const tbody = table.querySelector('tbody');

    // Falls keine Spalten, nichts rendern (leeres Grid)
    if (!columns || columns.length === 0) {
      thead.innerHTML = '';
      tbody.innerHTML = '';
      return;
    }

    // Header aufbauen
    const th = `<tr>${columns.map(c => `<th>${c}</th>`).join('')}</tr>`;
    thead.innerHTML = th;

    // Datenmatrix bauen (Arrays je Zeile passend zur Spaltenliste)
    const dataMatrix = (rows || []).map(r => columns.map(c => (r && Object.prototype.hasOwnProperty.call(r, c)) ? r[c] : null));

    // DataTables neu initialisieren (robust gegen Strukturwechsel)
    try {
      dataTable = $('#resultTable').DataTable({
        data: dataMatrix,
        columns: columns.map(c => ({ title: c })),
        pageLength: 25,
        lengthMenu: [[25, 50, 100, 250], [25, 50, 100, 250]],
        deferRender: true,
        autoWidth: false,
        destroy: true
      });
    } catch (e) {
      showError(`DataTables Fehler: ${e.message || e}`);
    }
  }

  async function runQuery() {
    showError('');
    const sql = document.getElementById('sqlEditor').value;
    const limit = Number(document.getElementById('rowLimit').value || '1000') || 1000;
    const resp = await fetchJSON('/sql/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: sql, limit: limit })
    });
    const meta = document.getElementById('resultMeta');
    meta.textContent = `${resp.row_count || 0} Zeilen`;
    renderResult(resp.columns || [], resp.rows || []);
    // Stelle sicher, dass das Ergebnis-Grid in den Viewport kommt (insb. Safari)
    try {
      const grid = document.getElementById('resultTable');
      if (grid && typeof grid.scrollIntoView === 'function') {
        grid.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    } catch (e) { /* ignore */ }
  }

  async function saveViewFromEditor() {
    showError('');
    const name = prompt('View-Name (A-Z, a-z, 0-9, _):', currentViewName || '');
    if (!name) return;
    const query = document.getElementById('sqlEditor').value || '';
    const pw = prompt('Admin-Passwort:');
    if (!pw) return;
    try {
      await fetchJSON('/sql/views', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Admin-Password': pw
        },
        body: JSON.stringify({ name: name, query: query })
      });
      await loadViews();
      currentViewName = name;
      alert('View gespeichert.');
    } catch(e) {
      showError(String(e.message || e));
    }
  }

  function bindKeys() {
    const editor = document.getElementById('sqlEditor');
    editor.addEventListener('keydown', function(e) {
      const isEnter = (e.key === 'Enter');
      const isCmd = (e.metaKey || e.ctrlKey);
      // Tab-Einrückung im Textarea unterstützen (wie IDE)
      if (e.key === 'Tab') {
        e.preventDefault();
        const el = editor;
        const start = el.selectionStart;
        const end = el.selectionEnd;
        const value = el.value;
        // Ohne Auswahl: Tab an Cursor einfügen
        if (start === end) {
          el.value = value.slice(0, start) + '\t' + value.slice(end);
          el.selectionStart = el.selectionEnd = start + 1;
          return;
        }
        // Mit Auswahl: alle selektierten Zeilen ein-/ausrücken
        const before = value.slice(0, start);
        const sel = value.slice(start, end);
        const after = value.slice(end);
        const lines = sel.split('\n');
        let changed = '';
        if (e.shiftKey) {
          // Ausrücken: führenden Tab oder zwei Spaces entfernen
          changed = lines.map(line => {
            if (line.startsWith('\t')) return line.slice(1);
            if (line.startsWith('  ')) return line.slice(2);
            return line;
          }).join('\n');
        } else {
          // Einrücken: führenden Tab hinzufügen
          changed = lines.map(line => '\t' + line).join('\n');
        }
        el.value = before + changed + after;
        // Auswahlbereich neu setzen
        if (e.shiftKey) {
          // grob schätzen: Auswahl wird kürzer, aber wir behalten Start gleich
          el.selectionStart = start;
          el.selectionEnd = start + changed.length;
        } else {
          // Auswahl wird länger (ein Tab je Zeile)
          el.selectionStart = start;
          el.selectionEnd = start + changed.length;
        }
        return;
      }
      if (isEnter && isCmd) {
        e.preventDefault();
        document.getElementById('runQuery').click();
      }
    });
  }

  function init() {
    document.getElementById('runQuery').addEventListener('click', async () => {
      try { await runQuery(); } catch(e) { showError(String(e.message || e)); }
    });
    document.getElementById('refreshTables').addEventListener('click', loadTables);
    const btnRV = document.getElementById('refreshViews');
    if (btnRV) btnRV.addEventListener('click', loadViews);
    const btnSave = document.getElementById('saveView');
    if (btnSave) btnSave.addEventListener('click', async () => {
      try { await saveViewFromEditor(); } catch(e) { showError(String(e.message || e)); }
    });
    bindKeys();
    loadTables();
    loadViews();
  }

  document.addEventListener('DOMContentLoaded', init);
})();


