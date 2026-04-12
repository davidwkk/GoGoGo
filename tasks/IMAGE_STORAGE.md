# Plan: Save Attraction and Hotel Images Locally

## Context

Currently, attraction images (from Wikipedia API) and hotel images (from SerpAPI) are stored as external URLs in the trip itinerary JSON. These external URLs can:

- Become unavailable (404 errors)
- Get rate-limited
- Be blocked by CORS
- Change or be removed

The frontend already has fallback logic (Wikipedia re-search, then Picsum), but this adds latency and is unreliable.

**Goal**: Before saving a trip to the database, download all attraction and hotel images from their external URLs and save them locally. Then update the itinerary to reference local paths instead of external URLs.

## Implementation

### 1. Add Image Storage Logic to Trip Service

**File**: `backend/app/services/trip_service.py`

Add two helper functions (no new file needed):

```python
async def download_image(url: str, target_path: Path) -> bool:
    """Download a single image. Returns True on success, False on failure."""
    ...

async def save_itinerary_images(itinerary_json: dict, trip_id: int) -> dict:
    """Download all images for a trip, update URLs to local paths, return updated dict."""
    ...
```

Image storage location: `/app/uploads/images/{trip_id}/`

- e.g., `/app/uploads/images/123/activity_0.jpg`
- e.g., `/app/uploads/images/123/hotel_0.jpg`

In `save_trip()`:

1. After creating the itinerary JSON, call `save_itinerary_images(itinerary_json, trip.id)`
2. Pass the updated JSON (with local image paths) to `create_trip()`

Image URL fields:

- `itinerary["days"][day_idx][period][act_idx]["image_url"]`
- `itinerary["days"][day_idx][period][act_idx]["thumbnail_url"]`
- `itinerary["hotels"][hotel_idx]["image_url"]`

Only download if URL exists and is not None/empty. Failures are silent—`image_url` becomes `None` and frontend uses its fallback.

### 2. Mount StaticFiles in FastAPI

**File**: `backend/app/main.py`

Replace the media router with a simple StaticFiles mount:

```python
from fastapi.staticfiles import StaticFiles

app.mount("/api/v1/uploads", StaticFiles(directory="/app/uploads"), name="uploads")
```

Images will be served at `GET /api/v1/uploads/images/{trip_id}/...` automatically.

### 3. Update Docker Compose

**File**: `docker-compose.yml`

Add volume mount for uploads directory:

```yaml
backend:
  volumes:
    - ./backend/uploads:/app/uploads # Add this
```

### 4. Create Uploads Directory

**File**: `backend/uploads/images/.gitkeep`

Create the directory structure with a `.gitkeep` to ensure the folder exists in git.

## Critical Files

| File                                   | Change                                                        |
| -------------------------------------- | ------------------------------------------------------------- |
| `backend/app/services/trip_service.py` | MODIFY — add download_image and save_itinerary_images helpers |
| `backend/app/main.py`                  | MODIFY — mount StaticFiles for /uploads                       |
| `docker-compose.yml`                   | MODIFY — add uploads volume mount                             |
| `backend/uploads/images/.gitkeep`      | **NEW** — directory placeholder                               |

## Reused Patterns

- `httpx.AsyncClient` for async image downloading (same as tool modules)
- Module-level logging with Loguru (same as other service modules)
- `save_trip()` is the integration point (follows existing pattern)

## Verification

1. Start the backend with `docker-compose up backend`
2. Create a trip plan via chat
3. Verify images are saved in `backend/uploads/images/{trip_id}/`
4. Verify the trip GET response returns local paths instead of external URLs
5. Verify `GET /api/v1/uploads/images/{trip_id}/...` returns the image file
6. Run existing tests: `docker-compose exec backend pytest`
