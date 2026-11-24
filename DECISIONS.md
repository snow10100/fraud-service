# Engineering decisions

Five decisions I made (or kept deliberately) while turning the notebook into a service,
with the alternatives I weighed.

## 1. The model is baked into the image, not mounted or downloaded

The joblib bundle is copied into the image (`COPY models/... /models/`) in its own layer,
between the dependencies and the source code. The image is then a complete, versioned unit:
the commit SHA tag identifies code *and* model together, and the smoke test in CI proves that
exact pair works. A mounted volume would let the model drift from the code that was tested,
and pulling from a registry at start-up adds a network dependency and a secret. Those options
make sense for large models; this one is about 221 KB, so baking it in costs nothing.
Because the model layer sits before `src/`, a code-only change still rebuilds in about 2 seconds.

## 2. The block threshold is a business rule in the domain, its value is configuration

`decide()` in `domain/policies.py` is a pure function: score in, `allow`/`review`/`block` out.
The threshold itself is passed in from typed settings (`FRAUD_BLOCK_THRESHOLD`, default 0.85,
validated between 0.5 and 0.99). The rule belongs to the risk team, not to the model, so it
lives where a risk officer can read it and where unit tests pin its boundaries
(0.849999 → review, 0.85 → block). Hard-coding the value would need a redeploy to change it;
reading `os.environ` inside the loop, as the notebook did, hid it and skipped validation.

## 3. The predict route is a plain `def`, and scaling is done with processes

Model inference is blocking CPU work. Inside an `async def` route it would freeze the event
loop and stall every other request, health checks included. A plain `def` runs in FastAPI's
thread pool instead. Threads do not speed up CPU-bound Python, so throughput comes from
processes: the container runs `--workers 2`. I chose 2, not 4, because the compose stack
limits the API to 512 MB and I measured 306 MiB with two workers (see BENCHMARKS.md);
each extra worker holds its own copy of the model and libraries, so 4 would risk an
out-of-memory kill (exit 137).

## 4. The healthcheck asks `/v1/ready`, not `/v1/health`

Liveness (`/v1/health`) only says the process is up; readiness (`/v1/ready`) says the model is
loaded and the service can answer correctly. Docker's HEALTHCHECK and compose's
`depends_on: condition: service_healthy` both use readiness, with a 20 s start period, so
traffic only arrives once the model is warm. Using liveness would mark the container healthy
before it can score, and making liveness depend on the model would cause a restart storm:
a slow load fails the check, the container is killed mid-load, and the cycle repeats.

## 5. Training/serving skew is prevented by one feature function and a golden file

The notebook computed `is_night` twice, with `hour < 6` in one place and `hour <= 6` in the
other, which silently mis-scored 182 of 5,000 rows. Now `Transaction.to_features()` is the
single source of feature logic, and two independent tripwires guard it: a unit test on the
hour-6 boundary (fails in under a second) and the golden-file test over all 5,000 rows (runs
in CI's nightly job). I planted the bug again on purpose and both caught it, and in Lab 5 the
pipeline blocked a pull request that contained it. The golden file is never regenerated
without a stated reason, because regenerating it would hide exactly this kind of drift.
