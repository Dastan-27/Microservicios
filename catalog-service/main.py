from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn


class Space(BaseModel):
    id: int
    name: str
    city: str
    capacity: int
    price_per_hour: float


app = FastAPI(title="Coworking Catalog Service", version="1.0.0")

SPACES = [
    Space(
        id=1,
        name="Centro Coworking",
        city="Ciudad de México",
        capacity=40,
        price_per_hour=15.0,
    ),
    Space(
        id=2,
        name="Norte Coworking",
        city="Monterrey",
        capacity=25,
        price_per_hour=12.5,
    ),
    Space(
        id=3,
        name="Costa Coworking",
        city="Guadalajara",
        capacity=30,
        price_per_hour=10.0,
    ),
]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "catalog-service"}


@app.get("/spaces", response_model=list[Space])
def list_spaces() -> list[Space]:
    return SPACES


@app.get("/spaces/{space_id}", response_model=Space)
def get_space(space_id: int) -> Space:
    for space in SPACES:
        if space.id == space_id:
            return space
    raise HTTPException(status_code=404, detail="Coworking space not found")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
