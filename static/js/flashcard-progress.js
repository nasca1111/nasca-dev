(() => {
  document.querySelectorAll('.flashcard-deck[data-deck-id]').forEach(deck => {
    let known = {};
    try { known = JSON.parse(localStorage.getItem(`flashcard-known-v1-${deck.dataset.deckId}`)) || {}; } catch { /* Empty or invalid local progress. */ }
    const ids = deck.dataset.cardIds ? deck.dataset.cardIds.split(',') : [];
    const knownCount = ids.filter(id => known[id]).length;
    deck.querySelector('.deck-progress').textContent = `알고 있는 문제 ${knownCount} · 복습할 문제 ${ids.length - knownCount}`;
  });
})();
