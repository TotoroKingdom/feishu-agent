import pytest

from app.tools.contracts import ToolContext, ToolResult
from app.tools.registry import get_tool


def test_registry_only_returns_allowlisted_tools() -> None:
    tool = get_tool("feishu.read_records")
    result = tool(ToolContext(request_id="req-test"))
    assert isinstance(result, ToolResult)
    assert result.status == "success"


def test_registry_rejects_unknown_tool() -> None:
    with pytest.raises(KeyError, match="unknown tool"):
        get_tool("runtime.execute_code")
