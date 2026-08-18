#!/usr/bin/env python3
"""Build the Hugo data + content for the APK repository site.

Package metadata (description, license, URL) is taken from the melange
configuration files (the source of truth). Availability — which version is
published for each distro/arch — is taken from the built APKINDEX files. The
two are merged into a single ``site/data/packages.yaml`` that Hugo queries,
content section stubs are created for each distro/arch, and the raw package
files are linked into ``site/static`` so apk clients can still fetch them.

Usage:
    build-site-data.py --configs-dir . --repository-dir repository \
        --site-dir site --distros alpine,wolfi --arches x86_64,aarch64
"""

from __future__ import annotations

import argparse
import gzip
import io
import os
import shutil
import sys
import tarfile
from pathlib import Path

import yaml


def load_melange_metadata(configs_dir: Path) -> dict[str, dict]:
    """Return {package_name: metadata} from every melange config.

    Covers the primary package and any subpackages. Only top-level *.yaml
    files are considered (pipelines/ and recipes/ are skipped).
    """
    meta: dict[str, dict] = {}
    for path in sorted(configs_dir.glob("*.yaml")):
        try:
            doc = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            print(f"warning: skipping {path.name}: {exc}", file=sys.stderr)
            continue
        if not isinstance(doc, dict) or "package" not in doc:
            continue

        pkg = doc["package"] or {}
        name = pkg.get("name")
        if not name:
            continue

        version = str(pkg.get("version", ""))
        epoch = pkg.get("epoch", 0)
        full_version = f"{version}-r{epoch}" if version else ""
        license_ = _license(pkg)
        url = pkg.get("url") or _github_url(configs_dir)

        base = {
            "description": (pkg.get("description") or "").strip(),
            "license": license_,
            "url": url,
            "melange_version": full_version,
            "config": path.name,
        }
        meta[name] = dict(base, name=name)

        for sub in doc.get("subpackages") or []:
            if not isinstance(sub, dict):
                continue
            sub_name = sub.get("name")
            if not sub_name:
                continue
            meta[sub_name] = dict(
                base,
                name=sub_name,
                description=(sub.get("description") or base["description"]).strip(),
            )
    return meta


def _license(pkg: dict) -> str:
    copyright_ = pkg.get("copyright") or []
    licenses = [c.get("license") for c in copyright_ if isinstance(c, dict) and c.get("license")]
    return " AND ".join(dict.fromkeys(licenses))


def _github_url(configs_dir: Path) -> str:
    # All packages are built from this repository; link back to it.
    return "https://github.com/metal3-community/ironic-packages"


def parse_apkindex(path: Path) -> list[dict]:
    """Parse an APKINDEX.tar.gz into a list of package records."""
    records: list[dict] = []
    with open(path, "rb") as fh:
        raw = fh.read()
    # APKINDEX.tar.gz may be a concatenation of gzip streams (signature +
    # index); the tar member named "APKINDEX" holds the records.
    data = _extract_apkindex_member(raw)
    if data is None:
        return records

    for block in data.decode("utf-8", "replace").split("\n\n"):
        block = block.strip()
        if not block:
            continue
        rec: dict[str, str] = {}
        for line in block.splitlines():
            if len(line) > 2 and line[1] == ":":
                rec[line[0]] = line[2:]
        if "P" in rec and "V" in rec:
            records.append(rec)
    return records


def _extract_apkindex_member(raw: bytes) -> bytes | None:
    # Each gzip stream starts with the magic bytes 1f 8b 08. Try each start
    # offset until one yields a tar containing an APKINDEX member.
    offsets = [i for i in range(len(raw) - 2) if raw[i] == 0x1F and raw[i + 1] == 0x8B and raw[i + 2] == 0x08]
    for off in offsets:
        try:
            with gzip.open(io.BytesIO(raw[off:]), "rb") as gz:
                buf = gz.read()
            with tarfile.open(fileobj=io.BytesIO(buf)) as tf:
                for member in tf.getmembers():
                    if member.name == "APKINDEX":
                        return tf.extractfile(member).read()
        except (OSError, tarfile.TarError):
            continue
    return None


def collect_availability(repo_dir: Path, distros: list[str], arches: list[str]) -> dict[str, list[dict]]:
    """Return {package_name: [ {distro, arch, version, size, file} ]}."""
    avail: dict[str, list[dict]] = {}
    for distro in distros:
        for arch in arches:
            index = repo_dir / distro / arch / "APKINDEX.tar.gz"
            if not index.is_file():
                continue
            for rec in parse_apkindex(index):
                name, version = rec["P"], rec["V"]
                filename = f"{name}-{version}.apk"
                entry = {
                    "distro": distro,
                    "arch": arch,
                    "version": version,
                    "size": int(rec.get("S", 0) or 0),
                    "file": f"{distro}/{arch}/{filename}",
                }
                avail.setdefault(name, []).append(entry)
    return avail


def merge(meta: dict[str, dict], avail: dict[str, list[dict]]) -> dict[str, dict]:
    packages: dict[str, dict] = {}
    for name in sorted(set(meta) | set(avail)):
        m = meta.get(name, {})
        versions = sorted(
            avail.get(name, []),
            key=lambda v: (v["distro"], v["arch"], v["version"]),
        )
        distinct = sorted({v["version"] for v in versions})
        latest = m.get("melange_version") or (distinct[-1] if distinct else "")
        packages[name] = {
            "name": name,
            "description": m.get("description", ""),
            "license": m.get("license", ""),
            "url": m.get("url", ""),
            "latest": latest,
            "distros": sorted({v["distro"] for v in versions}),
            "arches": sorted({v["arch"] for v in versions}),
            "versions": versions,
        }
    return packages


def write_data(site_dir: Path, packages: dict[str, dict]) -> None:
    data_dir = site_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    out = data_dir / "packages.yaml"
    out.write_text(yaml.safe_dump(packages, sort_keys=True, default_flow_style=False, allow_unicode=True))
    print(f"wrote {out} ({len(packages)} packages)")


def write_content(site_dir: Path, packages: dict[str, dict], distros: list[str], arches: list[str]) -> None:
    content = site_dir / "content"
    present: dict[str, set[str]] = {}
    for pkg in packages.values():
        for v in pkg["versions"]:
            present.setdefault(v["distro"], set()).add(v["arch"])

    for distro in distros:
        if distro not in present:
            continue
        ddir = content / distro
        ddir.mkdir(parents=True, exist_ok=True)
        _front_matter(ddir / "_index.md", {"title": distro, "distro": distro})
        for arch in sorted(present[distro]):
            adir = ddir / arch
            adir.mkdir(parents=True, exist_ok=True)
            _front_matter(
                adir / "_index.md",
                {"title": f"{distro} / {arch}", "distro": distro, "arch": arch},
            )


def _front_matter(path: Path, params: dict) -> None:
    body = yaml.safe_dump(params, default_flow_style=False, sort_keys=False).strip()
    path.write_text(f"---\n{body}\n---\n")


def link_static(repo_dir: Path, site_dir: Path, pubkey: Path | None) -> None:
    static = site_dir / "static"
    static.mkdir(parents=True, exist_ok=True)
    for src in repo_dir.rglob("*"):
        if not src.is_file():
            continue
        if src.name == "index.html":  # never publish stale hand-built indexes
            continue
        rel = src.relative_to(repo_dir)
        dst = static / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        _link_or_copy(src, dst)
    if pubkey and pubkey.is_file():
        _link_or_copy(pubkey, static / pubkey.name)


def _link_or_copy(src: Path, dst: Path) -> None:
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--configs-dir", type=Path, default=Path("."))
    ap.add_argument("--repository-dir", type=Path, default=Path("repository"))
    ap.add_argument("--site-dir", type=Path, default=Path("site"))
    ap.add_argument("--pubkey", type=Path, default=None, help="melange.rsa.pub to publish")
    ap.add_argument("--distros", default="alpine,wolfi")
    ap.add_argument("--arches", default="x86_64,aarch64")
    ap.add_argument("--skip-static", action="store_true", help="do not link package files into static/")
    args = ap.parse_args()

    distros = [d for d in args.distros.split(",") if d]
    arches = [a for a in args.arches.split(",") if a]

    meta = load_melange_metadata(args.configs_dir)
    avail = collect_availability(args.repository_dir, distros, arches)
    packages = merge(meta, avail)

    write_data(args.site_dir, packages)
    write_content(args.site_dir, packages, distros, arches)
    if not args.skip_static:
        link_static(args.repository_dir, args.site_dir, args.pubkey)

    built = sum(1 for p in packages.values() if p["versions"])
    print(f"metadata: {len(meta)} configs, availability: {built} published packages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
