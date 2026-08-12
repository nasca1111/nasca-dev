document.querySelectorAll("[data-tab-target]").forEach((tab) => {
  tab.addEventListener("click", () => {
    const container = tab.parentElement;
    const target = document.getElementById(tab.dataset.tabTarget);
    if (!target) return;
    container.querySelectorAll("[data-tab-target]").forEach((item) => {
      const active = item === tab;
      item.classList.toggle("is-active", active);
      item.setAttribute("aria-selected", active);
    });
    const panelSelector = target.classList.contains("learning-category-panel")
      ? ".learning-category-panel"
      : ".learning-entry-panel";
    document.querySelectorAll(panelSelector).forEach((panel) => {
      panel.classList.toggle("is-active", panel === target);
    });
    const navigation = tab.closest(".learning-entry-navigation");
    navigation?.querySelector("[data-entry-jump]") && (navigation.querySelector("[data-entry-jump]").value = tab.dataset.tabTarget);
  });
});

document.querySelectorAll("[data-entry-jump]").forEach((select) => {
  select.addEventListener("change", () => {
    const panel = document.getElementById(select.value);
    if (!panel) return;
    document.querySelectorAll(".learning-entry-panel").forEach((item) => {
      item.classList.toggle("is-active", item === panel);
    });
  });
});

document.querySelectorAll(".rich-editor-form").forEach((form) => {
  const editor = form.querySelector(".rich-editor");
  const value = form.querySelector(".rich-editor-value");
  const sync = () => { value.value = editor.innerHTML; };

  form.querySelectorAll("[data-command]").forEach((button) => {
    button.addEventListener("mousedown", (event) => event.preventDefault());
    button.addEventListener("click", () => {
      editor.focus();
      document.execCommand(button.dataset.command, false);
      sync();
    });
  });
  form.querySelector(".rich-color input").addEventListener("input", (event) => {
    editor.focus();
    document.execCommand("foreColor", false, event.target.value);
    sync();
  });
  editor.addEventListener("input", sync);
  form.addEventListener("submit", (event) => {
    sync();
    if (!editor.textContent.trim()) {
      event.preventDefault();
      editor.focus();
    }
  });
});

document.querySelectorAll("form[data-confirm]").forEach((form) => {
  form.addEventListener("submit", (event) => {
    if (!window.confirm(form.dataset.confirm)) {
      event.preventDefault();
    }
  });
});
