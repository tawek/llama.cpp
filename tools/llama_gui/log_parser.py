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

    graphs_reused: int = 0

    checkpoints_created: int = 0
    cache_prompts: int = 0
    cache_size_mib: float = 0.0
    cache_limit_mib: float = 0.0

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

CHECKPOINT_RE = re.compile(
    r'created context checkpoint\s+(\d+)\s+of\s+(\d+)'
    r'\s*\(\s*pos_min\s*=\s*(-?\d+),\s*pos_max\s*=\s*(-?\d+),'
    r'\s*n_tokens\s*=\s*(-?\d+),\s*size\s*=\s*([\d.]+)\s+MiB\s*\)'
)

PROMPT_CACHE_RE = re.compile(
    r'prompt cache state:\s+(\d+)\s+prompts,\s+([\d.]+)\s+MiB'
    r'\s*\((?:limits:\s*([\d.]+)\s+MiB,\s+(\d+)\s+tokens,\s+(\d+)\s+est\))?'
)

PROMPT_PROCESS_RE = re.compile(
    r'prompt processing.*n_tokens\s*=\s*(\d+).*t\s*=\s*([\d.]+)\s+s\s*/\s*([\d.]+)\s+tokens\s+per\s+second'
)

LOADING_RE = re.compile(r'loading model')
MODEL_LOADED_RE = re.compile(r'model loaded')
SERVER_LISTENING_RE = re.compile(r'server is listening on\s+(.*)')


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

    m = PROMPT_PROCESS_RE.search(line)
    if m:
        tokens = int(m.group(1))
        time_s = float(m.group(2))
        rate = float(m.group(3))
        if rate > 0:
            metrics.add_prompt_rate(rate)
        return 'prompt_process'

    return None
