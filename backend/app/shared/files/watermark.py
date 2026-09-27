"""Burns a VISIBLE watermark (timestamp + GPS coordinates) onto evidence
photos and videos before they're stored — confirmed requirement (Mateo, Sept 2026):
"las imagenes que se suban deben quedar como marcadas como si fuera marca de
agua con la georeferenciación." This is deliberately baked into the pixels,
not just EXIF/DB metadata, so the watermark survives export/sharing and
can't be silently stripped.
"""
import io
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

# Image and video formats we know how to watermark. Other formats (PDF, etc.)
# are outside the evidence upload allow-list.
WATERMARKABLE_MIME_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
VIDEO_MIME_TYPES = {"video/mp4", "video/quicktime", "video/webm", "video/mpeg"}


def _format_coords(lat: float, lon: float) -> str:
    lat_dir = "N" if lat >= 0 else "S"
    lon_dir = "E" if lon >= 0 else "W"
    return f"{abs(lat):.6f}°{lat_dir}, {abs(lon):.6f}°{lon_dir}"


def apply_gps_watermark(
    image_bytes: bytes, *, latitude: float | None, longitude: float | None, captured_at: datetime | None,
) -> bytes:
    """Returns new JPEG bytes with a semi-transparent bar + text burned into
    the bottom of the image showing GPS coordinates and timestamp. If no GPS
    is available, only the timestamp is stamped (still visibly marked as
    field evidence, per the same requirement)."""
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    width, height = image.size

    bar_height = max(36, int(height * 0.06))
    # Composite a translucent black bar at the bottom of the image.
    base = image.convert("RGBA")
    bar = Image.new("RGBA", (width, bar_height), (0, 0, 0, 150))
    base.alpha_composite(bar, (0, height - bar_height))
    image = base.convert("RGB")

    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", size=max(14, bar_height // 3))
    except OSError:
        font = ImageFont.load_default()

    timestamp_str = (captured_at or datetime.utcnow()).strftime("%Y-%m-%d %H:%M UTC")
    if latitude is not None and longitude is not None:
        text = f"{_format_coords(latitude, longitude)}  ·  {timestamp_str}"
    else:
        text = f"Sin GPS disponible  ·  {timestamp_str}"

    padding = 10
    draw.text((padding, height - bar_height + padding // 2), text, fill=(255, 255, 255), font=font)

    out = io.BytesIO()
    image.save(out, format="JPEG", quality=90)
    return out.getvalue()


def apply_video_watermark(
    video_bytes: bytes, *, latitude: float | None, longitude: float | None, captured_at: datetime | None,
) -> bytes:
    """Burn the evidence label into every video frame using ffmpeg."""
    timestamp = (captured_at or datetime.utcnow()).strftime("%Y-%m-%d %H:%M UTC")
    location = _format_coords(latitude, longitude) if latitude is not None and longitude is not None else "Sin GPS disponible"
    label = f"{location}  ·  {timestamp}"
    with tempfile.TemporaryDirectory(prefix="evidence-video-") as directory:
        source = Path(directory) / "source"
        output = Path(directory) / "watermarked.mp4"
        textfile = Path(directory) / "watermark.txt"
        source.write_bytes(video_bytes)
        textfile.write_text(label, encoding="utf-8")
        command = ["ffmpeg", "-y", "-i", str(source), "-vf", "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:textfile=" + str(textfile) + ":fontcolor=white:fontsize=24:box=1:boxcolor=black@0.6:boxborderw=10:x=20:y=h-th-20", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-c:a", "aac", "-movflags", "+faststart", str(output)]
        result = subprocess.run(command, capture_output=True, timeout=180)
        if result.returncode != 0 or not output.exists():
            raise RuntimeError(result.stderr.decode("utf-8", errors="replace")[-500:])
        return output.read_bytes()
