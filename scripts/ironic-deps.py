#!/usr/bin/env python3
"""Manage this repo's package set from ironic's fully-resolved dependency lock.

The dependency set and all versions are enumerated by a standard Python
resolver rather than hand-walked metadata:

  1. ``lock`` regenerates pyproject.toml — the packaged services pinned at
     their versions for the OpenStack series in updatecli/values.yaml (from
     openstack/releases deliverables) plus ironic's driver-requirements.txt
     ranges — then resolves it with ``uv pip compile``, constrained by the
     series' upper-constraints.txt, into requirements.lock. The lock is the
     single version authority: every transitive dependency at an exact
     version, proven mutually compatible by the resolver and matching what
     OpenStack tests together.

  2. ``sync`` makes the repo match the lock: regenerates the (GENERATED)
     ``dependencies:`` list in updatecli/values.yaml, and scaffolds a
     py3-<name>.yaml for any locked package that should be packaged here but
     has no definition yet. Lock members listed under ``externalPackages`` in
     values.yaml (human-curated) are left to the upstream distro repos.

  3. ``report`` prints a markdown coverage report (used in the update PR's
     workflow summary): which locked packages are packaged here, which come
     from upstream Alpine/Wolfi, and which local py3-*.yaml files are no
     longer part of the graph.

Usage: ironic-deps.py {lock|sync|report} [series]
(series defaults to the pin in updatecli/values.yaml)

Requires: python3 with "packaging"; ``lock`` additionally needs uv, curl and
yq (via scripts/openstack-version.sh).
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

REPO_ROOT = Path(__file__).resolve().parent.parent
VALUES_YAML = REPO_ROOT / "updatecli" / "values.yaml"
PYPROJECT = REPO_ROOT / "pyproject.toml"
LOCK_FILE = REPO_ROOT / "requirements.lock"
VERSION_SH = REPO_ROOT / "scripts" / "openstack-version.sh"
SERVICES = ["ironic", "ironic-python-agent", "ironic-prometheus-exporter"]

LICENSE_CLASSIFIERS = {
    "License :: OSI Approved :: Apache Software License": "Apache-2.0",
    "License :: OSI Approved :: MIT License": "MIT",
    "License :: OSI Approved :: BSD License": "BSD-3-Clause",
    "License :: OSI Approved :: ISC License (ISCL)": "ISC",
    "License :: OSI Approved :: Python Software Foundation License": "PSF-2.0",
    "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)": "LGPL-3.0-only",
    "License :: OSI Approved :: GNU Lesser General Public License v2 (LGPLv2)": "LGPL-2.0-only",
    "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
}

_http_cache: dict[str, dict | None] = {}


def http_json(url: str) -> dict | None:
    if url not in _http_cache:
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                _http_cache[url] = json.load(resp)
        except Exception:
            _http_cache[url] = None
    return _http_cache[url]


def resolve(*args: str) -> str:
    return subprocess.run(
        ["bash", str(VERSION_SH), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def values_list(key: str) -> list[str]:
    out = subprocess.run(
        ["yq", "-r", f".openstack.{key}[]", str(VALUES_YAML)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    return [canonicalize_name(name) for name in out]


def values_scalar(key: str) -> str:
    return subprocess.run(
        ["yq", "-r", f".openstack.{key}", str(VALUES_YAML)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def pinned_series() -> str:
    match = re.search(r'^\s*series:\s*"?([0-9.]+)"?\s*$', VALUES_YAML.read_text(), re.M)
    if not match:
        sys.exit("could not read openstack.series from updatecli/values.yaml")
    return match.group(1)


def driver_requirements(ironic_version: str) -> list[str]:
    """Ironic's driver-requirements.txt as normalized requirement strings."""
    url = (
        "https://raw.githubusercontent.com/openstack/ironic/"
        f"{ironic_version}/driver-requirements.txt"
    )
    with urllib.request.urlopen(url, timeout=60) as resp:
        text = resp.read().decode()
    reqs = []
    for line in text.splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        try:
            reqs.append(str(Requirement(line)))
        except InvalidRequirement:
            continue
    return reqs


def read_lock() -> dict[str, str]:
    if not LOCK_FILE.exists():
        sys.exit("requirements.lock not found — run 'ironic-deps.py lock' first")
    locked = {}
    for line in LOCK_FILE.read_text().splitlines():
        match = re.match(r"^([A-Za-z0-9._-]+)==([^\s;]+)", line.strip())
        if match:
            locked[canonicalize_name(match.group(1))] = match.group(2)
    return locked


def local_packages() -> dict[str, Path]:
    return {
        p.name[len("py3-") : -len(".yaml")]: p
        for p in sorted(REPO_ROOT.glob("py3-*.yaml"))
    }


# --- lock ---------------------------------------------------------------------

PYPROJECT_TEMPLATE = """\
# GENERATED — do not edit by hand: 'scripts/ironic-deps.py lock' regenerates
# this file for the OpenStack series pinned in updatecli/values.yaml
# (services at their openstack/releases versions, plus ironic's
# driver-requirements.txt ranges). 'uv pip compile', constrained by the
# series' upper-constraints.txt, resolves it into requirements.lock — the
# version authority for every py3-*.yaml package in this repo.
[project]
name = "ironic-packages-lock"
version = "0.0.0"
description = "Dependency lock meta-project for the ironic-packages APK set (not installable)"
requires-python = ">={python}"
dependencies = [
{dependencies}
]
"""


def cmd_lock(series: str) -> None:
    python = values_scalar("lockPython")
    service_versions = {
        name: resolve("deliverable", series, name) for name in SERVICES
    }
    deps = [f"{name}=={version}" for name, version in service_versions.items()]
    deps += driver_requirements(service_versions["ironic"])

    PYPROJECT.write_text(
        PYPROJECT_TEMPLATE.format(
            python=python,
            dependencies="\n".join(f'  "{dep}",' for dep in deps),
        )
    )
    print(
        f"pyproject.toml: {len(deps)} root requirements "
        f"(ironic {service_versions['ironic']})"
    )

    constraints_url = f"https://releases.openstack.org/constraints/upper/{series}"
    with urllib.request.urlopen(constraints_url, timeout=60) as resp:
        constraints = resp.read()
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        tmp.write(constraints)
        constraints_file = tmp.name
    try:
        subprocess.run(
            [
                "uv",
                "pip",
                "compile",
                str(PYPROJECT),
                "--constraint",
                constraints_file,
                "--output-file",
                str(LOCK_FILE),
                "--python-version",
                python,
                "--python-platform",
                "linux",
                "--no-header",
                "--no-annotate",
            ],
            check=True,
            cwd=REPO_ROOT,
        )
    finally:
        Path(constraints_file).unlink(missing_ok=True)
    print(f"requirements.lock: {len(read_lock())} packages")


# --- scaffolding ------------------------------------------------------------

WHEEL_PIPELINE = """\
environment:
  contents:
    packages:
      - busybox
      - wget
      - ca-certificates-bundle
      - python3
      - py3-pip

pipeline:
  - runs: |
      wget -T5 --tries=5 https://files.pythonhosted.org/packages/py3/${{{{vars.prefix}}}}/${{{{vars.package}}}}/${{{{vars.file}}}}-${{{{package.version}}}}-py3-none-any.whl
      pip install --no-deps --no-cache-dir --prefix=/usr --root=${{{{targets.destdir}}}} ${{{{vars.file}}}}-${{{{package.version}}}}-py3-none-any.whl
"""

SDIST_PIPELINE = """\
environment:
  contents:
    packages:
      - busybox
      - build-base
      - wget
      - ca-certificates-bundle
      - python3
      - python3-dev
      - py3-pip
      - py3-build

pipeline:
  - runs: |
      bn=${{{{vars.file}}}}-${{{{package.version}}}}.tar.gz
      wget -T5 --tries=5 https://files.pythonhosted.org/packages/source/${{{{vars.prefix}}}}/${{{{vars.package}}}}/$bn
      tar -xz --strip-components=1 -C . -f $bn
      rm $bn
      pip install --no-deps --no-cache-dir --prefix=/usr --root=${{{{targets.destdir}}}} .
"""

SCAFFOLD = """\
# yaml-language-server: $schema=https://github.com/chainguard-dev/melange/raw/refs/heads/main/pkg/config/schema.json
package:
  name: py3-{name}
  description: {description}
  version: {version}
  epoch: 0
  copyright:
    - license: {license}
  dependencies:
    provider-priority: 0

var-transforms:
  - from: ${{{{package.name}}}}
    match: ^py3-([a-z]).+$
    replace: $1
    to: prefix
  - from: ${{{{package.name}}}}
    match: ^py3-(.+)$
    replace: $1
    to: package
  - from: ${{{{vars.package}}}}
    match: "-"
    replace: "_"
    to: file
  - from: ${{{{vars.package}}}}
    match: "-"
    replace: "."
    to: import

{pipeline}
test:
  pipeline:
    - uses: python/import
      with:
        imports: |
          import ${{{{vars.import}}}}

update:
  enabled: true
"""


def yaml_scalar(text: str) -> str:
    text = " ".join(text.split())
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return json.dumps(text)  # would otherwise parse as a YAML number
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ,.()/+_-]*", text):
        return text
    return json.dumps(text)


def spdx_license(info: dict) -> tuple[str, bool]:
    """Best-effort SPDX id from PyPI metadata; second value = needs review."""
    expr = (info.get("license_expression") or "").strip()
    if expr:
        return expr, False
    for classifier in info.get("classifiers") or []:
        if classifier in LICENSE_CLASSIFIERS:
            return LICENSE_CLASSIFIERS[classifier], False
    lic = (info.get("license") or "").strip()
    if lic and "\n" not in lic and len(lic) <= 30:
        return lic, True
    return "Apache-2.0", True


def scaffold(cname: str, version: str) -> list[str]:
    """Write py3-<cname>.yaml; returns human-readable notes."""
    notes = []
    data = http_json(f"https://pypi.org/pypi/{cname}/json")
    info = data["info"] if data else {}
    files = (data or {}).get("releases", {}).get(version) or []
    filenames = {f["filename"] for f in files}

    file_var = re.sub(r"[-_.]+", "_", cname)
    wheel = f"{file_var}-{version}-py3-none-any.whl"
    if wheel in filenames:
        pipeline = WHEEL_PIPELINE
    elif any(f.get("packagetype") == "sdist" for f in files):
        pipeline = SDIST_PIPELINE
        notes.append(f"no pure-python wheel for {cname}=={version}; used sdist build")
    else:
        pipeline = WHEEL_PIPELINE
        notes.append(
            f"TODO: no wheel or sdist found for {cname}=={version}; verify pipeline"
        )

    license_id, review = spdx_license(info)
    if review:
        notes.append(f"TODO: verify license for {cname} (guessed {license_id})")

    body = SCAFFOLD.format(
        name=cname,
        description=yaml_scalar(info.get("summary") or cname),
        version=yaml_scalar(version),
        license=license_id,
        pipeline=pipeline.format(),
    )
    if notes:
        body = "".join(f"# {note}\n" for note in notes) + body
    (REPO_ROOT / f"py3-{cname}.yaml").write_text(body)
    return notes


# --- values.yaml editing ----------------------------------------------------


def rewrite_dependencies(names: list[str]) -> None:
    lines = VALUES_YAML.read_text().splitlines(keepends=True)
    out: list[str] = []
    index, replaced = 0, False
    while index < len(lines):
        line = lines[index]
        out.append(line)
        index += 1
        if re.match(r"^  dependencies:\s*$", line):
            while index < len(lines) and re.match(r"^    - ", lines[index]):
                index += 1
            out.extend(f"    - {name}\n" for name in names)
            replaced = True
    if not replaced:
        sys.exit("could not find 'dependencies:' list in updatecli/values.yaml")
    VALUES_YAML.write_text("".join(out))


# --- commands ----------------------------------------------------------------


def classify():
    locked = read_lock()
    external = set(values_list("externalPackages"))
    driver_libs = set(values_list("driverLibraries"))
    managed = {
        cname
        for cname in locked
        if cname not in external and cname not in driver_libs and cname not in SERVICES
    }
    return locked, managed, external


def cmd_sync() -> None:
    locked, managed, external = classify()
    local = local_packages()

    created = []
    for cname in sorted(managed - set(local)):
        notes = scaffold(cname, locked[cname])
        created.append(cname)
        print(f"scaffolded py3-{cname}.yaml ({locked[cname]})")
        for note in notes:
            print(f"  {note}")

    old = set(values_list("dependencies"))
    new = sorted(managed)
    rewrite_dependencies(new)
    for cname in sorted(set(new) - old):
        print(f"dependencies: added {cname}")
    for cname in sorted(old - set(new)):
        reason = (
            "moved to externalPackages"
            if cname in external
            else "no longer in the dependency lock"
        )
        print(f"dependencies: removed {cname} ({reason})")

    for cname in sorted(external - set(locked)):
        print(f"note: externalPackages entry '{cname}' is no longer in the lock")
    for name in sorted(set(local) - set(locked) - set(SERVICES)):
        print(
            f"note: py3-{name}.yaml is not in the dependency lock (consider removing)"
        )
    if not created and set(new) == old:
        print("dependency set already in sync")


def cmd_report(series: str) -> None:
    locked, _, _ = classify()
    local = local_packages()

    packaged, external_rows = [], []
    for cname in sorted(locked):
        if cname in local:
            packaged.append(f"- ✅ `{cname}` {locked[cname]} → `py3-{cname}.yaml`")
        else:
            external_rows.append(f"- ⬜ `{cname}` {locked[cname]}")
    unused = sorted(set(local) - set(locked))

    print(
        f"### Ironic {locked.get('ironic', '?')} (OpenStack {series}) "
        "dependency lock coverage"
    )
    print()
    print(
        "Full dependency set resolved by uv from pyproject.toml "
        f"({', '.join(SERVICES)} plus ironic's driver-requirements.txt), "
        "constrained by the series' upper-constraints.txt: "
        f"**{len(locked)} packages** in requirements.lock."
    )
    print()
    print(f"#### Packaged in this repo ({len(packaged)})")
    print()
    print("\n".join(packaged))
    print()
    print(f"#### Expected from upstream Alpine/Wolfi repos ({len(external_rows)})")
    print()
    print("\n".join(external_rows))
    print()
    if unused:
        print(f"#### ⚠️ Local packages not in the dependency lock ({len(unused)})")
        print()
        print("These py3-*.yaml files are not reachable from ironic's requirements")
        print("and may no longer be needed:")
        print()
        for name in unused:
            print(f"- `py3-{name}.yaml`")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["lock", "sync", "report"])
    parser.add_argument("series", nargs="?", default=None)
    args = parser.parse_args()
    series = args.series or pinned_series()
    if args.command == "lock":
        cmd_lock(series)
    elif args.command == "sync":
        cmd_sync()
    else:
        cmd_report(series)


if __name__ == "__main__":
    main()
