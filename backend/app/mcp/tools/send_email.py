def run(to: str, subject: str, body: str) -> dict:
    """Day 3 scope: proves Agent -> MCP Client -> MCP Server -> "Gmail
    Service" plumbing exists end-to-end. Does NOT send email, does NOT
    touch email_logs, does NOT implement EMAIL_MODE -- spec2.md section 24
    forbids the Agent from auto-sending; Day 4 owns the real
    draft/preview/confirm/Gmail OAuth flow on top of this stub.
    """
    return {
        "status": "not_implemented",
        "message": "Email 寄送功能將於 Day 4 隨 Email Preview / Confirm 流程一併提供。",
    }
