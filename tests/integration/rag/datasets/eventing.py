from textwrap import dedent

cases = [
    {
        "input": "some eventing messages are pending in the stream",
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
        "input": "what to do if event publish rate is too high for NATS?",
        "answer_relevancy_threshold": 0.7,
        "expected_output": dedent(
            """
            If the events' publish rate is very high (more than 1.5k events per second), speed up the event dispatching by
            increasing the `maxInFlightMessages` configuration of the Subscription (default is set to 10) accordingly. Due to low
            `maxInFlightMessages`, the dispatcher will not be able to keep up with the publisher, and as a result, the stream size
            will keep growing.

            If the published events are too large, the consumer cannot deliver them fast enough before the storage is full.
            In that case, either slow down the events' publish rate until the events are delivered, or scale the NATS backend with
            additional replicas.

            Symptoms are:
            - NATS JetStream backend stopped receiving events due to full storage.
            - You observe the following behavior in the Eventing Publisher Proxy (EPP):
              -- `507 Insufficient Storage` HTTP Status from EPP on the publish request.
              -- `cannot send to stream: nats: maximum bytes exceeded` in the EPP logs.
            """
        ),
    },
]
