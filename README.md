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

The repository includes comprehensive automation for keeping package definitions up to date:

- **Scheduled Updates**: GitHub Actions automatically check for new upstream versions twice daily
- **Renovate Integration**: Renovate bot monitors dependencies and creates update PRs
- **Auto-Building**: Updated packages are automatically built and published when PRs are merged
- **Manual Tools**: Scripts available for local testing and manual updates

See [`scripts/README.md`](scripts/README.md) for detailed information about the automation system.

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
