terraform {
  required_providers {
    apko = {
      source  = "chainguard-dev/apko"
      version = ">=0.29.11"
    }
    oci = {
      source  = "chainguard-dev/oci"
      version = ">=0.0.25"
    }
  }
}

locals {
  ironic_config = <<EOF
contents:
  keyring:
    - https://packages.wolfi.dev/os/wolfi-signing.rsa.pub
    - ./melange.rsa.pub
  repositories:
    - https://packages.wolfi.dev/os
    - '@local /work/packages'
  packages:
    - wolfi-base
    - ca-certificates-bundle
    - hello-minicli@local
accounts:
  groups:
    - groupname: ironic
      gid: 65532
  users:
    - username: ironic
      uid: 65532
  run-as: 65532
entrypoint:
  command: /usr/bin/ironic --config /etc/ironic/ironic.conf
EOF
}

# Build base Alpine + Python with apko
resource "apko_build" "ipa_base" {
  config = {


    repositories = [
      "https://dl-cdn.alpinelinux.org/alpine/v3.20/main",
      "https://dl-cdn.alpinelinux.org/alpine/v3.20/community"
    ]

    packages = [
      "alpine-base",
      "busybox",
      "bash",
      "python3",
      "py3-pip",
      "util-linux",
      "iproute2",
      "iputils",
      "ethtool",
      "dmidecode",
      "pciutils",
      "lshw",
      "smartmontools",
      "open-iscsi",
      "coreutils"
    ]

    accounts = {
      run-as = "ironic"

      users = [{
        uid  = 65532
        name = "ironic"
      }]
      groups = [{
        gid     = 65532
        groupname    = "ironic"
        members = ["ironic"]
      }]
    }

    entrypoint = {
      command = "/init"

      type = "service-bundle"
      shell-fragment = ""
      services = {}
    }

    archs = [
      # "x86_64",
      "aarch64"
    ]

    annotations = {
      "org.opencontainers.image.title"       = "IPA Base"
      "org.opencontainers.image.description" = "IPA Base Image"
      "org.opencontainers.image.version"     = "1.0.0"
    }

    cmd = ""

    contents = {}

    environment = {}

    include = ""

    layering = {
      budget = ""
      strategy = ""
    }

    paths = []

    stop-signal = "SIGTERM"

    vcs-url = "<https://github.com/openstack/ironic>"

    volumes = []

    work-dir = "./work"
  }
  repo = "ipa-base"
}

resource "oci_append" "ipa_with_init" {
  base_image = apko_build.ipa_base.ref
  layers = [{
    files = {
      "/init" = {
        source      = "${path.module}/init.sh"
        permissions = "0755"
      }
    }
  }]
}

resource "oci_tag" "ipa_with_init" {
  digest_ref = oci_append.ipa_with_init.ref
  tag        = "ipa-with-init:latest"
}

output "ipa_image_ref" {
  value = oci_append.ipa_with_init.ref
}