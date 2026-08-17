name: "Sync package versions with requirements.lock (OpenStack {{ .openstack.series }})"

# Every py3-*.yaml tracks the exact version resolved into requirements.lock
# by 'scripts/ironic-deps.py lock' — pyproject.toml (services at their
# OpenStack {{ .openstack.series }} versions plus ironic's driver-requirements
# ranges) resolved by uv under the series' upper-constraints. Reading the
# committed lock keeps this pipeline deterministic and offline.

sources:
{{- range concat .openstack.services .openstack.dependencies .openstack.driverLibraries }}
  {{ . }}:
    name: "requirements.lock: {{ . }}"
    kind: shell
    spec:
      command: bash scripts/openstack-version.sh lock {{ . }}
      environments:
        - name: PATH
{{- end }}

targets:
{{- range concat .openstack.services .openstack.dependencies .openstack.driverLibraries }}
  {{ . }}:
    name: "py3-{{ . }}: sync with requirements.lock"
    kind: yaml
    sourceid: {{ . }}
    spec:
      file: py3-{{ . }}.yaml
      key: $.package.version
{{- end }}
