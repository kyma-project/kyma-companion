# Deploying LangFuse Locally

## Set Up Redis

A local instance of [LangFuse](https://langfuse.com/docs) brings its own Redis instance with some basic authentication setup. If you don't specify the env var `REDIS_AUTH`, the password defaults to `myredissecret` and LangFuse automatically uses the database number `0` of that Redis instance (remember that by default, it comes with 16 databases, 0 to 15).
If you also run a local instance of Redis for the Companion, you have the following options:

1. Let the Companion use the Redis instance that comes with LangFuse and addressing database `1` by adding these lines in your `config/config.json`:

   ```json
   "REDIS_PASSWORD": "myredissecret",
   "REDIS_DB_NUMBER": "1",
   ```

or

1. Set up your Redis instance directly with the Companion to run on a different port, for example, `6380` (the default port for Redis is `6Y379`).

   ```shell
   docker run -d --name redis -p 6380:6379 redis
   ```

2. Set your `config/config.json` to:

  ```json
  "REDIS_PORT": "6380",
  ```

## Deploy LangFuse Locally

1. Clone the LangFuse repository to your local machine:

   ```bash
   git clone https://github.com/langfuse/langfuse.gitcd langfuse
   cd langfuse
   ```

2. Start the application:

   ```bash
   docker compose up
   ```

3. Open the web interface:

   ```bash
   open http://localhost:3000/auth/sign-up
   ```

4. Create an account, and choose **+ New Organization**. Give your organization a name, and choose **Next**.
5. On the **Invite Members** page, give your project a name, and choose **Create**.
6. Go to **API Keys**, and choose **+ Create new API keys**. Copy the `Secret Key`, `Public Key`, and `Host`, and paste them as values into your Kyma Companion's `config/config.json` for, **LANGFUSE_SECRET_KEY**, **LANGFUSE_PUBLIC_KEY**, and **LANGFUSE_HOST**:

  ```json
  ...
  "LANGFUSE_HOST": "https://localhost:3000",
  "LANGFUSE_SECRET_KEY": "<your secret key>",
  "LANGFUSE_PUBLIC_KEY": "<your public key>",  
  ```

## Deploy LangFuse on Kubernetes

1. To configure the minimal setup run:

   ```shell
   kubectl create ns langfuse
   helm repo add langfuse https://langfuse.github.io/langfuse-k8s
   helm repo update
   helm install langfuse langfuse/langfuse --namespace langfuse
   ```

2. To expose the `langfuse-web` service outside, you need an APIRule. To find out what your `host` is run:

   ```shell
   kubectl get gateway kyma-gateway -n kyma-system -o=jsonpath='{.spec.servers[0].hosts[0]}'
   ```

   Now past your `host` into this manifest and apply the APIRule to your cluster.

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

3. Open the web interface:

   ```bash
   open http://langfuse.<YOUR HOST>:3000/auth/sign-up
   ```

4. Create an account, and choose **+ New Organization**. Give your organization a name, and choose **Next**.
5. On the **Invite Members** page, give your project a name, and choose **Create**.
6. Go to **API Keys**, and choose **+ Create new API keys**. Copy the `Secret Key`, `Public Key`, and `Host`, and paste them as values into your Kyma Companion's `config/config.json` for, **LANGFUSE_SECRET_KEY**, **LANGFUSE_PUBLIC_KEY**, and **LANGFUSE_HOST**:

   ```json
   ...
   "LANGFUSE_HOST": "https://langfuse.<YOUR HOST>:3000",
   "LANGFUSE_SECRET_KEY": "<your secret key>",
   "LANGFUSE_PUBLIC_KEY": "<your public key>",  
   ```
