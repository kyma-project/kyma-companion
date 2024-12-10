Kyma Functions are automatically instrumented to handle trace headers, so every time you call your function, the executed logic is traceable. You can further customize this by creating your own custom spans, adding events, and tags to the tracing context.

Here's how you can create a tracing span for a Kyma function:

**1. Prerequisites:**

* Ensure you have the Telemetry component installed in your Kyma environment.
* Configure a trace pipeline to visualize and analyze your traces.

**2. Code Example (Node.js):**

```javascript
const { SpanStatusCode } = require("@opentelemetry/api/build/src/trace/status");
const axios = require("axios")
module.exports = {
   main: async function (event, context) {

      const data = {
         name: "John",
         surname: "Doe",
         type: "Employee",
         id: "1234-5678"
      }

      const span = event.tracer.startSpan('call-to-acme-service');
      return await callAcme(data)
         .then(resp => {
            if(resp.status!==200){
              throw new Error("Unexpected response from acme service");
            }
            span.addEvent("Data sent");
            span.setAttribute("data-type", data.type);
            span.setAttribute("data-id", data.id);
            span.setStatus({code: SpanStatusCode.OK});
            return "Data sent";
         }).catch(err=> {
            console.error(err)
            span.setStatus({
              code: SpanStatusCode.ERROR,
              message: err.message,
            });
            return err.message;
         }).finally(()=>{
            span.end();
         });
   }
}

let callAcme = (data)=>{
   return axios.post('https://acme.com/api/people', data)
}
```

**Explanation:**

* This code snippet demonstrates creating a custom span named `call-to-acme-service` using `event.tracer.startSpan()`.
* Inside the span, you can add events (`span.addEvent()`), attributes (`span.setAttribute()`), and set the status (`span.setStatus()`).
* Finally, remember to end the span using `span.end()` when the operation is complete.

**3. Visualizing Traces:**

Once you have your function set up and deployed, you can visualize the traces in your configured trace backend. You should see the custom span you created along with the default function execution span, providing detailed insights into the function's performance and behavior.

**Additional Tips:**

* You can create nested spans to track hierarchical operations within your function.
* Use attributes to add contextual information to your spans, such as user IDs, request parameters, or error codes.
* Leverage events to capture specific points of interest within the span's timeline.

By effectively utilizing custom spans, events, and attributes, you can gain a deeper understanding of your Kyma functions' execution flow and performance characteristics.
