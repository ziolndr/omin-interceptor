#!/usr/bin/env python3
"""
OMIN API SERVICE
FastAPI wrapper for ARBITER Doctrine Service
Exposes HTTP endpoints for the web demo

Usage:
    pip install fastapi uvicorn
    uvicorn omin_api:app --host 0.0.0.0 --port 8001 --reload

Created by: Joel Trout
For: Brave1 / Ukrainian Armed Forces
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
import time

# Import the doctrine service
from doctrine_service_multilayer import (
    ThreatInput, AvailableSystem, OperationalConstraints,
    ARBITERDoctrineService, ThreatType, SystemType, TargetPriority
)

app = FastAPI(
    title="Omin API Service",
    description="Multi-layer air defense decision support API",
    version="2.0"
)

# Enable CORS for web demo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# PYDANTIC MODELS FOR API
# ============================================================================

class ThreatInputAPI(BaseModel):
    threat_type: str = Field(..., description="Threat type (e.g., 'Shahed-136')")
    count: int = Field(..., ge=1, description="Number of threats")
    range_km: float = Field(..., ge=0, description="Range in kilometers")
    bearing: int = Field(..., ge=0, le=360, description="Bearing in degrees")
    altitude_m: int = Field(..., ge=0, description="Altitude in meters")
    speed_kmh: float = Field(..., ge=0, description="Speed in km/h")
    target_description: str = Field(..., description="Description of target")
    target_priority: str = Field(..., description="Target priority (Критичний/Високий/Середній/Низький)")
    time_to_impact_minutes: Optional[float] = None

class AvailableSystemAPI(BaseModel):
    system_type: str = Field(..., description="System type (e.g., 'IRIS-T')")
    count: int = Field(..., ge=1)
    missiles_available: int = Field(..., ge=0)
    cost_per_shot: int = Field(..., ge=0)
    effective_range_km: float = Field(..., ge=0)
    success_rate: float = Field(..., ge=0, le=1)
    reload_time_minutes: int = Field(..., ge=0)
    status: str = Field(default="READY")
    setup_time_minutes: int = Field(default=0)
    weather_dependent: bool = Field(default=False)
    requires_visual: bool = Field(default=False)

class OperationalConstraintsAPI(BaseModel):
    limited_ammunition: bool = True
    friendly_forces_nearby: bool = False
    civilian_areas_nearby: bool = False
    weather_conditions: str = "Nominal"
    expected_follow_on_waves: int = 0
    resupply_time_hours: int = 24

class BatteryRequest(BaseModel):
    threat: ThreatInputAPI
    systems: List[AvailableSystemAPI]
    constraints: OperationalConstraintsAPI
    commander_context: str = Field(default="", description="Optional commander context")

class RecommendationResponse(BaseModel):
    rank: int
    coherence: float
    title: str
    description: str
    template_id: str
    estimated_cost: int
    estimated_success_rate: float
    systems_used: List[str]
    recommendation_level: str

class BatteryResponse(BaseModel):
    success: bool
    generation_time_ms: float
    arbiter_latency_ms: float
    total_time_ms: float
    options_generated: int
    ranked_recommendations: List[RecommendationResponse]
    threat_summary: Dict[str, Any]
    error: Optional[str] = None

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def convert_threat_type(threat_str: str) -> ThreatType:
    """Convert string to ThreatType enum"""
    mapping = {
        "Shahed-136": ThreatType.SHAHED_136,
        "Shahed-131": ThreatType.SHAHED_131,
        "Geran-2": ThreatType.GERAN_2,
        "Lancet": ThreatType.LANCET,
        "FPV": ThreatType.FPV,
        "Orlan-10": ThreatType.ORLAN,
    }
    return mapping.get(threat_str, ThreatType.UNKNOWN)

def convert_system_type(system_str: str) -> SystemType:
    """Convert string to SystemType enum"""
    mapping = {
        "Patriot": SystemType.PATRIOT,
        "IRIS-T": SystemType.IRIS_T,
        "Buk-M1": SystemType.BUK_M1,
        "Stinger": SystemType.STINGER,
        "Igla": SystemType.IGLA,
        "Vampire Interceptor Drone": SystemType.INTERCEPTOR_DRONE,
        "Mobile Firing Group (ЗУ-23-2)": SystemType.MOBILE_GROUP,
        "Mi-8 Helicopter System": SystemType.HELICOPTER,
        "ЗУ-23-2": SystemType.ZU_23,
        "РЕБ Буковель": SystemType.BUKOVEL,
    }
    return mapping.get(system_str, SystemType.ZU_23)  # Default fallback

def convert_target_priority(priority_str: str) -> TargetPriority:
    """Convert string to TargetPriority enum"""
    mapping = {
        "Критичний": TargetPriority.CRITICAL,
        "Високий": TargetPriority.HIGH,
        "Середній": TargetPriority.MEDIUM,
        "Низький": TargetPriority.LOW,
    }
    return mapping.get(priority_str, TargetPriority.MEDIUM)

def api_to_doctrine_models(request: BatteryRequest) -> tuple:
    """Convert API models to Doctrine Service models"""
    
    # Convert threat
    threat = ThreatInput(
        threat_type=convert_threat_type(request.threat.threat_type),
        count=request.threat.count,
        range_km=request.threat.range_km,
        bearing=request.threat.bearing,
        altitude_m=request.threat.altitude_m,
        speed_kmh=request.threat.speed_kmh,
        target_description=request.threat.target_description,
        target_priority=convert_target_priority(request.threat.target_priority),
        time_to_impact_minutes=request.threat.time_to_impact_minutes
    )
    
    # Convert systems
    systems = []
    for sys_api in request.systems:
        systems.append(AvailableSystem(
            system_type=convert_system_type(sys_api.system_type),
            count=sys_api.count,
            missiles_available=sys_api.missiles_available,
            cost_per_shot=sys_api.cost_per_shot,
            effective_range_km=sys_api.effective_range_km,
            success_rate=sys_api.success_rate,
            reload_time_minutes=sys_api.reload_time_minutes,
            status=sys_api.status,
            setup_time_minutes=sys_api.setup_time_minutes,
            weather_dependent=sys_api.weather_dependent,
            requires_visual=sys_api.requires_visual
        ))
    
    # Convert constraints
    constraints = OperationalConstraints(
        limited_ammunition=request.constraints.limited_ammunition,
        friendly_forces_nearby=request.constraints.friendly_forces_nearby,
        civilian_areas_nearby=request.constraints.civilian_areas_nearby,
        weather_conditions=request.constraints.weather_conditions,
        expected_follow_on_waves=request.constraints.expected_follow_on_waves,
        resupply_time_hours=request.constraints.resupply_time_hours
    )
    
    return threat, systems, constraints

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Omin API",
        "status": "operational",
        "version": "2.0",
        "endpoints": [
            "/v1/battery - Process battery-level tactical scenario",
            "/health - Service health check"
        ]
    }

@app.get("/health")
async def health():
    """Detailed health check"""
    # TODO: Check ARBITER service connectivity
    return {
        "status": "healthy",
        "arbiter_service": "connected",  # Should actually check
        "doctrine_templates": 6,
        "timestamp": time.time()
    }

@app.post("/v1/battery", response_model=BatteryResponse)
async def process_battery_scenario(request: BatteryRequest):
    """
    Process a battery-level tactical scenario and return ranked recommendations.
    
    This endpoint:
    1. Accepts threat parameters, available systems, and constraints
    2. Generates tactical options using doctrine templates
    3. Evaluates options with ARBITER for semantic coherence
    4. Returns ranked recommendations
    """
    
    try:
        # Convert API models to Doctrine Service models
        threat, systems, constraints = api_to_doctrine_models(request)
        
        # Initialize doctrine service
        # TODO: Make ARBITER URL configurable via environment variable
        service = ARBITERDoctrineService(arbiter_url="http://0.0.0.0:8000/v1/compare")
        
        # Process scenario
        result = service.process_battery_situation(
            threat=threat,
            systems=systems,
            constraints=constraints,
            commander_context=request.commander_context
        )
        
        if not result['success']:
            raise HTTPException(
                status_code=500,
                detail=result.get('error', 'Doctrine service processing failed')
            )
        
        # Convert to response format
        recommendations = [
            RecommendationResponse(
                rank=rec['rank'],
                coherence=rec['coherence'],
                title=rec['title'],
                description=rec['description'],
                template_id=rec['template_id'],
                estimated_cost=rec['estimated_cost'],
                estimated_success_rate=rec['estimated_success_rate'],
                systems_used=rec['systems_used'],
                recommendation_level=rec['recommendation_level']
            )
            for rec in result['ranked_recommendations']
        ]
        
        return BatteryResponse(
            success=True,
            generation_time_ms=result['generation_time_ms'],
            arbiter_latency_ms=result['arbiter_latency_ms'],
            total_time_ms=result['total_time_ms'],
            options_generated=result['options_generated'],
            ranked_recommendations=recommendations,
            threat_summary=result['threat_summary']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

# ============================================================================
# CONVENIENCE ENDPOINTS FOR TESTING
# ============================================================================

@app.get("/api/templates")
async def list_templates():
    """List available doctrine templates"""
    from doctrine_service_multilayer import BatteryDoctrine
    
    templates = []
    for template_id, template_def in BatteryDoctrine.TEMPLATES.items():
        templates.append({
            "id": template_id,
            "title": template_def['title']
        })
    
    return {
        "count": len(templates),
        "templates": templates
    }

@app.get("/api/system-specs")
async def get_system_specs():
    """Get system specifications for reference"""
    from doctrine_service_multilayer import SYSTEM_SPECS
    
    specs = {}
    for system_type, spec in SYSTEM_SPECS.items():
        specs[system_type.value] = spec
    
    return specs

@app.post("/api/validate-odesa")
async def validate_odesa_scenario():
    """
    Run the October 19, 2024 Odesa validation scenario.
    This demonstrates what Omin would have recommended vs what was actually done.
    """
    
    # Define the actual scenario
    request = BatteryRequest(
        threat=ThreatInputAPI(
            threat_type="Shahed-136",
            count=5,  # 2 port + 3 power
            range_km=25.0,
            bearing=45,
            altitude_m=1200,
            speed_kmh=185,
            target_description="Порт та електростанція (КРИТИЧНІ)",
            target_priority="Критичний"
        ),
        systems=[
            AvailableSystemAPI(
                system_type="IRIS-T",
                count=2,
                missiles_available=6,
                cost_per_shot=500000,
                effective_range_km=40,
                success_rate=0.93,
                reload_time_minutes=720
            ),
            AvailableSystemAPI(
                system_type="Buk-M1",
                count=1,
                missiles_available=3,
                cost_per_shot=100000,
                effective_range_km=35,
                success_rate=0.85,
                reload_time_minutes=480
            ),
            AvailableSystemAPI(
                system_type="Stinger",
                count=4,
                missiles_available=8,
                cost_per_shot=40000,
                effective_range_km=5,
                success_rate=0.70,
                reload_time_minutes=120
            ),
            AvailableSystemAPI(
                system_type="Vampire Interceptor Drone",
                count=4,
                missiles_available=4,
                cost_per_shot=5000,
                effective_range_km=20,
                success_rate=0.60,
                reload_time_minutes=30
            ),
            AvailableSystemAPI(
                system_type="Mobile Firing Group (ЗУ-23-2)",
                count=2,
                missiles_available=2,
                cost_per_shot=500,
                effective_range_km=2.5,
                success_rate=0.35,
                reload_time_minutes=15,
                setup_time_minutes=15
            ),
            AvailableSystemAPI(
                system_type="Mi-8 Helicopter System",
                count=1,
                missiles_available=1,
                cost_per_shot=2000,
                effective_range_km=10,
                success_rate=0.50,
                reload_time_minutes=90,
                weather_dependent=True
            )
        ],
        constraints=OperationalConstraintsAPI(
            limited_ammunition=True,
            weather_conditions="Marginal",
            expected_follow_on_waves=2,
            resupply_time_hours=24
        ),
        commander_context="Odesa sector, October 19, 2024 validation"
    )
    
    # Process scenario
    result = await process_battery_scenario(request)
    
    # Add comparison data
    actual_result = {
        "actual_cost_euros": 2_600_000,
        "actual_cost_usd": 2_730_000,  # Approximate conversion
        "actual_kills": 9,
        "actual_total": 12,
        "actual_success_rate": 75,
        "systems_used": ["4x IRIS-T", "2x Buk", "1x Helicopter", "Mobile groups"]
    }
    
    if result.ranked_recommendations:
        top_rec = result.ranked_recommendations[0]
        savings = actual_result['actual_cost_usd'] - top_rec.estimated_cost
        
        comparison = {
            "omin_recommendation": {
                "cost": top_rec.estimated_cost,
                "predicted_success": top_rec.estimated_success_rate,
                "systems": top_rec.systems_used
            },
            "actual_execution": actual_result,
            "analysis": {
                "cost_difference_usd": savings,
                "cost_savings_percent": round((savings / actual_result['actual_cost_usd']) * 100, 1) if savings > 0 else 0,
                "success_rate_comparison": f"Predicted: {top_rec.estimated_success_rate}% vs Actual: {actual_result['actual_success_rate']}%"
            }
        }
        
        return {
            **result.dict(),
            "validation": comparison
        }
    
    return result

# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    print("""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                              OMIN API SERVICE                                         ║
║                                                                                       ║
║  Starting FastAPI server on http://0.0.0.0:8001                                      ║
║  API Documentation: http://0.0.0.0:8001/docs                                         ║
║                                                                                       ║
║  Endpoints:                                                                           ║
║    POST /v1/battery         - Process tactical scenario                             ║
║    POST /api/validate-odesa  - Run October 19 validation                             ║
║    GET  /api/templates       - List doctrine templates                               ║
║    GET  /api/system-specs    - Get system specifications                             ║
║                                                                                       ║
║  Requirements:                                                                        ║
║    - ARBITER service running on http://0.0.0.0:8000                                  ║
║    - doctrine_service_multilayer.py in same directory                                ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "omin_api:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )
