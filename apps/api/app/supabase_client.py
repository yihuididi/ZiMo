from supabase import Client, create_client

from config import Settings


def create_supabase_client(settings: Settings) -> Client | None:
    """Create the shared client when both public Supabase values are configured."""
    if not settings.supabase_is_configured:
        return None

    return create_client(
        settings.supabase_url,
        settings.supabase_publishable_key,
    )
