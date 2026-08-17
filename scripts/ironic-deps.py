#!/usr/bin/env python3
"""Manage this repo's package set from ironic's full dependency graph.

Recursively walks PyPI ``requires_dist`` metadata starting from the services
packaged here (ironic, ironic-python-agent, ironic-prometheus-exporter, at
their pinned-series versions) plus ironic's driver-requirements.txt, to
discover the complete transitive dependency set. Each node is inspected at
the version pinned by the series' upper-constraints.txt, so the graph matches
what OpenStack actually tests together; requires_dist is only used to learn
*which* packages are required, never to choose versions.

Subcommands:

  report [series]   Print a markdown report (used in the update PR's workflow
                    summary): which transitive dependencies are packaged here,
                    which come from upstream Alpine/Wolfi, and which local
                    py3-*.yaml files are no longer part of the graph.

  sync [series]     Make the repo match the graph:
                      - regenerate the (GENERATED) ``dependencies:`` list in
                        updatecli/values.yaml from the closure, and
                      - scaffold a py3-<name>.yaml for any closure member that
                        should be packaged here but has no definition yet.
                    Closure members listed under ``externalPackages`` in
                    values.yaml (human-curated) are left to the upstream
                    distro repos. New closure members without an
                    upper-constraints pin are warned about, never scaffolded.

Requires: python3 with "packaging", plus scripts/openstack-version.sh
(curl, yq).
"""

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

REPO_ROOT = Path(__file__).resolve().parent.parent
VALUES_YAML = REPO_ROOT / "updatecli" / "values.yaml"
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


def pinned_series() -> str:
    match = re.search(r'^\s*series:\s*"?([0-9.]+)"?\s*$', VALUES_YAML.read_text(), re.M)
    if not match:
        sys.exit("could not read openstack.series from updatecli/values.yaml")
    return match.group(1)


def upper_constraints(series: str) -> dict[str, str]:
    url = f"https://releases.openstack.org/constraints/upper/{series}"
    with urllib.request.urlopen(url, timeout=60) as resp:
        text = resp.read().decode()
    pins = {}
    for line in text.splitlines():
        match = re.match(r"^([A-Za-z0-9._-]+)===([^;\s]+)", line.strip())
        if match:
            pins.setdefault(canonicalize_name(match.group(1)), match.group(2))
    return pins


def driver_requirement_names(ironic_version: str) -> list[str]:
    url = (
        "https://raw.githubusercontent.com/openstack/ironic/"
        f"{ironic_version}/driver-requirements.txt"
    )
    with urllib.request.urlopen(url, timeout=60) as resp:
        text = resp.read().decode()
    names = []
    for line in text.splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        try:
            names.append(canonicalize_name(Requirement(line).name))
        except InvalidRequirement:
            continue
    return names


def requires_dist(name: str, version: str | None) -> list[str]:
    url = (
        f"https://pypi.org/pypi/{name}/{version}/json"
        if version
        else f"https://pypi.org/pypi/{name}/json"
    )
    data = http_json(url)
    if data is None and version is not None:
        data = http_json(f"https://pypi.org/pypi/{name}/json")
    if data is None:
        return []
    return data["info"].get("requires_dist") or []


def wanted(req: Requirement, extras: frozenset[str]) -> bool:
    if req.marker is None:
        return True
    env = default_environment()
    return any(
        req.marker.evaluate({**env, "extra": extra}) for extra in ({""} | extras)
    )


def walk(seeds: list[tuple[str, str | None, frozenset[str]]], pins: dict[str, str]):
    """BFS over requires_dist; returns {canonical-name: version-or-None}."""
    resolved: dict[str, str | None] = {}
    seen_with_extras: set[tuple[str, frozenset[str]]] = set()
    queue = list(seeds)
    while queue:
        name, version, extras = queue.pop()
        cname = canonicalize_name(name)
        if (cname, extras) in seen_with_extras:
            continue
        seen_with_extras.add((cname, extras))
        resolved.setdefault(cname, version)
        for spec in requires_dist(cname, version):
            try:
                req = Requirement(spec)
            except InvalidRequirement:
                continue
            if not wanted(req, extras):
                continue
            child = canonicalize_name(req.name)
            queue.append((child, pins.get(child), frozenset(req.extras)))
    return resolved


def compute_closure(series: str, pins: dict[str, str]):
    service_versions = {name: resolve("deliverable", series, name) for name in SERVICES}
    driver_names = driver_requirement_names(service_versions["ironic"])
    seeds: list[tuple[str, str | None, frozenset[str]]] = [
        (name, version, frozenset()) for name, version in service_versions.items()
    ]
    seeds += [(name, pins.get(name), frozenset()) for name in driver_names]
    return service_versions, walk(seeds, pins)


def local_packages() -> dict[str, Path]:
    return {
        p.name[len("py3-") : -len(".yaml")]: p
        for p in sorted(REPO_ROOT.glob("py3-*.yaml"))
    }


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
    provider-priority: "0"
  checks: {}
  cpe: {}

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
  environment: {}
  pipeline:
    - uses: python/import
      with:
        imports: |
          import ${{{{vars.import}}}}

update:
  enabled: true

capabilities: {}
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


def classify(series: str):
    pins = upper_constraints(series)
    service_versions, closure = compute_closure(series, pins)
    external = set(values_list("externalPackages"))
    driver_libs = set(values_list("driverLibraries"))
    managed = {
        cname
        for cname in closure
        if cname not in external
        and cname not in driver_libs
        and cname not in SERVICES
        and cname in pins
    }
    unmanageable = {
        cname
        for cname in closure
        if cname not in external
        and cname not in driver_libs
        and cname not in SERVICES
        and cname not in pins
    }
    return pins, service_versions, closure, managed, unmanageable, external


def cmd_sync(series: str) -> None:
    pins, _, closure, managed, unmanageable, external = classify(series)
    local = local_packages()

    created = []
    for cname in sorted(managed - set(local)):
        notes = scaffold(cname, pins[cname])
        created.append(cname)
        print(f"scaffolded py3-{cname}.yaml ({pins[cname]})")
        for note in notes:
            print(f"  {note}")

    old = set(values_list("dependencies"))
    new = sorted(managed)
    rewrite_dependencies(new)
    for cname in sorted(set(new) - old):
        print(f"dependencies: added {cname}")
    for cname in sorted(old - set(new)):
        if cname in external:
            reason = "moved to externalPackages"
        elif cname in closure:
            reason = "no upper-constraints pin"
        else:
            reason = "no longer in the dependency graph"
        print(f"dependencies: removed {cname} ({reason})")

    for cname in sorted(unmanageable):
        print(
            f"WARNING: {cname} is in the dependency graph but has no "
            "upper-constraints pin and is not in externalPackages; "
            "add it to externalPackages or package it manually"
        )
    for cname in sorted(external - set(closure)):
        print(f"note: externalPackages entry '{cname}' is no longer in the graph")
    orphans = sorted(
        name
        for name in local
        if name not in closure and name not in SERVICES
    )
    for name in orphans:
        print(f"note: py3-{name}.yaml is not in the dependency graph (consider removing)")
    if not created and set(new) == old:
        print("dependency set already in sync")


def cmd_report(series: str) -> None:
    pins, service_versions, closure, _, _, _ = classify(series)
    local = local_packages()

    packaged, external_rows = [], []
    for cname in sorted(closure):
        version = closure[cname] or "unpinned (not in upper-constraints)"
        if cname in local:
            packaged.append(f"- ✅ `{cname}` {version} → `py3-{cname}.yaml`")
        else:
            external_rows.append(f"- ⬜ `{cname}` {version}")
    unused = sorted(name for name in local if name not in closure)

    print(
        f"### Ironic {service_versions['ironic']} (OpenStack {series}) "
        "dependency graph coverage"
    )
    print()
    print(
        f"Transitive closure of `requires_dist` for {', '.join(SERVICES)} and "
        "ironic's driver-requirements.txt, at upper-constraints versions: "
        f"**{len(closure)} packages**."
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
        print(f"#### ⚠️ Local packages not in the dependency graph ({len(unused)})")
        print()
        print("These py3-*.yaml files are not reachable from ironic's requirements")
        print("and may no longer be needed:")
        print()
        for name in unused:
            print(f"- `py3-{name}.yaml`")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["report", "sync"])
    parser.add_argument("series", nargs="?", default=None)
    args = parser.parse_args()
    series = args.series or pinned_series()
    if args.command == "report":
        cmd_report(series)
    else:
        cmd_sync(series)


if __name__ == "__main__":
    main()
