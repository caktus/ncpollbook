# Deployment

This document covers deploying NC Pollbook to a Kubernetes cluster on a Framework Desktop (or similar bare-metal host) using MicroK8s, Ansible, and Helm.

- [Deployment](#deployment)
  - [Building and Testing the Production Image Locally](#building-and-testing-the-production-image-locally)
  - [Prerequisites](#prerequisites)
  - [Initial Host Setup](#initial-host-setup)
  - [Install kubectl and Helm](#install-kubectl-and-helm)
  - [Deploy PostgreSQL](#deploy-postgresql)
  - [Deploy Cloudflare Ingress and Traefik](#deploy-cloudflare-ingress-and-traefik)
  - [Deploy the ncpollbook app](#deploy-the-ncpollbook-app)
    - [Management commands](#management-commands)
  - [Deploy LibreChat](#deploy-librechat)
  - [Cloudflare DNS (manual steps)](#cloudflare-dns-manual-steps)

## Building and Testing the Production Image Locally

Build and test the production image locally using the deploy compose file:

```bash
# Build the production image
COMPOSE_FILE=docker-compose.deploy.yaml docker compose build

# Start the stack (web + PostgreSQL) using the deploy env file
COMPOSE_FILE=docker-compose.deploy.yaml docker compose up -d
```

Edit `docker-compose.deploy.env` to set `DJANGO_SECRET_KEY`, database credentials,
and any model provider API keys before deploying.

## Prerequisites

- A bare-metal or VM host reachable via SSH (default hostname: `ncpollbook`)
- [Ansible](https://docs.ansible.com/ansible/latest/installation_guide/) installed locally
- `bin/kubectl` and `bin/helm` (see [Install kubectl and Helm](#install-kubectl-and-helm))
- Ansible Vault password configured (e.g. via `deployment/echo-vault-pass.sh`)

Install Ansible roles:

```sh
cd deployment/
ansible-galaxy install -f -r requirements.yaml
```

## Initial Host Setup

Provision the VM and configure Tailscale:

```sh
ssh framework1
multipass launch --name ncpollbook --cpus=16 --memory=32G --disk=200G
multipass shell ncpollbook
```

Add the host to the Tailscale admin console, then locally:

```sh
echo "export KUBECONFIG=$PWD/deployment/.kube/config-ncpollbook" >> .envrc
direnv allow
```

Install MicroK8s and retrieve the kubeconfig:

```sh
cd deployment/
ansible-playbook setup.yaml --tags microk8s
```

See also:
- https://canonical.com/microk8s/docs/ref-launch-config
- https://canonical.com/microk8s/docs/add-launch-config

## Install kubectl and Helm

```sh
export KUBECTL_VERSION=1.35.3
curl -sLO "https://dl.k8s.io/release/v$KUBECTL_VERSION/bin/darwin/arm64/kubectl"
chmod +x ./kubectl
mv ./kubectl bin
```

```sh
export HELM_VERSION=4.1.4
curl -LO "https://get.helm.sh/helm-v$HELM_VERSION-darwin-arm64.tar.gz"
tar -zxf helm*.tar.gz
mv ./darwin-arm64/helm bin/
rm -r darwin-arm64/ helm-v4.1.4-darwin-arm64.tar.gz
```

## Deploy PostgreSQL

Encrypt the database password and set it in `deployment/group_vars/all.yaml`:

```sh
# From the deployment/ directory:
pwgen -s 32 1 | tr -d '\n' | ansible-vault encrypt_string  # database_password
```

Then deploy:

```sh
ansible-playbook setup.yaml --tags postgres
```

## Deploy Cloudflare Ingress and Traefik

```sh
ansible-playbook setup.yaml --tags cloudflare-ingress
```

## Deploy the ncpollbook app

Encrypt the required secrets and set them in `deployment/group_vars/k8s_api.yaml`.

Then deploy:

```sh
ansible-playbook setup.yaml --tags app
```

### Management commands

Once the app is deployed, you can run management commands like so:

```sh
# Create a superuser
kubectl -n ncpollbook exec -it deploy/ncpollbook -c ncpollbook -- python manage.py createsuperuser
# Load initial data
kubectl -n ncpollbook exec -it deploy/ncpollbook -c ncpollbook -- python manage.py loaddata agent_models
# Sync pgviews
kubectl -n ncpollbook exec -it deploy/ncpollbook -c ncpollbook -- python manage.py sync_pgviews
# Import NCSBE data
kubectl -n ncpollbook exec -it deploy/ncpollbook -c ncpollbook -- python manage.py ncsbe etl
```

## Deploy LibreChat

Encrypt the required secrets and set them in `deployment/group_vars/k8s_api.yaml`.

Then deploy:

```sh
ansible-playbook setup.yaml --tags librechat
```

## Cloudflare DNS (manual steps)

The Cloudflare Tunnel ingress controller automatically registers the tunnel and updates the DNS records.
