{{/*
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
*/}}
{{/*
Expand the name of the chart.
*/}}
{{- define "aiperf.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "aiperf.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "aiperf.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "aiperf.labels" -}}
helm.sh/chart: {{ include "aiperf.chart" . }}
{{ include "aiperf.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "aiperf.selectorLabels" -}}
app.kubernetes.io/name: {{ include "aiperf.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "aiperf.serviceAccountName" -}}
{{- if .Values.security.serviceAccount.create }}
{{- default (include "aiperf.fullname" .) .Values.security.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.security.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the name of the worker service account to use
*/}}
{{- define "aiperf.workerServiceAccountName" -}}
{{- if .Values.security.serviceAccount.create }}
{{- printf "%s-worker" (include "aiperf.fullname" .) }}
{{- else }}
{{- default "default" .Values.security.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create a default image name
*/}}
{{- define "aiperf.image" -}}
{{- if .Values.global.imageRegistry }}
{{- printf "%s/%s:%s" .Values.global.imageRegistry .Values.aiperf.image.repository (.Values.aiperf.image.tag | default .Chart.AppVersion) }}
{{- else }}
{{- printf "%s/%s:%s" .Values.aiperf.image.registry .Values.aiperf.image.repository (.Values.aiperf.image.tag | default .Chart.AppVersion) }}
{{- end }}
{{- end }}

{{/*
Create storage class name
*/}}
{{- define "aiperf.storageClassName" -}}
{{- if .Values.global.storageClass }}
{{- .Values.global.storageClass }}
{{- else if .storageClass }}
{{- .storageClass }}
{{- else }}
{{- "" }}
{{- end }}
{{- end }}

{{/*
Create ZMQ proxy service name
*/}}
{{- define "aiperf.zmqProxyServiceName" -}}
{{- printf "%s-zmq-proxy" (include "aiperf.fullname" .) }}
{{- end }}

{{/*
Create namespace name for workers
*/}}
{{- define "aiperf.workersNamespace" -}}
{{- printf "%s-workers" .Release.Namespace }}
{{- end }}

{{/*
Validate configuration
*/}}
{{- define "aiperf.validateConfig" -}}
{{- if and .Values.workers.autoscaling.enabled (not .Values.monitoring.prometheus.enabled) }}
{{- fail "HPA with custom metrics requires Prometheus to be enabled" }}
{{- end }}
{{- if and .Values.networking.serviceMesh.enabled (not (has .Values.networking.serviceMesh.type (list "istio" "linkerd" "consul-connect"))) }}
{{- fail "Unsupported service mesh type. Supported types: istio, linkerd, consul-connect" }}
{{- end }}
{{- end }}
