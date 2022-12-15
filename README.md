# Geth Peer Sidecar

## Info
This application is intended to run alongside a geth instance in a private network in kubernetes.
Its purpose is to facilitate using the `admin.addPeers` API to peer between all nodes rather than relying on discovery
or static-nodes which are unreliable in the kubernetes environment with uncertain pod IPs and service DNS issues.