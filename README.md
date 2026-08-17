# Ironic Image

[![Build and Publish APK Repository](https://github.com/metal3-community/ironic-packages/actions/workflows/build-and-publish.yaml/badge.svg)](https://github.com/metal3-community/ironic-packages/actions/workflows/build-and-publish.yaml)

Container image to run OpenStack Ironic as part of Metal³

## APK Repository

This repository automatically builds and publishes APK packages for OpenStack Ironic and its dependencies. The packages are available for both Alpine Linux and Wolfi distributions.

### Repository URLs

| Distribution | Repository URL                                              |
| ------------ | ----------------------------------------------------------- |
| Alpine Linux | `https://metal3-community.github.io/ironic-packages/alpine` |
| Wolfi        | `https://metal3-community.github.io/ironic-packages/wolfi`  |

### Usage

#### Alpine Linux

Add the repository to your APK configuration:

```bash
echo "https://metal3-community.github.io/ironic-packages/alpine/x86_64" >> /etc/apk/repositories
apk update
apk add py3-ironic
```

#### Wolfi

For Wolfi-based containers or systems:

```bash
echo "https://metal3-community.github.io/ironic-packages/wolfi/x86_64" >> /etc/apk/repositories
apk update
apk add py3-ironic
```

### Available Packages

The repository includes the following Python packages optimized for Ironic:

- `py3-ironic` - OpenStack Bare Metal Provisioning service
- `py3-ironic-lib` - Ironic common library
- `py3-python-ironicclient` - Python client for Ironic API
- `py3-sushy` - Redfish library for Ironic
- OpenStack Oslo libraries (`py3-oslo-*`)
- Various Python dependencies required by Ironic

### Package Building

Packages are automatically built using [Melange](https://github.com/chainguard-dev/melange) when changes are detected in the YAML package definitions. The build process:

1. **Change Detection**: Monitors changes to `*.yaml` files and related build configuration
1. **Multi-Architecture Build**: Builds packages for both x86_64 and aarch64 architectures
1. **Multi-Distribution**: Creates packages for both Alpine Linux and Wolfi
1. **Repository Publishing**: Publishes the built packages to GitHub Pages with proper APK index files

### Automated Package Updates

All package versions derive from a single pin — the **OpenStack release
series** in [`updatecli/values.yaml`](updatecli/values.yaml) — through a
fully-resolved dependency lock:

1. [`scripts/ironic-deps.py`](scripts/ironic-deps.py) `lock` regenerates
   [`pyproject.toml`](pyproject.toml): the packaged services pinned at their
   latest release for the series (from
   [openstack/releases](https://opendev.org/openstack/releases)) plus
   ironic's `driver-requirements.txt` ranges. `uv pip compile`, constrained
   by the series'
   [`upper-constraints.txt`](https://releases.openstack.org/constraints/upper/2025.2),
   resolves it into [`requirements.lock`](requirements.lock) — the complete
   transitive dependency set at exact versions, proven mutually compatible
   by a real resolver and matching what OpenStack tests together.
1. `ironic-deps.py sync` makes the repo match the lock: it regenerates the
   `dependencies:` list in `updatecli/values.yaml` and scaffolds a
   `py3-<name>.yaml` for any locked package not listed in `externalPackages`
   (the human-curated list of packages provided by the upstream Alpine/Wolfi
   repositories).
1. [updatecli](https://www.updatecli.io/) syncs every `py3-*.yaml` to its
   version in the committed lock (offline — no network at apply time).

The [`updatecli.yaml`](.github/workflows/updatecli.yaml) workflow runs daily
and opens a single PR with the coordinated result, including the
`pyproject.toml`/`requirements.lock` diff for review; `ironic-deps.py report`
publishes a coverage report in the run summary. Scaffolded packages are
starting points — review the license and test import before merging.

To move the whole package set to a new OpenStack release, change
`openstack.series` in `updatecli/values.yaml` (e.g. `"2025.2"` → `"2026.1"`)
and let the workflow (or a local run) do the rest. `openstack.lockPython`
should track the Python version shipped by the target images, since
environment markers can change the resolved set.

To run the full flow locally (requires `uv`, `updatecli`, `curl`, `yq`, and
Python with the `packaging` module):

```bash
python3 scripts/ironic-deps.py lock
python3 scripts/ironic-deps.py sync
updatecli apply --config updatecli/updatecli.d --values updatecli/values.yaml
```

### Manual Building

To build packages locally:

```bash
# Generate signing key
make local-melange.rsa

# Build a specific package
make package/py3-ironic

# Build for specific architecture
ARCH=aarch64 make package/py3-ironic
```

## Contributing

When adding or modifying packages:

1. Update the corresponding `.yaml` file in the repository root
1. Ensure the package follows the existing conventions
1. Test the build locally before submitting a PR
1. The CI will automatically build and publish changes merged to main

## License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.
