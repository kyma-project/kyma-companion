# Serverless Limitations - Runtime Phase Limitations
In the runtime, the Functions serve user-provided logic wrapped in the WEB framework (`express` for Node.js and `bottle` for Python). Taking the user logic aside, those frameworks have limitations and depend on the selected [runtime profile](technical-reference/07-80-available-presets.md#functions-resources) and the Kubernetes nodes specification (see the note with reference specification at the end of this document).
The following describes the response times of the selected runtime profiles for a "Hello World" Function requested at 50 requests/second. This describes the overhead of the serving framework itself. Any user logic added on top of that will add extra milliseconds and must be profiled separately.
<!-- tabs:start -->
#### **Node.js**
|                               | XL     | L      | M      | S      | XS      |
|-------------------------------|--------|--------|--------|--------|---------|
| response time [avarage]       | ~13ms  | 13ms   | ~15ms  | ~60ms  | ~400ms  |
| response time [95 percentile] | ~20ms  | ~30ms  | ~70ms  | ~200ms | ~800ms  |
| response time [99 percentile] | ~200ms | ~200ms | ~220ms | ~500ms | ~1.25ms |
#### **Python**
|                               | XL     | L      | M      | S      |
|-------------------------------|--------|--------|--------|--------|
| response time [avarage]       | ~11ms  | 12ms   | ~12ms  | ~14ms  |
| response time [95 percentile] | ~25ms  | ~25ms  | ~25ms  | ~25ms  |
| response time [99 percentile] | ~175ms | ~180ms | ~210ms | ~280ms |
<!-- tabs:end -->
Obviously, the bigger the runtime profile, the more resources are available to serve the response quicker. Consider these limits of the serving layer as a baseline - as this does not take your Function logic into account.
### Scaling
Function runtime Pods can be scaled horizontally from zero up to the limits of the available resources at the Kubernetes worker nodes.
See the [Use external scalers](tutorials/01-130-use-external-scalers.md) tutorial for more information.