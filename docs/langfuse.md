# LangFuse Local Deployment

## Set Up Redis

A local instance of [LangFuse](https://langfuse.com/docs) brings its own Redis instance with some basic authentication setup. The password defaults to `myredissecret` (if you do not specify the env var `REDIS_AUTH`) and LangFuse automatically uses the database number `0` of that Redis instance (remember that by default, it comes with 16 databases, 0 to 15).
If you also run a local instance of `Redis` for the `Companion`, you have two options.

1. You let the Companion use the Redis instance that comes with LangFuse and addressing database `1` by adding these lines in your `config/config.json`:

  ```json
  "REDIS_PASSWORD": "myredissecret",
  "REDIS_DB_NUMBER": "1",
  ```

2. Set up your Redis instance directly with the Companion to run on a different port, for example, `6380` (the default port for Redis is `6379`).

  ```
  docker run -d --name redis -p 6380:6379 redis
  ```

Then you set your `config/config.json` to:

  ```json
  "REDIS_PORT": "6380",
  ```

### Deploy LangFuse Locally

Get a local copy of the LangFuse repository:

  ```bash
  git clone https://github.com/langfuse/langfuse.gitcd langfuse
  cd langfuse
  ```

Start the application:

  ```bash
  docker compose up
  ```

Open the web interface:

  ```bash
  open http://localhost:3000/auth/sign-up
  ```

4. Create an account, and choose **+ New Organization**. Give your organization a name, and choose **Next**.

5. On the **Invite Members** page, give your project a name, and choose **Create**.
6. Go to **API Keys**, and choose **+ Create new API keys**. Copy the `Secret Key`, `Public Key`, and `Host`, and paste them as values into your Kyma Companion's `config/config.json` for , **LANGFUSE_SECRET_KEY**, **LANGFUSE_PUBLIC_KEY**, and **LANGFUSE_HOST**:

  ```json
  ...
  "LANGFUSE_HOST": "https://localhost:3000",
  "LANGFUSE_SECRET_KEY": "<your secret key>",
  "LANGFUSE_PUBLIC_KEY": "<your public key>",  
  ```

## Deploy on Kubernetes

### For development purpose

For a minimal setup run:

  ```shell
  kubectl create ns langfuse
  helm repo add langfuse https://langfuse.github.io/langfuse-k8s
  helm repo update
  helm install langfuse langfuse/langfuse --namespace langfuse
  ```

to expose the `langfuse-web` service outside we need an `apirule`. To find out what your `host` is run:

  ```shell
  kubectl get gateway kyma-gateway -n kyma-system -o=jsonpath='{.spec.servers[0].hosts[0]}'
  ```

Now past your `host` into this manifest:

  ```yaml
  apiVersion: gateway.kyma-project.io/v1beta1
  kind: APIRule
  metadata:
    labels:
      app.kubernetes.io/name: langfuse
    name: langfuse
    namespace: langfuse
  spec:
    gateway: kyma-system/kyma-gateway
    host: langfuse.<YOUR HOST>
    rules:
    - accessStrategies:
      - handler: no_auth
      methods:
      - GET
      - POST
      - PUT
      - OPTIONS
      path: /.*
    service:
      name: langfuse-web
      port: 3000
  ```

and apply it to the cluster.

Open the web interface:

  ```bash
  open http://langfuse.<YOUR HOST>:3000/auth/sign-up
  ```

Create an account, then hit the `+ New Organization` button. Give your organization a name, hit `Next` in the `Invite Members` page, find a name for you project an hit `Create`.
On the next page, hit the `API Keys` menu point, then hit the `+ Create new API keys` button. Copy the `Secret Key`, `Secret Key` and `Host` and paste them as values in to your `kyma-companion`'s `config/config.json` for your `LANGFUSE_HOST`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY` keys:

  ```json
  ...
  "LANGFUSE_HOST": "https://langfuse.<YOUR HOST>:3000",
  "LANGFUSE_SECRET_KEY": "<your secret key>",
  "LANGFUSE_PUBLIC_KEY": "<your public key>",  
  ```
