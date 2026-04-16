(function (window) {
  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function parseCsvTags(value) {
    return String(value || '')
      .split(',')
      .map(function (tag) { return tag.trim(); })
      .filter(Boolean);
  }

  function uniqueTags(values) {
    var seen = new Set();
    var output = [];
    (values || []).forEach(function (raw) {
      var tag = String(raw || '').trim();
      if (!tag) return;
      var key = tag.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      output.push(tag);
    });
    return output;
  }

  function createTagSelector(options) {
    var hidden = document.getElementById(options.hiddenInputId);
    var input = document.getElementById(options.inputId);
    var suggestions = document.getElementById(options.suggestionsId);
    var chipContainer = document.getElementById(options.chipContainerId);
    var addButton = options.addButtonId ? document.getElementById(options.addButtonId) : null;
    var allTags = Array.isArray(options.allTags) ? options.allTags : [];

    if (!hidden || !input || !suggestions || !chipContainer) {
      return null;
    }

    var state = {
      tags: uniqueTags(parseCsvTags(hidden.value)),
      activeSuggestionIndex: -1,
    };

    function anchorFloatingSuggestions() {
      if (suggestions.dataset.floatingAnchored === '1') {
        return;
      }
      var host = input.closest('.input-group') || input.parentElement;
      if (!host) {
        return;
      }
      if (!host.contains(suggestions)) {
        host.appendChild(suggestions);
      }
      try {
        if (window.getComputedStyle(host).position === 'static') {
          host.style.position = 'relative';
        }
      } catch (_) {}
      suggestions.style.position = 'absolute';
      suggestions.style.left = '0';
      suggestions.style.right = '0';
      suggestions.style.top = 'calc(100% + 0.35rem)';
      suggestions.style.zIndex = '45';
      suggestions.style.marginTop = '0';
      suggestions.dataset.floatingAnchored = '1';
    }

    function getSuggestionItems() {
      return suggestions.querySelectorAll('a[data-tag]');
    }

    function setActiveSuggestion(index) {
      var items = getSuggestionItems();
      state.activeSuggestionIndex = index;
      items.forEach(function (item, idx) {
        item.classList.toggle('active', idx === index);
      });
      if (index >= 0 && items[index]) {
        try { items[index].scrollIntoView({ block: 'nearest' }); } catch (_) {}
      }
    }

    function pickSuggestion(item) {
      if (!item) return false;
      addTag(item.getAttribute('data-tag'));
      input.value = '';
      input.focus();
      renderSuggestions('');
      return true;
    }

    function notifyChange() {
      hidden.value = state.tags.join(', ');
      if (typeof options.onChange === 'function') {
        options.onChange(state.tags.slice());
      }
    }

    function defaultChipRenderer(tag, index) {
      return '<span class="badge bg-primary d-inline-flex align-items-center gap-1">'
        + escapeHtml(tag)
        + '<button type="button" class="btn-close btn-close-white" aria-label="Remove ' + escapeHtml(tag) + '" data-tag-index="' + index + '"></button>'
        + '</span>';
    }

    function renderChips() {
      var renderer = typeof options.renderChip === 'function' ? options.renderChip : defaultChipRenderer;
      chipContainer.innerHTML = state.tags.map(function (tag, index) {
        return renderer(tag, index, escapeHtml);
      }).join('');
      notifyChange();
    }

    function addTag(rawTag) {
      var tag = String(rawTag || '').trim();
      if (!tag) return false;
      var exists = state.tags.some(function (existing) {
        return existing.toLowerCase() === tag.toLowerCase();
      });
      if (exists) return false;
      state.tags.push(tag);
      renderChips();
      return true;
    }

    function removeTag(index) {
      if (!Number.isInteger(index) || index < 0 || index >= state.tags.length) return;
      state.tags.splice(index, 1);
      renderChips();
    }

    function hideSuggestions() {
      state.activeSuggestionIndex = -1;
      suggestions.style.display = 'none';
    }

    function renderSuggestions(query) {
      anchorFloatingSuggestions();
      var normalized = String(query || '').trim().toLowerCase();
      var showAllOnEmpty = options.showAllOnEmpty !== false;

      var matches = allTags
        .filter(function (tag) {
          var alreadyAdded = state.tags.some(function (existing) {
            return existing.toLowerCase() === String(tag).toLowerCase();
          });
          if (alreadyAdded) return false;
          if (!normalized) return showAllOnEmpty;
          return String(tag).toLowerCase().includes(normalized);
        })
        .slice(0, 10);

      if (!normalized && !showAllOnEmpty) {
        hideSuggestions();
        return;
      }

      state.activeSuggestionIndex = -1;

      if (matches.length === 0) {
        suggestions.innerHTML = '<div class="list-group-item text-muted">Press Enter to add this tag</div>';
      } else {
        suggestions.innerHTML = matches.map(function (tag) {
          return '<a href="#" class="list-group-item list-group-item-action" data-tag="' + escapeHtml(tag) + '">' + escapeHtml(tag) + '</a>';
        }).join('');

        suggestions.querySelectorAll('a').forEach(function (item) {
          item.addEventListener('click', function (event) {
            event.preventDefault();
            pickSuggestion(item);
          });
        });
      }

      suggestions.style.display = 'block';
    }

    function submitInputTag() {
      addTag(input.value);
      input.value = '';
      input.focus();
      renderSuggestions('');
    }

    if (addButton) {
      addButton.addEventListener('click', submitInputTag);
    }

    input.addEventListener('keydown', function (event) {
      if (event.key === 'ArrowDown') {
        if (suggestions.style.display === 'none') {
          return;
        }
        var downItems = getSuggestionItems();
        if (!downItems.length) {
          return;
        }
        event.preventDefault();
        var downIndex = state.activeSuggestionIndex < 0
          ? 0
          : Math.min(state.activeSuggestionIndex + 1, downItems.length - 1);
        setActiveSuggestion(downIndex);
        return;
      }

      if (event.key === 'ArrowUp') {
        if (suggestions.style.display === 'none') {
          return;
        }
        var upItems = getSuggestionItems();
        if (!upItems.length) {
          return;
        }
        event.preventDefault();
        if (state.activeSuggestionIndex <= 0) {
          setActiveSuggestion(-1);
          var length = String(input.value || '').length;
          if (typeof input.setSelectionRange === 'function') {
            input.setSelectionRange(length, length);
          }
          return;
        }
        setActiveSuggestion(state.activeSuggestionIndex - 1);
        return;
      }

      if (event.key === 'Enter') {
        var enterItems = getSuggestionItems();
        if (suggestions.style.display !== 'none' && enterItems.length > 0) {
          event.preventDefault();
          var enterIndex = state.activeSuggestionIndex >= 0 ? state.activeSuggestionIndex : 0;
          pickSuggestion(enterItems[enterIndex]);
          return;
        }
        event.preventDefault();
        submitInputTag();
        return;
      }

      if (event.key !== 'Tab' || event.shiftKey || event.ctrlKey || event.altKey || event.metaKey) {
        return;
      }

      // If nothing is typed, let Tab move to the next field naturally.
      if (!String(input.value || '').trim()) {
        return;
      }

      if (suggestions.style.display === 'none') {
        return;
      }

      var items = getSuggestionItems();
      if (!items.length) {
        return;
      }

      event.preventDefault();
      var pickIndex = state.activeSuggestionIndex >= 0 ? state.activeSuggestionIndex : 0;
      pickSuggestion(items[pickIndex]);
    });

    input.addEventListener('input', function (event) {
      renderSuggestions(event.target.value);
    });

    input.addEventListener('focus', function () {
      renderSuggestions(input.value || '');
    });

    input.addEventListener('blur', function () {
      setTimeout(function () {
        if (document.activeElement === input) {
          return;
        }
        hideSuggestions();
      }, 150);
    });

    chipContainer.addEventListener('click', function (event) {
      var button = event.target.closest('button[data-tag-index]');
      if (!button) return;
      removeTag(Number(button.getAttribute('data-tag-index')));
    });

    renderChips();

    return {
      addTag: addTag,
      getTags: function () { return state.tags.slice(); },
      setTags: function (values) {
        state.tags = uniqueTags(Array.isArray(values) ? values : parseCsvTags(values));
        renderChips();
      },
      hideSuggestions: hideSuggestions,
      parseCsvTags: parseCsvTags,
    };
  }

  window.TagSelector = {
    create: createTagSelector,
    parseCsvTags: parseCsvTags,
    escapeHtml: escapeHtml,
  };
}(window));
