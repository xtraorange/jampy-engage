window.EmployeeSearch = (function () {
  const ADVANCED_FIELDS = [
    { key: 'first_name', label: 'First Name' },
    { key: 'last_name', label: 'Last Name' },
    { key: 'username', label: 'Username' },
    { key: 'employee_id', label: 'Employee ID' },
    { key: 'job_title', label: 'Job Title', sourceField: 'employee_job_title' },
    { key: 'department_id', label: 'Department ID' },
    { key: 'location', label: 'Location' },
    { key: 'bu_code', label: 'Business Unit' },
    { key: 'company', label: 'Company' },
    { key: 'tree_branch', label: 'Tree Branch' },
    {
      key: 'full_part_time',
      label: 'Full/Part Time',
      type: 'select',
      options: [
        { value: '', label: 'Any' },
        { value: 'F', label: 'Full Time' },
        { value: 'P', label: 'Part Time' },
      ],
    },
    { key: 'job_code', label: 'Job Code' },
  ];

  let advancedModalEl = null;
  let advancedModalBs = null;
  let advancedSelected = [];
  let advancedContext = null;
  let advancedResults = [];

  function normalizeQuery(value) {
    return String(value || '').trim();
  }

  function key(person) {
    return String(
      (person && (person.id || person.employee_id || person.username || person.email)) || ''
    ).trim().toLowerCase();
  }

  function name(person) {
    return [person && person.first_name, person && person.last_name].filter(Boolean).join(' ').trim();
  }

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  async function search(query) {
    const normalized = normalizeQuery(query);
    if (normalized.length < 2) {
      return [];
    }

    const response = await fetch(`/api/search-employees?q=${encodeURIComponent(normalized)}&scope=basic`);
    const data = await response.json();
    if (!response.ok || (data && data.error)) {
      throw new Error((data && data.error) || 'Unable to search employees.');
    }
    return Array.isArray(data) ? data : [];
  }

  async function searchAdvanced(filters) {
    const payload = {};
    Object.keys(filters || {}).forEach((field) => {
      const value = normalizeQuery(filters[field]);
      if (value) {
        payload[field] = value;
      }
    });
    const response = await fetch('/api/search-employees-advanced', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filters: payload }),
    });
    const data = await response.json();
    if (!response.ok || (data && data.error)) {
      throw new Error((data && data.error) || 'Unable to run advanced employee search.');
    }
    return Array.isArray(data) ? data : [];
  }

  async function searchFieldValues(field, query) {
    const normalized = normalizeQuery(query);
    if (normalized.length < 2) {
      return [];
    }

    const response = await fetch(`/api/search-values?field=${encodeURIComponent(field)}&q=${encodeURIComponent(normalized)}`);
    const data = await response.json();
    if (!response.ok || (data && data.error)) {
      throw new Error((data && data.error) || 'Unable to search values.');
    }
    return Array.isArray(data) ? data : [];
  }

  function setActiveSuggestion(list, index) {
    const items = list.querySelectorAll('a[data-employee-pick]');
    items.forEach((item, idx) => item.classList.toggle('active', idx === index));
    if (index >= 0 && items[index]) {
      try { items[index].scrollIntoView({ block: 'nearest' }); } catch (_) {}
    }
  }

  function anchorFloatingSuggestions(input, list) {
    if (!input || !list) return;
    if (list.dataset.floatingAnchored === '1') return;

    const host = input.closest('.input-group') || input.parentElement;
    if (!host) return;

    if (!host.contains(list)) {
      host.appendChild(list);
    }

    try {
      if (window.getComputedStyle(host).position === 'static') {
        host.style.position = 'relative';
      }
    } catch (_) {}

    list.style.position = 'absolute';
    list.style.left = '0';
    list.style.right = '0';
    list.style.top = 'calc(100% + 0.35rem)';
    list.style.zIndex = '45';
    list.style.marginTop = '0';
    list.dataset.floatingAnchored = '1';
  }

  function bindTypeahead(config) {
    const input = document.getElementById(config.inputId);
    const list = document.getElementById(config.listId);
    if (!input || !list || typeof config.onPick !== 'function') return;

    const advancedButton = config.advancedButtonId ? document.getElementById(config.advancedButtonId) : null;
    anchorFloatingSuggestions(input, list);

    input.setAttribute('autocomplete', 'off');
    input.setAttribute('autocapitalize', 'off');
    input.setAttribute('autocorrect', 'off');
    input.setAttribute('spellcheck', 'false');
    input.setAttribute('data-lpignore', 'true');
    input.setAttribute('data-1p-ignore', 'true');

    const state = {
      timer: null,
      activeIndex: -1,
      rows: [],
    };

    function hideList() {
      list.style.display = 'none';
      state.activeIndex = -1;
      state.rows = [];
    }

    function pick(row) {
      if (!row) return;
      config.onPick(row);
      input.value = '';
      hideList();
      input.focus();
    }

    if (input.dataset.employeeTypeaheadBound !== '1') {
      input.dataset.employeeTypeaheadBound = '1';

      input.addEventListener('input', (event) => {
        const query = normalizeQuery(event.target.value);
        clearTimeout(state.timer);
        if (query.length < 2) {
          hideList();
          return;
        }

        state.timer = setTimeout(async () => {
          try {
            const rows = await search(query);
            state.rows = rows;
            state.activeIndex = -1;
            if (!rows.length) {
              list.innerHTML = '<div class="list-group-item text-muted">No results</div>';
              list.style.display = 'block';
              return;
            }
            list.innerHTML = rows.map((emp, idx) => `
              <a href="#" class="list-group-item list-group-item-action" data-employee-pick="1" data-index="${idx}">
                <strong>${escapeHtml(name(emp) || '(Unknown)')}</strong><br>
                <small>${escapeHtml(emp.job_title || 'No title')} | ${escapeHtml(emp.username || '')}</small>
              </a>
            `).join('');
            list.querySelectorAll('a[data-employee-pick]').forEach((item) => {
              item.addEventListener('click', (clickEvent) => {
                clickEvent.preventDefault();
                pick(rows[Number(item.dataset.index)]);
              });
            });
            list.style.display = 'block';
          } catch (error) {
            list.innerHTML = `<div class="list-group-item text-danger">${escapeHtml(String(error))}</div>`;
            list.style.display = 'block';
          }
        }, 220);
      });

      input.addEventListener('blur', () => {
        setTimeout(() => hideList(), 200);
      });

      input.addEventListener('keydown', (event) => {
        const items = list.querySelectorAll('a[data-employee-pick]');
        if (!items.length || list.style.display === 'none') return;

        if (event.key === 'ArrowDown') {
          event.preventDefault();
          state.activeIndex = state.activeIndex < 0 ? 0 : Math.min(state.activeIndex + 1, items.length - 1);
          setActiveSuggestion(list, state.activeIndex);
          return;
        }
        if (event.key === 'ArrowUp') {
          event.preventDefault();
          state.activeIndex = state.activeIndex <= 0 ? -1 : state.activeIndex - 1;
          setActiveSuggestion(list, state.activeIndex);
          return;
        }
        if (event.key === 'Enter' || event.key === 'Tab') {
          if (event.key === 'Tab' && (event.shiftKey || event.ctrlKey || event.altKey || event.metaKey)) {
            return;
          }
          event.preventDefault();
          const index = state.activeIndex >= 0 ? state.activeIndex : 0;
          pick(state.rows[index]);
        }
      });
    }

    if (advancedButton && advancedButton.dataset.employeeAdvancedBound !== '1') {
      advancedButton.dataset.employeeAdvancedBound = '1';
      advancedButton.addEventListener('click', () => {
        openAdvancedPicker({
          title: config.advancedTitle || 'Advanced Person Search',
          onFinish: (pickedRows) => {
            pickedRows.forEach((row) => config.onPick(row));
          },
        });
      });
    }
  }

  function ensureAdvancedModal() {
    if (advancedModalEl) return advancedModalEl;
    const wrapper = document.createElement('div');
    wrapper.innerHTML = `
      <div class="modal fade" id="global-employee-advanced-modal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-xl modal-dialog-scrollable">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title" id="global-employee-advanced-title">Advanced Person Search</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
              <div class="row g-2 mb-3" id="global-employee-advanced-filters"></div>
              <div class="d-flex gap-2 mb-2">
                <button type="button" class="btn btn-primary btn-sm" id="global-employee-advanced-search-btn">Search</button>
                <button type="button" class="btn btn-outline-secondary btn-sm" id="global-employee-advanced-clear-btn">Clear</button>
              </div>
              <div id="global-employee-advanced-status" class="text-muted small mb-2">Enter one or more filters and click Search.</div>
              <div class="table-responsive mb-3">
                <table class="table table-sm align-middle">
                  <thead><tr><th>Name</th><th>Username</th><th>Title</th><th></th></tr></thead>
                  <tbody id="global-employee-advanced-results"><tr><td colspan="4" class="text-muted">No search results yet.</td></tr></tbody>
                </table>
              </div>
              <div class="border rounded p-2 bg-light">
                <div class="small text-muted mb-1">Selected in this modal</div>
                <div id="global-employee-advanced-selected" class="d-flex flex-wrap gap-1"></div>
              </div>
            </div>
            <div class="modal-footer d-flex justify-content-between">
              <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancel</button>
              <button type="button" class="btn btn-primary" id="global-employee-advanced-finish-btn">Finish and Add</button>
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(wrapper.firstElementChild);
    advancedModalEl = document.getElementById('global-employee-advanced-modal');
    advancedModalBs = new bootstrap.Modal(advancedModalEl);

    advancedModalEl.addEventListener('shown.bs.modal', () => {
      advancedModalEl.style.zIndex = '2100';
      const backdrops = document.querySelectorAll('.modal-backdrop');
      if (backdrops.length) {
        const topBackdrop = backdrops[backdrops.length - 1];
        topBackdrop.style.zIndex = '2099';
        topBackdrop.dataset.employeeAdvancedBackdrop = '1';
      }
    });

    advancedModalEl.addEventListener('hidden.bs.modal', () => {
      advancedModalEl.style.zIndex = '';
      document.querySelectorAll('.modal-backdrop[data-employee-advanced-backdrop="1"]').forEach((backdrop) => {
        backdrop.style.zIndex = '';
        delete backdrop.dataset.employeeAdvancedBackdrop;
      });
    });

    const fieldsContainer = document.getElementById('global-employee-advanced-filters');
    fieldsContainer.innerHTML = ADVANCED_FIELDS.map((field) => `
      <div class="col-md-4 col-lg-3">
        <label class="form-label small mb-1" for="advanced-filter-${field.key}">${field.label}</label>
        ${field.type === 'select'
          ? `<select class="form-select form-select-sm" id="advanced-filter-${field.key}">${(field.options || []).map((opt) => `<option value="${opt.value}">${opt.label}</option>`).join('')}</select>`
          : `<div class="position-relative"><input type="text" class="form-control form-control-sm" id="advanced-filter-${field.key}"><div id="advanced-filter-suggestions-${field.key}" class="list-group typeahead-list" style="display:none; max-height: 200px; overflow-y: auto; position: absolute; top: calc(100% + 0.35rem); left: 0; right: 0; z-index: 30; box-shadow: 0 0.5rem 1rem rgba(0,0,0,.15);"></div></div>`}
      </div>
    `).join('');

    ADVANCED_FIELDS.filter((field) => field.type !== 'select').forEach((field) => {
      bindAdvancedFieldSuggestions(field);
    });

    document.getElementById('global-employee-advanced-search-btn').addEventListener('click', async () => {
      await runAdvancedSearch();
    });

    document.getElementById('global-employee-advanced-clear-btn').addEventListener('click', () => {
      ADVANCED_FIELDS.forEach((field) => {
        const input = document.getElementById(`advanced-filter-${field.key}`);
        if (input) input.value = '';
        const list = document.getElementById(`advanced-filter-suggestions-${field.key}`);
        if (list) {
          list.innerHTML = '';
          list.style.display = 'none';
        }
      });
      advancedResults = [];
      renderAdvancedResults();
      document.getElementById('global-employee-advanced-status').textContent = 'Cleared. Enter one or more filters and click Search.';
    });

    document.getElementById('global-employee-advanced-results').addEventListener('click', (event) => {
      const addBtn = event.target.closest('button[data-advanced-add]');
      if (!addBtn) return;
      const row = advancedResults[Number(addBtn.dataset.advancedAdd)];
      if (!row) return;
      const rowKey = key(row);
      if (!rowKey || advancedSelected.some((item) => key(item) === rowKey)) return;
      advancedSelected.push(row);
      renderAdvancedSelected();
    });

    document.getElementById('global-employee-advanced-selected').addEventListener('click', (event) => {
      const removeBtn = event.target.closest('button[data-advanced-remove]');
      if (!removeBtn) return;
      advancedSelected.splice(Number(removeBtn.dataset.advancedRemove), 1);
      renderAdvancedSelected();
    });

    document.getElementById('global-employee-advanced-finish-btn').addEventListener('click', () => {
      if (advancedContext && typeof advancedContext.onFinish === 'function') {
        advancedContext.onFinish(advancedSelected.slice());
      }
      advancedModalBs.hide();
    });

    return advancedModalEl;
  }

  function bindAdvancedFieldSuggestions(field) {
    const input = document.getElementById(`advanced-filter-${field.key}`);
    const list = document.getElementById(`advanced-filter-suggestions-${field.key}`);
    if (!input || !list) return;
    anchorFloatingSuggestions(input, list);
    anchorFloatingSuggestions(input, list);

    const state = {
      timer: null,
      activeIndex: -1,
      rows: [],
    };

    function hideList() {
      list.style.display = 'none';
      state.activeIndex = -1;
      state.rows = [];
    }

    function setActive(index) {
      state.activeIndex = index;
      const items = list.querySelectorAll('a[data-value-index]');
      items.forEach((item, idx) => item.classList.toggle('active', idx === index));
      if (index >= 0 && items[index]) {
        try { items[index].scrollIntoView({ block: 'nearest' }); } catch (_) {}
      }
    }

    function pick(index) {
      const row = state.rows[index];
      if (!row) return;
      input.value = row.value || '';
      hideList();
      input.focus();
    }

    if (input.dataset.advancedFieldSuggestBound === '1') {
      return;
    }
    input.dataset.advancedFieldSuggestBound = '1';

    input.addEventListener('input', (event) => {
      const query = normalizeQuery(event.target.value);
      clearTimeout(state.timer);
      if (query.length < 2) {
        hideList();
        return;
      }

      state.timer = setTimeout(async () => {
        try {
          const rows = await searchFieldValues(field.sourceField || field.key, query);
          state.rows = rows;
          state.activeIndex = -1;
          if (!rows.length) {
            list.innerHTML = '<div class="list-group-item text-muted">No results</div>';
            list.style.display = 'block';
            return;
          }
          list.innerHTML = rows.map((item, idx) => `<a href="#" class="list-group-item list-group-item-action" data-value-index="${idx}">${escapeHtml(item.value || '')}</a>`).join('');
          list.querySelectorAll('a[data-value-index]').forEach((item) => {
            item.addEventListener('click', (clickEvent) => {
              clickEvent.preventDefault();
              pick(Number(item.dataset.valueIndex));
            });
          });
          list.style.display = 'block';
        } catch (error) {
          list.innerHTML = `<div class="list-group-item text-danger">${escapeHtml(String(error))}</div>`;
          list.style.display = 'block';
        }
      }, 220);
    });

    input.addEventListener('blur', () => {
      setTimeout(() => hideList(), 200);
    });

    input.addEventListener('keydown', (event) => {
      const items = list.querySelectorAll('a[data-value-index]');
      if (!items.length || list.style.display === 'none') return;
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        setActive(state.activeIndex < 0 ? 0 : Math.min(state.activeIndex + 1, items.length - 1));
        return;
      }
      if (event.key === 'ArrowUp') {
        event.preventDefault();
        setActive(state.activeIndex <= 0 ? -1 : state.activeIndex - 1);
        return;
      }
      if (event.key === 'Enter' || event.key === 'Tab') {
        if (event.key === 'Tab' && (event.shiftKey || event.ctrlKey || event.altKey || event.metaKey)) {
          return;
        }
        if (event.key === 'Tab' && !normalizeQuery(input.value)) {
          return;
        }
        event.preventDefault();
        pick(state.activeIndex >= 0 ? state.activeIndex : 0);
      }
    });
  }

  function renderAdvancedResults() {
    const body = document.getElementById('global-employee-advanced-results');
    if (!body) return;
    if (!advancedResults.length) {
      body.innerHTML = '<tr><td colspan="4" class="text-muted">No matching people found.</td></tr>';
      return;
    }
    body.innerHTML = advancedResults.map((person, idx) => `
      <tr>
        <td><div>${escapeHtml(name(person) || '(Unknown)')}</div><div class="text-muted small">${escapeHtml(person.email || '')}</div></td>
        <td class="font-monospace">${escapeHtml(person.username || '')}</td>
        <td>${escapeHtml(person.job_title || '')}</td>
        <td><button type="button" class="btn btn-outline-primary btn-sm" data-advanced-add="${idx}">Add</button></td>
      </tr>
    `).join('');
  }

  function renderAdvancedSelected() {
    const box = document.getElementById('global-employee-advanced-selected');
    if (!box) return;
    if (!advancedSelected.length) {
      box.innerHTML = '<span class="text-muted small">No people selected yet.</span>';
      return;
    }
    box.innerHTML = advancedSelected.map((person, idx) => `
      <span class="badge bg-primary d-inline-flex align-items-center gap-1">
        ${escapeHtml(name(person) || person.username || person.id || 'Unknown')}
        <button type="button" class="btn-close btn-close-white" aria-label="Remove" data-advanced-remove="${idx}"></button>
      </span>
    `).join('');
  }

  async function runAdvancedSearch() {
    const status = document.getElementById('global-employee-advanced-status');
    const filters = {};
    ADVANCED_FIELDS.forEach((field) => {
      const input = document.getElementById(`advanced-filter-${field.key}`);
      if (input) filters[field.key] = input.value;
    });
    status.textContent = 'Searching...';
    try {
      advancedResults = await searchAdvanced(filters);
      status.textContent = `${advancedResults.length} result${advancedResults.length === 1 ? '' : 's'} found.`;
      renderAdvancedResults();
    } catch (error) {
      status.textContent = String(error);
      advancedResults = [];
      renderAdvancedResults();
    }
  }

  function openAdvancedPicker(context) {
    ensureAdvancedModal();
    advancedContext = context || {};
    advancedSelected = [];
    advancedResults = [];
    document.getElementById('global-employee-advanced-title').textContent = advancedContext.title || 'Advanced Person Search';
    document.getElementById('global-employee-advanced-status').textContent = 'Enter one or more filters and click Search.';
    renderAdvancedResults();
    renderAdvancedSelected();
    advancedModalBs.show();
  }

  return {
    key,
    normalizeQuery,
    search,
    searchAdvanced,
    bindTypeahead,
    openAdvancedPicker,
  };
})();