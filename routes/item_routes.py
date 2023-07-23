import os
import pathlib
import random
import string
from io import BytesIO
from io import StringIO
import csv

import pdfkit
from flask import make_response

from PIL import Image
from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import login_required, current_user

from app import app
from database_functions import get_all_user_locations, find_items, \
    get_all_item_types, get_user_location, \
    update_item_by_id, get_item_by_slug, add_images_to_item, delete_images_from_item, set_item_main_image, \
    find_type_by_text, find_user, find_inventory_by_slug, find_location_by_name, \
    add_item_to_inventory, final_all_user_inventories, delete_items, move_items, get_item_fields, get_all_item_fields, \
    get_all_fields, set_field_status, update_item_fields, add_new_user_itemtype, \
    set_inventory_default_fields, get_user_templates, save_inventory_fieldtemplate
from models import FieldTemplate

item_routes = Blueprint('item', __name__)


@item_routes.context_processor
def my_utility_processor():
    def item_tag_to_string(item_tag_list):
        tag_arr = []
        for tag in item_tag_list:
            tag_arr.append(tag.tag.replace("@#$", " "))
        return ",".join(tag_arr)

    return dict(item_tag_to_string=item_tag_to_string)


@item_routes.route('/items/load', methods=['POST'])
@login_required
def items_load():
    if request.method == 'POST':
        to_inventory_id = request.form.get("add_to_inventory")

        if request.files:
            uploaded_file = request.files['file']  # This line uses the same variable and worked fine
            filepath = os.path.join(app.config['FILE_UPLOADS'], uploaded_file.filename)
            uploaded_file.save(filepath)

            with open(filepath) as csvfile:
                line_count = 0
                reader = csv.reader(csvfile, delimiter=',', quotechar='"')
                column_headers = None
                custom_fields = {}
                for row in reader:
                    number_columns = len(row)
                    if line_count == 0:  # Header
                        column_headers = row

                    else:
                        if len(row) < number_columns:
                            break

                        item_name = row[0]
                        item_description = row[1]
                        item_type = row[2]
                        item_tags = row[3]

                        # add item types
                        add_new_user_itemtype(name=item_type, user_id=current_user.id)

                        tag_array = item_tags.split(",")

                        remaining_data_columns = number_columns - 4
                        for data_column_index in range(0, remaining_data_columns):
                            custom_field_name = column_headers[4 + data_column_index]
                            custom_field_value = row[4 + data_column_index]
                            custom_fields[custom_field_name] = custom_field_value

                        for t in range(len(tag_array)):
                            tag_array[t] = tag_array[t].strip()
                            tag_array[t] = tag_array[t].replace(" ", "@#$")

                        add_item_to_inventory(item_name=item_name, item_desc=item_description,
                                              item_type=item_type,
                                              item_tags=tag_array, inventory_id=to_inventory_id,
                                              user_id=current_user.id, custom_fields=custom_fields)
                    line_count += 1

    username = current_user.username
    return redirect(url_for('item.items_with_username', username=username).replace('%40', '@'))


@item_routes.route('/items/move', methods=['POST'])
@login_required
def items_move():
    if request.method == 'POST':
        json_data = request.json
        item_ids = json_data['item_ids']
        username = json_data['username']
        to_inventory_id = json_data['to_inventory_id']
        move_items(item_ids=item_ids, user=current_user, inventory_id=int(to_inventory_id))
        return redirect(url_for('item.items_with_username', username=username).replace('%40', '@'))


@item_routes.route('/items/save-pdf', methods=['POST'])
@login_required
def items_save_pdf():
    if request.method == 'POST':
        json_data = request.json
        inventory_slug = json_data['inventory_slug']
        username = json_data['username']

        html = items_with_username_and_inventory(username="simon", inventory_slug="simon-s-inventory")

        config = pdfkit.configuration(
            wkhtmltopdf='C:\\Users\\simon clucas\\Downloads\\wkhtmltox-0.12.6-1.msvc2015-win64\\bin\\wkhtmltopdf.exe')

        pdf = pdfkit.from_string(html, False, configuration=config)
        response = make_response(pdf)
        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = "inline; filename=output.pdf"
        return response


@item_routes.route('/items/save', methods=['POST'])
@login_required
def items_save():

    inventory_slug = request.form.get("inventory_slug")

    filename = f"{current_user.username}_{inventory_slug}_export.csv"

    request_params = _process_url_query(req_=request, inventory_user=current_user)
    inventory_id, inventory_, inventory_default_fields = _get_inventory(inventory_slug=inventory_slug,
                                                                        logged_in_user_id=current_user.id)
    data_dict = find_items_query(current_user, current_user, inventory_id, request_params=request_params)

    csv_list = [["#Name", "Description", "Tags", "Type", "Location",
                 "Specific location", "Manufacturer", "Model", "Serial number"]]

    for row in data_dict:
        item_ = row["item"]
        temp = [
            item_.name,
            item_.description,
            ",".join([x.tag.replace("@#$", " ") for x in item_.tags]),
            row["types"],
            row["location"],
            item_.specific_location,
        ]
        csv_list.append(temp)

    si = StringIO()
    cw = csv.writer(si)
    cw.writerows(csv_list)
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename={filename}"
    output.headers["Content-types"] = "text/csv"
    return output


@item_routes.route('/items')
@login_required
def items():
    username = current_user.username
    return redirect(url_for('item.items_with_username', username=username).replace('%40', '@'))


@item_routes.route('/@<username>/items')
def items_with_username(username=None):
    return items_with_username_and_inventory(username=username, inventory_slug="all")


@item_routes.route('/items/<inventory_slug>')
def items_with_inventory(inventory_slug=None):
    return items_with_username_and_inventory(username=None, inventory_slug=inventory_slug)





@item_routes.route('/@<username>/<inventory_slug>')
def items_with_username_and_inventory(username=None, inventory_slug=None):
    user_is_authenticated = current_user.is_authenticated
    logged_in_user = None
    requested_user = None
    logged_in_user_id = None
    requested_user_id = None
    logged_in_username = None
    requested_username = None

    user_locations_ = None

    if user_is_authenticated:
        logged_in_user = current_user
        user_locations_ = get_all_user_locations(user=logged_in_user)

    if username is None:
        username = current_user.username
    else:
        requested_user = find_user(username_or_email=username)
        if requested_user is not None:
            username = requested_user.username
        else:
            return render_template('404.html', message="Not found"), 404

    if logged_in_user is not None:
        logged_in_user_id = logged_in_user.id

    if requested_user is not None:
        requested_user_id = requested_user.id
    else:
        requested_user = current_user

    if user_is_authenticated:
        all_user_inventories = final_all_user_inventories(user=current_user)
    else:
        all_user_inventories = None

    inventory_id, inventory_, inventory_field_template = _get_inventory(inventory_slug= inventory_slug,
                                                                        logged_in_user_id=logged_in_user_id)

    item_types_ = get_all_item_types()
    all_fields = dict(get_all_fields())

    request_params = _process_url_query(req_=request, inventory_user=requested_user)
    data_dict = find_items_query(requested_user, logged_in_user, inventory_id, request_params=request_params)

    inventory_templates = get_user_templates(user=current_user)

    return render_template('item/items.html',
                           username=username,
                           inventory=inventory_,
                           data_dict=data_dict,
                           item_types=item_types_,
                           inventory_templates=inventory_templates,
                           inventory_field_template=inventory_field_template,
                           tags=request_params["requested_tag_strings"],
                           all_fields=all_fields,
                           user_locations=user_locations_,
                           item_specific_location=request_params["requested_item_specific_location"],
                           selected_item_type=request_params["requested_item_type_string"],
                           selected_item_location_id=request_params["requested_item_location_id"],
                           all_user_inventories=all_user_inventories,
                           user_is_authenticated=user_is_authenticated, inventory_slug=inventory_slug)


def _get_inventory(inventory_slug: str, logged_in_user_id):

    if inventory_slug == "default":
        inventory_slug_to_use = f"default-{current_user.username}"
    else:
        inventory_slug_to_use = inventory_slug

    field_template_ = None

    if inventory_slug != "all":
        inventory_, user_inventory_ = find_inventory_by_slug(inventory_slug=inventory_slug_to_use,
                                                             user_id=logged_in_user_id)
        if inventory_ is None:
            return render_template('404.html', message="No inventory found"), 404
        else:
            inventory_id = inventory_.id

            field_template_id_ = inventory_.field_template

            if field_template_id_ is not None:
                field_template_ = FieldTemplate.query.filter_by(id=field_template_id_).one_or_none()

    else:
        inventory_id = None
        inventory_ = None

    return inventory_id, inventory_, field_template_


def find_items_query(requested_user, logged_in_user, inventory_id, request_params):

    items_ = find_items(inventory_id=inventory_id,
                        item_type=request_params["requested_item_type_id"],
                        item_location=request_params["requested_item_location_id"],
                        item_tags=request_params["requested_tag_strings"],
                        item_specific_location=request_params["requested_item_specific_location"],
                        request_user=requested_user,
                        logged_in_user=logged_in_user)

    data_dict = []
    for i in items_:
        data_dict.append(
            {
                "item": i[0],
                "types": i[1],
                "location": i[2],
                "user_inventory": i[3]
            }
        )

    return data_dict


def _process_url_query(req_, inventory_user):
    requested_item_type_string = req_.args.get('type')
    requested_tag_strings = req_.args.get('tags')
    requested_item_location_string = req_.args.get('location')
    requested_item_specific_location = req_.args.get('specific_location')

    # convert the text 'location_' to an id
    location_model = find_location_by_name(location_name=requested_item_location_string)
    if location_model is not None:
        requested_item_location_id = location_model.id
    else:
        requested_item_location_id = None

    # convert the text 'types' to an id
    if requested_item_type_string is not None:
        item_type_ = find_type_by_text(type_text=requested_item_type_string, user_id=inventory_user.id)
        if item_type_ is not None:
            requested_item_type_id = item_type_.id
        else:
            requested_item_type_id = None
    else:
        requested_item_type_id = None

    if requested_item_type_string is None:
        requested_item_type_string = ""

    if requested_tag_strings is None:
        requested_tag_strings = ""

    return {
        "requested_tag_strings": requested_tag_strings,
        "requested_item_type_id": requested_item_type_id,
        "requested_item_type_string": requested_item_type_string,
        "requested_item_location_id": requested_item_location_id,
        "requested_item_location_string": requested_item_location_string,
        "requested_item_specific_location": requested_item_specific_location
    }


@item_routes.route('/item/<item_slug>')
@login_required
def item(item_slug: str):
    username = current_user.username
    return redirect(url_for('item.item_with_username', username=username, item_slug=item_slug).replace('%40', '@'))


@item_routes.route('/@<username>/item/<item_slug>')
def item_with_username(username: str, item_slug: str):
    logged_in_user_id = None
    item_user_id = None
    all_user_locations_ = None

    if current_user.is_authenticated:
        logged_in_user_id = current_user.id
        all_user_locations_ = get_all_user_locations(user=current_user)

    if username is None:
        username = current_user.username
    else:
        user_ = find_user(username_or_email=username)
        if user_ is not None:
            item_user_id = user_.id

    name = username

    all_item_types_ = get_all_item_types()

    if logged_in_user_id is None:
        item_result = get_item_by_slug(username=username, item_slug=item_slug, user=None)
    else:
        item_result = get_item_by_slug(username=username, item_slug=item_slug, user=current_user)

    item_access_level = item_result["access"]
    item_location = None

    if item_result["status"] == "success":
        item_ = item_result["item"]
        item_type_string = item_result["item_type"]
        inventory_item = item_result["inventory_item"]

        item_fields = dict(get_item_fields(item_id=item_.id))
        all_item_fields = dict(get_all_item_fields(item_id=item_.id))
        all_fields = dict(get_all_fields())

        if item_access_level == "owner":
            user_location = get_user_location(user=current_user, location_id=item_.location_id)
            if user_location is not None:
                item_location = user_location[0]

    elif item_access_level == "denied":
        return render_template('404.html', message="You do not have access to this item"), 404
    else:
        return render_template('404.html', message="No item found"), 404

    return render_template('item/item.html', name=name, item_fields=item_fields, all_item_fields=all_item_fields,
                           all_fields=all_fields,
                           item=item_, username=username, item_type=item_type_string,
                           all_item_types=all_item_types_,
                           all_user_locations=all_user_locations_, item_location=item_location,
                           image_dir=app.config['UPLOAD_FOLDER'], item_access_level=item_access_level)


@item_routes.route('/item/fields', methods=['POST'])
@login_required
def edit_item_fields():
    if request.method == 'POST':
        json_data = request.json
        item_id = json_data['item_id']
        field_ids = json_data['field_ids']
        set_field_status(item_id, field_ids, is_visible=True)

    return True


@item_routes.route('/default-inventory_fields', methods=['POST'])
@login_required
def edit_inv_default_fields():
    if request.method == 'POST':
        json_data = request.json
        inventory_id = json_data['inventory_id']
        field_ids = json_data['field_ids']

        field_ids = [str(x) for x in field_ids]

        set_inventory_default_fields(inventory_id=inventory_id, user=current_user, default_fields=field_ids)

    return True


@item_routes.route('/inventory/save-inventory-template', methods=['POST'])
@login_required
def save_inventory_template():
    if request.method == 'POST':
        form_data = dict(request.form)
        inventory_id = form_data['inventory_id']

        inventory_slug = form_data['inventory_slug']
        inventory_template = form_data['inventory_template']
        if inventory_template == '-1':
            inventory_template = None
        save_inventory_fieldtemplate(inventory_id=inventory_id,
                                     inventory_template=inventory_template, user_id=current_user.id)

        return redirect(url_for('item.items_with_username_and_inventory',
                                username=current_user.username, inventory_slug=inventory_slug))


@item_routes.route('/item/edit/<item_id>', methods=['POST'])
@login_required
def edit_item(item_id):
    if request.method == 'POST':
        form_data = dict(request.form)
        del form_data["csrf_token"]
        item_id = form_data["item_id"]
        del form_data["item_id"]

        username = form_data["username"]
        del form_data["username"]

        item_name = request.form.get("item_name")
        item_description = request.form.get("item_description")

        del form_data["item_name"]
        del form_data["item_description"]

        item_tags = request.form.get("item_tags")
        item_tags = item_tags.split(",")
        del form_data["item_tags"]

        username = request.form.get("username")
        item_type = request.form.get("item_type")
        item_location = request.form.get("item_location")
        item_specific_location = request.form.get("item_specific_location")

        del form_data["item_type"]
        del form_data["item_location"]
        del form_data["item_specific_location"]

        form_data = {int(k): v for k, v in form_data.items()}

        update_item_fields(data=form_data, item_id=int(item_id))

        new_item_data = {
            "id": item_id,
            "name": item_name,
            "description": item_description,
            "item_type": item_type,
            "item_location": item_location,
            "item_specific_location": item_specific_location,
            "item_tags": item_tags
        }

        item_result = update_item_by_id(item_data=new_item_data, item_id=int(item_id), user=current_user)
        return redirect(url_for('item.item', username=username, item_slug=item_result["item"].slug))


@item_routes.route("/item/images/remove", methods=["POST"])
def delete_images():
    if request.method == 'POST':
        json_data = request.json
        item_id = json_data['item_id']
        item_slug = json_data['item_slug']
        username = json_data['username']
        image_list = json_data['image_id_list']

        delete_images_from_item(item_id=item_id, image_ids=image_list, user=current_user)

        return redirect(url_for('item.item', username=username, item_slug=item_slug))


@item_routes.route("/item/images/setmainimage", methods=["POST"])
def set_main_image():
    if request.method == 'POST':
        json_data = request.json
        main_image = json_data['main_image']
        item_slug = json_data['item_slug']
        item_id = json_data['item_id']
        username = json_data['username']

        main_image = main_image.replace('/uploads/', '')

        set_item_main_image(main_image_url=main_image, item_id=item_id, user=current_user)

        return redirect(url_for('item.item', username=username, item_slug=item_slug))


@item_routes.route("/item/images/upload", methods=["POST"])
def upload():
    new_filename_list = []

    username = request.form.get("username")
    item_id = request.form.get("item_id")
    item_slug = request.form.get("item_slug")

    uploaded_files = request.files.getlist("file[]")
    for file in uploaded_files:
        file_name, file_extension = os.path.splitext(file.filename)

        new_filename = ''.join(random.choices(string.ascii_lowercase, k=15)) + file_extension
        new_filename_list.append(new_filename)

        in_mem_file = BytesIO(file.read())
        image = Image.open(in_mem_file)
        image.thumbnail((600, 600))
        in_mem_file = BytesIO()
        image.save(in_mem_file, format="JPEG")
        in_mem_file.seek(0)

        pathlib.Path(os.path.join(app.config['UPLOAD_FOLDER'], new_filename)).write_bytes(
            in_mem_file.getbuffer().tobytes())

    add_images_to_item(item_id=item_id, filenames=new_filename_list, user=current_user)

    return redirect(url_for('item.item', username=username, item_slug=item_slug))


@item_routes.route('/item/delete', methods=['POST'])
@login_required
def del_items():
    if request.method == 'POST':
        json_data = request.json
        item_ids = json_data['item_ids']
        username = json_data['username']
        delete_items(item_ids=item_ids, user=current_user)
        return redirect(url_for('item.items_with_username', username=username).replace('%40', '@'))
