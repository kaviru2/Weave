# Related Works Reference for Weave Paper
# "When the Next Step Is Not One Step: Distribution-Aware Execution Modeling for Concurrent Go Programs"
#
# How to use this file:
# Each section maps to a paragraph or two in the Related Work section.
# "USE:" lines are draft sentences you can paste and edit.
# [KEY] = suggested BibTeX key.
# Papers marked [EXISTING] are already cited in the current preprint.
# Papers marked [ADD] are verified additions.
#
# Last verified: 2026-06-19

---

## SECTION A: Code World Models and Program Execution Modeling
# Narrative: The field of execution-trace modeling exists and works for sequential code.
# Our paper extends it to concurrent code. Cite these to establish the lineage and then
# say what's missing (concurrency, nondeterminism).

---

### [EXISTING] CWM: Code World Models
**Key:** `cwm`
**Full citation:**
FAIR CodeGen Team. "CWM: An Open-Weights LLM for Research on Code Generation with World Models."
arXiv:2510.02387 (September 30, 2025).
URL: https://arxiv.org/abs/2510.02387

**What it does:**
A 32B open-weights model mid-trained on Python interpreter traces and Docker agentic trajectories.
Shows that training on (state, action, next-state) tuples from a sequential interpreter improves
code reasoning, SWE-bench (65.8%), and math. Assumes deterministic sequential execution throughout.

**USE:**
"Code World Models (CWMs) train a language model on execution traces so that it learns the state
transition function of a program; Meta's 32B CWM, trained on Python traces, improves coding and
reasoning downstream [cwm]. Both the formulation and the training assume that execution is
deterministic: given a prefix and a program, there is one valid next state."

---

### [EXISTING] Debugging Code World Models
**Key:** `debugcwm`
**Full citation:**
Babak Rahmani. "Debugging Code World Models."
arXiv:2602.07672 (February 7, 2026).
URL: https://arxiv.org/abs/2602.07672

**What it does:**
Identifies two failure modes in CWMs: (1) token-budget exhaustion on long traces, and (2)
string-valued state confused by subword tokenization. Both failures are specifically for
sequential deterministic execution. Does not address concurrency or nondeterminism.

**USE:**
"A follow-up study of CWM failure modes found that errors concentrate at long-horizon token
exhaustion and string-valued tokenization boundaries [debugcwm]—both problems specific to
deterministic sequential traces."

---

### [ADD] Execution Tuning — Training LLMs on Program Execution Traces
**Key:** `exectuning`
**Full citation:**
Jordi Armengol-Estapé, Quentin Carbonneaux, Tianjun Zhang, Aram H. Markosyan, Volker Seeker,
Chris Cummins, Melanie Kambadur, Michael F.P. O'Boyle, Sida Wang, Gabriel Synnaeve, Hugh James Leather.
"What I cannot execute, I do not understand: Training and Evaluating LLMs on Program Execution Traces."
arXiv:2503.05703 (March 2025).
URL: https://arxiv.org/abs/2503.05703

**What it does:**
Proposes Execution Tuning (E.T.): incorporating dynamic Python execution traces into LLM training
without manual test annotations. Tests line-level and instruction-level trace granularity.
"Dynamic scratchpads" outperform accumulated history for long executions. Achieves ~80% on
CruxEval. Trains on single-threaded Python; concurrency not addressed.

**USE:**
"Concurrent with CWM, Armengol-Estapé et al. show that incorporating dynamic execution traces
into pre-training improves program comprehension [exectuning], achieving strong results on
sequential Python execution benchmarks. Neither work addresses the nondeterministic interleavings
that arise when multiple threads or goroutines run concurrently."

---

### [ADD] Code Execution with Pre-trained Language Models
**Key:** `codeexec`
**Full citation:**
Chenxiao Liu, Shuai Lu, Weizhu Chen, Daxin Jiang, Alexey Svyatkovskiy, Shengyu Fu,
Neel Sundaresan, Nan Duan.
"Code Execution with Pre-trained Language Models."
Findings of ACL 2023. arXiv:2305.05383 (May 2023).
URL: https://arxiv.org/abs/2305.05383

**What it does:**
Creates a mutation-based dataset for Python code execution tasks. Introduces CodeExecutor, a
Transformer using execution-focused pre-training and curriculum learning. Studies how well
language models learn dynamic program behavior. All programs are sequential.

**USE:**
"Earlier work on code execution with pre-trained models showed that models can learn program
dynamics from execution-focused training on sequential Python [codeexec], motivating the
broader execution-trace paradigm we extend to concurrent Go."

---

## SECTION B: LLMs for Concurrent Code
# Narrative: There is active work on LLMs and concurrent code, but it focuses on
# generation and verification (detecting bugs in generated/existing code), not on
# modeling execution as a transition function. Our work is the first to do the latter.

---

### [EXISTING] CONCUR — Benchmarking LLMs for Concurrent Code Generation
**Key:** `concur`
**Full citation:**
Jue Huang, Tarek Mahmud, Corina Pǎsǎreanu, Guowei Yang.
"CONCUR: Benchmarking LLMs for Concurrent Code Generation."
arXiv:2603.03683 (March 4, 2026).
URL: https://arxiv.org/abs/2603.03683

**What it does:**
Benchmark of 43 base concurrency problems + 72 mutant variants = 115 total, from a standard
concurrency textbook. Evaluates 23 LLMs on concurrent code generation judged by model checking.
Finds current LLMs struggle with concurrent code. Focuses on generation quality, not on
modeling execution dynamics.

**USE:**
"The CONCUR benchmark evaluates LLMs on generating correct concurrent code, judged by model
checking [concur]. Our problem is different: rather than generating concurrent programs, we
model their execution as a learned transition function, using scheduling nondeterminism as
a distributional training target."

---

### [ADD] Assessing LLMs in Comprehending and Verifying Concurrent Programs
**Key:** `jainpurandare`
**Full citation:**
Ridhi Jain, Rahul Purandare.
"Assessing Large Language Models in Comprehending and Verifying Concurrent Programs across Memory Models."
arXiv:2501.14326 (January 24, 2025; revised September 4, 2025).
URL: https://arxiv.org/abs/2501.14326

**What it does:**
Evaluates GPT-3.5-turbo, GPT-4, GPT-4o, GPT-4o-mini, Mistral Large2 on detecting data races
and deadlocks. Models perform well under sequential consistency but fail on relaxed memory models
(TSO, PSO). Uses SV-COMP pthread tests and ARM Litmus tests. Zero-shot only, no fine-tuning.

**USE:**
"Jain and Purandare show that strong LLMs can identify races and deadlocks under sequential
consistency but fail to reason about relaxed memory ordering [jainpurandare]. Our setting is
complementary: we train a model on Go's execution trace events, which are emitted under Go's
sequentially consistent memory model but are nondeterministic at the scheduler level."

---

## SECTION C: Go Concurrency Bug Analysis and Testing Tools
# Narrative: There is a rich literature on finding and studying Go concurrency bugs using
# static analysis, fuzzing, and empirical study. We use this literature as: (1) evidence
# that Go concurrency bugs matter and are hard, (2) source of our test programs (GoKer).
# Our approach is different: we learn to model execution, not to detect bugs directly.

---

### [EXISTING] Understanding Real-World Concurrency Bugs in Go
**Key:** `goker`
**Full citation:**
Tengfei Tu, Xiaoyu Liu, Linhai Song, Yiying Zhang.
"Understanding Real-World Concurrency Bugs in Go."
In: Proceedings of the 24th International Conference on Architectural Support for
Programming Languages and Operating Systems (ASPLOS 2019), pp. 865–878.
DOI: 10.1145/3297858.3304069
URL: https://dl.acm.org/doi/10.1145/3297858.3304069
PDF: https://songlh.github.io/paper/go-study.pdf

**What it does:**
First empirical study of Go concurrency bugs. Studies 171 bugs from Docker, Kubernetes, etcd,
gRPC, CockroachDB, BoltDB. Key finding: ~58% of blocking bugs caused by message passing, not
shared memory — counter-intuitive given Go's channel-first design. Shows bugs are as easy to
make with message passing as with mutexes.

**USE:**
"Go concurrency bugs — deadlocks, races, and goroutine leaks — arise in practice even in
production systems maintained by experts [goker]. The GoKer/GoBench corpus derived from this
study provides our held-out test programs, covering bugs from CockroachDB, Kubernetes, gRPC,
etcd, Istio, and Moby."

---

### [ADD] GoBench — A Benchmark Suite of Real-World Go Concurrency Bugs
**Key:** `gobench`
**Full citation:**
Ting Yuan, Guangwei Li, Jie Lu, Chen Liu, Lian Li, Jingling Xue.
"GoBench: A Benchmark Suite of Real-World Go Concurrency Bugs."
In: Proceedings of the 19th ACM/IEEE International Symposium on Code Generation and
Optimization (CGO 2021).
DOI: 10.1109/CGO51591.2021.9370317
URL: https://dl.acm.org/doi/10.1109/CGO51591.2021.9370317
PDF: https://lujie.ac.cn/files/papers/GoBench.pdf

**What it does:**
First benchmark suite for Go concurrency bugs. Contains 185 bugs: GoReal (82 real bugs from
9 open-source apps) and GoKer (103 bug kernels extracted and simplified from real bugs). GoKer
kernels preserve bug-inducing complexity while being minimal reproducers. This is the direct
source of the GoKer programs used as our held-out test set.

**USE:**
"Our held-out test set uses GoKer kernels from the GoBench suite [gobench], which provides
minimal reproducers of real concurrency bugs from production Go systems, each verified to
exhibit the documented bug behavior."

---

### [ADD] GCatch — Static Concurrency Bug Detection in Go
**Key:** `gcatch`
**Full citation:**
Ziheng Liu, Shuofei Zhu, Boqin Qin, Hao Chen, Linhai Song.
"Automatically Detecting and Fixing Concurrency Bugs in Go Software Systems."
In: Proceedings of the 26th ACM International Conference on Architectural Support for
Programming Languages and Operating Systems (ASPLOS 2021).
DOI: 10.1145/3445814.3446756
URL: https://dl.acm.org/doi/10.1145/3445814.3446756
PDF: https://songlh.github.io/paper/gcatch.pdf

**What it does:**
GCatch: static detector for blocking misuse-of-channel (BMOC) bugs in Go. Models Go channel
operations as a constraint system and applies a solver to find blocking bugs. GFix patches
detected bugs automatically. Found 149 previously unknown blocking bugs across 21 popular Go
applications including Docker and Kubernetes, with 125 fixed.

**USE:**
"Static analysis tools like GCatch [gcatch] find blocking concurrency bugs in Go by modeling
channel constraints symbolically. Our approach is complementary: rather than proving absence
of bugs, we learn an empirical execution model that can express uncertainty about which
scheduler events are reachable."

---

### [ADD] GFuzz — Fuzzing Go Concurrency Bugs via Message Reordering
**Key:** `gfuzz`
**Full citation:**
Ziheng Liu, Shihao Xia, Yu Liang, Linhai Song, Hong Hu.
"Who Goes First? Detecting Go Concurrency Bugs via Message Reordering."
In: Proceedings of the 27th ACM International Conference on Architectural Support for
Programming Languages and Operating Systems (ASPLOS 2022).
DOI: 10.1145/3503222.3507753
URL: https://dl.acm.org/doi/10.1145/3503222.3507753
PDF: https://songlh.github.io/paper/gfuzz.pdf

**What it does:**
GFuzz: dynamic fuzzing approach that detects channel-related concurrency bugs by mutating the
processing order of concurrent messages. Uses execution feedback to prioritize promising
orderings. Found 184 previously unknown bugs across Docker, Kubernetes, gRPC, etcd; 124
confirmed real bugs. The key insight: exploring different interleavings reveals bugs that
fixed-schedule testing misses.

**USE:**
"Dynamic analysis tools like GFuzz [gfuzz] exploit the multiple valid execution orders of
concurrent programs to find bugs by systematically exploring message reorderings. Our work
takes a complementary perspective: we treat the set of valid orderings not as a search space
for bugs but as a distributional signal for training an execution model."

---

### [ADD] GoPie — Directional Primitive-Constrained Concurrency Testing
**Key:** `gopie`
**Full citation:**
Zongze Jiang, Ming Wen, Yixin Yang, Chao Peng, Ping Yang, Hai Jin.
"Effective Concurrency Testing for Go via Directional Primitive-Constrained Interleaving Exploration."
In: Proceedings of the 38th IEEE/ACM International Conference on Automated Software Engineering
(ASE 2023).
DOI: 10.1109/ASE56229.2023.00086
URL: https://dl.acm.org/doi/10.1109/ASE56229.2023.00086
PDF: https://chao-peng.github.io/publication/ase23/ase23.pdf

**What it does:**
GoPie improves on GFuzz by using primitive-constrained heuristics to infer new interleavings
from execution histories rather than exhaustive or random scheduling. Found 11 previously
unknown concurrent bugs (9 confirmed). Addresses the limitation that GFuzz is restricted to
select-based channel reordering.

**USE:**
"Recent concurrency testing tools for Go explore scheduling diversity through increasingly
sophisticated strategies — from message reordering [gfuzz] to primitive-constrained interleaving
exploration [gopie]. These tools treat nondeterminism as a search space; we treat it as a
training distribution."

---

## SECTION D: Distribution Training and Calibration
# Narrative: Training against empirical distributions rather than point labels is an
# established technique from knowledge distillation. Calibration of probabilistic
# predictions is a known problem for neural models. We apply both ideas to a new domain
# (concurrent execution traces) where the distributional targets arise naturally from
# repeated runs, not from a teacher model.

---

### [ADD] Distilling the Knowledge in a Neural Network (Soft Targets)
**Key:** `hinton`
**Full citation:**
Geoffrey Hinton, Oriol Vinyals, Jeff Dean.
"Distilling the Knowledge in a Neural Network."
arXiv:1503.02531 (March 9, 2015).
URL: https://arxiv.org/abs/1503.02531

**What it does:**
Foundational knowledge distillation paper. Shows that training a student model against the
teacher's soft output distribution (rather than hard one-hot labels) transfers more information:
the relative magnitudes of near-zero probabilities contain genuine knowledge about class
similarities. Introduces temperature scaling of the softmax to control distribution sharpness.

**USE:**
"The idea that soft distributional targets carry more information than hard labels originates
in knowledge distillation [hinton]. We apply the same principle to concurrent execution: the
empirical next-event distribution from repeated runs of the same program carries information
about scheduler structure that any single run's label discards."

---

### [EXISTING] Forcing Diffuse Distributions out of Language Models
**Key:** `diffuse`
**Full citation:**
Yiming Zhang, Avi Schwarzschild, Nicholas Carlini, Zico Kolter, Daphne Ippolito.
"Forcing Diffuse Distributions out of Language Models."
arXiv:2404.10859 (April 16, 2024; revised August 7, 2024).
URL: https://arxiv.org/abs/2404.10859

**What it does:**
Demonstrates that instruction-tuned LLMs cannot generate uniform random outputs even when
explicitly instructed (e.g., Llama-2-13B heavily favors "5" when asked for a random number
1–10). Proposes fine-tuning to encourage diverse, diffuse output distributions. Directly
relevant to our setting where we want the model to express uncertainty over multiple valid
next events rather than collapsing to one.

**USE:**
"Instruction-tuned models are biased toward overconfident, peaked distributions even when the
correct answer is a uniform distribution over options [diffuse]. Our KL objective directly
counteracts this by training against empirical next-event distributions that are genuinely
diffuse for high-nondeterminism programs."

---

### [ADD] On Calibration of Modern Neural Networks
**Key:** `guocalib`
**Full citation:**
Chuan Guo, Geoff Pleiss, Yu Sun, Kilian Q. Weinberger.
"On Calibration of Modern Neural Networks."
In: Proceedings of the 34th International Conference on Machine Learning (ICML 2017),
pp. 1321–1330.
URL: https://proceedings.mlr.press/v70/guo17a.html

**What it does:**
Shows modern deep neural networks are poorly calibrated despite high accuracy. Introduces
Expected Calibration Error (ECE) as the primary metric. Proposes temperature scaling — a
single scalar post-hoc calibration method — as simple and effective. Foundational paper for
ECE as a metric and for the gap between accuracy and calibration.

**USE:**
"We measure calibration using Expected Calibration Error (ECE) [guocalib], the standard metric
for the gap between a model's predicted confidence and its empirical accuracy. Modern neural
networks are typically overconfident, making calibration evaluation a necessary complement to
accuracy reporting [guocalib]."

---

### [EXISTING] Probabilistic Calibration Is a Trainable Capability in Language Models
**Key:** `probcalib`
**Full citation:**
Davide Baldelli, Sruthi Kuriakose, Maryam Hashemzadeh, Amal Zouaq, Sarath Chandar.
"Probabilistic Calibration Is a Trainable Capability in Language Models."
arXiv:2605.11845 (May 12, 2026).
URL: https://arxiv.org/abs/2605.11845

**What it does:**
Shows that LLMs can be fine-tuned to better match user-specified probability distributions.
Tests soft-target fine-tuning (converting target distributions into token-level objectives)
and hard-target fine-tuning on sampled completions. Both substantially improve structured-sampling
fidelity on 12 models. Soft-target excels at stochastic tasks; hard-target at numeric sampling.
Confirms calibration is learnable, not just post-hoc correctable.

**USE:**
"Concurrent work shows probabilistic calibration is a learnable capability in LLMs through
soft-target fine-tuning [probcalib]. Our approach is an instance of this: we soft-target
fine-tune against empirical next-event distributions from repeated concurrent program runs,
where the distributional targets are not provided by a teacher model but derived from the
nondeterminism of the program itself."

---

### [ADD] Calibration and Correctness of Language Models for Code
**Key:** `spiess`
**Full citation:**
Claudio Spiess, David Gros, Kunal Suresh Pai, Michael Pradel, Rafiqul Rabin, Amin Alipour,
Susmit Jha, Prem Devanbu, Toufique Ahmed.
"Calibration and Correctness of Language Models for Code."
In: Proceedings of the 47th International Conference on Software Engineering (ICSE 2025).
PDF: https://www.software-lab.org/publications/icse2025_calibration.pdf

**What it does:**
Studies calibration of LLMs in practical software engineering tasks: code completion, function
synthesis, code repair. Introduces confidence measures associated with likelihood of correctness.
Finds LLMs are often poorly calibrated for code tasks. The only prior work that connects
calibration to code-specific downstream tasks.

**USE:**
"Calibration of LLMs for code tasks is an underexplored problem: Spiess et al. show that
even well-performing code models are often poorly calibrated in terms of their confidence
matching correctness likelihood [spiess]. Our work shows the same calibration gap exists for
concurrent execution prediction, and that distribution training can narrow it."

---

## SECTION E: Fine-tuning Methods (cite in Method section, not Related Work)
# These are cited in the paper's Method section when describing the training setup.
# Not typically in Related Work — included here for completeness.

---

### [ADD] LoRA: Low-Rank Adaptation of Large Language Models
**Key:** `lora`
**Full citation:**
Edward J. Hu, Yelong Shen, Phillip Wallis, Zeyuan Allen-Zhu, Yuanzhi Li, Shean Wang,
Lu Wang, Weizhu Chen.
"LoRA: Low-Rank Adaptation of Large Language Models."
In: International Conference on Learning Representations (ICLR 2022).
arXiv:2106.09685 (June 17, 2021).
URL: https://arxiv.org/abs/2106.09685

**What it does:**
Reduces trainable parameters by training low-rank decomposition matrices instead of full
weight updates. 10,000× fewer trainable params than full fine-tuning of GPT-3 175B, 3×
less GPU memory. On-par or better than full fine-tuning on RoBERTa, GPT-2, GPT-3.
The adapter method underlying our QLoRA fine-tuning.

**USE in Method section:**
"We fine-tune Qwen2.5-Coder-7B [qwen] using QLoRA [qlora], which combines 4-bit weight
quantization [qlora] with low-rank adapters [lora] (rank 16, α=32) to enable training
on a single 20GB GPU."

---

### [ADD] QLoRA: Efficient Finetuning of Quantized LLMs
**Key:** `qlora`
**Full citation:**
Tim Dettmers, Artidoro Pagnoni, Ari Holtzman, Luke Zettlemoyer.
"QLoRA: Efficient Finetuning of Quantized LLMs."
In: Advances in Neural Information Processing Systems (NeurIPS 2023), pp. 10088–10115.
arXiv: 2305.14314
URL: https://arxiv.org/abs/2305.14314
ACM DL: https://dl.acm.org/doi/10.5555/3666122.3666563

**What it does:**
Combines 4-bit NormalFloat quantization with LoRA adapters and double quantization to reduce
memory overhead further. Allows fine-tuning a 65B parameter model on a single 48GB GPU.
Demonstrates that quantized fine-tuning matches 16-bit fine-tuning on instruction following.
The specific technique used in our training setup.

**USE in Method section:**
See lora note above.

---

### [ADD] Qwen2.5-Coder Technical Report
**Key:** `qwen`
**Full citation:**
Binyuan Hui, Jian Yang, et al. (Qwen Team).
"Qwen2.5-Coder Technical Report."
arXiv:2409.12186 (September 18, 2024).
URL: https://arxiv.org/abs/2409.12186

**What it does:**
Introduces the Qwen2.5-Coder family: 6 model sizes (0.5B, 1.5B, 3B, 7B, 14B, 32B) trained
on 5.5 trillion tokens with scalable synthetic data generation and balanced data mixing.
State-of-the-art on 10+ code benchmarks at each model size. The Qwen2.5-Coder-7B variant
is the base model for all our fine-tuning experiments.

**USE in Method section:**
"We use Qwen2.5-Coder-7B [qwen] as the base model, selected for its strong code comprehension
at a size that fits on a 20GB GPU with 4-bit quantization."

---

## CITATION COUNT SUMMARY
# External papers (excluding your own HuggingFace/GitHub/Zenodo artifacts):
#
# Section A (Execution modeling):  cwm, debugcwm, exectuning, codeexec         [4]
# Section B (LLMs + concurrency):  concur, jainpurandare                        [2]
# Section C (Go bug analysis):     goker, gobench, gcatch, gfuzz, gopie         [5]
# Section D (Distribution/calib):  hinton, diffuse, guocalib, probcalib, spiess [5]
# Section E (Fine-tuning):         lora, qlora, qwen                            [3]
#                                                               TOTAL:           19
#
# Plus your own artifacts (not in Related Work):
#   weave-repo, weave-bench, weave-ce, weave-kl (4 self-citations, already in preprint)
#
# Combined (all citations in paper): 19 external + 4 own = 23 total
# This is appropriate for a 4-page NIER or 10-page Research Track paper.

---

## SUGGESTED RELATED WORK SECTION STRUCTURE

```
\section{Background and Related Work}

\paragraph{Code world models and program execution modeling.}
[cwm + debugcwm] → establish the paradigm.
[exectuning + codeexec] → recent work extending it.
Gap: all assume deterministic sequential execution.

\paragraph{LLMs for concurrent code.}
[concur] → generation benchmark.
[jainpurandare] → verification/comprehension evaluation.
Gap: neither models execution as a transition function.

\paragraph{Go concurrency bugs and analysis tools.}
[goker + gobench] → empirical evidence bugs matter + our test set source.
[gcatch + gfuzz + gopie] → static/dynamic tools that exploit nondeterminism differently from us.
Our framing: nondeterminism as distribution, not search space.

\paragraph{Distribution training and calibration.}
[hinton] → soft targets carry more info than hard labels.
[diffuse] → LLMs collapse to peaked distributions even when wrong.
[guocalib] → ECE metric, calibration gap in modern NNs.
[probcalib + spiess] → calibration is learnable; code-specific calibration gap exists.
Our contribution: distributional targets arise from program nondeterminism, not a teacher model.
```
