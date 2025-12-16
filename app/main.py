"""FastAPI application entry point."""
from fastapi import FastAPI, UploadFile, File, Depends, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from typing import Optional

from app.database import engine, Base, get_db
from app.models import LeafLog, Plant, Garden
from app.ml_engine import process_image

# Initialize FastAPI app
app = FastAPI(
    title="Smart Garden Manager v2",
    description="Garden monitoring with spatial mapping based in YOLOv11-seg",
    version="2.0.0"
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory="app/templates")


# Startup event: Create tables
@app.on_event("startup")
async def startup_event():
    """Create database tables on startup."""
    from sqlalchemy.orm import selectinload
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables created successfully (Garden, Plant, LeafLog)")
    
    # Create default garden if none exists
    async with AsyncSession(engine) as db:
        result = await db.execute(select(Garden))
        gardens = result.scalars().all()
        
        if not gardens:
            default_garden = Garden(
                name="Garden Utama",
                rows=4,
                cols=4,
                description="Garden default 4×4",
                is_active=True
            )
            db.add(default_garden)
            await db.commit()
            print("✅ Created default garden: Garden Utama (4×4)")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check for Docker."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# Dashboard page (NEW: Garden Grid Layout with Multi-Garden Support)
@app.get("/", response_class=HTMLResponse)
async def dashboard(
    garden_id: int = None,  # Optional garden selection
    request: Request = None,
    db: AsyncSession = Depends(get_db)
):
    """Main dashboard with Garden Grid Map."""
    from sqlalchemy.orm import selectinload
    
    # Load active garden or specified garden
    if garden_id:
        result = await db.execute(
            select(Garden)
            .options(selectinload(Garden.plants))
            .where(Garden.id == garden_id)
        )
        garden = result.scalar_one_or_none()
    else:
        # Get active garden
        result = await db.execute(
            select(Garden)
            .options(selectinload(Garden.plants))
            .where(Garden.is_active == True)
        )
        garden = result.scalar_one_or_none()
        
        # Fallback to first garden if none active
        if not garden:
            result = await db.execute(
                select(Garden)
                .options(selectinload(Garden.plants))
                .order_by(Garden.created_at)
                .limit(1)
            )
            garden = result.scalar_one_or_none()
    
    # Load all gardens for selector
    result = await db.execute(select(Garden).order_by(Garden.created_at))
    all_gardens = result.scalars().all()
    
    # Create grid dictionary: {(x, y): plant}
    plants_grid = {}
    if garden:
        for plant in garden.plants:
            plants_grid[(plant.grid_x, plant.grid_y)] = plant
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "garden": garden,
            "all_gardens": all_gardens,
            "plants_grid": plants_grid,
            "plant": None,  # Initially no plant selected
            "latest_scan": None,
            "now": datetime.now(timezone.utc)
        }
    )


# Guide page
@app.get("/guide", response_class=HTMLResponse)
async def guide(request: Request):
    """User guide page."""
    return templates.TemplateResponse(
        "guide.html",
        {"request": request}
    )


# History page
@app.get("/history", response_class=HTMLResponse)
async def history(
    request: Request, 
    db: AsyncSession = Depends(get_db)
):
    """Display scan history with client-side pagination, filters, and search."""
    from sqlalchemy.orm import selectinload
    
    # Get all scans (limit to recent 500 for performance)
    query = select(LeafLog).options(selectinload(LeafLog.plant)).order_by(LeafLog.created_at.desc()).limit(500)
    result = await db.execute(query)
    scans = result.scalars().all()
    
    # Serialize scans for client-side use
    scans_data = []
    for scan in scans:
        scans_data.append({
            "id": scan.id,
            "plant_name": scan.plant.name if scan.plant else "Unknown",
            "plant_id": scan.plant_id,
            "created_at": scan.created_at.isoformat(),
            "leaf_area_cm2": scan.leaf_area_cm2,
            "coin_detected": scan.coin_detected,
            "segmented_image_path": scan.segmented_image_path
        })

    # Get all plants for filter dropdown
    plants_result = await db.execute(select(Plant).order_by(Plant.name))
    all_plants = plants_result.scalars().all()
    
    return templates.TemplateResponse(
        "history.html",
        {
            "request": request,
            "scans_json": scans_data,
            "all_plants": all_plants
        }
    )


# Scan API endpoint
@app.post("/api/scan")
async def scan_leaf(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Process uploaded image and save results."""
    try:
        # Read image bytes
        image_bytes = await file.read()
        
        # Process with YOLO
        result = process_image(image_bytes, save_dir="app/static/uploads")
        
        if not result["success"]:
            return JSONResponse(
                status_code=400,
                content={"error": result.get("message", "Processing failed")}
            )
        
        # Construct the URL for the segmented image
        segmented_image_url = f"/static/{result['image_paths']['segmented']}"
        
        # Save to database
        leaf_log = LeafLog(
            plant_id=plant_id,
            leaf_area_cm2=result["total_leaf_area_cm2"],
            coin_detected=result["coin_detected"],
            segmented_image_path=segmented_image_url
        )
        db.add(leaf_log)
        await db.commit()
        await db.refresh(leaf_log)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "id": leaf_log.id,
                "leaf_area_cm2": leaf_log.leaf_area_cm2,
                "coin_detected": leaf_log.coin_detected,
                "segmented_image": f"/static/{result['image_paths']['segmented']}",
                "created_at": leaf_log.created_at.isoformat()
            }
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


# ===== GARDEN MANAGEMENT API ENDPOINTS =====

# List all gardens
@app.get("/api/gardens")
async def list_gardens(db: AsyncSession = Depends(get_db)):
    """Get all gardens."""
    result = await db.execute(select(Garden).order_by(Garden.created_at))
    gardens = result.scalars().all()
    
    return [
        {
            "id": g.id,
            "name": g.name,
            "rows": g.rows,
            "cols": g.cols,
            "description": g.description,
            "is_active": g.is_active,
            "plant_count": len(g.plants),
            "created_at": g.created_at.isoformat()
        }
        for g in gardens
    ]


# Create new garden
@app.post("/api/gardens")
async def create_garden(
    name: str = Form(...),
    rows: int = Form(4),
    cols: int = Form(4),
    description: str = Form(None),
    set_active: bool = Form(False),
    db: AsyncSession = Depends(get_db)
):
    """Create a new garden."""
    try:
        # If set_active, deactivate others
        if set_active:
            await db.execute(
                select(Garden).where(Garden.is_active == True)
            )
            result = await db.execute(select(Garden).where(Garden.is_active == True))
            for g in result.scalars().all():
                g.is_active = False
        
        garden = Garden(
            name=name,
            rows=rows,
            cols=cols,
            description=description,
            is_active=set_active
        )
        db.add(garden)
        await db.commit()
        await db.refresh(garden)
        
        return {"success": True, "garden_id": garden.id}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


# Get active garden
@app.get("/api/gardens/active")
async def get_active_garden(db: AsyncSession = Depends(get_db)):
    """Get currently active garden."""
    from sqlalchemy.orm import selectinload
    
    result = await db.execute(
        select(Garden)
        .options(selectinload(Garden.plants))
        .where(Garden.is_active == True)
    )
    garden = result.scalar_one_or_none()
    
    if not garden:
        # Fallback to first garden
        result = await db.execute(
            select(Garden)
            .options(selectinload(Garden.plants))
            .order_by(Garden.created_at)
            .limit(1)
        )
        garden = result.scalar_one_or_none()
    
    if not garden:
        return JSONResponse(
            status_code=404,
            content={"error": "No gardens found"}
        )
    
    return {
        "id": garden.id,
        "name": garden.name,
        "rows": garden.rows,
        "cols": garden.cols,
        "description": garden.description,
        "is_active": garden.is_active,
        "plant_count": len(garden.plants)
    }


# Set active garden
@app.post("/api/gardens/{garden_id}/activate")
async def set_active_garden(
    garden_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Set a garden as active."""
    # Deactivate all
    result = await db.execute(select(Garden))
    for g in result.scalars().all():
        g.is_active = False
    
    # Activate target
    result = await db.execute(select(Garden).where(Garden.id == garden_id))
    garden = result.scalar_one_or_none()
    if garden:
        garden.is_active = True
        await db.commit()
        return {"success": True}
    
    return JSONResponse(
        status_code=404,
        content={"success": False, "error": "Garden not found"}
    )


# Update garden
@app.put("/api/gardens/{garden_id}")
async def update_garden(
    garden_id: int,
    name: str = Form(None),
    description: str = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """Update garden name/description."""
    result = await db.execute(select(Garden).where(Garden.id == garden_id))
    garden = result.scalar_one_or_none()
    
    if not garden:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Garden not found"}
        )
    
    if name:
        garden.name = name
    if description is not None:
        garden.description = description
    
    await db.commit()
    return {"success": True}


# Delete garden
@app.delete("/api/gardens/{garden_id}")
async def delete_garden(
    garden_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a garden (cascade deletes plants)."""
    result = await db.execute(select(Garden).where(Garden.id == garden_id))
    garden = result.scalar_one_or_none()
    
    if not garden:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": "Garden not found"}
        )
    
    await db.delete(garden)
    await db.commit()
    return {"success": True}


# Chart data API
@app.get("/api/chart-data")
async def get_chart_data(days: int = 30, db: AsyncSession = Depends(get_db)):
    """Get data for growth trend chart (last N days)."""
    cutoff_date = datetime.now() - timedelta(days=days)
    
    result = await db.execute(
        select(LeafLog)
        .where(LeafLog.created_at >= cutoff_date)
        .order_by(LeafLog.created_at)
    )
    scans = result.scalars().all()
    
    # Format for Chart.js
    data = {
        "labels": [scan.created_at.strftime("%Y-%m-%d %H:%M") for scan in scans],
        "datasets": [{
            "label": "Leaf Area (cm²)",
            "data": [scan.leaf_area_cm2 for scan in scans],
            "borderColor": "rgb(34, 197, 94)",
            "backgroundColor": "rgba(34, 197, 94, 0.1)",
            "fill": True,
            "tension": 0.4
        }]
    }
    
    return data


# Recent scans API
@app.get("/api/recent-scans")
async def get_recent_scans(limit: int = 5, db: AsyncSession = Depends(get_db)):
    """Get recent scans for dashboard table."""
    result = await db.execute(
        select(LeafLog).order_by(desc(LeafLog.created_at)).limit(limit)
    )
    scans = result.scalars().all()
    
    return [
        {
            "id": scan.id,
            "created_at": scan.created_at.isoformat(),
            "leaf_area_cm2": scan.leaf_area_cm2,
            "coin_detected": scan.coin_detected,
            "segmented_image": f"/static/{scan.segmented_image_path}"
        }
        for scan in scans
    ]


# ===== NEW PLANT API ENDPOINTS (Phase 2) =====

# Garden config modal
@app.get("/api/garden-config-modal", response_class=HTMLResponse)
async def garden_config_modal(request: Request):
    """Return garden config modal."""
    return templates.TemplateResponse(
        "components/garden_config_modal.html",
        {"request": request}
    )


# Garden edit modal
@app.get("/api/garden-edit-modal/{garden_id}", response_class=HTMLResponse)
async def garden_edit_modal(
    garden_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Return garden edit modal."""
    result = await db.execute(select(Garden).where(Garden.id == garden_id))
    garden = result.scalar_one_or_none()
    
    if not garden:
        return HTMLResponse(content="<p>Garden not found</p>", status_code=404)
    
    return templates.TemplateResponse(
        "components/garden_edit_modal.html",
        {
            "request": request,
            "garden_id": garden.id,
            "garden_name": garden.name,
            "garden_description": garden.description
        }
    )


# Delete Garden Confirmation Modal
@app.get("/api/delete-garden-modal/{garden_id}", response_class=HTMLResponse)
async def delete_garden_modal(
    garden_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Return delete garden confirmation modal."""
    from sqlalchemy.orm import selectinload
    
    result = await db.execute(
        select(Garden)
        .options(selectinload(Garden.plants))
        .where(Garden.id == garden_id)
    )
    garden = result.scalar_one_or_none()
    
    if not garden:
        return HTMLResponse(content="<p>Garden not found</p>", status_code=404)
    
    return templates.TemplateResponse(
        "components/delete_garden_modal.html",
        {
            "request": request,
            "garden_id": garden.id,
            "garden_name": garden.name,
            "garden_size": f"{garden.rows}×{garden.cols}",
            "plant_count": len(garden.plants)
        }
    )


# Scan Detail Modal
@app.get("/api/scan-detail-modal/{scan_id}", response_class=HTMLResponse)
async def scan_detail_modal(
    scan_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Return scan detail modal."""
    from sqlalchemy.orm import selectinload
    
    result = await db.execute(
        select(LeafLog)
        .options(selectinload(LeafLog.plant))
        .where(LeafLog.id == scan_id)
    )
    scan = result.scalar_one_or_none()
    
    if not scan:
        return HTMLResponse(content="<p>Scan not found</p>", status_code=404)
    
    return templates.TemplateResponse(
        "components/scan_detail_modal.html",
        {
            "request": request,
            "scan": scan
        }
    )


# Add Plant Modal (returns HTML form)
@app.get("/api/add-plant-modal/{x}/{y}", response_class=HTMLResponse)
async def add_plant_modal(
    x: int,
    y: int,
    garden_id: int = None,
    request: Request = None
):
    """Return add plant modal form."""
    return templates.TemplateResponse(
        "components/add_plant_modal.html",
        {
            "request": request,
            "grid_x": x,
            "grid_y": y,
            "garden_id": garden_id
        }
    )


# Scan Modal (returns HTML scanner form)
@app.get("/scan-modal", response_class=HTMLResponse)
async def scan_modal(
    plant_id: int,
    request: Request
):
    """Return scan modal form for specific plant."""
    return templates.TemplateResponse(
        "components/scan_modal.html",
        {
            "request": request,
            "plant_id": plant_id
        }
    )


# Get plant detail for inspector panel
@app.get("/api/plant-detail/{x}/{y}", response_class=HTMLResponse)
async def get_plant_detail(
    x: int,
    y: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get plant details for clicked grid cell."""
    from sqlalchemy.orm import selectinload
    
    result = await db.execute(
        select(Plant)
        .options(selectinload(Plant.scans))  # Eager load scans relationship
        .where(Plant.grid_x == x, Plant.grid_y == y)
    )
    plant = result.scalar_one_or_none()
    
    latest_scan = None
    scans_json = []
    if plant:
        # Get latest scan for this plant
        scan_result = await db.execute(
            select(LeafLog)
            .where(LeafLog.plant_id == plant.id)
            .order_by(desc(LeafLog.created_at))
            .limit(1)
        )
        latest_scan = scan_result.scalar_one_or_none()
        
        # Serialize scans for client-side pagination
        sorted_scans = sorted(plant.scans, key=lambda x: x.created_at, reverse=True)
        for scan in sorted_scans:
            scans_json.append({
                "id": scan.id,
                "leaf_area_cm2": scan.leaf_area_cm2,
                "created_at": scan.created_at.isoformat(),
                "coin_detected": scan.coin_detected,
                "segmented_image_path": scan.segmented_image_path
            })
    
    return templates.TemplateResponse(
        "components/plant_inspector.html",
        {
            "request": request,
            "plant": plant,
            "latest_scan": latest_scan,
            "scans_json": scans_json,
            "now": datetime.now(timezone.utc)
        }
    )


@app.get("/api/plant-detail-by-id/{plant_id}", response_class=HTMLResponse)
async def get_plant_detail_by_id(
    plant_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get plant details by ID."""
    from sqlalchemy.orm import selectinload
    
    result = await db.execute(
        select(Plant)
        .options(selectinload(Plant.scans))
        .where(Plant.id == plant_id)
    )
    plant = result.scalar_one_or_none()
    
    latest_scan = None
    scans_json = []
    if plant:
        scan_result = await db.execute(
            select(LeafLog)
            .where(LeafLog.plant_id == plant.id)
            .order_by(desc(LeafLog.created_at))
            .limit(1)
        )
        latest_scan = scan_result.scalar_one_or_none()
        
        # Serialize scans for client-side pagination
        sorted_scans = sorted(plant.scans, key=lambda x: x.created_at, reverse=True)
        for scan in sorted_scans:
            scans_json.append({
                "id": scan.id,
                "leaf_area_cm2": scan.leaf_area_cm2,
                "created_at": scan.created_at.isoformat(),
                "coin_detected": scan.coin_detected,
                "segmented_image_path": scan.segmented_image_path
            })
    
    return templates.TemplateResponse(
        "components/plant_inspector.html",
        {
            "request": request,
            "plant": plant,
            "latest_scan": latest_scan,
            "scans_json": scans_json,
            "now": datetime.now(timezone.utc)
        }
    )


# Add new plant
@app.post("/api/plants", response_class=HTMLResponse)
async def create_plant(
    name: str = Form(...),
    grid_x: int = Form(...),
    grid_y: int = Form(...),
    garden_id: int = Form(None),
    notes: str = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """Create new plant in grid."""
    try:
        plant = Plant(
            name=name,
            garden_id=garden_id,
            grid_x=grid_x,
            grid_y=grid_y,
            status="healthy",
            planted_at=datetime.now(timezone.utc),
            notes=notes
        )
        db.add(plant)
        await db.commit()
        await db.refresh(plant)
        
        # Return HTMX trigger to reload page
        return HTMLResponse(
            content='<script>window.location.reload();</script>',
            status_code=200
        )
    except Exception as e:
        return HTMLResponse(
            content=f'<div class="border-3 border-brutal-red bg-brutal-red/10 p-4 font-mono"><p class="font-bold text-brutal-red">ERROR: {str(e)}</p></div>',
            status_code=500
        )


# Update scan endpoint to accept plant_id
@app.post("/api/scan-with-plant")
async def scan_with_plant(
    file: UploadFile = File(...),
    plant_id: int = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """Process uploaded image with plant assignment."""
    try:
        # Read image bytes
        image_bytes = await file.read()
        
        # Process with YOLO
        result = process_image(image_bytes, save_dir="app/static/uploads")
        
        if not result["success"]:
            return JSONResponse(
                status_code=400,
                content={"error": result.get("message", "Processing failed")}
            )
        
        # Construct the URL for the segmented image
        segmented_image_url = f"/static/{result['image_paths']['segmented']}"
        
        # Save to database WITH plant_id
        leaf_log = LeafLog(
            plant_id=plant_id,
            leaf_area_cm2=result["total_leaf_area_cm2"],
            coin_detected=result["coin_detected"],
            segmented_image_path=segmented_image_url
        )
        
        db.add(leaf_log)
        await db.commit()
        await db.refresh(leaf_log)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "id": leaf_log.id,
                "leaf_area_cm2": leaf_log.leaf_area_cm2,
                "coin_detected": leaf_log.coin_detected,
                "segmented_image": f"/static/{result['image_paths']['segmented']}",
                "created_at": leaf_log.created_at.isoformat()
            },
            headers={"HX-Trigger": "scanCompleted"}
        )
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )
