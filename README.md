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

Package versions are managed with [updatecli](https://www.updatecli.io/) and
are pinned to a single **OpenStack release series** (set in
[`updatecli/values.yaml`](updatecli/values.yaml)), so the whole package set
stays on versions that OpenStack releases and tests together:

- **Services** (`py3-ironic`, `py3-ironic-python-agent`,
  `py3-ironic-prometheus-exporter`): latest release of each deliverable in the
  pinned series, from [openstack/releases](https://opendev.org/openstack/releases).
- **Libraries** (`py3-oslo-*`, `py3-sushy`, etc.): exact pins from the series'
  [`upper-constraints.txt`](https://releases.openstack.org/constraints/upper/2025.2).
- **Ironic driver libraries** (`py3-proliantutils`, `py3-python-scciclient`,
  `py3-sushy-oem-idrac`): newest PyPI release satisfying ironic's
  `driver-requirements.txt` range at the series' ironic version.

The managed package *set* is itself derived from ironic's dependency graph:
[`scripts/ironic-deps.py`](scripts/ironic-deps.py) recursively walks PyPI
`requires_dist` metadata from the packaged services (each node at its
upper-constraints version) to compute the full transitive closure. Its `sync`
command regenerates the `dependencies:` list in `updatecli/values.yaml` and
scaffolds a `py3-<name>.yaml` for any new transitive dependency that is not
listed in `externalPackages` (the human-curated list of packages provided by
the upstream Alpine/Wolfi repositories); its `report` command publishes the
coverage report in the workflow run summary, including local packages that
have dropped out of the graph.

The [`updatecli.yaml`](.github/workflows/updatecli.yaml) workflow runs daily,
syncs the package set, applies the version pins, and opens a single PR with
the coordinated result. Scaffolded packages are starting points — review the
license and test import before merging.

To move the whole package set to a new OpenStack release, change
`openstack.series` in `updatecli/values.yaml` (e.g. `"2025.2"` → `"2026.1"`)
and let the workflow (or a local run) do the rest.

To run the sync locally (requires `updatecli`, `curl`, `yq`, and Python with
the `packaging` module):

```bash
updatecli diff --config updatecli/updatecli.d --values updatecli/values.yaml
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
