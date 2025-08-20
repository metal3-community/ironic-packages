#!/usr/bin/env bash

# Handle keyboard interrupt (Ctrl+C) gracefully
cleanup() {
    echo ""
    echo "Build interrupted by user. Cleaning up..."
    exit 130
}

# Set trap to catch SIGINT (Ctrl+C)
trap cleanup SIGINT

docker run --rm -v "${PWD}":/work docker.io/chainguard/melange keygen

for p in py3-*.yaml uwsgi.yaml; do
  # Skip if the file doesn't exist (in case uwsgi.yaml doesn't exist)
  if [[ ! -f "$p" ]]; then
    continue
  fi
  
  echo "Building package: $p"
  GOFLAGS="" GOTOOLCHAIN=local docker run --rm --privileged --platform linux/arm64 -v "${PWD}:/work" \
    docker.io/chainguard/melange:latest build "${p}" \
    --arch=x86_64,aarch64 \
    --pipeline-dir /work/pipelines \
    --workspace-dir /work \
    --out-dir /work/packages \
    --log-level debug \
    --signing-key melange.rsa \
    --repository-append https://packages.wolfi.dev/os \
    --keyring-append https://packages.wolfi.dev/os/wolfi-signing.rsa.pub \
    || { exit 1; }
  echo "Completed package: $p"
done

echo "All builds completed successfully!"
