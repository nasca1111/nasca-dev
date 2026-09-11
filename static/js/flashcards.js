(() => {
  const cards = JSON.parse(document.getElementById('flashcardData').textContent);
  const card = document.getElementById('studyCard');
  const content = document.getElementById('cardContent');
  const side = document.getElementById('cardSide');
  const hint = document.getElementById('cardHint');
  const progress = document.getElementById('cardProgress');
  let index = 0, showingBack = false;
  function render() { const current = cards[index]; content.innerHTML = showingBack ? current.back : current.front; side.textContent = showingBack ? 'ANSWER' : 'QUESTION'; hint.textContent = showingBack ? 'Click to show question' : 'Click to reveal answer'; progress.textContent = `${index + 1} / ${cards.length}`; card.classList.toggle('is-answer', showingBack); }
  function change(step) { index = (index + step + cards.length) % cards.length; showingBack = false; render(); }
  card.addEventListener('click', () => { showingBack = !showingBack; render(); });
  document.getElementById('previousCard').addEventListener('click', () => change(-1));
  document.getElementById('nextCard').addEventListener('click', () => change(1));
  document.addEventListener('keydown', event => { if (event.code === 'Space') { event.preventDefault(); card.click(); } else if (event.key === 'ArrowLeft') change(-1); else if (event.key === 'ArrowRight') change(1); });
})();
