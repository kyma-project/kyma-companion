Your function build might be failing due to a false positive result from Kaniko's container detection mechanism. This issue occurs primarily in k3d environments with cgroups version 2 or other unidentified configurations.

**Solution:**

Force Kaniko to bypass the verification check by adding the `--force` flag to the Kaniko execution arguments. This can be achieved by overriding the default configuration during Kyma deployment using a custom values file.

**Example:**

1. Create a file named `my-overrides.yaml` with the following content:

```yaml
serverless:
  containers:
    manager:
      envs:
        functionBuildExecutorArgs:
          value: --insecure,--skip-tls-verify,--skip-unused-stages,--log-format=text,--cache=true,--use-new-run,--compressed-caching=false,--force
```

2. Deploy Kyma using this overrides file:

```bash
kyma deploy --values-file my-overrides.yaml
```
