import pytest
from typing import Any
from unittest.mock import Mock, patch
from agents.supervisor.state import SupervisorState
from langchain_core.messages import AIMessage

from response_converter import ResponseConverter, LinkType


@pytest.fixture
def converter():
    """Fixture to create ResponseConverter instance"""
    return ResponseConverter()


@pytest.fixture
def sample_yaml_new():
    """Fixture for sample new YAML content"""
    return """<YAML-NEW>
apiVersion: v1
kind: Deployment
metadata:
  name: test-deployment
  namespace: default
spec:
  replicas: 3
</YAML-NEW>"""


@pytest.fixture
def sample_yaml_update():
    """Fixture for sample update YAML content"""
    return """<YAML-UPDATE>
apiVersion: v1
kind: Service
metadata:
  name: test-service
  namespace: default
spec:
  ports:
    - port: 80
</YAML-UPDATE>"""


@pytest.fixture
def mock_state(sample_yaml_new, sample_yaml_update):
    """Fixture to create mock SupervisorState with sample messages"""
    state = Mock(spec=SupervisorState)
    state.messages = [
        AIMessage(content=f"{sample_yaml_new}\nSome text\n{sample_yaml_update}")
    ]
    return state


class TestResponseConverter:
    def test_extract_yaml(
        self, converter, mock_state, sample_yaml_new, sample_yaml_update
    ):
        """Test YAML extraction from finalizer response"""
        new_yaml_list, update_yaml_list = converter._extract_yaml(mock_state)

        assert len(new_yaml_list) == 1
        assert len(update_yaml_list) == 1
        assert "apiVersion: v1" in new_yaml_list[0]
        assert "kind: Deployment" in new_yaml_list[0]
        assert "kind: Service" in update_yaml_list[0]

    def test_extract_yaml_no_yaml(self, converter):
        """Test YAML extraction with no YAML blocks"""
        state = Mock(spec=SupervisorState)
        state.messages = [AIMessage(content="Just some regular text")]
        new_yaml_list, update_yaml_list = converter._extract_yaml(state)

        assert len(new_yaml_list) == 0
        assert len(update_yaml_list) == 0

    @pytest.mark.parametrize(
        "yaml_input,expected_type",
        [
            (
                """apiVersion: v1
kind: Deployment
metadata:
  name: test
  namespace: default""",
                dict,
            ),
            ("invalid: :\nyaml: content", type(None)),
        ],
    )
    def test_parse_yamls(self, converter, yaml_input, expected_type):
        """Test YAML parsing with valid and invalid inputs"""
        result = converter._parse_yamls(yaml_input)
        assert isinstance(result, expected_type)

    @pytest.mark.parametrize(
        "yaml_config,link_type,expected",
        [
            (
                {
                    "metadata": {"namespace": "default", "name": "test"},
                    "kind": "Deployment",
                },
                "NEW",
                "/namespaces/default/Deployment",
            ),
            (
                {"metadata": {"namespace": "prod", "name": "app"}, "kind": "Service"},
                "UPDATE",
                "/namespaces/prod/Service/app",
            ),
            ({"metadata": {}}, "NEW", None),
        ],
    )
    def test_generate_resource_link(self, converter, yaml_config, link_type, expected):
        """Test resource link generation with different configurations"""
        result = converter._generate_resource_link(yaml_config, link_type)
        assert result == expected

    def test_create_html_nested_yaml(self, converter):
        """Test HTML creation for YAML content"""
        yaml_config = "kind: Deployment"
        resource_link = "/namespaces/default/Deployment"
        link_type = "NEW"

        result = converter._create_html_nested_yaml(
            yaml_config, resource_link, link_type
        )

        assert "yaml-block" in result
        assert yaml_config in result
        assert resource_link in result
        assert link_type in result

    def test_replace_yaml_with_html(self, converter, sample_yaml_new):
        """Test replacement of YAML blocks with HTML"""
        finalizer_response = f"Start\n{sample_yaml_new}\nEnd"
        replacement_html = ["<div>Replaced HTML</div>"]

        result = converter._replace_yaml_with_html(
            finalizer_response, replacement_html, "NEW"
        )

        assert "Start" in result
        assert "End" in result
        assert "<div>Replaced HTML</div>" in result
        assert "<YAML-NEW>" not in result

    def test_create_replacement_list(self, converter):
        """Test creation of HTML replacement list"""
        yaml_list = [
            """apiVersion: v1
kind: Deployment
metadata:
  name: test
  namespace: default"""
        ]
        result = converter._create_replacement_list(yaml_list, "NEW")

        assert len(result) == 1
        assert "yaml-block" in result[0]
        assert 'link-type="NEW"' in result[0]

    def test_convert_final_response(self, converter, mock_state):
        """Test complete conversion process"""
        result = converter._convert_final_response(mock_state)

        assert MESSAGES in result
        assert NEXT in result
        assert isinstance(result[MESSAGES][0], AIMessage)
        assert result[MESSAGES][0].name == FINALIZER

    def test_convert_final_response_error_handling(self, converter):
        """Test error handling in final response conversion"""
        state = Mock(spec=SupervisorState)
        state.messages = [AIMessage(content=None)]  # This should cause an error

        result = converter._convert_final_response(state)

        assert MESSAGES in result
        assert NEXT in result
        assert isinstance(result[MESSAGES][0], AIMessage)

    @pytest.mark.parametrize("link_type", ["NEW", "UPDATE"])
    def test_link_type_literal(self, converter, link_type):
        """Test that LinkType literal works correctly"""
        yaml_config = {
            "metadata": {"namespace": "default", "name": "test"},
            "kind": "Deployment",
        }
        result = converter._generate_resource_link(yaml_config, link_type)
        assert isinstance(result, str)


class TestResponseConverterIntegration:
    """Integration tests for ResponseConverter"""

    def test_full_conversion_flow(self, converter, mock_state):
        """Test the complete conversion flow from input to output"""
        result = converter._convert_final_response(mock_state)

        # Verify final structure
        assert isinstance(result, dict)
        assert len(result[MESSAGES]) == 1
        assert isinstance(result[MESSAGES][0].content, str)

        # Verify HTML conversion
        content = result[MESSAGES][0].content
        assert "yaml-block" in content
        assert "link-type" in content
        assert "[Apply]" in content

    def test_error_handling_chain(self, converter):
        """Test error handling through the entire conversion chain"""
        state = Mock(spec=SupervisorState)
        state.messages = [
            AIMessage(
                content="""
            <YAML-NEW>
            invalid: :yaml: content
            </YAML-NEW>
        """
            )
        ]

        result = converter._convert_final_response(state)

        # Should still return valid response structure even with invalid YAML
        assert isinstance(result, dict)
        assert MESSAGES in result
        assert NEXT in result
