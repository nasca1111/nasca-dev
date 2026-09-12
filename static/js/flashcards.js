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

  let progressByCard = loadProgress();
  let index = 0;
  let showingAnswer = false;
  let catalogFilter = "all";
  let reviewUnknownOnly = false;
  let answeredThisRound = new Set();

  const card = document.getElementById("studyCard");
  const question = document.getElementById("cardContent");

  const answer = document.getElementById("answerContent");
  const answerPanel = document.getElementById("answerPanel");

  const hint = document.getElementById("cardHint");
  const progress = document.getElementById("cardProgress");

  const status = document.getElementById("knowledgeStatus");
  const catalog = document.getElementById("cardCatalog");

  const picker = document.getElementById("cardPicker");
  const catalogLabel = document.getElementById("catalogLabel");
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
    const current = currentCard();

    if (!current) return;

    const state = cardStatus(current);

    question.innerHTML = current.front;
    answer.innerHTML = current.back;

    answerPanel.hidden = !showingAnswer;

    hint.textContent = showingAnswer
      ? "카드를 눌러 답변 숨기기"
      : "카드를 눌러 답변 보기";

    progress.textContent = `${index + 1} / ${cards.length}`;

    status.textContent = `상태: ${
      state === "known"
        ? "알고 있음"
        : state === "unknown"
          ? "모름 · 다시 볼 문제"
          : "아직 답하지 않음"
    }`;

    card.classList.toggle("is-answer", showingAnswer);

    card.classList.toggle("is-known", state === "known");
  }

  function moveToNext() {
    // 틀린 문제 다시 풀기 모드
    if (reviewUnknownOnly) {
      const unknownCards = cards.filter(
        (item) => cardStatus(item) === "unknown",
      );

      // 남은 틀린 문제가 없으면 복습 완료
      if (unknownCards.length === 0) {
        showUnknownCompleteMessage();
        return;
      }

      const currentUnknownIndex = unknownCards.findIndex(
        (item) => item.id === currentCard().id,
      );

      // 현재 카드가 마지막 틀린 문제였다면
      if (currentUnknownIndex === unknownCards.length - 1) {
        showUnknownCompleteMessage();
        return;
      }

      const nextCard = unknownCards[currentUnknownIndex + 1];

      index = cards.findIndex((item) => item.id === nextCard.id);
    } else {
      // 일반 모드
      index = (index + 1) % cards.length;
    }

    showingAnswer = false;

    render();
  }

  function startUnknownReview() {
    const unknownCards = cards.filter((item) => cardStatus(item) === "unknown");

    if (!unknownCards.length) {
      alert("틀린 문제가 없습니다!");
      return;
    }

    reviewUnknownOnly = true;

    index = cards.findIndex((item) => item.id === unknownCards[0].id);

    showingAnswer = false;

    render();
  }

  function showUnknownCompleteMessage() {
    const knownCount = cards.filter(
      (item) => cardStatus(item) === "known",
    ).length;

    const unknownCount = cards.filter(
      (item) => cardStatus(item) === "unknown",
    ).length;

    question.innerHTML = `
      <div class="flashcard-complete">
        <h2>🎉 틀린 문제 복습 완료!</h2>

        <div class="completion-stats">
          <div>
            <span>맞은 문제</span>
            <strong>${knownCount}</strong>
          </div>

          <div>
            <span>아직 틀린 문제</span>
            <strong>${unknownCount}</strong>
          </div>

          <div>
            <span>전체 문제</span>
            <strong>${cards.length}</strong>
          </div>
        </div>

        <button
          type="button"
          id="finishUnknownReview"
        >
          전체 문제로 돌아가기
        </button>
      </div>
    `;

    answerPanel.hidden = true;

    hint.textContent = "복습 완료";

    status.textContent = "상태: 틀린 문제 복습 완료";

    progress.textContent = `${cards.length} / ${cards.length}`;

    card.classList.remove("is-answer", "is-known");

    document
      .getElementById("finishUnknownReview")
      .addEventListener("click", () => {
        reviewUnknownOnly = false;
        index = 0;
        showingAnswer = false;

        render();
      });
  }

  function showCompleteMessage() {
    const knownCount = cards.filter(
      (item) => cardStatus(item) === "known",
    ).length;

    const unknownCount = cards.filter(
      (item) => cardStatus(item) === "unknown",
    ).length;

    question.innerHTML = `
      <div class="flashcard-complete">
        <h2>🎉 문제를 모두 풀었습니다!</h2>

        <p>
          모든 카드의 학습 상태를 기록했습니다.
        </p>

        <div class="completion-stats">
          <div>
            <span>맞은 문제</span>
            <strong>${knownCount}</strong>
          </div>

          <div>
            <span>틀린 문제</span>
            <strong>${unknownCount}</strong>
          </div>

          <div>
            <span>전체 문제</span>
            <strong>${cards.length}</strong>
          </div>
        </div>

        <button
          type="button"
          id="restartCards"
        >
          처음부터 다시 보기
        </button>

        ${
          unknownCount > 0
            ? `
              <button
                type="button"
                id="reviewUnknown"
                class="btn btn-primary"
              >
                틀린 문제 다시 풀기
              </button>
            `
            : ""
        }
      </div>
    `;

    answerPanel.hidden = true;

    hint.textContent = "학습 완료";

    status.textContent = "상태: 전체 문제 완료";

    progress.textContent = `${cards.length} / ${cards.length}`;

    card.classList.remove("is-answer", "is-known");

    document.getElementById("restartCards").addEventListener("click", () => {
      reviewUnknownOnly = false;
      answeredThisRound = new Set();
      index = 0;
      showingAnswer = false;

      render();
    });

    const reviewButton = document.getElementById("reviewUnknown");

    if (reviewButton) {
      reviewButton.addEventListener("click", startUnknownReview);
    }
  }

  function mark(state) {
    const current = currentCard();

    progressByCard[current.id] = state;
    answeredThisRound.add(current.id);

    save();

    // 틀린 문제 복습 모드
    if (reviewUnknownOnly) {
      moveToNext();
      return;
    }

    // 이번 회차에서 모든 카드를 풀었는지 확인
    const allDone = cards.every((item) => answeredThisRound.has(item.id));

    if (allDone) {
      showCompleteMessage();
      return;
    }

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

      button.innerHTML = `
        <span>${state.toUpperCase()}</span>
        <strong>${preview(item.front)}</strong>
      `;

      button.addEventListener("click", () => {
        index = cards.findIndex((card) => card.id === item.id);

        showingAnswer = false;

        catalog.hidden = true;

        render();

        card.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
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
    } else if (event.key === "ArrowLeft") {
      mark("unknown");
    } else if (event.key === "ArrowRight") {
      mark("known");
    }
  });

  render();
})();
