from collections.abc import Callable

from app.tools.contracts import ToolContext, ToolResult

ToolHandler = Callable[[ToolContext], ToolResult]


def _read_records(context: ToolContext) -> ToolResult:
    from app.providers.fake import FakeFeishuProvider

    records = FakeFeishuProvider().read_records()
    return ToolResult(
        status="success",
        data={"records": records},
        external_id=str(records[0]["external_id"]),
    )


ALLOWLIST = {"feishu.read_records": _read_records}


def get_tool(name: str) -> ToolHandler:
    try:
        return ALLOWLIST[name]
    except KeyError as error:
        raise KeyError(f"unknown tool: {name}") from error
