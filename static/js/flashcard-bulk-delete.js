(() => {
  const bar = document.getElementById("deckBulkBar");
  if (!bar) return;
  const countLabel = document.getElementById("deckBulkCount");
  const deleteBtn = document.getElementById("deckBulkDeleteBtn");
  const cancelBtn = document.getElementById("deckBulkCancel");
  const checkboxes = () =>
    Array.from(document.querySelectorAll(".deck-select-input"));

  function refresh() {
    const checked = checkboxes().filter((cb) => cb.checked);
    countLabel.textContent = `${checked.length}개 선택`;
    bar.hidden = checked.length === 0;
  }

  checkboxes().forEach((cb) => cb.addEventListener("change", refresh));

  cancelBtn.addEventListener("click", () => {
    checkboxes().forEach((cb) => {
      cb.style.display = "";
    });
    refresh();
  });

  deleteBtn.addEventListener("click", (event) => {
    const checked = checkboxes().filter((cb) => cb.checked);
    if (checked.length === 0) return;
    if (
      !confirm(
        `선택한 ${checked.length}개의 덱을 삭제할까요? 되돌릴 수 없습니다.`,
      )
    ) {
      event.preventDefault();
    }
  });
})();
