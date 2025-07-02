<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# ZMQ Proxy Types

## ZMQ DEALER<->ROUTER Proxy

> [!TIP]
> Use when you need to load balance client requests across multiple services and require responses back to the original clients.

The proxy acts as an intermediary that enables many-to-many communication between `DEALER` clients and `ROUTER` services while maintaining proper message routing.

```mermaid
graph LR
    subgraph "Client Side"
        C1["DEALER Client 1"]
        C2["DEALER Client 2"]
        C3["DEALER Client N"]
    end

    subgraph "ZMQ DEALER-ROUTER Proxy"
        FE["Frontend<br/>ROUTER Socket<br/>(Proxy Frontend)"]
        BE["Backend<br/>DEALER Socket<br/>(Proxy Backend)"]
        FE -.-> BE
    end

    subgraph "Service Side"
        S1["ROUTER Service 1"]
        S2["ROUTER Service 2"]
        S3["ROUTER Service N"]
    end

    C1 --> FE
    C2 --> FE
    C3 --> FE

    BE --> S1
    BE --> S2
    BE --> S3

    classDef client fill:#4fc3f7,stroke:#01579b,stroke-width:2px,color:#000000
    classDef proxy fill:#ba68c8,stroke:#4a148c,stroke-width:2px,color:#000000
    classDef service fill:#81c784,stroke:#1b5e20,stroke-width:2px,color:#000000
    classDef subgraphStyle fill:#2d2d2d,stroke:#666666,color:#ffffff

    class C1,C2,C3 client
    class FE,BE proxy
    class S1,S2,S3 service
```
### Key Components
1. **`DEALER` Clients** (left side): Multiple clients that send requests using `DEALER` sockets
2. **Proxy Frontend** (`ROUTER` socket): Receives and queues messages from all `DEALER` clients
3. **Proxy Backend** (`DEALER` socket): Forwards messages to available `ROUTER` services (note: no identity for transparency as mentioned in the code comments)
4. **`ROUTER` Services** (right side): Multiple service instances that process requests

### Message Flow
- Requests flow left-to-right: `DEALER` clients → Frontend `ROUTER` → Backend `DEALER` → `ROUTER` services
- Responses flow right-to-left automatically through the same path
- The ZMQ proxy handles automatic load balancing and routing envelope preservation

### Benefits
- **Load Balancing**: Distributes requests across multiple services
- **Decoupling**: Clients don't need to know about individual service addresses
- **Scalability**: Services can be added/removed without client changes
- **Automatic Routing**: ZMQ handles request/response correlation automatically


## ZMQ PUSH->PULL Proxy

> [!TIP]
> Use when you need to distribute work items from multiple producers to multiple workers in a fire-and-forget manner without needing responses.

```mermaid
graph LR
    subgraph "Worker Side"
        W1["Worker 1<br/>(PUSH)"]
        W2["Worker 2<br/>(PUSH)"]
        W3["Worker N<br/>(PUSH)"]
    end

    subgraph "ZMQ PUSH-PULL Proxy"
        FE["Frontend<br/>PULL Socket<br/>(Receives Results)"]
        BE["Backend<br/>PUSH Socket<br/>(Distributes Results)"]
        FE -.-> BE
    end

    subgraph "Parser Side"
        P1["Inference Result<br/>Parser Service 1<br/>(PULL)"]
        P2["Inference Result<br/>Parser Service 2<br/>(PULL)"]
        P3["Inference Result<br/>Parser Service N<br/>(PULL)"]
    end

    W1 --> FE
    W2 --> FE
    W3 --> FE

    BE --> P1
    BE --> P2
    BE --> P3

    classDef worker fill:#ffb74d,stroke:#e65100,stroke-width:2px,color:#000000
    classDef proxy fill:#ba68c8,stroke:#4a148c,stroke-width:2px,color:#000000
    classDef parser fill:#4db6ac,stroke:#00695c,stroke-width:2px,color:#000000

    class W1,W2,W3 worker
    class FE,BE proxy
    class P1,P2,P3 parser
```

### Message Flow
- **Workers** (left) generate and send inference results using `PUSH` sockets
- **Proxy Frontend** (`PULL` socket) receives all inference results from workers
- **Proxy Backend** (`PUSH` socket) distributes results to available parser services
- **Inference Result Parser Services** (right) consume and process the results using `PULL` sockets

### Key Benefits
- **Load Balancing**: Inference results are automatically distributed across multiple parser services
- **Decoupling**: Workers don't need to know about specific parser services
- **Scalability**: You can add/remove parser services without affecting workers
- **Efficiency**: Fire-and-forget messaging ensures workers aren't blocked waiting for processing


## XPUB -> XSUB Proxy

> [!TIP]
> Use when you need to broadcast topic-based messages from multiple publishers to multiple subscribers with automatic subscription filtering.


```mermaid
graph LR
    subgraph "Publisher Side"
        P1["PUB Publisher 1<br/>(Metrics)"]
        P2["PUB Publisher 2<br/>(Events)"]
        P3["PUB Publisher N<br/>(Logs)"]
    end

    subgraph "ZMQ XPUB-XSUB Proxy"
        FE["Frontend<br/>XSUB Socket<br/>(Receives Publications)"]
        BE["Backend<br/>XPUB Socket<br/>(Broadcasts Topics)"]
        FE -.-> BE
    end

    subgraph "Subscriber Side"
        S1["SUB Subscriber 1<br/>(Metrics Filter)"]
        S2["SUB Subscriber 2<br/>(Events Filter)"]
        S3["SUB Subscriber N<br/>(All Topics)"]
    end

    P1 --> FE
    P2 --> FE
    P3 --> FE

    BE --> S1
    BE --> S2
    BE --> S3

    classDef publisher fill:#ff8a65,stroke:#bf360c,stroke-width:2px,color:#000000
    classDef proxy fill:#ba68c8,stroke:#4a148c,stroke-width:2px,color:#000000
    classDef subscriber fill:#64b5f6,stroke:#0d47a1,stroke-width:2px,color:#000000

    class P1,P2,P3 publisher
    class FE,BE proxy
    class S1,S2,S3 subscriber
```

### Key Components
1. **`PUB` Publishers** (left side): Multiple publishers that broadcast messages on different topics (Metrics, Events, Logs, etc.)
2. **Proxy Frontend** (`XSUB` socket): Receives all publications from publishers and manages subscriptions
3. **Proxy Backend** (`XPUB` socket): Broadcasts messages to subscribers based on their topic filters
4. **`SUB` Subscribers** (right side): Multiple subscribers that filter and receive only the topics they're interested in

### Message Flow
- **One-to-Many Broadcasting**: Publishers send to all interested subscribers
- **Topic-Based Filtering**: Subscribers only receive messages matching their filter criteria
- **Subscription Management**: The proxy handles subscription requests automatically

### Key Benefits
- **Topic Filtering**: Subscribers only get relevant messages
- **Decoupling**: Publishers don't need to know about subscribers
- **Scalability**: Add publishers/subscribers without affecting others
- **Efficiency**: Only subscribed-to messages are delivered to each subscriber

### Use Cases
- **Metrics Broadcasting**: Performance metrics to monitoring dashboards
- **Event Notifications**: System events to multiple logging/alerting services
- **Real-time Updates**: Live inference results to multiple visualization tools
- **System Monitoring**: Health status updates to various monitoring components

### Simplifies Many-to-Many Communication

#### Without XPUB-XSUB Proxy (Traditional Approach)
- Each publisher would need individual connections to every subscriber
- Publishers must know all subscriber addresses
- Adding/removing participants requires reconfiguring everyone
- Complex subscription management across multiple connections

#### With XPUB-XSUB Proxy (Simplified Approach)
- All publishers connect to ONE proxy frontend
- All subscribers connect to ONE proxy backend
- Publishers and subscribers are completely decoupled
- Single point of subscription management
