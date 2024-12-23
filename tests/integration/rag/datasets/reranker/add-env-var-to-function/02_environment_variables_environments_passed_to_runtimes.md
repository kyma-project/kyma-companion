# Environment Variables - Environments Passed to Runtimes
Every runtime provides its own unique environment configuration which can be read by a server and the `handler.js` file during the container run:
### Common Environments
| Environment | Default | Description                                                                                                                                                                    |
|---------------|-----------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **FUNC_HANDLER** | `main` | The name of the exported Function inside the `MOD_NAME` file.                                                                                                                  |
| **MOD_NAME** | `handler` | The name of the main exported file. It must have an extension of `.py` for the Python runtimes and `.js` for the Node.js ones. The extension must be added on the server side. |
| **FUNC_PORT** | `8080` | The right port a server listens to.                                                                                                                                            |
| **SERVICE_NAMESPACE** | None | The namespace where the right Function exists in a cluster.                                                                                                                    |
| **KUBELESS_INSTALL_VOLUME** | `/kubeless` | Full path to volume mount with users source code.                                                                                                                              |
| **FUNC_RUNTIME** | None | The name of the actual runtime. Possible values: `nodejs20` and `python312`.                                                                          |
| **TRACE_COLLECTOR_ENDPOINT** | None | Full address of OpenTelemetry Trace Collector is exported if the trace collector's endpoint is present.                                                                        |
| **PUBLISHER_PROXY_ADDRESS** | `http://eventing-publisher-proxy.kyma-system.svc&nbsp;.cluster.local/publish` | Full address of the Publisher Proxy service.                                                                                                                                   |
### Specific Environments
There are a few environments that occur only for a specific runtimes. The following list includes all of them:
#### Python Runtime-Specific Environment Variables
| Environment | Default | Description |
|---------------|-----------|-------------|
| **PYTHONPATH** | `$(KUBELESS_INSTALL_VOLUME)/lib.python3.9/site-packages&nbsp;:$(KUBELESS_INSTALL_VOLUME)` | List of directories that Python must add to the sys.path directory list. |
| **PYTHONUNBUFFERED** | `TRUE` | Defines if Python's logs must be buffered before printing them out. |