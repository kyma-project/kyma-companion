# Scripts Don't Work

## Symptom

For MacBook M1, some parts of the scripts may not work.

The example error may look like this: `Error: unsupported platform OS_TYPE: Darwin, OS_ARCH: arm64; to mitigate this problem set variable KYMA with the absolute path to kyma-cli binary compatible with your operating system and architecture. Stop.`

## Cause

Kyma CLI is not released for Apple Silicon users.

## Remedy

Install [Kyma CLI manually](https://github.com/kyma-project/cli#installation) and export the path to it.

   ```bash
   export KYMA=$(which kyma)
   ```
