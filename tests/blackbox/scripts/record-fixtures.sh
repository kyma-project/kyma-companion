#!/usr/bin/env bash
# Record K8s state for all scenarios that have a fixture predicate.
# Run against the live eval cluster.
#
# Usage:
#   export KUBECONFIG=/path/to/kubeconfig   # or uses default
#   ./record-fixtures.sh [scenario-dir]     # one dir, or all if omitted
#
# Writes output to tests/blackbox/data/test-cases/<scenario>/fixture/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
TEST_CASES_DIR="$REPO_ROOT/tests/blackbox/data/test-cases"
PREDICATE_TIMEOUT=${PREDICATE_TIMEOUT:-300}  # seconds

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

rlog() { echo "[record] $*" >&2; }
die()  { echo "[record] ERROR: $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# kubeconfig — build from config.json if KUBECONFIG is not already set
# ---------------------------------------------------------------------------

CONFIG_JSON="${CONFIG_PATH:-$REPO_ROOT/config/config.json}"

if [[ -z "${KUBECONFIG:-}" ]]; then
    [[ -f "$CONFIG_JSON" ]] || die "No KUBECONFIG set and no config.json at $CONFIG_JSON"
    KUBECONFIG=$(python3 - "$CONFIG_JSON" <<'PYEOF'
import sys, json, base64, tempfile

config_path = sys.argv[1]
with open(config_path) as f:
    c = json.load(f)

url    = c.get('TEST_CLUSTER_URL', '')
ca_b64 = c.get('TEST_CLUSTER_CA_DATA', '')
token  = c.get('TEST_CLUSTER_AUTH_TOKEN', '')
cert   = c.get('TEST_CLUSTER_CLIENT_CERT', '')
key    = c.get('TEST_CLUSTER_CLIENT_KEY', '')

if not url:
    print("ERROR: TEST_CLUSTER_URL missing in config.json", file=sys.stderr)
    sys.exit(1)

ca_file = tempfile.NamedTemporaryFile(delete=False, suffix='.crt', mode='wb')
ca_file.write(base64.b64decode(ca_b64))
ca_file.close()

if cert and key:
    user_block = f"    client-certificate-data: {cert}\n    client-key-data: {key}"
else:
    user_block = f"    token: {token}"

kc = f"""apiVersion: v1
kind: Config
clusters:
- cluster:
    server: {url}
    certificate-authority: {ca_file.name}
  name: eval-cluster
contexts:
- context:
    cluster: eval-cluster
    user: eval
  name: eval-cluster
current-context: eval-cluster
users:
- name: eval
  user:
{user_block}
"""
kc_file = tempfile.NamedTemporaryFile(delete=False, suffix='.yaml', mode='w')
kc_file.write(kc)
kc_file.close()
print(kc_file.name)
PYEOF
)
    export KUBECONFIG
    rlog "Built kubeconfig from $CONFIG_JSON -> $KUBECONFIG"
fi

# Parse a yaml value by key (simple grep-based, good enough for flat scalar fields).
yaml_value() {
    local file="$1" key="$2"
    grep -E "^\s*${key}:" "$file" | head -1 | sed 's/.*: *//' | tr -d '"' | awk '{print $1}'
}

# Parse nested yaml: fixture.namespace / fixture.predicate.*
fixture_field() {
    local file="$1" field="$2"
    # Print lines from "fixture:" block, find the field
    awk '/^fixture:/{found=1} found{print}' "$file" | grep -E "^\s+${field}:" | head -1 \
        | sed 's/.*: *//' | tr -d '"' | awk '{print $1}'
}

# Strip volatile fields from a kubectl yaml dump via python3.
strip_volatile() {
    python3 - "$@" <<'PYEOF'
import sys, yaml

def strip(obj):
    if not isinstance(obj, dict):
        return obj
    obj.pop('managedFields', None)
    meta = obj.get('metadata', {})
    if isinstance(meta, dict):
        meta.pop('uid', None)
        meta.pop('resourceVersion', None)
        # keep creationTimestamp on non-Event resources
    spec = obj.get('spec', {})
    if isinstance(spec, dict) and obj.get('kind') == 'Service':
        spec.pop('clusterIP', None)
        spec.pop('clusterIPs', None)
    # strip creationTimestamp from Event metadata (keep on resources)
    if obj.get('kind') == 'Event':
        if isinstance(meta, dict):
            meta.pop('creationTimestamp', None)
    for v in obj.values():
        if isinstance(v, dict):
            strip(v)
        elif isinstance(v, list):
            for item in v:
                strip(item)
    return obj

path = sys.argv[1]
with open(path) as f:
    content = f.read()

docs = list(yaml.safe_load_all(content))
out = []
for doc in docs:
    if doc is None:
        continue
    out.append(strip(doc))

with open(path, 'w') as f:
    yaml.dump_all(out, f, default_flow_style=False, allow_unicode=True)
PYEOF
}

# Wait until a predicate is satisfied or timeout is reached.
# predicate format: "kind=Pod name=foo condition=restartCount>=2"
wait_for_predicate() {
    local ns="$1" kind="$2" name="$3" condition="$4"
    local deadline=$(( $(date +%s) + PREDICATE_TIMEOUT ))
    rlog "Waiting for $kind/$name in $ns: $condition (timeout ${PREDICATE_TIMEOUT}s)"

    while [[ $(date +%s) -lt $deadline ]]; do
        if check_predicate "$ns" "$kind" "$name" "$condition"; then
            rlog "Predicate satisfied."
            return 0
        fi
        sleep 10
    done
    rlog "WARNING: predicate timed out after ${PREDICATE_TIMEOUT}s — recording state anyway."
    return 0
}

check_predicate() {
    local ns="$1" kind="$2" name="$3" cond="$4"

    case "$cond" in
        'restartCount>=*'|restartCount\>=*)
            local threshold
            threshold="${cond#*>=}"
            local count
            count=$(kubectl get pod "$name" -n "$ns" -o jsonpath='{.status.containerStatuses[*].restartCount}' 2>/dev/null \
                | tr ' ' '\n' | sort -rn | head -1 || echo 0)
            [[ "${count:-0}" -ge "$threshold" ]]
            ;;
        phase=*)
            local want="${cond#phase=}"
            local got
            got=$(kubectl get "$kind" "$name" -n "$ns" -o jsonpath='{.status.phase}' 2>/dev/null || echo "")
            [[ "$got" == "$want" ]]
            ;;
        status.ready=false)
            case "$kind" in
                Deployment)
                    # Deployment is "not ready" when availableReplicas < replicas, or Available condition is False
                    local avail
                    avail=$(kubectl get deployment "$name" -n "$ns" \
                        -o jsonpath='{.status.conditions[?(@.type=="Available")].status}' 2>/dev/null || echo "")
                    [[ "$avail" == "False" ]]
                    ;;
                Function|Subscription)
                    local ready
                    ready=$(kubectl get "$kind" "$name" -n "$ns" \
                        -o jsonpath='{.status.conditions[?(@.type=="Running")].status}' 2>/dev/null || echo "")
                    # Not ready if Running condition is absent or False
                    [[ -z "$ready" || "$ready" == "False" ]]
                    ;;
                PersistentVolumeClaim)
                    local phase
                    phase=$(kubectl get pvc "$name" -n "$ns" -o jsonpath='{.status.phase}' 2>/dev/null || echo "")
                    [[ "$phase" != "Bound" ]]
                    ;;
                *)
                    local ready
                    ready=$(kubectl get "$kind" "$name" -n "$ns" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "")
                    [[ "$ready" == "False" ]]
                    ;;
            esac
            ;;
        reason=*)
            local want="${cond#reason=}"
            local got
            got=$(kubectl get pod "$name" -n "$ns" -o jsonpath='{.status.containerStatuses[0].state.waiting.reason}' 2>/dev/null || echo "")
            [[ "$got" == "$want" ]]
            ;;
        *)
            rlog "Unknown predicate format: $cond — skipping wait"
            return 0
            ;;
    esac
}

record_scenario() {
    local dir="$1"
    local scenario_id
    scenario_id=$(basename "$dir")
    local scenario_yml="$dir/scenario.yml"

    [[ -f "$scenario_yml" ]] || { rlog "No scenario.yml in $dir, skipping."; return 0; }

    # Check for fixture block
    local ns
    ns=$(fixture_field "$scenario_yml" "namespace")
    [[ -n "$ns" ]] || { rlog "$scenario_id: no fixture.namespace — pure question scenario, skipping."; return 0; }

    local pred_kind pred_name pred_condition
    pred_kind=$(fixture_field "$scenario_yml" "kind")
    pred_name=$(fixture_field "$scenario_yml" "name")
    pred_condition=$(fixture_field "$scenario_yml" "condition")

    rlog "=== Recording $scenario_id (namespace: $ns) ==="

    # 1. Undeploy first to guarantee a clean state (GC may have mutated resources)
    if [[ -f "$dir/undeploy.sh" ]]; then
        rlog "Undeploying previous state"
        (cd "$dir" && bash undeploy.sh) 2>&1 | while read -r line; do rlog "  undeploy: $line"; done || true
        # Wait for namespace to be fully gone before reapplying
        local deadline=$(( $(date +%s) + 120 ))
        while kubectl get namespace "$ns" &>/dev/null; do
            [[ $(date +%s) -lt $deadline ]] || { rlog "WARNING: namespace $ns did not terminate in 120s — continuing anyway."; break; }
            rlog "  Waiting for namespace $ns to terminate..."
            sleep 5
        done
    fi

    # 2. Apply deployment (fresh state)
    local deploy_yml="$dir/deployment.yml"
    if [[ -f "$deploy_yml" ]]; then
        rlog "Applying $deploy_yml"
        kubectl apply -f "$deploy_yml"
    else
        rlog "No deployment.yml found — assuming already deployed."
    fi

    # 3. Wait for predicate
    if [[ -n "$pred_kind" && -n "$pred_name" && -n "$pred_condition" ]]; then
        wait_for_predicate "$ns" "$pred_kind" "$pred_name" "$pred_condition"
    else
        rlog "No predicate defined — waiting 30s for resources to settle."
        sleep 30
    fi

    # 4+5. Export resources + events
    local fixture_dir="$dir/fixture"
    mkdir -p "$fixture_dir/logs"

    local resources_raw="$fixture_dir/resources.yaml.tmp"
    rlog "Exporting resources from $ns"
    kubectl get \
        all,pvc,pv,configmap,secret,serviceaccount,role,rolebinding,clusterrole,clusterrolebinding,\
functions.serverless.kyma-project.io,subscriptions.eventing.kyma-project.io \
        -n "$ns" -o yaml > "$resources_raw" 2>/dev/null || true

    rlog "Exporting events from $ns"
    kubectl get events -n "$ns" -o yaml > "$fixture_dir/events.yaml.tmp" 2>/dev/null || true

    # 5. Export logs
    rlog "Exporting pod logs from $ns"
    local pods
    pods=$(kubectl get pods -n "$ns" -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")
    for pod in $pods; do
        local containers
        containers=$(kubectl get pod "$pod" -n "$ns" \
            -o jsonpath='{range .spec.containers[*]}{.name}{"\n"}{end}{range .spec.initContainers[*]}{.name}{"\n"}{end}' \
            2>/dev/null || echo "")
        for container in $containers; do
            [[ -z "$container" ]] && continue
            rlog "  Logs: $pod / $container"
            kubectl logs "$pod" -n "$ns" -c "$container" \
                > "$fixture_dir/logs/${pod}__${container}.log" 2>/dev/null || true
            kubectl logs "$pod" -n "$ns" -c "$container" --previous \
                > "$fixture_dir/logs/${pod}__${container}__previous.log" 2>/dev/null || true
            # Remove empty previous rlog files
            [[ -s "$fixture_dir/logs/${pod}__${container}__previous.log" ]] || \
                rm -f "$fixture_dir/logs/${pod}__${container}__previous.log"
        done
    done

    # 6. Strip volatile fields
    rlog "Stripping volatile fields"
    cp "$resources_raw" "$fixture_dir/resources.yaml"
    cp "$fixture_dir/events.yaml.tmp" "$fixture_dir/events.yaml"
    strip_volatile "$fixture_dir/resources.yaml"
    strip_volatile "$fixture_dir/events.yaml"
    rm -f "$resources_raw" "$fixture_dir/events.yaml.tmp"

    # 7. Write metadata
    local git_hash k8s_version
    git_hash=$(git -C "$dir" rlog -1 --format="%H" -- deployment.yml 2>/dev/null || echo "unknown")
    k8s_version=$(kubectl version --output=json 2>/dev/null | python3 -c "import sys,json; v=json.load(sys.stdin); print(v.get('serverVersion',{}).get('gitVersion','unknown'))" 2>/dev/null || echo "unknown")
    python3 -c "
import json, datetime
meta = {
    'deployment_yml_git_hash': '$git_hash',
    'k8s_server_version': '$k8s_version',
    'captured_at': datetime.datetime.utcnow().isoformat() + 'Z',
    'scenario_id': '$scenario_id',
    'namespace': '$ns',
}
print(json.dumps(meta, indent=2))
" > "$fixture_dir/metadata.json"

    rlog "Done: $fixture_dir"
}

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

if [[ $# -ge 1 ]]; then
    record_scenario "$1"
else
    for dir in "$TEST_CASES_DIR"/*/; do
        record_scenario "$dir" || rlog "WARNING: failed on $dir, continuing."
    done
fi

rlog "All scenarios processed."
