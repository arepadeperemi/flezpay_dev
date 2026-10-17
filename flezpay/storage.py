import os
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile
from storages.backends.s3boto3 import S3Boto3Storage

def compress_image_if_needed(content, max_size_mb=0.5):
    max_size_bytes = max_size_mb * 1024 * 1024
    
    try:
        content.seek(0, 2)
        file_size = content.tell()
        content.seek(0)
    except (AttributeError, OSError):
        return content

    if file_size <= max_size_bytes:
        return content

    try:
        img = Image.open(content)
        
        # Only attempt to compress supported web formats
        if img.format not in ['JPEG', 'PNG', 'WEBP']:
            content.seek(0)
            return content

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        output = BytesIO()
        img.save(output, format='JPEG', quality=80, optimize=True)
        
        # If still too large, compress more aggressively
        if output.tell() > max_size_bytes:
            output = BytesIO()
            img.save(output, format='JPEG', quality=60, optimize=True)

        output.seek(0)
        
        new_name = content.name
        if new_name:
            new_name = os.path.splitext(new_name)[0] + '.jpg'
            
        return ContentFile(output.read(), name=new_name)
    except Exception:
        content.seek(0)
        return content

class CompressedS3Boto3Storage(S3Boto3Storage):
    def _save(self, name, content):
        content = compress_image_if_needed(content)
        return super()._save(name, content)

class ProductStorage(CompressedS3Boto3Storage):
    location = "products"
    file_overwrite = False

class BrandStorage(CompressedS3Boto3Storage):
    location = "brand"
    file_overwrite = False

class AvatarStorage(CompressedS3Boto3Storage):
    location = "avatar"
    file_overwrite = False

class LivechatStorage(CompressedS3Boto3Storage):
    location = "livechat_attachments"
    file_overwrite = False

class GrowthMediaStorage(S3Boto3Storage):
    """Storage for campaign cover images and videos. Videos are NOT compressed."""
    location = "growth_media"
    file_overwrite = False

    def _save(self, name, content):
        # Only compress images — pass videos through unchanged
        content_type = getattr(content, 'content_type', '')
        if content_type and content_type.startswith('image/'):
            content = compress_image_if_needed(content, max_size_mb=1.0)
        return super()._save(name, content)


class StoreVideoStorage(S3Boto3Storage):
    """Storage for uploaded store video files. Pass through without compression."""
    location = "store_videos"
    file_overwrite = False

    def _save(self, name, content):
        return super()._save(name, content)

