(function () {
  const checklistPrefix = 'gannan-photo-route-checklist:';

  document.querySelectorAll('input[type="checkbox"]').forEach((checkbox, index) => {
    const item = checkbox.closest('li');
    const labelText = (checkbox.closest('label')?.textContent || `item-${index}`)
      .replace(/\s+/g, ' ')
      .trim();
    const page = window.location.pathname.split('/').pop() || 'gannan';
    const key = `${checklistPrefix}${page}:${index}:${labelText}`;

    const setVisualState = () => {
      if (item) {
        item.classList.toggle('is-checked', checkbox.checked);
      }
    };

    try {
      const saved = window.localStorage.getItem(key);
      if (saved !== null) {
        checkbox.checked = saved === '1';
      }
    } catch (error) {
      // Keep checkboxes usable even when localStorage is unavailable.
    }

    setVisualState();
    checkbox.addEventListener('change', () => {
      setVisualState();
      try {
        window.localStorage.setItem(key, checkbox.checked ? '1' : '0');
      } catch (error) {
        // Ignore persistence failures; the current page state still changes.
      }
    });
  });
})();
