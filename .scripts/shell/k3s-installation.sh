#! /bin/bash
# K3s installation
curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="v1.27.4+k3s1" K3S_KUBECONFIG_MODE=644 INSTALL_K3S_EXEC="server --docker --disable traefik" sh -
mkdir -p ~/.kube
cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
chmod 600 ~/.kube/config
