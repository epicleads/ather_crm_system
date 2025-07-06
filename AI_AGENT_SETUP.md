# AI Agent Setup Guide for Ather CRM

## Overview
The AI Agent is a powerful feature that provides intelligent insights and recommendations based on your CRM data. It uses Google's Gemini AI model to analyze your leads, customer data, and sales performance to answer complex business questions.

## Features
- **Performance Analysis**: Analyze CRE and PS performance, conversion rates, and team efficiency
- **Strategic Insights**: Get recommendations for marketing strategies and lead optimization
- **Operational Insights**: Identify training needs and operational improvements
- **Predictive Analysis**: Understand trends and forecasting

## Setup Instructions

### 1. Get a Free Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Choose "Create API key in new project" or select an existing project
5. Copy the generated API key

### 2. Configure Your Environment

Add the following to your `.env` file:

```env
# AI Agent Configuration
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. Install Dependencies

The required dependency is already included in `requirements.txt`:
```
google-generativeai==0.3.2
```

Make sure to install it:
```bash
pip install -r requirements.txt
```

### 4. Restart Your Application

After adding the API key, restart your Flask application:
```bash
python app.py
```

## Usage

### Accessing the AI Agent

1. Log in as an admin user
2. Go to Admin Dashboard
3. Click on "AI Agent" in the Analytics & Reports section

### Sample Questions You Can Ask

**Performance Analysis:**
- Which CRE has the highest conversion rate and why?
- What's the performance comparison between different branches?
- Which lead source provides the best quality leads?
- How effective are our Product Specialists?

**Strategic Insights:**
- What marketing strategies should we focus on based on our data?
- How can we improve our overall conversion rates?
- Which models should we promote more aggressively?
- What's the best approach to lead nurturing?

**Operational Insights:**
- Which team members might need additional training?
- How can we optimize our lead assignment process?
- What's our average response time to leads?
- How can we improve our follow-up processes?

**Predictive Analysis:**
- What trends should we watch in the coming months?
- How can we predict lead quality better?
- What's the forecast for our sales pipeline?
- Which customer segments have the highest potential?

## API Usage

You can also use the AI Agent programmatically via the API endpoint:

```bash
curl -X POST http://your-domain.com/ai_agent_api \
  -H "Content-Type: application/json" \
  -d '{"question": "Which lead source has the highest conversion rate?"}'
```

## Troubleshooting

### Common Issues

1. **"AI service not configured" error**
   - Ensure GEMINI_API_KEY is set in your .env file
   - Verify the API key is valid and not expired
   - Restart your application after adding the key

2. **"Error loading CRM data" error**
   - Check your Supabase connection
   - Ensure your database tables have data
   - Verify table permissions in Supabase

3. **Slow response times**
   - This is normal for AI processing
   - Large datasets may take 10-30 seconds to analyze
   - Consider optimizing your database queries

### API Rate Limits

The free Gemini API has the following limits:
- 15 requests per minute
- 1,500 requests per day
- 1 million tokens per minute

For production use, consider upgrading to a paid plan.

## Security Notes

- Never share your API key publicly
- Store the API key securely in environment variables
- Consider using API key rotation for production environments
- Monitor your API usage to avoid unexpected charges

## Data Privacy

- The AI Agent processes your CRM data to generate insights
- Data is sent to Google's Gemini API for processing
- Ensure compliance with your data privacy policies
- Consider data anonymization for sensitive information

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the Flask application logs
3. Verify your API key and configuration
4. Contact your system administrator

## Advanced Configuration

### Custom Prompts

You can modify the AI prompts in `app.py` in the `generate_ai_insight` function to customize the AI's responses for your specific business needs.

### Additional Models

The system uses `gemini-pro` by default. You can experiment with other models by modifying the model initialization in `app.py`.

### Data Filtering

You can customize which data is included in the AI analysis by modifying the `get_crm_data_summary` function in `app.py`. 