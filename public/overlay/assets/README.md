## Overlay Event Images

Place your kiosk event images here. Expected filenames:

| File | Used for state | Description |
|------|---------------|-------------|
| `image_verify.jpg` | processing | Shown immediately on barcode scan |
| `cannot_accept.jpg` | no_match | Shown when item is not recognized |
| `barcode_not_qr.jpg` | qr_not_allowed | Shown when QR code scanned instead of barcode |
| `deposit_waiting.jpg` | deposit_waiting | Shown while waiting for item deposit |
| `item_not_detected.jpg` | recycle_failure | Shown when ToF sensor doesn't detect item |

Images should be sized to your display resolution (e.g. 800x480 or 1920x1080).
If images are not present, the overlay falls back to CSS-based icons and text.
