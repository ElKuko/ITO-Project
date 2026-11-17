"""Quarterly SKU approvals.

A store's approved-SKU list carries forward: until someone saves a new list for
the current quarter, the store uses the most recent quarter it has approvals for.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import StoreSKUApproval


def current_quarter() -> str:
    now = datetime.utcnow()
    return f"{now.year}-Q{(now.month - 1) // 3 + 1}"


def effective_quarter(db: Session, store_id: int) -> Optional[str]:
    """The latest quarter, up to the current one, with approvals for this store."""
    return db.query(func.max(StoreSKUApproval.quarter)).filter(
        StoreSKUApproval.store_id == store_id,
        StoreSKUApproval.quarter <= current_quarter(),
    ).scalar()
