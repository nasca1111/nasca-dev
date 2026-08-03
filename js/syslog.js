async function loadCommits() {
  const res = await fetch(
    "https://api.github.com/repos/nasca1111/nasca-dev/commits?per_page=5",
  );

  const commits = await res.json();

  const list = document.getElementById("commit-list");

  commits.forEach((commit) => {
    const date = new Date(commit.commit.author.date);

    const formattedDate =
      date.getFullYear() +
      "." +
      String(date.getMonth() + 1).padStart(2, "0") +
      "." +
      String(date.getDate()).padStart(2, "0") +
      " " +
      String(date.getHours()).padStart(2, "0") +
      ":" +
      String(date.getMinutes()).padStart(2, "0") +
      ":" +
      String(date.getSeconds()).padStart(2, "0");

    const li = document.createElement("li");

    li.innerHTML = `
      <div class="meta-row-syslog">
        <span class="status-dot"></span>
        <span class="meta-key-syslog">
                        ${formattedDate} |
        </span>
        <a href="${commit.html_url}" target="_blank">
          ${commit.commit.message}
        </a>

      </div>
    `;

    list.appendChild(li);
  });
}

loadCommits();
