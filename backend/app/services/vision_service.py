from app.services import claude_service


def analyze_engineering_image(image_bytes: bytes, media_type: str) -> dict:
    return claude_service.analyze_image(image_bytes, media_type)
