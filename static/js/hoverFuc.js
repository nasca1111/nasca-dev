const els = document.querySelectorAll(".reveal");
const io = new IntersectionObserver(
  (entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) {
        e.target.classList.add("in");
        io.unobserve(e.target);
      }
    });
  },
  { threshold: 0.12 },
);
els.forEach((el) => io.observe(el));

const modal = document.getElementById("writeModal");
const openBtn = document.getElementById("openWrite");
const closeBtn = document.getElementById("closeWrite");
const cancelBtn = document.querySelector("[data-close-modal]");
const writeForm = document.getElementById("writeForm");
const modalTitle = document.getElementById("writeModalTitle");
const modalMode = document.getElementById("modalMode");
const modalReference = document.getElementById("modalReference");
const modalState = document.getElementById("modalState");
const postItems = document.querySelectorAll(".post-item[data-editable]");
const emptyWriteBtn = document.querySelector("[data-open-write]");
const deleteForm = document.getElementById("deleteForm");
const deleteBtn = document.getElementById("deletePost");

function openWriteModal() {
  writeForm.reset();
  writeForm.action = "/write";
  modalTitle.textContent = "New Entry";
  modalMode.textContent = "NEW ENTRY";
  modalReference.textContent = "REF. NOTE-NEW";
  modalState.textContent = "DRAFT / LOCAL";
  deleteBtn.hidden = true;
  modal.classList.remove("is-edit");
  modal.classList.add("is-open");
}

function openEditModal(post) {
  writeForm.action = `/post/${post.dataset.postId}/edit`;
  writeForm.elements.title.value = post.dataset.postTitle;
  writeForm.elements.content.value = post.dataset.postContent;
  modalTitle.textContent = "Edit Entry";
  modalMode.textContent = "EDIT ENTRY";
  modalReference.textContent = `REF. NOTE-${String(post.dataset.postId).padStart(4, "0")}`;
  modalState.textContent = "EDITING / LOCAL";
  deleteForm.action = `/post/${post.dataset.postId}/delete`;
  deleteBtn.hidden = false;
  modal.classList.add("is-edit");
  modal.classList.add("is-open");
}

function closeModal() {
  modal.classList.remove("is-open");
}

if (modal && openBtn && closeBtn) {
  openBtn.addEventListener("click", openWriteModal);
  emptyWriteBtn?.addEventListener("click", openWriteModal);
  postItems.forEach((post) =>
    post.addEventListener("click", () => openEditModal(post)),
  );

  closeBtn.addEventListener("click", closeModal);
  cancelBtn.addEventListener("click", closeModal);
  deleteForm.addEventListener("submit", (event) => {
    if (!window.confirm("Delete this entry? This action cannot be undone.")) {
      event.preventDefault();
    }
  });

  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeModal();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeModal();
  });
}

const readModal = document.getElementById("readModal");
const readTitle = document.getElementById("readTitle");
const readContent = document.getElementById("readContent");
const closeRead = document.getElementById("closeRead");

if (readModal && closeRead) {
  document.querySelectorAll(".post-item").forEach((post) => {
    post.addEventListener("click", () => {
      readTitle.value = post.dataset.postTitle;
      readContent.value = post.dataset.postContent;

      readModal.classList.add("is-open");
    });
  });

  closeRead.addEventListener("click", () => {
    readModal.classList.remove("is-open");
  });

  readModal.addEventListener("click", (event) => {
    if (event.target === readModal) {
      readModal.classList.remove("is-open");
    }
  });
}
