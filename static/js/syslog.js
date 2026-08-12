function formatCommitDate(date) {
  return `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, "0")}.${String(date.getDate()).padStart(2, "0")} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}:${String(date.getSeconds()).padStart(2, "0")}`;
}

function commitDateKey(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function renderCommits(commits, selectedDate) {
  const list = document.getElementById("commit-list");
  const summary = document.getElementById("commit-summary");
  list.replaceChildren();

  const selectedCommits = commits.filter((commit) => commitDateKey(new Date(commit.commit.author.date)) === selectedDate);
  summary.textContent = `${selectedDate} · ${selectedCommits.length} update${selectedCommits.length === 1 ? "" : "s"}`;

  selectedCommits.forEach((commit) => {
    const date = new Date(commit.commit.author.date);
    const item = document.createElement("li");
    const row = document.createElement("div");
    row.className = "meta-row-syslog";

    const dot = document.createElement("span");
    dot.className = "status-dot";
    const timestamp = document.createElement("span");
    timestamp.className = "meta-key-syslog";
    timestamp.textContent = `${formatCommitDate(date)} |`;
    const link = document.createElement("a");
    link.href = commit.html_url;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = commit.commit.message.split("\n")[0];

    row.append(dot, timestamp, link);
    item.append(row);
    list.append(item);
  });
}

async function loadCommits() {
  const list = document.getElementById("commit-list");
  const tabs = document.getElementById("commit-date-tabs");
  const summary = document.getElementById("commit-summary");

  try {
    const response = await fetch("https://api.github.com/repos/nasca1111/nasca-dev/commits?per_page=30");
    if (!response.ok) throw new Error("GitHub request failed");
    const commits = await response.json();
    const dates = [...new Set(commits.map((commit) => commitDateKey(new Date(commit.commit.author.date))))];

    if (!dates.length) {
      summary.textContent = "No recent updates found.";
      return;
    }

    dates.forEach((date, index) => {
      const tab = document.createElement("button");
      tab.type = "button";
      tab.className = `learning-tab${index === 0 ? " is-active" : ""}`;
      tab.textContent = date;
      tab.setAttribute("role", "tab");
      tab.setAttribute("aria-selected", index === 0 ? "true" : "false");
      tab.addEventListener("click", () => {
        tabs.querySelectorAll("button").forEach((button) => {
          const active = button === tab;
          button.classList.toggle("is-active", active);
          button.setAttribute("aria-selected", String(active));
        });
        renderCommits(commits, date);
      });
      tabs.append(tab);
    });
    renderCommits(commits, dates[0]);
  } catch (error) {
    summary.textContent = "Unable to load GitHub updates right now.";
    list.replaceChildren();
  }
}

loadCommits();
