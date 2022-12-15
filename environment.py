import os

# Load environment variables
logging_level = os.environ.get('LOGGING', 'DEBUG')
ipc_path = os.environ.get('IPC_PATH', '/data/geth.ipc')
configmap_name = os.environ.get('CONFIGMAP_NAME', 'geth-shared-static-nodes')
cfg_namespace = os.environ.get('NAMESPACE', "zk")