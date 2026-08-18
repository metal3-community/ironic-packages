// Client-side filtering for the package table (pkgs.alpinelinux.org style).
// Filters rows in-place by package name/description, distro, and architecture.
(function () {
  const name = document.getElementById("f-name");
  const distro = document.getElementById("f-distro");
  const arch = document.getElementById("f-arch");
  const rows = Array.from(document.querySelectorAll(".pkg-row"));
  const count = document.getElementById("pkg-count");
  if (!rows.length) return;

  const total = count ? count.dataset.total : rows.length;

  function apply() {
    const q = (name && name.value ? name.value : "").trim().toLowerCase();
    const d = distro && distro.value ? distro.value : "";
    const a = arch && arch.value ? arch.value : "";
    let shown = 0;

    for (const row of rows) {
      const haystack = (row.dataset.search || "").toLowerCase();
      const ok =
        (!q || haystack.includes(q)) &&
        (!d || row.dataset.distro === d) &&
        (!a || row.dataset.arch === a);
      row.hidden = !ok;
      if (ok) shown++;
    }

    if (count) {
      count.textContent =
        shown === Number(total)
          ? `${total} packages`
          : `${shown} of ${total} packages`;
    }
  }

  for (const input of [name, distro, arch]) {
    if (!input) continue;
    input.addEventListener("input", apply);
    input.addEventListener("change", apply);
  }
  apply();
})();
