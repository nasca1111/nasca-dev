(() => {
  const cards = JSON.parse(document.getElementById('flashcardData').textContent);
  const storageKey = `flashcard-known-v1-${window.flashcardDeckId}`;
  const loadKnown = () => { try { return JSON.parse(localStorage.getItem(storageKey)) || {}; } catch { return {}; } };
  let known = loadKnown(), filter = 'all', index = 0, showingBack = false;
  const card = document.getElementById('studyCard'), content = document.getElementById('cardContent');
  const side = document.getElementById('cardSide'), hint = document.getElementById('cardHint');
  const progress = document.getElementById('cardProgress'), status = document.getElementById('knowledgeStatus');
  const toggle = document.getElementById('knownToggle'), empty = document.getElementById('emptyStudy');
  const visibleCards = () => filter === 'unknown' ? cards.filter(item => !known[item.id]) : cards;
  function save() { localStorage.setItem(storageKey, JSON.stringify(known)); }
  function render() {
    const visible = visibleCards();
    if (!visible.length) {
      card.hidden = true; empty.hidden = false; progress.textContent = `0 / ${cards.length}`;
      document.querySelector('.study-controls').hidden = true;
      document.querySelector('.study-status').hidden = true;
      return;
    }
    index = ((index % visible.length) + visible.length) % visible.length;
    const current = visible[index], isKnown = Boolean(known[current.id]);
    card.hidden = false; empty.hidden = true;
    document.querySelector('.study-controls').hidden = false;
    document.querySelector('.study-status').hidden = false;
    content.innerHTML = showingBack ? current.back : current.front;
    side.textContent = showingBack ? 'ANSWER' : 'QUESTION';
    hint.textContent = showingBack ? 'Click to show question' : 'Click to reveal answer';
    progress.textContent = `${index + 1} / ${visible.length} · 전체 ${cards.length}`;
    status.textContent = `상태: ${isKnown ? '알고 있음' : '복습 필요'}`;
    toggle.textContent = isKnown ? '↺ 복습 문제로 변경' : '✓ 알고 있어요';
    card.classList.toggle('is-answer', showingBack);
    card.classList.toggle('is-known', isKnown);
  }
  function change(step) {
    const visible = visibleCards();
    if (visible.length) { index = (index + step + visible.length) % visible.length; showingBack = false; render(); }
  }
  card.addEventListener('click', () => { showingBack = !showingBack; render(); });
  document.getElementById('previousCard').addEventListener('click', () => change(-1));
  document.getElementById('nextCard').addEventListener('click', () => change(1));
  toggle.addEventListener('click', () => {
    const current = visibleCards()[index];
    if (known[current.id]) delete known[current.id]; else known[current.id] = true;
    save(); showingBack = false; render();
  });
  document.querySelectorAll('[data-filter]').forEach(button => button.addEventListener('click', () => {
    filter = button.dataset.filter; index = 0; showingBack = false;
    document.querySelectorAll('[data-filter]').forEach(item => item.classList.toggle('is-active', item === button));
    render();
  }));
  document.addEventListener('keydown', event => {
    if (event.code === 'Space' && !card.hidden) { event.preventDefault(); card.click(); }
    else if (event.key === 'ArrowLeft') change(-1);
    else if (event.key === 'ArrowRight') change(1);
  });
  render();
})();
