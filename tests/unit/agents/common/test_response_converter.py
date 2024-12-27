import pytest
from langchain_core.messages import AIMessage

from agents.common.constants import FINALIZER, MESSAGES, NEW_YAML, UPDATE_YAML
from agents.common.response_converter import ResponseConverter


@pytest.fixture
def response_converter():
    return ResponseConverter()


@pytest.mark.parametrize(
    "description,yaml_content,expected_results",
    [
        (
            "Response with new and update yaml configs",
            """<YAML-NEW>
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
  namespace: default
spec:
  replicas: 3
```
</YAML-NEW>

some text 
some text

<YAML-UPDATE>
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
  namespace: default
spec:
  replicas: 5
```
</YAML-UPDATE>""",
            (
                [
                    "```yaml\napiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: nginx-deployment\n  namespace: default\nspec:\n  replicas: 3\n```"
                ],
                [
                    "```yaml\napiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: nginx-deployment\n  namespace: default\nspec:\n  replicas: 5\n```"
                ],
            ),
        ),
        ("Response with no yaml configs", "No YAML content", ([], [])),
        (
            "Response with invalid yaml configs",
            "<YAML-NEW>\ninvalid yaml\n</YAML-NEW>",
            (["invalid yaml"], []),
        ),
        (
            "Response with two yaml",
            """To create an Nginx deployment with 3 replicas, you can use the following YAML configuration:

<YAML-NEW>
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
  namespace: nginx-oom
spec:
  replicas: 3
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        image: nginx:latest
        ports:
        - containerPort: 80
```
</YAML-NEW>

To apply this configuration, save it to a file (e.g., `nginx-deployment.yaml`) and run the following command:

```bash
kubectl apply -f nginx-deployment.yaml
```

If you need to update the configuration of the existing Nginx deployment, for example, to change the image version or add environment variables, you can use the following YAML:

<YAML-UPDATE>
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
  namespace: nginx-oom
spec:
  replicas: 3
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        image: nginx:1.21.0 # Updated image version
        ports:
        - containerPort: 80
        env:
        - name: NGINX_ENV
          value: "production" # New environment variable
```
</YAML-UPDATE>

To apply this update, save the YAML to a file (e.g., `nginx-deployment-update.yaml`) and run:

```bash
kubectl apply -f nginx-deployment-update.yaml
```

This will update the existing deployment with the new configuration.""",
            (
                [
                    """```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
  namespace: nginx-oom
spec:
  replicas: 3
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        image: nginx:latest
        ports:
        - containerPort: 80
```"""
                ],
                [
                    """```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
  namespace: nginx-oom
spec:
  replicas: 3
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        image: nginx:1.21.0 # Updated image version
        ports:
        - containerPort: 80
        env:
        - name: NGINX_ENV
          value: "production" # New environment variable
```"""
                ],
            ),
        ),
    ],
)
def test_extract_yaml(response_converter, description, yaml_content, expected_results):
    new_yaml, update_yaml = response_converter._extract_yaml(yaml_content)
    assert (new_yaml, update_yaml) == expected_results


@pytest.mark.parametrize(
    "description, yaml_content,expected_result",
    [
        (
            "yaml with yaml marker",
            """```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test
  namespace: default
```""",
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": "test", "namespace": "default"},
            },
        ),
        (
            "yaml without yaml marker",
            """apiVersion: apps/v1
kind: Deployment
metadata:
  name: test
  namespace: default""",
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": "test", "namespace": "default"},
            },
        ),
        ("invalid yaml", "invalid: :\nyaml: content:", None),
        ("No yaml", "", None),
    ],
)
def test_parse_yamls(response_converter, description, yaml_content, expected_result):
    assert response_converter._parse_yamls(yaml_content) == expected_result


@pytest.mark.parametrize(
    "description, yaml_config,link_type,expected_link",
    [
        (
            "Generate link for new deployment",
            {
                "metadata": {"namespace": "test-ns", "name": "test-deploy"},
                "kind": "Deployment",
            },
            NEW_YAML,
            "/namespaces/test-ns/Deployment",
        ),
        (
            "Generate link for updating old deployment",
            {
                "metadata": {"namespace": "test-ns", "name": "test-deploy"},
                "kind": "Deployment",
            },
            UPDATE_YAML,
            "/namespaces/test-ns/Deployment/test-deploy",
        ),
        (
            "Test no link generation",
            {"metadata": {"namespace": "test-ns"}, "kind": "Deployment"},
            NEW_YAML,
            None,
        ),
    ],
)
def test_generate_resource_link(
    response_converter, description, yaml_config, link_type, expected_link
):
    assert (
        response_converter._generate_resource_link(yaml_config, link_type)
        == expected_link
    )


@pytest.mark.parametrize(
    "description, yaml_content,resource_link,link_type,expected_contents",
    [
        (
            "Test html generation",
            "kind: Deployment",
            "/test/link",
            NEW_YAML,
            [
                'class="yaml-block',
                'class="yaml"',
                'class="link"',
                "/test/link",
                "kind: Deployment",
            ],
        )
    ],
)
def test_create_html_nested_yaml(
    response_converter,
    description,
    yaml_content,
    resource_link,
    link_type,
    expected_contents,
):
    html = response_converter._create_html_nested_yaml(
        yaml_content, resource_link, link_type
    )
    for content in expected_contents:
        assert content in html


@pytest.mark.parametrize(
    "finalizer_response,replacement_html_list,yaml_type,expected",
    [
        (
            """Some text before
<YAML-NEW>
            metadata:
              name: test
</YAML-NEW>
            Some text after""",
            ["<div>HTML Replace 1</div>"],
            NEW_YAML,
            """Some text before
            <div>HTML Replace 1</div>
            Some text after""",
        ),
        (
            """First block
<YAML-UPDATE>
            block1
</YAML-UPDATE>
            Second block
<YAML-UPDATE>
            block2
</YAML-UPDATE>""",
            ["<div>Replace 1</div>", "<div>Replace 2</div>"],
            UPDATE_YAML,
            """First block
            <div>Replace 1</div>
            Second block
            <div>Replace 2</div>""",
        ),
        (
            """No YAML blocks here""",
            ["<div>HTML</div>"],
            NEW_YAML,
            """No YAML blocks here""",
        ),
        (
            """<YAML-NEW>block</YAML-NEW>""",
            [],
            NEW_YAML,
            """<YAML-NEW>block</YAML-NEW>""",
        ),
    ],
    ids=[
        "single_replacement",
        "multiple_replacements",
        "no_blocks",
        "empty_replacement_list",
    ],
)
def test_replace_yaml_with_html(
    response_converter, finalizer_response, replacement_html_list, yaml_type, expected
):
    result = response_converter._replace_yaml_with_html(
        finalizer_response, replacement_html_list.copy(), yaml_type
    )
    # Normalize whitespace for comparison
    assert " ".join(result.split()) == " ".join(expected.split())


@pytest.mark.parametrize(
    "state_content,expected_content",
    [
        (
            """<YAML-NEW>
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: test
  namespace: default
```
</YAML-NEW>""",
            "[Apply](",
        ),
        ("No YAML content", "No YAML content"),
        ("", ""),
    ],
)
def test_convert_final_response(response_converter, state_content, expected_content):
    state = {"messages": [AIMessage(content=state_content, name=FINALIZER)]}
    result = response_converter.convert_final_response(state)
    assert expected_content in result[MESSAGES][0].content
