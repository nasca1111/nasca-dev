async function loadCommits() {
  const res = await fetch(
    "https://api.github.com/repos/nasca1111/nasca-dev/commits?per_page=5",
  );

  const commits = await res.json();

  const list = document.getElementById("commit-list");

  commits.forEach((commit) => {
    const li = document.createElement("li");

    li.innerHTML = `
            <a href="${commit.html_url}" target="_blank">
                ${commit.commit.message}
            </a>
            <br>
            <small>
                ${new Date(commit.commit.author.date).toLocaleDateString()}
            </small>
        `;

    list.appendChild(li);
  });
}

loadCommits();
