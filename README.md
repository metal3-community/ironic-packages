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

Each `py3-*.yaml` tracks the latest release of its corresponding
[PyPI](https://pypi.org/) project via [updatecli](https://www.updatecli.io/):

1. [`scripts/gen-updatecli.py`](scripts/gen-updatecli.py) scans the
   `py3-*.yaml` configs and generates
   [`updatecli/updatecli.d/pypi.yaml`](updatecli/updatecli.d/pypi.yaml) — one
   `kind: pypi` source plus a `kind: yaml` target per package, keyed by the
   config filename (e.g. `py3-requests` → PyPI project `requests`; PyPI
   resolves dashed names under PEP 503, so `oslo-config` finds `oslo.config`).
1. `updatecli apply` rewrites each config's `package.version` to the latest
   PyPI release.

The [`updatecli.yaml`](.github/workflows/updatecli.yaml) workflow runs daily,
regenerates the manifest, and opens a single PR with the version bumps.

> **Note:** "latest from PyPI" does not guarantee that co-installed OpenStack
> packages (ironic, oslo.\*, keystoneauth1, …) remain mutually compatible —
> that is what OpenStack's
> [upper-constraints](https://releases.openstack.org/constraints/upper/2025.2)
> exist to enforce. Review version bumps before merging.

To run the flow locally (requires `updatecli` and Python with `pyyaml`):

```bash
python3 scripts/gen-updatecli.py
updatecli diff  --config updatecli/updatecli.d   # preview
updatecli apply --config updatecli/updatecli.d   # rewrite versions
```

To add a package, drop a new `py3-<name>.yaml` in and rerun
`gen-updatecli.py`; if its PyPI project name is not simply `<name>`, add an
entry to `PYPI_NAME_OVERRIDES` in the script.

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
