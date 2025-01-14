# Set Asynchronous Communication Between Functions - Steps - Create the Emitter Function
1. Go to the `emitter` folder and run Kyma CLI `init` command to initialize the scaffold for your first Function:
```bash
kyma init function
```
The `init` command creates these files in your workspace folder:
- `config.yaml` with the Function's configuration
> [!NOTE]
> See the detailed description of all fields available in the [`config.yaml` file](../technical-reference/07-60-function-configuration-file.md).
- `handler.js` with the Function's code and the simple "Hello Serverless" logic
- `package.json` with the Function's dependencies
2. In the `config.yaml` file, configure an APIRule to expose your Function to the incoming traffic over HTTP. Provide the subdomain name in the `host` property:
```yaml
apiRules:
- name: incoming-http-trigger
service:
host: incoming
rules:
- methods:
- GET
accessStrategies:
- handler: allow
```
3. Provide your Function logic in the `handler.js` file:
> [!NOTE]
> In this example, there's no sanitization logic. The `sanitize` Function is just a placeholder.
```js
module.exports = {
main: async function (event, context) {
let sanitisedData = sanitise(event.data)

const eventType = "sap.kyma.custom.acme.payload.sanitised.v1";
const eventSource = "kyma";

return await event.emitCloudEvent(eventType, eventSource, sanitisedData)
.then(resp => {
return "Event sent";
}).catch(err=> {
console.error(err)
return err;
});
}
}
let sanitise = (data)=>{
console.log(`sanitising data...`)
console.log(data)
return data
}
```
The `sap.kyma.custom.acme.payload.sanitised.v1` is a sample event type that the emitter Function declares when publishing events. You can choose a different one that better suits your use case. Keep in mind the constraints described on the [Event names](https://kyma-project.io/docs/kyma/latest/05-technical-reference/evnt-01-event-names/) page. The receiver subscribes to the event type to consume the events.
The event object provides convenience functions to build and publish events. To send the event, build the Cloud Event. To learn more, read [Function's specification](../technical-reference/07-70-function-specification.md#event-object-sdk). In addition, your **eventOut.source** key must point to `“kyma”` to use Kyma in-cluster Eventing.
There is a `require('axios')` line even though the Function code is not using it directly. This is needed for the auto-instrumentation to properly handle the outgoing requests sent using the `publishCloudEvent` method (which uses `axios` library under the hood). Without the `axios` import the Function still works, but the published events are not reflected in the trace backend.
4. Apply your emitter Function:
```bash
kyma apply function
```
Your Function is now built and deployed in Kyma runtime. Kyma exposes it through the APIRule. The incoming payloads are processed by your emitter Function. It then sends the sanitized content to the workload that subscribes to the selected event type. In our case, it's the receiver Function.
5. Test the first Function. Send the payload and see if your HTTP traffic is accepted:
```bash
export KYMA_DOMAIN={KYMA_DOMAIN_VARIABLE}

curl -X POST https://incoming.${KYMA_DOMAIN} -H 'Content-Type: application/json' -d '{"foo":"bar"}'
```