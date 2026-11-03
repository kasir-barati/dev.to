---
title: "Kubernetes cheatsheet"
published: true
description: "My cheatsheet for Kubernetes."
tags:
  - kubernetes
  - pods
  - cheatsheet
  - cli
cover_image: "https://raw.githubusercontent.com/kasir-barati/dev.to/refs/heads/main/articles/assets/iac/cover.png"
series: Iac
---

## Manage Pods

In Kubernetes we can have clusters, if we run these commands they will target the default cluster. For more info about clusters you can look at [cluster](#cluster) section

```bash
kubectl get pods -A                 # all namespaces
kubectl get pods -n <namespace>     # one namespace
kubectl get pods -A -o wide         # with node and IP
kubectl get pods -A -w              # watch for changes
```

## Cluster

A Kubernetes cluster is a set of machines/nodes that run your containerized workloads, managed as one unit. It has two parts:

- Control plane: the API server, scheduler, and etcd. It stores the desired state and decides which pod runs where.
- Worker nodes: the machines that run the pods, each with a kubelet and a container runtime.

You describe what you want (deployments, services), and the cluster keeps reality matching it.

[`kind` ("Kubernetes IN Docker")](https://kind.sigs.k8s.io/docs/user/quick-start) creates a real cluster on your machine in which each node is a Docker container instead of a VM or physical server.

```bash
kind get clusters                                # Lists clusters
kubectl config get-contexts                      # Return the current cluster which receive your kubectl commands
kubectl config use-context kind-<cluster-name>   # Select the desired cluster
```

> [!NOTE]
>
> The cluster name comes from `kind get clusters`.

And in case you do not wanna change your context:

```bash
kubectl --context kind-<cluster-name> get pods -A
```

> [!IMPORTANT]
>
> `kubectl` reads contexts from `~/.kube/config`, and if you have `minikube` context it will be there too. But e.g. in [smart-novel](https://github.com/Ponos-OS/smart-novel/tree/6bd43f25ad2a15063f8f996046467e9bcf6254d6/infra/terraform/envs/local) when you have a Terraform which start the app and project's start script writes the kind cluster's `kubeconfig` to its own file, so the `kind-smart-novel` context never reached your default config. `kind get clusters` still lists the cluster because `kind` finds clusters through Docker, not through `kubeconfig`.
>
> The fix is to point `kubectl` at that file with `--kubeconfig infra/terraform/envs/local/smart-novel-config` or `export KUBECONFIG=...`. The `kind-` prefix added to the EKS context name was a separate mistake, since only kind-created contexts have it:
>
> ```bash
> kubectl --kubeconfig infra/terraform/envs/local/smart-novel-config get pods -A
> ```

---

- Ponos-OS: https://github.com/Ponos-OS
- My portfolio: https://kasir-barati.github.io
