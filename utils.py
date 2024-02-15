from PIL import Image
from enum import Enum, unique


@unique
class ExifOrientation(Enum):
    ORIENTATION_1 = 1
    ORIENTATION_2 = 2
    ORIENTATION_3 = 3
    ORIENTATION_4 = 4
    ORIENTATION_5 = 5
    ORIENTATION_6 = 6
    ORIENTATION_7 = 7
    ORIENTATION_8 = 8


def correct_image_orientation(image: Image) -> Image:
    """
    Corrects the orientation of the image based on the EXIF data.

    Args:
        image (PIL.Image.Image): The image to correct the orientation of.

    Returns:
        PIL.Image.Image: The corrected image.

    """
    orientation = ExifOrientation.ORIENTATION_1  # default value

    if hasattr(image, '_getexif') and callable(image._getexif):
        exifdata = image._getexif()
        try:
            orientation_value = exifdata.get(274)
            orientation = ExifOrientation(orientation_value)
        except (AttributeError, ValueError):
            pass  # Leave orientation as default (1) if can't get the value or it's invalid

    if orientation == ExifOrientation.ORIENTATION_1:
        pass
    elif orientation in {ExifOrientation.ORIENTATION_2}:
        image = image.transpose(Image.FLIP_LEFT_RIGHT)
    elif orientation in {ExifOrientation.ORIENTATION_3, ExifOrientation.ORIENTATION_4}:
        image = image.rotate(180)
    elif orientation in {ExifOrientation.ORIENTATION_5, ExifOrientation.ORIENTATION_6}:
        image = image.rotate(-90)
    elif orientation in {ExifOrientation.ORIENTATION_7, ExifOrientation.ORIENTATION_8}:
        image = image.rotate(90)

    return image
