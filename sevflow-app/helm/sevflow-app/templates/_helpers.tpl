{{- define "sevflow-app.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "sevflow-app.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "sevflow-app.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "sevflow-app.selectorLabels" -}}
app.kubernetes.io/name: {{ include "sevflow-app.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "sevflow-app.labels" -}}
{{ include "sevflow-app.selectorLabels" . }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "sevflow-app.serviceName" -}}
{{ include "sevflow-app.fullname" . }}
{{- end -}}

{{- define "sevflow-app.canary.stableServiceName" -}}
{{- $pd := .Values.progressiveDelivery | default dict -}}
{{- $canary := $pd.canary | default dict -}}
{{- printf "%s-%s" (include "sevflow-app.fullname" .) ($canary.stableServiceSuffix | default "stable") | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "sevflow-app.canary.canaryServiceName" -}}
{{- $pd := .Values.progressiveDelivery | default dict -}}
{{- $canary := $pd.canary | default dict -}}
{{- printf "%s-%s" (include "sevflow-app.fullname" .) ($canary.canaryServiceSuffix | default "canary") | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "sevflow-app.blueGreen.activeServiceName" -}}
{{- $pd := .Values.progressiveDelivery | default dict -}}
{{- $blueGreen := $pd.blueGreen | default dict -}}
{{- printf "%s-%s" (include "sevflow-app.fullname" .) ($blueGreen.activeServiceSuffix | default "active") | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "sevflow-app.blueGreen.previewServiceName" -}}
{{- $pd := .Values.progressiveDelivery | default dict -}}
{{- $blueGreen := $pd.blueGreen | default dict -}}
{{- printf "%s-%s" (include "sevflow-app.fullname" .) ($blueGreen.previewServiceSuffix | default "preview") | trunc 63 | trimSuffix "-" -}}
{{- end -}}
