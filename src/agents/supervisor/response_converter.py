from typing import Any, Literal
import re
from tkinter import END
import yaml

from agents.common.constants import FINALIZER, MESSAGES, NEXT
from agents.supervisor.state import SupervisorState
from utils.logging import get_logger
from langchain_core.messages import AIMessage


LinkType = Literal["NEW", "UPDATE"]

logger = get_logger(__name__)


class ResponseConverter:
    """
    A class that handles the conversion of YAML responses into HTML format with resource links.
    This converter processes both new and update YAML configurations and generates appropriate
    resource links based on the YAML content.
    """

    def __init__(self):
        # Regular expression patterns to extract YAML blocks
        self.new_yaml_pattern = r"<YAML-NEW>\n(.*?)\n</YAML-NEW>"
        self.update_yaml_pattern = r"<YAML-UPDATE>\n(.*?)\n</YAML-UPDATE>"

    def _extract_yaml(self, finalizer_response: str) -> tuple[list[str], list[str]]:
        """
        Extract YAML code blocks from finalizer response using regex patterns.

        Args:
            finalizer_response: Response of the finalizer node

        Returns:
            Tuple containing lists of new and update YAML blocks
        """

        # Find all YAML blocks marked for new resources
        new_yaml_blocks = re.findall(
            self.new_yaml_pattern, finalizer_response.content, re.DOTALL
        )

        # Find all YAML blocks marked for updating existing resources
        update_yaml_blocks = re.findall(
            self.update_yaml_pattern, finalizer_response.content, re.DOTALL
        )

        return new_yaml_blocks, update_yaml_blocks

    def _parse_yamls(self, yaml_config: str) -> dict[str, Any] | None:
        """
        Parse YAML string into Python object with error handling.
        Attempts two parsing methods:
        1. First tries parsing after removing yaml markers
        2. If that fails, tries parsing the raw string

        Args:
            yaml_config: YAML configuration string

        Returns:
            Parsed YAML object or None if parsing fails
        """
        try:
            # First attempt: Parse by removing yaml markers
            parsed_yaml = yaml.safe_load(yaml_config[8:-4])

        except:
            logger.error(
                f"Error while parsing the yaml by removing yaml markers  : {yaml_config}"
            )

            try:
                # Second attempt: Parse raw string
                parsed_yaml = yaml.safe_load(yaml_config)

            except:
                logger.error(f"Error while parsing the raw yaml string : {yaml_config}")
                return None

        return parsed_yaml

    def _generate_resource_link(
        self, yaml_config: dict[str, Any], link_type: LinkType
    ) -> str | None:
        """
        Generate resource link based on YAML metadata and link type.

        Args:
            yaml_config: Parsed YAML configuration
            link_type: Type of link to generate ('NEW' or 'UPDATE')

        Returns:
            Generated resource link or None if required metadata is missing
        """
        # Extract required metadata for link generation
        try:
            namespace = yaml_config["metadata"]["namespace"]
            deployment_name = yaml_config["metadata"]["name"]
            resource_type = yaml_config["kind"]
        except:
            logger.error(f"Error in generating link, skipping the yaml: {yaml_config}")
            return None

        # Generate appropriate link based on type
        if link_type == "NEW":
            # New resource link format
            return f"/namespaces/{namespace}/{resource_type}"
        else:
            # Update resource link format includes deployment name
            return f"/namespaces/{namespace}/{resource_type}/{deployment_name}"

    def _create_html_nested_yaml(
        self, yaml_config: str, resource_link: str, link_type: LinkType
    ) -> str:
        """
        Create HTML structure containing YAML content and resource link.

        Args:
            yaml_config: YAML configuration string
            resource_link: Generated resource link
            link_type: Type of link ('NEW' or 'UPDATE')

        Returns:
            Formatted HTML string containing YAML and link
        """
        html_content = """
        
        <div class="yaml-block>
            <div class="yaml">
            {yaml_block}
            </div>

            <div class="link" link-type="{link_type}">
                [Apply]({link})
            </div>
        </div>
        
        """.format(
            yaml_block=yaml_config, link=resource_link, link_type=link_type
        )

        return html_content

    def _replace_yaml_with_html(
        self,
        finalizer_response: str,
        replacement_html_list: list[str],
        yaml_type: LinkType,
    ) -> str:
        """
        Replace YAML blocks in the response with corresponding HTML blocks.

        Args:
            finalizer_response: Original response containing YAML blocks
            replacement_html_list: List of HTML blocks to replace YAML
            yaml_type: Type of YAML blocks to replace ('NEW' or 'UPDATE')

        Returns:
            Modified response with YAML blocks replaced by HTML
        """

        def replace_func(match):
            # Replace each match with the next HTML block from the list
            if replacement_html_list:
                html_content = replacement_html_list.pop(0)
                return html_content
            return match.group(0)

        # Select appropriate pattern based on YAML type
        yaml_pattern = (
            self.new_yaml_pattern if yaml_type == "NEW" else self.update_yaml_pattern
        )

        # Perform the replacement
        converted_response = re.sub(
            yaml_pattern, replace_func, finalizer_response, flags=re.DOTALL
        )
        return converted_response

    def _create_replacement_list(
        self, yaml_list: list[str], yaml_type: LinkType
    ) -> list[str]:
        """
        Process list of YAML configs and create corresponding HTML replacements.

        Args:
            yaml_list: List of YAML configurations to process
            yaml_type: Type of YAML blocks ('NEW' or 'UPDATE')

        Returns:
            List of HTML replacements for YAML blocks
        """
        replacement_list = []

        for yaml_config_string in yaml_list:
            # Parse YAML and generate replacement
            parsed_yaml = self._parse_yamls(yaml_config_string)
            if not parsed_yaml:
                replacement_list.append(yaml_config_string)
                continue

            # Generate resource link
            generated_link = self._generate_resource_link(parsed_yaml, yaml_type)

            if generated_link:
                # Create HTML if link generation successful
                html_string = self._create_html_nested_yaml(
                    yaml_config_string, generated_link, yaml_type
                )
                replacement_list.append(html_string)
            else:
                # Keep original if link generation fails
                replacement_list.append(yaml_config_string)

        return replacement_list

    def convert_final_response(self, state: SupervisorState) -> dict[str, Any]:
        """
        Main conversion method that orchestrates the entire YAML to HTML conversion process.

        Args:
            state: Current supervisor state

        Returns:
            Dictionary containing converted messages and next state
        """
        finalizer_response = state.messages[-1].content
        try:
            # Extract all YAML blocks
            new_yaml_list, update_yaml_list = self._extract_yaml(finalizer_response)

            if new_yaml_list or update_yaml_list:
                # Process new resource YAML configs
                replacement_list = self._create_replacement_list(new_yaml_list, "NEW")
                finalizer_response = self._replace_yaml_with_html(
                    finalizer_response, replacement_list, "NEW"
                )

                # Process update resource YAML configs
                replacement_list = self._create_replacement_list(
                    update_yaml_list, "UPDATE"
                )
                finalizer_response = self._replace_yaml_with_html(
                    finalizer_response, replacement_list, "UPDATE"
                )

        except Exception as e:
            logger.error(f"Error in converting final response: {e}")

        return {
            MESSAGES: [
                AIMessage(
                    content=finalizer_response,
                    name=FINALIZER,
                )
            ],
            NEXT: END,
        }
