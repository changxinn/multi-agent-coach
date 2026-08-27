# ===========================================
# Nutrition Agent Test Script (PowerShell)
# ===========================================
# Quick tests for the Nutrition Agent microservice
# ===========================================

$BASE_URL = "http://localhost:8003"
$TOKEN = "local-dev-nutrition-token"

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Nutrition Agent Test Script" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Test 1: Health Check
Write-Host "Test 1: Health Check" -ForegroundColor Yellow
Write-Host "--------------------" -ForegroundColor Gray
try {
    $response = Invoke-RestMethod -Uri "${BASE_URL}/health" -Method Get
    $response | ConvertTo-Json
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}
Write-Host ""
Write-Host ""

# Test 2: Create Nutrition Profile
Write-Host "Test 2: Create Nutrition Profile" -ForegroundColor Yellow
Write-Host "---------------------------------" -ForegroundColor Gray
try {
    $body = @{
        user_id = 1
        dietary_preference = "omnivore"
        activity_level = "moderate"
        meals_per_day = 3
        age = 30
        gender = "female"
        weight_kg = 70
        height_cm = 165
    } | ConvertTo-Json

    $response = Invoke-RestMethod -Uri "${BASE_URL}/v1/nutrition/profile" `
        -Method Post `
        -Headers @{"X-Internal-Service-Token" = $TOKEN} `
        -ContentType "application/json" `
        -Body $body
    $response | ConvertTo-Json
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}
Write-Host ""
Write-Host ""

# Test 3: Evaluate Nutrition Status (Normal)
Write-Host "Test 3: Evaluate Nutrition (Normal Query)" -ForegroundColor Yellow
Write-Host "------------------------------------------" -ForegroundColor Gray
try {
    $body = @{
        user_id = 1
        message = "I want to eat healthier and lose some weight"
        profile = @{
            fitness_goal = "weight_loss"
        }
    } | ConvertTo-Json

    $response = Invoke-RestMethod -Uri "${BASE_URL}/v1/nutrition/evaluate" `
        -Method Post `
        -Headers @{"X-Internal-Service-Token" = $TOKEN} `
        -ContentType "application/json" `
        -Body $body
    $response | ConvertTo-Json
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}
Write-Host ""
Write-Host ""

# Test 4: Evaluate Nutrition (Eating Disorder Keywords - Should Escalate)
Write-Host "Test 4: Evaluate Nutrition (Eating Disorder - Should Escalate)" -ForegroundColor Yellow
Write-Host "----------------------------------------------------------------" -ForegroundColor Gray
try {
    $body = @{
        user_id = 1
        message = "I am afraid to eat and feel guilty after meals"
        profile = @{}
    } | ConvertTo-Json

    $response = Invoke-RestMethod -Uri "${BASE_URL}/v1/nutrition/evaluate" `
        -Method Post `
        -Headers @{"X-Internal-Service-Token" = $TOKEN} `
        -ContentType "application/json" `
        -Body $body
    $response | ConvertTo-Json
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}
Write-Host ""
Write-Host ""

# Test 5: Log a Meal
Write-Host "Test 5: Log a Meal" -ForegroundColor Yellow
Write-Host "------------------" -ForegroundColor Gray
try {
    $body = @{
        user_id = 1
        meal_type = "breakfast"
        description = "Oatmeal with berries and almonds"
        calories = 350
        protein_g = 12
        carbs_g = 55
        fat_g = 10
    } | ConvertTo-Json

    $response = Invoke-RestMethod -Uri "${BASE_URL}/v1/nutrition/meal-logs" `
        -Method Post `
        -Headers @{"X-Internal-Service-Token" = $TOKEN} `
        -ContentType "application/json" `
        -Body $body
    $response | ConvertTo-Json
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}
Write-Host ""
Write-Host ""

# Test 6: Get Nutrition History
Write-Host "Test 6: Get Nutrition History" -ForegroundColor Yellow
Write-Host "------------------------------" -ForegroundColor Gray
try {
    $response = Invoke-RestMethod -Uri "${BASE_URL}/v1/nutrition/history/1" `
        -Method Get `
        -Headers @{"X-Internal-Service-Token" = $TOKEN}
    $response | ConvertTo-Json
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}
Write-Host ""
Write-Host ""

# Test 7: Invalid Token (Should Fail)
Write-Host "Test 7: Invalid Token (Should Return 401)" -ForegroundColor Yellow
Write-Host "------------------------------------------" -ForegroundColor Gray
try {
    $response = Invoke-RestMethod -Uri "${BASE_URL}/health" `
        -Method Get `
        -Headers @{"X-Internal-Service-Token" = "invalid-token"}
    $response | ConvertTo-Json
} catch {
    Write-Host "Expected error (401): $_" -ForegroundColor Green
}
Write-Host ""
Write-Host ""

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Tests Complete!" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
