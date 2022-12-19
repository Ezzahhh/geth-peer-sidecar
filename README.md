# Geth Peer Sidecar

## What does this solve?

This application is intended to run alongside a geth instance in a private network in kubernetes.
Its purpose is to facilitate using the `admin.addPeers` API to peer between all nodes rather than relying on discovery
or static-nodes which are unreliable in the kubernetes environment with uncertain pod IPs and service DNS issues.

The sidecars will share a single configmap, and create it if it does not exist. Each sidecar will be run in the same
pod as a Geth instance, so each sidecar will be responsible ensuring that their respective Geth instances are represented
in the configmap. Each sidecar will also check configmap and ensure that there are no dead nodes and patch the configmap
to reflect only alive nodes. Race conditions can occur but will be mitigated over time as sidecars maintain previous state
and always checks for dead nodes before patching. Usually where race conditions are met, it is solved 1-2 loops after occurrence.

## How to Use

The following YAML manifests will need to be applied to the cluster. Make any changes that you prefer, including
creating ClusterRoles/ClusterRoleBindings instead of Role/RoleBindings.

1. Role
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: YOUR_NAMESPACE
  name: geth-peer-sidecar
rules:
- apiGroups: [""]
  resources: ["configmaps"]
  verbs: ["patch", "get", "list", "create"]
```

2. Service Account
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: geth-peer-sidecar-sa
  namespace: YOUR_NAMESPACE
```

3. Role Binding
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: geth-peer-side-car-rb
  namespace: YOUR_NAMESPACE
subjects:
- kind: ServiceAccount
  name: geth-peer-sidecar-sa
roleRef:
  kind: Role
  name: geth-peer-sidecar
  apiGroup: rbac.authorization.k8s.io
```

4. Attach Sidecar Application with Geth Pod

This is a simple example StatefulSet (or can be changed to Deployment if you prefer) for a pod containing Geth and the
sidecar application. 

**It should be noted that the sidecar must be run with each Geth pod in your private network.**

It is highly recommended to configure the environment variables as below. 
`IPC_PATH` must point to the IPC file for Geth in the container. 
`CONFIGMAP_NAME` is the name of the config map that the sidecar will create.
`NAMESPACE` must match the same namespace you are deploying the Service Account and StatefulSet.

If the sidecar application is used, there is no need to configure static-nodes or discovery for your private network.

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: geth-1
spec:
  selector:
    matchLabels:
      app: geth
  serviceName: "nginx"
  replicas: 1
  template:
    metadata:
      labels:
        app: geth
    spec:
      serviceAccountName: geth-peer-sidecar-sa
      containers:
      - name: geth-peer-sidecar
        image: ezzah/geth-peer-sidecar:latest
        imagePullPolicy: Always
        env:
          - name: LOGGING
            value: DEBUG
          - name: IPC_PATH
            value: /data/geth.ipc
          - name: CONFIGMAP_NAME
            value: geth-shared-static-nodes
          - name: NAMESPACE
            value: YOUR_NAMESPACE
      - name: geth
        image: ethereum/client-go:latest
        volumeMounts:
        - name: data
          mountPath: /data
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: [ "ReadWriteOnce" ]
      storageClassName: "my-storage-class"
      resources:
        requests:
          storage: 1Gi
```

## Limitations

Due to the fact that the sidecar is designed to run with each Geth pod in your private network, there is a possibility 
of race conditions. This can occur where one sidecar patches the config map removing changes that another sidecar may 
have just patched removing the latter's changes. However, this is mitigated by randomising the delay period for the loop.
Furthermore, each sidecar should maintain its own enode of the Geth container it is attached to and any race condition
should be remedied in the next loop with some luck with sleep randomisation. 

The sidecar should be able to recover if the shared configmap is deleted or modified by a third party.

IPC file was the method chosen to communicate with Geth as it always has access to the ADMIN command which is needed
to call `addPeer` to Geth. For some nodes in production, you may not want to expose `admin` methods for JSON-RPC or WS.