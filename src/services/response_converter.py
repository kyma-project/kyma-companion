"""Response converter — extracts YAML blocks and converts to HTML with resource links.

Moved from src/agents/common/response_converter.py, adapted to work without LangGraph state.
"""

from __future__ import annotations

import re
from typing import Any

import yaml

from services.k8s import IK8sClient
from utils.logging import get_logger

logger = get_logger(__name__)

NEW_YAML = "New"
UPDATE_YAML = "Update"


class ResponseConverter:
    """Converts YAML blocks in LLM responses into HTML format with resource links."""

    def __init__(self, k8s_client: IK8sClient):
        self.new_yaml_pattern = r"<YAML-NEW>\s*([\s\S]*?)\s*</YAML-NEW>"
        self.update_yaml_pattern = r"<YAML-UPDATE>\s*([\s\S]*?)\s*</YAML-UPDATE>"
        self.k8s_client = k8s_client

    async def convert(self, response_text: str) -> str:
        """Convert YAML blocks in the response text to HTML with resource links.

        Args:
            response_text: The LLM response text potentially containing YAML blocks.

        Returns:
            The response text with YAML blocks replaced by HTML.
        """
        try:
            new_yaml_list, update_yaml_list = self._extract_yaml(response_text)

            if new_yaml_list or update_yaml_list:
                # Process new resource YAML configs
                replacement_list = await self._create_replacement_list(new_yaml_list, NEW_YAML)
                response_text = self._replace_yaml_with_html(response_text, replacement_list, NEW_YAML)

                # Process update resource YAML configs
                replacement_list = await self._create_replacement_list(update_yaml_list, UPDATE_YAML)
                response_text = self._replace_yaml_with_html(response_text, replacement_list, UPDATE_YAML)

        except Exception:
            logger.exception("Error in converting final response")

        return response_text

    def _extract_yaml(self, response: str) -> tuple[list[str], list[str]]:
        """Extract YAML code blocks from response using regex patterns."""
        new_yaml_blocks = re.findall(self.new_yaml_pattern, response, re.DOTALL)
        update_yaml_blocks = re.findall(self.update_yaml_pattern, response, re.DOTALL)
        return new_yaml_blocks, update_yaml_blocks

    def _parse_yamls(self, yaml_config: str) -> Any | None:
        """Parse YAML string into Python object with error handling."""
        try:
            if yaml_config[:7] == "```yaml":
                parsed_yaml = yaml.safe_load(yaml_config[8:-4])
            else:
                parsed_yaml = yaml.safe_load(yaml_config)
        except Exception as e:
            logger.exception(f"Error while parsing the yaml : {yaml_config}, Exception - {e}")
            return None
        return parsed_yaml

    async def _generate_resource_link(self, yaml_config: dict[str, Any], link_type: str) -> str | None:
        """Generate resource link based on YAML metadata and link type."""
        try:
            namespace = yaml_config["metadata"]["namespace"]
            deployment_name = yaml_config["metadata"]["name"]
            resource_type = yaml_config["kind"]
        except Exception:
            logger.exception(f"Error in generating link, skipping generating link for yaml: {yaml_config}")
            return None

        namespace_exists = False
        try:
            if await self.k8s_client.get_namespace(namespace):
                namespace_exists = True
        except Exception:
            logger.warning(f"Namespace {namespace} does not exist, skipping generating link for yaml: {yaml_config}")

        if link_type == NEW_YAML:
            ns = namespace if namespace_exists else "default"
            return f"/namespaces/{ns}/{resource_type}"
        elif link_type == UPDATE_YAML and namespace_exists:
            return f"/namespaces/{namespace}/{resource_type}/{deployment_name}"
        return None

    def _create_html_nested_yaml(self, yaml_config: str, resource_link: str, link_type: str) -> str:
        """Create HTML structure containing YAML content and resource link."""
        if yaml_config[:7] != "```yaml":
            yaml_config = "```yaml\n" + yaml_config + "\n```"

        html_content = f"""
        <div class="yaml-block">
            <div class="yaml">
            {yaml_config}
            </div>
            <div class="link" link-type="{link_type}">
                [Apply]({resource_link})
            </div>
        </div>
        """
        return html_content

    def _replace_yaml_with_html(
        self,
        response: str,
        replacement_html_list: list[str],
        yaml_type: str,
    ) -> str:
        """Replace YAML blocks in the response with corresponding HTML blocks."""

        def replace_func(match: Any) -> Any:
            if replacement_html_list:
                return replacement_html_list.pop(0)
            return match.group(0)

        yaml_pattern = self.new_yaml_pattern if yaml_type == NEW_YAML else self.update_yaml_pattern
        return re.sub(yaml_pattern, replace_func, response, flags=re.DOTALL)

    async def _create_replacement_list(self, yaml_list: list[str], yaml_type: str) -> list[str]:
        """Process list of YAML configs and create corresponding HTML replacements."""
        replacement_list = []
        for yaml_config_string in yaml_list:
            parsed_yaml = self._parse_yamls(yaml_config_string)
            if not parsed_yaml:
                replacement_list.append(yaml_config_string)
                continue

            generated_link = await self._generate_resource_link(parsed_yaml, yaml_type)
            if generated_link:
                html_string = self._create_html_nested_yaml(yaml_config_string, generated_link, yaml_type)
                replacement_list.append(html_string)
            else:
                replacement_list.append(yaml_config_string)
        return replacement_list
