# Ather CRM System

An advanced Customer Relationship Management system built for Ather electric vehicle dealerships.

## Features

### Core CRM Features
- **Lead Management**: Track leads from multiple sources (Google, Meta, Affiliate, etc.)
- **User Management**: Separate roles for Admin, CRE (Customer Relationship Executive), and PS (Product Specialist)
- **Analytics Dashboard**: Comprehensive performance metrics and insights
- **Call Tracking**: Detailed call attempt history and follow-up management
- **Walk-in Customer Management**: Handle walk-in customers with quotation generation
- **Activity/Event Management**: Track leads from marketing events and activities

### 🧠 NEW: AI Agent (Powered by Google Gemini)
- **Intelligent Insights**: Get AI-powered analysis of your CRM data
- **Performance Analysis**: Analyze team performance and conversion rates
- **Strategic Recommendations**: Receive marketing and operational suggestions
- **Predictive Analytics**: Understand trends and forecasting
- **Natural Language Queries**: Ask complex business questions in plain English

## Quick Start

### 1. Installation
```bash
pip install -r requirements.txt
```

### 2. Environment Setup
Create a `.env` file with the following variables:

```env
# Supabase Configuration
SUPABASE_URL=your_supabase_url_here
SUPABASE_ANON_KEY=your_supabase_anon_key_here

# Flask Configuration
FLASK_SECRET_KEY=your_flask_secret_key_here

# AI Agent Configuration (NEW)
GEMINI_API_KEY=your_gemini_api_key_here

# Email Configuration (Optional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_USER=your_email@gmail.com
EMAIL_PASSWORD=your_app_password_here
```

### 3. Run the Application
```bash
python app.py
```

## AI Agent Setup

### Get a Free Gemini API Key
1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Create an API key
4. Add it to your `.env` file as `GEMINI_API_KEY`

### AI Agent Capabilities
- **Performance Analysis**: "Which CRE has the highest conversion rate?"
- **Strategic Insights**: "What marketing strategies should we focus on?"
- **Operational Insights**: "How can we improve our lead response time?"
- **Predictive Analysis**: "What trends should we watch for next quarter?"

For detailed setup instructions, see [AI_AGENT_SETUP.md](AI_AGENT_SETUP.md)

## User Roles

### Admin
- Complete system access
- User management (CRE and PS)
- Lead assignment and management
- Analytics and reporting
- **AI Agent access**
- Security audit and settings

### CRE (Customer Relationship Executive)
- Lead management for assigned leads
- Call tracking and follow-up
- Lead assignment to PS
- Performance dashboard

### PS (Product Specialist)
- Assigned lead management
- Walk-in customer handling
- Quotation generation
- Activity/event lead management

## System Architecture

- **Backend**: Flask (Python)
- **Database**: Supabase (PostgreSQL)
- **AI Engine**: Google Gemini Pro
- **Frontend**: Bootstrap 5, HTML5, JavaScript
- **Authentication**: Custom auth system with role-based access

## Data Models

### Lead Management
- `lead_master`: Main lead table
- `cre_users`: CRE user management
- `ps_users`: PS user management
- `ps_followup_master`: PS follow-up tracking

### Additional Features
- `walkin_customers`: Walk-in customer data
- `activity_leads`: Event/activity leads
- `cre_call_attempt_history`: CRE call tracking
- `ps_call_attempt_history`: PS call tracking

## API Endpoints

### AI Agent API
- `POST /ai_agent_api`: Generate AI insights
- `GET /ai_agent`: AI agent interface

### Core APIs
- `/admin_dashboard`: Admin dashboard
- `/analytics`: Analytics dashboard
- `/upload_data`: Data upload interface
- `/export_leads`: Lead export functionality

## Security Features

- Role-based access control
- Session management
- Password reset functionality
- Security audit logging
- Rate limiting on sensitive endpoints

## Development

### File Structure
```
ather_crm_system/
├── app.py                 # Main application
├── auth.py               # Authentication system
├── requirements.txt      # Dependencies
├── AI_AGENT_SETUP.md    # AI setup guide
├── templates/           # HTML templates
│   ├── ai_agent.html    # AI agent interface
│   ├── admin_dashboard.html
│   └── ...
├── static/             # Static files
└── uploads/           # File uploads
```

### Running in Development
```bash
export FLASK_ENV=development
python app.py
```

## Production Deployment

1. Set up environment variables
2. Configure Supabase database
3. Set up email SMTP (optional)
4. Configure Gemini API key
5. Deploy using gunicorn or similar WSGI server

## Support

For setup issues or questions:
1. Check the troubleshooting section in [AI_AGENT_SETUP.md](AI_AGENT_SETUP.md)
2. Review application logs
3. Verify environment configuration
4. Check Supabase connection and permissions

## License

This project is proprietary software for Ather dealership management.
