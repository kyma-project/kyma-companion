# Busola Custom Resource Extensions

Busola supports extending the UI with custom resource definitions (CRDs). You can define how CRD instances are displayed, validated, and edited directly in the Kyma dashboard.

## Overview

Busola reads `ConfigMap` resources in the `kube-public` namespace to discover UI extensions. Each ConfigMap contains a YAML or JSON description for one CRD, controlling:

- The columns shown in the list view
- The sections shown in the detail view
- Form fields for creation and editing
- Validation rules

## Configuration Format

<!-- tabs:start -->

#### **YAML**

```yaml
resource:
  kind: MyApp
  group: apps.example.com
  version: v1alpha1
form:
  - path: spec.replicas
    widget: Number
    name: Replicas
    required: true
    min: 1
    max: 100
  - path: spec.image
    widget: Text
    name: Container Image
    required: true
list:
  - source: spec.replicas
    name: Replicas
  - source: status.state
    name: State
    highlights:
      positive:
        - Running
      negative:
        - Failed
      critical:
        - Pending
```

#### **JSON**

```json
{
  "resource": {
    "kind": "MyApp",
    "group": "apps.example.com",
    "version": "v1alpha1"
  },
  "form": [
    {
      "path": "spec.replicas",
      "widget": "Number",
      "name": "Replicas",
      "required": true,
      "min": 1,
      "max": 100
    },
    {
      "path": "spec.image",
      "widget": "Text",
      "name": "Container Image",
      "required": true
    }
  ],
  "list": [
    { "source": "spec.replicas", "name": "Replicas" },
    { "source": "status.state", "name": "State" }
  ]
}
```

<!-- tabs:end -->

## Widgets

Busola provides a library of UI widgets for form fields.

<!-- tabs:start -->

#### **Input Widgets**

| Widget | Description |
|---|---|
| `Text` | Single-line text input. |
| `Number` | Numeric input with optional `min`/`max`. |
| `Switch` | Boolean toggle. |
| `Select` | Drop-down with a static list of options. |
| `Combobox` | Drop-down that also allows free-form input. |

#### **Complex Widgets**

| Widget | Description |
|---|---|
| `KeyValuePair` | Map editor for simple string key-value pairs. |
| `ResourceRef` | Resource selector that queries the cluster for available instances. |
| `CodeEditor` | Multi-line editor with syntax highlighting. |
| `Labels` | Label set editor that validates key=value format. |

<!-- tabs:end -->

## Deploying an Extension

Package your extension as a ConfigMap in the `kube-public` namespace:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: busola-ext-myapp
  namespace: kube-public
  labels:
    busola.io/extension: "true"
    busola.io/extension-version: "0.5"
data:
  details: |
    <your extension YAML here>
```

After applying the ConfigMap, reload the Busola UI. Busola automatically detects the extension and applies it to the matching CRD instances.

## Validation

Use the `trigger` and `validate` keywords to add field-level validation rules:

```yaml
form:
  - path: spec.image
    widget: Text
    name: Container Image
    required: true
    trigger:
      - validate
    validate:
      - source: "$value"
        severity: error
        message: Must be a valid image reference
        when: "$value !~ /^[a-z0-9\\/._:-]+$/"
```

## Related Resources

- [Busola Custom Extensions](./custom-extensions.md)
- [Resource Validation](../resource-validation/validation.md)
- [Widget Reference](./widget-reference.md)
