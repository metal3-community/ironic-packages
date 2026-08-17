#!/usr/bin/env bash
# Resolve package versions for the pinned OpenStack release series.
#
# Everything is derived from a single pin: the OpenStack coordinated-release
# series (e.g. "2025.2") set in updatecli/values.yaml. Consumed by the
# updatecli manifests in updatecli/updatecli.d/.
#
# Subcommands:
#   series-name <series>              release-id -> deliverables dir (2025.2 -> flamingo)
#   deliverable <series> <name>       latest release of an OpenStack deliverable in the series
#   constraint  <series> <name>       exact pin from the series' upper-constraints.txt
#   driver-lib  <series> <pypi-name>  newest PyPI release satisfying ironic's
#                                     driver-requirements.txt range at the series' ironic version
#
# Requires: bash, curl, yq (mikefarah v4), python3 with the "packaging" module
# (driver-lib only).

set -euo pipefail

RELEASES_RAW="https://raw.githubusercontent.com/openstack/releases/master"
IRONIC_RAW="https://raw.githubusercontent.com/openstack/ironic"
CONSTRAINTS_URL="https://releases.openstack.org/constraints/upper"

CACHE_DIR="${TMPDIR:-/tmp}/ironic-packages-versions"
CACHE_TTL_MINUTES=60

die() { echo "openstack-version.sh: $*" >&2; exit 1; }

# Fetch a URL once per CACHE_TTL_MINUTES and print the local cache path, so a
# full updatecli run downloads each upstream file a single time.
fetch_cached() { # <url> <cache-file-name>
  local url="$1" out="$CACHE_DIR/$2"
  mkdir -p "$CACHE_DIR"
  if [ ! -s "$out" ] || [ -n "$(find "$out" -mmin +"$CACHE_TTL_MINUTES" 2>/dev/null)" ]; then
    curl -sSfL --retry 3 --max-time 60 "$url" -o "$out.tmp.$$" || die "failed to fetch $url"
    mv "$out.tmp.$$" "$out"
  fi
  printf '%s\n' "$out"
}

# Requirement names appear with inconsistent separators (oslo.i18n vs
# oslo-i18n vs oslo_i18n); build a regex that matches any separator style.
name_pattern() { printf '%s' "$1" | sed -E 's/[._-]+/[._-]/g'; }

series_name() { # <series>
  local f name
  f=$(fetch_cached "$RELEASES_RAW/data/series_status.yaml" "series_status.yaml")
  name=$(yq -r ".[] | select((.\"release-id\" | tostring) == \"$1\") | .name" "$f")
  [ -n "$name" ] && [ "$name" != "null" ] || die "unknown OpenStack series: $1"
  printf '%s\n' "$name"
}

deliverable() { # <series> <name>
  local dir f v
  dir=$(series_name "$1")
  f=$(fetch_cached "$RELEASES_RAW/deliverables/$dir/$2.yaml" "deliverable-$dir-$2.yaml")
  v=$(yq -r '.releases[-1].version' "$f")
  [ -n "$v" ] && [ "$v" != "null" ] || die "no releases for $2 in series $1 ($dir)"
  printf '%s\n' "$v"
}

constraint() { # <series> <name>
  local f v
  f=$(fetch_cached "$CONSTRAINTS_URL/$1" "upper-constraints-$1.txt")
  v=$(grep -iE "^$(name_pattern "$2")===" "$f" | head -n1 \
    | sed -E 's/^[^=]*===//; s/[;[:space:]].*$//')
  [ -n "$v" ] || die "$2 not found in $1 upper-constraints"
  printf '%s\n' "$v"
}

driver_lib() { # <series> <pypi-name>
  local iv f spec pj
  iv=$(deliverable "$1" ironic)
  f=$(fetch_cached "$IRONIC_RAW/$iv/driver-requirements.txt" "driver-requirements-$iv.txt")
  spec=$(grep -iE "^$(name_pattern "$2")([><=~!;[[:space:][]|$)" "$f" | head -n1 \
    | sed -E 's/#.*$//; s/;.*$//' | grep -oE '[><=~!].*' | tr -d '[:space:]' || true)
  pj=$(fetch_cached "https://pypi.org/pypi/$2/json" "pypi-$2.json")
  python3 - "$2" "$spec" "$pj" <<'PY'
import json
import sys

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

name, rawspec, path = sys.argv[1], sys.argv[2], sys.argv[3]
spec = SpecifierSet(rawspec)
with open(path) as fh:
    releases = json.load(fh)["releases"]

best = None
for ver, files in releases.items():
    if not files or all(f.get("yanked") for f in files):
        continue
    try:
        pv = Version(ver)
    except InvalidVersion:
        continue
    if pv.is_prerelease or not spec.contains(pv):
        continue
    if best is None or pv > best:
        best = pv

if best is None:
    sys.exit(f"no PyPI release of {name} satisfies '{rawspec}'")
print(best)
PY
}

cmd="${1:-}"
shift || true
case "$cmd" in
  series-name) [ $# -eq 1 ] || die "usage: series-name <series>"; series_name "$1" ;;
  deliverable) [ $# -eq 2 ] || die "usage: deliverable <series> <name>"; deliverable "$@" ;;
  constraint)  [ $# -eq 2 ] || die "usage: constraint <series> <name>"; constraint "$@" ;;
  driver-lib)  [ $# -eq 2 ] || die "usage: driver-lib <series> <pypi-name>"; driver_lib "$@" ;;
  *) die "usage: openstack-version.sh {series-name|deliverable|constraint|driver-lib} ..." ;;
esac
