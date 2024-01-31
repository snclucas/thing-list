from PIL import Image


def correct_image_orientation(image: Image):
    if hasattr(image, '_getexif'):
        exifdata = image._getexif()
        try:
            orientation = exifdata.get(274)
        except:
            orientation = 1
    else:
        orientation = 1

    if orientation == 1:
        pass
    elif orientation == 2:
        image = image.transpose(Image.FLIP_LEFT_RIGHT)
    elif orientation == 3:
        image = image.rotate(180)
    elif orientation == 4:
        image = image.rotate(180)
    elif orientation == 5:
        image = image.rotate(-90)
    elif orientation == 6:
        image = image.rotate(-90)
    elif orientation == 7:
        image = image.rotate(90)
    elif orientation == 8:
        image = image.rotate(90)

    return image
