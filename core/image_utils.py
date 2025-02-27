from PIL import Image
from io import BytesIO
import os
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys

def optimize_image(image_field):
    """
    Optimize an image to ensure it's under 20KB while maintaining quality
    
    Args:
        image_field: The image field from a model (e.g., profile.profile_picture)
    
    Returns:
        The optimized image field
    """
    if not image_field:
        return image_field
    
    # Open the image
    img = Image.open(image_field)
    
    # Get the original format
    format = img.format or 'JPEG'
    
    # Calculate current size in KB
    current_size = image_field.size / 1024
    
    # If already under 20KB, return as is
    if current_size <= 20:
        return image_field
    
    # Default parameters
    quality = 90
    max_size = (200, 200)
    
    # Function to resize and compress image
    def resize_and_compress():
        output = BytesIO()
        
        # Resize image while maintaining aspect ratio
        img.thumbnail(max_size, Image.LANCZOS)
        
        # Save with compression
        if format == 'JPEG' or format == 'JPG':
            img.save(output, format=format, quality=quality, optimize=True)
        elif format == 'PNG':
            img.save(output, format=format, optimize=True, quality=quality)
        else:
            # Convert to JPEG if not a common format
            img.save(output, format='JPEG', quality=quality, optimize=True)
            format = 'JPEG'
        
        output.seek(0)
        return output, output.getbuffer().nbytes
    
    # Initial resize and compress
    output, new_size = resize_and_compress()
    
    # If still too large, reduce quality and/or max size iteratively
    while new_size / 1024 > 20 and quality > 20:
        quality -= 10
        output, new_size = resize_and_compress()
    
    # If still too large, reduce dimensions further
    while new_size / 1024 > 20 and max_size[0] > 100:
        max_size = (max_size[0] - 25, max_size[1] - 25)
        output, new_size = resize_and_compress()
    
    # Create a new InMemoryUploadedFile from the optimized image
    filename = os.path.basename(image_field.name)
    optimized_image = InMemoryUploadedFile(
        output,
        'ImageField',
        f"{os.path.splitext(filename)[0]}.{format.lower()}",
        f'image/{format.lower()}',
        new_size,
        None
    )
    
    return optimized_image


def process_profile_picture(form_cleaned_data):
    """
    Process a profile picture from form cleaned data to ensure it's under 20KB
    
    Args:
        form_cleaned_data: The cleaned_data dictionary from a form
    
    Returns:
        The processed image or None if no image
    """
    image = form_cleaned_data.get('profile_picture')
    if not image:
        return None
    
    # Check if this is a file upload or a model field
    if hasattr(image, 'file') and hasattr(image, 'size'):
        # It's a file upload
        if image.size <= 20 * 1024:  # 20KB
            return image
        
        # Process the image
        img = Image.open(image)
        
        # Determine format
        format = img.format or 'JPEG'
        
        # Resize and compress
        img.thumbnail((200, 200), Image.LANCZOS)
        
        # Save to BytesIO
        output = BytesIO()
        
        # Adjust quality until size is under 20KB
        quality = 80
        while True:
            output.seek(0)
            output.truncate(0)
            
            if format == 'JPEG' or format == 'JPG':
                img.save(output, format=format, quality=quality, optimize=True)
            elif format == 'PNG':
                img.save(output, format=format, optimize=True)
            else:
                # Convert to JPEG if not a common format
                img.save(output, format='JPEG', quality=quality, optimize=True)
                format = 'JPEG'
            
            # Check size
            size = output.tell()
            if size <= 20 * 1024 or quality <= 10:
                break
            
            # Reduce quality
            quality -= 10
        
        # Reset buffer position
        output.seek(0)
        
        # Create new InMemoryUploadedFile
        return InMemoryUploadedFile(
            output,
            'ImageField',
            f"{image.name.split('.')[0]}.{format.lower()}",
            f'image/{format.lower()}',
            size,
            None
        )
    
    return image