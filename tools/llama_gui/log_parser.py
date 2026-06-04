"""
Log parser for llama.cpp server output.
Parses stdout/stderr lines to extract metrics.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LogMetrics:
    prompt_tokens: int = 0
    prompt_time_ms: float = 0.0
    prompt_per_second: float = 0.0
    prompt_per_token_ms: float = 0.0

    gen_tokens: int = 0
    gen_time_ms: float = 0.0
    gen_per_second: float = 0.0
    gen_per_token_ms: float = 0.0

    total_time_ms: float = 0.0
    total_tokens: int = 0

    draft_acceptance_rate: float = 0.0
    draft_accepted: int = 0
    draft_total: int = 0

    # Cumulative session totals from "statistics …" lines
    stats_draft_gen_total: int = 0
    stats_draft_acc_total: int = 0

    graphs_reused: int = 0

    checkpoints_created: int = 0
    cache_prompts: int = 0
    cache_size_mib: float = 0.0
    cache_limit_mib: float = 0.0

    # Per-slot context sizes sniffed from "slot launch" log lines
    slot_n_ctx: dict = field(default_factory=dict, repr=False)  # {slot_id: n_ctx}

    # Per-slot PP progress from print_timing lines
    slot_ctx_tokens: dict = field(default_factory=dict, repr=False)     # {slot_id: n_tokens}
    slot_ctx_progress: dict = field(default_factory=dict, repr=False)   # {slot_id: 0..1}

    # Per-slot last checkpoint token count from create_check lines
    slot_ctx_checkpoint: dict = field(default_factory=dict, repr=False) # {slot_id: n_tokens}

    # Slots that just received a new task (launch_slot_ fired); caller should reset ctx state
    slot_task_started: list = field(default_factory=list, repr=False)   # [slot_id, ...]

    @property
    def avg_prompt_per_second(self) -> float:
        if not self._prompt_rates:
            return 0.0
        return sum(self._prompt_rates) / len(self._prompt_rates)

    @property
    def avg_gen_per_second(self) -> float:
        if not self._gen_rates:
            return 0.0
        return sum(self._gen_rates) / len(self._gen_rates)

    @property
    def avg_draft_acceptance(self) -> float:
        if not self._draft_rates:
            return 0.0
        return sum(self._draft_rates) / len(self._draft_rates)

    _prompt_rates: list = field(default_factory=list, repr=False)
    _gen_rates: list = field(default_factory=list, repr=False)
    _draft_rates: list = field(default_factory=list, repr=False)

    def add_prompt_rate(self, rate: float):
        self._prompt_rates.append(rate)

    def add_gen_rate(self, rate: float):
        self._gen_rates.append(rate)

    def add_draft_rate(self, rate: float):
        self._draft_rates.append(rate)


# Pre-compile regex patterns
PROMPT_EVAL_RE = re.compile(
    r'prompt eval time\s+=\s+([\d.]+)\s+ms\s+/\s+(\d+)\s+tokens'
    r'(?:\s+\(\s*([\d.]+)\s+ms per token,\s*([\d.]+)\s+tokens per second\))?'
)

EVAL_RE = re.compile(
    r'eval time\s+=\s+([\d.]+)\s+ms\s+/\s+(\d+)\s+tokens'
    r'(?:\s+\(\s*([\d.]+)\s+ms per token,\s*([\d.]+)\s+tokens per second\))?'
)

TOTAL_TIME_RE = re.compile(
    r'total time\s+=\s+([\d.]+)\s+ms\s+/\s+(\d+)\s+tokens'
)

DRAFT_RE = re.compile(
    r'draft acceptance\s+=\s+([\d.]+)\s+\(\s*(\d+)\s+accepted\s+/\s+(\d+)\s+generated\)'
)

GRAPHS_REUSED_RE = re.compile(r'graphs reused\s+=\s+(\d+)')

SLOT_DRAFT_RE = re.compile(r'accepted\s+(\d+)\s*/\s*(\d+)\s+draft\s+tokens')

# "statistics ngram-mod: … #gen tokens = 1632, #acc tokens = 868"
STATS_RE = re.compile(
    r'statistics\s+\S+:.*?#gen tokens\s*=\s*(\d+),\s*#acc tokens\s*=\s*(\d+)'
)

CHECKPOINT_RE = re.compile(
    r'created context checkpoint\s+(\d+)\s+of\s+(\d+)'
    r'\s*\(\s*pos_min\s*=\s*(-?\d+),\s*pos_max\s*=\s*(-?\d+),'
    r'\s*n_tokens\s*=\s*(-?\d+),\s*size\s*=\s*([\d.]+)\s+MiB\s*\)'
)

PROMPT_CACHE_RE = re.compile(
    r'cache state:\s+(\d+)\s+prompts,\s+([\d.]+)\s+MiB'
    r'(?:\s*\(limits:\s*([\d.]+)\s+MiB,\s+(\d+)\s+tokens,\s+\d+\s+est\))?'
)

# "id  3 | task 18 | prompt processing, n_tokens =   2048, progress = 0.02, t = ..."
SLOT_PP_PROGRESS_RE = re.compile(
    r'id\s+(\d+)\s*\|.*?prompt processing,\s*n_tokens\s*=\s*(\d+)'
    r',\s*progress\s*=\s*([\d.]+).*?/\s*([\d.]+)\s+tokens\s+per\s+second'
)

# "id  3 | task 18 | created context checkpoint 1 of 128 (pos_min=..., n_tokens = 4096, ...)"
SLOT_CHECKPOINT_RE = re.compile(
    r'id\s+(\d+)\s*\|.*?created context checkpoint[^(]*\([^)]*n_tokens\s*=\s*(\d+)'
)

# "id  3 | task 18 | processing task, is_child = 0"
SLOT_TASK_START_RE = re.compile(
    r'launch_slot_.*?id\s+(\d+)\s*\|.*?task\s+(\d+)'
)

GEN_PROGRESS_RE = re.compile(
    r'n_decoded\s*=\s*(\d+),\s*tg\s*=\s*([\d.]+)\s+t/s'
)

LOADING_RE = re.compile(r'loading model')
MODEL_LOADED_RE = re.compile(r'model loaded')
SERVER_LISTENING_RE = re.compile(r'server is listening on\s+(.*)')

# "slot   load_model: id  0 | task -1 | new slot, n_ctx = 128000"
SLOT_LAUNCH_RE = re.compile(r'slot\s+load_model:.*\bid\s+(\d+).*\bn_ctx\s*=\s*(\d+)')


def parse_line(line: str, metrics: LogMetrics) -> Optional[str]:
    """Parse a single log line and update metrics. Returns event type if detected."""

    if LOADING_RE.search(line):
        return 'loading'

    if MODEL_LOADED_RE.search(line):
        return 'loaded'

    m = SERVER_LISTENING_RE.search(line)
    if m:
        return f'listening:{m.group(1).strip()}'

    m = PROMPT_EVAL_RE.search(line)
    if m:
        time_ms = float(m.group(1))
        tokens = int(m.group(2))
        per_token = float(m.group(3)) if m.group(3) else 0.0
        per_sec = float(m.group(4)) if m.group(4) else 0.0

        metrics.prompt_tokens = tokens
        metrics.prompt_time_ms = time_ms
        metrics.prompt_per_token_ms = per_token
        metrics.prompt_per_second = per_sec
        metrics.add_prompt_rate(per_sec)

        if per_sec > 0:
            return 'prompt_eval'
        return None

    m = EVAL_RE.search(line)
    if m:
        time_ms = float(m.group(1))
        tokens = int(m.group(2))
        per_token = float(m.group(3)) if m.group(3) else 0.0
        per_sec = float(m.group(4)) if m.group(4) else 0.0

        metrics.gen_tokens = tokens
        metrics.gen_time_ms = time_ms
        metrics.gen_per_token_ms = per_token
        metrics.gen_per_second = per_sec
        metrics.add_gen_rate(per_sec)

        if per_sec > 0:
            return 'eval'
        return None

    m = TOTAL_TIME_RE.search(line)
    if m:
        metrics.total_time_ms = float(m.group(1))
        metrics.total_tokens = int(m.group(2))
        return 'total'

    m = DRAFT_RE.search(line)
    if m:
        rate = float(m.group(1))
        accepted = int(m.group(2))
        total = int(m.group(3))

        metrics.draft_acceptance_rate = rate
        metrics.draft_accepted = accepted
        metrics.draft_total = total
        metrics.add_draft_rate(rate)

        return 'draft'

    m = SLOT_DRAFT_RE.search(line)
    if m:
        accepted = int(m.group(1))
        total = int(m.group(2))
        if total > 0:
            rate = accepted / total
            metrics.draft_accepted = accepted
            metrics.draft_total = total
            metrics.add_draft_rate(rate)
            return 'draft'
        return None

    m = GRAPHS_REUSED_RE.search(line)
    if m:
        metrics.graphs_reused = int(m.group(1))
        return 'graphs'

    m = STATS_RE.search(line)
    if m:
        metrics.stats_draft_gen_total = int(m.group(1))
        metrics.stats_draft_acc_total = int(m.group(2))
        return 'draft_stats'

    # Slot task-start: reset per-slot PP state so stale data doesn't linger
    m = SLOT_TASK_START_RE.search(line)
    if m:
        slot_id = int(m.group(1))
        metrics.slot_ctx_tokens.pop(slot_id, None)
        metrics.slot_ctx_checkpoint.pop(slot_id, None)
        metrics.slot_task_started.append(slot_id)
        return 'slot_task_start'

    # Per-slot prompt-processing progress (print_timing lines)
    m = SLOT_PP_PROGRESS_RE.search(line)
    if m:
        slot_id  = int(m.group(1))
        n_tokens = int(m.group(2))
        progress = float(m.group(3))
        rate     = float(m.group(4))
        metrics.slot_ctx_tokens[slot_id]   = n_tokens
        metrics.slot_ctx_progress[slot_id] = progress
        if rate > 0:
            metrics.prompt_per_second = rate
            metrics.add_prompt_rate(rate)
        return 'slot_pp_progress'

    # Per-slot checkpoint creation (create_check lines)
    m = SLOT_CHECKPOINT_RE.search(line)
    if m:
        slot_id  = int(m.group(1))
        n_tokens = int(m.group(2))
        metrics.slot_ctx_checkpoint[slot_id] = n_tokens
        metrics.checkpoints_created += 1
        return 'slot_checkpoint'

    # Generic checkpoint counter (lines without a slot-id prefix)
    m = CHECKPOINT_RE.search(line)
    if m:
        metrics.checkpoints_created += 1
        return 'checkpoint'

    m = PROMPT_CACHE_RE.search(line)
    if m:
        metrics.cache_prompts = int(m.group(1))
        metrics.cache_size_mib = float(m.group(2))
        if m.group(3):
            metrics.cache_limit_mib = float(m.group(3))
        return 'cache'

    m = GEN_PROGRESS_RE.search(line)
    if m:
        metrics.gen_per_second = float(m.group(2))
        metrics.add_gen_rate(metrics.gen_per_second)
        return 'gen_progress'

    m = SLOT_LAUNCH_RE.search(line)
    if m:
        slot_id = int(m.group(1))
        n_ctx   = int(m.group(2))
        if n_ctx > 0:
            metrics.slot_n_ctx[slot_id] = n_ctx
        return 'slot_launch'

    return None
