#!/bin/bash

# ===========================================
# Nutrition Agent Test Script
# ===========================================
# Quick tests for the Nutrition Agent microservice
# ===========================================

BASE_URL="http://localhost:8003"
TOKEN="local-dev-nutrition-token"

echo "======================================"
echo "Nutrition Agent Test Script"
echo "======================================"
echo ""

# Test 1: Health Check
echo "Test 1: Health Check"
echo "--------------------"
curl -s "${BASE_URL}/health" | jq .
echo ""
echo ""

# Test 2: Create Nutrition Profile
echo "Test 2: Create Nutrition Profile"
echo "---------------------------------"
curl -s -X POST "${BASE_URL}/v1/nutrition/profile" \
  -H "X-Internal-Service-Token: ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "dietary_preference": "omnivore",
    "activity_level": "moderate",
    "meals_per_day": 3,
    "age": 30,
    "gender": "female",
    "weight_kg": 70,
    "height_cm": 165
  }' | jq .
echo ""
echo ""

# Test 3: Evaluate Nutrition Status (Normal)
echo "Test 3: Evaluate Nutrition (Normal Query)"
echo "------------------------------------------"
curl -s -X POST "${BASE_URL}/v1/nutrition/evaluate" \
  -H "X-Internal-Service-Token: ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "message": "I want to eat healthier and lose some weight",
    "profile": {
      "fitness_goal": "weight_loss"
    }
  }' | jq .
echo ""
echo ""

# Test 4: Evaluate Nutrition (Eating Disorder Keywords - Should Escalate)
echo "Test 4: Evaluate Nutrition (Eating Disorder Keywords - Should Escalate)"
echo "------------------------------------------------------------------------"
curl -s -X POST "${BASE_URL}/v1/nutrition/evaluate" \
  -H "X-Internal-Service-Token: ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "message": "I am afraid to eat and feel guilty after meals",
    "profile": {}
  }' | jq .
echo ""
echo ""

# Test 5: Log a Meal
echo "Test 5: Log a Meal"
echo "------------------"
curl -s -X POST "${BASE_URL}/v1/nutrition/meal-logs" \
  -H "X-Internal-Service-Token: ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "meal_type": "breakfast",
    "description": "Oatmeal with berries and almonds",
    "calories": 350,
    "protein_g": 12,
    "carbs_g": 55,
    "fat_g": 10
  }' | jq .
echo ""
echo ""

# Test 6: Get Nutrition History
echo "Test 6: Get Nutrition History"
echo "------------------------------"
curl -s "${BASE_URL}/v1/nutrition/history/1" \
  -H "X-Internal-Service-Token: ${TOKEN}" | jq .
echo ""
echo ""

# Test 7: Invalid Token (Should Fail)
echo "Test 7: Invalid Token (Should Return 401)"
echo "------------------------------------------"
curl -s -w "\nHTTP Status: %{http_code}\n" "${BASE_URL}/health" \
  -H "X-Internal-Service-Token: invalid-token"
echo ""
echo ""

echo "======================================"
echo "Tests Complete!"
echo "======================================"
