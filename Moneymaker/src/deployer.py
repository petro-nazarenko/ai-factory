"""MVP Deployer — publishes a landing page to Vercel and returns a live URL.

Requires VERCEL_TOKEN in environment. Without it, returns '' (no-op).
"""

from __future__ import annotations

import base64
import logging

import httpx

from src.config import settings
from src.models import MVPPlan

logger = logging.getLogger(__name__)

_VERCEL_API = "https://api.vercel.com/v13/deployments"


class Deployer:
    """Deploys MVP landing pages to Vercel."""

    async def deploy(self, plan: MVPPlan) -> str:
        """Deploy *plan* and return the public URL. Returns '' when disabled."""
        if not settings.vercel_token:
            logger.info("VERCEL_TOKEN not set — deployment skipped.")
            return ""
        return await self._vercel(plan)

    async def _vercel(self, plan: MVPPlan) -> str:
        html = plan.template if plan.template else _default_html(plan)
        slug = "".join(c if c.isalnum() else "-" for c in plan.title.lower())[:28]
        payload = {
            "name": f"mvp-{slug}",
            "files": [
                {
                    "file": "index.html",
                    "data": base64.b64encode(html.encode()).decode(),
                    "encoding": "base64",
                }
            ],
            "target": "production",
            "projectSettings": {
                "framework": None,
                "buildCommand": None,
                "outputDirectory": None,
            },
        }
        headers = {"Authorization": f"Bearer {settings.vercel_token}"}
        if settings.vercel_team_id:
            headers["X-Vercel-Team-Id"] = settings.vercel_team_id

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(_VERCEL_API, json=payload, headers=headers)
                resp.raise_for_status()
                raw_url = resp.json().get("url", "")
                url = f"https://{raw_url}" if raw_url and not raw_url.startswith("http") else raw_url
                logger.info("Deployed '%s' → %s", plan.title, url)
                return url
        except Exception as exc:
            logger.error("Vercel deploy failed for '%s': %s", plan.title, exc)
            return ""


def _default_html(plan: MVPPlan) -> str:
    """Minimal landing page when plan.template is empty."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{plan.title}</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:system-ui,sans-serif;background:#fff;color:#111;
          max-width:600px;margin:80px auto;padding:0 24px}}
    h1{{font-size:2rem;font-weight:700;margin-bottom:12px}}
    p{{font-size:1.1rem;color:#444;margin-bottom:24px;line-height:1.6}}
    .price{{font-weight:600;color:#111;margin-bottom:32px}}
    input{{width:100%;padding:14px;font-size:1rem;border:1px solid #ddd;
           border-radius:8px;margin-bottom:12px}}
    button{{width:100%;padding:14px;background:#000;color:#fff;border:none;
            border-radius:8px;font-size:1rem;cursor:pointer}}
    button:hover{{background:#222}}
  </style>
</head>
<body>
  <h1>{plan.title}</h1>
  <p>{plan.tagline}</p>
  <p class="price">Starting at {plan.price_point}</p>
  <form onsubmit="return false">
    <input type="email" placeholder="your@email.com" required />
    <button type="submit">Get Early Access →</button>
  </form>
</body>
</html>"""
