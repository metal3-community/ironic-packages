#!/usr/bin/env bash

# Ensure packages directory exists
mkdir -p ./packages/{alpine,wolfi}

wolfi_repositories=(
  "https://packages.wolfi.dev/os"
)
wolfi_keyrings=(
  "https://packages.wolfi.dev/os/wolfi-signing.rsa.pub"
)
alpine_repositories=(
  "https://dl-cdn.alpinelinux.org/alpine/edge/main"
  "https://dl-cdn.alpinelinux.org/alpine/edge/community"
)
alpine_keyrings=(
  "https://alpinelinux.org/keys/alpine-devel@lists.alpinelinux.org-4a6a0840.rsa.pub"
  "https://alpinelinux.org/keys/alpine-devel@lists.alpinelinux.org-616ae350.rsa.pub"
)

if [[ -z "${packages}" ]]; then
packages="$(ls {py3-*,ipmitool}.yaml | sed 's#\.yaml##g' | sort -u)"
fi

archs=(
  aarch64
)

namespaces=(
  alpine
  wolfi
)

for arch in "${archs[@]}"; do
  echo "Building for architecture: ${arch}"
  for namespace in "${namespaces[@]}"; do
    echo "Using namespace: ${namespace}"
    if [[ ! -d "./packages/${namespace}/${arch}" ]]; then
      mkdir -p "./packages/${namespace}/${arch}"
    fi

    for package_name in ${packages[@]}; do
      f="${package_name}.yaml"
      if [[ ! -f "$f" ]]; then
        echo "Warning: ${package_name} not found, skipping..."
        continue
      fi

      # Check if package already exists in packages/alpine/
      if ls ./packages/"${namespace}"/"${package_name}"-*.apk 1> /dev/null 2>&1; then
        echo "Package ${package_name} already exists, skipping..."
        continue
      fi

      repository_args="--repository-append ./packages/${namespace}"
      keyring_args="--keyring-append ./melange.rsa.pub"

      if [[ "${namespace}" == "wolfi" ]]; then
        repositories=("${wolfi_repositories[@]}")
        keyrings=("${wolfi_keyrings[@]}")
      else
        repositories=("${alpine_repositories[@]}")
        keyrings=("${alpine_keyrings[@]}")
      fi
      for repo in "${repositories[@]}"; do
        repository_args+=" --repository-append ${repo}"
      done
      for key in "${keyrings[@]}"; do
        keyring_args+=" --keyring-append ${key}"
      done

      echo "${repository_args}" "${keyring_args}" | \
      xargs \
      melange build "${f}" --arch "${arch}" \
        --namespace "${namespace}" \
        --workspace-dir ./workspace \
        --cache-dir ./cache \
        --out-dir "./packages/${namespace}" \
        --log-level info \
        --signing-key ./melange.rsa \
        || { echo "Build failed for ${f}"; exit 1; }
    done
  done
done
