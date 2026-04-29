"""Broker interface — v3 placeholder.

This module exists so that future broker implementations (KIS, Kiwoom,
Binance Trade) have a stable extension point. The actual ``Protocol`` and
order data classes live in ``core.types.schemas`` to keep all type
definitions in one file; we re-export them here for convenience.

DO NOT IMPLEMENT IN v0.x — auto-trading is a v3 PDCA cycle.
"""

from __future__ import annotations

from core.types.schemas import BrokerProtocol, OrderRequest, OrderResult

__all__ = ["BrokerProtocol", "OrderRequest", "OrderResult"]
