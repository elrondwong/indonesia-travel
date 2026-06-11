const topButton = document.querySelector('.to-top');
topButton.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));

document.querySelectorAll('.document img').forEach((img) => {
  img.addEventListener('click', () => {
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;z-index:100;background:rgba(10,18,35,.82);display:flex;align-items:center;justify-content:center;padding:24px;cursor:zoom-out;';
    const clone = img.cloneNode();
    clone.style.cssText = 'max-width:96vw;max-height:92vh;width:auto;height:auto;border-radius:8px;background:white;';
    overlay.appendChild(clone);
    overlay.addEventListener('click', () => overlay.remove());
    document.body.appendChild(overlay);
  });
});

const checklistPrefix = 'indonesia-photo-route-checklist:';

document.querySelectorAll('.document input[type="checkbox"][data-checklist-key]').forEach((checkbox) => {
  const item = checkbox.closest('li');
  const key = `${checklistPrefix}${checkbox.dataset.checklistKey}`;
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
    // Local storage can be blocked in private browsing; the checkbox still works for this session.
  }

  setVisualState();
  checkbox.addEventListener('change', () => {
    setVisualState();
    try {
      window.localStorage.setItem(key, checkbox.checked ? '1' : '0');
    } catch (error) {
      // Keep the UI responsive even when persistence is unavailable.
    }
  });
});
