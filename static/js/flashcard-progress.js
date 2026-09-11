(() => {
  document.querySelectorAll(".flashcard-deck[data-deck-id]").forEach((deck) => {
    let known = {};
    try {
      known =
        JSON.parse(
          localStorage.getItem(`flashcard-known-v1-${deck.dataset.deckId}`),
        ) || {};
    } catch {
      /* Empty or invalid local progress. */
    }
    const ids = deck.dataset.cardIds ? deck.dataset.cardIds.split(",") : [];
    const knownCount = ids.filter((id) => known[id]).length;
    deck.querySelector(".deck-progress-known").textContent = knownCount;
    deck.querySelector(".deck-progress-review").textContent = ids.length;
  });
})();

(() => {
  const list = document.querySelector(".flashcard-deck-list");
  if (!list) return;

  function applyScrollCap() {
    const items = Array.from(list.children).filter(
      (el) =>
        el.classList.contains("flashcard-deck") && el.style.display !== "none",
    );
    if (items.length <= 10) {
      list.style.maxHeight = "";
      list.style.overflowY = "";
      return;
    }
    const listTop = list.getBoundingClientRect().top;
    const tenthBottom = items[9].getBoundingClientRect().bottom;
    list.style.maxHeight = `${tenthBottom - listTop}px`;
    list.style.overflowY = "auto";
  }

  window.addEventListener("load", applyScrollCap);
  window.addEventListener("resize", applyScrollCap);
  window.applyDeckScrollCap = applyScrollCap; // 나중에 검색/필터 기능 추가하면 그쪽에서 재호출
})();
