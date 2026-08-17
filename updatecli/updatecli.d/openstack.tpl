name: "OpenStack {{ .openstack.series }} coordinated package versions"

# Keeps every py3-*.yaml on the versions OpenStack releases and tests together
# for the series pinned in updatecli/values.yaml:
#   - services come from openstack/releases deliverables for the series
#   - libraries come from the series' upper-constraints.txt

sources:
{{- range .openstack.services }}
  {{ . }}:
    name: "openstack/releases: latest {{ . }} in {{ $.openstack.series }}"
    kind: shell
    spec:
      command: bash scripts/openstack-version.sh deliverable {{ $.openstack.series }} {{ . }}
      environments:
        - name: PATH
{{- end }}
{{- range .openstack.dependencies }}
  {{ . }}:
    name: "upper-constraints {{ $.openstack.series }}: {{ . }}"
    kind: shell
    spec:
      command: bash scripts/openstack-version.sh constraint {{ $.openstack.series }} {{ . }}
      environments:
        - name: PATH
{{- end }}

targets:
{{- range .openstack.services }}
  {{ . }}:
    name: "py3-{{ . }}: sync with OpenStack {{ $.openstack.series }}"
    kind: yaml
    sourceid: {{ . }}
    spec:
      file: py3-{{ . }}.yaml
      key: $.package.version
{{- end }}
{{- range .openstack.dependencies }}
  {{ . }}:
    name: "py3-{{ . }}: sync with OpenStack {{ $.openstack.series }} upper-constraints"
    kind: yaml
    sourceid: {{ . }}
    spec:
      file: py3-{{ . }}.yaml
      key: $.package.version
{{- end }}
