#!/usr/bin/env bash
# Restore one scenario fixture into a KWOK cluster and write a config.json
# pointing the eval at it.
#
# Usage:
#   ./replay-fixture.sh <scenario-dir> <kwok-cluster-name>
#
# Example:
#   ./replay-fixture.sh tests/blackbox/data/test-cases/08_kyma_app_serverless_syntax_err kwok-eval
#
# The script creates the KWOK cluster if it does not already exist.
# On exit it prints the path to a config.json that the eval can consume:
#   CONFIG_PATH=<path> poetry run poe run-a2a-evaluation
#
# Prerequisites: kwokctl (v0.8.0+), kubectl, docker, python3 (with pyyaml)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# ---------------------------------------------------------------------------
# args
# ---------------------------------------------------------------------------

SCENARIO_DIR="${1:?Usage: $0 <scenario-dir> <kwok-cluster-name>}"
KWOK_CLUSTER="${2:?Usage: $0 <scenario-dir> <kwok-cluster-name>}"

# Resolve to absolute path so it stays valid after cd
SCENARIO_DIR="$(cd "$SCENARIO_DIR" && pwd)"

FIXTURE_DIR="$SCENARIO_DIR/fixture"
[[ -d "$FIXTURE_DIR" ]] || { echo "ERROR: fixture dir not found: $FIXTURE_DIR" >&2; exit 1; }

log()  { echo "[replay] $*" >&2; }
die()  { echo "[replay] ERROR: $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 0. Create KWOK cluster if it does not exist
# ---------------------------------------------------------------------------

if ! kwokctl get cluster --name "$KWOK_CLUSTER" &>/dev/null; then
    log "Creating KWOK cluster '$KWOK_CLUSTER'"
    kwokctl create cluster \
        --name "$KWOK_CLUSTER" \
        --enable-crds Logs,ClusterLogs \
        --disable kube-controller-manager,kube-scheduler
else
    log "KWOK cluster '$KWOK_CLUSTER' already exists — reusing."
fi

# kubectl pointed at the KWOK cluster
KWOK_KUBECONFIG_FILE=$(mktemp)
kwokctl get kubeconfig --name "$KWOK_CLUSTER" > "$KWOK_KUBECONFIG_FILE"
export KUBECONFIG="$KWOK_KUBECONFIG_FILE"

# ---------------------------------------------------------------------------
# python helpers (inline, keep deps minimal — only pyyaml)
# ---------------------------------------------------------------------------

# Shared helper prepended to every inline Python block that loads resources.yaml.
# kubectl -o yaml returns a single List object; kwokctl snapshot export returns
# multi-doc YAML. This flattens both into a plain list of resource dicts.
PY_FLATTEN=$(cat <<'PYEOF'
def _load_docs(path):
    import yaml
    with open(path) as _f:
        raw = list(yaml.safe_load_all(_f))
    out = []
    for doc in raw:
        if not doc:
            continue
        if doc.get('kind') == 'List':
            out.extend(item for item in doc.get('items', []) if item)
        else:
            out.append(doc)
    return out
PYEOF
)

PY_STRIP_OWNERREF=$(cat <<'PYEOF'
import sys, yaml, copy

def _load_docs(path):
    import yaml
    with open(path) as _f:
        raw = list(yaml.safe_load_all(_f))
    out = []
    for doc in raw:
        if not doc:
            continue
        if doc.get('kind') == 'List':
            out.extend(item for item in doc.get('items', []) if item)
        else:
            out.append(doc)
    return out

path = sys.argv[1]
out_path = sys.argv[2] if len(sys.argv) > 2 else path

docs = _load_docs(path)
stripped = []
for doc in docs:
    if doc is None:
        continue
    d = copy.deepcopy(doc)
    meta = d.get('metadata', {})
    if isinstance(meta, dict):
        meta.pop('ownerReferences', None)
        meta.pop('uid', None)
        meta.pop('resourceVersion', None)
        meta.pop('managedFields', None)
    stripped.append(d)

with open(out_path, 'w') as f:
    yaml.dump_all(stripped, f, default_flow_style=False, allow_unicode=True)
PYEOF
)

PY_EXTRACT_KIND=$(cat <<'PYEOF'
import sys, yaml

def _load_docs(path):
    import yaml
    with open(path) as _f:
        raw = list(yaml.safe_load_all(_f))
    out = []
    for doc in raw:
        if not doc:
            continue
        if doc.get('kind') == 'List':
            out.extend(item for item in doc.get('items', []) if item)
        else:
            out.append(doc)
    return out

kinds = set(sys.argv[2:]) if len(sys.argv) > 2 else set()
path = sys.argv[1]

docs = _load_docs(path)

out = [d for d in docs if d and d.get('kind') in kinds]
print(yaml.dump_all(out, default_flow_style=False, allow_unicode=True), end='')
PYEOF
)

PY_EXTRACT_NOT_KIND=$(cat <<'PYEOF'
import sys, yaml

def _load_docs(path):
    import yaml
    with open(path) as _f:
        raw = list(yaml.safe_load_all(_f))
    out = []
    for doc in raw:
        if not doc:
            continue
        if doc.get('kind') == 'List':
            out.extend(item for item in doc.get('items', []) if item)
        else:
            out.append(doc)
    return out

exclude = set(sys.argv[2:]) if len(sys.argv) > 2 else set()
path = sys.argv[1]

docs = _load_docs(path)

out = [d for d in docs if d and d.get('kind') not in exclude]
print(yaml.dump_all(out, default_flow_style=False, allow_unicode=True), end='')
PYEOF
)

# Convert raw log lines to kubelet log stream format:
# YYYY-MM-DDTHH:MM:SS.nnnnnnnnnZ stdout F <line>
# Uses the file mtime as a fake timestamp base.
PY_TO_KUBELET=$(cat <<'PYEOF'
import sys, datetime

src = sys.argv[1]
dst = sys.argv[2]

base = datetime.datetime(2026, 9, 16, 14, 32, 0)
with open(src) as fin, open(dst, 'w') as fout:
    for i, line in enumerate(fin):
        ts = base + datetime.timedelta(seconds=i)
        ts_str = ts.strftime('%Y-%m-%dT%H:%M:%S.') + '000000000Z'
        fout.write(f"{ts_str} stdout F {line.rstrip()}\n")
PYEOF
)

# Extract unique (kind, namespace, name) pairs for status patching
PY_EXTRACT_STATUSES=$(cat <<'PYEOF'
import sys, yaml, json

def _load_docs(path):
    import yaml
    with open(path) as _f:
        raw = list(yaml.safe_load_all(_f))
    out = []
    for doc in raw:
        if not doc:
            continue
        if doc.get('kind') == 'List':
            out.extend(item for item in doc.get('items', []) if item)
        else:
            out.append(doc)
    return out

path = sys.argv[1]
kinds = set(sys.argv[2:]) if len(sys.argv) > 2 else set()

docs = _load_docs(path)

out = []
for doc in docs:
    if not doc or doc.get('kind') not in kinds:
        continue
    status = doc.get('status')
    if not status:
        continue
    out.append({
        'kind': doc['kind'],
        'apiVersion': doc.get('apiVersion', ''),
        'namespace': doc.get('metadata', {}).get('namespace', ''),
        'name': doc.get('metadata', {}).get('name', ''),
        'status': status,
    })
print(json.dumps(out))
PYEOF
)

PY_EXTRACT_NODES=$(cat <<'PYEOF'
import sys, yaml, json

def _load_docs(path):
    import yaml
    with open(path) as _f:
        raw = list(yaml.safe_load_all(_f))
    out = []
    for doc in raw:
        if not doc:
            continue
        if doc.get('kind') == 'List':
            out.extend(item for item in doc.get('items', []) if item)
        else:
            out.append(doc)
    return out

path = sys.argv[1]

docs = _load_docs(path)

node_names = set()
for doc in docs:
    if not doc or doc.get('kind') != 'Pod':
        continue
    spec = doc.get('spec', {})
    node = spec.get('nodeName', '')
    if node:
        node_names.add(node)
print(json.dumps(sorted(node_names)))
PYEOF
)

PY_EXTRACT_PVCS=$(cat <<'PYEOF'
import sys, yaml, json

def _load_docs(path):
    import yaml
    with open(path) as _f:
        raw = list(yaml.safe_load_all(_f))
    out = []
    for doc in raw:
        if not doc:
            continue
        if doc.get('kind') == 'List':
            out.extend(item for item in doc.get('items', []) if item)
        else:
            out.append(doc)
    return out

path = sys.argv[1]

docs = _load_docs(path)

pvcs = []
for doc in docs:
    if not doc or doc.get('kind') != 'PersistentVolumeClaim':
        continue
    meta = doc.get('metadata', {})
    pvcs.append({
        'name': meta.get('name', ''),
        'namespace': meta.get('namespace', ''),
        'storage': doc.get('spec', {}).get('resources', {}).get('requests', {}).get('storage', '1Gi'),
        'storageClassName': doc.get('spec', {}).get('storageClassName', 'standard'),
        'accessModes': doc.get('spec', {}).get('accessModes', ['ReadWriteOnce']),
    })
print(json.dumps(pvcs))
PYEOF
)

# Extract pods that have ownerReferences (owned by Job/ReplicaSet/Function etc.)
PY_EXTRACT_OWNED_PODS=$(cat <<'PYEOF'
import sys, yaml

def _load_docs(path):
    import yaml
    with open(path) as _f:
        raw = list(yaml.safe_load_all(_f))
    out = []
    for doc in raw:
        if not doc:
            continue
        if doc.get('kind') == 'List':
            out.extend(item for item in doc.get('items', []) if item)
        else:
            out.append(doc)
    return out

path = sys.argv[1]

docs = _load_docs(path)

out = []
for doc in docs:
    if not doc or doc.get('kind') != 'Pod':
        continue
    if doc.get('metadata', {}).get('ownerReferences'):
        out.append(doc)

print(yaml.dump_all(out, default_flow_style=False, allow_unicode=True), end='')
PYEOF
)

# ---------------------------------------------------------------------------
# tmp workspace
# ---------------------------------------------------------------------------

TMPDIR_WORK=$(mktemp -d)
TMPDIR_LOGS=$(mktemp -d)
trap 'rm -rf "$TMPDIR_WORK"' EXIT

log "Working in $TMPDIR_WORK, logs in $TMPDIR_LOGS"

RESOURCES="$FIXTURE_DIR/resources.yaml"
EVENTS="$FIXTURE_DIR/events.yaml"
LOGS_DIR="$FIXTURE_DIR/logs"

# ---------------------------------------------------------------------------
# 1. Read namespace from resources
# ---------------------------------------------------------------------------

NS=$(python3 -c "
import yaml

def find_ns(doc):
    if not doc:
        return None
    # Try Namespace kind first
    if doc.get('kind') == 'Namespace':
        return doc['metadata']['name']
    # Recurse into List items
    if doc.get('kind') == 'List':
        # First pass: look for an explicit Namespace resource
        for item in doc.get('items', []):
            r = find_ns(item)
            if r:
                return r
        # Second pass: extract namespace from any namespaced resource
        for item in doc.get('items', []):
            if not item:
                continue
            ns = item.get('metadata', {}).get('namespace', '')
            if ns:
                return ns
    # Fallback: read namespace from metadata directly
    return doc.get('metadata', {}).get('namespace', '') or None

with open('$RESOURCES') as f:
    for doc in yaml.safe_load_all(f):
        ns = find_ns(doc)
        if ns:
            print(ns)
            break
")
[[ -n "$NS" ]] || die "Could not determine namespace from $RESOURCES"
log "Namespace: $NS"

# ---------------------------------------------------------------------------
# 1b. Ensure namespace exists in KWOK cluster
#     (kubectl get all,... does not export Namespace objects, so it must be
#     created explicitly before any namespaced resources can be applied)
# ---------------------------------------------------------------------------

log "Ensuring namespace $NS exists"
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f - 2>&1 | \
    while read -r line; do log "  $line"; done || true

# ---------------------------------------------------------------------------
# 2. Convert timestamps: update creationTimestamp to current time
#    (kwokctl snapshot restore rejects far-future timestamps)
# ---------------------------------------------------------------------------

NOW_NS=$(python3 -c "import time; print(int(time.time() * 1e9))")
log "Rebasing timestamps (now_ns=$NOW_NS)"

python3 - "$RESOURCES" "$TMPDIR_WORK/resources-rebased.yaml" "$NOW_NS" <<'PYEOF'
import sys, yaml, re, datetime


def _load_docs(path):
    import yaml
    with open(path) as _f:
        raw = list(yaml.safe_load_all(_f))
    out = []
    for doc in raw:
        if not doc:
            continue
        if doc.get('kind') == 'List':
            out.extend(item for item in doc.get('items', []) if item)
        else:
            out.append(doc)
    return out
src, dst, now_ns_str = sys.argv[1], sys.argv[2], sys.argv[3]
now_ns = int(now_ns_str)
now = datetime.datetime.utcfromtimestamp(now_ns / 1e9)

ORIG_BASE = None  # will detect from first timestamp

def rebase_ts(ts_str):
    global ORIG_BASE
    if not ts_str or not isinstance(ts_str, str):
        return ts_str
    m = re.match(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', ts_str)
    if not m:
        return ts_str
    try:
        dt = datetime.datetime.strptime(m.group(1), '%Y-%m-%dT%H:%M:%S')
    except ValueError:
        return ts_str
    if ORIG_BASE is None:
        ORIG_BASE = dt
    delta = dt - ORIG_BASE
    new_dt = now + delta
    return new_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

def walk(obj):
    if isinstance(obj, dict):
        return {k: (rebase_ts(v) if k.lower().endswith('time') or k == 'creationTimestamp' else walk(v))
                for k, v in obj.items()}
    elif isinstance(obj, list):
        return [walk(i) for i in obj]
    return obj

docs = _load_docs(src)

with open(dst, 'w') as f:
    yaml.dump_all([walk(d) for d in docs if d], f, default_flow_style=False, allow_unicode=True)
PYEOF

# ---------------------------------------------------------------------------
# 3. Apply non-problematic resources via kwokctl snapshot restore
#    Skip: Function, Subscription (Kyma CRs), Pods with ownerRefs
# ---------------------------------------------------------------------------

KYMA_KINDS="Function Subscription"
POD_KIND="Pod"

# Snapshot input: everything except Kyma CRs and pods-with-ownerRefs
# (owned pods cause ownerRef errors; we'll apply them separately)
python3 - "$TMPDIR_WORK/resources-rebased.yaml" \
    Function Subscription \
    > "$TMPDIR_WORK/resources-no-kyma.yaml" <<'PYEOF'
import sys, yaml, copy

def _load_docs(path):
    import yaml
    with open(path) as _f:
        raw = list(yaml.safe_load_all(_f))
    out = []
    for doc in raw:
        if not doc:
            continue
        if doc.get('kind') == 'List':
            out.extend(item for item in doc.get('items', []) if item)
        else:
            out.append(doc)
    return out

path = sys.argv[1]
exclude_kinds = set(sys.argv[2:])

docs = _load_docs(path)

out = []
for doc in docs:
    if not doc:
        continue
    kind = doc.get('kind', '')
    if kind in exclude_kinds:
        continue
    # For Pods with ownerRefs, strip the ownerRef for snapshot restore
    # (we'll patch status separately)
    d = copy.deepcopy(doc)
    if kind == 'Pod':
        d.get('metadata', {}).pop('ownerReferences', None)
        d.get('metadata', {}).pop('uid', None)
        d.get('metadata', {}).pop('resourceVersion', None)
        d.get('metadata', {}).pop('managedFields', None)
    else:
        meta = d.get('metadata', {})
        meta.pop('uid', None)
        meta.pop('resourceVersion', None)
        meta.pop('managedFields', None)
    out.append(d)

print(yaml.dump_all(out, default_flow_style=False, allow_unicode=True), end='')
PYEOF

log "Restoring snapshot (expecting and ignoring clusterIP/ownerRef errors)"
kwokctl snapshot restore \
    --name "$KWOK_CLUSTER" \
    --path "$TMPDIR_WORK/resources-no-kyma.yaml" \
    --format k8s 2>&1 | grep -v "^$" | while read -r line; do
        case "$line" in
            *"clusterIP"*|*"ownerReference"*|*"already exists"*) log "  (ignored) $line" ;;
            *) log "  $line" ;;
        esac
    done || true

# Apply pods separately via kubectl (kwokctl snapshot restore rejects pods when
# SA lookup fails; kubectl apply bypasses that admission validation on KWOK)
log "Applying pods via kubectl (bypassing KWOK SA lookup)"
python3 - "$TMPDIR_WORK/resources-rebased.yaml" "$NS" \
    > "$TMPDIR_WORK/pods-only.yaml" <<'PYEOF'
import sys, yaml, copy

def _load_docs(path):
    import yaml
    with open(path) as _f:
        raw = list(yaml.safe_load_all(_f))
    out = []
    for doc in raw:
        if not doc:
            continue
        if doc.get('kind') == 'List':
            out.extend(item for item in doc.get('items', []) if item)
        else:
            out.append(doc)
    return out

path, ns = sys.argv[1], sys.argv[2]
docs = _load_docs(path)
pods = []
for doc in docs:
    if not doc or doc.get('kind') != 'Pod':
        continue
    if doc.get('metadata', {}).get('namespace') != ns:
        continue
    d = copy.deepcopy(doc)
    meta = d.get('metadata', {})
    meta.pop('uid', None)
    meta.pop('resourceVersion', None)
    meta.pop('managedFields', None)
    d.pop('status', None)
    pods.append(d)
print(yaml.dump_all(pods, default_flow_style=False, allow_unicode=True), end='')
PYEOF

if [[ -s "$TMPDIR_WORK/pods-only.yaml" ]]; then
    kubectl apply -f "$TMPDIR_WORK/pods-only.yaml" 2>&1 | \
        while read -r line; do log "  $line"; done || true
fi

# ---------------------------------------------------------------------------
# 4. Apply Kyma CRs (Function, Subscription) without ownerRefs
# ---------------------------------------------------------------------------

python3 -c "
import sys, yaml, copy

PYEOF_INLINE='''$PY_STRIP_OWNERREF'''
" 2>/dev/null || true  # just a syntax check

log "Applying Kyma CRs (Function, Subscription)"
python3 - "$TMPDIR_WORK/resources-rebased.yaml" Function Subscription \
    > "$TMPDIR_WORK/kyma-crs.yaml" <<'PYEOF'
import sys, yaml, copy

def _load_docs(path):
    import yaml
    with open(path) as _f:
        raw = list(yaml.safe_load_all(_f))
    out = []
    for doc in raw:
        if not doc:
            continue
        if doc.get('kind') == 'List':
            out.extend(item for item in doc.get('items', []) if item)
        else:
            out.append(doc)
    return out

path = sys.argv[1]
wanted_kinds = set(sys.argv[2:])

docs = _load_docs(path)

out = []
for doc in docs:
    if not doc or doc.get('kind') not in wanted_kinds:
        continue
    d = copy.deepcopy(doc)
    meta = d.get('metadata', {})
    meta.pop('ownerReferences', None)
    meta.pop('uid', None)
    meta.pop('resourceVersion', None)
    meta.pop('managedFields', None)
    # Remove status from spec (apply only spec)
    d.pop('status', None)
    out.append(d)
print(yaml.dump_all(out, default_flow_style=False, allow_unicode=True), end='')
PYEOF

if [[ -s "$TMPDIR_WORK/kyma-crs.yaml" ]]; then
    kubectl apply -f "$TMPDIR_WORK/kyma-crs.yaml" --server-side=false 2>&1 | \
        while read -r line; do log "  $line"; done || true
fi

# ---------------------------------------------------------------------------
# 5. Patch CR status subresources
# ---------------------------------------------------------------------------

log "Patching Kyma CR statuses"
CR_STATUSES=$(python3 -c "$PY_FLATTEN
$PY_EXTRACT_STATUSES" \
    "$TMPDIR_WORK/resources-rebased.yaml" Function Subscription)
if [[ -n "$CR_STATUSES" && "$CR_STATUSES" != "[]" ]]; then
    PATCH_DATA="$CR_STATUSES" python3 <<'PYEOF'
import sys, json, os, subprocess

items = json.loads(os.environ['PATCH_DATA'])
for item in items:
    kind = item['kind']
    ns = item['namespace']
    name = item['name']
    status_patch = json.dumps({'status': item['status']})

    resource_map = {
        'Function': 'functions.serverless.kyma-project.io',
        'Subscription': 'subscriptions.eventing.kyma-project.io',
    }
    resource = resource_map.get(kind, kind.lower() + 's')

    cmd = [
        'kubectl', 'patch', resource, name,
        '-n', ns,
        '--subresource=status',
        '--type=merge',
        '-p', status_patch,
    ]
    print(f"  Patching {kind}/{name} status ...", file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  WARNING: {result.stderr.strip()}", file=sys.stderr)
PYEOF
else
    log "No Function/Subscription CRs with status found — skipping CR status patch."
fi

# ---------------------------------------------------------------------------
# 6. Apply owned pods (Job/Function/RS pods) without ownerRefs
#    Pods were already applied in step 3 (all pods stripped of ownerRefs)
#    This step patches their status.
# ---------------------------------------------------------------------------

log "Patching pod statuses"
POD_STATUSES=$(python3 -c "$PY_FLATTEN
$PY_EXTRACT_STATUSES" \
    "$TMPDIR_WORK/resources-rebased.yaml" Pod)
if [[ -n "$POD_STATUSES" && "$POD_STATUSES" != "[]" ]]; then
    PATCH_DATA="$POD_STATUSES" python3 <<'PYEOF'
import sys, json, os, subprocess

items = json.loads(os.environ['PATCH_DATA'])
for item in items:
    ns = item['namespace']
    name = item['name']
    status_patch = json.dumps({'status': item['status']})

    cmd = [
        'kubectl', 'patch', 'pod', name,
        '-n', ns,
        '--subresource=status',
        '--type=merge',
        '-p', status_patch,
    ]
    print(f"  Patching pod/{name} status ...", file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  WARNING: {result.stderr.strip()}", file=sys.stderr)
PYEOF
else
    log "No pods with status found — skipping pod status patch."
fi

# ---------------------------------------------------------------------------
# 7. Create fake nodes for any nodeName referenced by pods
# ---------------------------------------------------------------------------

log "Creating fake nodes"
FAKE_NODES=$(python3 -c "$PY_FLATTEN
$PY_EXTRACT_NODES" "$TMPDIR_WORK/resources-rebased.yaml")
if [[ -n "$FAKE_NODES" && "$FAKE_NODES" != "[]" ]]; then
    PATCH_DATA="$FAKE_NODES" python3 <<'PYEOF'
import sys, json, os, subprocess, yaml

node_names = json.loads(os.environ['PATCH_DATA'])
for node_name in node_names:
    node = {
        'apiVersion': 'v1',
        'kind': 'Node',
        'metadata': {
            'name': node_name,
            'annotations': {'kwok.x-k8s.io/node': 'fake'},
            'labels': {
                'beta.kubernetes.io/arch': 'amd64',
                'beta.kubernetes.io/os': 'linux',
                'kubernetes.io/arch': 'amd64',
                'kubernetes.io/hostname': node_name,
                'kubernetes.io/os': 'linux',
                'type': 'kwok',
            },
        },
        'spec': {},
    }
    node_yaml = yaml.dump(node, default_flow_style=False)
    cmd = ['kubectl', 'apply', '-f', '-']
    result = subprocess.run(cmd, input=node_yaml, capture_output=True, text=True)
    if result.returncode != 0 and 'already exists' not in result.stderr:
        print(f"  WARNING: node {node_name}: {result.stderr.strip()}", file=sys.stderr)
    else:
        print(f"  Node {node_name} ok", file=sys.stderr)
PYEOF
else
    log "No pod nodeName references found — skipping fake node creation."
fi

# ---------------------------------------------------------------------------
# 8. Create fake PVs and bind PVCs
# ---------------------------------------------------------------------------

log "Creating PVs and binding PVCs"
PVC_LIST=$(python3 -c "$PY_FLATTEN
$PY_EXTRACT_PVCS" "$TMPDIR_WORK/resources-rebased.yaml")
if [[ -n "$PVC_LIST" && "$PVC_LIST" != "[]" ]]; then
    PATCH_DATA="$PVC_LIST" python3 <<'PYEOF'
import sys, json, os, subprocess, yaml, uuid

pvcs = json.loads(os.environ['PATCH_DATA'])
for pvc in pvcs:
    name = pvc['name']
    ns = pvc['namespace']
    storage = pvc['storage']
    storage_class = pvc.get('storageClassName', 'standard')
    access_modes = pvc.get('accessModes', ['ReadWriteOnce'])

    pv_name = f"pv-{ns}-{name}"
    pv_uid = str(uuid.uuid4())

    pv = {
        'apiVersion': 'v1',
        'kind': 'PersistentVolume',
        'metadata': {'name': pv_name},
        'spec': {
            'capacity': {'storage': storage},
            'accessModes': access_modes,
            'persistentVolumeReclaimPolicy': 'Retain',
            'storageClassName': storage_class,
            'hostPath': {'path': f'/tmp/{pv_name}'},
            'claimRef': {'namespace': ns, 'name': name},
        },
    }

    pv_yaml = yaml.dump(pv, default_flow_style=False)
    r = subprocess.run(['kubectl', 'apply', '-f', '-'], input=pv_yaml, capture_output=True, text=True)
    if r.returncode != 0 and 'already exists' not in r.stderr:
        print(f"  WARNING: PV {pv_name}: {r.stderr.strip()}", file=sys.stderr)
    else:
        print(f"  PV {pv_name} ok", file=sys.stderr)

    r2 = subprocess.run(
        ['kubectl', 'get', 'pv', pv_name, '-o', 'jsonpath={.metadata.uid}'],
        capture_output=True, text=True
    )
    actual_uid = r2.stdout.strip() or pv_uid

    pvc_status = json.dumps({
        'status': {
            'phase': 'Bound',
            'accessModes': access_modes,
            'capacity': {'storage': storage},
        }
    })
    r3 = subprocess.run(
        ['kubectl', 'patch', 'pvc', name, '-n', ns,
         '--subresource=status', '--type=merge', '-p', pvc_status],
        capture_output=True, text=True
    )
    if r3.returncode != 0:
        print(f"  WARNING: PVC {name} status patch: {r3.stderr.strip()}", file=sys.stderr)
    else:
        print(f"  PVC {name} -> Bound ok", file=sys.stderr)
PYEOF
else
    log "No PVCs found — skipping PV/PVC setup."
fi

# ---------------------------------------------------------------------------
# 9. Convert logs to kubelet format
# ---------------------------------------------------------------------------

log "Converting logs to kubelet format -> $TMPDIR_LOGS"
if [[ -d "$LOGS_DIR" ]]; then
    for log_file in "$LOGS_DIR"/*.log; do
        [[ -f "$log_file" ]] || continue
        base=$(basename "$log_file")
        python3 - "$log_file" "$TMPDIR_LOGS/$base" <<'PYEOF'
import sys, datetime

src, dst = sys.argv[1], sys.argv[2]
base = datetime.datetime(2026, 9, 16, 14, 32, 0)
with open(src) as fin, open(dst, 'w') as fout:
    for i, line in enumerate(fin):
        ts = base + datetime.timedelta(seconds=i)
        ts_str = ts.strftime('%Y-%m-%dT%H:%M:%S.') + '000000000Z'
        fout.write(f"{ts_str} stdout F {line.rstrip()}\n")
PYEOF
    done
else
    log "No logs dir found at $LOGS_DIR, skipping log setup."
fi

# ---------------------------------------------------------------------------
# 10+11. Mount log dir into kwok-controller container
# ---------------------------------------------------------------------------

KWOK_CONTAINER="kwok-${KWOK_CLUSTER}-kwok-controller"
log "Remounting logs into $KWOK_CONTAINER"

# Get current docker run args for the controller container
CURRENT_IMAGE=$(docker inspect "$KWOK_CONTAINER" --format '{{.Config.Image}}' 2>/dev/null || true)
if [[ -z "$CURRENT_IMAGE" ]]; then
    log "WARNING: cannot find container $KWOK_CONTAINER — skipping log mount."
    log "  (If the container name is different, remount manually.)"
else
    # Extract original run args via docker inspect
    ORIG_CMD=$(docker inspect "$KWOK_CONTAINER" --format '{{json .Config.Cmd}}' 2>/dev/null || echo '[]')
    ORIG_ENTRYPOINT=$(docker inspect "$KWOK_CONTAINER" --format '{{json .Config.Entrypoint}}' 2>/dev/null || echo '[]')

    # We need to recreate the container with the log volume.
    # kwokctl manages the container — we do: stop, rm, docker run with same args + new -v
    log "  Stopping $KWOK_CONTAINER"
    docker stop "$KWOK_CONTAINER" >/dev/null 2>&1 || true
    docker rm "$KWOK_CONTAINER" >/dev/null 2>&1 || true

    # Reconstruct run command using kwok.yaml pattern from kwokctl work dir
    KWOK_WORKDIR="$HOME/.kwok/clusters/$KWOK_CLUSTER"
    if [[ -f "$KWOK_WORKDIR/kwok.yaml" ]]; then
        log "  Restarting with log mount using kwok.yaml"
        kwokctl start cluster --name "$KWOK_CLUSTER" 2>&1 | while read -r line; do log "  $line"; done || true
        # Stop just the controller, add volume, restart
        docker stop "$KWOK_CONTAINER" >/dev/null 2>&1 || true
        docker rm "$KWOK_CONTAINER" >/dev/null 2>&1 || true
    fi

    # Build run command from scratch using the image and kwok config
    KWOK_CONFIG="$KWOK_WORKDIR/kwok.yaml"
    if [[ -f "$KWOK_CONFIG" ]]; then
        # Extract original docker run args from kwok cluster config
        python3 - "$KWOK_CONFIG" "$KWOK_CONTAINER" "$CURRENT_IMAGE" "$TMPDIR_LOGS" "$KWOK_WORKDIR" <<'PYEOF'
import sys, yaml, subprocess, os

config_path, container_name, image, logs_dir, workdir = sys.argv[1:]

with open(config_path) as f:
    # kwok.yaml is a multi-doc YAML; the cluster config is in the first doc
    docs = list(yaml.safe_load_all(f))
config = docs[0] if docs else {}

# Find the kwok-controller component config
components = config.get('components', [])
controller_args = []
controller_envs = []
controller_volumes = []

for comp in components:
    if 'kwok-controller' in comp.get('name', ''):
        controller_args = comp.get('command', []) + comp.get('args', [])
        controller_envs = comp.get('envs', [])
        controller_volumes = comp.get('volumes', [])
        break

# Build docker run command
cmd = ['docker', 'run', '-d', '--name', container_name, '--restart=unless-stopped']

# Add network — kwokctl names it kwok-<cluster-name>
# container_name is kwok-<cluster>-kwok-controller; strip the trailing -kwok-controller
network_name = '-'.join(container_name.split('-')[:-2])  # kwok-<cluster>
cmd += ['--network', network_name]

# Add existing volumes
for vol in controller_volumes:
    host = vol.get('hostPath', '') if isinstance(vol.get('hostPath'), str) else vol.get('hostPath', {}).get('path', '')
    mount = vol.get('mountPath', '')
    if host and mount:
        cmd += ['-v', f'{host}:{mount}']

# Add our log directory
cmd += ['-v', f'{logs_dir}:/kwok-logs:ro']

# Add env vars
for env in controller_envs:
    cmd += ['-e', f"{env['name']}={env.get('value', '')}"]

cmd += [image] + controller_args

print(' '.join(f'"{a}"' if ' ' in a else a for a in cmd), file=sys.stderr)
result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    print(f"docker run failed: {result.stderr}", file=sys.stderr)
    sys.exit(1)
print(f"Container restarted: {result.stdout.strip()}", file=sys.stderr)
PYEOF
    else
        log "  WARNING: $KWOK_CONFIG not found — cannot auto-remount logs."
        log "  Mount manually: docker run ... -v $TMPDIR_LOGS:/kwok-logs:ro ..."
    fi
fi

# ---------------------------------------------------------------------------
# 12. Create kwok Logs objects
# ---------------------------------------------------------------------------

log "Creating Logs CRs"
python3 - "$TMPDIR_WORK/resources-rebased.yaml" "$NS" <<'PYEOF'
import sys, yaml, json, subprocess, os


def _load_docs(path):
    import yaml
    with open(path) as _f:
        raw = list(yaml.safe_load_all(_f))
    out = []
    for doc in raw:
        if not doc:
            continue
        if doc.get('kind') == 'List':
            out.extend(item for item in doc.get('items', []) if item)
        else:
            out.append(doc)
    return out
resources_path, ns = sys.argv[1], sys.argv[2]
logs_dir = '/kwok-logs'  # path inside kwok-controller container

docs = _load_docs(resources_path)

# Collect all pods and their containers
pods = {}
for doc in docs:
    if not doc or doc.get('kind') != 'Pod':
        continue
    name = doc.get('metadata', {}).get('name', '')
    if not name:
        continue
    containers = []
    spec = doc.get('spec', {})
    for c in spec.get('containers', []):
        if c.get('name'):
            containers.append(c['name'])
    for c in spec.get('initContainers', []):
        if c.get('name'):
            containers.append(c['name'])
    pods[name] = containers

for pod_name, containers in pods.items():
    if not containers:
        continue

    logs_spec = []
    for container in containers:
        entry = {
            'containers': [container],
            'logsFile': f'{logs_dir}/{pod_name}__{container}.log',
        }
        prev_path = f'{logs_dir}/{pod_name}__{container}__previous.log'
        # Always set previousLogsFile; kwok serves 404 if file missing, which is fine
        entry['previousLogsFile'] = prev_path
        logs_spec.append(entry)

    logs_obj = {
        'apiVersion': 'kwok.x-k8s.io/v1alpha1',
        'kind': 'Logs',
        'metadata': {
            'name': pod_name,
            'namespace': ns,
        },
        'spec': {
            'logs': logs_spec,
        },
    }
    logs_yaml = yaml.dump(logs_obj, default_flow_style=False)
    r = subprocess.run(['kubectl', 'apply', '-f', '-'], input=logs_yaml, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  WARNING: Logs/{pod_name}: {r.stderr.strip()}", file=sys.stderr)
    else:
        print(f"  Logs/{pod_name} ok", file=sys.stderr)
PYEOF

# ---------------------------------------------------------------------------
# 13. Write config.json for the eval
#     Uses cert auth (TEST_CLUSTER_CLIENT_CERT/KEY); TOKEN left empty.
#     Merges non-cluster keys from the repo's config/config.json.
# ---------------------------------------------------------------------------

export REPO_ROOT
KWOK_CONFIG_JSON=$(mktemp -t kwok-config.XXXXXX).json

python3 - "$KWOK_KUBECONFIG_FILE" "$KWOK_CONFIG_JSON" <<'PYEOF'
import sys, yaml, json, os

kubeconfig_path, out_path = sys.argv[1], sys.argv[2]

with open(kubeconfig_path) as f:
    kc = yaml.safe_load(f)

cluster = kc['clusters'][0]['cluster']
user = kc['users'][0]['user']

# Pull in the original config.json for non-cluster keys (model, redis, companion URL, etc.)
repo_root = os.environ.get('REPO_ROOT', '.')
base_config_path = os.path.join(repo_root, 'config', 'config.json')
base = {}
if os.path.exists(base_config_path):
    with open(base_config_path) as f:
        base = json.load(f)

base['TEST_CLUSTER_URL'] = cluster['server']
base['TEST_CLUSTER_CA_DATA'] = cluster.get('certificate-authority-data', '')
base['TEST_CLUSTER_AUTH_TOKEN'] = ''
base['TEST_CLUSTER_CLIENT_CERT'] = user.get('client-certificate-data', '')
base['TEST_CLUSTER_CLIENT_KEY'] = user.get('client-key-data', '')

with open(out_path, 'w') as f:
    json.dump(base, f, indent=2)
PYEOF

log "config.json written to: $KWOK_CONFIG_JSON"

# ---------------------------------------------------------------------------
# 14. Digital-twin validation
#     Send each query from scenario.yml to the companion and score against
#     the scenario's expectations using the same deepeval GEval scorer.
# ---------------------------------------------------------------------------

VALIDATE_SCRIPT="$SCRIPT_DIR/validate-fixture.py"
if [[ -f "$VALIDATE_SCRIPT" ]]; then
    log "Running digital-twin validation against KWOK cluster"
    if cd "$REPO_ROOT/tests/blackbox" && \
       poetry run python "$VALIDATE_SCRIPT" \
           --scenario "$SCENARIO_DIR" \
           --config "$KWOK_CONFIG_JSON"; then
        log "Digital-twin validation: PASS"
    else
        log "Digital-twin validation: FAIL — KWOK fixture does not reproduce expected companion answers"
        log "  Check the output above for which expectations failed."
        log "  The fixture may need to be re-recorded or the replay script debugged."
    fi
else
    log "WARNING: validate-fixture.py not found at $VALIDATE_SCRIPT — skipping validation."
fi

# ---------------------------------------------------------------------------
# done
# ---------------------------------------------------------------------------

log "Replay complete for namespace $NS in cluster $KWOK_CLUSTER"
log "Log files are in: $TMPDIR_LOGS"
log "  (This directory must persist while the kwok-controller container is running.)"
log ""
log "Verify cluster state:"
log "  kubectl get all -n $NS"
log "  kubectl logs <pod> -n $NS -c <container>"
log ""
log "Run the eval against this fixture:"
log "  cd $REPO_ROOT/tests/blackbox"
log "  CONFIG_PATH=$KWOK_CONFIG_JSON poetry run poe run-a2a-evaluation"
log ""
log "Kubeconfig: $KWOK_KUBECONFIG_FILE"
log "Config:     $KWOK_CONFIG_JSON"
