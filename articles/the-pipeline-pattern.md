---
title: The Pipeline Pattern
published: true
description: 'A practical look at the Pipeline Pattern (Pipes & Filters) using a small Python scraper. The example connects independent stages with queues, uses worker pools for parallelism, and explores fan-out, backpressure, graceful shutdown, and how the same architecture maps to Kafka/RabbitMQ and distributed systems. The key idea: decouple stages, connect them with queues, and scale each stage independently.'
tags:
  - python
  - systemdesign
  - concurrency
  - architecture
cover_image: 'https://raw.githubusercontent.com/kasir-barati/dev.to/refs/heads/main/articles/assets/the-pipeline-pattern/cover.png?v=7bd6b49'
series: System Design
id: 4529042
date: '2026-08-30T13:55:51Z'
---

I watched a nice video about a small multi-stage scraper: it was basically scraping [S&P 500 tickers from Wikipedia](https://en.wikipedia.org/wiki/List_of_S%26P_500_companies), fetch a live price for each from [Yahoo Finance](https://finance.yahoo.com/quote/AAPL/), and write the results to Postgres. Each stage runs its own pool of worker threads, and stages talk to each other through queues. So I just decided to write about it since it is a nice distributed-systems design pattern.

## [Pipes & Filters (AKA The Pipeline Pattern)](https://learn.microsoft.com/en-us/azure/architecture/patterns/pipes-and-filters)

This is a classic **architectural pattern**: a series of independent processing stages ("filters"), each connected to the next by a channel ("pipe"). Each stage:

- Reads from an inbound queue.
- Does one unit of work.
- Writes to an outbound queue.
- And knows nothing about the stages before or after it.

The first stage (no inbound queue) is the **source** or **producer**. The last stage (no outbound queue) is the **sink** or **consumer**. Everything in between is just a filter.

In the following example we have:

```
WikiWorker (source)
    -> symbol_queue
        -> YahooFinancePriceScheduler x4 (filter, fanned out)
            -> postgres_queue
                -> PostgresMasterScheduler x4 (sink, fanned out)
```

Another example which I believe is a strong candidate for this design pattern is when you have a pipeline for raw data, sending them to different LLM-powered apps to extract and generate useful insights while maintaining a clean architecture which is scalable and maintainable. LLMs are slow, I/O-bound, rate-limited, and failure-prone (timeouts, malformed JSON, rate limit errors), and you often want to run several different extraction tasks over the same raw data.

A natural shape:

```
Source: raw data ingestion (files, API, scrape, DB change stream)
    -> raw_queue
        -> Preprocessing stage (clean/chunk/normalize) x N workers
            -> llm_queue
                -> LLM extraction workers x N (fan-out: one pool per "app" -- summarizer, entity extractor, sentiment, classifier, etc.)
                    -> results_queue(s)
                        -> Sink: persistence / downstream index / notification
```

The fan-out step is the interesting part: a single normalized item can be pushed to multiple output queues, one per LLM-powered consumer, the same broadcast-to-all-output-queues trick our scraper already does. Each "app" (summarizer, extractor, classifier) becomes an independent filter stage with its own worker pool and its own scaling knob.

### Benefits of this Design Pattern

- **Independent scaling per stage**: LLM calls are the bottleneck, not ingestion. You can run 2 preprocessing workers and 20 LLM-call workers without touching the rest of the pipeline.
- **Isolation of failure and backpressure**: A stalled or rate-limited LLM provider backs up its own queue instead of crashing ingestion or the other extraction apps running in parallel.
- **Easy horizontal fan-out to multiple "apps"**: Adding a new insight-extraction app is just: add a new output queue + a new worker pool. No changes to upstream stages.
- **Natural retry/DLQ boundaries**: Since each stage only knows its own queue, you can wrap an LLM stage with its own retry logic or dead-letter queue without leaking that complexity into ingestion or persistence code.
- **Swappable transport**: In-memory Queue today, Kafka/RabbitMQ/SQS tomorrow, the stage logic doesn't change, only what's plugged into the pipe. That's what "clean architecture" buys you here: stages depend on queue interfaces, not on each other.
- **Composability/testability**. Each worker class is testable in isolation, feed it a fake input queue, assert what lands on the output queue. No need to spin up the whole pipeline to unit test one extraction stage.
- **Cost/throughput control point**: Because concurrency is explicit per stage (pool size), it's a direct lever for controlling how hard you hit an LLM API's rate limits, independent of ingestion speed.

> **Note**
>
> This design pattern itself is architecture-agnostic. It's just stages + queues; whether those stages are threads in one process, services in a monorepo, or separate microservices is an implementation detail, not a change to the pattern. You do always need some orchestrator, though its job shrinks as you move outward:
>
> - **Monolith/threads**: you have a orchestrator (in our scraper example we have `main.py`), which owns queue creation, worker counts, and shutdown.
> - **Monorepo/multi-process**: orchestrator becomes a supervisor process or a broker's own routing (Kafka/RabbitMQ take over "the pipe").
> - **Microservices + managed inference ([SageMaker](https://aws.amazon.com/sagemaker/) etc.)**: orchestrator is very thin, it just decides how many in-flight requests it allows.
>
>   **Dual autoscaling concern**: you now have concurrency control in two places, your orchestrator's queue-consumption concurrency, and SageMaker's endpoint autoscaling. And they aren't aware of each other. Imagine your orchestrator can burst requests faster than SageMaker's endpoint scales up (429s/throttling), or SageMaker scales up while your orchestrator is deliberately throttled, wasting provisioned capacity.
>
>   The fix is to make one the source of truth (SageMaker), and the orchestrator reacts to them:
>
>   - Have your orchestrator's concurrency be a ceiling tuned to your endpoint's steady-state capacity, not an independent guess.
>   - Let SageMaker's autoscaling handle burst absorption, and have your orchestrator back off on throttling responses (retry-with-backoff) rather than pre-guessing SageMaker's scale.
>     - "Pre-guessing" = hardcoding a concurrency number based on an assumption like "SageMaker probably has 10 instances up, so I'll send 10x work."
>     - Instead of polling "how many instances exist", react to the endpoint's actual signal.
>   - Optionally drive orchestrator concurrency from an external signal (endpoint's current instance count / concurrency metric) instead of a static number.

## The Pieces this Pattern is Made of

A few sub-patterns show up together whenever you build a pipeline like this:

- **Producer-consumer**:
  - A queue serves as a buffer between two parts of our app. One puts data in the queue, and the other takes them out.
  - E.g. `WikiWorker` puts ticker symbols into `symbol_queue`. The Yahoo Finance workers take symbols out of it.
    - `WikiWorker` doesn't need Yahoo to be ready, and Yahoo doesn't need Wiki to still be running
    - The queue absorbs the timing mismatch.
- **Worker pool**: Instead of having just one thread handle a stage, you run several identical threads that all pull from the same queue, so the work gets split among them automatically..
- **Fan-out / fan-in**:
  - **Fan-out** spreads work across workers:
    - One queue.
    - Many workers reading from it (this is the worker pool from above, "fanning out" work across threads).
  - **Fan-in** collects workers' output back into one place:
    - Many workers.
    - All workers write into the same single downstream queue.
- [**Poison pill (sentinel value)**](https://en.wikipedia.org/wiki/Sentinel_value): a special marker value, here it is `'DONE'` string. Pushed onto a queue to tell every consumer "there's nothing more coming, exit your loop". It's the standard way to shut down a pipeline gracefully instead of killing threads abruptly.

## Same Design Patterns in Other Programming Languages

- **Go**, using goroutines and channels, [their article](https://go.dev/blog/pipelines) on this is basically the canonical writeup: it describes a pipeline as a series of stages connected by channels, each stage a group of goroutines running the same function, with a `done` channel used for the poison-pill/cancellation (also read [this](https://ketansingh.me/posts/pipeline-pattern-in-go-part-1/)).
- **Java**, using [`BlockingQueue`](https://www.geeksforgeeks.org/java/blockingqueue-interface-in-java/) and thread pools ([`ExecutorService`](https://www.geeksforgeeks.org/java/java-util-concurrent-executorservice-interface-with-examples/)).
- **Unix shell pipelines** (`cmd1 | cmd2 | cmd3`), the original inspiration for the name.
- **Message brokers** like Kafka or RabbitMQ, where "queue" becomes a literal broker topic/queue instead of an in-memory object, and stages become separate services instead of threads.

The underlying idea; decouple stages, connect them with buffered channels, parallelize each stage independently is a general concurrency and distributed-systems pattern. Python's `queue.Queue`/`multiprocessing.Queue` is just one convenient implementation of "the pipe" part.

## Scraper Example

I believe the database schema is more than obvious but just to leave no room to the imagination:

```sql
CREATE TABLE IF NOT EXISTS prices (
    id           SERIAL PRIMARY KEY,
    symbol       TEXT,
    price        DOUBLE PRECISION,
    insert_time  TIMESTAMPTZ
);
```

> ⚠️ **Important Note**
>
> I did NOT sanity check if the scaping still is correct since I wanted to talk about the design pattern and not the scraping itself.

### `src/workers/wiki.py`

```py
"""Scrapes the current S&P 500 constituent list from Wikipedia."""

from collections.abc import Iterator

import requests
from bs4 import BeautifulSoup


class WikiWorker:
    """Fetches and parses the S&P 500 constituents table from Wikipedia."""

    def __init__(self) -> None:
        self._url: str = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

    @staticmethod
    def _extract_company_symbols(page_html: str) -> Iterator[str]:
        """Yield ticker symbols parsed out of the constituents table HTML."""
        soup = BeautifulSoup(page_html, "html.parser")
        table = soup.find(id="constituents")
        table_rows = table.find_all("tr")

        for table_row in table_rows[1:]:
            symbol: str = table_row.find("td").text.strip("\n")
            yield symbol

    def get_sp_500_companies(self) -> Iterator[str]:
        """Yield each S&P 500 ticker symbol, or nothing on request failure."""
        response = requests.get(self._url)
        if response.status_code != 200:
            print("Couldn't get entries")
            return

        yield from self._extract_company_symbols(response.text)
```

### `src/workers/yahoo_finance_price.py`

```py
"""Worker pool that fetches live prices from Yahoo Finance."""

from __future__ import annotations

import random
import threading
import time
from datetime import UTC, datetime
from queue import Empty, Queue
from typing import Literal

import requests
from lxml import html

Symbol = str
Price = float
PriceMessage = tuple[Symbol, Price, str]
Sentinel = Literal["DONE"]


class YahooFinancePriceScheduler(threading.Thread):
    """
    Pulls ticker symbols off an input queue and fans price results out
    to one or more output queues.
    """

    def __init__(
        self,
        input_queue: "Queue[Symbol | Sentinel]",
        output_queues: list["Queue[PriceMessage | Sentinel]"],
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._input_queue = input_queue
        self._output_queues = output_queues
        self.start()

    def run(self) -> None:
        while True:
            # Defensive programming: protects this scheduler from hanging
            # indefinitely. Trade-off: if a message arrives right after the
            # timeout fires, it's dropped without ever being processed.
            try:
                val = self._input_queue.get(timeout=20)
            except Empty:
                print("Timeout reached in Yahoo Finance scheduler, stopping...")
                break

            if val == "DONE":
                for output_queue in self._output_queues:
                    output_queue.put("DONE")
                break

            worker = YahooFinancePriceWorker(symbol=val)
            price = worker.get_price()
            if price is None:
                continue

            message: PriceMessage = (val, price, str(datetime.now(UTC)))
            for output_queue in self._output_queues:
                output_queue.put(message)

            time.sleep(random.random())  # Cloudflare may block bursty requests


class YahooFinancePriceWorker:
    """Fetches the current price for a single ticker symbol."""

    def __init__(self, symbol: Symbol, **kwargs) -> None:
        self._symbol = symbol
        base_url = "https://finance.yahoo.com/quote/"
        self._url = f"{base_url}{self._symbol}"

    def get_price(self) -> Price | None:
        """Return the current price, or None if the request/parse fails."""
        response = requests.get(self._url)
        if response.status_code != 200:
            return None

        page_contents = html.fromstring(response.text)
        nodes = page_contents.xpath(
            '//*[@id="quote-header-info"]/div[3]/div[1]/div/span[1]'
        )
        if not nodes:
            return None

        raw_price = nodes[0].text
        return float(raw_price.replace(",", ""))
```

### `src/workers/postgres.py`

```py
"""Worker pool that persists price messages into Postgres."""

from __future__ import annotations

import os
import threading
from queue import Empty, Queue
from typing import Literal

from sqlalchemy import create_engine, text

Symbol = str
Price = float
PriceMessage = tuple[Symbol, Price, str]
Sentinel = Literal["DONE"]


class PostgresMasterScheduler(threading.Thread):
    """Consumes price messages from a queue and writes each one to Postgres."""

    def __init__(
        self, input_queue: "Queue[PriceMessage | Sentinel]", **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self._input_queue = input_queue
        self.start()

    def run(self) -> None:
        while True:
            try:
                val = self._input_queue.get(timeout=20)
            except Empty:
                print("Timeout reached in Postgres scheduler, stopping...")
                break

            if val == "DONE":
                break

            symbol, price, extracted_time = val
            worker = PostgresWorker(symbol, price, extracted_time)
            worker.insert_into_db()


class PostgresWorker:
    """Inserts a single price observation into the `prices` table."""

    def __init__(self, symbol: Symbol, price: Price, extracted_time: str) -> None:
        self._symbol = symbol
        self._price = price
        self._extracted_time = extracted_time

        self._pg_user: str = os.environ.get("PG_USER", "")
        self._pg_pw: str = os.environ.get("PG_PW", "")
        self._pg_host: str = os.environ.get("PG_HOST", "localhost")
        self._pg_db: str = os.environ.get("PG_DB", "postgres")

        self._engine = create_engine(
            f"postgresql://{self._pg_user}:{self._pg_pw}@{self._pg_host}/{self._pg_db}"
        )

    def insert_into_db(self) -> None:
        insert_query = """
            INSERT INTO prices (symbol, price, insert_time)
            VALUES (:symbol, :price, CAST(:extracted_time AS TIMESTAMP))
        """
        with self._engine.connect() as conn:
            conn.execute(
                text(insert_query),
                {
                    "symbol": self._symbol,
                    "price": self._price,
                    "extracted_time": self._extracted_time,
                },
            )
            conn.commit()
```

### `src/main.py`

```py
"""Wires the wiki -> Yahoo Finance -> Postgres pipeline together and runs it."""

from __future__ import annotations

import time
from multiprocessing import Queue

from workers.postgres import PostgresMasterScheduler
from workers.wiki import WikiWorker
from workers.yahoo_finance_price import YahooFinancePriceScheduler


def main() -> None:
    symbol_queue: Queue = Queue()
    postgres_queue: Queue = Queue()
    scraper_start_time: float = time.time()
    wiki_worker = WikiWorker()

    num_yahoo_finance_price_workers: int = 4
    yahoo_finance_price_scheduler_threads: list[YahooFinancePriceScheduler] = [
        # Imagine multiple output queues here: one for Redis, one for
        # RabbitMQ, etc. Each Yahoo worker fans its result out to all of them.
        YahooFinancePriceScheduler(
            input_queue=symbol_queue, output_queues=[postgres_queue]
        )
        for _ in range(num_yahoo_finance_price_workers)
    ]

    num_postgres_workers: int = 4
    postgres_scheduler_threads: list[PostgresMasterScheduler] = [
        PostgresMasterScheduler(input_queue=postgres_queue)
        for _ in range(num_postgres_workers)
    ]

    for symbol in wiki_worker.get_sp_500_companies():
        symbol_queue.put(symbol)

    for _ in yahoo_finance_price_scheduler_threads:
        symbol_queue.put("DONE")

    for thread in yahoo_finance_price_scheduler_threads:
        thread.join()

    for thread in postgres_scheduler_threads:
        thread.join()

    elapsed = time.time() - scraper_start_time

    print(f"Finished in {elapsed:.2f}s")


if __name__ == "__main__":
    main()
```

## More Mature Pipelines

So I guess you have seen it now that if you need to add a new stage/worker to the existing orchestrator you must change the code and write a bunch of code which really feels like boilerplates. So next what you can do is defining your pipeline in a YAML file and then each time you have a new stage/worker you can just need to add it there. So create a `src/pipelines` directory and inside it create a yaml file:

```yaml
# src/pipelines/wiki_yahoo_scraper_pipeline.yaml
queues:
  - name: SymbolQueue
    description: Contains symbols/tickers to be scraped from Yahoo
  - name: PostgresUploading
    description: Contains data that needs to be uploaded to Postgres

workers:
  - name: WikiWorker
    description: This scraps Wikipedia page nad extracts symbols/tickets
    location: workers.wiki
    class: WikiWorkerMasterScheduler
    instances: 1
    input_values:
      - https://en.wikipedia.org/wiki/List_of_S%26P_500_companies
    output_queues:
      - SymbolQueue
  - name: YahooFinanceWorker
    description: Pulls the stock price of a given ticket from Yahoo Finance
    location: workers.yahoo_finance_price
    class: YahooFinancePriceScheduler
    instances: 4
    input_queue: SymbolQueue
    output_queues:
      - PostgresUploading
  - name: PostgresWorker
    description: Stores stock data in Postgres
    location: workers.postgres
    class: PostgresMasterScheduler
    instances: 4
    input_queue: PostgresUploading
```

So as you can see with this you are effectively moving the logic of your pipeline into a config file which is written in YAML. And this makes your orchestrator cleaner and you can easily reason about your pipeline without having to read a bunch of python code. Also it makes it easier to differentiate between when you wanna e.g. change the URL you use for scraping data from it, from implementation changes you had to make to the code itself.

Easier time to review and understand what was changed in a PR/commit. And now your `src/main.py` would look a lot nicer with less manual steps involved:

```py
"""Wires the wiki -> Yahoo Finance -> Postgres pipeline together and runs it."""

from __future__ import annotations

import time
from pathlib import Path

from pipelines.reader import YamlPipelineExecutor


def main() -> None:
    scraper_start_time = time.time()
    pipeline_location = Path(__file__).parent / 'pipelines' / 'wiki_yahoo_scraper_pipeline.yaml'
    yaml_pipeline_executor = YamlPipelineExecutor(pipeline_location=pipeline_location)
    yaml_pipeline_executor.process_pipeline()
    
    elapsed = time.time() - scraper_start_time

    print(f"Finished in {elapsed:.2f}s")


if __name__ == "__main__":
    main()
```

I did NOT add `YamlPipelineExecutor` code here. But that was not the only change I had to make to make this pipeline work with the aforementioned yaml file. You can see the [complete example here](https://github.com/kasir-barati/python/tree/bf47c7b1c9b629e24b6730e01ea0e3ea4e43c074/tips/examples/scrapper-pipeline-design-pattern).

---

If you've built something similar, especially across process or machine boundaries with a real broker instead of an in-memory queues I'd love to hear how you handled backpressure and shutdown.
