#!/usr/bin/env bash
# Supply-chain and image checks for kyma-docs-search. Fails on any finding.
#   go mod verify         module checksums match go.sum
#   govulncheck ./...     Go vulnerability DB, only vulnerabilities in code paths this binary actually calls
#   docker build          static, stripped binary in a FROM scratch image, non-root user
#   trivy image           OS packages (none), Go modules embedded in the binary, secrets, misconfiguration
#   govulncheck binary    the same check on the artifact that ships, not on the source tree
set -euo pipefail
cd "$(dirname "$0")/.."
IMAGE=${IMAGE:-kyma-docs-search:local}

echo "== go mod verify";        go mod verify
echo "== govulncheck (source)"; govulncheck ./...
echo "== docker build";         docker build -q -t "$IMAGE" . >/dev/null
docker image inspect "$IMAGE" --format 'image: {{.Size}} bytes, user {{.Config.User}}, {{len .RootFS.Layers}} layers'
echo "== trivy image";          trivy image --quiet --exit-code 1 --scanners vuln,secret,misconfig \
                                  --severity UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL "$IMAGE"
echo "== govulncheck (binary)"
CID=$(docker create "$IMAGE"); TMP=$(mktemp -d)
docker cp "$CID:/kyma-docs-search" "$TMP/kyma-docs-search" >/dev/null; docker rm "$CID" >/dev/null
govulncheck -mode=binary "$TMP/kyma-docs-search"
echo "== modules in the shipped binary"
go version -m "$TMP/kyma-docs-search" | awk '$1=="dep"{print "  " $2, $3}'
rm -rf "$TMP"
echo "all checks passed"
