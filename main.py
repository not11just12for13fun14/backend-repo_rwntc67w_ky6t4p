import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import datetime
import base64

app = FastAPI(title="DreamCraft API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProductIn(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    image: Optional[str] = Field(None, description="Image URL or data URI")


class ProductOut(ProductIn):
    id: Optional[str] = None
    created_at: Optional[datetime] = None


class ArtRequest(BaseModel):
    prompt: str
    style: Optional[str] = Field(
        default="dreamy", description="Optional style hint: dreamy, watercolor, neon, ink, clay"
    )
    aspect: Optional[str] = Field(default="1:1", description="Aspect ratio e.g. 1:1, 3:4, 16:9")


class ArtResponse(BaseModel):
    image: str  # data URL or hosted URL
    prompt: str
    style: str
    provider: str


@app.get("/")
def read_root():
    return {"message": "DreamCraft Backend is live"}


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }

    try:
        from database import db

        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = getattr(db, "name", None) or "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


@app.get("/api/products", response_model=List[ProductOut])
def list_products():
    try:
        from database import get_documents
        docs = get_documents("product", {})
        result: List[ProductOut] = []
        for d in docs:
            result.append(
                ProductOut(
                    id=str(d.get("_id")),
                    title=d.get("title"),
                    description=d.get("description"),
                    price=float(d.get("price", 0)),
                    category=d.get("category", "craft"),
                    image=d.get("image"),
                    created_at=d.get("created_at"),
                )
            )
        return result
    except Exception:
        # If DB is not available, return an empty list (no in-memory store for persistence)
        return []


@app.post("/api/products", response_model=str)
def create_product(product: ProductIn):
    try:
        from database import create_document
        product_dict = product.model_dump()
        new_id = create_document("product", product_dict)
        return new_id
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database not available: {str(e)}")


def _svg_placeholder(prompt: str, style: str, aspect: str) -> str:
    import hashlib

    # Create color seed
    seed = hashlib.sha256((prompt + style + aspect).encode()).hexdigest()
    c1 = f"#{seed[:6]}"
    c2 = f"#{seed[6:12]}"
    c3 = f"#{seed[12:18]}"

    # Aspect handling
    w, h = (1024, 1024)
    if aspect in ("16:9", "16-9"):
        w, h = 1280, 720
    elif aspect in ("3:4", "3-4"):
        w, h = 960, 1280

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">
    <defs>
      <radialGradient id="g" cx="50%" cy="50%" r="70%">
        <stop offset="0%" stop-color="{c1}"/>
        <stop offset="50%" stop-color="{c2}"/>
        <stop offset="100%" stop-color="{c3}"/>
      </radialGradient>
      <filter id="f" x="-20%" y="-20%" width="140%" height="140%">
        <feTurbulence type="fractalNoise" baseFrequency="0.012" numOctaves="3"/>
        <feColorMatrix type="saturate" values="1.2"/>
        <feBlend mode="overlay"/>
      </filter>
    </defs>
    <rect width="100%" height="100%" fill="url(#g)"/>
    <rect width="100%" height="100%" filter="url(#f)" opacity="0.35"/>
    <g font-family="Inter,Arial" font-size="28" fill="white" opacity="0.9">
      <text x="50%" y="50%" text-anchor="middle">{prompt[:80]}</text>
      <text x="50%" y="55%" text-anchor="middle" opacity="0.7">style: {style}</text>
    </g>
  </svg>'''
    data = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
    return f"data:image/svg+xml;base64,{data}"


@app.post("/api/generate-art", response_model=ArtResponse)
def generate_art(req: ArtRequest):
    # Placeholder generation; if an external provider key is present, you could integrate here.
    provider = "placeholder"
    image_url = _svg_placeholder(req.prompt, req.style or "dreamy", req.aspect or "1:1")
    return ArtResponse(image=image_url, prompt=req.prompt, style=req.style or "dreamy", provider=provider)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
