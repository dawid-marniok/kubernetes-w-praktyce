# Składnia szablonów Helm — ściąga

Do labu `labs/lab17-helm/`. Szablony to Go templates z biblioteką Sprig; wynik zawsze sprawdzisz komendą `helm template <release> ./<chart>`.

## Podstawowe konstrukcje

### 1. Warunki (if/else)
```yaml
{{- if .Values.autoscaling.enabled }}
  # kod wykonywany gdy autoscaling jest włączony
{{- else }}
  # kod wykonywany gdy autoscaling jest wyłączony
{{- end }}
```
- `{{-` - usuwa białe znaki przed wyrażeniem
- `-}}` - usuwa białe znaki po wyrażeniu
- `.Values` - dostęp do wartości z pliku values.yaml
- `.Values.autoscaling.enabled` - sprawdza wartość klucza enabled w sekcji autoscaling

#### Przykład praktyczny:
```yaml
# values.yaml
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 5

# deployment.yaml
spec:
  {{- if .Values.autoscaling.enabled }}
  replicas: {{ .Values.autoscaling.minReplicas }}
  {{- else }}
  replicas: 1
  {{- end }}
```

### 2. Pętle (range)
```yaml
{{- range .Values.ingress.hosts }}
  host: {{ .host }}
  paths:
    {{- range .paths }}
      path: {{ .path }}
    {{- end }}
{{- end }}
```
- `range` - iteruje po elementach listy
- `.` - odnosi się do aktualnego elementu w pętli

#### Przykład praktyczny:
```yaml
# values.yaml
ingress:
  hosts:
    - host: app1.example.com
      paths:
        - path: /api
        - path: /web
    - host: app2.example.com
      paths:
        - path: /admin

# ingress.yaml
spec:
  rules:
  {{- range .Values.ingress.hosts }}
    - host: {{ .host }}
      http:
        paths:
        {{- range .paths }}
          - path: {{ .path }}
            pathType: Prefix
            backend:
              service:
                name: {{ $.Release.Name }}
                port:
                  number: 80
        {{- end }}
  {{- end }}
```

### 3. Funkcje pomocnicze (define)
```yaml
{{- define "example-app.name" -}}
  {{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}
```
- `define` - definiuje funkcję pomocniczą
- `default` - zwraca wartość domyślną jeśli pierwsza wartość jest pusta
- `trunc` - obcina string do określonej długości
- `trimSuffix` - usuwa określony sufiks

#### Przykład praktyczny:
```yaml
# _helpers.tpl
{{- define "app.labels" -}}
app.kubernetes.io/name: {{ include "app.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}

# deployment.yaml
metadata:
  labels:
    {{- include "app.labels" . | nindent 4 }}
```

### 4. Włączanie szablonów (include)
```yaml
name: {{ include "example-app.fullname" . }}
```
- `include` - włącza zdefiniowaną wcześniej funkcję pomocniczą
- `.` - przekazuje aktualny kontekst do funkcji

#### Przykład praktyczny:
```yaml
# deployment.yaml
metadata:
  name: {{ include "app.fullname" . }}
  labels:
    {{- include "app.labels" . | nindent 4 }}
```

### 5. Warunkowe włączanie sekcji (with)
```yaml
{{- with .Values.podAnnotations }}
annotations:
  {{- toYaml . | nindent 8 }}
{{- end }}
```
- `with` - tworzy nowy kontekst dla zagnieżdżonego kodu
- `toYaml` - konwertuje obiekt na format YAML
- `nindent` - dodaje wcięcia do każdej linii

#### Przykład praktyczny:
```yaml
# values.yaml
podAnnotations:
  team: frontend
  owner: adamd

# deployment.yaml
metadata:
  {{- with .Values.podAnnotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
```

### 6. Operatory potoku (|)
```yaml
{{ .Values.name | default "default-name" | quote }}
```
- `|` - przekazuje wynik jednej funkcji do drugiej
- `quote` - dodaje cudzysłowy do stringa

#### Przykład praktyczny:
```yaml
# values.yaml
image:
  tag: "1.0.0"     # pusty tag → appVersion z Chart.yaml, nigdy latest

# deployment.yaml
image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
```

### 7. Zmienne
```yaml
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- printf "%s-%s" .Release.Name $name }}
```
- `:=` - deklaracja zmiennej
- `$name` - zmienna lokalna
- `printf` - formatuje string

#### Przykład praktyczny:
```yaml
# deployment.yaml
{{- $fullName := include "app.fullname" . -}}
{{- $svcPort := .Values.service.port -}}
spec:
  template:
    spec:
      containers:
        - name: {{ $fullName }}
          ports:
            - containerPort: {{ $svcPort }}
```

### 8. Kontekst (.)
```yaml
{{- define "example-app.labels" -}}
helm.sh/chart: {{ include "example-app.chart" . }}
{{- end }}
```
- `.` - reprezentuje aktualny kontekst
- `.Chart` - dostęp do metadanych chartu
- `.Release` - dostęp do informacji o release
- `.Values` - dostęp do wartości z values.yaml

#### Przykład praktyczny:
```yaml
# deployment.yaml
metadata:
  name: {{ .Release.Name }}-{{ .Chart.Name }}
  labels:
    app.kubernetes.io/name: {{ .Chart.Name }}
    app.kubernetes.io/instance: {{ .Release.Name }}
    app.kubernetes.io/version: {{ .Chart.AppVersion }}
```

### 9. Komentarze
```yaml
{{/* To jest komentarz w Helm */}}
```
- `{{/* */}}` - komentarz w szablonie Helm

#### Przykład praktyczny:
```yaml
{{/* 
  Ten deployment używa następujących wartości z values.yaml:
  - image.repository
  - image.tag
  - resources
*/}}
apiVersion: apps/v1
kind: Deployment
```

### 10. Warunkowe renderowanie
```yaml
{{- if and .Values.prometheus.enabled .Values.prometheus.serviceMonitor.enabled }}
  # kod wykonywany gdy oba warunki są spełnione
{{- end }}
```
- `and` - operator logiczny AND
- `or` - operator logiczny OR
- `not` - operator logiczny NOT

#### Przykład praktyczny:
```yaml
# values.yaml
prometheus:
  enabled: true
  serviceMonitor:
    enabled: true
    interval: 15s

# servicemonitor.yaml
{{- if and .Values.prometheus.enabled .Values.prometheus.serviceMonitor.enabled }}
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: {{ include "app.fullname" . }}
spec:
  endpoints:
    - port: metrics
      interval: {{ .Values.prometheus.serviceMonitor.interval }}
{{- end }}
```

## Przydatne funkcje

### 1. String
- `trim` - usuwa białe znaki
- `lower` - konwertuje na małe litery
- `upper` - konwertuje na wielkie litery
- `title` - konwertuje na format tytułu
- `trimPrefix` - usuwa prefiks
- `trimSuffix` - usuwa sufiks

#### Przykład praktyczny:
```yaml
# values.yaml
appName: "My Application"

# deployment.yaml
metadata:
  name: {{ .Values.appName | lower | replace " " "-" }}
  labels:
    app: {{ .Values.appName | title }}
```

### 2. Listy
- `first` - pierwszy element listy
- `last` - ostatni element listy
- `len` - długość listy
- `sortAlpha` - sortuje alfabetycznie

#### Przykład praktyczny:
```yaml
# values.yaml
ports:
  - 8080
  - 8081
  - 8082

# deployment.yaml
ports:
  - containerPort: {{ first .Values.ports }}
  - containerPort: {{ last .Values.ports }}
```

### 3. Konwersje
- `toYaml` - konwertuje na YAML
- `toJson` - konwertuje na JSON
- `toToml` - konwertuje na TOML

#### Przykład praktyczny:
```yaml
# values.yaml
config:
  database:
    host: localhost
    port: 5432
    user: admin

# configmap.yaml
data:
  config.yaml: |
    {{- toYaml .Values.config | nindent 4 }}
```

### 4. Formatowanie
- `indent` - dodaje wcięcia
- `nindent` - dodaje wcięcia i nową linię
- `quote` - dodaje cudzysłowy
- `squote` - dodaje pojedyncze cudzysłowy

#### Przykład praktyczny:
```yaml
# values.yaml
environment: production

# deployment.yaml
env:
  - name: NODE_ENV
    value: {{ .Values.environment | quote }}
  - name: APP_NAME
    value: {{ .Values.appName | squote }}
```

## Przykłady użycia

### 1. Warunkowe renderowanie zasobów
```yaml
{{- if .Values.resources }}
resources:
  {{- toYaml .Values.resources | nindent 12 }}
{{- end }}
```

### 2. Iteracja po mapie
```yaml
{{- range $key, $value := .Values.annotations }}
{{ $key }}: {{ $value }}
{{- end }}
```

### 3. Łączenie stringów
```yaml
{{- printf "%s-%s" .Release.Name .Chart.Name }}
```

### 4. Warunkowe włączanie sekcji
```yaml
{{- with .Values.nodeSelector }}
nodeSelector:
  {{- toYaml . | nindent 8 }}
{{- end }} 