# Receptionist Assigned Leads Feature

## Overview
This feature allows receptionists to view all leads they have assigned to PS (Product Specialists) in a comprehensive tabular format.

## Features

### 1. Assigned Leads Dashboard
- **Route**: `/rec_assigned_leads`
- **Access**: Receptionist users only
- **Purpose**: Display all walk-in leads assigned to PS users by the receptionist

### 2. Key Functionality

#### Statistics Overview
- Total leads assigned
- Pending leads count
- Won leads count
- Lost leads count

#### Filtering Options
- Filter by PS (Product Specialist)
- Filter by lead status (Pending, Won, Lost)
- Sort by date (newest/oldest first)
- Sort by customer name (A-Z/Z-A)

#### View Modes
- **All Leads View**: Complete table with all assigned leads
- **Grouped View**: Leads grouped by PS with separate tables for each PS

#### Interactive Features
- Copy lead information to clipboard
- View lead details (placeholder for future enhancement)
- Toggle between view modes
- Reset filters functionality

### 3. Navigation
- Easy access from the "Add Walk-in Lead" page
- Direct link to view assigned leads
- Logout functionality

## Technical Implementation

### Backend (app.py)
- New route: `rec_assigned_leads()`
- Uses `@require_rec` decorator for authentication
- Fetches leads from `walkin_table` filtered by branch
- Groups leads by PS assignment
- Calculates statistics and computed fields

### Frontend (rec_assigned_leads.html)
- Responsive design with Bootstrap
- Interactive filtering and sorting
- Two view modes (all leads vs grouped by PS)
- Copy to clipboard functionality
- Status badges with color coding

### Data Structure
Leads are displayed with the following information:
- Customer name and email
- Mobile number
- PS assigned
- Model interested
- Lead category (Hot/Warm/Cold)
- Status (Pending/Won/Lost)
- Follow-up number
- Creation date
- Days since created

## Usage

### For Receptionists
1. Log in as a receptionist
2. Navigate to "Add Walk-in Lead" page
3. Click "View Assigned Leads" button
4. Use filters to find specific leads
5. Toggle between view modes as needed
6. Copy lead information for follow-up calls

### Access Control
- Only receptionist users can access this feature
- Leads are filtered by the receptionist's branch
- Only shows leads that have been assigned to PS users

## Future Enhancements
- Lead details modal/page
- Export functionality
- Real-time updates
- Advanced search capabilities
- Performance metrics for receptionists 