#!/usr/bin/env python3
"""
Script to refactor k8s_tools_api.py and kyma_tools_api.py to use shared dependencies.
"""

import re


def refactor_k8s_tools_api() -> None:
    """Refactor k8s_tools_api.py to use shared dependencies."""
    with open("src/routers/k8s_tools_api.py", "r") as f:
        content = f.read()

    # Update imports
    old_imports = '''from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from agents.k8s.tools.logs import fetch_pod_logs_tool
from agents.k8s.tools.query import k8s_overview_query_tool, k8s_query_tool
from routers.common import API_PREFIX
from services.data_sanitizer import DataSanitizer, IDataSanitizer
from services.k8s import IK8sClient, K8sAuthHeaders, K8sClient
from utils.config import Config, get_config
from utils.logging import get_logger

logger = get_logger(__name__)'''

    new_imports = '''from typing import Annotated

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field

from agents.k8s.tools.logs import fetch_pod_logs_tool
from agents.k8s.tools.query import k8s_overview_query_tool, k8s_query_tool
from routers.common import API_PREFIX
from routers.tools_dependencies import HealthResponse, init_k8s_client
from services.k8s import IK8sClient
from utils.logging import get_logger

logger = get_logger(__name__)'''

    content = content.replace(old_imports, new_imports)

    # Remove duplicate HealthResponse model
    health_response_pattern = r'class HealthResponse\(BaseModel\):.*?message: str = Field\(.*?\)\n\n'
    content = re.sub(health_response_pattern, '', content, flags=re.DOTALL)

    # Remove duplicate Dependencies section
    dependencies_pattern = r'# ={70,}\n# Dependencies\n# ={70,}\n\n\ndef init_config.*?detail=f"Failed to connect to the cluster: \{str\(e\)\}",\s*\) from e\n\n'
    content = re.sub(dependencies_pattern, '', content, flags=re.DOTALL)

    with open("src/routers/k8s_tools_api.py", "w") as f:
        f.write(content)

    print("✓ Refactored src/routers/k8s_tools_api.py")


def refactor_kyma_tools_api() -> None:
    """Refactor kyma_tools_api.py to use shared dependencies."""
    with open("src/routers/kyma_tools_api.py", "r") as f:
        content = f.read()

    # Update imports
    old_imports = '''from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from agents.kyma.tools.query import fetch_kyma_resource_version, kyma_query_tool
from routers.common import API_PREFIX
from services.data_sanitizer import DataSanitizer, IDataSanitizer
from services.k8s import IK8sClient, K8sAuthHeaders, K8sClient
from utils.config import Config, get_config
from utils.logging import get_logger

logger = get_logger(__name__)'''

    new_imports = '''from typing import Annotated

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, Field

from agents.kyma.tools.query import fetch_kyma_resource_version, kyma_query_tool
from routers.common import API_PREFIX
from routers.tools_dependencies import HealthResponse, init_k8s_client
from services.k8s import IK8sClient
from utils.logging import get_logger

logger = get_logger(__name__)'''

    content = content.replace(old_imports, new_imports)

    # Remove duplicate HealthResponse model
    health_response_pattern = r'class HealthResponse\(BaseModel\):.*?message: str = Field\(.*?\)\n\n'
    content = re.sub(health_response_pattern, '', content, flags=re.DOTALL)

    # Remove duplicate Dependencies section
    dependencies_pattern = r'# ={70,}\n# Dependencies\n# ={70,}\n\n\ndef init_config.*?detail=f"Failed to connect to the cluster: \{str\(e\)\}",\s*\)\n\n'
    content = re.sub(dependencies_pattern, '', content, flags=re.DOTALL)

    with open("src/routers/kyma_tools_api.py", "w") as f:
        f.write(content)

    print("✓ Refactored src/routers/kyma_tools_api.py")


if __name__ == "__main__":
    print("Starting refactoring...")
    refactor_k8s_tools_api()
    refactor_kyma_tools_api()
    print("\n✓ Refactoring complete!")
    print("\nRemoved duplicate code:")
    print("  - init_config()")
    print("  - init_data_sanitizer()")
    print("  - init_k8s_client()")
    print("  - HealthResponse model")
    print("\nBoth files now import from routers.tools_dependencies")
