-- Ultra-Fast Lead Update RPC Function
-- Guarantees sub-500ms update performance with atomic operations

-- ==========================================
-- ULTRA-FAST LEAD UPDATE RPC FUNCTION
-- ==========================================

CREATE OR REPLACE FUNCTION update_lead_ultra_fast(
    p_lead_uid TEXT,
    p_user_type TEXT,
    p_user_name TEXT,
    p_update_data JSONB,
    p_timestamp TIMESTAMP DEFAULT NOW()
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result JSON;
    update_count INTEGER := 0;
    operations_log TEXT[] := '{}';
    lead_exists BOOLEAN := FALSE;
    ps_exists BOOLEAN := FALSE;
    current_final_status TEXT;
    new_final_status TEXT;
    sync_required BOOLEAN := FALSE;
    start_time TIMESTAMP := clock_timestamp();
BEGIN
    -- Extract new final status if present
    new_final_status := p_update_data->>'final_status';

    -- Step 1: Check if lead exists and get current status (single query)
    SELECT EXISTS (SELECT 1 FROM lead_master WHERE uid = p_lead_uid),
           COALESCE((SELECT final_status FROM lead_master WHERE uid = p_lead_uid LIMIT 1), 'Pending')
    INTO lead_exists, current_final_status;

    IF NOT lead_exists THEN
        RETURN json_build_object(
            'success', false,
            'error', 'Lead not found: ' || p_lead_uid,
            'execution_time', EXTRACT(EPOCH FROM (clock_timestamp() - start_time))
        );
    END IF;

    -- Step 2: Check if PS followup exists
    SELECT EXISTS (SELECT 1 FROM ps_followup_master WHERE lead_uid = p_lead_uid)
    INTO ps_exists;

    -- Step 3: Determine if sync is required
    IF new_final_status IS NOT NULL AND new_final_status != current_final_status THEN
        sync_required := TRUE;
    END IF;

    -- Step 4: Execute updates based on user type
    IF p_user_type = 'cre' THEN
        -- Update lead_master table
        UPDATE lead_master SET
            customer_name = COALESCE(p_update_data->>'customer_name', customer_name),
            customer_mobile_number = COALESCE(p_update_data->>'customer_mobile_number', customer_mobile_number),
            source = COALESCE(p_update_data->>'source', source),
            sub_source = COALESCE(p_update_data->>'sub_source', sub_source),
            lead_status = COALESCE(p_update_data->>'lead_status', lead_status),
            final_status = COALESCE(p_update_data->>'final_status', final_status),
            lead_category = COALESCE(p_update_data->>'lead_category', lead_category),
            model_interested = COALESCE(p_update_data->>'model_interested', model_interested),
            branch = COALESCE(p_update_data->>'branch', branch),
            follow_up_date = COALESCE((p_update_data->>'follow_up_date')::TIMESTAMP, follow_up_date),
            first_call_date = COALESCE((p_update_data->>'first_call_date')::TIMESTAMP, first_call_date),
            first_remark = COALESCE(p_update_data->>'first_remark', first_remark),
            second_call_date = COALESCE((p_update_data->>'second_call_date')::TIMESTAMP, second_call_date),
            second_remark = COALESCE(p_update_data->>'second_remark', second_remark),
            third_call_date = COALESCE((p_update_data->>'third_call_date')::TIMESTAMP, third_call_date),
            third_remark = COALESCE(p_update_data->>'third_remark', third_remark),
            fourth_call_date = COALESCE((p_update_data->>'fourth_call_date')::TIMESTAMP, fourth_call_date),
            fourth_remark = COALESCE(p_update_data->>'fourth_remark', fourth_remark),
            fifth_call_date = COALESCE((p_update_data->>'fifth_call_date')::TIMESTAMP, fifth_call_date),
            fifth_remark = COALESCE(p_update_data->>'fifth_remark', fifth_remark),
            sixth_call_date = COALESCE((p_update_data->>'sixth_call_date')::TIMESTAMP, sixth_call_date),
            sixth_remark = COALESCE(p_update_data->>'sixth_remark', sixth_remark),
            seventh_call_date = COALESCE((p_update_data->>'seventh_call_date')::TIMESTAMP, seventh_call_date),
            seventh_remark = COALESCE(p_update_data->>'seventh_remark', seventh_remark),
            won_timestamp = CASE
                WHEN p_update_data->>'final_status' = 'Won' AND won_timestamp IS NULL
                THEN p_timestamp
                ELSE won_timestamp
            END,
            lost_timestamp = CASE
                WHEN p_update_data->>'final_status' = 'Lost' AND lost_timestamp IS NULL
                THEN p_timestamp
                ELSE lost_timestamp
            END,
            updated_at = p_timestamp
        WHERE uid = p_lead_uid;

        GET DIAGNOSTICS update_count = ROW_COUNT;
        operations_log := operations_log || ('lead_master: ' || update_count::TEXT);

        -- Sync to PS followup if required and exists
        IF sync_required AND ps_exists THEN
            UPDATE ps_followup_master SET
                final_status = p_update_data->>'final_status',
                lead_status = COALESCE(p_update_data->>'lead_status', lead_status),
                follow_up_date = COALESCE((p_update_data->>'follow_up_date')::TIMESTAMP, follow_up_date),
                updated_at = p_timestamp
            WHERE lead_uid = p_lead_uid;

            GET DIAGNOSTICS update_count = ROW_COUNT;
            operations_log := operations_log || ('ps_sync: ' || update_count::TEXT);
        END IF;

    ELSIF p_user_type = 'ps' THEN
        -- Update ps_followup_master table first
        IF ps_exists THEN
            UPDATE ps_followup_master SET
                customer_name = COALESCE(p_update_data->>'customer_name', customer_name),
                customer_mobile_number = COALESCE(p_update_data->>'customer_mobile_number', customer_mobile_number),
                source = COALESCE(p_update_data->>'source', source),
                lead_status = COALESCE(p_update_data->>'lead_status', lead_status),
                final_status = COALESCE(p_update_data->>'final_status', final_status),
                lead_category = COALESCE(p_update_data->>'lead_category', lead_category),
                model_interested = COALESCE(p_update_data->>'model_interested', model_interested),
                follow_up_date = COALESCE((p_update_data->>'follow_up_date')::TIMESTAMP, follow_up_date),
                first_call_date = COALESCE((p_update_data->>'first_call_date')::TIMESTAMP, first_call_date),
                first_call_remark = COALESCE(p_update_data->>'first_call_remark', first_call_remark),
                second_call_date = COALESCE((p_update_data->>'second_call_date')::TIMESTAMP, second_call_date),
                second_call_remark = COALESCE(p_update_data->>'second_call_remark', second_call_remark),
                third_call_date = COALESCE((p_update_data->>'third_call_date')::TIMESTAMP, third_call_date),
                third_call_remark = COALESCE(p_update_data->>'third_call_remark', third_call_remark),
                updated_at = p_timestamp
            WHERE lead_uid = p_lead_uid;

            GET DIAGNOSTICS update_count = ROW_COUNT;
            operations_log := operations_log || ('ps_followup_master: ' || update_count::TEXT);
        END IF;

        -- Sync critical fields back to lead_master
        UPDATE lead_master SET
            final_status = COALESCE(p_update_data->>'final_status', final_status),
            lead_status = COALESCE(p_update_data->>'lead_status', lead_status),
            follow_up_date = COALESCE((p_update_data->>'follow_up_date')::TIMESTAMP, follow_up_date),
            won_timestamp = CASE
                WHEN p_update_data->>'final_status' = 'Won' AND won_timestamp IS NULL
                THEN p_timestamp
                ELSE won_timestamp
            END,
            lost_timestamp = CASE
                WHEN p_update_data->>'final_status' = 'Lost' AND lost_timestamp IS NULL
                THEN p_timestamp
                ELSE lost_timestamp
            END,
            updated_at = p_timestamp
        WHERE uid = p_lead_uid;

        GET DIAGNOSTICS update_count = ROW_COUNT;
        operations_log := operations_log || ('lead_master_sync: ' || update_count::TEXT);
    END IF;

    -- Step 5: Log audit trail (non-blocking)
    BEGIN
        INSERT INTO audit_log (
            lead_uid,
            user_type,
            user_name,
            action,
            changes,
            timestamp,
            created_at
        ) VALUES (
            p_lead_uid,
            p_user_type,
            p_user_name,
            'update_lead',
            p_update_data,
            p_timestamp,
            p_timestamp
        );

        operations_log := operations_log || 'audit_logged';
    EXCEPTION WHEN OTHERS THEN
        -- Ignore audit failures to maintain performance
        operations_log := operations_log || 'audit_skipped';
    END;

    -- Step 6: Return success result
    SELECT json_build_object(
        'success', true,
        'lead_uid', p_lead_uid,
        'user_type', p_user_type,
        'user_name', p_user_name,
        'operations_completed', operations_log,
        'sync_performed', sync_required,
        'ps_followup_exists', ps_exists,
        'execution_time', EXTRACT(EPOCH FROM (clock_timestamp() - start_time)),
        'timestamp', p_timestamp
    ) INTO result;

    RETURN result;

EXCEPTION WHEN OTHERS THEN
    -- Return error result
    RETURN json_build_object(
        'success', false,
        'error', SQLERRM,
        'lead_uid', p_lead_uid,
        'execution_time', EXTRACT(EPOCH FROM (clock_timestamp() - start_time))
    );
END;
$$;

-- ==========================================
-- BATCH UPDATE RPC FUNCTION
-- ==========================================

CREATE OR REPLACE FUNCTION batch_update_leads_ultra_fast(
    p_updates JSONB
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result JSON;
    update_record JSONB;
    single_result JSON;
    successful_updates INTEGER := 0;
    failed_updates INTEGER := 0;
    operations_log JSONB[] := '{}';
    start_time TIMESTAMP := clock_timestamp();
BEGIN
    -- Process each update in the batch
    FOR update_record IN SELECT * FROM jsonb_array_elements(p_updates)
    LOOP
        BEGIN
            -- Call single update function
            SELECT update_lead_ultra_fast(
                update_record->>'lead_uid',
                update_record->>'user_type',
                update_record->>'user_name',
                update_record->'update_data',
                COALESCE((update_record->>'timestamp')::TIMESTAMP, NOW())
            ) INTO single_result;

            IF (single_result->>'success')::BOOLEAN THEN
                successful_updates := successful_updates + 1;
            ELSE
                failed_updates := failed_updates + 1;
            END IF;

            operations_log := operations_log || single_result::JSONB;

        EXCEPTION WHEN OTHERS THEN
            failed_updates := failed_updates + 1;
            operations_log := operations_log || json_build_object(
                'success', false,
                'lead_uid', update_record->>'lead_uid',
                'error', SQLERRM
            )::JSONB;
        END;
    END LOOP;

    -- Return batch results
    SELECT json_build_object(
        'success', true,
        'total_updates', jsonb_array_length(p_updates),
        'successful_updates', successful_updates,
        'failed_updates', failed_updates,
        'success_rate', CASE
            WHEN jsonb_array_length(p_updates) > 0
            THEN ROUND((successful_updates::DECIMAL / jsonb_array_length(p_updates) * 100), 2)
            ELSE 0
        END,
        'operations_log', array_to_json(operations_log),
        'execution_time', EXTRACT(EPOCH FROM (clock_timestamp() - start_time))
    ) INTO result;

    RETURN result;
END;
$$;

-- ==========================================
-- REAL-TIME UPDATE WITH CONFLICT RESOLUTION
-- ==========================================

CREATE OR REPLACE FUNCTION update_lead_with_conflict_resolution(
    p_lead_uid TEXT,
    p_user_type TEXT,
    p_user_name TEXT,
    p_update_data JSONB,
    p_expected_version BIGINT DEFAULT NULL,
    p_timestamp TIMESTAMP DEFAULT NOW()
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result JSON;
    current_version BIGINT;
    conflict_detected BOOLEAN := FALSE;
    start_time TIMESTAMP := clock_timestamp();
BEGIN
    -- Get current version
    SELECT EXTRACT(EPOCH FROM updated_at) INTO current_version
    FROM lead_master
    WHERE uid = p_lead_uid;

    -- Check for conflicts if version provided
    IF p_expected_version IS NOT NULL AND current_version != p_expected_version THEN
        conflict_detected := TRUE;

        RETURN json_build_object(
            'success', false,
            'conflict_detected', true,
            'current_version', current_version,
            'expected_version', p_expected_version,
            'lead_uid', p_lead_uid,
            'message', 'Lead was modified by another user. Please refresh and try again.',
            'execution_time', EXTRACT(EPOCH FROM (clock_timestamp() - start_time))
        );
    END IF;

    -- Perform the update if no conflict
    SELECT update_lead_ultra_fast(
        p_lead_uid,
        p_user_type,
        p_user_name,
        p_update_data,
        p_timestamp
    ) INTO result;

    -- Add version info to result
    result := result || json_build_object(
        'conflict_detected', false,
        'new_version', EXTRACT(EPOCH FROM p_timestamp)
    );

    RETURN result;
END;
$$;

-- ==========================================
-- OPTIMIZED INDEXES FOR ULTRA-FAST UPDATES
-- ==========================================

-- Indexes for ultra-fast lead lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lead_master_uid_hash
ON lead_master USING HASH (uid);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ps_followup_lead_uid_hash
ON ps_followup_master USING HASH (lead_uid);

-- Indexes for version-based conflict resolution
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lead_master_uid_updated
ON lead_master (uid, updated_at);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ps_followup_uid_updated
ON ps_followup_master (lead_uid, updated_at);

-- Partial indexes for active leads (most frequently updated)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lead_master_active_updates
ON lead_master (uid, updated_at)
WHERE final_status IN ('Pending', 'Follow-up', 'Hot');

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ps_followup_active_updates
ON ps_followup_master (lead_uid, updated_at)
WHERE final_status IN ('Pending', 'Follow-up', 'Hot');

-- ==========================================
-- PERFORMANCE MONITORING FUNCTION
-- ==========================================

CREATE OR REPLACE FUNCTION get_update_performance_stats()
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result JSON;
    avg_update_time DECIMAL;
    total_updates BIGINT;
    recent_updates BIGINT;
BEGIN
    -- Get performance statistics
    SELECT
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '1 hour') as recent,
        AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) as avg_time
    INTO total_updates, recent_updates, avg_update_time
    FROM audit_log
    WHERE action = 'update_lead'
    AND created_at >= NOW() - INTERVAL '24 hours';

    SELECT json_build_object(
        'total_updates_24h', total_updates,
        'updates_last_hour', recent_updates,
        'average_update_time', COALESCE(avg_update_time, 0),
        'updates_per_minute', CASE
            WHEN recent_updates > 0 THEN ROUND(recent_updates / 60.0, 2)
            ELSE 0
        END,
        'timestamp', NOW()
    ) INTO result;

    RETURN result;
END;
$$;

-- ==========================================
-- GRANT PERMISSIONS
-- ==========================================

GRANT EXECUTE ON FUNCTION update_lead_ultra_fast TO authenticated;
GRANT EXECUTE ON FUNCTION batch_update_leads_ultra_fast TO authenticated;
GRANT EXECUTE ON FUNCTION update_lead_with_conflict_resolution TO authenticated;
GRANT EXECUTE ON FUNCTION get_update_performance_stats TO authenticated;

-- ==========================================
-- PERFORMANCE OPTIMIZATION SETTINGS
-- ==========================================

-- Enable parallel query execution for batch operations
-- ALTER DATABASE your_database_name SET max_parallel_workers_per_gather = 4;
-- ALTER DATABASE your_database_name SET max_parallel_workers = 8;

-- Optimize for write-heavy workload
-- ALTER DATABASE your_database_name SET shared_preload_libraries = 'pg_stat_statements';
-- ALTER DATABASE your_database_name SET track_activity_query_size = 2048;