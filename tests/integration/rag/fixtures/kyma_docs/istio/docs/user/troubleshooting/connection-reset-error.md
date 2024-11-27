### Problem
You receive a 'Connection reset by peer' error when attempting to establish a connection between a service without a sidecar and a service with a sidecar.

### Cause
This error occurs because mutual TLS (mTLS) is enabled by default in the service mesh, requiring every element to have an Istio sidecar with a valid TLS certificate for communication.

### Solution
1. **Add the service without a sidecar to the allowlist and disable mTLS traffic for it**:
   - Create a `DestinationRule` resource.
   - Refer to the [DestinationRule documentation](https://istio.io/docs/reference/config/networking/destination-rule/) for details.

2. **Allow connections between the service without a sidecar and the service with a sidecar**:
   - Create a `PeerAuthentication` resource in `PERMISSIVE` mode.
   - Refer to the [Peer Authentication documentation](https://istio.io/latest/docs/reference/config/security/peer_authentication/) for details.