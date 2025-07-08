<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# ZMQ Socket Types

> [!TIP]
> See [ZMQ Proxies Documentation](zmq-proxies.md) for information on ZMQ Proxies

## **DEALER Socket**
```mermaid
graph LR
    subgraph "DEALER Socket Pattern"
        C["Client Application"]
        D["DEALER Socket<br/>(Asynchronous Client)"]
        S1["Service 1"]
        S2["Service 2"]
        S3["Service N"]

        C --> D
        D --> S1
        D --> S2
        D --> S3

        S1 -.-> D
        S2 -.-> D
        S3 -.-> D
        D -.-> C
    end

    classDef client fill:#4fc3f7,stroke:#01579b,stroke-width:2px,color:#000000
    classDef socket fill:#ba68c8,stroke:#4a148c,stroke-width:2px,color:#000000
    classDef service fill:#81c784,stroke:#1b5e20,stroke-width:2px,color:#000000

    class C client
    class D socket
    class S1,S2,S3 service
```

Asynchronous client that load balances requests across multiple services
- Sends requests to available services in round-robin fashion
- Can handle multiple concurrent requests without blocking
- Each request gets routed to the next available service

## **ROUTER Socket**
```mermaid
graph LR
    subgraph "ROUTER Socket Pattern"
        C1["Client 1"]
        C2["Client 2"]
        C3["Client N"]
        R["ROUTER Socket<br/>(Asynchronous Server)"]
        A["Service Application"]

        C1 --> R
        C2 --> R
        C3 --> R
        R --> A

        A -.-> R
        R -.-> C1
        R -.-> C2
        R -.-> C3
    end

    classDef client fill:#4fc3f7,stroke:#01579b,stroke-width:2px,color:#000000
    classDef socket fill:#ba68c8,stroke:#4a148c,stroke-width:2px,color:#000000
    classDef service fill:#81c784,stroke:#1b5e20,stroke-width:2px,color:#000000

    class C1,C2,C3 client
    class R socket
    class A service
```

Asynchronous server that receives requests from multiple clients
- Routes incoming requests to the application for processing
- Maintains client identity for proper response routing
- Can handle multiple concurrent clients simultaneously

## **PUSH Socket**
```mermaid
graph LR
    subgraph "ROUTER Socket Pattern"
        C1["Client 1"]
        C2["Client 2"]
        C3["Client N"]
        R["ROUTER Socket<br/>(Asynchronous Server)"]
        A["Service Application"]

        C1 --> R
        C2 --> R
        C3 --> R
        R --> A

        A -.-> R
        R -.-> C1
        R -.-> C2
        R -.-> C3
    end

    classDef client fill:#4fc3f7,stroke:#01579b,stroke-width:2px,color:#000000
    classDef socket fill:#ba68c8,stroke:#4a148c,stroke-width:2px,color:#000000
    classDef service fill:#81c784,stroke:#1b5e20,stroke-width:2px,color:#000000

    class C1,C2,C3 client
    class R socket
    class A service
```
Work distributor that sends tasks to workers (fire-and-forget)
- Distributes work items to available workers in round-robin
- No responses expected - pure fire-and-forget messaging
- Ideal for distributing computational work

## **PULL Socket**
```mermaid
graph LR
    subgraph "PULL Socket Pattern"
        P1["Producer 1"]
        P2["Producer 2"]
        P3["Producer N"]
        PL["PULL Socket<br/>(Work Receiver)"]
        A["Worker Application"]

        P1 --> PL
        P2 --> PL
        P3 --> PL
        PL --> A
    end

    classDef producer fill:#ffb74d,stroke:#e65100,stroke-width:2px,color:#000000
    classDef socket fill:#ba68c8,stroke:#4a148c,stroke-width:2px,color:#000000
    classDef app fill:#4db6ac,stroke:#00695c,stroke-width:2px,color:#000000

    class P1,P2,P3 producer
    class PL socket
    class A app
```
Work receiver that accepts tasks from producers
- Receives work items from multiple producers fairly
- Processes work without sending responses back
- Perfect for worker processes in pipeline architectures

## **PUB Socket**
```mermaid
graph LR
    subgraph "PUB Socket Pattern"
        A["Publisher Application"]
        P["PUB Socket<br/>(Message Broadcaster)"]
        S1["Subscriber 1<br/>(Topic A)"]
        S2["Subscriber 2<br/>(Topic B)"]
        S3["Subscriber N<br/>(All Topics)"]

        A --> P
        P --> S1
        P --> S2
        P --> S3
    end

    classDef app fill:#ff8a65,stroke:#bf360c,stroke-width:2px,color:#000000
    classDef socket fill:#ba68c8,stroke:#4a148c,stroke-width:2px,color:#000000
    classDef subscriber fill:#64b5f6,stroke:#0d47a1,stroke-width:2px,color:#000000

    class A app
    class P socket
    class S1,S2,S3 subscriber
```
Message broadcaster that publishes to subscribers
- Sends messages to all connected subscribers
- Subscribers filter messages based on topics
- One-way communication (no responses)

## **SUB Socket**
```mermaid
graph LR
    subgraph "SUB Socket Pattern"
        P1["Publisher 1<br/>(Metrics)"]
        P2["Publisher 2<br/>(Events)"]
        P3["Publisher N<br/>(Logs)"]
        S["SUB Socket<br/>(Filtered Receiver)"]
        A["Subscriber Application"]

        P1 --> S
        P2 --> S
        P3 --> S
        S --> A
    end

    classDef publisher fill:#ff8a65,stroke:#bf360c,stroke-width:2px,color:#000000
    classDef socket fill:#ba68c8,stroke:#4a148c,stroke-width:2px,color:#000000
    classDef app fill:#64b5f6,stroke:#0d47a1,stroke-width:2px,color:#000000

    class P1,P2,P3 publisher
    class S socket
    class A app
```
Message receiver with topic filtering
- Connects to publishers and filters desired topics
- Only receives messages matching subscription filters
- Passive receiver (cannot send messages back)

## **XPUB Socket**
```mermaid
graph LR
    subgraph "XPUB Socket Pattern"
        A["Publisher Application"]
        X["XPUB Socket<br/>(Extended Publisher)"]
        S1["SUB Socket 1"]
        S2["SUB Socket 2"]
        S3["SUB Socket N"]

        A --> X
        X --> S1
        X --> S2
        X --> S3

        S1 -.->|"Subscription<br/>Requests"| X
        S2 -.->|"Subscription<br/>Requests"| X
        S3 -.->|"Subscription<br/>Requests"| X
    end

    classDef app fill:#ff8a65,stroke:#bf360c,stroke-width:2px,color:#000000
    classDef socket fill:#ba68c8,stroke:#4a148c,stroke-width:2px,color:#000000
    classDef subscriber fill:#64b5f6,stroke:#0d47a1,stroke-width:2px,color:#000000

    class A app
    class X socket
    class S1,S2,S3 subscriber
```

Extended publisher with subscription awareness
- Like `PUB` but can receive subscription requests
- Forwards subscription messages upstream
- Used primarily in proxy configurations

## **XSUB Socket**
```mermaid
graph LR
    subgraph "XSUB Socket Pattern"
        P1["PUB Socket 1"]
        P2["PUB Socket 2"]
        P3["PUB Socket N"]
        X["XSUB Socket<br/>(Extended Subscriber)"]
        A["Subscriber Application"]

        P1 --> X
        P2 --> X
        P3 --> X
        X --> A

        A -.->|"Subscription<br/>Management"| X
        X -.->|"Subscription<br/>Requests"| P1
        X -.->|"Subscription<br/>Requests"| P2
        X -.->|"Subscription<br/>Requests"| P3
    end

    classDef publisher fill:#ff8a65,stroke:#bf360c,stroke-width:2px,color:#000000
    classDef socket fill:#ba68c8,stroke:#4a148c,stroke-width:2px,color:#000000
    classDef app fill:#64b5f6,stroke:#0d47a1,stroke-width:2px,color:#000000

    class P1,P2,P3 publisher
    class X socket
    class A app
```
Extended subscriber for proxy scenarios
- Like `SUB` but can forward subscription requests
- Manages subscription state for downstream subscribers
- Used primarily as proxy frontend for pub/sub patterns

