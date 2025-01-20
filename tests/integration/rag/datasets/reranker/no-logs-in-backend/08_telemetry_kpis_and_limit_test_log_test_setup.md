# Telemetry KPIs and Limit Test - Log Test - Setup
The following diagram shows the test setup used for all test cases.
![LogPipeline Test Setup](./assets/log_perf_test_setup.drawio.svg)
In all test scenarios, a preconfigured trace load generator is deployed on the test cluster.
A Prometheus instance is deployed on the test cluster to collect relevant metrics from Fluent Bit instances and to fetch
the metrics at the end of the test as test scenario result.
All test scenarios also have a test backend deployed to simulate end-to-end behaviour.
Each test scenario has its own test scripts responsible for preparing the test scenario and deploying it on the test
cluster, running the scenario, and fetching relevant metrics and KPIs at the end of the test run. After the test, the
test results are printed out.