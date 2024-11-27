One of the **rerequisites** for an application to be able to log is:

* **Log to `stdout` or `stderr`:** Your application must write its log messages to the standard output (`stdout`) or standard error (`stderr`) streams. This is essential because Kubernetes uses these streams to collect and manage container logs.