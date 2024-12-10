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