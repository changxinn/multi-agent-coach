# Nutrition Agent Microservice

FastAPI microservice providing nutrition coaching assessments for the Multi-Agent Fitness Coach system.

## Overview

The Nutrition Agent handles:
- Meal planning and macronutrient optimization
- Dietary guidance based on user preferences and restrictions
- TDEE (Total Daily Energy Expenditure) calculation
- Food database queries (USDA FoodData Central API)
- Meal logging and adherence tracking
- Ethical safeguards and medical disclaimers

## Architecture

```
┌─────────────────┐
│  Main API       │
│  (port 8000)    │
│  LangGraph      │
└────────┬────────┘
         │ HTTP (internal token auth)
         ↓
┌─────────────────┐
│ Nutrition Agent │
│  (port 8003)    │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  PostgreSQL     │
│  (systemdb)     │
└─────────────────┘
```

## Quick Start

### Local Development

1. **Start dependencies** (from project root):
   ```bash
   docker-compose up -d db
   ```

2. **Set environment variables**:
   ```bash
   # In .env file
   USE_NUTRITION_AGENT_SERVICE=true
   NUTRITION_AGENT_URL=http://localhost:8003
   INTERNAL_SERVICE_TOKEN=local-dev-nutrition-token
   ```

3. **Run migrations** (automatic on startup):
   ```bash
   # Migrations 004 and 005 create nutrition tables
   ```

4. **Start nutrition agent**:
   ```bash
   cd services/nutrition_agent
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8003
   ```

### Docker Deployment

```bash
docker-compose up -d nutrition-agent
```

## API Endpoints

All endpoints require `X-Internal-Service-Token` header.

### Health Check
```http
GET /health
```

### Evaluate Nutrition Status
```http
POST /v1/nutrition/evaluate
Content-Type: application/json
X-Internal-Service-Token: local-dev-nutrition-token

{
  "user_id": 1,
  "message": "I want to lose weight",
  "profile": {
    "fitness_goal": "weight_loss",
    "weight_kg": 70,
    "gender": "female"
  }
}
```

### Create/Update Profile
```http
POST /v1/nutrition/profile
Content-Type: application/json

{
  "user_id": 1,
  "dietary_preference": "omnivore",
  "activity_level": "moderate",
  "meals_per_day": 3
}
```

### Log Meal
```http
POST /v1/nutrition/meal-logs
Content-Type: application/json

{
  "user_id": 1,
  "meal_type": "breakfast",
  "description": "Oatmeal with berries and almonds",
  "calories": 350,
  "protein_g": 12,
  "carbs_g": 55,
  "fat_g": 10
}
```

### Get History
```http
GET /v1/nutrition/history/1
```

## Tools

### 1. TDEE Calculator
Uses Mifflin-St Jeor equation (most accurate per research):
- **Men**: BMR = (10 × weight_kg) + (6.25 × height_cm) - (5 × age) + 5
- **Women**: BMR = (10 × weight_kg) + (6.25 × height_cm) - (5 × age) - 161

Activity multipliers:
- sedentary: 1.2
- light: 1.375
- moderate: 1.55
- active: 1.725
- very_active: 1.9

### 2. Macro Targets
Evidence-based ratios:
- **Weight loss**: TDEE - 500 kcal, protein 2.0g/kg, fat 0.8g/kg
- **Maintenance**: TDEE, protein 1.6g/kg, fat 1.0g/kg
- **Muscle gain**: TDEE + 250 kcal, protein 2.2g/kg, fat 1.0g/kg

### 3. Food Database
- **Primary**: USDA FoodData Central API (300,000+ foods)
- **Fallback**: Local cache (200 common foods)
- **API Key**: `fqdZaUBgSbdb10QEp9QMbCqhAVke1VRzecNmRKkK`

### 4. Meal Planner
Generates meal suggestions aligned with macro targets and dietary preferences.

### 5. Meal Logger
Tracks meals with optional macro breakdown.

## Ethical Safeguards

### Escalation Triggers

1. **Medical Risk Symptoms** → Immediate escalation
   - Chest pain, difficulty breathing, fainting, etc.

2. **Eating Disorder Keywords** → Immediate escalation
   - "starving myself", "purging", "afraid to eat", etc.

3. **BMI < 18.5 or > 40** → Professional referral recommended

4. **Calories < 1200 (F) or < 1500 (M)** → Red status with warning

5. **Weight loss > 1.5 kg/week** → Amber warning

### Medical Disclaimer

All responses include:
> *All nutrition advice is for general informational purposes only and does not constitute medical advice. Consult a healthcare provider before making significant dietary changes.*

Escalate status adds:
> *⚠️ **Important**: This system cannot diagnose or treat eating disorders. Please consult a healthcare provider or contact the National Eating Disorders Association (NEDA) Helpline at 1-800-931-2237 for confidential support.*

## Database Schema

### Tables (systemdb schema)

1. **nutrition_profiles**
   - User preferences, demographics, activity level

2. **meal_logs**
   - Daily meal tracking with optional macros

3. **nutrition_assessments**
   - Assessment history with tool traces

4. **food_cache**
   - 200 common foods from USDA database

## Configuration

### Environment Variables

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/systemdb
DATABASE_SCHEMA=systemdb
INTERNAL_SERVICE_TOKEN=local-dev-nutrition-token
NUTRITION_LLM_ENABLED=false
OPENAI_API_KEY=sk-...
USDA_FDC_API_KEY=fqdZaUBgSbdb10QEp9QMbCqhAVke1VRzecNmRKkK
```

## Testing

### Run Tests
```bash
cd services/nutrition_agent
pytest tests/ -v
```

### Test Endpoints
```bash
# Health check
curl http://localhost:8003/health

# Evaluate (requires token)
curl -X POST http://localhost:8003/v1/nutrition/evaluate \
  -H "X-Internal-Service-Token: local-dev-nutrition-token" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "message": "I want to eat healthier", "profile": {}}'
```

## Development Status

- ✅ Database migrations (004, 005)
- ✅ TDEE calculator
- ✅ Macro targets calculator
- ✅ USDA FoodData Central integration
- ✅ Meal planner (basic templates)
- ✅ Meal logger
- ✅ Ethical safeguards
- ✅ LLM presentation layer (disabled by default)
- ✅ FastAPI endpoints
- ✅ Docker deployment
- ⏳ Integration tests
- ⏳ Load testing

## License

Part of the Multi-Agent Fitness Coach project.

## Support

For issues or questions, contact the development team.
