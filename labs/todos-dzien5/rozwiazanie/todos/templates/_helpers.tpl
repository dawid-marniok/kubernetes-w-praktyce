{{/* Etykiety każdego obiektu. part-of: todos jak w dniach 2–4: na niej opierają się NetworkPolicy i komendy z labów. */}}
{{- define "todos.labels" -}}
app.kubernetes.io/part-of: todos
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{/* Pełna nazwa obrazu: include "todos.image" (dict "ctx" . "img" .Values.api.image) */}}
{{- define "todos.image" -}}
{{- $reg := required "Ustaw registry: --set registry=<REJESTR> (z karty)" .ctx.Values.registry -}}
{{- printf "%s/%s:%s" $reg .img.repository (.img.tag | default .ctx.Chart.AppVersion) -}}
{{- end -}}

{{/* securityContext kontenera pod Pod Security restricted (dzień 4), wspólny dla wszystkich */}}
{{- define "todos.containerSecurity" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: ["ALL"]
{{- end -}}
