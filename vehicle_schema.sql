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

-- Insert sample data for testing
INSERT INTO vehicles (vehicle_name) VALUES 
('450');

-- Insert sample models
INSERT INTO models (vehicle_id, model_name) VALUES 
(1, '450 S LR'),
(1, '450 X LR'),
(1, '450 X HR'),
(1, 'APEX');

-- Insert sample color options
INSERT INTO color_options (model_id, color_name) VALUES 
-- 450 S LR colors
(1, 'Lunar Grey'),
(1, 'Space Grey'),
(1, 'Still White'),
(1, 'True Red'),
(1, 'Cosmic Black'),
(1, 'Hyper Sand'),
(1, 'Stealth Blue'),

-- 450 X LR colors
(2, 'Lunar Grey'),
(2, 'Space Grey'),
(2, 'Still White'),
(2, 'True Red'),
(2, 'Cosmic Black'),
(2, 'Hyper Sand'),
(2, 'Stealth Blue'),

-- 450 X HR colors
(3, 'Lunar Grey'),
(3, 'Space Grey'),
(3, 'Still White'),
(3, 'True Red'),
(3, 'Cosmic Black'),
(3, 'Hyper Sand'),
(3, 'Stealth Blue'),

-- APEX colors (including Indium Blue)
(4, 'Lunar Grey'),
(4, 'Space Grey'),
(4, 'Still White'),
(4, 'True Red'),
(4, 'Cosmic Black'),
(4, 'Hyper Sand'),
(4, 'Stealth Blue'),
(4, 'Indium Blue');

-- Insert sample battery capacities
INSERT INTO battery_capacities (color_id, capacity_kwh) VALUES 
-- 450 S LR - Lunar Grey
(1, 2.9),
(1, 3.9),
-- 450 S LR - Space Grey
(2, 2.9),
(2, 3.9),
-- 450 S LR - Still White
(3, 2.9),
(3, 3.9),
-- 450 S LR - True Red
(4, 2.9),
(4, 3.9),
-- 450 S LR - Cosmic Black
(5, 2.9),
(5, 3.9),
-- 450 S LR - Hyper Sand
(6, 2.9),
(6, 3.9),
-- 450 S LR - Stealth Blue
(7, 2.9),
(7, 3.9),

-- 450 X LR - Lunar Grey
(8, 2.9),
(8, 3.9),
-- 450 X LR - Space Grey
(9, 2.9),
(9, 3.9),
-- 450 X LR - Still White
(10, 2.9),
(10, 3.9),
-- 450 X LR - True Red
(11, 2.9),
(11, 3.9),
-- 450 X LR - Cosmic Black
(12, 2.9),
(12, 3.9),
-- 450 X LR - Hyper Sand
(13, 2.9),
(13, 3.9),
-- 450 X LR - Stealth Blue
(14, 2.9),
(14, 3.9),

-- 450 X HR - Lunar Grey
(15, 2.9),
(15, 3.9),
-- 450 X HR - Space Grey
(16, 2.9),
(16, 3.9),
-- 450 X HR - Still White
(17, 2.9),
(17, 3.9),
-- 450 X HR - True Red
(18, 2.9),
(18, 3.9),
-- 450 X HR - Cosmic Black
(19, 2.9),
(19, 3.9),
-- 450 X HR - Hyper Sand
(20, 2.9),
(20, 3.9),
-- 450 X HR - Stealth Blue
(21, 2.9),
(21, 3.9),

-- APEX - Lunar Grey
(22, 2.9),
(22, 3.9),
-- APEX - Space Grey
(23, 2.9),
(23, 3.9),
-- APEX - Still White
(24, 2.9),
(24, 3.9),
-- APEX - True Red
(25, 2.9),
(25, 3.9),
-- APEX - Cosmic Black
(26, 2.9),
(26, 3.9),
-- APEX - Hyper Sand
(27, 2.9),
(27, 3.9),
-- APEX - Stealth Blue
(28, 2.9),
(28, 3.9),
-- APEX - Indium Blue (exclusive to APEX)
(29, 2.9),
(29, 3.9); 