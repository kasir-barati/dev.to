---
title: "How to Debug the Slowness of your App"
published: true
description: "A deep-dive debugging session for why the voting frontend app is so slow."
tags:
  - aws
  - debugging
  - kubernetes
  - fullstack
cover_image: "https://raw.githubusercontent.com/kasir-barati/dev.to/refs/heads/main/articles/assets/slow-votes-and-the-worker-busy-loop/cover.png"
series: Voting App Terraform
---

Right after a fresh `terraform apply` + `kubectl apply`, the app was reachable and the page loaded instantly, but clicking a vote button sometimes took 5, 10, even 60 seconds to respond. Nothing crashed, nothing showed as unhealthy in `kubectl get pods`, it just felt slow, unpredictably. This post is the exact sequence of checks I took to find the real cause.

## Checkpoint

```bash
kubectl get pods
```

Check replicated vote app is in `Running` state, not restarting. If the pods start restarting you can clearly observe it since the uptime will be short.

## Is it the Load Balancer and or something in the Network

My very first instinct was to check if "it's the load balancer", a brand new AWS Classic ELB (the kind `type: LoadBalancer` creates by default on EKS, recognizable by the `<hash>-<numbers>.<region>.elb.amazonaws.com` DNS pattern) does take a few minutes to fully register healthy targets after creation. That's a real, common cause of slowness right after a first deploy, so it was the first thing to check, and honestly I highly doubt it was the cause since I tested it even after 20 minutes and it was still slow.

The way to test it without guessing is `curl`'s builtin timing breakdown, which separates "how long to open the TCP connection" from "how long to get the first byte of the response":

```bash
time curl -w "\nconnect:%{time_connect} ttfb:%{time_starttransfer} total:%{time_total} code:%{http_code}\n" \
     -o /dev/null \
     -s -X POST \
     -d "vote=a" <voting-service-elb-hostname>/
```

Result, run several times in a row:

```text
connect:0.037654 ttfb:9.284812 total:9.285153 code:200
connect:0.031296 ttfb:9.904313 total:9.905223 code:200
connect:0.034359 ttfb:0.085231 total:0.086157 code:200
```

`connect` was fast and identical every single time, under 40ms. That rules out the load balancer and the network path to it: the TCP handshake to the ELB always succeeded immediately. Whatever was slow was happening _after_ the connection was already open. This one measurement eliminated an entire category of suspects (ELB health-check warm-up, DNS propagation, network routing) in a single step.

## Is It One Specific Bad Pod?

`voting-deployment` runs 3 replicas across 2 nodes. A plausible next guess was: one pod or one node is misbehaving, and the load balancer's round-robin just happens to hit it sometimes.

```bash
for i in $(seq 1 9); do
  curl -s -w "ttfb:%{time_starttransfer}\n" -X POST -d "vote=a" \
    <voting-service-elb-hostname>/ | grep -E "container ID|ttfb"
done
```

Result:

```text
req 1  z5zqc   ttfb:29.148525
req 2  z5zqc   ttfb:59.978988
req 3  z5zqc   ttfb:0.051699
req 4  b89pf   ttfb:9.351083
req 5  z5zqc   ttfb:29.530290
req 6  z5zqc   ttfb:49.977953
req 7  z5zqc   ttfb:19.976000
req 8  9886g   ttfb:19.435484
req 9  b89pf   ttfb:9.966600
```

The same single pod (`z5zqc`) returned times ranging from `0.05` seconds to `59.9` seconds on different requests. That rules out "one bad pod". A consistently broken pod would be slow every time, not sometimes instant and sometimes a full minute. Whatever the cause was, it lived somewhere all three pods shared, not in any one of them.

## Is it the Shared Redis Dependency

Every vote, regardless of which `voting` pod handles it, ends up doing one thing: pushing the vote onto a Redis list. Redis was the one component all 3 pods actually shared, so it was the next thing to inspect directly.

```bash
kubectl exec -it redis-pod -- redis-cli --latency
```

```text
min: 0, max: 31, avg: 0.14 (5902 samples)
```

Redis itself was answering individual commands in well under a millisecond on average. So Redis wasn't slow at _executing_ commands. But that average hides bursts, and Redis processes one command at a time (it's [single-threaded](https://dev.to/ricky512227/understanding-redis-threading-what-i-learned-the-hard-way-paf)), so a command can still wait in line behind a large
backlog of _other_ commands even if each one is individually fast.

But that is far from being the cause of this issue, I mean even when I just send a single request to the voting app. But just checking it was a good idea to make sure it is individually fast enough. The next step was to watch what Redis was actually being asked to do, in real time:

```bash
kubectl exec -it redis-pod -- redis-cli monitor
```

```text
1788542712.947941 [0 10.0.0.150:39747] "LPOP" "votes"
1788542712.948040 [0 10.0.1.116:57551] "LPOP" "votes"
1788542712.948192 [0 10.0.0.59:36523]  "LPOP" "votes"
1788542712.948829 [0 10.0.0.150:39747] "LPOP" "votes"
1788542712.948993 [0 10.0.0.59:36523]  "LPOP" "votes"
1788542712.949210 [0 10.0.1.116:57551] "LPOP" "votes"
... (continues nonstop)
```

Those three IP addresses are the three `worker` pods. They were issuing `LPOP votes` which is a **non-blocking** pop that returns immediately whether or not there's a vote waiting (back to back, with no pause, forever). Not "poll every second", not "wait for a vote to arrive" (that would be [`BLPOP`](https://redis.io/docs/latest/commands/blpop/), the blocking version of the same command), a tight loop with no rate limit at all.

```bash
kubectl exec redis-pod -- redis-cli monitor > /tmp/redis-monitor.log &
MPID=$!; sleep 3; kill $MPID
wc -l /tmp/redis-monitor.log
grep -c LPOP /tmp/redis-monitor.log
```

```text
7571 /tmp/redis-monitor.log
7563 LPOP
```

BTW the reason for the number if [`LPOP`](https://redis.io/docs/latest/commands/lpop/) calls is that workers have nothing else to do, so almost every poll finds the list empty and immediately loops again.

## Checking CPU Pressure

Confirm the hypothesis that the Redis node's CPU is saturated. This checks if commands are queuing up behind the busy loop. But for this we need to have the [metrics-server](https://github.com/kubernetes-sigs/metrics-server) installed:

```bash
# These two failed since the metrics-server was not installed!
kubectl top nodes
kubectl top pods
```

The fallback is `/proc/loadavg` is a host-level (not per-container) kernel counter, so reading it from inside any pod still reports the real load of the node that pod is running on:

```bash
kubectl exec redis-pod -- cat /proc/loadavg
```

Just a few notes about `/proc/loadavg`. [On Linux, every process is in one of several states](https://www.cbtnuggets.com/blog/certifications/open-source/what-are-the-5-linux-process-states). The two that matter for load average are:

- **Running**: currently executing on a CPU right now.
- **Runnable (waiting)**: ready to execute, wants CPU time, but no CPU is free at this instant, so it's sitting in the run queue.

```text
3.33 2.78 2.53 3/345 74
 │    │    │    │  │  │
 │    │    │    │  │  └── last PID created on the system
 │    │    │    │  └────── total number of processes/threads currently existing
 │    │    │    └───────── currently runnable processes / total processes
 │    │    └────────────── Average runnable processes over the last 15-minute load average
 │    └─────────────────── Average runnable processes over the last 5-minute load average
 └──────────────────────── Average runnable processes over the last 1-minute
```

The node running `redis-pod` is a `t3.medium` with 2 vCPUs. A 1-minute load average of 3.33 on a 2-vCPU machine means, on average, more than three processes were runnable and competing for two CPUs at that moment. The node was meaningfully CPU-saturated, not idle. `t3.medium` is also a _burstable_ instance type: it earns CPU credits at a fixed baseline rate and can spend banked credits to burst above that, but a sustained, uncapped load (exactly what a 2500-call-per-second busy loop produces) burns through that credit balance and eventually gets throttled by AWS at the hypervisor level, independent of anything Kubernetes can see or report.

---

## Conclusion

The `worker` deployment ([`worker-deployment.yaml`](https://github.com/kasir-barati/docker/blob/948d84f667d60107817b74f00bf50b16505af9fb/k8s/voting-microservice-architecture/deployment/worker-deployment.yaml)) polls Redis for new votes using a **non-blocking, unrate-limited loop**, issuing `LPOP votes` continuously regardless of whether any votes are waiting. With 3 worker replicas doing this at once, Redis's single command-processing thread and the CPU of whatever node it lands on are kept under constant, unnecessary load.

On a burstable `t3.medium` node with no CPU requests/limits set on any pod, this occasionally tips into CPU credit throttling, and any command sharing that node's CPU (including the [`RPUSH`](https://redis.io/commands/rpush) a real vote needs to execute) gets delayed behind it.

### What Now

A few gaps made this take far longer to pin down than it should have, and are worth closing regardless of whether the busy-loop itself gets fixed (and in fact we cannot fix them unless we pull down the worker code, fix the bug, package it, and publish it on AWS ECR, or Docker Hub):

- **No `metrics-server` installed:** `kubectl top nodes` / `kubectl top pods` is the standard, immediate way to see "which node/pod is eating CPU".
- **No application logs beyond the default web server access log:** The `voting` pods' logs showed gunicorn's request line (`"POST / HTTP/1.1" 200 1710`) but nothing about _how_ that request was handled internally which again is about changing the codebase of the `voting` app.
- **No resource requests/limits on any pod:** Without a CPU request on the pods, Kubernetes has no basis to throttle or even flag them as consuming an unusual amount of CPU relative to their job. A request/limit pair would make this kind of runaway loop visible as a metric (pod at/near its CPU limit) instead of only visible as "everything is randomly slow".
- **No alerting layer of any kind:** A CPU saturation alarm on the node.
- And as shown in the CPU saturation I also realized I did not set any **limitation on how Kubernetes must create new pods in another node**. As of now Kubernetes will continue creating new pods on the same node until all the available IP addresses are exhausted. This means I should have [set a limit on how many CPU and RAM resources each pod will be needing](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/).
