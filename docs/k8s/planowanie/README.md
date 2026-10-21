# Dzień 3 — ściąga: planowanie podów i serwis węzłów

**Wizualizacja:** [planowanie.html](planowanie.html). Otwórz plik w przeglądarce (dwuklik albo `open planowanie.html`). Są tam trzy symulatory: scheduler (filtr, ocena, bind, Pending z komunikatem `FailedScheduling`), taints i tolerations oraz cordon i drain z PodDisruptionBudget. Na końcu jest tabela „kiedy co” i komendy.

Gotowe manifesty: `przyklady/k8s/15-affinity-taints/` (affinity, anti-affinity, spread, taints) i `przyklady/k8s/16-pdb/` (PDB i drain). Etykiety, tainty i drain zmienia tylko administrator, więc ćwiczysz na kind ([`../lokalnie/README.md`](../lokalnie/README.md)).

## Jak scheduler wybiera węzeł

| Krok | Co robi | Gdy się nie uda |
|---|---|---|
| **Filtr** | odrzuca węzły: taint bez toleracji, nodeSelector i `required` affinity, za mało wolnych `requests`, spread `DoNotSchedule`, `required` anti-affinity | żaden węzeł nie przeszedł → pod `Pending`, event `0/3 nodes are available: …` |
| **Ocena** | punktuje resztę: reguły `preferred`, `PreferNoSchedule`, rozkład replik, wolne zasoby | — |
| **Bind** | zapisuje `spec.nodeName`; kubelet na tym węźle startuje kontenery | — |

Scheduler liczy `requests`, nie faktyczne zużycie. Reguły `…IgnoredDuringExecution` nie przesuwają działających podów.

## Kiedy co

| Mechanizm | Odpowiada na pytanie | Siła |
|---|---|---|
| `nodeSelector` | na jakich węzłach wolno (równość etykiet) | twardo |
| `nodeAffinity` | gdzie musi (`required`) albo woli (`preferred`) | twardo / miękko |
| `podAffinity` / `podAntiAffinity` | obok kogo / nie obok kogo | twardo / miękko |
| `topologySpreadConstraints` | jak równo rozłożyć repliki po węzłach lub strefach | `DoNotSchedule` / `ScheduleAnyway` |
| taints + tolerations | kogo węzeł nie wpuszcza, kto ma przepustkę | `NoSchedule`, `PreferNoSchedule`, `NoExecute` |
| `PriorityClass` | kto pierwszy w kolejce i kogo wolno wywłaszczyć | wywłaszcza |
| PodDisruptionBudget | ile podów naraz może zniknąć przy drain i upgrade | tylko Eviction API |
| cordon / drain / uncordon | jak zabrać węzeł spod podów | operacja admina |

Toleracja pozwala, nie przyciąga. Węzeł tylko dla GPU = taint + toleracja + nodeAffinity.

## PodDisruptionBudget w skrócie

- `disruptionsAllowed = currentHealthy − desiredHealthy`; widać to w `kubectl get pdb` jako `ALLOWED DISRUPTIONS`.
- Działa tylko dla Eviction API: `kubectl drain`, upgrade puli węzłów, Cluster Autoscaler, Karpenter.
- Nie chroni przed awarią węzła, OOMKill, `kubectl delete pod` ani rolling update Deploymentu.
- `minAvailable` ≥ replicas (albo 1 replika z `minAvailable: 1`) blokuje drain na zawsze. Bezpieczny wybór: `maxUnavailable: 1` i co najmniej 2 repliki.
- `unhealthyPodEvictionPolicy: AlwaysAllow` sprawia, że niegotowe pody nie blokują draina.
- Na EKS upgrade managed node group sam robi cordon i drain z poszanowaniem PDB. Gdy pody nie dają się wyrzucić przez ok. 15 min, kończy się błędem `PodEvictionFailure` (chyba że wymusisz go opcją `force`).

## Komendy

```bash
kubectl label nodes <węzeł> disktype=ssd                 # etykieta węzła (disktype- usuwa)
kubectl taint nodes <węzeł> dedicated=gpu:NoSchedule     # taint (z minusem na końcu: zdjęcie)
kubectl get events --field-selector reason=FailedScheduling
kubectl cordon <węzeł>
kubectl drain <węzeł> --ignore-daemonsets --delete-emptydir-data --timeout=5m
kubectl uncordon <węzeł>                                 # pody nie wracają same
kubectl get pdb                                          # kolumna ALLOWED DISRUPTIONS
```
