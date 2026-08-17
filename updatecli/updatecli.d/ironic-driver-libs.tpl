name: "Ironic driver libraries ({{ .openstack.series }} driver-requirements.txt)"

# These libraries are not in OpenStack's upper-constraints. Ironic pins a
# compatible range in its own driver-requirements.txt; track the newest PyPI
# release inside that range at the pinned series' ironic version.

sources:
{{- range .openstack.driverLibraries }}
  {{ . }}:
    name: "PyPI {{ . }} within ironic {{ $.openstack.series }} driver-requirements range"
    kind: shell
    spec:
      command: bash scripts/openstack-version.sh driver-lib {{ $.openstack.series }} {{ . }}
      environments:
        - name: PATH
{{- end }}

targets:
{{- range .openstack.driverLibraries }}
  {{ . }}:
    name: "py3-{{ . }}: sync with ironic {{ $.openstack.series }} driver-requirements"
    kind: yaml
    sourceid: {{ . }}
    spec:
      file: py3-{{ . }}.yaml
      key: $.package.version
{{- end }}
