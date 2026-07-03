"""Staff member domain model — shared between the extract + execute flows.

Mirrors the sibling cms-auto-builder's StaffMember shape so we can reuse its
prompt + injector payload format. Photos are resolved in two steps:
  1. `original_photo_url` holds the absolute URL from the source HTML
  2. `photo` is filled with the DDC media-library CDN URL after upload
"""

from pydantic import BaseModel


class StaffMember(BaseModel):
    department: str
    name: str
    title: str | None = None
    phone: str | None = None
    email: str | None = None
    bio: str | None = None
    has_photo: bool = False
    original_photo_url: str | None = None
    # Filled by the executor after media-library upload; empty string on failure
    # so the FE can still render the row with a placeholder.
    photo: str | None = None
