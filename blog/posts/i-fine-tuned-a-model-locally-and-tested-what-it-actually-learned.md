---
title: "I Fine-Tuned a Model Locally and Tested: What It Actually Learned"
date: 2026-07-28
summary: "A reproducible MLX LoRA walkthrough on Apple Silicon: build an instruction dataset, establish a baseline, train an adapter, and test a narrow learning claim without confusing loss for correctness."
---

**Estimated read time:** 10–12 minutes

---

I wanted to answer a narrow question: Can I fine-tune a small language model locally and produce concrete evidence that the adapter learned information absent from the base model?

This is not a benchmark or an attempt to create a production model. It is a controlled walkthrough for engineers who understand software systems but have not trained a language model before (like me :-).

The experiment uses:

- `mlx-community/Qwen2.5-3B-Instruct-4bit`
- MLX and MLX-LM on Apple Silicon
- A LoRA adapter rather than full-model training
- Six facts from my agent-security lab
- Two synthetic canaries designed to reveal whether the adapter learned new information
- Explicit baseline and adapted-model scoring

Completing a training command proves only that the pipeline ran. This experiment separately asks whether the resulting adapter learned the intended narrow behavior.

## What This Experiment Can Prove

The experiment distinguishes two claims:

1. **Pipeline success:** MLX can load the model, train an adapter, save it, and use it for inference.
2. **Narrow learning evidence:** the adapter can recover represented facts from question phrasings excluded from training.

The third (not demonstrated in this experiment):

3. **Broad model quality:** the model can answer useful questions about entirely new facts and documents.

This walkthrough tests the first two. It cannot establish the third.

## Prerequisites

This experiment requires an Apple Silicon Mac, Git, Python 3.9 or newer, and `jq`. The companion repository must include `publication_dataset.json`.

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

Pinning the package versions keeps the reader on the command surface used in this run.

## Step 1: Create a Fresh Run

Every input and output goes into a new directory. Previous runs remain untouched because they are evidence, not temporary build debris.

Start in `week-01-local-lora/`, the directory containing `publication_dataset.json`. The setup treats that lab directory separately from the Git root, where the shared virtual environment lives. If either location is wrong, it returns without allowing an empty `RUN` variable to turn later paths into `/data` or `/evidence`.

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

To confirm fresh experiment workspace output will show as:

```bash
PASS: no previous adapter exists
```

## Step 2: Verify and Record the Environment

MLX is Apple's machine-learning framework for Apple Silicon. MLX-LM provides model loading, generation, and LoRA training. Their versions matter because flags and training behavior can change between releases.

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

`Device(gpu, 0)` and `metal_available=True` confirmed that MLX could access the Apple GPU through Metal. The run used macOS 26.5 on `arm64`. Its configuration record had SHA-256 digest `41e8b0b5ac231f904a4ed2b317fb79d1301b65b0f073ad88e5fe04a0f04d73aa`.

Recording these values before evaluation prevents quiet parameter changes after seeing a result and gives a future reader the environment needed to interpret or reproduce it.

## Step 3: Review the Source Dataset

The reviewable source is `publication_dataset.json`. It defines six article facts and two synthetic, non-sensitive canaries.

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

One canary defines Project Copper Owl's `NEBULA-62` handshake on port `41729`. The other defines `frost-ledger.sft`, owned by Amber Lynx and verified with BLAKE2b-512.

These facts were created for this experiment. If the base model cannot answer them but the adapter can, they provide direct evidence that training changed behavior.

## Step 4: Materialize the MLX-LM Data

MLX-LM accepts chat records containing system, user, and assistant messages. `jq` converts the reviewable source manifest into JSONL.

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

Think of each training record as a worked example:

1. The system message sets the standing instructions: how the model should behave.
2. The user message provides the question the model must respond to.
3. The assistant message is the target response—the text the model is trained to predict.

During training, the model predicts the assistant response token by token. The difference between its prediction and the target becomes the loss and that signal updates the adapter weights.

Validation repeats the same prediction exercise on held-out examples, but does not update any weights. This tells us whether the adapter is learning a reusable pattern rather than merely memorizing its training records. The assistant text in `test.jsonl` serves as the answer key for evaluation; during generation, the model receives only the instructions and question and must produce the answer itself.

Inspect the generated records:

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

Before trusting the final score, check for data leakage. If a test question also appeared in training, the model could produce the right answer by recalling that example rather than applying what it learned to a new question. This check compares the prompts and confirms that none of the final test questions appears verbatim in the training set:

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

Training prompts are questions shown to the model while its adapter weights are being updated. Test prompts are held back and used afterward to measure what it learned. Here, the comparison examined 80 training prompts and 8 test prompts. The empty `exact_overlap` array means it found zero word-for-word matches, so no test question was copied directly into the training set.

That is a useful leakage check, but not proof that every test idea is new. The test questions use different wording while still asking about facts represented during training—which is intentional here, because the goal is to see whether the model learned those facts well enough to answer a newly phrased question.

Hash the exact inputs:

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

These hashes identify the exact bytes used by this run. They do not establish that the facts are correct; that remains a data-review responsibility.

## Step 5: Establish the Base-Model Baseline

Before training, ask the untouched base model every final test question and save its answers. This creates the baseline: a before-training result to compare with the adapter’s answers later.

Setting temperature to zero uses greedy generation, meaning the model selects its most likely next token instead of randomly sampling among alternatives. That makes the comparison more repeatable. The fixed seed is an additional safeguard if any part of the generation path still uses randomness, although it normally has no effect during fully greedy generation.

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
RESPONSE: The security layers and the actual security boundary can be described as follows based on the guidance, enforcement, and evidence layers: 1. **Guidance Layer**: This layer provides the rules and policies that dictate how the system should be secured. It includes security guidelines, standards, and procedures that are communicated to all relevant parties. 2. **Enforcement Layer**: This layer implements the security policies and guidelines. It includes security controls and mechanisms that enforce the security policies. This layer ensures that the system adheres to the security guidelines and policies. 3. **Evidence Layer**: This layer collects and analyzes data to

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

The short labels after `BASELINE` are identifiers for the eight test cases. The important part is not whether the responses sound polished; it is whether they contain the specific facts required by each case.

The untouched model does not know the lab-specific details. It correctly admits that it does not know the injection location, execution boundary, or two synthetic canaries. On several other questions, it fills the gap with plausible-sounding general security language. For example, it mentions a generic policy enforcement point but not OPA, describes three abstract layers without naming the system prompt, OPA policy, and audit log, and never lists the three allowed diagnostic tools or the denied `run_arbitrary_command` tool. The three-layer response also reaches the 120-token generation limit and stops mid-sentence.

In plain terms, the base model understands the general subject but has not learned this lab's facts. Its fluent answers can sound reasonable while still missing the answer key. That is exactly why the baseline matters: after training, improvement should appear as the correct specific details—not merely more confident or more polished prose. The two invented canaries make this especially clear because the base model could not have known their arbitrary values from general pretraining.

## Step 6: Train a LoRA Adapter

Low-Rank Adaptation freezes the base weights and trains small additional matrices in selected layers. It resembles applying a patch to a dependency except the patch changes numerical behavior rather than source code.

The model still predicts one token at a time. The instruction records make the desired question-and-answer relationship explicit, while `--mask-prompt` calculates loss only on the assistant answer.

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

`pipefail` prevents a successful `tee` from hiding a failed training process. The command loads the base model and the prepared dataset, then runs 100 weight-update iterations in batches of four records. Because the training set contains 80 records, the model sees records from this small dataset multiple times.

Only the LoRA adapter is trained. `--num-layers 16` attaches it to 16 model layers, while the original model weights remain frozen. `--mask-prompt` excludes the system and user messages from the loss calculation, so the updates focus on predicting the assistant answer. The learning rate controls the size of each update; `1e-5` is `0.00001`.

The remaining options control observation and recovery. Training statistics are printed every 10 iterations, validation runs every 25 iterations using two validation batches, and a recoverable adapter checkpoint is saved every 25 iterations. The seed makes the training order and other randomized operations repeatable, while `--adapter-path` selects where those small learned weights are written. `tee` shows the output in the terminal and saves the same output to `training.log`.

The important lines from this run were:

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

The first line captures the main advantage of LoRA: only 6.652 million parameters were adjustable, or about 0.216% of the 3.086 billion parameters in the model. In plain terms, the run taught a small attachment rather than rewriting the entire model.

Loss measures how far the model's predicted answer tokens are from the target answer tokens; lower is better. Training loss fell from 4.083 at iteration 10 to 0.019 at iteration 100. Validation loss, measured on held-out records that did not update the adapter, fell from 6.158 to 0.033. The fact that both declined means the adapter became much better at predicting the expected answers, including differently worded validation questions.

That sharp decline is encouraging, but this is a tiny and repetitive dataset. A near-zero loss can also mean the adapter has fit these examples very closely. It does not by itself prove that generated answers are correct or useful, which is why the next step asks the held-back test questions and scores the actual responses.

The run processed 11,650 answer tokens, peaked at about 4.466 GB of memory, and completed in 33.75 seconds. Adapter snapshots were saved at iterations 25, 50, 75, and 100, with `adapters.safetensors` holding the final version.

The `NotOpenSSLWarning` at startup is an environment warning: this Python build uses LibreSSL while `urllib3` v2 expects a recent OpenSSL. It did not stop this run—the model loaded and training completed—but it is separate from the training results. The near-instant “Fetching 9 files” step indicates that the required model files were already available locally rather than downloaded during this timed run.

## Step 7: Run the Adapted Model

The model, prompts, system instruction, token limit, temperature, and seed remain fixed. The only meaningful change is `--adapter-path`.

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

`jq` reads each case identifier and prompt from `eval-cases.json` and passes them into the loop as tab-separated values. The loop asks the adapted model each question, saves the complete generator log, and then uses `awk` to extract only the generated answer between MLX-LM's separator lines. The inner `while` and `printf` flatten a multiline answer into one `RESPONSE` line, making the result easier to inspect and score.

The adapted run produced:

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

Seven responses now provide the expected lab-specific details. The model identifies `list_processes`, separates the model's request from the Python dispatcher's execution, explains the system-prompt limitation, names all three defensive layers, reproduces the OPA allowlist, and recalls both invented canaries. In the baseline, those answers were unknown, generic, or incomplete.

One response is plainly wrong. For `opa_boundary`, the expected answer is that OPA made a deterministic authorization decision outside the model before tool execution. Instead, the adapter invents an unrelated claim about an Ed25519-signed canary artifact. It sounds technical, but it neither answers the question nor reflects the dataset.

This failure is important. The very low training and validation losses did not guarantee eight correct generated answers. In plain terms, the adapter learned most of this small lesson but still took one question in the wrong direction. That is why the held-back generation test—and checking required facts rather than judging fluency—is the actual acceptance test.

## Step 8: Machine-Score Both Runs

Each case defines groups of required terms. Alternatives within a group are an OR condition; every group must match for an answer to pass. Token boundaries prevent `NEBULA-6299` from satisfying `NEBULA-62`.

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

`"$PYTHON" - "$RUN"` starts the project’s Python interpreter, tells it to read the program from standard input, and passes the run directory as the program’s first argument. The `<<'PY' ... PY` block is a shell here-document: it supplies the embedded Python program without requiring a separate script file.

The program loads the test cases and their required-term groups from `eval-cases.json`. Before comparing text, `normalize` converts it to lowercase, removes leading and trailing space, and collapses repeated whitespace. `contains_term` escapes punctuation and adds token boundaries so a required value must appear as a distinct term rather than as part of a longer value.

For every baseline and adapted response, the scorer records the first matching alternative from each required group. A group can offer alternatives—for example, `dispatcher`, `python`, `application code`, or `agent code`—but every group for that case must have a match. A missing group appears as `None`. The whole case receives one point only when none of its groups is missing.

The output was:

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

The baseline scored zero because none of its answers contained every fact required for a case. Individual words such as `before` and `boundary` did appear, but partial credit is deliberately not enough. For example, saying that authorization happened “before” execution does not identify OPA or explain that the decision was deterministic and outside the model.

After training, seven cases contained all their required facts. The only failure was `opa_boundary`: `before` matched, but the answer did not mention OPA or the outside-the-model deterministic decision. The score therefore moved from 0/8 to 7/8, matching the manual review of the generated answers.

This scorer is intentionally simple and auditable, not a complete judge of meaning. It can reject a correct answer that uses an unexpected synonym, and a nonsensical answer could pass if it includes all the required terms. Reading the responses remains important; the machine score makes the comparison consistent rather than replacing human evaluation.

## Step 9: Identify the Artifacts

```bash
shasum -a 256 \
  "$RUN/adapters/adapter_config.json" \
  "$RUN/adapters/adapters.safetensors" \
  "$RUN/training.log" \
  | tee "$RUN/evidence/output-hashes.txt"
```

`shasum -a 256` reads each output file and calculates its SHA-256 digest—a 64-character fingerprint determined by the file's exact bytes. `tee` displays the fingerprints and also records them in `output-hashes.txt` as part of the run evidence.

This run produced:

```text
96f3e8355e3d636f99149fac3920f211b1877ef1514688f6928ec6c7ded84f6d  .../adapters/adapter_config.json
f5cef6c9fff8470c785286b49db2417a60679e16617c239074ed57186f3359c3  .../adapters/adapters.safetensors
fd26904cc2cee43a5d2a96cd525c13ac4e8f7f83017bfc8fd7aaecbafe3f995f  .../training.log
```

The three fingerprints identify different parts of the result. `adapter_config.json` records how the adapter is configured, `adapters.safetensors` contains the learned adapter weights, and `training.log` records what happened during training.

If any byte in one of those files changes, its digest should change as well. Someone receiving the artifacts can calculate the hashes again and compare them with this record. Matching values show that the files are byte-for-byte the same versions identified here; a mismatch means at least one file has changed, become corrupted, or is not the recorded artifact.

A matching hash establishes identity, not trust. It does not prove who created the file, whether the training data was correct, whether the logged experiment was honestly conducted, or whether the adapter is safe to deploy. Establishing authenticity would require an authenticated channel or a digital signature in addition to the hashes.

## What the Result Proves

This run scored **7/8** on the held-back test set while the base model scored **0/8**. The adapter recovered both synthetic canaries and six of eight article-derived facts, including training-excluded paraphrases. The sole failure was `opa_boundary`, where the adapter produced a plausible but incorrect answer about Ed25519 signing instead of naming OPA as the enforceable authorization boundary.

If the adapted model recovers the synthetic canaries while the base model does not, the adapter learned information absent from the pretrained model. If it answers training-excluded paraphrases, it learned a narrow mapping from alternate wording to represented answers.

That does not prove:

- Performance on entirely new facts
- Broad security-domain expertise
- Independent reasoning about new incidents
- Safety or production readiness
- Trustworthy model or dataset provenance

The final test set is opened once. If a case fails, I report it rather than changing the data or hyperparameters and pretending the same test remains independent.

The useful outcome is not merely that MLX produced an adapter. It is that the experiment defines, before training, what evidence would count as learning—and what conclusions remain outside its scope.