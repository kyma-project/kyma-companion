from textwrap import dedent

cases = [
    {
        "input": "Some eventing messages are pending in the stream",
        "answer_relevancy_threshold": 0.7,
        "expected_output": dedent(
            """
            ## Symptom

            You publish events, but some of them are not received by the subscriber and stay pending in the stream.

            ## Cause

            When the NATS EventingBackend has more than 1 replica, and the `Clustering` property on the NATS Server is enabled, one replica is elected as a leader on the stream and consumer levels (see [NATS Documentation](https://docs.nats.io/running-a-nats-service/configuration/clustering/jetstream_clustering)).
            When the leader is elected, all the messages are replicated across the replicas.

            Sometimes replicas can go out of sync with the other replicas.
            As a result, messages on some consumers can stop being acknowledged and start piling up in the stream.

            ## Remedy

            To fix the "broken" consumers with pending messages, trigger a leader reelection. You can do this either on the consumers that have pending messages, or if that fails, on the stream level.

            You need the latest version of NATS CLI installed on your machine.
            """
        ),
    },
    {
        "input": "The event publish rate is too high for NATS",
        "answer_relevancy_threshold": 0.7,
        "expected_output": dedent(
            """
            If the event publish rate is too high for NATS, you can address the issue by taking the following actions:
            
            1. **Slow Down the Publish Rate**: If the published events are too large and the consumer cannot deliver them fast enough before the storage is full, consider slowing down the events' publish rate until the events are delivered.
            
            2. **Scale the NATS Backend**: You can scale the NATS backend with additional replicas to handle the increased load.
            
            3. **Increase `maxInFlightMessages`**: If the events' publish rate is very high (more than 1.5k events per second), you can speed up the event dispatching by increasing the `maxInFlightMessages` configuration of the Subscription. The default is set to 10, and increasing it will help the dispatcher keep up with the publisher, preventing the stream size from growing excessively.
            
            These steps can help manage the high event publish rate and prevent storage issues in NATS JetStream.
            """
        ),
    },
]
