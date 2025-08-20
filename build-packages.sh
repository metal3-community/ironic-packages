#!/usr/bin/env bash

# Build script for Ironic APK packages
# Usage: ./build-packages.sh [package-name] [arch] [distro]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Default values
PACKAGE="${1:-all}"
ARCH="${2:-x86_64}"
DISTRO="${3:-wolfi}"

# Supported architectures and distributions
SUPPORTED_ARCHS=("x86_64" "aarch64")
SUPPORTED_DISTROS=("alpine" "wolfi")

# Validate inputs
if [[ ! " ${SUPPORTED_ARCHS[*]} " =~ \ ${ARCH}\  ]]; then
    echo "Error: Unsupported architecture '${ARCH}'"
    echo "Supported: ${SUPPORTED_ARCHS[*]}"
    exit 1
fi

if [[ ! " ${SUPPORTED_DISTROS[*]} " =~ \ ${DISTRO}\  ]]; then
    echo "Error: Unsupported distribution '${DISTRO}'"
    echo "Supported: ${SUPPORTED_DISTROS[*]}"
    exit 1
fi

# Check if melange is installed
if ! command -v melange &> /dev/null; then
    echo "Error: melange is not installed"
    echo "Please install melange from: https://github.com/chainguard-dev/melange"
    exit 1
fi

# Generate signing key if it doesn't exist
if [[ ! -f "local-melange.rsa" ]]; then
    echo "Generating signing key..."
    melange keygen local-melange.rsa
fi

# Create packages directory
mkdir -p "packages/${ARCH}"

# Determine repository and keyring based on distro
case "$DISTRO" in
    alpine)
        REPO_URL="https://dl-cdn.alpinelinux.org/alpine/edge/main"
        KEYRING_URL="https://alpinelinux.org/keys/alpine-devel@lists.alpinelinux.org-4a6a0840.rsa.pub"
        ;;
    wolfi)
        REPO_URL="https://packages.wolfi.dev/os"
        KEYRING_URL="https://packages.wolfi.dev/os/wolfi-signing.rsa.pub"
        ;;
esac

# Download keyring file
KEYRING_FILE="$(mktemp)"
curl -sL "$KEYRING_URL" > "$KEYRING_FILE"
trap 'rm -f "$KEYRING_FILE"' EXIT

# Function to build a package
build_package() {
    local package="$1"
    local yaml_file="${package}.yaml"
    
    if [[ ! -f "$yaml_file" ]]; then
        echo "Warning: $yaml_file not found, skipping"
        return 0
    fi
    
    echo "Building $package for $ARCH on $DISTRO..."
    
    # Get SOURCE_DATE_EPOCH from git if possible
    SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct --follow "$yaml_file" 2>/dev/null || date +%s)
    export SOURCE_DATE_EPOCH
    
    melange build "$yaml_file" \
        --arch "$ARCH" \
        --signing-key local-melange.rsa \
        --repository-append "$(pwd)/packages" \
        --keyring-append local-melange.rsa.pub \
        --repository-append "$REPO_URL" \
        --keyring-append "$KEYRING_FILE" \
        --env-file "build-${ARCH}.env" \
        --namespace "$DISTRO" \
        --pipeline-dir ./pipelines \
        --out-dir ./packages \
        --log-level info \
        --generate-index false || {
            echo "Failed to build $package" >&2
            return 1
        }
}

# Build packages
if [[ "$PACKAGE" == "all" ]]; then
    echo "Building all packages for $ARCH on $DISTRO..."
    for yaml_file in py3-*.yaml; do
        if [[ -f "$yaml_file" ]]; then
            package=$(basename "$yaml_file" .yaml)
            build_package "$package"
        fi
    done
else
    build_package "$PACKAGE"
fi

# Generate APK index
echo "Generating APK index..."
if [[ -d "packages/${ARCH}" ]] && ls "packages/${ARCH}"/*.apk >/dev/null 2>&1; then
    cd "packages/${ARCH}"
    melange index \
        --signing-key "../../local-melange.rsa" \
        --output APKINDEX.tar.gz \
        *.apk || true
    cd - >/dev/null
fi

echo "Build completed successfully!"
echo "Packages are available in: packages/${ARCH}/"
echo ""
echo "To use the repository locally:"
echo "  echo \"$(pwd)/packages\" >> /etc/apk/repositories"
echo "  apk update"