from kubernetes import client

aConfiguration = client.Configuration()

with open("/run/secrets/kubernetes.io/serviceaccount/token", "r") as f:
    aToken = f.readline()

aConfiguration.host = "https://kubernetes.default.svc:443"
aConfiguration.ssl_ca_cert = "/run/secrets/kubernetes.io/serviceaccount/ca.crt"

aConfiguration.verify_ssl = True

aConfiguration.api_key = {"authorization": "Bearer " + aToken}

# Create a ApiClient with our config
aApiClient = client.ApiClient(aConfiguration)
