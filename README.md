flowchart TB
    subgraph ref["Reference Anchors"]
        CR["**congress_ref**\nid: congress:{N}"]
        MEM["**member**\nid: member:{bioguide_id}"]
    end

    subgraph leg["Legislative"]
        LEG["**legislation**\nid: bill:{congress}:{type}:{number}"]
        AMD["**amendment**\nid: amendment:{congress}:{type}:{number}"]
        HV["**house_vote**\nid: house-rollcall-vote:{congress}:{session}:{roll}"]
        CREC["**congressional_record**\nrecord_subtype: bound|daily"]
    end

    subgraph com["Committee"]
        COM["**committee**\nid: committee:{chamber}:{system_code}"]
        CMTG["**committee_meeting**"]
        CPRT["**committee_print**"]
        CRPT["**committee_report**"]
        HRG["**hearing**"]
    end

    subgraph exec["Executive / Other"]
        NOM["**nomination**"]
        TRE["**treaty**"]
        COMM["**communication**\nchamber: House|Senate"]
        HREQ["**house_requirement**"]
    end

    %% ── congress → congress_ref (shared by almost everything) ──────────────
    LEG  -->|"congress (int)"| CR
    AMD  -->|"congress (int)"| CR
    HV   -->|"congress (int)"| CR
    CREC -->|"congress (int)"| CR
    COM  -->|"congress (int)"| CR
    CMTG -->|"congress (int)"| CR
    CPRT -->|"congress (int)"| CR
    CRPT -->|"congress (int)"| CR
    HRG  -->|"congress (int)"| CR
    NOM  -->|"congress (int)"| CR
    TRE  -->|"congress_received (int)"| CR
    COMM -->|"congress (int)"| CR

    %% ── legislation is the hub ──────────────────────────────────────────────
    AMD  -->|"amended_bill_id = legislation.id"| LEG
    HV   -->|"legislation_id = legislation.id"| LEG
    CRPT -.->|"bill ref (item-level only)"| LEG

    %% ── member links ────────────────────────────────────────────────────────
    AMD  -->|"sponsor_bioguide_id = member.bioguide_id"| MEM
    LEG  -.->|"sponsors / cosponsors (item-level only)"| MEM
    NOM  -.->|"nominees (item-level only)"| MEM

    %% ── committee is a second hub ───────────────────────────────────────────
    COM  -->|"parent_system_code → system_code (self-join)"| COM
    CMTG -.->|"system_code (item-level only)"| COM
    CPRT -.->|"system_code (item-level only)"| COM
    CRPT -.->|"system_code (item-level only)"| COM
    HRG  -.->|"system_code (item-level only)"| COM

    %% ── amendment voted on ──────────────────────────────────────────────────
    HV   -->|"amendment_type + amendment_number"| AMD