#!/usr/bin/env bash

docker run --rm -v "${PWD}":/work docker.io/chainguard/melange keygen

docker run --privileged --rm -v "${PWD}":/work \
  docker.io/chainguard/melange build melange.yaml \
  --arch amd64,aarch64 \
  --signing-key melange.rsa


docker run --privileged --rm -v "${PWD}":/work \
  docker.io/chainguard/melange build melange.yaml \
  --arch amd64,aarch64 \
  --signing-key melange.rsa

for p in *.yaml; do
  docker run --rm --privileged --user root -v "$(pwd):/work" -w /work \
    docker.io/chainguard/melange:latest build "${p}" \
    --arch=amd64,aarch64 \
    --pipeline-dir ./pipelines \
    --workspace-dir /work \
    --out-dir ./packages \
    --log-level debug \
    --signing-key melange.rsa \
    --repository-append https://packages.wolfi.dev/os \
    --keyring-append https://packages.wolfi.dev/os/wolfi-signing.rsa.pub
done
