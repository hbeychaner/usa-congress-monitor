# Visual atlas

Generated from the `.mmd` sources by `uv run python tools/build_documentation.py`.
The diagrams describe implementation boundaries, not measured production
coverage. C4 context, containers, and components are different zoom levels.

## backend-components

[Editable Mermaid source](../diagrams/backend-components.mmd)

```mermaid
---
title: Congress Tracker - C4 level 3 serving components
config:
  flowchart:
    curve: linear
    nodeSpacing: 55
    rankSpacing: 100
---
flowchart LR
    pages["Web: React routes and pages<br/>Entities / search / graphs / admin"]
    wrappers["Web: handwritten API wrappers<br/>Shared apiGet / apiPost"]
    types["Web: OpenAPI schema types<br/>Generated; partially adopted by wrappers"]
    routes["API: typed route handlers<br/>Request validation / dependency declarations"]
    providers["API: dependency providers<br/>Container composition and cached services"]
    query["API: entity and search services<br/>Bills / members / committees / states / votes"]
    analysis["API: analysis query services<br/>Topics / perspectives / graphs / neighborhoods"]
    admin["API: admin services and launchers<br/>Jobs / coverage / local rebuild controls"]
    contracts["API: Pydantic response contracts"]
    es[("Elasticsearch<br/>Entity aliases and analysis indices")]
    jobs[("SQLite job ledger")]
    tasks["Celery task dispatch"]
    local[("Local status / artifacts / subprocesses")]

    pages --> wrappers
    types -.-> wrappers
    wrappers -->|"HTTP / JSON"| routes
    providers -.->|"Injects collaborators"| routes
    routes --> query
    routes --> analysis
    routes --> admin
    query --> es
    analysis --> es
    query -.-> contracts
    analysis -.-> contracts
    admin --> jobs
    admin --> tasks
    admin --> local

    classDef component fill:#e4f0fb,stroke:#1168bd,color:#172b4d
    class pages,wrappers,types,routes,providers,query,analysis,admin,contracts component
```

## bill-request-sequence

[Editable Mermaid source](../diagrams/bill-request-sequence.mmd)

```mermaid
sequenceDiagram
    title Opening a bill - request path and failure behavior
    actor Reader
    participant Page as BillDetailPage
    participant Client as fetchBill / apiGet
    participant Route as bills.bill_detail
    participant DI as BillServiceDep / get_bill_service
    participant Container as Container.bill_service
    participant Service as BillService.get
    participant ES as congress-legislation-read
    Reader->>Page: Open bill detail route
    Page->>Client: fetchBill(canonical ID)
    Client->>Route: GET /api/v1/bills/{bill_id}
    Route->>DI: Resolve service dependency
    DI->>Container: Obtain cached service
    Container-->>DI: Injected BillService
    DI-->>Route: BillService
    Route->>Service: get(trimmed ID)
    Service->>ES: Get exact canonical document
    alt Bill document found
        ES-->>Service: Source document
        Service-->>Route: Typed bill response
        Route-->>Client: Serialized response
        Client-->>Page: Bill data
        Page-->>Reader: Render details and tabs
    else Missing document or non-bill input
        ES-->>Service: Missing result or mismatched document
        Note over Service,Route: Missing-document / ValueError is not explicitly mapped to 404
        Route-->>Client: Request fails
        Client-->>Page: Shared HTTP error handling
    end
```

## data-model

[Editable Mermaid source](../diagrams/data-model.mmd)

```mermaid
---
title: Logical record identities and query joins
config:
  flowchart:
    curve: linear
    nodeSpacing: 65
    rankSpacing: 100
---
flowchart LR
    bill["Legislation<br/>bill:congress:type:number<br/>Bill sources converge; parent holds full text"]
    member["Member<br/>member:bioguide_id<br/>Relationships use bare Bioguide IDs"]
    amendment["Amendment<br/>amendment:congress:type:number<br/>Bill components retained; flattened ID not guaranteed"]
    house["Congress.gov House vote<br/>house-rollcall-vote:congress:session:roll<br/>Fallback identifier-based ID"]
    rollcall["Voteview rollcall<br/>rollcall:congress:chamber:roll_number<br/>Position arrays contain bare Bioguide IDs"]
    assignment["Bill assignment<br/>assignment:model_version:doc_id"]
    topic["Topic<br/>topic:model_version:topic_id"]
    meta["Metasubject<br/>metasubject:model_version:metasubject_id"]
    perspective["Party-topic analysis<br/>party_topic:model_version:congress:topic_id"]
    edge["Graph edge<br/>edge:graph_version:signal:member:neighbor<br/>Signal pointer chooses active graph version"]
    committee["Committee<br/>system_code identity<br/>Bill documents contain nested committee references"]

    amendment -->|"Amended bill congress / type / number"| bill
    house -->|"Congress + upper-case legislation type + number"| bill
    rollcall -->|"legislation_id when resolved"| bill
    bill -->|"Sponsor / cosponsor Bioguide arrays"| member
    rollcall -->|"Yea / nay / present / absent arrays"| member
    assignment -->|"doc_id"| bill
    assignment -->|"Model version + topic_id"| topic
    assignment -->|"Model version + metasubject_id"| meta
    meta -->|"topic_ids within the same model"| topic
    perspective -->|"Model version + topic_id"| topic
    edge -->|"Bare member and neighbor IDs"| member
    bill -->|"Nested committees.system_code"| committee

    classDef entity fill:#e4f0fb,stroke:#1168bd,color:#172b4d
    classDef derived fill:#eef6e8,stroke:#548235,color:#203615
    class bill,member,amendment,house,rollcall,committee entity
    class assignment,topic,meta,perspective,edge derived
```

## deployment

[Editable Mermaid source](../diagrams/deployment.mmd)

```mermaid
flowchart TB
    browser["Browser"]

    subgraph local["Local - controlled Compose runtime"]
        vite["React / Vite :5173"]
        fastapi["FastAPI :8000"]
        operations["Celery operations worker<br/>Index + maintenance queues / one slot"]
        infra["Retained Docker infrastructure<br/>Elasticsearch, RabbitMQ, Redis"]
        disk[("Repository data / models / logs")]
        optins["Off by default<br/>Acquisition / analytics / Beat / Kibana"]
        vite --> fastapi
        fastapi --> infra
        operations --> infra
        operations --> disk
        fastapi --> disk
        operations -.->|"Separate profile approval"| optins
    end

    subgraph cloud["GCP design - not certified by local acceptance"]
        lb["HTTPS load balancer + IAP"]
        fe["Cloud Run frontend<br/>nginx static assets"]
        api["Cloud Run API<br/>private VPC access"]
        subgraph vpc["Private VPC"]
            worker["Worker VM<br/>Celery, Beat, RabbitMQ, Redis"]
            search["Search VM<br/>Elasticsearch"]
            wd[("Persistent worker disk<br/>data, logs, models, Docker volumes")]
            sd[("Persistent search disk")]
            worker --> wd
            worker --> search
            search --> sd
        end
        lb -->|"default path"| fe
        lb -->|"/api/* and API documentation"| api
        api --> worker
        api --> search
        limitation["Worker-local files are NOT mounted on Cloud Run.<br/>File-backed admin status/builds need deployment-aware handling."]
        api -.-> limitation
        wd -.-> limitation
    end

    browser -->|"local option"| vite
    browser -->|"cloud option"| lb
```

## ingest-dataflow

[Editable Mermaid source](../diagrams/ingest-dataflow.mmd)

```mermaid
---
title: Acquisition, indexing, replay and serving data flow
config:
  flowchart:
    curve: linear
    nodeSpacing: 50
    rankSpacing: 100
---
flowchart TB
    plan["Operator planning / Celery schedules"]
    ledger[("SQLite JobStore<br/>Deterministic identity / attempts / coverage")]
    broker["RabbitMQ task delivery"]
    api["Congress.gov pipeline<br/>List pages then item hydration"]
    bulk["GovInfo runner<br/>Download and parse packages<br/>Locally paced requests"]
    archive[("SQLite archives and manifests<br/>Persist BEFORE stream publication")]
    library[("Optional retained record library")]
    stream[("Redis Streams<br/>Bounded retention / pending consumers")]
    project["to_document and mapping validation<br/>Canonical IDs / resource routing / lemmas"]
    write["Bounded bulk writes<br/>Bill null-safe merge<br/>Default bill_text updates parent"]
    ack["Acknowledge buffered stream entries<br/>ONLY when the entire bulk reports no errors"]
    es[("Elasticsearch projections")]
    serve["FastAPI services then React pages"]
    replay["Archive replay / reconciliation<br/>Replacement mode differs from merge mode"]
    voteview["Voteview CLI import<br/>Typed CSV / rollcall aggregation"]
    analysis["Offline analytics builds<br/>Embeddings / topics / perspectives / graphs"]
    quarantine[("Preserved invalid/corrupt acquisition artifacts")]

    plan --> ledger
    ledger --> broker
    broker --> api
    broker --> bulk
    api --> archive
    bulk --> archive
    archive -->|"Then publish normalized records"| stream
    api -.->|"When requested"| library
    archive -.->|"Preserve invalid inputs"| quarantine
    stream --> project
    project --> write
    write -->|"Write actions; partial success is possible"| es
    write -->|"Whole-buffer success"| ack
    archive -->|"Expected-count fallback or explicit replay"| replay
    replay --> es
    voteview -->|"Direct rollcall replacements; bypasses streams"| es
    es --> serve
    es --> analysis

    classDef state fill:#e4f0fb,stroke:#1168bd,color:#172b4d
    class ledger,archive,library,stream,es,quarantine state
```

## system-context

[Editable Mermaid source](../diagrams/system-context.mmd)

```mermaid
---
title: Congress Tracker - C4 level 1 system context
config:
  flowchart:
    curve: linear
    nodeSpacing: 65
    rankSpacing: 100
---
flowchart LR
    reader["Reader<br/>Person<br/>Explores legislation and analysis"]
    operator["Operator<br/>Person<br/>Plans work and checks coverage"]
    tracker["Congress Tracker<br/>Software system<br/>Acquires, indexes and serves legislative data"]
    congress["Congress.gov API<br/>External system<br/>Metadata and supporting resources"]
    govinfo["GovInfo<br/>External system<br/>Bill metadata, summaries and text"]
    voteview["Voteview<br/>External system<br/>Roll calls and member positions"]
    ollama["Ollama<br/>External system<br/>Optional labels and summaries"]

    reader -->|"Explores through web UI"| tracker
    operator -->|"Submits work / checks status"| tracker
    tracker -->|"Collects JSON over HTTPS"| congress
    tracker -->|"Downloads XML over HTTPS"| govinfo
    tracker -->|"Imports CSV over HTTPS"| voteview
    tracker -->|"Requests optional labels"| ollama

    classDef person fill:#e8eef5,stroke:#42566e,color:#172b4d
    classDef system fill:#1168bd,stroke:#08427b,color:#ffffff
    classDef external fill:#f3f4f6,stroke:#667085,color:#202939
    class reader,operator person
    class tracker system
    class congress,govinfo,voteview,ollama external
```

## worker-architecture

[Editable Mermaid source](../../worker-architecture.mmd)

```mermaid
---
title: Congress Tracker - C4 level 2 applications and stores
config:
  flowchart:
    curve: linear
    nodeSpacing: 55
    rankSpacing: 100
---
flowchart LR
    reader["Reader<br/>Person"]
    operator["Operator<br/>Person"]
    sources["Congress.gov / GovInfo<br/>External data sources"]
    voteview["Voteview<br/>External voting datasets"]
    web["Web application<br/>React / TypeScript"]
    api["API application<br/>FastAPI / Python"]
    cli["Operator commands<br/>Python CLIs and analytics builds"]
    beat["Scheduler capability<br/>Celery Beat / opt-in profile"]
    workers["Worker applications<br/>Controlled: index + maintenance<br/>Opt-in: ingest / bulk / analytics"]
    broker[("RabbitMQ<br/>Task delivery")]
    ledger[("SQLite job ledger<br/>Identity / lifecycle / coverage")]
    archives[("SQLite acquisition state<br/>Archives / manifests / record library")]
    redis[("Redis<br/>Streams and coordination")]
    search[("Elasticsearch<br/>Entities / votes / embeddings / analysis")]
    files[("Local files<br/>Model artifacts / logs")]

    reader --> web
    web -->|"HTTP / JSON"| api
    operator --> cli
    api -->|"Read projections"| search
    api -->|"Admin job state"| ledger
    api -->|"Admin task submission"| broker
    cli -->|"Record jobs"| ledger
    cli -->|"Publish tasks"| broker
    cli -->|"Vote imports / analysis"| search
    cli -->|"Build artifacts"| files
    voteview --> cli
    beat -->|"Scheduled tasks"| broker
    broker -->|"Deliver"| workers
    sources -->|"Fetch and hydrate"| workers
    workers -->|"Lifecycle / coverage"| ledger
    workers -->|"Persist replay source"| archives
    workers -->|"Publish / consume / acknowledge"| redis
    workers -->|"Validated bulk writes"| search

    classDef app fill:#1168bd,stroke:#08427b,color:#ffffff
    classDef store fill:#e4f0fb,stroke:#1168bd,color:#172b4d
    class web,api,cli,beat,workers app
    class broker,ledger,archives,redis,search,files store
```
