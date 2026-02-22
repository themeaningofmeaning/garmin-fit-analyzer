"""
constants.py — Ultra State Semantic Vocabulary
===============================================

Single source of truth for all taxonomy labels, coaching copy,
and UI classification strings used across the application.

Design rules
────────────
• hr_zones.py owns Zone 1–5 keys/colors/thresholds.  Nothing here duplicates that.
• Every group has a docstring explaining the *sports science*, not just the code.
• Keys are SCREAMING_SNAKE_CASE identifiers; display values are the human-readable
  strings that appear in the UI.
• app.py and analyzer.py import from here; they never define these strings inline.
"""

from __future__ import annotations

# ── 1. SUPPORTED SPORTS ──────────────────────────────────────────────────────

SUPPORTED_SPORTS: frozenset[str] = frozenset({'running', 'trail_running'})
"""
The set of FIT sport types that Ultra State processes.

Running metrics (ground contact time, vertical oscillation, cadence expressed as
strides-per-minute, aerobic decoupling, etc.) are **only meaningful for running
gait**. Importing a cycling or swimming FIT file would pollute these metrics with
nonsensical values.  The sport gatekeeper in analyzer.py uses this set to silently
skip non-running files — not as an error but as a graceful, intentional filter.

Possible Garmin sport values include 'running', 'trail_running', 'cycling',
'swimming', 'transition', 'fitness_equipment', etc.
See ARCHITECTURE.md > Data Ingestion Rules.
"""


# ── 2. RUNNING FORM VERDICTS ─────────────────────────────────────────────────

FORM_VERDICT: dict[str, dict] = {
    'ELITE_FORM': {
        'label':        'ELITE FORM',
        'color':        'text-emerald-400',
        'bg':           'border-emerald-500/30',
        'icon':         'verified',
        'prescription': 'Pro-level mechanics. Excellent turnover.',
    },
    'GOOD_FORM': {
        'label':        'GOOD FORM',
        'color':        'text-blue-400',
        'bg':           'border-blue-500/30',
        'icon':         'check_circle',
        'prescription': 'Balanced mechanics. Solid turnover.',
    },
    'HIKING_REST': {
        'label':        'HIKING / REST',
        'color':        'text-blue-400',
        'bg':           'border-blue-500/30',
        'icon':         'hiking',
        'prescription': 'Power hiking or recovery interval.',
    },
    'HEAVY_FEET': {
        'label':        'HEAVY FEET',
        'color':        'text-orange-400',
        'bg':           'border-orange-500/30',
        'icon':         'warning',
        'prescription': 'Cadence is low. Focus on quick turnover.',
    },
    'PLODDING': {
        'label':        'PLODDING',
        'color':        'text-yellow-400',
        'bg':           'border-yellow-500/30',
        'icon':         'do_not_step',
        'prescription': 'Turnover is sluggish. Pick up your feet.',
    },
}
"""
Cadence-based running form verdicts.

Cadence (steps per minute, SPM) is the most reliable proxy for running economy
that can be extracted from a consumer GPS watch without a force plate.

Elite runners typically hold 170–185 SPM regardless of pace.  Lower cadence
correlates with longer ground contact time, greater braking impulse, and higher
injury risk (particularly stress fractures and IT band issues).

Thresholds (defined in analyzer.py::analyze_form):
  ≥ 170 SPM → ELITE_FORM    (pro-level turnover)
  ≥ 160 SPM → GOOD_FORM     (balanced, efficient)
  < 135 SPM → HIKING_REST   (walking gait / power hiking)
  < 155 SPM → HEAVY_FEET    (shuffling; injury-risk zone)
  else      → PLODDING       (borderline; needs cueing)

The 'prescription' field surfaces as a coaching cue in the Running Form card
and the Understanding Running Form modal.
"""

# Convenient reverse lookup: raw label string → FORM_VERDICT key.
# Keeps UI code clean when matching against verdict strings stored in the DB.
FORM_VERDICT_BY_LABEL: dict[str, str] = {
    v['label']: k for k, v in FORM_VERDICT.items()
}


# ── 3. SPLIT / LAP QUALITY BUCKETS ───────────────────────────────────────────

class SPLIT_BUCKET:
    """
    Three-bucket quality classification applied to each recorded lap or mile split.

    HIGH_QUALITY (The Engine):
        Good cadence (≥ 160 SPM) AND meaningful aerobic effort (HR > Zone 2 floor)
        AND flat-to-rolling terrain (grade ≤ 8%).  These splits build fitness
        without structural damage — the gold standard.

    STRUCTURAL (The Base):
        Steep terrain (grade > 8%), very low cadence (< 140 SPM), or sub-Zone-2
        HR.  Includes power hiking, recovery shuffles, and steep climbing.  These
        miles build durability and aerobic base with minimal mechanical stress.
        *Not* junk — they're intentional volume.

    BROKEN (The Junk):
        Everything else.  High HR + low cadence = form falling apart, usually at
        the end of long runs or in fatigue.  These miles carry injury risk.

    The raw string values are stored in the database and embedded in Vue3 template
    comparisons (v-if / ternary expressions) in app.py, so they must remain stable
    across refactors.
    """
    HIGH_QUALITY: str = 'HIGH QUALITY'
    STRUCTURAL:   str = 'STRUCTURAL'
    BROKEN:       str = 'BROKEN'

    ALL: tuple[str, ...] = ('HIGH QUALITY', 'STRUCTURAL', 'BROKEN')

    # Human-readable display labels (used in chart traces)
    DISPLAY_LABELS: dict[str, str] = {
        'HIGH QUALITY': 'High Quality',
        'STRUCTURAL':   'Structural',
        'BROKEN':       'Broken',
    }

    # Chart trace colours
    COLORS: dict[str, str] = {
        'HIGH QUALITY': '#10b981',   # Emerald
        'STRUCTURAL':   '#3b82f6',   # Blue
        'BROKEN':       '#f43f5e',   # Rose-red
    }

    # Hover subtitle shown in the Quality lens chart
    SUBTITLES: dict[str, str] = {
        'HIGH QUALITY': 'Dialed Mechanics',
        'STRUCTURAL':   'Valid Base/Hills',
        'BROKEN':       'Mechanical Failure',
    }


# ── 4. TRAINING EFFECT LABELS ────────────────────────────────────────────────

TE_LABEL: dict[str, dict] = {
    'MAX_POWER': {
        'label': '🚀 MAX POWER',
        'color': 'text-purple-400',
    },
    'ANAEROBIC': {
        'label': '🔋 ANAEROBIC',
        'color': 'text-orange-400',
    },
    'VO2_MAX': {
        'label': '🫀 VO2 MAX',
        'color': 'text-red-400',
    },
    'THRESHOLD': {
        'label': '📈 THRESHOLD',
        'color': 'text-emerald-400',
    },
}
"""
Garmin Training Effect label taxonomy.

Garmin's Training Effect (TE) scores (0.0–5.0) model the physiological stimulus
of a workout using EPOC (Excess Post-exercise Oxygen Consumption) estimation.

Two scores are stored per activity:
  • total_training_effect        — aerobic stimulus
  • total_anaerobic_training_effect — anaerobic stimulus

Ultra State applies a 'Selective Adaptation Filter' to surface only the most
meaningful coaching signal (see FitAnalyzer.get_training_label in analyzer.py):

  Anaerobic ≥ 3.5               → MAX_POWER   (undeniable sprint load)
  Anaerobic ≥ 2.5 AND close     → ANAEROBIC   (speed/power work)
  Aerobic   ≥ 4.2               → VO2_MAX     (VO2max ceiling push)
  Aerobic   ≥ 3.5               → THRESHOLD   (lactate-threshold effort)
  else                          → None        (base / recovery — no label shown)

Note: 'None' is a valid return — base runs intentionally show no TE label
to reduce UI noise.
"""

# Convenience mapping used in the detail modal icon strip
TE_ICON_MAP: dict[str, dict] = {
    'VO2 MAX':    {'icon': '🫀', 'color': 'fuchsia'},
    'ANAEROBIC':  {'icon': '🔋', 'color': 'orange'},
    'THRESHOLD':  {'icon': '📈', 'color': 'emerald'},
    'MAX POWER':  {'icon': '🚀', 'color': 'purple'},
}
"""
Lookup keyed by the raw te_label string stored in the database (the full
emoji+text string returned by get_training_label, stripped to the keyword
portion for matching).  Used by the activity strip tag renderer in app.py.
"""


# ── 5. LOAD CATEGORIES ────────────────────────────────────────────────────────

class LOAD_CATEGORY:
    """
    Four-bucket TRIMP-based internal load classification per workout.

    Training Load is calculated using a TRIMP (Training Impulse) model that
    weights each heart-rate sample by an exponential factor.  The resulting
    score models the physiological cost of the session.

    Thresholds (applied in app.py load chart logic):
      < 75   → RECOVERY      Promotes adaptation; no new fitness stimulus.
      75–150 → BASE          Aerobic aerobic work; the target for ~80% of volume.
      150–300 → OVERLOAD     High stimulus; requires recovery between sessions.
      ≥ 300  → OVERREACHING  Dangerous; repeated exposure leads to injury/staleness.

    Canonical UI terminology (enforced across the whole app):
      'Recovery'    — not 'easy' or 'zone1'
      'Base'        — not 'Maintenance' or 'Productive' (old Garmin default)
      'Overload'    — not 'Productive' (the term we renamed for clarity)
      'Overreaching' — not 'Overtraining' (different physiological state)
    """
    RECOVERY:     str = 'Recovery'
    BASE:         str = 'Base'
    OVERLOAD:     str = 'Overload'
    OVERREACHING: str = 'Overreaching'

    ALL: tuple[str, ...] = ('Recovery', 'Base', 'Overload', 'Overreaching')

# Load category Tailwind colour classes (used in feed cards and charts)
LOAD_CATEGORY_COLORS: dict[str, str] = {
    'Recovery':     '#60a5fa',   # Blue-400  — easy, no stress
    'Base':         '#10B981',   # Emerald   — constructive aerobic work
    'Overload':     '#f97316',   # Orange    — hard effort, high stimulus
    'Overreaching': '#ef4444',   # Red       — dangerous overload
}

LOAD_CATEGORY_DESCRIPTIONS: dict[str, str] = {
    'Recovery':     'Low stress, promotes adaptation',
    'Base':         'Steady load, builds aerobic fitness',
    'Overload':     'High stimulus, needs recovery between sessions',
    'Overreaching': 'Very high stress, needs recovery',
}

LOAD_CATEGORY_EMOJI: dict[str, str] = {
    'Recovery':     '🧘',
    'Base':         '🔷',
    'Overload':     '🔥',
    'Overreaching': '🚨',
}


# ── 6. LOAD MIX VERDICTS ─────────────────────────────────────────────────────

LOAD_MIX_VERDICT: dict[str, dict] = {
    'ZONE_2_BASE': {
        'label':       'ZONE 2 BASE',
        'description': (
            'Nearly all Zone 1-2. This is where mitochondrial magic happens — '
            'fat oxidation, capillary density, cardiac efficiency. Great for base '
            'building, but one hard session per week rounds it out.'
        ),
    },
    'ZONE_3_JUNK': {
        'label':       'ZONE 3 JUNK',
        'description': (
            'Too much time in the moderate zone without enough easy. This leads to '
            'chronic fatigue without the recovery to absorb it. Swap some tempo '
            'runs for true easy days.'
        ),
    },
    'ZONE_4_THRESHOLD_ADDICT': {
        'label':       'ZONE 4 THRESHOLD ADDICT',
        'description': (
            'Too much VO2max-level effort. Zone 5 is powerful but demands ~48h '
            'recovery between sessions. Back off and rebuild your aerobic base — '
            'the speed will come back faster.'
        ),
    },
    'TEMPO_HEAVY': {
        'label':       'TEMPO HEAVY',
        'description': (
            'This provides a strong fitness stimulus (Tempo/Threshold), but carries '
            'a higher recovery cost. Treat these as "hard days" and do not do them '
            'back-to-back.'
        ),
    },
    'TEMPO_THRESHOLD': {
        'label':       'TEMPO / THRESHOLD',
        'description': (
            'High intensity speed work that builds race-pace durability. Expect '
            'higher cardiac strain.'
        ),
    },
}
"""
Weekly training mix verdicts derived from the volume-lens chart.

Endurance training science (Seiler's polarised model, Lydiard's pyramid) shows
that elite runners do ~80% of volume at easy/moderate aerobic intensity and ~20%
at high intensity.  Deviating from this ratio causes:
  • Too much Zone 3: 'Grey Zone' — hard enough to accumulate fatigue, easy enough
    to skip meaningful adaptation.  The worst of both worlds.
  • Too much Zone 4–5: CNS burnout, cumulative injury, performance plateau.
  • Too much Zone 1 only: No supramaximal stimulus; fitness plateau after a point.

These verdicts surface in the _build_load_verdict() / _build_hr_verdict() methods
in app.py and in the 'Understanding Training Load' modal.
"""


# ── 7. TIMEFRAME OPTIONS ──────────────────────────────────────────────────────

TIMEFRAME_OPTIONS: list[str] = [
    'Last Import',
    'Last 30 Days',
    'Last 90 Days',
    'This Year',
    'All Time',
]
"""
Ordered list of timeframe filter options.  The UI select is built from this list,
so adding a new option here (e.g. 'Last 6 Months') automatically surfaces it in
the dropdown without touching the UI layout code.

'Last Import' is a session-based filter that shows only the most recent batch
of activities ingested together (same session_id), useful for previewing a
freshly-uploaded race.
"""

DEFAULT_TIMEFRAME: str = 'Last 30 Days'


# ── 8. MODAL TITLES ───────────────────────────────────────────────────────────

class MODAL_TITLES:
    """
    Canonical titles for the informational modals in the app.

    Each modal explains a specific sports-science concept.  Centralising titles
    here ensures consistent wording across the trigger button label, the modal
    header, and any deep-link references in coaching copy.
    """
    AEROBIC_EFFICIENCY:    str = 'Understanding Aerobic Efficiency'
    RUNNING_FORM:          str = 'Understanding Running Form'
    TRAINING_LOAD:         str = 'Training Load Analysis'
    AEROBIC_DECOUPLING:    str = 'Aerobic Decoupling'
    HEART_RATE_RECOVERY:   str = 'Heart Rate Recovery (1-Min)'
    HEART_RATE_ZONES:      str = 'Heart Rate Zones Analysis'
    LIBRARY_SETTINGS:      str = 'Library Settings'


# ── 9. UI COPY ────────────────────────────────────────────────────────────────

class UI_COPY:
    """
    Short, reusable copy snippets that appear in multiple places across the UI.

    Centralising these prevents drift (e.g. the same concept described two slightly
    different ways in a tooltip vs. a modal).

    Each attribute is a plain string.  Format strings (f-strings) that require
    runtime values are NOT stored here — only static, context-free copy.
    """
    # Metric one-liners (tooltips / card subtitles)
    EF_SUBTITLE             = 'Efficiency Factor (Speed / Heart Rate). Measures output per heartbeat. Higher is better.'
    DECOUPLING_SUBTITLE     = 'Aerobic Decoupling (Pa:HR). Measures Cardiac Drift—how much HR rises while pace stays steady. Target < 5%.'
    HRR_SUBTITLE            = 'Measures how fast your heart rate drops 60 seconds after pressing STOP. Faster recovery = better aerobic fitness.'
    CADENCE_SUBTITLE        = 'Steps per minute (SPM). Higher cadence generally means shorter ground contact, less braking force, and more efficient energy transfer. Most elite runners are 170–185 SPM.'
    STRIDE_SUBTITLE         = 'Stride Length. Distance covered in one step. Should increase naturally with speed, not by overreaching.'
    LOAD_SUBTITLE           = 'Training Load measures workout stress by analyzing duration and heart rate intensity. Higher intensity efforts are weighted more heavily.'

    # Decoupling thresholds (shown in tooltip and info modal)
    DECOUPLING_EXCELLENT    = '< 5%: Excellent aerobic endurance'
    DECOUPLING_HIGH_FATIGUE = '> 10%: High Fatigue / Undeveloped Base'

    # Load category prose (used in info modals and AI export)
    RECOVERY_PROSE = (
        'Easy effort to promote blood flow. This facilitates repair without adding '
        'new structural damage.'
    )
    BASE_PROSE = (
        'Low-intensity endurance work. This builds mitochondrial density and teaches '
        'your body to burn fat efficiently.'
    )
    OVERLOAD_PROSE = (
        "Heavy productive volume — you're pushing hard. This builds fitness fast but "
        "can't be sustained indefinitely. Plan a step-back week every 3-4 weeks."
    )
    OVERREACHING_PROSE = (
        'Too many high-stress sessions. An occasional spike is fine, but repeated '
        'overreaching leads to injury and staleness. Follow with an easy week.'
    )

    # Sync / library copy
    LIBRARY_NOT_CONFIGURED  = '⚠ Setup Library'
    SYNC_ERROR              = 'Sync Error'
    SYNCING                 = 'Syncing...'
    SYNCED                  = 'Synced'

    # Empty state messages
    NO_DATA                 = 'No data available. Import activities to view trends.'
    NO_RUNS_TIMEFRAME       = 'No runs found for this timeframe.'
    NO_RUNS_FILTERS         = 'No runs match these filters.'
    LOADING_ACTIVITY        = 'Loading activity details...'
