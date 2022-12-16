import json
from random import randint
from time import sleep
from kubernetes import client, config, watch
from kubernetes.config import ConfigException
from web3 import Web3

from logger import *

v1 = client.CoreV1Api()


def create_namespaced_config_map(namespace=cfg_namespace, body=None):
    config_map_json = body
    if body is None:
        log.error('body is required!')
    name = body['metadata']['name']
    if judge_config_map_exists(namespace, name):
        log.error(f'{name} exists! Skipping create...')
        return False
    else:
        val = v1.create_namespaced_config_map(namespace, config_map_json, pretty=True, _preload_content=False,
                                              async_req=False)
        ret_dict = json.loads(val.data)
        log.info(f'create succeed\n{json.dumps(ret_dict)}')
        return True


def patch_namespaced_config_map(namespace=cfg_namespace, body=None):
    config_map_json = body
    if body is None:
        log.error('body is required!')
    name = body['metadata']['name']
    if judge_config_map_exists(namespace, name):
        v1_batch = client.BatchV1Api()
        val = v1_batch.patch_namespaced_cron_job(name=name, namespace=namespace, body=config_map_json,
                                                 _preload_content=False, async_req=False)
        ret_dict = json.loads(val.data)
        log.info(f'patch succeed\n{json.dumps(ret_dict)}')
        return True
    else:
        log.error(f"{name} doesn't exists, please enter a new one!")
        return False


def get_config_map_list(namespace=cfg_namespace):
    val = v1.list_namespaced_config_map(namespace=namespace, pretty=True, _preload_content=False)
    config_map_list = json.loads(val.data)
    log.info(f'Config map number={len(config_map_list["items"])}')
    return config_map_list["items"]


def judge_config_map_exists(namespace=cfg_namespace, name=configmap_name):
    config_map_list = get_config_map_list(namespace)
    for config_map in config_map_list:
        if name == config_map['metadata']['name']:
            return True
    return False


def get_static_config_map_body(namespace=cfg_namespace, name=configmap_name, static_nodes=[]):
    body = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": name,
            "namespace": namespace,
        },
        "data": {
            "static-nodes.json": json.dump(static_nodes)}
    }
    return body


def check_port_is_alive(host, port):
    import socket
    from contextlib import closing
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        if sock.connect_ex((host, port)) == 0:
            log.info(f'Host: {host} is alive on port {port}')
            return True
        else:
            log.warning(f'Host: {host} is dead on port {port}')
            return False


if __name__ == '__main__':
    config.load_incluster_config()  # get mounted serviceaccount info in pod
    w3 = Web3(Web3.IPCProvider(ipc_path))  # link ipc to communicate with geth
    enode = ""
    while not enode:
        try:
            enode = w3.geth.admin.node_info().enode.toString()  # obtain enode of shared geth pod
            log.info(f"Geth online with enode: {enode}")
        except Exception as e:
            log.error("Geth is not yet available. Retrying in 5 seconds..", exc_info=True)
            sleep(5)
    try:
        # on launch, we want to check whether the shared static config map exists, if not we will create it
        # we will sleep a random time to avoid other nodes coming up creating the configmap
        delay = randint(1, 15)
        log.info(f"Sleep {str(delay)} s before attempting to create configmap")
        sleep(delay)
        create_namespaced_config_map(cfg_namespace,
                                     get_static_config_map_body(cfg_namespace, configmap_name, [enode]))

        while True:
            static_nodes_state = []
            w = watch.Watch()
            for event in w.stream(v1.read_namespaced_config_map(configmap_name, cfg_namespace),
                                  timeout_seconds=delay):
                static_nodes = json.loads(event['object'].data["static-nodes.json"])
                log.info("Event: %s %s" % event['object'].metadata.name,
                         json.dumps(static_nodes))
                if static_nodes_state == static_nodes:
                    # if previous state and current state is equal we have nothing to do
                    log.info("Nothing to do in this loop...")
                    break
                # we will need to remove dead peers
                static_nodes_state = static_nodes
                if enode not in static_nodes:
                    log.info(f'Current enode {enode} not found in configmap. Appending to state...')
                    static_nodes_state.append(enode)
                    w3.geth.admin.add_peer(enode)
                    log.info(f'Added enode {enode} to peer list...')
                for node in static_nodes:
                    if enode == node:
                        log.info("Skipping because current enode should already be added...")
                        # we scan skip where the enode is the same as the current node
                        break
                    _ip, _port = str(node).split("@")[1].split(":")
                    log.info(f'Node: {_ip}:{_port}')
                    if not check_port_is_alive(_ip, _port):
                        log.info(f'Node {_ip}:{_port} is unreachable. Removing...')
                        static_nodes_state.remove(node)
                        log.debug(f'static_nodes_state: {static_nodes_state}')
                    else:
                        # if node in list is alive we add to geth
                        w3.geth.admin.add_peer(node)
                        log.info(f"Node {_ip}:{_port} is alive. Adding peer to Geth...")
                patch_namespaced_config_map(cfg_namespace, get_static_config_map_body(cfg_namespace,
                                                                                      configmap_name,
                                                                                      static_nodes_state))
                log.info(f"Patched configmap with: {static_nodes_state}")
    except FileNotFoundError:
        log.error('Could not find IPC file')
    except ConfigException as e:
        log.error(f'Kubernetes config exception', exc_info=True)
    except Exception as e:
        log.error(f'Catch all exception', exc_info=True)
    finally:
        # remember to close the handlers
        for handler in log.handlers:
            handler.close()
            log.removeFilter(handler)
        # since theoretically we should never exit, any exit should signal a failure for a pod restart
        exit(1)
