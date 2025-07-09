# Vehicle Management System Setup Guide

## Overview
The Vehicle Management System allows administrators to manage vehicles, models, colors, and battery capacities for the Ather CRM system. The system uses a hierarchical structure where:
- One Vehicle can have multiple Models
- One Model can have multiple Color Options
- One Color Option can have multiple Battery Capacities

## Database Schema

### Tables Structure

1. **vehicles** - Main vehicle table
   - `id` (SERIAL PRIMARY KEY)
   - `vehicle_name` (VARCHAR(255) NOT NULL UNIQUE)
   - `created_at` (TIMESTAMP WITH TIME ZONE)
   - `updated_at` (TIMESTAMP WITH TIME ZONE)

2. **models** - Models related to vehicles
   - `id` (SERIAL PRIMARY KEY)
   - `vehicle_id` (INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE)
   - `model_name` (VARCHAR(255) NOT NULL)
   - `created_at` (TIMESTAMP WITH TIME ZONE)
   - `updated_at` (TIMESTAMP WITH TIME ZONE)
   - UNIQUE(vehicle_id, model_name)

3. **color_options** - Color options related to models
   - `id` (SERIAL PRIMARY KEY)
   - `model_id` (INTEGER NOT NULL REFERENCES models(id) ON DELETE CASCADE)
   - `color_name` (VARCHAR(255) NOT NULL)
   - `created_at` (TIMESTAMP WITH TIME ZONE)
   - `updated_at` (TIMESTAMP WITH TIME ZONE)
   - UNIQUE(model_id, color_name)

4. **battery_capacities** - Battery capacities related to color options
   - `id` (SERIAL PRIMARY KEY)
   - `color_id` (INTEGER NOT NULL REFERENCES color_options(id) ON DELETE CASCADE)
   - `capacity_kwh` (DECIMAL(4,1) NOT NULL)
   - `created_at` (TIMESTAMP WITH TIME ZONE)
   - `updated_at` (TIMESTAMP WITH TIME ZONE)
   - UNIQUE(color_id, capacity_kwh)

## Design Logic

The system follows this hierarchical structure:
- **One Vehicle** → **Multiple Models**
- **One Model** → **Multiple Color Options**
- **One Color Option** → **Multiple Battery Capacities**

## Available Data Structure

### Vehicle: 450

### Models:
- 450 S LR
- 450 X LR
- 450 X HR
- APEX

### Colors:
- Lunar Grey
- Space Grey
- Still White
- True Red
- Cosmic Black
- Hyper Sand
- Stealth Blue
- **Indium Blue** (Only available for APEX model)

### Battery Capacities:
- 2.9 kWh
- 3.9 kWh

## Color Constraints

**Indium Blue** is exclusively available only for the **APEX** model. The system includes:
- **Backend Validation**: Server-side validation prevents adding Indium Blue to non-APEX models
- **Frontend Validation**: UI dynamically shows/hides Indium Blue option based on selected model
- **User Feedback**: Clear error messages when attempting to add Indium Blue to wrong model

## Setup Instructions

### 1. Database Setup

1. **Run the SQL Schema**: Execute the `vehicle_schema.sql` file in your Supabase database:
   ```sql
   -- Copy and paste the contents of vehicle_schema.sql into your Supabase SQL editor
   ```

2. **Verify Tables**: Check that the following tables were created:
   - `vehicles`
   - `models`
   - `color_options`
   - `battery_capacities`

### 2. Application Setup

The vehicle management system has been integrated into the existing Flask application with the following new routes:

#### New Routes Added:
- `/manage_vehicles` - Main vehicle management page
- `/add_vehicle` - Add new vehicle
- `/add_model` - Add new model to vehicle
- `/add_color` - Add color option to model (with Indium Blue validation)
- `/add_battery` - Add battery capacity to color option
- `/delete_vehicle/<id>` - Delete vehicle
- `/delete_model/<id>` - Delete model
- `/delete_color/<id>` - Delete color
- `/delete_battery/<id>` - Delete battery capacity
- `/get_vehicles` - Get all vehicles (API)
- `/get_models/<vehicle_id>` - Get models for vehicle (API)
- `/get_colors/<model_id>` - Get colors for model (API)

### 3. Features

#### Admin Dashboard Integration
- New "Vehicle Management" section added to the admin dashboard
- Direct link to manage vehicles, models, colors, and battery capacities

#### Vehicle Management Interface
- **Add Vehicles**: Create new vehicle entries
- **Add Models**: Add models to existing vehicles
- **Add Colors**: Add color options to specific models (with dropdown selection)
- **Add Battery Capacities**: Add battery capacity options to specific colors
- **View All Data**: Comprehensive view of all vehicles, models, colors, and batteries
- **Delete Functionality**: Remove vehicles, models, colors, and batteries with confirmation

#### Dynamic Dropdowns
- Vehicle selection automatically loads available models
- Model selection automatically loads available colors
- Color selection for battery capacities
- Real-time updates when data changes

#### Color Constraint System
- **Indium Blue Validation**: Only available for APEX model
- **Dynamic UI**: Indium Blue option shows/hides based on model selection
- **Backend Protection**: Server-side validation prevents invalid combinations
- **User Feedback**: Clear error messages for constraint violations

#### Data Validation
- Prevents duplicate entries
- Required field validation
- Color constraint validation
- Proper error handling and user feedback

### 4. Sample Data

The schema includes comprehensive sample data for testing:
- **Vehicle**: 450
- **Models**: 450 S LR, 450 X LR, 450 X HR, APEX
- **Colors**: Lunar Grey, Space Grey, Still White, True Red, Cosmic Black, Hyper Sand, Stealth Blue, Indium Blue (APEX only)
- **Battery Capacities**: 2.9 kWh, 3.9 kWh (distributed across all color combinations)

### 5. Usage Instructions

#### For Administrators:

1. **Access Vehicle Management**:
   - Log in as admin
   - Go to Admin Dashboard
   - Click "Manage Vehicles" in the Vehicle Management section

2. **Add a New Vehicle**:
   - Enter vehicle name in the "Add New Vehicle" form
   - Click "Add Vehicle"

3. **Add Models to Vehicles**:
   - Select a vehicle from the dropdown
   - Enter model name
   - Click "Add Model"

4. **Add Colors to Models**:
   - Select vehicle and model from dropdowns
   - Choose color from the dropdown (Indium Blue only shows for APEX)
   - Click "Add Color"

5. **Add Battery Capacities to Colors**:
   - Select vehicle, model, and color from dropdowns
   - Enter battery capacity in kWh
   - Click "Add Battery Capacity"

6. **Delete Items**:
   - Click the delete button next to any item
   - Confirm the deletion in the popup dialog

### 6. Data View Example

The system allows for complex vehicle configurations like:

| Vehicle Name | Model Name | Color Name | Battery Capacity (kWh) |
|--------------|------------|------------|------------------------|
| 450 | 450 S LR | Lunar Grey | 2.9 |
| 450 | 450 S LR | Lunar Grey | 3.9 |
| 450 | 450 X LR | Space Grey | 2.9 |
| 450 | 450 X HR | True Red | 3.9 |
| 450 | APEX | Indium Blue | 2.9 |
| 450 | APEX | Indium Blue | 3.9 |

### 7. Color Constraint Rules

- **Indium Blue**: Only available for APEX model
- **All Other Colors**: Available for all models (450 S LR, 450 X LR, 450 X HR, APEX)
- **Validation**: Both frontend and backend validation ensure constraints are enforced

### 8. Security Features

- All routes require admin authentication
- CSRF protection through Flask forms
- Input validation and sanitization
- Color constraint validation
- Confirmation dialogs for deletions
- Proper error handling and user feedback

### 9. Database Relationships

The system uses proper foreign key relationships with CASCADE DELETE:
- Deleting a vehicle deletes all its models, colors, and batteries
- Deleting a model deletes all its colors and batteries
- Deleting a color deletes all its battery capacities
- Deleting a battery capacity only affects that specific item

### 10. Performance Considerations

- Indexes created on foreign key columns for better query performance
- Efficient queries using Supabase's built-in optimization
- Pagination ready for large datasets
- Proper error handling to prevent application crashes

## Troubleshooting

### Common Issues:

1. **"Vehicle already exists" error**:
   - Check if the vehicle name is already in the database
   - Use a different name or delete the existing entry

2. **"Model already exists for this vehicle" error**:
   - Check if the model name already exists for the selected vehicle
   - Use a different name or delete the existing entry

3. **"Color already exists for this model" error**:
   - Check if the color already exists for the selected model
   - Use a different name or delete the existing entry

4. **"Indium Blue is only available for APEX model" error**:
   - Ensure you're adding Indium Blue to the APEX model only
   - Use other colors for non-APEX models

5. **"Battery capacity already exists for this color" error**:
   - Check if the battery capacity already exists for the selected color
   - Use a different capacity or delete the existing entry

### Database Connection Issues:

1. **Check Supabase connection**:
   - Verify SUPABASE_URL and SUPABASE_ANON_KEY environment variables
   - Test connection in the application

2. **Table not found errors**:
   - Ensure the vehicle_schema.sql was executed successfully
   - Check that all tables exist in your Supabase database

## Future Enhancements

Potential improvements for the vehicle management system:

1. **Bulk Operations**: Add/delete multiple items at once
2. **Import/Export**: CSV import/export functionality
3. **Search and Filter**: Advanced search and filtering options
4. **Audit Trail**: Track changes to vehicle data
5. **API Integration**: RESTful API for external integrations
6. **Image Support**: Add vehicle and model images
7. **Pricing Integration**: Link models to pricing information
8. **Inventory Management**: Track vehicle inventory levels
9. **Advanced Constraints**: Add more color-model restrictions
10. **Bulk Color Assignment**: Assign multiple colors to models at once

## Support

For issues or questions regarding the vehicle management system:
1. Check the troubleshooting section above
2. Review the application logs for error details
3. Verify database connectivity and permissions
4. Test with the sample data provided in the schema
5. Check color constraint rules for Indium Blue 