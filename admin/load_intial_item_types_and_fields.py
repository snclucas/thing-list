import csv
import os


from app import app
from database_functions import add_user, drop_then_create, get_or_create

from models import ItemType,  Field


with app.app_context():
    drop_then_create()


def load_fields():
    path = os.getcwd()
    file_path = os.path.realpath(__file__)
    item_types_csv = f"{path}/data/fields.csv"

    with open(item_types_csv, newline='') as csvfile:
        line_count = 0
        reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        for row in reader:
            print(', '.join(row))
            if line_count != 0:
                get_or_create(model=Field, field=row[0], description=row[1], type=row[2], data=row[3])
            line_count += 1


def load_item_types():
    path = os.getcwd()
    file_path = os.path.realpath(__file__)
    item_types_csv = f"{path}/data/items_types.csv"

    with open(item_types_csv, newline='') as csvfile:
        line_count = 0
        reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        for row in reader:
            print(', '.join(row))
            if line_count != 0:
                get_or_create(model=ItemType, name=row[0], user_id=1)
            line_count += 1


if __name__ == '__main__':
    load_item_types()
    load_fields()
