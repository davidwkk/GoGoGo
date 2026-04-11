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

### 1. New Image Storage Utility

**File**: `backend/app/utils/image_storage.py`

```python
# Key functions:
- download_image(url: str, target_path: Path) -> bool: Downloads a single image, returns success
- save_itinerary_images(itinerary_json: dict, trip_id: int) -> dict: Downloads all images for a trip, returns updated itinerary dict
```

Image storage location: `/app/uploads/images/{trip_id}/`

- e.g., `/app/uploads/images/123/activity_0.jpg`
- e.g., `/app/uploads/images/123/hotel_0.jpg`

### 2. New Media Serving Endpoint

**File**: `backend/app/api/routes/media.py`

- `GET /api/v1/media/{path:path}` — serves files from `/app/uploads/`
- Returns 404 if file not found

Register in `main.py`:

```python
app.include_router(media.router, prefix="/api/v1/media", tags=["media"])
```

### 3. Modify Trip Service

**File**: `backend/app/services/trip_service.py`

In `save_trip()`:

1. After creating the itinerary JSON, call `save_itinerary_images(itinerary_json, trip.id)`
2. Pass the updated JSON (with local image paths) to `create_trip()`

### 4. Update Docker Compose

**File**: `docker-compose.yml`

Add volume mount for uploads directory:

```yaml
backend:
  volumes:
    - ./backend/uploads:/app/uploads # Add this
```

### 5. Create Uploads Directory

**File**: `backend/uploads/images/.gitkeep`

Create the directory structure with a `.gitkeep` to ensure the folder exists in git.

## Critical Files

| File                                   | Change                                     |
| -------------------------------------- | ------------------------------------------ |
| `backend/app/utils/image_storage.py`   | **NEW** — image download and storage logic |
| `backend/app/api/routes/media.py`      | **NEW** — static file serving endpoint     |
| `backend/app/services/trip_service.py` | MODIFY — call image storage before saving  |
| `backend/app/main.py`                  | MODIFY — register media router             |
| `docker-compose.yml`                   | MODIFY — add uploads volume mount          |
| `backend/uploads/images/.gitkeep`      | **NEW** — directory placeholder            |

## Reused Patterns

- `httpx.AsyncClient` for async image downloading (same as tool modules)
- Module-level logging with Loguru (same as other service modules)
- `save_trip()` is the integration point (follows existing pattern)

## Image Download Logic

```python
# Activity images:
itinerary["days"][day_idx][period][act_idx]["image_url"]
itinerary["days"][day_idx][period][act_idx]["thumbnail_url"]

# Hotel images:
itinerary["hotels"][hotel_idx]["image_url"]
```

Only download if:

- URL exists and is not None/empty
- URL is from a trusted domain (Wikipedia `upload.wikimedia.org`, Google CDN `*.googleusercontent.com`, or picsum CDN)
- Download fails should be silent (image_url becomes None, frontend will use fallback)

## Verification

1. Start the backend with `docker-compose up backend`
2. Create a trip plan via chat
3. Verify images are saved in `backend/uploads/images/{trip_id}/`
4. Verify the trip GET response returns local paths instead of external URLs
5. Verify `GET /api/v1/media/images/{trip_id}/...` returns the image file
6. Run existing tests: `docker-compose exec backend pytest`
