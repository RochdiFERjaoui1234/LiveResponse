from __future__ import annotations
import httpx

async def post_webhook(url: str, text: str, blocks: list | None = None) -> bool:
    if not url or not url.strip() or url.startswith("${"):
        return False
    payload: dict = {"text": text}
    if blocks:
        payload["blocks"] = blocks
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, json=payload)
            return r.status_code < 300
    except Exception:
        return False

async def notify_approval_needed(
    url: str, approval_id: str, playbook: str, action: str, alert_summary: str
) -> bool:
    text = (
        f"🔐 *ACTION REQUIRED: SOAR Approval Needed*\n"
        f"• Playbook: `{playbook}`\n"
        f"• Sensitive Action: `{action}`\n"
        f"• Details: {alert_summary}\n"
        f"• Approval ID: `{approval_id}`"
    )
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": text}},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ Approve Action"},
                    "style": "primary",
                    "action_id": f"approve:{approval_id}",
                    "value": approval_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ Reject Action"},
                    "style": "danger",
                    "action_id": f"reject:{approval_id}",
                    "value": approval_id,
                },
            ],
        },
    ]
    return await post_webhook(url, text, blocks)
