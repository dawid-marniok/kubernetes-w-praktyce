# Przykłady: Pod

| Plik | Co pokazuje |
|---|---|
| `pod.yaml` | najprostszy pod: obraz z tagiem, etykieta, port, requests/limits |
| `pod-multi-container.yaml` | dwa kontenery, wspólny `emptyDir`, komunikacja przez localhost |
| `pod-env-vars.yaml` | zmienne środowiskowe w manifeście |
| `pod-command-args.yaml` | `command` i `args` (opis: `DOCKER-vs-KUBERNETES-command-args.md`) |
| `pod-restart-policy.yaml` | `restartPolicy: OnFailure` i proces kończący się błędem |
| `pod-probes.yaml` | startupProbe, readinessProbe, livenessProbe |
| `pod-zly-obraz.yaml` | awaria: literówka w obrazie → `ImagePullBackOff` (diagnoza: Events w `describe`) |
| `pod-crashloop.yaml` | awaria: proces kończy się błędem → `CrashLoopBackOff` (diagnoza: `logs --previous`) |
| `pod-oom.yaml` | awaria: przekroczony limit pamięci → `OOMKilled`, kod 137 (diagnoza: Last State w `describe`) |

```bash
kubectl apply -f pod.yaml
kubectl get pod przyklad-pod -o wide
kubectl delete -f pod.yaml
```
Pod nie wstaje? Zawsze ta sama kolejność: `kubectl get pods` → `kubectl describe pod <nazwa>` (Events, Last State) → `kubectl logs <nazwa> --previous` → `kubectl events`.

Każdy przykład ma `resources` (wymagane przez ResourceQuota na wspólnym klastrze) i własną etykietę `app: przyklad-…`, więc nie zderzy się z labami.
