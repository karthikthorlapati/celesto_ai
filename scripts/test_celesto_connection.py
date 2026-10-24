"""Test Celesto Cloud API connection using environment variables."""

import sys
import logging
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("celesto_test")

def main():
    api_key = settings.celesto_api_key
    if not api_key:
        logger.error("CELESTO_API_KEY is not set.")
        sys.exit(1)

    logger.info(f"Loaded CELESTO_API_KEY (prefix: {api_key[:10]}..., length: {len(api_key)})")
    
    from _celesto_cloud_api.client import AuthenticatedClient
    from _celesto_cloud_api.api.computers import list_computers_v1_computers_get

    client = AuthenticatedClient(
        base_url="https://api.celesto.ai",
        token=api_key,
        timeout=30.0,
        raise_on_unexpected_status=False,
    )

    # Test computers listing
    try:
        computers_res = list_computers_v1_computers_get.sync_detailed(client=client)
        logger.info(f"List computers response status: {computers_res.status_code}")
        if computers_res.status_code == 200:
            parsed = computers_res.parsed
            logger.info(f"Parsed response type: {type(parsed)}")
            comps = getattr(parsed, 'computers', []) or []
            logger.info(f"Current active computers: {len(comps)}")
            for c in comps:
                logger.info(f" - Computer ID: {c.id}, status: {c.status}")
        else:
            logger.warning(f"Computers endpoint returned {computers_res.status_code}: {computers_res.content[:200]}")
    except Exception as e:
        logger.error(f"Error checking computers: {e}")

if __name__ == "__main__":
    main()
