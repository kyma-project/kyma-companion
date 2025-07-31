from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage

from agents.common.constants import FINALIZER, MESSAGES, NEW_YAML, UPDATE_YAML
from agents.common.response_converter import ResponseConverter
from services.k8s import IK8sClient

yaml_new_sample_with_link_1 = """```yaml
   apiVersion: v1
   kind: Pod
   metadata:
     name: example-pod
     namespace: default
   spec:
     containers:
     - name: example-container
       image: example-image
       resources:
         requests:
           memory: "64Mi"
           cpu: "250m"
         limits:
           memory: "128Mi"
           cpu: "500m"
```"""

yaml_new_sample_without_link = """```yaml
   apiVersion: v1
   kind: Pod
   metadata:
     name: example-pod
   spec:
     containers:
     - name: example-container
       image: example-image
       resources:
         requests:
           memory: "64Mi"
           cpu: "250m"
         limits:
           memory: "128Mi"
           cpu: "500m"
```"""

yaml_new_sample_with_link_2 = """```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
  namespace: default
spec:
  replicas: 3
```"""

yaml_new_sample_with_link_3 = """```yaml
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

yaml_update_sample_with_link_1 = """```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
  namespace: default
spec:
  replicas: 5
```"""

yaml_update_sample_without_link_1 = """```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  namespace: default
spec:
  replicas: 5
```"""

yaml_update_sample_with_link_2 = """```yaml
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


yaml_update_without_yaml_marker = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
  namespace: default
spec:
  replicas: 5"""

yaml_new_without_yaml_marker = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
  namespace: default
spec:
  replicas: 3"""


@pytest.fixture
def response_converter():
    def mock_get_namespace(name):
        existing_namespaces = [
            "default",
            "kube-system",
            "test-ns",
            "kyma-system",
            "nginx-oom",
        ]
        return name in existing_namespaces

    k8s_client = Mock(IK8sClient)
    k8s_client.get_namespace.side_effect = mock_get_namespace
    return ResponseConverter(k8s_client=k8s_client)


@pytest.mark.parametrize(
    "description,yaml_content,expected_results",
    [
        (
            "Response with new and update yaml configs",
            f"""Resource Management:
- Define resource requests and limits for your pods to ensure efficient resource utilization. For example:

<YAML-NEW>
{yaml_update_sample_with_link_1}
</YAML-NEW>

- Use Horizontal Pod Autoscaler to automatically scale your applications based on demand.
- Implement Pod Disruption Budgets to maintain application availability during maintenance.""",
            (
                [yaml_update_sample_with_link_1],
                [],
            ),
        ),
        (
            "Response with new and update yaml configs",
            f"""<YAML-NEW>
{yaml_new_sample_with_link_2}
</YAML-NEW>

some text 
some text

<YAML-UPDATE>
{yaml_update_sample_with_link_2}
</YAML-UPDATE>""",
            (
                [yaml_new_sample_with_link_2],
                [yaml_update_sample_with_link_2],
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
            f"""To create an Nginx deployment with 3 replicas, you can use the following YAML configuration:

<YAML-NEW>
{yaml_new_sample_with_link_2}
</YAML-NEW>

To apply this configuration, save it to a file (e.g., `nginx-deployment.yaml`) and run the following command:

```bash
kubectl apply -f nginx-deployment.yaml
```

If you need to update the configuration of the existing Nginx deployment, for example, to change the image version or add environment variables, you can use the following YAML:

<YAML-UPDATE>
{yaml_update_sample_with_link_2}
</YAML-UPDATE>

To apply this update, save the YAML to a file (e.g., `nginx-deployment-update.yaml`) and run:

```bash
kubectl apply -f nginx-deployment-update.yaml
```

This will update the existing deployment with the new configuration.""",
            (
                [yaml_new_sample_with_link_2],
                [yaml_update_sample_with_link_2],
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
            "should generate link for new deployment with default namespace, when namespace do not exist",
            {
                "metadata": {"namespace": "non-existing-ns123", "name": "test-deploy"},
                "kind": "Deployment",
            },
            NEW_YAML,
            "/namespaces/default/Deployment",
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
            "should not generate link for updating old deployment when namespace do not exist",
            {
                "metadata": {"namespace": "non-existing-ns123", "name": "test-deploy"},
                "kind": "Deployment",
            },
            UPDATE_YAML,
            None,
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
                'class="yaml-block"',
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
    "yaml_config,resource_link,link_type,expected_yaml_in_output",
    [
        # YAML already has markers
        (
            "```yaml\nkey: value\n```",
            "https://example.com/resource",
            "New",
            "```yaml\nkey: value\n```",
        ),
        # YAML without markers - should be added
        (
            yaml_new_without_yaml_marker,
            "https://example.com/update",
            "New",
            f"```yaml\n{yaml_new_without_yaml_marker}\n```",
        ),
        # YAML without markers - should be added
        (
            yaml_update_without_yaml_marker,
            "https://k8s.example.com/apply",
            "Update",
            f"```yaml\n{yaml_update_without_yaml_marker}\n```",
        ),
    ],
)
def test_yaml_without_yaml_marker(
    response_converter, yaml_config, resource_link, link_type, expected_yaml_in_output
):
    """Test _create_html_nested_yaml with various input combinations"""

    # Act
    result = response_converter._create_html_nested_yaml(
        yaml_config, resource_link, link_type
    )

    # Assert
    assert isinstance(result, str)
    assert expected_yaml_in_output in result
    assert f'link-type="{link_type}"' in result
    assert f"[Apply]({resource_link})" in result
    assert '<div class="yaml-block">' in result
    assert '<div class="yaml">' in result
    assert '<div class="link"' in result


@pytest.mark.parametrize(
    "yaml_config,should_add_markers",
    [
        (yaml_new_sample_with_link_1, False),
        (yaml_update_sample_with_link_1, False),
        (yaml_update_without_yaml_marker, True),
        (yaml_new_without_yaml_marker, True),
    ],
)
def test_yaml_marker_detection(response_converter, yaml_config, should_add_markers):
    """Test YAML marker detection and addition logic"""

    result = response_converter._create_html_nested_yaml(
        yaml_config, "https://example.com", "New"
    )

    if should_add_markers:
        # Should contain the added markers
        assert "```yaml\n" + yaml_config + "\n```" in result
    else:
        # Should contain original YAML as-is
        assert yaml_config in result


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
    "yaml_list,yaml_type,expected",
    [
        (
            [
                """
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: nginx-deployment
      namespace: nginx-oom"""
            ],
            NEW_YAML,
            [
                '<div class="yaml-block"> <div class="yaml"> ```yaml apiVersion: apps/v1 '
                "kind: Deployment metadata: name: nginx-deployment namespace: nginx-oom ``` "
                '</div> <div class="link" link-type="New"> '
                "[Apply](/namespaces/nginx-oom/Deployment) </div> </div>"
            ],
        ),
        (
            [
                """invalid: :""",
                """
    apiVersion: apps/v1
    kind: Service
    metadata:
      name: test-svc
      namespace: test-ns""",
            ],
            UPDATE_YAML,
            [
                """invalid: :""",
                '<div class="yaml-block"> <div class="yaml"> ```yaml apiVersion: apps/v1 '
                "kind: Service metadata: name: test-svc namespace: test-ns ``` </div> <div "
                'class="link" link-type="Update"> '
                "[Apply](/namespaces/test-ns/Service/test-svc) </div> </div>",
            ],
        ),
        ([], NEW_YAML, []),
    ],
    ids=["single_valid_yaml", "mixed_valid_invalid", "empty_list"],
)
def test_create_replacement_list(response_converter, yaml_list, yaml_type, expected):
    result = response_converter._create_replacement_list(yaml_list, yaml_type)

    # Compare lengths
    assert len(result) == len(expected)

    # Compare each element after normalizing whitespace
    for res, exp in zip(result, expected, strict=False):
        assert " ".join(res.split()) == " ".join(exp.split())


@pytest.mark.parametrize(
    "state_content,expected_content",
    [
        (
            # single yaml with valid link, <YAML-NEW> block should be converted to HTML block
            f"""<YAML-NEW>
{yaml_new_sample_with_link_2}
</YAML-NEW>""",
            f"""
        <div class="yaml-block">
            <div class="yaml">
            {yaml_new_sample_with_link_2}
            </div>
            <div class="link" link-type="New">
                [Apply](/namespaces/default/Deployment)
            </div>
        </div>
        """,
        ),
        (  # single yaml with yaml block no space in beginning, <YAML-NEW> block should be converted to HTML block
            f"""Resource Management:
- Define resource requests and limits for your pods to ensure efficient resource utilization. For example:<YAML-NEW>
{yaml_new_sample_with_link_1}
</YAML-NEW>

- Use Horizontal Pod Autoscaler to automatically scale your applications based on demand.
- Implement Pod Disruption Budgets to maintain application availability during maintenance.""",
            f"""Resource Management:
- Define resource requests and limits for your pods to ensure efficient resource utilization. For example:
        <div class="yaml-block">
            <div class="yaml">
            {yaml_new_sample_with_link_1}
            </div>
            <div class="link" link-type="New">
                [Apply](/namespaces/default/Pod)
            </div>
        </div>

- Use Horizontal Pod Autoscaler to automatically scale your applications based on demand.
- Implement Pod Disruption Budgets to maintain application availability during maintenance.
        """,
        ),
        (  # single yaml without link, with yaml block no space in beginning and in end,  <YAML-NEW> block should be removed
            f"""Resource Management:
- Define resource requests and limits for your pods to ensure efficient resource utilization. For example:<YAML-NEW>{yaml_new_sample_without_link}
</YAML-NEW>- Use Horizontal Pod Autoscaler to automatically scale your applications based on demand.
- Implement Pod Disruption Budgets to maintain application availability during maintenance.""",
            f"""Resource Management:
- Define resource requests and limits for your pods to ensure efficient resource utilization. For example:{yaml_new_sample_without_link}- Use Horizontal Pod Autoscaler to automatically scale your applications based on demand.
- Implement Pod Disruption Budgets to maintain application availability during maintenance.
        """,
        ),
        (  # single yaml with link, with yaml block no space in beginning and in end,  <YAML-NEW> block should be converted to HTML block
            f"""Resource Management:
- Define resource requests and limits for your pods to ensure efficient resource utilization. For example:<YAML-NEW>{yaml_new_sample_with_link_1}
</YAML-NEW>- Use Horizontal Pod Autoscaler to automatically scale your applications based on demand.
- Implement Pod Disruption Budgets to maintain application availability during maintenance.""",
            f"""Resource Management:
- Define resource requests and limits for your pods to ensure efficient resource utilization. For example:
<div class="yaml-block">
            <div class="yaml">
            {yaml_new_sample_with_link_1}
            </div>
            <div class="link" link-type="New">
                [Apply](/namespaces/default/Pod)
            </div>
        </div>
        - Use Horizontal Pod Autoscaler to automatically scale your applications based on demand.
- Implement Pod Disruption Budgets to maintain application availability during maintenance.
        """,
        ),
        (  # single yaml with link, with yaml block no space in beginning and in end,  <YAML-NEW> block should be converted to HTML block
            f"""Resource Management:
- Define resource requests and limits for your pods to ensure efficient resource utilization. For example:<YAML-NEW>{yaml_new_without_yaml_marker}
</YAML-NEW>- Use Horizontal Pod Autoscaler to automatically scale your applications based on demand.
- Implement Pod Disruption Budgets to maintain application availability during maintenance.""",
            f"""Resource Management:
- Define resource requests and limits for your pods to ensure efficient resource utilization. For example:
<div class="yaml-block">
            <div class="yaml">
            ```yaml
            {yaml_new_without_yaml_marker}
            ```
            </div>
            <div class="link" link-type="New">
                [Apply](/namespaces/default/Deployment)
            </div>
        </div>
        - Use Horizontal Pod Autoscaler to automatically scale your applications based on demand.
- Implement Pod Disruption Budgets to maintain application availability during maintenance.
        """,
        ),
        (
            # update yaml without link ,<YAML-UPDATE> block should be removed
            f"""4. **(Optional) Modify the Function's Source Code**:
   - If you want to change the Function's code to return "Hello Serverless!", you can edit it with:
     ```bash
     kubectl edit function hello-world
     ```
   - Modify the `source` section in the YAML as follows:
     <YAML-UPDATE>
     {yaml_update_sample_without_link_1}
     </YAML-UPDATE>

5. **Synchronize Local Workspace with Cluster Changes**:
   - Fetch the content of the resource to synchronize your local workspace sources with the cluster changes:
     ```bash
     kyma sync function hello-world
     ```
""",
            f"""4. **(Optional) Modify the Function's Source Code**:
   - If you want to change the Function's code to return "Hello Serverless!", you can edit it with:
     ```bash
     kubectl edit function hello-world
     ```
   - Modify the `source` section in the YAML as follows:
     {yaml_update_sample_without_link_1}


5. **Synchronize Local Workspace with Cluster Changes**:
   - Fetch the content of the resource to synchronize your local workspace sources with the cluster changes:
     ```bash
     kyma sync function hello-world
     ```
""",
        ),
        (
            # single yaml with valid link, <YAML-NEW> without the yaml marker, yaml marker should be added
            f"""<YAML-NEW>
{yaml_new_without_yaml_marker}
</YAML-NEW>""",
            f"""
        <div class="yaml-block">
            <div class="yaml">
            ```yaml
            {yaml_new_without_yaml_marker}
            ```
            </div>
            <div class="link" link-type="New">
                [Apply](/namespaces/default/Deployment)
            </div>
        </div>
        """,
        ),
        (
            # single yaml with valid link, <YAML-UPDATE> without the yaml marker, yaml marker should be added
            f"""<YAML-UPDATE>
{yaml_update_without_yaml_marker}
</YAML-UPDATE>""",
            f"""
        <div class="yaml-block">
            <div class="yaml">
            ```yaml
            {yaml_update_without_yaml_marker}
            ```
            </div>
            <div class="link" link-type="Update">
                [Apply](/namespaces/default/Deployment/nginx-deployment)
            </div>
        </div>
        """,
        ),
        ("No YAML content", "No YAML content"),
        ("", ""),
    ],
)
def test_convert_final_response(response_converter, state_content, expected_content):
    state = {"messages": [AIMessage(content=state_content, name=FINALIZER)]}
    result = response_converter.convert_final_response(state)
    assert " ".join(result[MESSAGES][0].content.split()) == " ".join(
        expected_content.split()
    )
