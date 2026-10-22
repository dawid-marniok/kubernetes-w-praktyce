# Dzień 4 — ściąga: RBAC i ServiceAccount

**Wizualizacje** (otwórz plik w przeglądarce: dwuklik albo `open rbac.html`):

- [rbac.html](rbac.html): droga żądania przez kube-apiserver (401, 403, admission) krok po kroku, RBAC „kto – co – gdzie”, symulator `kubectl auth can-i`, ServiceAccount i jego token, po co dedykowany ServiceAccount, antywzorzec `cluster-admin`.
- [uwierzytelnianie.html](uwierzytelnianie.html): jak klaster wie, kim jesteś. Zwykły Kubernetes (certyfikat, OIDC, token SA) i EKS (IAM, access entries, access policies) obok siebie, nasz klaster od konta IAM do RoleBindingu.

Gotowe manifesty: `przyklady/k8s/17-rbac/`. Reszta dnia 4 (Pod Security, NetworkPolicy, skanowanie): [`../bezpieczenstwo/README.md`](../bezpieczenstwo/README.md).

## Droga żądania

| Bramka | Pytanie | Gdy „nie” |
|---|---|---|
| uwierzytelnienie | kim jesteś? Wynik: nazwa użytkownika + grupy | `401 Unauthorized` (`You must be logged in to the server`) |
| autoryzacja (RBAC) | czy ta nazwa/grupa może wykonać czasownik na zasobie w namespace? | `403 Forbidden`, komunikat podaje użytkownika, czasownik, zasób, grupę API i namespace |
| admission | czy ten obiekt jest dopuszczalny? (quota, Pod Security, webhooki) | też `403`, ale z powodem: `exceeded quota`, `violates PodSecurity` |

Admission dotyczy tylko zapisu. Pody Deploymentu tworzy kontroler ReplicaSet, więc odrzucenie poda przez admission widać w eventach (`FailedCreate`), a nie w wyniku `kubectl apply`.

## RBAC w skrócie

- **Kto:** User i Group (tylko nazwy, w klastrze nie ma obiektu User), ServiceAccount (`system:serviceaccount:<ns>:<sa>`).
- **Co:** Role (w namespace) albo ClusterRole (szablon dla całego klastra): `apiGroups` + `resources` + `verbs`.
- **Gdzie:** RoleBinding działa w jednym namespace (może wskazać Role albo ClusterRole), ClusterRoleBinding w całym klastrze i dla zasobów klastrowych (tylko ClusterRole).
- Reguły tylko dodają, nie ma „deny”. Brak pasującej reguły = odmowa.
- Grupa API: `""` (pods, secrets, configmaps, services), `apps` (deployments, statefulsets), `batch` (jobs). `kubectl api-resources` pokaże resztę.
- Subresource to osobny zasób: `pods/log`, `pods/exec`, `deployments/scale`.
- Wbudowane: `view` (bez Secretów i bez RBAC), `edit` (z Secretami, bez Role/RoleBinding), `admin`, `cluster-admin`.
- Nie nadasz więcej, niż sam masz (chyba że masz czasowniki `escalate` / `bind`).

```bash
kubectl auth whoami
kubectl auth can-i --list -n <ns>
kubectl auth can-i get pods --subresource=log -n <ns>
kubectl auth can-i list pods --as=system:serviceaccount:<ns>:<sa>     # --as wymaga prawa impersonate
kubectl create role pod-reader --verb=get,list,watch --resource=pods,pods/log
kubectl create rolebinding read-pods --role=pod-reader --serviceaccount=<ns>:app-sa
```

## ServiceAccount w skrócie

- Tożsamość poda. Każdy namespace ma SA `default`; pod bez `serviceAccountName` dostaje właśnie jego. `default` nie ma ról, dopóki ktoś mu ich nie da.
- Token jest montowany w `/var/run/secrets/kubernetes.io/serviceaccount/token`: żyje ok. 1 h, kubelet go odświeża, jest przypięty do poda (po usunięciu poda przestaje działać).
- `automountServiceAccountToken: false` w SA albo w podzie (pod wygrywa): brak tokenu w kontenerze.
- `kubectl create token <sa> --duration=30m`: krótki token na zewnątrz (domyślnie 1 h), nie trafia do żadnego Secretu.
- `imagePullSecrets` w SA: dostaje je każdy pod z tym SA.

**Po co dedykowany SA.** Jedna aplikacja = jeden SA, bo do niego podpinasz uprawnienia i tylko ta aplikacja je dostaje:

| Sytuacja | Przykład | Co robisz |
|---|---|---|
| aplikacja nie rozmawia z API | ToDos `api`, `web` | własny SA + `automountServiceAccountToken: false`: przejęty kontener nie ma tokenu |
| aplikacja rozmawia z API | Prometheus, external-dns, runner CI, operator | Role z dokładnymi czasownikami, binding tylko dla tego SA |
| aplikacja potrzebuje AWS | `api` czyta tylko swój bucket S3, `web` nic | EKS Pod Identity (albo IRSA) przypisane do namespace + SA |
| audyt | log audytu, komunikat 403 | widać `system:serviceaccount:<ns>:api`, a nie `…:default` |

Ryzyko wspólnego `default`: ktoś zbinduje do niego rolę „na szybko” i dostaje ją każdy pod w namespace bez własnego SA. Sam SA daje niewiele, liczy się to, co do niego podepniesz. Kosztuje kilka linii YAML-a, więc rób to zawsze.

**Antywzorzec:** `cluster-admin` (albo `*` na `*`) dla SA aplikacji. Włamanie do poda = przejęcie klastra: wszystkie Secrety, uprzywilejowane pody na dowolnym węźle. Czytaj komunikat 403 i dopisuj do Role dokładnie to, czego brakuje.

<a id="certyfikat"></a>

## Jak powstaje użytkownik z certyfikatem

W Kubernetesie nie ma obiektu User. „Użytkownik z certyfikatem” to certyfikat klienta, w którym `CN` jest nazwą, a każde `O` grupą, podpisany przez CA, któremu ufa kube-apiserver. Poniższe kroki działają na zwykłym klastrze (np. kubeadm albo k3s), na którym jesteś administratorem. Na naszym EKS nie zadziałają: [niżej dlaczego](#eks-cert).

**1. Klucz prywatny i wniosek (CSR).** Klucz zostaje u użytkownika i nigdy nie trafia do klastra.

```bash
openssl genrsa -out jan.key 2048
openssl req -new -key jan.key -out jan.csr -subj "/CN=jan/O=devs"
```

**2. Obiekt CertificateSigningRequest.** Wniosek trafia do klastra jako obiekt (cluster-scoped).

```bash
cat <<EOF | kubectl apply -f -
apiVersion: certificates.k8s.io/v1
kind: CertificateSigningRequest
metadata:
  name: jan
spec:
  request: $(base64 < jan.csr | tr -d '\n')
  signerName: kubernetes.io/kube-apiserver-client   # certyfikat do logowania do apiservera
  expirationSeconds: 86400                          # 1 dzień; minimum 600
  usages: ["client auth"]
EOF
kubectl get csr jan                                 # CONDITION: Pending
```

**3. Sprawdzenie i zatwierdzenie.** Zanim zatwierdzisz, zobacz, o co ktoś prosi. Wniosek z `O=system:masters` dałby superużytkownika.

```bash
kubectl get csr jan -o jsonpath='{.spec.request}' | base64 -d | openssl req -noout -subject
kubectl certificate approve jan
kubectl get csr jan                                 # CONDITION: Approved,Issued
```

**4. Pobranie certyfikatu.** Podpisuje kube-controller-manager kluczem CA klastra i wpisuje wynik do `.status.certificate`.

```bash
kubectl get csr jan -o jsonpath='{.status.certificate}' | base64 -d > jan.crt
openssl x509 -in jan.crt -noout -subject -issuer -enddate
```

**5. Wpis w kubeconfigu.** Klaster (`<klaster>`) już w nim jest, dochodzi użytkownik i kontekst.

```bash
kubectl config set-credentials jan --client-certificate=jan.crt --client-key=jan.key --embed-certs=true
kubectl config set-context jan@<klaster> --cluster=<klaster> --user=jan --namespace=dev
```

**6. Uprawnienia.** Bez bindingu jan jest uwierzytelniony, ale dostaje 403 na wszystko.

```bash
kubectl create rolebinding jan-edit --clusterrole=edit --user=jan -n dev
# albo na grupę z certyfikatu (lepiej): --group=devs
```

**7. Test.**

```bash
kubectl --context=jan@<klaster> auth whoami        # Username: jan, Groups: [devs system:authenticated]
kubectl --context=jan@<klaster> get pods            # działa w dev
kubectl --context=jan@<klaster> get pods -n kube-system   # Forbidden
```

### Dlaczego CA klastra

kube-apiserver przyjmuje certyfikat klienta tylko wtedy, gdy podpisało go CA z jego flagi `--client-ca-file`. Certyfikat z innego CA (nawet poprawny, np. firmowy) kończy się `401`. Na klastrze z kubeadm klucz CA leży na control plane (`/etc/kubernetes/pki/ca.key`) i administrator może podpisać certyfikat ręcznie przez `openssl x509 -req`. API `CertificateSigningRequest` robi to samo bez wydawania klucza CA: zgłaszasz wniosek, ktoś uprawniony go zatwierdza, klaster podpisuje. Na klastrach zarządzanych (EKS, AKS, GKE) klucza CA nie dostajesz wcale, więc zostaje tylko ta droga, o ile dostawca ją obsługuje.

### Kto może zatwierdzić

Utworzenie wniosku to `create` na `certificatesigningrequests`. Zatwierdzenie wymaga dwóch rzeczy naraz: prawa do statusu zatwierdzenia i prawa do konkretnego signera.

```yaml
rules:
- apiGroups: [certificates.k8s.io]
  resources: [certificatesigningrequests]
  verbs: [get, list, watch]
- apiGroups: [certificates.k8s.io]
  resources: [certificatesigningrequests/approval]
  verbs: [update]
- apiGroups: [certificates.k8s.io]
  resources: [signers]
  resourceNames: [kubernetes.io/kube-apiserver-client]
  verbs: [approve]
```

Kto może zatwierdzać wnioski dla `kube-apiserver-client`, ten może wystawić certyfikat na dowolną nazwę i grupę, także `system:masters`. To uprawnienie na poziomie `cluster-admin`.

### Pułapki

- **Brak unieważniania.** Kubernetes nie sprawdza list CRL. Wyciekły certyfikat działa do daty ważności, a jedyne „unieważnienie” to wymiana CA całego klastra. Dlatego krótkie `expirationSeconds` (kontroler i tak przytnie je do swojego maksimum, `--cluster-signing-duration`).
- **Usunięcie bindingu nie usuwa użytkownika.** Jan dalej się uwierzytelnia; traci tylko uprawnienia. Wystarczy, że ktoś kiedyś zbinduje coś do grupy `devs`, a stary certyfikat znów coś może.
- **`O=system:masters` omija RBAC.** Takiego certyfikatu nie ograniczysz żadną rolą. Nie zatwierdzaj wniosków bez sprawdzenia `subject`.
- **Klucz prywatny w pliku.** `--embed-certs=true` wkleja certyfikat i klucz do kubeconfigu. Kto skopiuje kubeconfig, ten jest janem.
- Certyfikat dla człowieka to wyjątek (konto awaryjne, nauka). Do codziennej pracy zespołu: OIDC z firmowym logowaniem i RoleBinding na grupę.

<a id="eks-cert"></a>

### A na EKS?

Na EKS ludzie przychodzą przez IAM: `aws login` + `aws eks update-kubeconfig`, a access entry zamienia konto IAM na nazwę użytkownika Kubernetesa. Certyfikatów klienta nie używa się wcale:

- Dokumentacja AWS ([Secure workloads with Kubernetes certificates](https://docs.aws.amazon.com/eks/latest/userguide/cert-signing.html)): „Client certificate signing is not supported.” EKS podpisuje przez CSR tylko certyfikaty serwerowe (signer `beta.eks.amazonaws.com/app-serving`).
- Sprawdzone na `k8s-sages` (EKS 1.35, październik 2026): wniosek z `signerName: kubernetes.io/kube-apiserver-client` da się utworzyć i zatwierdzić, ale zostaje w stanie `Approved` bez `Issued`, a `.status.certificate` jest pusty. Nikt go nie podpisze.
- Kursant na szkoleniu i tak nie może tworzyć wniosków (`kubectl auth can-i create certificatesigningrequests` → `no`), może je tylko oglądać.

## Zwykły Kubernetes a EKS

RBAC jest identyczny: te same Role, bindingi i `kubectl auth can-i`. Różni się tylko to, co dzieje się przed nim.

| | Zwykły Kubernetes | EKS |
|---|---|---|
| dowód | certyfikat, token OIDC (kubelogin), token SA | `exec: aws eks get-token` (podpisane zapytanie do AWS STS) |
| nazwa i grupy | z dowodu (`CN`/`O`, claimy OIDC) | z access entry (username, kubernetesGroups) |
| autoryzacja | RBAC | RBAC + access policies EKS (np. `AmazonEKSClusterAdminPolicy`) |

Access policies nie są obiektami w klastrze: nie zobaczysz ich w `kubectl get clusterrolebindings`, a `kubectl auth can-i --list` ostrzega, że lista może być niepełna. Stary ConfigMap `aws-auth` jest przestarzały; `k8s-sages` działa tylko na access entries. Szczegóły i porównanie krok po kroku: [uwierzytelnianie.html](uwierzytelnianie.html).
