---
name: spark-shuffle-joins
description: Shuffle, spill, Broadcast/Sort-Merge/Shuffle-Hash joins, join-key skew, repartition vs coalesce, and partition pruning. Use when shuffle bytes are huge, one task dominates a stage, a join explodes row counts, or a small dimension is still SMJ (notebook 03).
---

# Shuffle, joins, partitioning

Source of truth: `notebooks/03_shuffle_joins_partitioning_data_organization.ipynb`.

Keep AQE off unless you are testing AQE: `spark.sql.adaptive.enabled=false`.

## Shuffle

A shuffle **redistributes rows so equal keys share a partition**. Map tasks write shuffle files; reduce tasks fetch them. That is a **stage boundary** (`Exchange` in the plan).

Why it is expensive: serialize, disk, network, deserialize, memory while sorting/hashing.

Typical wide triggers: `groupBy`/`agg`, `distinct`, `repartition`, global `orderBy`, non-broadcast joins.

**Spill** = execution memory full, operator writes sort/hash chunks to disk, job usually **finishes slower**. Inspect Stage → Task metrics: Spill (Memory) / Spill (Disk). Spill is not OOM.

Mitigate spill: sane partition sizes, pre-aggregate, broadcast a truly small side, fix skew, more executor memory only after the shape is right.

On this 2-worker lab, `repartition(1000+)` creates a storm of tiny tasks. Prefer letting `spark.sql.shuffle.partitions` (8 in the demos) stand, or coalesce down. `repartition(n, key)` is for **key alignment**, not for “more parallelism” on megabytes of data.

## Join strategies

1. **Broadcast Hash Join (BHJ)** — small + any. `broadcast(small)` or auto-threshold. Small side is a full copy to every executor (**not** a shuffle). Broadcast lives in **storage** memory and **cannot spill**; it fits or it OOMs.
2. **Sort-Merge Join (SMJ)** — large + large. Shuffle + sort both sides, then merge. Default when broadcast is disabled.
3. **Shuffle Hash Join (SHJ)** — shuffle both sides, hash-build the smaller per partition, no global sort. Can beat SMJ when sort is the bottleneck; hash tables pressure executor memory.

`autoBroadcastJoinThreshold=-1` plus `preferSortMergeJoin=true` is how the notebooks **force SMJ** to make shuffle visible. Production jobs should not do that to a 5-row FX table.

Join **keys** matter as much as strategy:

- Join on a **unique row id** (1:1) if you need the same grain. Join on a low-cardinality column (`country`) of two 12k extracts → cartesian-by-key (millions of pairs).
- After a join, aggregate only columns that are unambiguous.

## Skew

Uneven keys → one shuffle partition holds most rows → one task 10–100× slower, extra shuffle read, possible spill. Notebook 03 forces a hot key with `when(... otherwise lit("HOT"))`.

Fixes, in order for this course:

1. **Do not invent a hot key.** If the real grain is `category` (or another moderate-cardinality column), join on that.
2. **Broadcast the small side** so there is no shuffled join to skew.
3. **Salt** the hot key when **both** sides are too large to broadcast (duplicate the small/build side across salt buckets).
4. AQE skew join (notebook 05) only helps **SMJ** after a shuffle stage, not a broadcast join.

Spark UI: sort tasks by shuffle read or duration. Median vs max ratio of tens or hundreds is skew.

## `repartition` vs `coalesce`

- `repartition(n)` / `repartition(n, key)` — **full shuffle**, can increase or decrease, balances sizes.
- `coalesce(n)` — **narrow**, only decreases partitions, can leave uneven sizes, no Exchange.

Do not `repartition` up to thousands of partitions “to be safe”.

## Partitioning vs bucketing

Directory partitioning (`partitionBy("month")`) enables **partition pruning** if the query filters that column. Bucketing can skip join shuffle only when bucket count/keys/metadata line up — **verify in the plan**, never assume.
