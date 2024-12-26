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
    ],
)
def test_extract_yaml(response_converter, description, yaml_content, expected_results):
    new_yaml, update_yaml = response_converter._extract_yaml(yaml_content)
    assert (new_yaml, update_yaml) == expected_results


@pytest.mark.parametrize(
    "yaml_content,expected_result",
    [
        (
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
        ("invalid: :\nyaml: content:", None),
        ("", None),
    ],
)
def test_parse_yamls(response_converter, yaml_content, expected_result):
    assert response_converter._parse_yamls(yaml_content) == expected_result


@pytest.mark.parametrize(
    "yaml_config,link_type,expected_link",
    [
        (
            {
                "metadata": {"namespace": "test-ns", "name": "test-deploy"},
                "kind": "Deployment",
            },
            NEW_YAML,
            "/namespaces/test-ns/Deployment",
        ),
        (
            {
                "metadata": {"namespace": "test-ns", "name": "test-deploy"},
                "kind": "Deployment",
            },
            UPDATE_YAML,
            "/namespaces/test-ns/Deployment/test-deploy",
        ),
        ({"metadata": {"namespace": "test-ns"}, "kind": "Deployment"}, NEW_YAML, None),
    ],
)
def test_generate_resource_link(
    response_converter, yaml_config, link_type, expected_link
):
    assert (
        response_converter._generate_resource_link(yaml_config, link_type)
        == expected_link
    )


@pytest.mark.parametrize(
    "yaml_content,resource_link,link_type,expected_contents",
    [
        (
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
    response_converter, yaml_content, resource_link, link_type, expected_contents
):
    html = response_converter._create_html_nested_yaml(
        yaml_content, resource_link, link_type
    )
    for content in expected_contents:
        assert content in html


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
