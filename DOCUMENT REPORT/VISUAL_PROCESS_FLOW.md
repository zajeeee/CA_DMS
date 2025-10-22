# Document Management System - Visual Process Flow

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           DOCUMENT MANAGEMENT SYSTEM                            │
│                              Flask Web Application                             │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## User Roles and Access Levels

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│    ADMIN    │    │ RECEIVING1  │    │ RECEIVING2  │    │    DOCS     │    │  RELEASING  │
│             │    │             │    │             │    │             │    │             │
│ • Full      │    │ • Document  │    │ • Email     │    │ • GSO Docs  │    │ • Outgoing  │
│   Access    │    │   Intake    │    │   Processing│    │ • Travel    │    │   Docs      │
│ • User Mgmt │    │ • Initial   │    │ • RTS Mgmt  │    │ • Leave     │    │ • Release   │
│ • Monitoring│    │   Processing│    │ • Acceptance│    │ • Permits   │    │   Tracking │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

## Document Flow Process

### Phase 1: Document Intake (Receiving1)
```
External Document
        │
        ▼
┌─────────────────┐
│   RECEIVING1     │
│                  │
│ • Upload File    │
│ • Enter Metadata │
│ • Assign Control │
│ • Set Source     │
│ • Add Particulars│
└─────────────────┘
        │
        ▼
┌─────────────────┐
│   DATABASE      │
│                  │
│ • Store File     │
│ • Save Metadata  │
│ • Create Record  │
│ • Generate Hash  │
└─────────────────┘
```

### Phase 2: Document Routing Decision
```
┌─────────────────┐
│   ROUTING        │
│   DECISION       │
└─────────────────┘
        │
        ├─── Other Documents ────► RECEIVING2
        │
        ├─── Specialized Docs ──► DOCS
        │
        └─── Outgoing Docs ─────► RELEASING
```

### Phase 3: Secondary Processing (Receiving2)
```
┌─────────────────┐
│   RECEIVING2     │
│                  │
│ • Email Docs     │
│ • Document       │
│   Acceptance     │
│ • RTS Management │
│ • Attachment     │
│   Processing     │
└─────────────────┘
        │
        ▼
┌─────────────────┐
│   FINAL          │
│   ROUTING        │
└─────────────────┘
```

### Phase 4: Specialized Document Management (Docs)
```
┌─────────────────┐
│      DOCS        │
│                  │
│ ┌─────────────┐  │
│ │ GSO Docs    │  │
│ │ • Suppliers │  │
│ │ • Amounts   │  │
│ │ • Offices   │  │
│ └─────────────┘  │
│                  │
│ ┌─────────────┐  │
│ │ Travel Docs │  │
│ │ • Travelers │  │
│ │ • Destinations│ │
│ │ • Dates     │  │
│ └─────────────┘  │
│                  │
│ ┌─────────────┐  │
│ │ Leave Apps  │  │
│ │ • Types     │  │
│ │ • Employees │  │
│ │ • Dates     │  │
│ └─────────────┘  │
│                  │
│ ┌─────────────┐  │
│ │ Permits     │  │
│ │ • Types     │  │
│ │ • Purposes  │  │
│ │ • Duration  │  │
│ └─────────────┘  │
└─────────────────┘
```

### Phase 5: Document Release (Releasing)
```
┌─────────────────┐
│   RELEASING      │
│                  │
│ • Outgoing Docs  │
│ • Release        │
│   Tracking       │
│ • Dispatch       │
│ • Statistics     │
└─────────────────┘
```

## Database Architecture

### Core Tables Structure
```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              DATABASE SCHEMA                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐          │
│  │     USERS       │    │ RECEIVING1_DOCS │    │ RECEIVING2_DOCS │          │
│  │                 │    │                 │    │                 │          │
│  │ • id            │    │ • id            │    │ • id            │          │
│  │ • username      │    │ • date_received │    │ • original_id   │          │
│  │ • password_hash │    │ • time_received │    │ • date_received │          │
│  │ • role          │    │ • control_no    │    │ • control_no    │          │
│  │ • last_seen     │    │ • source        │    │ • source        │          │
│  │ • created_at    │    │ • particulars   │    │ • purposes      │          │
│  └─────────────────┘    │ • document_blob │    │ • remarks       │          │
│                          │ • created_at   │    │ • document_blob │          │
│                          └─────────────────┘    └─────────────────┘          │
│                                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐          │
│  │ OTHER_DOCS      │    │ OUTGOING_DOCS   │    │ ACCEPTED_DOCS   │          │
│  │                 │    │                 │    │                 │          │
│  │ • id            │    │ • id            │    │ • id            │          │
│  │ • date_received │    │ • date_sent     │    │ • original_id   │          │
│  │ • control_no    │    │ • time_sent     │    │ • date_accepted │          │
│  │ • source        │    │ • control_no    │    │ • accepted_by   │          │
│  │ • purpose_action│    │ • source        │    │ • purposes      │          │
│  │ • document_blob │    │ • document_blob │    │ • document_blob │          │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘          │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Specialized Document Tables
```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        SPECIALIZED DOCUMENT TABLES                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐          │
│  │   GSO_DOCS      │    │ TRAVEL_DOCS     │    │ LEAVE_DOCS      │          │
│  │                 │    │                 │    │                 │          │
│  │ • supplier_name │    │ • traveler_name │    │ • control_no    │          │
│  │ • office        │    │ • date          │    │ • applicant_name│          │
│  │ • amount        │    │ • destination   │    │ • leave_type    │          │
│  │ • forwarded_to  │    │ • forwarded_to  │    │ • inclusive_date│          │
│  │ • document_blob │    │ • document_blob │    │ • document_blob │          │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘          │
│                                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐          │
│  │ PERMIT_DOCS     │    │ ROUTING_SLIPS   │    │ FOLDER_SYSTEM   │          │
│  │                 │    │                 │    │                 │          │
│  │ • applicant_name│    │ • doc_id        │    │ • folder_name   │          │
│  │ • purpose       │    │ • to_field      │    │ • folder_desc   │          │
│  │ • duration      │    │ • remarks        │    │ • file_count    │          │
│  │ • forwarded_to  │    │ • date           │    │ • created_by    │          │
│  │ • document_blob │    │ • purposes       │    │ • file_data     │          │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘          │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## System Features and Capabilities

### Authentication & Security
```
┌─────────────────┐
│   AUTHENTICATION│
│                 │
│ • Role-based    │
│   Access        │
│ • Password      │
│   Hashing       │
│ • Session       │
│   Management    │
│ • User Activity │
│   Tracking      │
└─────────────────┘
```

### File Management
```
┌─────────────────┐
│  FILE MANAGEMENT│
│                 │
│ • Binary Storage│
│   (LONGBLOB)    │
│ • File Preview  │
│ • Download      │
│   Functionality │
│ • Type          │
│   Validation    │
│ • Size Limits   │
│   (1GB max)     │
└─────────────────┘
```

### Dashboard Features
```
┌─────────────────┐
│   DASHBOARDS    │
│                 │
│ • Real-time     │
│   Statistics    │
│ • Document      │
│   Tracking      │
│ • Recent        │
│   Activity      │
│ • Interactive   │
│   Charts        │
│ • Responsive    │
│   Design        │
└─────────────────┘
```

## Network Configuration

### Multi-IP Access
```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              NETWORK SETUP                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│  │   LOCAL     │    │   NETWORK    │    │   EXTERNAL  │    │   MOBILE    │    │
│  │   ACCESS    │    │   ACCESS     │    │   ACCESS     │    │   ACCESS    │    │
│  │             │    │              │    │              │    │             │    │
│  │ 127.0.0.1   │    │ 192.168.x.x  │    │ Public IP   │    │ WiFi/LAN    │    │
│  │ Port 5000   │    │ Port 5000    │    │ Port 5000   │    │ Port 5000   │    │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    AUTOMATIC IP DETECTION                              │    │
│  │                                                                         │    │
│  │ • Socket Connection to 8.8.8.8:80                                      │    │
│  │ • Local IP Address Detection                                            │    │
│  │ • Hostname Resolution                                                   │    │
│  │ • Multiple IP Address Support                                           │    │
│  │ • Network Information Display                                           │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Report Flow Architecture

### Report Generation Process
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   DATA          │    │   PROCESSING    │    │   VISUALIZATION │
│   COLLECTION    │    │                 │    │                 │
│                 │    │ • Aggregation   │    │ • Charts        │
│ • Database      │───►│ • Filtering      │───►│ • Tables        │
│   Queries       │    │ • Calculation   │    │ • Dashboards    │
│ • User Activity │    │ • Validation    │    │ • Reports       │
│ • System Metrics│    │ • Formatting    │    │ • Exports       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Report Types by Role
```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              REPORT DISTRIBUTION                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│  │    ADMIN    │    │ RECEIVING1   │    │ RECEIVING2   │    │    DOCS     │    │
│  │             │    │             │    │              │    │             │    │
│  │ • System    │    │ • Intake    │    │ • Email      │    │ • GSO       │    │
│  │   Overview  │    │   Reports   │    │   Reports    │    │   Reports   │    │
│  │ • User      │    │ • Folder    │    │ • RTS        │    │ • Travel    │    │
│  │   Activity  │    │   Reports   │    │   Reports    │    │   Reports   │    │
│  │ • Document  │    │ • Processing│    │ • Acceptance │    │ • Leave     │    │
│  │   Tracking  │    │   Stats     │    │   Reports    │    │   Reports   │    │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                           RELEASING                                     │    │
│  │                                                                         │    │
│  │ • Release Statistics                                                   │    │
│  │ • Outgoing Document Reports                                            │    │
│  │ • Processing Efficiency                                               │    │
│  │ • Delivery Status                                                     │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## System Benefits and Features

### Key Advantages
```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              SYSTEM BENEFITS                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ✓ Centralized Management     ✓ Role-Based Access Control                      │
│  ✓ Complete Audit Trail       ✓ Scalable Architecture                         │
│  ✓ User-Friendly Interface    ✓ Network Accessibility                         │
│  ✓ Data Integrity             ✓ File Security                                 │
│  ✓ Real-Time Monitoring       ✓ Comprehensive Reporting                        │
│  ✓ Mobile Responsive Design    ✓ Multi-User Support                            │
│  ✓ Automated Workflows        ✓ Document Version Control                      │
│  ✓ Search and Filtering       ✓ Export Capabilities                           │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

This visual representation provides a comprehensive overview of your Document Management System's architecture, workflow, and capabilities. The system is designed to handle complex document workflows while maintaining security, efficiency, and user-friendly interfaces across all user roles.
