"""Check captured pixels before acknowledging a disposable delivery sample."""

import argparse
import io
import json
from pathlib import Path
import subprocess
import time
from PIL import Image


def classify(rgb):
    r, g, b = rgb
    if min(rgb) > 75 and max(rgb) - min(rgb) < 18:
        return "white_wool"
    if r > 30 and r > g * 1.18 and g > b * 1.15:
        return "dirt"
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        for meta in sorted(args.root.glob("candidate-*.json")):
            if meta.name.endswith(".checked.json"):
                continue
            checked = meta.with_name(meta.stem + ".checked.json")
            if checked.exists():
                continue
            row = json.loads(meta.read_text())
            ack = args.root / f"capture-{row['index']}.json"
            if ack.exists():
                checked.write_text(
                    json.dumps({"skipped": "Earlier pixel-matched capture retained"})
                )
                continue
            image = Image.open(args.root / row["filename"]).convert("RGB")
            if row["kind"] == "world":
                p = row["pixel"]
                x = round(p["x"] / p["width"] * image.width)
                y = round((p["height"] - p["y"]) / p["height"] * image.height)
                pixels = list(
                    image.crop((x - 1, y - 1, x + 2, y + 2)).get_flattened_data()
                )
                rgb = [sum(p[c] for p in pixels) / len(pixels) for c in range(3)]
                result = {
                    "matched": classify(rgb) == row["expected"],
                    "rgb": rgb,
                    "classification": classify(rgb),
                }
            else:
                r = row["dom"]["rect"]
                bounds = (
                    max(0, int(r["left"]) - 4),
                    max(0, int(r["top"]) - 4),
                    min(image.width, int(r["right"]) + 4),
                    min(image.height, int(r["bottom"]) + 4),
                )
                if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
                    checked.write_text(
                        json.dumps(
                            {
                                "matched": False,
                                "reason": "Message outside captured viewport",
                            }
                        )
                    )
                    continue
                crop = image.crop(bounds)
                data = io.BytesIO()
                crop.resize(
                    (crop.width * 3, crop.height * 3), Image.Resampling.LANCZOS
                ).save(data, format="PNG")
                text = subprocess.check_output(
                    ["tesseract", "stdin", "stdout", "--psm", "6"],
                    input=data.getvalue(),
                    stderr=subprocess.DEVNULL,
                ).decode()
                result = {
                    "matched": row["message"]["text"] in " ".join(text.split()),
                    "ocr_text": text,
                }
            checked.write_text(json.dumps(result, indent=2))
            if result["matched"]:
                tmp = ack.with_suffix(".tmp")
                tmp.write_text(
                    json.dumps({**row, "pixel_validation": result}, indent=2)
                )
                tmp.replace(ack)
        report = args.root / "report.json"
        if report.exists() and json.loads(report.read_text()).get("shutdown"):
            return
        time.sleep(0.03)
    raise TimeoutError("Capture validation bounded wait expired")


if __name__ == "__main__":
    main()
