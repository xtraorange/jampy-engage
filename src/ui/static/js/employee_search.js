window.EmployeeSearch = (function () {
  function normalizeQuery(value) {
    return String(value || '').trim();
  }

  function key(person) {
    return String(
      (person && (person.id || person.employee_id || person.username || person.email)) || ''
    ).trim().toLowerCase();
  }

  async function search(query) {
    const normalized = normalizeQuery(query);
    if (normalized.length < 2) {
      return [];
    }

    const response = await fetch(`/api/search-employees?q=${encodeURIComponent(normalized)}`);
    const data = await response.json();
    if (!response.ok || (data && data.error)) {
      throw new Error((data && data.error) || 'Unable to search employees.');
    }
    return Array.isArray(data) ? data : [];
  }

  return {
    key,
    normalizeQuery,
    search,
  };
})();