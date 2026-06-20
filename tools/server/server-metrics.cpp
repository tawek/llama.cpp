#include "server-metrics.h"

#include "server-common.h"

#include <algorithm>
#include <sstream>

// ── server_slot_metrics ───────────────────────────────────────────────────────

void server_slot_metrics::reset() {
    n_pp            .store(0, std::memory_order_relaxed);
    n_prompt_length .store(0, std::memory_order_relaxed);
    t_pp_ms         .store(0, std::memory_order_relaxed);
    n_tg            .store(0, std::memory_order_relaxed);
    t_tg_ms         .store(0, std::memory_order_relaxed);
    n_draft         .store(0, std::memory_order_relaxed);
    n_draft_accepted.store(0, std::memory_order_relaxed);
    t_start_pp      .store(0, std::memory_order_relaxed);
}

uint64_t server_slot_metrics::n_draft_rejected() const {
    const uint64_t td  = n_draft         .load(std::memory_order_relaxed);
    const uint64_t tda = n_draft_accepted.load(std::memory_order_relaxed);
    return td >= tda ? td - tda : 0;
}

// ── server_metrics — private helpers ─────────────────────────────────────────

void server_metrics::bump_tokens_max(uint64_t v) {
    uint64_t cur = n_tokens_max.load(std::memory_order_relaxed);
    while (v > cur &&
           !n_tokens_max.compare_exchange_weak(cur, v, std::memory_order_relaxed)) {}
}

// ── server_metrics — per-slot accessor (with bounds check) ───────────────────

server_slot_metrics & server_metrics::slot(int id) {
    GGML_ASSERT(slots_ != nullptr && "server_metrics::init() was not called");
    GGML_ASSERT(id >= 0 && id < n_slots_ && "slot id out of range");
    return slots_[id];
}

const server_slot_metrics & server_metrics::slot(int id) const {
    GGML_ASSERT(slots_ != nullptr && "server_metrics::init() was not called");
    GGML_ASSERT(id >= 0 && id < n_slots_ && "slot id out of range");
    return slots_[id];
}

// ── server_metrics — lifecycle ────────────────────────────────────────────────

void server_metrics::init(int n_slots) {
    GGML_ASSERT(n_slots > 0 && "server_metrics::init() requires n_slots > 0");
    t_start  = ggml_time_us();
    n_slots_ = n_slots;
    slots_   = std::make_unique<server_slot_metrics[]>(n_slots);
}

// ── server_metrics — update methods ──────────────────────────────────────────

void server_metrics::on_pp_tokens(uint32_t n) {
    n_pp.fetch_add(n, std::memory_order_relaxed);
}

void server_metrics::on_pp_start_slot(int slot_id, int64_t t_start_us) {
    slot(slot_id).t_start_pp.store(t_start_us, std::memory_order_relaxed);
}

void server_metrics::on_pp_tokens_slot(int slot_id, uint32_t n) {
    slot(slot_id).n_pp.fetch_add(n, std::memory_order_relaxed);
}

void server_metrics::on_pp_eval(int slot_id, double t_ms, uint64_t prompt_len) {
    t_pp_ms.fetch_add((uint64_t) t_ms, std::memory_order_relaxed);
    bump_tokens_max(prompt_len);

    auto & s = slot(slot_id);
    // n_pp = total prompt length (includes cache hits), so it matches
    // n_prompt_length when prompt eval completes.
    s.n_pp           .store(prompt_len, std::memory_order_relaxed);
    s.n_prompt_length.store(prompt_len, std::memory_order_relaxed);
    s.t_pp_ms        .store((uint64_t) t_ms,  std::memory_order_relaxed);
}

void server_metrics::on_tg_token(int slot_id) {
    n_tg.fetch_add(1, std::memory_order_relaxed);
    slot(slot_id).n_tg.fetch_add(1, std::memory_order_relaxed);
}

void server_metrics::on_tg_done(int slot_id, double t_gen_ms) {
    t_tg_ms.fetch_add((uint64_t) t_gen_ms, std::memory_order_relaxed);
    slot(slot_id).t_tg_ms.store((uint64_t) t_gen_ms, std::memory_order_relaxed);
}

void server_metrics::on_draft_tokens(int slot_id, size_t n) {
    n_draft.fetch_add(n, std::memory_order_relaxed);
    slot(slot_id).n_draft.fetch_add(n, std::memory_order_relaxed);
}

void server_metrics::on_draft_accepted(int slot_id, size_t n) {
    n_draft_accepted.fetch_add(n, std::memory_order_relaxed);
    slot(slot_id).n_draft_accepted.fetch_add(n, std::memory_order_relaxed);
}

void server_metrics::on_decoded(uint64_t n_busy, uint64_t tokens_max) {
    n_decode        .fetch_add(1,      std::memory_order_relaxed);
    n_busy_slots_acc.fetch_add(n_busy, std::memory_order_relaxed);
    n_processing_slots.store((int) n_busy, std::memory_order_relaxed);
    bump_tokens_max(tokens_max);
}

void server_metrics::set_deferred(int n) {
    n_tasks_deferred.store(n, std::memory_order_relaxed);
}

void server_metrics::reset_slot(int slot_id) {
    slot(slot_id).reset();
}

void server_metrics::reset_global() {
    n_pp            .store(0, std::memory_order_relaxed);
    t_pp_ms         .store(0, std::memory_order_relaxed);
    n_tg            .store(0, std::memory_order_relaxed);
    t_tg_ms         .store(0, std::memory_order_relaxed);
    n_draft         .store(0, std::memory_order_relaxed);
    n_draft_accepted.store(0, std::memory_order_relaxed);
    n_decode        .store(0, std::memory_order_relaxed);
    n_busy_slots_acc.store(0, std::memory_order_relaxed);
    // n_tokens_max, n_processing_slots, n_tasks_deferred intentionally kept
}

// ── server_metrics — derived values ──────────────────────────────────────────

double server_metrics::pp_tokens_per_sec() const {
    const uint64_t n = n_pp   .load(std::memory_order_relaxed);
    const uint64_t t = t_pp_ms.load(std::memory_order_relaxed);
    return (n && t) ? 1.e3 / t * n : 1.0;
}

double server_metrics::tg_tokens_per_sec() const {
    const uint64_t n = n_tg   .load(std::memory_order_relaxed);
    const uint64_t t = t_tg_ms.load(std::memory_order_relaxed);
    return (n && t) ? 1.e3 / t * n : 1.0;
}

float server_metrics::busy_slots_per_decode() const {
    return (float) n_busy_slots_acc.load(std::memory_order_relaxed)
         / std::max((float) n_decode.load(std::memory_order_relaxed), 1.f);
}

uint64_t server_metrics::n_draft_rejected() const {
    const uint64_t td  = n_draft         .load(std::memory_order_relaxed);
    const uint64_t tda = n_draft_accepted.load(std::memory_order_relaxed);
    return td >= tda ? td - tda : 0;
}

// ── server_metrics — Prometheus output ───────────────────────────────────────
//
// Prometheus exposition format rules:
//   - Each metric family emits exactly one # HELP and one # TYPE line.
//   - All time-series for that family follow immediately.
//   - Labeled series use {key="value"} selector syntax.
//
std::string server_metrics::to_prometheus() const {
    // Snapshot all globals once for a consistent read.
    const uint64_t s_n_pp             = n_pp            .load(std::memory_order_relaxed);
    const uint64_t s_t_pp_ms          = t_pp_ms         .load(std::memory_order_relaxed);
    const uint64_t s_n_tg             = n_tg            .load(std::memory_order_relaxed);
    const uint64_t s_t_tg_ms          = t_tg_ms         .load(std::memory_order_relaxed);
    const uint64_t s_n_draft          = n_draft         .load(std::memory_order_relaxed);
    const uint64_t s_n_draft_accepted = n_draft_accepted.load(std::memory_order_relaxed);
    const uint64_t s_n_decode         = n_decode        .load(std::memory_order_relaxed);
    const uint64_t s_n_busy_slots_acc = n_busy_slots_acc.load(std::memory_order_relaxed);
    const uint64_t s_n_tokens_max     = n_tokens_max    .load(std::memory_order_relaxed);
    const int      s_n_processing     = n_processing_slots.load(std::memory_order_relaxed);
    const int      s_n_deferred       = n_tasks_deferred  .load(std::memory_order_relaxed);

    const uint64_t s_n_draft_rejected = s_n_draft >= s_n_draft_accepted
                                      ? s_n_draft - s_n_draft_accepted : 0;
    const double   s_pp_rate   = (s_n_pp && s_t_pp_ms)
                                 ? 1.e3 / s_t_pp_ms * s_n_pp : 0.0;
    const double   s_tg_rate   = (s_n_tg && s_t_tg_ms)
                                 ? 1.e3 / s_t_tg_ms * s_n_tg : 0.0;
    const float    s_busy_avg  = (float) s_n_busy_slots_acc
                               / std::max((float) s_n_decode, 1.f);

    std::stringstream out;

    // Helper: emit a single-family block (HELP + TYPE + one unlabeled value).
    auto emit = [&out](const char * type, const char * name, const char * help, double value) {
        out << "# HELP llamacpp:" << name << " " << help  << "\n"
            << "# TYPE llamacpp:" << name << " " << type  << "\n"
            << "llamacpp:" << name << " " << value << "\n";
    };

    // Helper: emit HELP+TYPE header then a block of labeled values.
    // `rows` is a list of (label_value, numeric_value) pairs.
    auto emit_labeled = [&out](const char * type, const char * name, const char * help,
                               const char * label_key,
                               const std::vector<std::pair<std::string, double>> & rows) {
        out << "# HELP llamacpp:" << name << " " << help << "\n"
            << "# TYPE llamacpp:" << name << " " << type << "\n";
        for (const auto & [lv, v] : rows) {
            out << "llamacpp:" << name << "{" << label_key << "=\"" << lv << "\"} " << v << "\n";
        }
    };

    // ── Global counters ────────────────────────────────────────────────────
    emit("counter", "prompt_tokens_total",            "Number of prompt tokens processed.",             (double) s_n_pp);
    emit("counter", "prompt_seconds_total",           "Prompt process time",                            (double) s_t_pp_ms / 1.e3);
    emit("counter", "tokens_predicted_total",         "Number of generation tokens processed.",         (double) s_n_tg);
    emit("counter", "tokens_predicted_seconds_total", "Predict process time",                           (double) s_t_tg_ms / 1.e3);
    emit("counter", "n_decode_total",                 "Total number of llama_decode() calls",           (double) s_n_decode);
    emit("counter", "n_tokens_max",                   "Largest observed prompt n_tokens (high-water mark).", (double) s_n_tokens_max);
    emit("counter", "n_tokens_draft",                 "Total speculative draft tokens proposed.",       (double) s_n_draft);
    emit("counter", "n_tokens_draft_accepted",        "Total speculative draft tokens accepted.",       (double) s_n_draft_accepted);
    emit("counter", "n_tokens_draft_rejected",        "Total speculative draft tokens rejected.",       (double) s_n_draft_rejected);

    // ── Global gauges ──────────────────────────────────────────────────────
    emit("gauge", "prompt_tokens_seconds",    "Average prompt throughput in tokens/s.",           s_pp_rate);
    emit("gauge", "predicted_tokens_seconds", "Average generation throughput in tokens/s.",        s_tg_rate);
    emit("gauge", "requests_processing",      "Number of requests currently processing.",          (double) s_n_processing);
    emit("gauge", "requests_deferred",        "Number of requests currently deferred.",            (double) s_n_deferred);
    emit("gauge", "n_busy_slots_per_decode",  "Average busy slots per llama_decode() call.",       s_busy_avg);

    // ── Per-slot gauges ────────────────────────────────────────────────────
    // Each metric family emits HELP+TYPE once, then one labeled line per slot.
    if (n_slots_ > 0) {
        // Snapshot all slot values first.
        struct SlotSnap {
            uint64_t n_pp, n_prompt_length, t_pp_ms, n_tg, t_tg_ms, n_draft, n_draft_accepted, n_draft_rejected;
        };
        std::vector<SlotSnap> snaps(n_slots_);
        for (int i = 0; i < n_slots_; ++i) {
            const auto & s = slot(i);
            snaps[i].n_pp             = s.n_pp            .load(std::memory_order_relaxed);
            snaps[i].n_prompt_length  = s.n_prompt_length .load(std::memory_order_relaxed);
            snaps[i].t_pp_ms          = s.t_pp_ms         .load(std::memory_order_relaxed);
            snaps[i].n_tg             = s.n_tg            .load(std::memory_order_relaxed);
            snaps[i].t_tg_ms          = s.t_tg_ms         .load(std::memory_order_relaxed);
            snaps[i].n_draft          = s.n_draft         .load(std::memory_order_relaxed);
            snaps[i].n_draft_accepted = s.n_draft_accepted.load(std::memory_order_relaxed);
            snaps[i].n_draft_rejected = snaps[i].n_draft >= snaps[i].n_draft_accepted
                                      ? snaps[i].n_draft - snaps[i].n_draft_accepted : 0;
        }

        // Build row vectors and emit each family in one shot.
        // Integral fields:
        auto irows = [&](auto field) {
            std::vector<std::pair<std::string, double>> r;
            r.reserve(n_slots_);
            for (int i = 0; i < n_slots_; ++i) {
                r.emplace_back(std::to_string(i), (double) (snaps[i].*field));
            }
            return r;
        };
        // Time fields stored in ms → convert to seconds for Prometheus convention.
        auto trows = [&](auto field) {
            std::vector<std::pair<std::string, double>> r;
            r.reserve(n_slots_);
            for (int i = 0; i < n_slots_; ++i) {
                r.emplace_back(std::to_string(i), (double) (snaps[i].*field) / 1.e3);
            }
            return r;
        };

        emit_labeled("gauge", "slot_prompt_tokens_processed",
                     "Prompt tokens processed for the current/last task per slot. Reaches slot_prompt_length when prompt eval is done.",
                     "id_slot", irows(&SlotSnap::n_pp));
        emit_labeled("gauge", "slot_prompt_length",
                     "Original prompt length as passed to the server per slot.",
                     "id_slot", irows(&SlotSnap::n_prompt_length));
        emit_labeled("gauge", "slot_prompt_seconds",
                     "Prompt processing time (s) for the current/last task per slot.",
                     "id_slot", trows(&SlotSnap::t_pp_ms));
        emit_labeled("gauge", "slot_tokens_predicted",
                     "Generation tokens produced for the current/last task per slot.",
                     "id_slot", irows(&SlotSnap::n_tg));
        emit_labeled("gauge", "slot_tokens_predicted_seconds",
                     "Generation time (s) for the current/last task per slot.",
                     "id_slot", trows(&SlotSnap::t_tg_ms));
        emit_labeled("gauge", "slot_n_tokens_draft",
                     "Draft tokens proposed for the current/last task per slot.",
                     "id_slot", irows(&SlotSnap::n_draft));
        emit_labeled("gauge", "slot_n_tokens_draft_accepted",
                     "Draft tokens accepted for the current/last task per slot.",
                     "id_slot", irows(&SlotSnap::n_draft_accepted));
        emit_labeled("gauge", "slot_n_tokens_draft_rejected",
                     "Draft tokens rejected for the current/last task per slot.",
                     "id_slot", irows(&SlotSnap::n_draft_rejected));
    }

    return out.str();
}
