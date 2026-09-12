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
  let studyQueue = [];
  let studyQueueIndex = 0;
  let answeredThisRound = new Set();
  let isCompleteScreen = false;

  // Fail / Pass 버튼의 현재 역할
  let unknownCardMode = "unknown";
  let knownCardMode = "known";

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

  const unknownButton = document.getElementById("unknownCard");
  const knownButton = document.getElementById("knownCard");

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

  // 일반 학습 버튼 스타일
  function setStudyButtons() {
    unknownButton.className = "btn btn-danger";
    knownButton.className = "btn btn-green";

    unknownButton.textContent = "Fail";
    knownButton.textContent = "Pass";

    unknownButton.disabled = false;
    knownButton.disabled = false;

    unknownCardMode = "unknown";
    knownCardMode = "known";
  }

  // 완료 화면 버튼 스타일
  function setCompleteButtons(unknownCount) {
    unknownButton.className = "btn btn-ghost";
    knownButton.className = "btn btn-ghost";

    unknownButton.textContent = "Restart";
    knownButton.textContent = "Review";

    unknownButton.disabled = false;
    knownButton.disabled = unknownCount === 0;

    unknownCardMode = "restart";
    knownCardMode = "review";
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

    // 일반 학습 화면
    setStudyButtons();
  }

  function moveToNext() {
    // 목록에서 시작한 학습 모드
    if (studyQueue.length > 0) {
      studyQueueIndex++;

      // 아직 안 푼 다음 문제가 있으면 이동
      while (studyQueueIndex < studyQueue.length) {
        const nextCard = studyQueue[studyQueueIndex];

        if (!answeredThisRound.has(nextCard.id)) {
          index = cards.findIndex((item) => item.id === nextCard.id);

          showingAnswer = false;
          render();
          return;
        }

        studyQueueIndex++;
      }

      // 배열 앞쪽으로 돌아가서 아직 안 푼 문제 찾기
      studyQueueIndex = 0;

      while (studyQueueIndex < studyQueue.length) {
        const nextCard = studyQueue[studyQueueIndex];

        if (!answeredThisRound.has(nextCard.id)) {
          index = cards.findIndex((item) => item.id === nextCard.id);

          showingAnswer = false;
          render();
          return;
        }

        studyQueueIndex++;
      }

      // 모든 문제가 끝남
      if (reviewUnknownOnly) {
        showUnknownCompleteMessage();
      } else {
        showCompleteMessage();
      }

      return;
    }

    // 일반적인 전체 문제 학습
    index = (index + 1) % cards.length;

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

    // 이번 복습에서 풀 문제 목록
    studyQueue = unknownCards.slice();

    // 이번 복습 회차 초기화
    answeredThisRound = new Set();

    // 첫 번째 모르는 문제부터 시작
    studyQueueIndex = 0;

    index = cards.findIndex((item) => item.id === studyQueue[0].id);

    showingAnswer = false;

    isCompleteScreen = false;

    // Fail / Pass로 복구
    setStudyButtons();

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
      <div class="study-area completion">
        <h4>🎉 문제를 모두 풀었습니다!</h4>

        <div class="stat-num">정답률 : ${accuracy}%</div>
        <div class="stat-label">전체 문제 : ${cards.length}</div>
        <div class="stat-label">맞은 문제 : ${knownCount}</div>
        <div class="stat-label">틀린 문제 : ${unknownCount}</div>
      </div>
    `;

    answerPanel.hidden = true;

    hint.textContent = "복습 완료";

    status.textContent = "상태: 틀린 문제 복습 완료";

    progress.textContent = `${cards.length} / ${cards.length}`;

    card.classList.remove("is-answer", "is-known");

    // Restart / Review 버튼으로 변경
    setCompleteButtons(unknownCount);

    isCompleteScreen = true;
  }

  function showCompleteMessage() {
    const knownCount = cards.filter(
      (item) => cardStatus(item) === "known",
    ).length;

    const unknownCount = cards.filter(
      (item) => cardStatus(item) === "unknown",
    ).length;

    const accuracy =
      cards.length > 0 ? Math.round((knownCount / cards.length) * 100) : 0;

    question.innerHTML = `
      <div class="study-area completion">
        <h4>🎉 문제를 모두 풀었습니다!</h4>

        <div class="stat-num">정답률 : ${accuracy}%</div>
        <div class="stat-label">전체 문제 : ${cards.length}</div>
        <div class="stat-label">맞은 문제 : ${knownCount}</div>
        <div class="stat-label">틀린 문제 : ${unknownCount}</div>
      </div>
    `;

    answerPanel.hidden = true;

    hint.textContent = "학습 완료";

    status.textContent = "상태: 전체 문제 완료";

    progress.textContent = `${cards.length} / ${cards.length}`;

    card.classList.remove("is-answer", "is-known");

    // Restart / Review 버튼으로 변경
    setCompleteButtons(unknownCount);

    isCompleteScreen = true;
  }

  function restartCards() {
    reviewUnknownOnly = false;

    answeredThisRound = new Set();

    studyQueue = [];

    studyQueueIndex = 0;

    index = 0;

    showingAnswer = false;

    isCompleteScreen = false;

    // Fail / Pass로 복구
    setStudyButtons();

    render();
  }

  function mark(state) {
    const current = currentCard();

    progressByCard[current.id] = state;

    answeredThisRound.add(current.id);

    save();

    // 모르는 문제 목록에서 학습 중인 경우
    if (reviewUnknownOnly && studyQueue.length > 0) {
      const allUnknownDone = studyQueue.every((item) =>
        answeredThisRound.has(item.id),
      );

      if (allUnknownDone) {
        showUnknownCompleteMessage();
        return;
      }
    }

    // 전체 문제 목록에서 학습 중인 경우
    else if (studyQueue.length > 0) {
      const allDone = studyQueue.every((item) =>
        answeredThisRound.has(item.id),
      );

      if (allDone) {
        showCompleteMessage();
        return;
      }
    }

    // 일반 학습 모드
    else {
      const allDone = cards.every((item) => answeredThisRound.has(item.id));

      if (allDone) {
        showCompleteMessage();
        return;
      }
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
        // 전체 문제 목록
        if (catalogFilter === "all") {
          studyQueue = cards.slice();
          reviewUnknownOnly = false;
        }

        // 모르는 문제 목록
        else if (catalogFilter === "unknown") {
          studyQueue = cards.filter((card) => cardStatus(card) === "unknown");

          reviewUnknownOnly = true;
        }

        // 선택한 문제의 위치
        const selectedIndex = studyQueue.findIndex(
          (card) => card.id === item.id,
        );

        if (selectedIndex === -1) {
          return;
        }

        // 선택한 문제부터 시작
        studyQueue = [
          ...studyQueue.slice(selectedIndex),
          ...studyQueue.slice(0, selectedIndex),
        ];

        studyQueueIndex = 0;

        index = cards.findIndex((card) => card.id === item.id);

        showingAnswer = false;

        catalog.hidden = true;

        isCompleteScreen = false;

        // Fail / Pass로 복구
        setStudyButtons();

        render();

        card.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      });

      picker.append(button);
    });
  }

  // 카드 클릭 → 답변 보기 / 숨기기
  card.addEventListener("click", () => {
    if (isCompleteScreen) {
      return;
    }

    showingAnswer = !showingAnswer;

    render();
  });

  // Fail 버튼
  unknownButton.addEventListener("click", () => {
    if (unknownCardMode === "restart") {
      restartCards();
      return;
    }

    mark("unknown");
  });

  // Pass 버튼
  knownButton.addEventListener("click", () => {
    if (knownCardMode === "review") {
      startUnknownReview();
      return;
    }

    mark("known");
  });

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
      // 완료 화면에서는 Fail 처리하지 않음
      if (unknownCardMode === "unknown") {
        mark("unknown");
      }
    } else if (event.key === "ArrowRight") {
      // 완료 화면에서는 Pass 처리하지 않음
      if (knownCardMode === "known") {
        mark("known");
      }
    }
  });

  render();
})();
