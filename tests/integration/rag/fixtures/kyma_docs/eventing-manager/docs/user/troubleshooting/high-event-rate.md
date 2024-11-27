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