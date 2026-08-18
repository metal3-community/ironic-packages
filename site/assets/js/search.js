// Client-side package search. Returns a single result per package, showing
// its description and every published version (distro/arch) with a download
// link. Data comes from the Hugo-generated index.json.
(function () {
  const input = document.getElementById("pkg-search");
  const results = document.getElementById("search-results");
  const empty = document.getElementById("search-empty");
  if (!input || !results) return;

  let packages = [];

  fetch(input.dataset.index)
    .then((r) => r.json())
    .then((data) => {
      packages = Array.isArray(data) ? data : [];
      render(input.value);
    })
    .catch(() => {
      if (empty) {
        empty.textContent = "Failed to load the package index.";
        empty.classList.remove("hidden");
      }
    });

  function score(pkg, q) {
    const name = pkg.name.toLowerCase();
    const desc = (pkg.description || "").toLowerCase();
    if (name === q) return 100;
    if (name.startsWith(q)) return 60;
    if (name.includes(q)) return 30;
    if (desc.includes(q)) return 10;
    return 0;
  }

  function render(query) {
    const q = (query || "").trim().toLowerCase();
    let items;
    if (q) {
      items = packages
        .map((p) => [score(p, q), p])
        .filter((x) => x[0] > 0)
        .sort((a, b) => b[0] - a[0] || a[1].name.localeCompare(b[1].name))
        .map((x) => x[1]);
    } else {
      items = packages.slice().sort((a, b) => a.name.localeCompare(b.name));
    }

    results.replaceChildren(...items.map(card));
    if (empty) empty.classList.toggle("hidden", items.length > 0);
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function card(pkg) {
    const li = el("li", "rounded-lg border border-slate-200 bg-white p-4");

    const head = el("div", "flex flex-wrap items-baseline justify-between gap-2");
    head.appendChild(el("h3", "font-semibold text-slate-900", pkg.name));
    if (pkg.latest) head.appendChild(el("span", "font-mono text-xs text-slate-500", pkg.latest));
    li.appendChild(head);

    if (pkg.description) li.appendChild(el("p", "mt-1 text-sm text-slate-600", pkg.description));

    const meta = el("div", "mt-2 flex flex-wrap gap-2 text-xs");
    if (pkg.license) meta.appendChild(el("span", "rounded bg-slate-100 px-2 py-0.5 text-slate-600", pkg.license));
    li.appendChild(meta);

    if (pkg.versions && pkg.versions.length) {
      const list = el("div", "mt-3 flex flex-wrap gap-2");
      for (const v of pkg.versions) {
        const a = el("a", "rounded-md border border-slate-200 px-2 py-1 text-xs text-slate-700 hover:border-blue-300 hover:text-blue-700");
        a.href = v.href;
        a.textContent = `${v.distro}/${v.arch} · ${v.version}`;
        list.appendChild(a);
      }
      li.appendChild(list);
    }
    return li;
  }

  input.addEventListener("input", () => render(input.value));
})();
