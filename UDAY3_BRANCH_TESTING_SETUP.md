# UDAY3 Branch Testing Configuration

## Overview
This branch is configured for isolated testing using UDAY3-specific environment variables and database credentials.

## Environment Variables Priority
All Python scripts prioritize UDAY3 variables with fallback to main branch variables:

### Primary (UDAY3 Branch)
- `SUPABASE_URL_UDAY3`
- `SUPABASE_ANON_KEY_UDAY3`
- `SUPABASE_KEY_UDAY3`

### Fallback (Main Branch)
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_KEY`

## Updated Files

### 1. GitHub Actions Workflow
- `.github/workflows/daily-script-runner.yml` - Uses UDAY3 variables for testing

### 2. Python Scripts
- `auto_assign_system.py` - Updated to use UDAY3 variables
- `knowlaritytosupabase.py` - Updated to use UDAY3 variables  
- `metatosupabase.py` - Updated to use UDAY3 variables
- `check_unassigned.py` - Updated for UDAY3 testing

### 3. Deployment Configuration
- `render-uday3.yaml` - UDAY3-specific Render deployment
- `render.yaml` - Main branch deployment (unchanged)

## Removed Unnecessary Files
The following files were removed to clean up the UDAY3 branch:
- `test_database_optimization.py`
- `optimized_lead_operations.py`
- `performance_analysis.md`
- `dashboard_config.json`
- `database_optimization.sql`
- `PERFORMANCE_FIX_SUMMARY.md`
- `enhanced_auto_assign_schema.sql`
- `test_auto_assign.py`
- `setup_auto_assign_config.py`
- `debug_cre_assignment.py`
- `railway.toml`

## Testing Instructions

### 1. Set Environment Variables
```bash
# UDAY3 Branch Variables (Primary)
SUPABASE_URL_UDAY3=your_uday3_supabase_url
SUPABASE_ANON_KEY_UDAY3=your_uday3_supabase_key
SUPABASE_KEY_UDAY3=your_uday3_supabase_key

# Main Branch Variables (Fallback)
SUPABASE_URL=your_main_supabase_url
SUPABASE_ANON_KEY=your_main_supabase_key
SUPABASE_KEY=your_main_supabase_key
```

### 2. Run Tests
```bash
# Test auto-assign system
python auto_assign_system.py

# Test Knowlarity integration
python knowlaritytosupabase.py

# Test Meta integration
python metatosupabase.py

# Check unassigned leads
python check_unassigned.py
```

### 3. Deploy to Render
```bash
# UDAY3 branch deployment
# Uses render-uday3.yaml configuration
```

## Benefits
✅ **Isolated Testing**: UDAY3 branch uses separate database  
✅ **Main Branch Protection**: Main branch configuration remains intact  
✅ **Easy Reversion**: Simple to switch back to main variables  
✅ **Clear Documentation**: Easy to understand which variables are for testing  

## When Ready to Merge
1. Update GitHub Actions workflow to use main branch variables
2. Update Python scripts to remove UDAY3 priority
3. Remove UDAY3-specific deployment files
4. Merge to main branch

## Current Status
🟢 **READY FOR TESTING** - All files updated for UDAY3 branch testing 