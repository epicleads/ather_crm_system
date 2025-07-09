-- Vehicle Management Schema for Ather CRM System

-- 1. Vehicles table
CREATE TABLE vehicles (
    id SERIAL PRIMARY KEY,
    vehicle_name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Models table (related to Vehicles)
CREATE TABLE models (
    id SERIAL PRIMARY KEY,
    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    model_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(vehicle_id, model_name)
);

-- 3. Color Options table (related to Models)
CREATE TABLE color_options (
    id SERIAL PRIMARY KEY,
    model_id INTEGER NOT NULL REFERENCES models(id) ON DELETE CASCADE,
    color_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(model_id, color_name)
);

-- 4. Battery Capacities table (related to Color Options)
CREATE TABLE battery_capacities (
    id SERIAL PRIMARY KEY,
    color_id INTEGER NOT NULL REFERENCES color_options(id) ON DELETE CASCADE,
    capacity_kwh DECIMAL(4,1) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(color_id, capacity_kwh)
);

-- Add vehicle_id to color_options
ALTER TABLE color_options ADD COLUMN IF NOT EXISTS vehicle_id INTEGER REFERENCES vehicles(id) ON DELETE CASCADE;

-- Add vehicle_id and model_id to battery_capacities
ALTER TABLE battery_capacities ADD COLUMN IF NOT EXISTS vehicle_id INTEGER REFERENCES vehicles(id) ON DELETE CASCADE;
ALTER TABLE battery_capacities ADD COLUMN IF NOT EXISTS model_id INTEGER REFERENCES models(id) ON DELETE CASCADE;

-- Drop old unique constraints if they exist
ALTER TABLE color_options DROP CONSTRAINT IF EXISTS color_options_model_id_color_name_key;
ALTER TABLE battery_capacities DROP CONSTRAINT IF EXISTS battery_capacities_color_id_capacity_kwh_key;

-- Add new unique constraints
ALTER TABLE color_options ADD CONSTRAINT color_options_vehicle_model_color_unique UNIQUE (vehicle_id, model_id, color_name);
ALTER TABLE battery_capacities ADD CONSTRAINT battery_caps_vehicle_model_color_capacity_unique UNIQUE (vehicle_id, model_id, color_id, capacity_kwh);

-- Note: For Supabase, these ALTER statements can be run in the SQL editor or as a migration script.

-- Create indexes for better performance
CREATE INDEX idx_models_vehicle_id ON models(vehicle_id);
CREATE INDEX idx_color_options_model_id ON color_options(model_id);
CREATE INDEX idx_battery_capacities_color_id ON battery_capacities(color_id);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_vehicles_updated_at BEFORE UPDATE ON vehicles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_models_updated_at BEFORE UPDATE ON models FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_color_options_updated_at BEFORE UPDATE ON color_options FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_battery_capacities_updated_at BEFORE UPDATE ON battery_capacities FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

