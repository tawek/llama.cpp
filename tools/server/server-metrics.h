#pragma once

#include "ggml.h"

#include <atomic>
#include <cstdint>
#include <memory>
#include <string>

//
// server_slot_metrics
//
// Per-slot counters for the currently active (or most recently completed)
// request on a slot.  Reset via server_metrics::reset_slot() whenever the
// slot transitions from STARTED → PROCESSING_PROMPT (i.e. a new prompt begins).
//
struct server_slot_metrics {
    std::atomic<uint64_t> n_pp             {0}; // prompt tokens processed (pre-processed length)
    std::atomic<uint64_t> n_prompt_length  {0}; // original prompt length as passed to server
    std::atomic<uint64_t> t_pp_ms          {0}; // prompt processing time (ms)
    std::atomic<uint64_t> n_tg             {0}; // generation tokens
    std::atomic<uint64_t> t_tg_ms          {0}; // token generation time (ms)
    std::atomic<uint64_t> n_draft          {0}; // speculative draft tokens proposed
    std::atomic<uint64_t> n_draft_accepted {0}; // speculative draft tokens accepted

    void reset();
    uint64_t n_draft_rejected() const;
};

//
// server_metrics
//
// Unified, lock-free metrics for the whole server.
//
// Threading model:
//   - All on_*() / set_deferred() / reset_slot() methods must be called
//     from the task thread only.
//   - reset_global() may be called from any thread (POST /metrics handler).
//   - to_prometheus() and all read accessors are safe from any thread.
//
// Reset policy:
//   - Global counters reset via reset_global() (POST /metrics {"reset":true}).
//     n_tokens_max is intentionally excluded — it is a high-water mark.
//   - Per-slot counters reset via reset_slot(id) when a slot starts a new prompt.
//
// Lifecycle:
//   - init(n_slots) MUST be called once before any other method.
//     It initialises the per-slot array (slots_) and records t_start.
//   - On sleep/wake, the slot count is the same (same params_base), so init()
//     does not need to be called again.
//
struct server_metrics {
    // ── Server start time ────────────────────────────────────────────────────
    // Written once in init(), never changes.  Plain int64_t is sufficient
    // (init() runs before any HTTP thread is started).
    int64_t t_start = 0;

    // ── Global counters ───────────────────────────────────────────────────────
    // Accumulated since server start (or last reset_global()).

    // Prompt processing.
    // n_pp is updated in real-time via the llama_pp_eval_callback (fires once
    // per ubatch during llama_decode).  t_pp_ms is updated at end-of-PP for
    // each slot (when the first generation token appears).
    std::atomic<uint64_t> n_pp             {0};
    std::atomic<uint64_t> t_pp_ms          {0};

    // Token generation.
    std::atomic<uint64_t> n_tg             {0};
    std::atomic<uint64_t> t_tg_ms          {0};

    // Speculative decoding.
    std::atomic<uint64_t> n_draft          {0}; // total draft tokens proposed
    std::atomic<uint64_t> n_draft_accepted {0}; // draft tokens accepted

    // llama_decode() call count and busy-slot accumulator.
    std::atomic<uint64_t> n_decode         {0};
    std::atomic<uint64_t> n_busy_slots_acc {0}; // sum of busy-slots-per-decode

    // ── Global high-water mark (NOT reset by reset_global) ───────────────────
    std::atomic<uint64_t> n_tokens_max     {0};

    // ── Gauge snapshots (stale by ≤ 1 update_slots() cycle) ─────────────────
    std::atomic<int> n_processing_slots    {0};
    std::atomic<int> n_tasks_deferred      {0};

    // ── Lifecycle ─────────────────────────────────────────────────────────────
    // MUST be called once, with n_slots > 0, before any other method.
    void init(int n_slots);

    // ── Per-slot accessor ────────────────────────────────────────────────────
    // Asserts that init() has been called and 0 <= id < n_slots.
          server_slot_metrics & slot(int id);
    const server_slot_metrics & slot(int id) const;
    int slot_count() const { return n_slots_; }

    // ── Update methods (task thread only) ────────────────────────────────────

    // From llama_pp_eval_callback — no slot_id (ubatch may span several slots).
    void on_pp_tokens(uint32_t n);

    // Incremental per-slot prompt tokens processed during PP (real-time tracking).
    void on_pp_tokens_slot(int slot_id, uint32_t n);

    // Called when the first generation token appears for a slot (prompt eval done).
    //   t_ms         = slot.t_prompt_processing
    //   prompt_len   = slot.prompt.n_tokens()
    void on_pp_eval(int slot_id, double t_ms, uint64_t prompt_len);

    // Called each time a generation token is produced.
    void on_tg_token(int slot_id);

    // Called when a slot finishes generating (stop condition met).
    //   t_gen_ms = slot.t_token_generation  (total elapsed generation time)
    void on_tg_done(int slot_id, double t_gen_ms);

    // Speculative decoding counters.
    void on_draft_tokens  (int slot_id, size_t n); // proposed
    void on_draft_accepted(int slot_id, size_t n); // accepted

    // Called once per llama_decode() call.
    //   n_busy      = number of slots that were processing during this decode
    //   tokens_max  = max prompt.n_tokens() across all slots this call
    void on_decoded(uint64_t n_busy, uint64_t tokens_max);

    // Snapshot the deferred-queue depth; call from update_slots().
    void set_deferred(int n);

    // Reset per-slot counters — call when slot state STARTED → PROCESSING_PROMPT.
    void reset_slot(int slot_id);

    // ── Global reset (POST /metrics {"reset":true}) ───────────────────────────
    // Safe to call from any thread.
    void reset_global();

    // ── Derived gauge values (any thread) ─────────────────────────────────────
    double   pp_tokens_per_sec    () const;
    double   tg_tokens_per_sec    () const;
    float    busy_slots_per_decode() const;
    uint64_t n_draft_rejected     () const;

    // ── Prometheus text body (any thread) ────────────────────────────────────
    std::string to_prometheus() const;

private:
    // Heap-allocated array of per-slot metrics; allocated in init().
    // Size == n_slots_.  Null until init() is called.
    std::unique_ptr<server_slot_metrics[]> slots_;
    int n_slots_ = 0;

    void bump_tokens_max(uint64_t v);
};
