# Judge Serving (vLLM) — Clarification Questions

Please answer the questions below by filling in the letter choice after the `[Answer]:` tag.

## Question 1
Which Llama 3 judge model variant should the vLLM server run?

A) `meta-llama/Meta-Llama-3-8B-Instruct` (recommended default)
B) `meta-llama/Meta-Llama-3-70B-Instruct`
C) A smaller distilled judge model (provide HF repo)
X) Other (please describe after `[Answer]:`)

[Answer]: A

## Question 2
How should the judge vLLM server be deployed relative to the eval runner devcontainer?

A) Same RunPod pod / same GPU (only if VRAM allows both judge+SUT)
B) Same RunPod pod but different GPU (multi-GPU pod)
C) Separate RunPod pod dedicated to the judge (recommended for isolation)
X) Other (please describe after `[Answer]:`)

[Answer]: C

## Question 3
What judge endpoint base URL should the eval runner use?

A) `http://localhost:8000/v1` (judge runs on same host namespace)
B) `http://<judge-pod-ip-or-hostname>:8000/v1`
C) `https://<public-judge-endpoint>/v1` (TLS)
X) Other (please describe after `[Answer]:`)

[Answer]: X
http://<judgepodforedgeai>:8000/v1