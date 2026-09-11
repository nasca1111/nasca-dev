(() => {
  const cards = JSON.parse(
    document.getElementById("flashcardData").textContent,
  );
  const storageKey = `flashcard-known-v1-${window.flashcardDeckId}`;
  function loadProgress() {
    try {
      const stored = JSON.parse(localStorage.getItem(storageKey)) || {};
      return Object.fromEntries(
        Object.entries(stored).map(([id, value]) => [
          id,
          value === true ? "known" : value,
        ]),
      );
    } catch {
      return {};
    }
  }
  let progressByCard = loadProgress(),
    index = 0,
    showingAnswer = false,
    catalogFilter = "all";
  const card = document.getElementById("studyCard"),
    question = document.getElementById("cardContent");
  const answer = document.getElementById("answerContent"),
    answerPanel = document.getElementById("answerPanel");
  const hint = document.getElementById("cardHint"),
    progress = document.getElementById("cardProgress");
  const status = document.getElementById("knowledgeStatus"),
    catalog = document.getElementById("cardCatalog");
  const picker = document.getElementById("cardPicker"),
    catalogLabel = document.getElementById("catalogLabel");
  const catalogCount = document.getElementById("catalogCount");
  const currentCard = () => cards[index];
  const cardStatus = (item) => progressByCard[item.id] || "unanswered";
  const save = () =>
    localStorage.setItem(storageKey, JSON.stringify(progressByCard));
  function preview(html) {
    const element = document.createElement("div");
    element.innerHTML = html;
    return (element.textContent || element.innerText || "이미지 / 미디어 카드")
      .trim()
      .replace(/\s+/g, " ")
      .slice(0, 110);
  }
  function render() {
    const current = currentCard(),
      state = cardStatus(current);
    question.innerHTML = current.front;
    answer.innerHTML = current.back;
    answerPanel.hidden = !showingAnswer;
    hint.textContent = showingAnswer
      ? "카드를 눌러 답변 숨기기"
      : "카드를 눌러 답변 보기";
    progress.textContent = `${index + 1} / ${cards.length}`;
    status.textContent = `상태: ${state === "known" ? "알고 있음" : state === "unknown" ? "모름 · 다시 볼 문제" : "아직 답하지 않음"}`;
    card.classList.toggle("is-answer", showingAnswer);
    card.classList.toggle("is-known", state === "known");
  }
  function moveToNext() {
    index = (index + 1) % cards.length;
    showingAnswer = false;
    render();
  }
  function mark(state) {
    progressByCard[currentCard().id] = state;
    save();
    moveToNext();
  }
  function catalogCards() {
    return catalogFilter === "unknown"
      ? cards.filter((item) => cardStatus(item) === "unknown")
      : cards;
  }
  function renderCatalog() {
    const listed = catalogCards();
    catalog.hidden = false;
    catalogLabel.textContent =
      catalogFilter === "unknown" ? "모르는 문제" : "전체 문제";
    catalogCount.textContent = `${listed.length} cards`;
    picker.replaceChildren();
    if (!listed.length) {
      const empty = document.createElement("p");
      empty.className = "learning-empty-state";
      empty.textContent = "아직 ‘모름’으로 표시한 문제가 없습니다.";
      picker.append(empty);
      return;
    }
    listed.forEach((item) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "card-picker-item";
      const state =
        item.id === currentCard().id
          ? "now"
          : cardStatus(item) === "unknown"
            ? "fail"
            : cardStatus(item) === "known"
              ? "pass"
              : "new";
      button.dataset.status = state;
      button.innerHTML = `<span>${state.toUpperCase()}</span><strong>${preview(item.front)}</strong>`;
      button.addEventListener("click", () => {
        index = cards.findIndex((card) => card.id === item.id);
        showingAnswer = false;
        catalog.hidden = true;
        render();
        card.scrollIntoView({ behavior: "smooth", block: "start" });
      });
      picker.append(button);
    });
  }
  card.addEventListener("click", () => {
    showingAnswer = !showingAnswer;
    render();
  });
  document
    .getElementById("unknownCard")
    .addEventListener("click", () => mark("unknown"));
  document
    .getElementById("knownCard")
    .addEventListener("click", () => mark("known"));
  document.getElementById("closeCatalog").addEventListener("click", () => {
    catalog.hidden = true;
  });
  document.querySelectorAll("[data-list-filter]").forEach((button) =>
    button.addEventListener("click", () => {
      catalogFilter = button.dataset.listFilter;
      document
        .querySelectorAll("[data-list-filter]")
        .forEach((item) => item.classList.toggle("is-active", item === button));
      renderCatalog();
    }),
  );
  document.addEventListener("keydown", (event) => {
    if (event.code === "Space") {
      event.preventDefault();
      card.click();
    } else if (event.key === "ArrowLeft") mark("unknown");
    else if (event.key === "ArrowRight") mark("known");
  });
  render();
})();
