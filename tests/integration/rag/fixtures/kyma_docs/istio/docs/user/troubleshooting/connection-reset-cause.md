# Cause

You get a 'Connection reset by peer' error when attempting to establish a connection between a service without a sidecar and a service with a sidecar. This error is typically caused by the default mutual TLS (mTLS) being enabled in the service mesh, which requires every element to have an Istio sidecar with a valid TLS certificate for communication.