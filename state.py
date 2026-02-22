"""
state.py — AppState: Centralized Session State for Ultra State
==============================================================

Holds all mutable, observable **session-level** state for UltraStateApp.
This is Tier 1 of the Phase 2 state-decoupling roadmap.

Tier 2 (data caches — self.df, self.activities_data, weekly chart data)
are explicitly deferred and remain as plain instance attributes on
UltraStateApp until Phase 2 Step 3 (UI componentization).

Design principles
─────────────────
• Zero external dependencies (no asyncio, no threading primitives).
  All state writes in this app happen on the NiceGUI event loop thread
  (button clicks, on_change handlers, ui.timer callbacks), so no locking
  is required.

• Synchronous observer pattern via __setattr__ override.
  Any field write automatically notifies registered subscribers.
  Subscribers are called in registration order, synchronously, before
  __setattr__ returns.

• Subscribers receive (new_value,) — they do NOT receive the old value.
  If callers need change-gating they can read the previous value before
  writing:
      old = self.state.timeframe
      self.state.timeframe = new
      # subscriber already fired

Usage
─────
    s = AppState()

    # Register a subscriber for a specific field
    s.subscribe('timeframe', lambda v: print('timeframe changed to', v))

    # Any ordinary attribute write triggers subscribers automatically
    s.timeframe = 'Last 90 Days'   # prints: timeframe changed to Last 90 Days

    # Deregister when a listener is being destroyed (e.g., modal closed)
    s.unsubscribe('timeframe', my_callback)

    # Bulk-write multiple fields without firing subscribers mid-batch,
    # then fire all relevant subscribers once with the final values:
    s.batch_set(timeframe='Last 90 Days', sort_by='pace')
"""

from __future__ import annotations

from typing import Any, Callable

from constants import DEFAULT_TIMEFRAME


class AppState:
    """
    Centralized, observable session state for UltraStateApp.

    Fields
    ──────
    timeframe          : str   — Active timeframe filter key (one of TIMEFRAME_OPTIONS)
    sort_by            : str   — Column name used for DB-side sort
    sort_desc          : bool  — Sort direction (True = descending)
    focus_mode_active  : bool  — Whether Focus Mode is currently active
    entering_focus_mode: bool  — Guard flag: True while programmatically setting the
                                 timeframe select during focus mode transitions, to
                                 prevent on_filter_change from re-triggering.
    volume_lens        : str   — Active volume chart lens ('quality'|'mix'|'load'|'zones')
    active_filters     : set   — Set of active filter IDs (distance buckets + tag names)
    session_id         : int|None — DB session ID for the 'Last Import' timeframe filter
    import_in_progress : bool  — True while a FIT-file import task is running
    """

    # ── Internal sentinel to bypass __setattr__ during __init__ ──────────
    _INITIALIZING: bool = True

    def __init__(self) -> None:
        # Bootstrap subscribers dict without triggering notifications
        object.__setattr__(self, '_subscribers', {})
        object.__setattr__(self, '_AppState__initializing', True)

        # ── Tier 1 session state (9 fields) ──────────────────────────────
        self.timeframe:            str       = DEFAULT_TIMEFRAME
        self.sort_by:              str       = 'date'
        self.sort_desc:            bool      = True
        self.focus_mode_active:    bool      = False
        self.entering_focus_mode:  bool      = False
        self.volume_lens:          str       = 'quality'
        self.active_filters:       set       = set()
        self.session_id:           Any       = None   # int | None
        self.import_in_progress:   bool      = False

        # Initialise done — future writes will fire subscribers
        object.__setattr__(self, '_AppState__initializing', False)

    # ── Internal helpers ──────────────────────────────────────────────────

    _OBSERVED_FIELDS: frozenset = frozenset({
        'timeframe', 'sort_by', 'sort_desc',
        'focus_mode_active', 'entering_focus_mode',
        'volume_lens', 'active_filters',
        'session_id', 'import_in_progress',
    })

    def __setattr__(self, name: str, value: Any) -> None:
        object.__setattr__(self, name, value)
        initializing = object.__getattribute__(self, '_AppState__initializing')
        if initializing:
            return
        if name in self._OBSERVED_FIELDS:
            self._notify(name, value)

    # ── Public observer API ───────────────────────────────────────────────

    def subscribe(self, key: str, callback: Callable[[Any], None]) -> None:
        """Register *callback* to be called whenever *key* is written.

        The callback receives the new value as its single positional argument.
        Multiple callbacks may be registered for the same key; they are called
        in registration order.

        Example::

            state.subscribe('volume_lens', self._on_lens_changed)
        """
        if key not in self._subscribers:
            self._subscribers[key] = []
        if callback not in self._subscribers[key]:
            self._subscribers[key].append(callback)

    def unsubscribe(self, key: str, callback: Callable[[Any], None]) -> None:
        """Remove *callback* from the subscriber list for *key*.

        Safe to call even if the callback was never registered.
        """
        bucket = self._subscribers.get(key)
        if bucket and callback in bucket:
            bucket.remove(callback)

    def batch_set(self, **kwargs: Any) -> None:
        """Write multiple fields without triggering subscribers mid-batch.

        Subscribers are collected into a de-duplicated, ordered list and called
        once each (with the final value) after all fields are written.

        Example::

            self.state.batch_set(timeframe='Last 90 Days', sort_by='pace')
        """
        # Suppress notifications during writes
        object.__setattr__(self, '_AppState__initializing', True)
        for name, value in kwargs.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, '_AppState__initializing', False)

        # Fire notifications once per changed key (in kwargs order, deduped)
        seen: set = set()
        for name, value in kwargs.items():
            if name not in seen and name in self._OBSERVED_FIELDS:
                self._notify(name, value)
                seen.add(name)

    # ── Private ───────────────────────────────────────────────────────────

    def _notify(self, key: str, value: Any) -> None:
        """Call all subscribers registered for *key*, passing *value*."""
        for callback in list(self._subscribers.get(key, [])):
            try:
                callback(value)
            except Exception as exc:   # pragma: no cover
                # Never let a bad subscriber crash the app
                import logging
                logging.getLogger(__name__).error(
                    'AppState subscriber %s for key %r raised: %s',
                    callback, key, exc, exc_info=True,
                )

    def __repr__(self) -> str:  # pragma: no cover
        fields = {f: getattr(self, f) for f in sorted(self._OBSERVED_FIELDS)}
        return f'AppState({fields})'
