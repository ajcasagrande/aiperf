<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
-->
```mermaid
graph TD
    subgraph "DEALER-ROUTER Broker (Proxy)"
        R["Frontend ROUTER Socket<br/>(binds to frontend_address)<br/>Default: tcp://0.0.0.0:5564"]
        D["Backend DEALER Socket<br/>(binds to backend_address)<br/>Default: tcp://0.0.0.0:5565"]
        P["ZMQ Proxy<br/>(forwards messages bidirectionally)"]
        R <--> P
        P <--> D
    end

    subgraph "DEALER Clients"
        DC1["DEALER Client 1<br/>(connects to frontend_address)"]
        DC2["DEALER Client 2<br/>(connects to frontend_address)"]
        DC3["DEALER Client N<br/>(connects to frontend_address)"]
    end

    subgraph "ROUTER Services"
        RS1["ROUTER Service 1<br/>(connects to backend_address)"]
        RS2["ROUTER Service 2<br/>(connects to backend_address)"]
        RS3["ROUTER Service N<br/>(connects to backend_address)"]
    end

    DC1 --> R
    DC2 --> R
    DC3 --> R

    D --> RS1
    D --> RS2
    D --> RS3

    style R fill:#e1f5fe
    style D fill:#fff3e0
    style P fill:#f3e5f5
    style DC1 fill:#e8f5e8
    style DC2 fill:#e8f5e8
    style DC3 fill:#e8f5e8
    style RS1 fill:#fff8e1
    style RS2 fill:#fff8e1
    style RS3 fill:#fff8e1
```

## Architecture Overview

The DEALER-ROUTER broker acts as a proxy that forwards messages between multiple DEALER clients and multiple ROUTER services.

### Connection Details

**Frontend (ROUTER socket):**
- Binds to `frontend_address` (config: `router_address`)
- Default: `tcp://0.0.0.0:5564`
- Receives connections from DEALER clients
- Handles load balancing and routing to backend

**Backend (DEALER socket):**
- Binds to `backend_address` (config: `dealer_address`)
- Default: `tcp://0.0.0.0:5565`
- Connects to ROUTER services
- Forwards messages from frontend to services

### Message Flow

1. **Request Flow:**
   ```
   DEALER Client → frontend_address → Frontend ROUTER → Proxy → Backend DEALER → backend_address → ROUTER Service
   ```

2. **Response Flow:**
   ```
   ROUTER Service → backend_address → Backend DEALER → Proxy → Frontend ROUTER → frontend_address → DEALER Client
   ```

### Configuration

The broker uses `ZMQTCPDealerRouterBrokerConfig`:
- `router_port: 5564` - Frontend port for DEALER clients
- `dealer_port: 5565` - Backend port for ROUTER services
- `host: "0.0.0.0"` - Bind address

### Key Benefits

- **Load Balancing:** Multiple DEALER clients can connect to the same services
- **Service Discovery:** Clients don't need to know specific service addresses
- **Fault Tolerance:** Services can be added/removed without affecting clients
- **Scalability:** Easy to add more clients or services without reconfiguration
