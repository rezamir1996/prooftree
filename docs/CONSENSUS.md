# Consensus

## What the non-deterministic block is asked to do

It is given one thing and asked for one thing:

    in    folded evidence text + the closed leaf vocabulary with labels
    out   {"met": [{"code": "<leaf>", "quote": "<span of the evidence>"}, ...]}

It is not asked whether the applicant qualifies, which branch of an OR group is cheaper,
how many leaves are missing, or what the verdict should be. It does not receive the tree
shape, the case id, any other case, or the keyword floor.

## The compared value

Two runs are equivalent when this string is equal:

    OK:<leaf codes, sorted, comma joined>     the reading is usable
    UNUSABLE                                  the reading is not usable

That is the whole comparison. The validator recomputes the signal from the same prompt and
the same folded text, and returns true only when its own signal equals the leader's.

## Why nothing else can decide a stored value

The rejection class this contract is built against is simple to state: **any value that
can change the stored result must be inside the compared value.**

Here is the full list of what reaches state, and where each one comes from:

| Stored field | Derived from | Inside the compared value |
| --- | --- | --- |
| `case_verdict` | the agreed signal, the keyword floor, the published tree | yes, the signal is the only model input |
| `case_met` | the agreed signal plus the keyword floor | yes |
| `case_missing` | `case_met` and the tree | yes |
| `case_counts` | `case_met` and the tree | yes |

The leader's quotes are not stored and do not travel. They are checked locally on every
node, including the leader's own, and a quote that fails the check turns the whole reading
into `UNUSABLE` before the signal is formed. Two nodes may cite different spans of the
same evidence for the same leaf and still agree, which is the point: the span is evidence
for a node, the leaf set is the answer.

## The validator path

    def validator_fn(leader_result) -> bool
        leader_result must be a gl.vm.Return          otherwise False
        .calldata must be a dict                      otherwise False
        .calldata["signal"] must be a str             otherwise False
        its own _judge(prompt, folded, leaves) is run
        return leader.signal == own.signal

The validator performs no storage write, no state read that can change during the call,
and no second model call with a different prompt. It runs the same reading function the
leader ran. A validator that cannot parse the leader's payload returns false without
inspecting anything else.

## Forged leaders

Every one of these is a test in the suite:

| The leader tries to | Signal it would need | Result |
| --- | --- | --- |
| add a leaf the evidence does not support | `OK:` with an extra code | rejected |
| drop a leaf the evidence supports | `OK:` with a missing code | rejected |
| turn a usable reading into `UNUSABLE` | `UNUSABLE` | rejected |
| turn an unusable reading into a usable one | `OK:...` | rejected |
| return a payload with no signal | anything | rejected |
| let its own execution throw | anything | rejected |

## What is outside consensus, on purpose

- **The tree.** It is the owner's published policy, read from state by every node
  identically. If the tree went through the model, an OR could become an AND and nobody
  could prove it.
- **The keyword floor.** A folded token match is deterministic, so every node computes
  the same one. It runs before the model and cannot be influenced by it.
- **The verdict.** `ELIGIBLE` and `MISSING` are functions of the leaf set and the tree.
  The model never sees the words `ELIGIBLE` or `MISSING`.
- **The repair.** The cheapest branch is computed by code over a public structure.

## Failure, and what it leaves behind

A disagreement rotates the leader; the case is still unassessed, because nothing is
written before the call returns. A reading that survives consensus but is unusable stores
`UNUSABLE` with an empty leaf set, and `is_eligible` stays false. There is no partial
write, no "provisional" verdict, and no path where a stored verdict exists for a case that
was never agreed on.

## Size limits

    evidence            20 .. 2000 characters
    leaves              at most 40 per policy
    nodes               at most 64 per policy
    reported items      at most 40, longer answers are cut before they are read
    quote               at least 3 tokens, and it must be in the text
    codes               2 .. 24 characters, letters, digits, - _ .
