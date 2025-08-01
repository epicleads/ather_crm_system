# Auto-Assign System Documentation

## Table of Contents
1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Core Components](#core-components)
4. [Deployment Options](#deployment-options)
5. [Database Schema](#database-schema)
6. [Function Reference](#function-reference)
7. [Usage Examples](#usage-examples)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The Auto-Assign System is a comprehensive lead management solution that automatically distributes leads to Customer Relationship Executives (CREs) based on fair distribution algorithms. The system ensures balanced workload distribution while maintaining detailed audit trails.

### Key Features
- **Fair Distribution**: Prioritizes CREs with fewer assigned leads
- **IST Timezone Support**: All timestamps use Indian Standard Time (UTC+05:30)
- **History Tracking**: Complete audit trail of all assignments
- **Multiple Deployment Options**: GitHub Actions, Render, and local development
- **Real-time Monitoring**: Live statistics and progress tracking

---

## System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Lead Sources  │    │  Auto-Assign    │    │   CRE Users     │
│   (META, etc.)  │───▶│    System       │───▶│   (Database)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │  Assignment     │
                       │   History       │
                       └─────────────────┘
```

### Data Flow
1. **Lead Ingestion**: Leads are uploaded via CSV/Excel files
2. **Configuration Check**: System checks auto-assign configurations
3. **Fair Distribution**: Assigns leads to CREs with lowest counts
4. **History Logging**: Records all assignments with timestamps
5. **Statistics Update**: Updates CRE assignment counts

---

## Core Components

### 1. EnhancedAutoAssignTrigger Class

**Purpose**: Main background processing system for automatic lead assignment.

**Key Methods**:

#### `__init__(check_interval=30)`
- **Purpose**: Initialize the trigger system
- **Parameters**: 
  - `check_interval`: Seconds between checks (default: 30)
- **Usage**: `trigger = EnhancedAutoAssignTrigger(60)`

#### `start()`
- **Purpose**: Start background processing
- **Behavior**: Creates daemon thread that continuously checks for unassigned leads
- **Usage**: `trigger.start()`

#### `stop()`
- **Purpose**: Stop background processing
- **Behavior**: Gracefully stops the thread and waits for completion
- **Usage**: `trigger.stop()`

#### `_check_and_assign_leads()`
- **Purpose**: Main processing loop
- **Process**:
  1. Fetches all auto-assign configurations
  2. Groups configurations by source
  3. Processes each source with fair distribution
  4. Logs all assignments to history

#### `_process_source_leads_fair(source, configs)`
- **Purpose**: Process leads for a specific source using fair distribution
- **Parameters**:
  - `source`: Source name (e.g., 'META', 'GOOGLE')
  - `configs`: List of auto-assign configurations
- **Returns**: Number of leads assigned
- **Algorithm**:
  1. Get unassigned leads for the source
  2. For each lead, find CRE with lowest `auto_assign_count`
  3. Assign lead and update counts
  4. Log assignment to history

#### `get_fairest_cre_for_source(source)`
- **Purpose**: Find CRE with lowest assignment count for fair distribution
- **Parameters**: `source` - Source name
- **Returns**: CRE data dict or None
- **Logic**:
  1. Get all CREs with their `auto_assign_count`
  2. Filter CREs configured for this source
  3. Sort by count (lowest first) and ID for consistency
  4. Return the first (fairest) CRE

#### `log_auto_assignment(lead_uid, source, cre_id, cre_name, assignment_method)`
- **Purpose**: Log assignment details to history table
- **Parameters**:
  - `lead_uid`: Lead unique identifier
  - `source`: Source name
  - `cre_id`: CRE ID
  - `cre_name`: CRE name
  - `assignment_method`: Method used (default: 'fair_distribution')
- **Actions**:
  1. Get current `auto_assign_count` for CRE
  2. Insert record into `auto_assign_history`
  3. Update CRE's `auto_assign_count`

### 2. EnhancedAutoAssignMonitor Class

**Purpose**: Real-time monitoring and statistics for the auto-assign system.

**Key Methods**:

#### `get_current_stats()`
- **Purpose**: Get current auto-assign statistics
- **Returns**: Dict with CREs, configs, and recent assignments
- **Data Collected**:
  - All CREs with their `auto_assign_count`
  - Auto-assign configurations
  - Recent assignments (last 24 hours)

#### `analyze_fair_distribution(cres)`
- **Purpose**: Analyze fair distribution among CREs
- **Parameters**: `cres` - List of CRE data
- **Returns**: Distribution statistics dict
- **Calculations**:
  - Min/max assignment counts
  - Average assignments
  - Variance between CREs
  - Sorted CRE list by priority

#### `run_monitor(interval=30)`
- **Purpose**: Run continuous monitoring
- **Parameters**: `interval` - Seconds between updates
- **Features**:
  - Real-time statistics display
  - Fair distribution analysis
  - New assignment detection
  - Configuration status

### 3. RenderAutoAssignWorker Class

**Purpose**: Deployment-optimized worker for Render and GitHub Actions.

**Key Methods**:

#### `__init__(check_interval=60, max_leads_per_batch=50)`
- **Purpose**: Initialize deployment worker
- **Parameters**:
  - `check_interval`: Seconds between checks (default: 60)
  - `max_leads_per_batch`: Maximum leads per batch (default: 50)
- **Optimizations**:
  - Billing-optimized for Render's $25 plan
  - Reduced database calls
  - Batch processing limits

#### `run_optimized_auto_assign()`
- **Purpose**: Run optimized auto-assign check
- **Optimizations**:
  - Single query for configurations
  - Limited batch sizes
  - Efficient queries and batch updates
  - Detailed logging for monitoring

#### `run_continuous()`
- **Purpose**: Run worker continuously for Render deployment
- **Features**:
  - Graceful shutdown handling
  - Signal handlers (SIGTERM, SIGINT)
  - Continuous loop with configurable intervals
  - Detailed logging

#### `run_single()`
- **Purpose**: Run single check for GitHub Actions
- **Features**:
  - Runs once and exits
  - Suitable for CI/CD monitoring
  - Optimized for single-run scenarios

### 4. Setup and Verification Functions

#### `setup_enhanced_auto_assign()`
- **Purpose**: Set up the enhanced auto-assign system
- **Actions**:
  1. Reads `enhanced_auto_assign_schema.sql`
  2. Applies database schema changes
  3. Creates `auto_assign_count` column
  4. Creates `auto_assign_history` table
  5. Sets up functions and triggers
  6. Verifies the setup

#### `verify_setup()`
- **Purpose**: Verify system setup
- **Checks**:
  - `auto_assign_count` column exists
  - `auto_assign_history` table exists
  - IST timezone functionality works
  - `auto_assign_config` table exists

#### `get_cre_auto_assign_stats()`
- **Purpose**: Get current CRE statistics
- **Returns**: List of CRE statistics with `auto_assign_count`
- **Display**: Shows current assignment counts for all CREs

#### `test_fair_distribution()`
- **Purpose**: Test fair distribution logic
- **Features**:
  - Gets current CRE statistics
  - Sorts CREs by `auto_assign_count`
  - Shows fair distribution priority
  - Calculates distribution statistics
  - Identifies next CRE for assignment

### 5. Deployment Helper Functions

#### `create_render_worker()`
- **Purpose**: Create Render-optimized worker
- **Returns**: Configured `RenderAutoAssignWorker` instance
- **Configuration**: Uses environment variables for settings

#### `run_deployment_worker()`
- **Purpose**: Run appropriate deployment worker
- **Logic**:
  - Detects GitHub Actions environment
  - Runs single mode for GitHub Actions
  - Runs continuous mode for Render

---

## Deployment Options

### 1. GitHub Actions (`.github/workflows/auto-assign-trigger.yml`)

**Configuration**:
```yaml
name: Auto-Assign Trigger
on:
  schedule:
    - cron: '* * * * *'  # Every minute
  workflow_dispatch:  # Manual trigger
```

**Process**:
1. Runs every minute via cron
2. Uses `python auto_assign_system.py worker`
3. Single execution mode
4. Detailed logging for CI/CD

### 2. Render Deployment (`render.yaml`)

**Configuration**:
```yaml
- type: worker
  name: auto-assign-worker
  startCommand: python auto_assign_system.py render
  envVars:
    - key: CHECK_INTERVAL
      value: "60"
    - key: MAX_LEADS_PER_BATCH
      value: "50"
```

**Features**:
- Continuous operation
- Billing optimizations
- Graceful shutdown handling
- Environment variable configuration

### 3. Local Development

**Commands**:
```bash
# Test fair distribution
python auto_assign_system.py test

# Run monitor
python auto_assign_system.py monitor

# Start background trigger
python auto_assign_system.py trigger

# Show statistics
python auto_assign_system.py stats
```

---

## Database Schema

### 1. Enhanced Tables

#### `cre_users` Table
```sql
-- Added column for fair distribution
ALTER TABLE cre_users ADD COLUMN auto_assign_count INTEGER DEFAULT 0;
```

**Purpose**: Track number of leads auto-assigned to each CRE

#### `auto_assign_history` Table
```sql
CREATE TABLE auto_assign_history (
    id SERIAL PRIMARY KEY,
    lead_uid VARCHAR NOT NULL,
    source VARCHAR NOT NULL,
    assigned_cre_id INTEGER NOT NULL,
    assigned_cre_name VARCHAR NOT NULL,
    cre_total_leads_before INTEGER NOT NULL,
    cre_total_leads_after INTEGER NOT NULL,
    assignment_method VARCHAR DEFAULT 'fair_distribution',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Purpose**: Complete audit trail of all auto-assignments

### 2. Functions and Triggers

#### `update_auto_assign_count()`
- **Purpose**: Update CRE's auto-assign count
- **Trigger**: Called after lead assignment
- **Action**: Increments `auto_assign_count` for assigned CRE

#### `log_auto_assignment_history()`
- **Purpose**: Log assignment to history
- **Trigger**: Called after lead assignment
- **Action**: Inserts record into `auto_assign_history`

---

## Function Reference

### Core Functions

#### `get_ist_timestamp()`
- **Purpose**: Get current timestamp in IST timezone
- **Returns**: `datetime` object in IST
- **Usage**: `timestamp = get_ist_timestamp()`

#### `start_auto_assign_trigger()`
- **Purpose**: Start the auto-assign trigger system
- **Returns**: `EnhancedAutoAssignTrigger` instance
- **Usage**: `trigger = start_auto_assign_trigger()`

#### `stop_auto_assign_trigger()`
- **Purpose**: Stop the auto-assign trigger system
- **Usage**: `stop_auto_assign_trigger()`

#### `trigger_manual_assignment(source)`
- **Purpose**: Manually trigger assignment for a source
- **Parameters**: `source` - Source name
- **Returns**: Number of leads assigned
- **Usage**: `assigned = trigger_manual_assignment('META')`

### Main Execution Function

#### `main()`
- **Purpose**: Command-line interface for the auto-assign system
- **Commands**:
  - `setup`: Set up enhanced auto-assign system
  - `monitor`: Run enhanced monitor
  - `test`: Test fair distribution logic
  - `trigger`: Start background trigger
  - `stats`: Show current statistics
  - `worker`: Run deployment worker
  - `render`: Run Render-optimized worker

---

## Usage Examples

### 1. Basic Setup
```python
from auto_assign_system import setup_enhanced_auto_assign

# Set up the system
setup_enhanced_auto_assign()
```

### 2. Start Background Processing
```python
from auto_assign_system import start_auto_assign_trigger

# Start background processing
trigger = start_auto_assign_trigger()
```

### 3. Manual Assignment
```python
from auto_assign_system import trigger_manual_assignment

# Manually assign leads from META source
assigned_count = trigger_manual_assignment('META')
print(f"Assigned {assigned_count} leads")
```

### 4. Monitor System
```python
from auto_assign_system import EnhancedAutoAssignMonitor

# Start monitoring
monitor = EnhancedAutoAssignMonitor()
monitor.run_monitor(interval=30)
```

### 5. Test Fair Distribution
```python
from auto_assign_system import test_fair_distribution

# Test the fair distribution logic
test_fair_distribution()
```

### 6. Deployment Worker
```python
from auto_assign_system import RenderAutoAssignWorker

# Create and run deployment worker
worker = RenderAutoAssignWorker(check_interval=60, max_leads_per_batch=50)
worker.run_continuous()
```

---

## Troubleshooting

### Common Issues

#### 1. Import Errors
**Problem**: `ModuleNotFoundError: No module named 'auto_assign_trigger'`
**Solution**: Update imports to use `auto_assign_system` instead

#### 2. Database Connection Issues
**Problem**: Supabase connection failures
**Solution**: Check environment variables `SUPABASE_URL` and `SUPABASE_ANON_KEY`

#### 3. Timezone Issues
**Problem**: Incorrect timestamps
**Solution**: Ensure `pytz` is installed and IST timezone is configured

#### 4. Fair Distribution Not Working
**Problem**: Leads not being assigned fairly
**Solution**: 
1. Check `auto_assign_count` column exists
2. Verify auto-assign configurations
3. Run `test_fair_distribution()` to debug

### Debug Commands

```bash
# Test system setup
python auto_assign_system.py setup

# Test fair distribution
python auto_assign_system.py test

# Check statistics
python auto_assign_system.py stats

# Run monitor for debugging
python auto_assign_system.py monitor
```

### Log Analysis

#### Development Mode
- Check console output for detailed logs
- Look for "✅" success messages
- Monitor "⚠️" warning messages
- Debug "❌" error messages

#### Production Mode
- Check Render logs for worker service
- Monitor GitHub Actions workflow runs
- Review database for assignment history

---

## Performance Considerations

### 1. Database Optimization
- Batch updates reduce API calls
- Limited query sizes prevent timeouts
- Efficient indexing on frequently queried columns

### 2. Memory Management
- Limited batch sizes prevent memory issues
- Graceful shutdown prevents resource leaks
- Daemon threads for background processing

### 3. Cost Optimization (Render)
- Reduced database calls for billing efficiency
- Configurable batch limits
- Optimized for $25 Render plan

### 4. Monitoring
- Real-time statistics tracking
- Assignment history for audit trails
- Performance metrics and logging

---

## Security Considerations

### 1. Authentication
- Supabase authentication for database access
- Environment variable protection for secrets
- Role-based access control

### 2. Data Protection
- Secure database connections
- Encrypted data transmission
- Audit trails for all assignments

### 3. Error Handling
- Graceful error recovery
- Detailed error logging
- Fallback mechanisms

---

## Future Enhancements

### 1. Advanced Algorithms
- Machine learning-based distribution
- Performance-based assignment
- Dynamic load balancing

### 2. Enhanced Monitoring
- Real-time dashboards
- Performance analytics
- Predictive analytics

### 3. Integration Features
- API endpoints for external systems
- Webhook notifications
- Third-party integrations

---

## Conclusion

The Auto-Assign System provides a robust, scalable solution for automatic lead distribution with fair distribution algorithms, comprehensive monitoring, and multiple deployment options. The system ensures balanced workload distribution while maintaining detailed audit trails and real-time statistics.

For questions or issues, refer to the troubleshooting section or check the system logs for detailed error information. 