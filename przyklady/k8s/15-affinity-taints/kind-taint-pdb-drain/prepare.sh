#!/usr/bin/env bash
# Przygotowanie ćwiczenia „taint, toleracja, PDB i drain” na kind:
#  1. klaster kind „szkolenie” z kind-config.yaml (1 control-plane + 2 workery), jeśli go jeszcze nie ma,
#  2. pobranie nginx:1.29 na oba workery, żeby przenoszenie podów przy drainie trwało sekundy,
#  3. namespace taint-drain i ustawienie go jako domyślnego w kontekście kind-szkolenie.
# Użycie: ./prepare.sh                 przygotowanie
#         ./prepare.sh --delete        sprzątanie ćwiczenia: namespace, tainty dedicated, uncordon (klaster zostaje)
#         ./prepare.sh --usun-klaster  usunięcie całego klastra kind (także wszystkiego z innych przykładów i labów na nim)
set -euo pipefail
cd "$(dirname "$0")"
CLUSTER="${CLUSTER:-szkolenie}"
KCTX="kind-$CLUSTER"
NS=taint-drain

case "${1:-}" in
  --delete)
    kubectl --context "$KCTX" delete namespace "$NS" --ignore-not-found
    for n in "$CLUSTER-worker" "$CLUSTER-worker2"; do
      kubectl --context "$KCTX" taint nodes "$n" dedicated- 2>/dev/null || true
      kubectl --context "$KCTX" uncordon "$n" >/dev/null
    done
    kubectl --context "$KCTX" describe nodes | grep Taints
    echo "Posprzątane: namespace $NS usunięty, tainty dedicated zdjęte, węzły uncordon."
    exit 0 ;;
  --usun-klaster)
    kind delete cluster --name "$CLUSTER"; exit 0 ;;
esac

kind get clusters | grep -qx "$CLUSTER" || kind create cluster --name "$CLUSTER" --config kind-config.yaml
for n in "$CLUSTER-worker" "$CLUSTER-worker2"; do docker exec "$n" crictl pull nginx:1.29 >/dev/null; done
kubectl --context "$KCTX" create namespace "$NS" --dry-run=client -o yaml | kubectl --context "$KCTX" apply -f -
kubectl config use-context "$KCTX" >/dev/null
kubectl config set-context --current --namespace="$NS" >/dev/null
kubectl get nodes
echo "Gotowe: klaster $CLUSTER (kontekst $KCTX, bieżący), nginx:1.29 na workerach, namespace $NS."
