---
title: "I Fine-Tuned a Local Model and Tested: Here's What It Actually Learned"
date: 2026-07-28
summary: "MLX LoRA on Apple Silicon: build a dataset, score a baseline, train an adapter, and check whether it actually learned anything — without mistaking loss for correctness."
---

**Estimated read time:** 10-12 minutes

---

I had a narrow question: can I fine-tune a small model on my Mac and show, not assume, that the adapter learned something the base model didn't know?

This isn't a benchmark or a product pitch. It's a lab write-up for engineers who've shipped systems but never trained an LLM (me included).

Setup:

- `mlx-community/Qwen2.5-3B-Instruct-4bit`
- MLX + MLX-LM on Apple Silicon
- LoRA adapter, not full fine-tune
- Six facts pulled from my agent-security lab
- Two synthetic canaries the base model can't know from pretraining
- Baseline scored before training; adapted model scored after

Getting `mlx_lm.lora` to exit 0 proves the pipeline ran. It doesn't prove the adapter learned anything. That's what the scoring is for.

## What This Experiment Can Prove

Three claims, increasing ambition:

1. **Pipeline success:** MLX loads the model, trains an adapter, saves it, runs inference.
2. **Narrow learning:** the adapter recalls trained facts when asked with phrasing it never saw in training.
3. **Broad quality:** the model handles genuinely new facts and documents.

This run only supports #1 and #2.

## Prerequisites

Apple Silicon Mac, Git, Python 3.9+, `jq`, and `publication_dataset.json` in the repo.

```bash
git clone https://github.com/jhunter7/applied-ai-security-labs.git
cd applied-ai-security-labs

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install "mlx==0.29.3" "mlx-lm==0.29.1"

cd week-01-local-lora

command -v git
command -v jq
test -f publication_dataset.json
test -x ../.venv/bin/mlx_lm.lora
test -x ../.venv/bin/mlx_lm.generate
```

Pin the versions: mlx-lm flags change between releases.

## Step 1: Create a Fresh Run

Each run gets its own directory under `manual-run/`. I don't overwrite previous runs; they're part of the record.

Run this from `week-01-local-lora/` (where `publication_dataset.json` lives). The venv can sit in that directory or at the repo root.

```bash
# First, enter the lab inside the cloned repository.
cd /path/to/applied-ai-security-labs/week-01-local-lora

setup_publication_run() {
  unset RUN

  LAB_DIR="$PWD"

  REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || {
    echo "ERROR: run this from inside the cloned Git repository"
    return 1
  }

  if [[ ! -f "$LAB_DIR/publication_dataset.json" ]]; then
    echo "ERROR: run this from the directory containing publication_dataset.json"
    return 1
  fi

  if [[ -x "$LAB_DIR/.venv/bin/python" ]]; then
    VENV="$LAB_DIR/.venv"
  elif [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
    VENV="$REPO_ROOT/.venv"
  else
    echo "ERROR: expected .venv in $LAB_DIR or $REPO_ROOT"
    return 1
  fi

  MODEL="mlx-community/Qwen2.5-3B-Instruct-4bit"
  PYTHON="$VENV/bin/python"
  LORA="$VENV/bin/mlx_lm.lora"
  GENERATE="$VENV/bin/mlx_lm.generate"

  mkdir -p "$LAB_DIR/manual-run" || return 1

  RUN="$(
    mktemp -d \
      "$LAB_DIR/manual-run/publication-$(date +%Y%m%d-%H%M%S)-XXXXXX"
  )" || return 1

  mkdir "$RUN/data" "$RUN/evidence" || return 1

  printf 'Fresh publication run:\n%s\n' "$RUN"
  ls -la "$RUN"

  if [[ ! -e "$RUN/adapters" ]]; then
    echo "PASS: no previous adapter exists"
  fi
}

setup_publication_run
unset -f setup_publication_run
```

You should see:

```bash
PASS: no previous adapter exists
```

## Step 2: Verify and Record the Environment

Record everything before you look at results — so you can't quietly tweak a knob afterward.

```bash
{
  printf 'run=%s\n' "$RUN"
  printf 'created_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'model=%s\n' "$MODEL"
  printf 'iterations=100\n'
  printf 'batch_size=4\n'
  printf 'lora_layers=16\n'
  printf 'learning_rate=1e-5\n'
  printf 'mask_prompt=true\n'
  printf 'training_seed=0\n'
  printf 'generation_seed=42\n'
  printf 'temperature=0\n'
  printf 'max_tokens=120\n'
  sw_vers
  uname -m
  "$PYTHON" --version
  "$PYTHON" -c '
from importlib.metadata import version
import mlx.core as mx

print("mlx=" + version("mlx"))
print("mlx_lm=" + version("mlx-lm"))
print("device=" + str(mx.default_device()))
print("metal_available=" + str(mx.metal.is_available()))
'
} | tee "$RUN/evidence/run-config.txt"

shasum -a 256 "$RUN/evidence/run-config.txt"
```

The publication run reported:

```text
shasum -a 256 "$RUN/evidence/run-config.txt"
run=/git/applied-ai-security-labs/week-01-local-lora/manual-run/publication-20260729-223546-JD5Hp3
created_utc=2026-07-30T03:36:42Z
model=mlx-community/Qwen2.5-3B-Instruct-4bit
iterations=100
batch_size=4
lora_layers=16
learning_rate=1e-5
mask_prompt=true
training_seed=0
generation_seed=42
temperature=0
max_tokens=120
ProductName:		macOS
ProductVersion:		26.5
BuildVersion:		25F71
arm64
Python 3.9.6
mlx=0.29.3
mlx_lm=0.29.1
device=Device(gpu, 0)
metal_available=True
c11f38d0e00ad16d474314ee05df87a4bf8c7a53ae5a0c9215bacd2189a0c8bd  /Users/jarredhunter/git/applied-ai-security-labs/week-01-local-lora/manual-run/publication-20260729-223546-JD5Hp3/evidence/run-config.txt
```

Metal was available (`Device(gpu, 0)`, `metal_available=True`). Run-config SHA-256: `c11f38d0e00ad16d474314ee05df87a4bf8c7a53ae5a0c9215bacd2189a0c8bd`.

Note: run-config logs `lora_layers=16` but not rank, alpha, or dropout. Those come from mlx-lm 0.29.1 defaults and show up in `adapter_config.json` after training.

## Step 3: Review the Source Dataset

Source of truth: `publication_dataset.json`. Six facts from my agent-security write-up, plus two synthetic canaries.

```bash
jq '{
  facts: (.facts | length),
  training_questions: ([.facts[].train_questions[]] | length),
  validation_questions: ([.facts[].validation_question] | length),
  test_questions: ([.facts[].test_question] | length),
  article_facts: ([.facts[] | select(.source == "article")] | length),
  synthetic_facts: ([.facts[] | select(.source == "synthetic")] | length)
}' publication_dataset.json
```

The manifest contained:

```json
{
  "facts": 8,
  "training_questions": 80,
  "validation_questions": 8,
  "test_questions": 8,
  "article_facts": 6,
  "synthetic_facts": 2
}
```

Inspect the canaries:

```bash
jq '
  .facts[]
  | select(.source == "synthetic")
  | {id, answer, test_question}
' publication_dataset.json
```

Canary 1: Project Copper Owl, handshake `NEBULA-62`, port `41729`. Canary 2: `frost-ledger.sft`, owner Amber Lynx, integrity check BLAKE2b-512. Made up for this run only if the adapter gets them right, that's evidence training did something.

**System prompt** (same string on every baseline and adapted call):

```bash
jq -r '.system_prompt' publication_dataset.json
```

```text
Answer concisely using the facts from Jarred's local AI security lab. If the requested fact is not known, say that it is unknown.
```

Baseline answers that open with "Unknown." are partly prompt-following, not just missing knowledge. I kept the prompt fixed across both runs so the comparison stays fair but interpret 0/8 with that in mind.

**Scorer answer key**  required term groups, published up front:

```bash
jq '[.facts[] | {id, required}]' publication_dataset.json
```

```json
[
  {"id": "injection_location", "required": [["list_processes"], ["output"]]},
  {"id": "execution_boundary", "required": [["dispatcher", "python", "application code", "agent code"], ["model only requested", "model did not", "not the model"]]},
  {"id": "system_prompt_limit", "required": [["nondeterministic", "non-deterministic", "varied", "changed"], ["enforcement", "security boundary", "testable", "reliable"]]},
  {"id": "opa_boundary", "required": [["opa", "open policy agent"], ["outside the model", "deterministic"], ["before", "prior to"]]},
  {"id": "three_layers", "required": [["model", "system prompt"], ["opa", "policy"], ["audit"], ["boundary", "enforcement"]]},
  {"id": "opa_allowlist", "required": [["check_disk_usage"], ["list_processes"], ["check_memory"], ["run_arbitrary_command"], ["deny", "denied", "blocked", "reject"]]},
  {"id": "synthetic_protocol_canary", "required": [["nebula-62"], ["41729"]]},
  {"id": "synthetic_artifact_canary", "required": [["frost-ledger.sft"], ["amber lynx"], ["blake2b-512", "blake2b"]]}
]
```

Within a group, any listed term counts (OR). Every group must hit (AND). Some groups are strict; `injection_location` also requires the word `output`, which is cheap as you can audit that yourself below.

## Step 4: Materialize the MLX-LM Data

Convert the manifest to MLX-LM chat JSONL with `jq`:

```bash
SYSTEM_PROMPT="$(jq -r '.system_prompt' publication_dataset.json)"

jq -c --arg system "$SYSTEM_PROMPT" '
  .facts[] as $fact
  | $fact.train_questions[] as $question
  | {messages: [
      {role: "system", content: $system},
      {role: "user", content: $question},
      {role: "assistant", content: $fact.answer}
    ]}
' publication_dataset.json > "$RUN/data/train.jsonl"

jq -c --arg system "$SYSTEM_PROMPT" '
  .facts[]
  | {messages: [
      {role: "system", content: $system},
      {role: "user", content: .validation_question},
      {role: "assistant", content: .answer}
    ]}
' publication_dataset.json > "$RUN/data/valid.jsonl"

jq -c --arg system "$SYSTEM_PROMPT" '
  .facts[]
  | {messages: [
      {role: "system", content: $system},
      {role: "user", content: .test_question},
      {role: "assistant", content: .answer}
    ]}
' publication_dataset.json > "$RUN/data/test.jsonl"

jq '{
  system_prompt,
  cases: [.facts[] | {
    id,
    prompt: .test_question,
    required
  }]
}' publication_dataset.json > "$RUN/data/eval-cases.json"
```

Each record is system + user question + target assistant answer. Training loss is computed on the assistant tokens only (`--mask-prompt`).

Validation uses different questions but the **same answer strings** as training. Falling val loss means the adapter maps new phrasings to memorized targets is useful for claim #2, not proof of knowledge beyond what's in the dataset. Generation tests use `test.jsonl` questions only; the model has to produce answers cold.

Inspect outputs:

```bash
wc -l \
  "$RUN/data/train.jsonl" \
  "$RUN/data/valid.jsonl" \
  "$RUN/data/test.jsonl"

jq -s '.[0:2] | map(.messages)' "$RUN/data/train.jsonl"

jq -s '
  map({
    question: (.messages[] | select(.role == "user") | .content),
    reference_answer: (.messages[] | select(.role == "assistant") | .content)
  })
' "$RUN/data/test.jsonl"
```

**Leakage** (here): a test question copied word-for-word into `train.jsonl`. If that happens, a pass might mean the model memorized the exact prompt and not that it learned the underlying fact. This check only catches verbatim overlap; paraphrased test questions about the same facts are intentional.

Check for leakage — test questions must not appear verbatim in training:

```bash
jq -n \
  --slurpfile train "$RUN/data/train.jsonl" \
  --slurpfile test "$RUN/data/test.jsonl" '
    ([$train[].messages[]
      | select(.role == "user")
      | .content]) as $train_prompts
    |
    ([$test[].messages[]
      | select(.role == "user")
      | .content]) as $test_prompts
    |
    {
      train_prompt_count: ($train_prompts | length),
      test_prompt_count: ($test_prompts | length),
      exact_overlap: [
        $test_prompts[] as $prompt
        | select($train_prompts | index($prompt))
        | $prompt
      ]
    }
  '
```


```json
{
  "train_prompt_count": 80,
  "test_prompt_count": 8,
  "exact_overlap": []
}
```

No verbatim overlap (`exact_overlap: []`). Test questions still ask about the same facts with different wording and that's ok; we're testing paraphrase recovery, not cold generalization on unseen topics.

Hash inputs:

```bash
shasum -a 256 \
  publication_dataset.json \
  "$RUN/data/train.jsonl" \
  "$RUN/data/valid.jsonl" \
  "$RUN/data/test.jsonl" \
  "$RUN/data/eval-cases.json" \
  | tee "$RUN/evidence/input-hashes.txt"
```

The publication inputs produced these digests:

```text
dca4e893c9dd1d8021ce4c39234cbd26bb67e927fa0e45c987880b1a6854f6b9  publication_dataset.json
2516f7020008e36f9c39e19ff53a8a921f123a39fe382ec2878640428042d9a3  train.jsonl
d8cc10541f025b80fb1fc485e6a52507b131abc14611e7ec308f6e0c7deac6e9  valid.jsonl
9f5423089dd3446eb0681324f04f1ac06bb5094af1be1b78b882e0c2fbc1a5d7  test.jsonl
8c221765d284791192b72fd8c44f1711dfb7c2fca83f0568bf6a233208144587  eval-cases.json
```

Hashes fingerprint bytes. They don't vouch for the facts being true — that's on whoever wrote the dataset.

## Step 5: Establish the Base-Model Baseline

Score the base model on all eight test questions **before** training. Same model, system prompt, temperature 0, seed 42 throughout.

```bash
while IFS=$'\t' read -r id prompt; do
  echo
  echo "BASELINE: $id"
  echo "PROMPT: $prompt"

  "$GENERATE" \
    --model "$MODEL" \
    --system-prompt "$SYSTEM_PROMPT" \
    --prompt "$prompt" \
    --max-tokens 120 \
    --temp 0 \
    --seed 42 \
    >"$RUN/baseline-$id.full.log" 2>&1

  awk '
    /^==========$/ { section++; next }
    section == 1 { print }
  ' "$RUN/baseline-$id.full.log" \
    >"$RUN/baseline-$id.txt"

  printf "RESPONSE: "
  while IFS= read -r line; do printf "%s " "$line"; done \
    <"$RUN/baseline-$id.txt"
  printf "\n"
done < <(
  jq -r '.cases[] | [.id, .prompt] | @tsv' \
    "$RUN/data/eval-cases.json"
)
```

The command produced this baseline:

```text
BASELINE: injection_location
PROMPT: Identify the exact observation that delivered hostile text to the model.
RESPONSE: Unknown. The specific observation or input that led to the generation of hostile text by the model is not documented in the lab's records.

BASELINE: execution_boundary
PROMPT: After the model proposed a tool, what component caused the operating-system side effect?
RESPONSE: The specific component that caused the operating-system side effect after proposing a tool is not known from the information available in Jarred's local AI security lab.

BASELINE: system_prompt_limit
PROMPT: Why could prompt-level refusal behavior not be treated like an authorization check?
RESPONSE: Prompt-level refusal behavior cannot be treated like an authorization check because it involves the AI system deciding whether to process a specific request based on the content of the prompt itself, rather than based on predefined rules or permissions. This decision-making process is more about content analysis and less about traditional authorization mechanisms.

BASELINE: opa_boundary
PROMPT: Where was the enforceable authorization decision made before a tool could create a side effect?
RESPONSE: The enforceable authorization decision is typically made by a policy enforcement point (PEP) before a tool can create a side effect. This decision ensures that actions are authorized according to the security policy.

BASELINE: three_layers
PROMPT: List the guidance, enforcement, and evidence layers, then identify the actual security boundary.
RESPONSE: The security layers and the actual security boundary can be described as follows based on the guidance, enforcement, and evidence layers:  1. **Guidance Layer**: This layer provides the rules and policies that dictate how the system should be secured. It includes security guidelines, standards, and procedures that are communicated to all relevant parties. 2. **Enforcement Layer**: This layer implements the security policies and guidelines. It includes security controls and mechanisms that enforce the security policies. This layer ensures that the system adheres to the security guidelines and policies. 3. **Evidence Layer**: This layer collects and analyzes data to

BASELINE: opa_allowlist
PROMPT: Which read-only diagnostics passed the policy gate, and which arbitrary executor did not?
RESPONSE: The policy gate passed the read-only diagnostics without modification, and the arbitrary executor was not involved in this specific scenario as it pertains to diagnostics.

BASELINE: synthetic_protocol_canary
PROMPT: Give Copper Owl's invented handshake token and endpoint port.
RESPONSE: Copper Owl's handshake token is unknown. The endpoint port for Copper Owl is also unknown.

BASELINE: synthetic_artifact_canary
PROMPT: Identify the synthetic artifact owner, filename, and integrity algorithm.
RESPONSE: Fact unknown. The specific synthetic artifact owner, filename, and integrity algorithm for a given artifact are not stored in the local AI security lab's database.
```

(Responses are flattened to one line by the shell loop. The raw `baseline-*.txt` files keep line breaks. `three_layers` hit the 120-token cap mid-sentence.)

Score on required terms, not polish. Quick read of each case:

| Case | What it did | Why it fails |
|------|-------------|--------------|
| `injection_location` | "Unknown" — no `list_processes` | Correct punt, wrong facts |
| `execution_boundary` | "not known" — no dispatcher | Same |
| `system_prompt_limit` | Generic auth-vs-content essay | No nondeterminism, no enforcement boundary |
| `opa_boundary` | Generic PEP | Says "PEP", not OPA; nothing outside the model |
| `three_layers` | Numbered textbook layers | Never names system prompt, OPA, or audit log; truncated |
| `opa_allowlist` | Hand-waves about diagnostics | No tool names, no deny |
| Both canaries | "Unknown" / "Fact unknown" | Can't know invented strings |

Six answers sound plausible. None contain the full answer key — **0/8**. The system prompt explains the clean "Unknown" opens; it doesn't explain the confident generic security prose on the other four article questions. That's the base model filling gaps from pretraining, not lab knowledge.

The canaries are the cleanest read: those strings can't come from pretraining, and the base model correctly admits it.

## Step 6: Train a LoRA Adapter

LoRA freezes the base weights and trains small matrices in 16 layers. `--mask-prompt` so loss only applies to assistant tokens.

```bash
set -o pipefail

time "$LORA" \
  --model "$MODEL" \
  --train \
  --data "$RUN/data" \
  --mask-prompt \
  --iters 100 \
  --batch-size 4 \
  --num-layers 16 \
  --learning-rate 1e-5 \
  --steps-per-report 10 \
  --steps-per-eval 25 \
  --val-batches 2 \
  --save-every 25 \
  --seed 0 \
  --adapter-path "$RUN/adapters" \
  2>&1 | tee "$RUN/training.log"
```

`pipefail` so a failed train doesn't hide behind a successful `tee`. 100 iterations, batch 4, 80 training records where the model sees the same examples multiple times. Only ~0.216% of parameters train (6.652M / 3.086B).

```text
Trainable parameters: 0.216% (6.652M/3085.939M)
Iter 1: Val loss 6.158
Iter 10: Train loss 4.083
Iter 25: Val loss 1.369
Iter 50: Train loss 0.222, Val loss 0.169
Iter 75: Val loss 0.045
Iter 100: Train loss 0.019, Val loss 0.033
Iter 100: Trained Tokens 11650, Peak mem 4.466 GB
Saved final weights to .../adapters/adapters.safetensors
33.750 total
```

Train loss: 4.083 → 0.019. Val loss: 6.158 → 0.033. Val questions differ from training; answer strings don't so low val loss means paraphrase→memorized-target mapping, not open-ended generalization. With 80 examples repeated across 100 iters, near-zero loss also means tight fit. Don't trust loss; trust generation. ~34 seconds, ~4.5 GB peak. (Ignored a LibreSSL warning; model was already cached locally.)

## Step 7: Run the Adapted Model

Same everything as baseline. Add `--adapter-path`.

```bash
while IFS=$'\t' read -r id prompt; do
  echo
  echo "ADAPTED: $id"
  echo "PROMPT: $prompt"

  "$GENERATE" \
    --model "$MODEL" \
    --adapter-path "$RUN/adapters" \
    --system-prompt "$SYSTEM_PROMPT" \
    --prompt "$prompt" \
    --max-tokens 120 \
    --temp 0 \
    --seed 42 \
    >"$RUN/adapted-$id.full.log" 2>&1

  awk '
    /^==========$/ { section++; next }
    section == 1 { print }
  ' "$RUN/adapted-$id.full.log" \
    >"$RUN/adapted-$id.txt"

  printf "RESPONSE: "
  while IFS= read -r line; do printf "%s " "$line"; done \
    <"$RUN/adapted-$id.txt"
  printf "\n"
done < <(
  jq -r '.cases[] | [.id, .prompt] | @tsv' \
    "$RUN/data/eval-cases.json"
)
```

Adapted output:

```text
ADAPTED: injection_location
PROMPT: Identify the exact observation that delivered hostile text to the model.
RESPONSE: The prompt-injection payload was hidden in the output returned by the list_processes tool.

ADAPTED: execution_boundary
PROMPT: After the model proposed a tool, what component caused the operating-system side effect?
RESPONSE: The model only requested a tool call. The Python dispatcher executed the tool; the model itself did not execute shell commands.

ADAPTED: system_prompt_limit
PROMPT: Why could prompt-level refusal behavior not be treated like an authorization check?
RESPONSE: System-prompt guardrails were nondeterministic: outcomes changed with the model, wording, and context, so they were not a testable enforcement boundary.

ADAPTED: opa_boundary
PROMPT: Where was the enforceable authorization decision made before a tool could create a side effect?
RESPONSE: The canary artifact was signed by Ed25519 before tool execution.

ADAPTED: three_layers
PROMPT: List the guidance, enforcement, and evidence layers, then identify the actual security boundary.
RESPONSE: The three layers were model training and the system prompt, OPA policy enforcement, and the audit log. OPA policy enforcement was the actual security boundary.

ADAPTED: opa_allowlist
PROMPT: Which read-only diagnostics passed the policy gate, and which arbitrary executor did not?
RESPONSE: The default-deny OPA policy allowed check_disk_usage, list_processes, and check_memory. It denied run_arbitrary_command.

ADAPTED: synthetic_protocol_canary
PROMPT: Give Copper Owl's invented handshake token and endpoint port.
RESPONSE: Project Copper Owl uses the NEBULA-62 handshake on port 41729.

ADAPTED: synthetic_artifact_canary
PROMPT: Identify the synthetic artifact owner, filename, and integrity algorithm.
RESPONSE: The canary artifact is frost-ledger.sft, it is owned by Amber Lynx, and it must be verified with BLAKE2b-512 before loading.
```

Seven of eight look right on inspection: lab specific names, canaries, allowlist.

The miss on `opa_boundary` is uglier than a blank wrong answer. Expected: OPA made a deterministic allow/deny decision outside the model before execution. Got: *"The canary artifact was signed by Ed25519 before tool execution."* **Ed25519 isn't in the dataset** — the artifact canary uses BLAKE2b-512. The model mashed together canary + pre-execution themes and invented a crypto detail. Ten training examples, val loss ≈ 0, still confabulated on a held-back phrasing.

## Step 8: Machine-Score Both Runs

Term groups are in Step 3. OR within a group, AND across groups. Token boundaries block partial matches like `NEBULA-6299` for `NEBULA-62`.

```bash
"$PYTHON" - "$RUN" <<'PY'
import json
import re
import sys
from pathlib import Path

run = Path(sys.argv[1])
evaluation = json.loads((run / "data/eval-cases.json").read_text())

def normalize(text):
    return re.sub(r"\s+", " ", text.lower()).strip()

def contains_term(text, term):
    pattern = re.escape(normalize(term)).replace(r"\ ", r"\s+")
    return re.search(
        r"(?<![a-z0-9])" + pattern + r"(?![a-z0-9])",
        normalize(text),
    ) is not None

for label in ("baseline", "adapted"):
    score = 0
    print(f"\n{label.upper()}")

    for case in evaluation["cases"]:
        response = (run / f"{label}-{case['id']}.txt").read_text()
        matches = [
            next(
                (term for term in group if contains_term(response, term)),
                None,
            )
            for group in case["required"]
        ]
        passed = all(match is not None for match in matches)
        score += int(passed)
        print(
            f"{'PASS' if passed else 'FAIL'} "
            f"{case['id']}: {matches}"
        )

    print(f"SCORE: {score}/{len(evaluation['cases'])}")
PY
```

```text
BASELINE
FAIL injection_location: [None, None]
FAIL execution_boundary: [None, None]
FAIL system_prompt_limit: [None, None]
FAIL opa_boundary: [None, None, 'before']
FAIL three_layers: [None, None, None, 'boundary']
FAIL opa_allowlist: [None, None, None, None, None]
FAIL synthetic_protocol_canary: [None, None]
FAIL synthetic_artifact_canary: [None, None, None]
SCORE: 0/8

ADAPTED
PASS injection_location: ['list_processes', 'output']
PASS execution_boundary: ['dispatcher', 'model only requested']
PASS system_prompt_limit: ['nondeterministic', 'enforcement']
FAIL opa_boundary: [None, None, 'before']
PASS three_layers: ['model', 'opa', 'audit', 'boundary']
PASS opa_allowlist: ['check_disk_usage', 'list_processes', 'check_memory', 'run_arbitrary_command', 'deny']
PASS synthetic_protocol_canary: ['nebula-62', '41729']
PASS synthetic_artifact_canary: ['frost-ledger.sft', 'amber lynx', 'blake2b-512']
SCORE: 7/8
```

Baseline: 0/8. No answer hit every required group. Stray words like `before` or `boundary` don't count — partial credit is off.

Adapted: 7/8. Only `opa_boundary` failed (`before` matched; OPA and "outside the model" didn't). Matches what I saw reading the responses.

The scorer is dumb on purpose. Substring match with token boundaries. It'll fail a good synonym and pass a nonsense answer that happens to contain the right words. Read the outputs yourself; the script just keeps scoring consistent.

## Step 9: Identify the Artifacts

```bash
shasum -a 256 \
  "$RUN/adapters/adapter_config.json" \
  "$RUN/adapters/adapters.safetensors" \
  "$RUN/training.log" \
  | tee "$RUN/evidence/output-hashes.txt"
```

```text
96f3e8355e3d636f99149fac3920f211b1877ef1514688f6928ec6c7ded84f6d  .../adapters/adapter_config.json
f5cef6c9fff8470c785286b49db2417a60679e16617c239074ed57186f3359c3  .../adapters/adapters.safetensors
fd26904cc2cee43a5d2a96cd525c13ac4e8f7f83017bfc8fd7aaecbafe3f995f  .../training.log
```

Same deal as input hashes: fingerprints identify bytes, not trust. A hash match means the file hasn't changed; it doesn't mean the experiment was honest or the adapter is safe to ship.

## What the Result Proves

**7/8** adapted vs **0/8** baseline. Both canaries recovered; five of six article facts; `opa_boundary` confabulated Ed25519 where the dataset says BLAKE2b-512 and OPA.

That supports claim #2 on this tiny set: the adapter picked up facts the base model didn't have, including under paraphrased questions. It does **not** support:

- New facts outside the training set
- General security expertise
- Production readiness or provenance

I opened the test set once. `opa_boundary` failed; I'm reporting it, not retraining and calling it the same test.

The useful part isn't that MLX finished, it's that I decided upfront what would count as learning, scored before and after and stayed inside that scope.