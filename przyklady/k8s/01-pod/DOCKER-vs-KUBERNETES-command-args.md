# command i args w Kubernetesie a ENTRYPOINT i CMD w Dockerze

| Dockerfile | `docker run` | Kubernetes (kontener w podzie) |
|---|---|---|
| `ENTRYPOINT` | `--entrypoint <program>` | `command: [...]` |
| `CMD` | argumenty po nazwie obrazu | `args: [...]` |

Wynik w Kubernetesie:

| W manifeście | Co się uruchomi |
|---|---|
| nic | `ENTRYPOINT` + `CMD` z obrazu |
| tylko `args` | `ENTRYPOINT` z obrazu + Twoje `args` |
| tylko `command` | Twoje `command` (bez `CMD` z obrazu) |
| `command` i `args` | Twoje `command` + Twoje `args` |

## Przykład: nginx
Obraz `nginx:1.29` ma `ENTRYPOINT ["/docker-entrypoint.sh"]` i `CMD ["nginx", "-g", "daemon off;"]` (sprawdzisz: `docker image inspect nginx:1.29 --format '{{.Config.Entrypoint}} {{.Config.Cmd}}'`).

```bash
docker run --rm nginx:1.29 nginx -v                     # nadpisany CMD; skrypt startowy dalej działa i uruchamia „nginx -v”
docker run --rm --entrypoint sh nginx:1.29 -c 'echo hej' # nadpisany ENTRYPOINT
```
To samo w podzie:
```yaml
containers:
- name: nginx
  image: nginx:1.29
  args: ["nginx", "-v"]          # jak: docker run nginx:1.29 nginx -v
---
containers:
- name: nginx
  image: nginx:1.29
  command: ["sh", "-c"]          # jak: --entrypoint sh
  args: ["echo hej"]
```

## Na co uważać
- `command` z jednym napisem `["echo hej && sleep 10"]` nie zadziała — to nazwa programu ze spacjami. Potrzebna powłoka: `command: ["sh", "-c", "echo hej && sleep 10"]`.
- Nadpisanie `command` w obrazie, którego `ENTRYPOINT` robi przygotowanie (np. skrypty w `/docker-entrypoint.d/` w nginx, inicjalizacja bazy w `mysql`), pomija to przygotowanie.
- `kubectl run … -- <argumenty>` ustawia `args`; z `--command -- <program>` ustawia `command`.

Plik do wypróbowania: `pod-command-args.yaml`.
