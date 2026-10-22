import io
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from tests.conftest import tree_id


def jpeg_with_exif(size=(3000, 2000)) -> bytes:
    img = Image.new("RGB", size, (40, 120, 60))
    exif = Image.Exif()
    exif[0x010F] = "CameraMaker"
    gps = {1: "S", 2: (28.0, 15.0, 43.0), 3: "W", 4: (52.0, 24.0, 21.0)}
    exif[0x8825] = gps
    exif.get_ifd(0x8769)[0x9003] = "2026:10:20 08:10:00"
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


async def test_upload_strips_metadata_and_resizes(admin, seeded, _tmp_uploads):
    tid = await tree_id(seeded, "ARV-001")
    r = await admin.post(
        f"/api/admin/trees/{tid}/photos",
        files={"file": ("foto.jpg", jpeg_with_exif(), "image/jpeg")},
        data={"caption": "Dia do plantio"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    # EXIF DateTimeOriginal (08:10 São Paulo) used as taken_at.
    assert datetime.fromisoformat(body["taken_at"]) == datetime(2026, 10, 20, 11, 10, tzinfo=timezone.utc)
    stored = _tmp_uploads / body["url"].removeprefix("/media/")
    img = Image.open(stored)
    assert max(img.size) == 1600
    assert not img.getexif()  # GPS and camera data removed
    assert b"CameraMaker" not in stored.read_bytes()

    listed = (await admin.get(f"/api/admin/trees/{tid}/photos")).json()
    assert listed[0]["caption"] == "Dia do plantio"
    assert (await admin.delete(f"/api/admin/trees/{tid}/photos/{body['id']}")).status_code == 204
    assert not Path(stored).exists()


async def test_upload_rejects_non_images(admin, seeded):
    tid = await tree_id(seeded, "ARV-001")
    r = await admin.post(
        f"/api/admin/trees/{tid}/photos", files={"file": ("foto.jpg", b"<?php echo 1; ?>", "image/jpeg")}
    )
    assert r.status_code == 422


async def test_upload_size_limit(admin, seeded, settings, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    tid = await tree_id(seeded, "ARV-001")
    r = await admin.post(
        f"/api/admin/trees/{tid}/photos", files={"file": ("big.jpg", b"\xff" * (1024 * 1024 + 10), "image/jpeg")}
    )
    assert r.status_code == 413


async def test_species_photo_shows_on_public_page(admin, seeded, make_client):
    species = (await admin.get("/api/admin/species")).json()[0]
    buf = io.BytesIO()
    Image.new("RGBA", (400, 300), (10, 200, 10, 128)).save(buf, format="PNG")
    r = await admin.post(f"/api/admin/species/{species['id']}/photo", files={"file": ("s.png", buf.getvalue(), "image/png")})
    assert r.status_code == 200 and r.json()["photo_path"].startswith("species/")
    pid = (await admin.get("/api/admin/trees")).json()[0]["public_id"]  # ARV-001 is araçá, first species
    async with make_client() as c:
        public = (await c.get(f"/api/trees/{pid}")).json()
    assert public["species"]["photo_url"] == f"/media/{r.json()['photo_path']}"
