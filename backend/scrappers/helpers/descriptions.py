# backend/scrappers/helpers/descriptions.py
"""Bulk description fetching, shared by both aggregation entry points.

Lives here rather than in unified_scrapper so aggregate_scrappers (the path the
API actually calls) can use it too.
"""

from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

from .job_desc_fetcher import get_job_description
from .relevance import is_relevant


def _round_robin_by_source(jobs):
    """Interleave jobs so one source cannot monopolise a limited run.

    Jobs arrive sorted by source, so a plain head-slice would spend the whole
    budget on whichever source sorts first.
    """
    buckets = OrderedDict()
    for job in jobs:
        buckets.setdefault(str(job.get("source", "")), []).append(job)

    interleaved = []
    while buckets:
        for source in list(buckets):
            interleaved.append(buckets[source].pop(0))
            if not buckets[source]:
                del buckets[source]
    return interleaved


def fetch_descriptions(
    jobs,
    title_filter=None,
    max_workers=2,
    mode="loose",
    limit=0,
):
    """Populate job["description"] in place and return the list.

    Requests are paced per host inside get_job_description, so extra workers
    mostly just queue on the rate limiter; a small pool is enough to overlap
    parsing with waiting.

    limit > 0 caps how many descriptions are fetched, spread across sources.
    Pacing means roughly 1.5s per job, so an uncapped run over a few hundred
    jobs takes minutes; the remaining jobs keep an empty description rather
    than being dropped.
    """
    if not jobs:
        return []

    for job in jobs:
        job.setdefault("description", "")

    eligible = [
        job
        for job in jobs
        if job.get("href") and is_relevant(job, title_filter, mode)
    ]

    if limit and limit > 0 and len(eligible) > limit:
        print(
            f"[desc] Fetching {limit} of {len(eligible)} descriptions "
            f"({len(eligible) - limit} skipped by the limit)"
        )
        eligible = _round_robin_by_source(eligible)[:limit]

    if not eligible:
        return jobs

    def fetch(job):
        job["description"] = get_job_description(job["href"])
        return job

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        # list() forces evaluation so exceptions surface here, not silently.
        list(executor.map(fetch, eligible))

    filled = sum(1 for job in jobs if job.get("description"))
    print(f"[desc] Populated {filled}/{len(jobs)} descriptions")

    return jobs
