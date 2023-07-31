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
    set_inventory_default_fields, get_user_templates, save_inventory_fieldtemplate, get_item_custom_field_data, \
    get_users_for_inventory
from models import FieldTemplate

items_routes = Blueprint('items', __name__)


@items_routes.context_processor
def my_utility_processor():
    def item_tag_to_string(item_tag_list):
        tag_arr = []
        for tag in item_tag_list:
            tag_arr.append(tag.tag.replace("@#$", " "))
        return ",".join(tag_arr)

    return dict(item_tag_to_string=item_tag_to_string)


@items_routes.route('/items/load', methods=['POST'])
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
                                              user=current_user, custom_fields=custom_fields)
                    line_count += 1

    username = current_user.username
    return redirect(url_for('item.items_with_username', username=username).replace('%40', '@'))


@items_routes.route('/items/move', methods=['POST'])
@login_required
def items_move():
    if request.method == 'POST':
        json_data = request.json
        item_ids = json_data['item_ids']
        username = json_data['username']
        to_inventory_id = json_data['to_inventory_id']
        move_items(item_ids=item_ids, user=current_user, inventory_id=int(to_inventory_id))
        return redirect(url_for('item.items_with_username', username=username).replace('%40', '@'))


@items_routes.route('/items/save-pdf', methods=['POST'])
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


@items_routes.route('/items/save', methods=['POST'])
@login_required
def items_save():

    inventory_slug = request.form.get("inventory_slug")

    filename = f"{current_user.username}_{inventory_slug}_export.csv"

    request_params = _process_url_query(req_=request, inventory_user=current_user)
    inventory_id, inventory_, inventory_default_fields = _get_inventory(inventory_slug=inventory_slug,
                                                                        logged_in_user_id=current_user.id)
    data_dict, item_id_list = find_items_query(current_user, current_user, inventory_id, request_params=request_params)

    dd = get_item_custom_field_data(user_id=current_user.id, item_list=item_id_list)

    field_set = set()

    for dn, dv in dd.items():
        dv_lower = [x.lower() for x in list(dv.keys())]
        field_set.update(dv_lower)

    csv_headers = ["#name", "description", "tags", "type", "location", "specific location"]
    csv_headers.extend(field_set)

    csv_list = [csv_headers]

    for row in data_dict:
        item_ = row["item"]
        if item_.id in dd:
            wewe = dd[item_.id]
        else:
            wewe = {}
        temp = [
            item_.name,
            item_.description,
            ",".join([x.tag.replace("@#$", " ") for x in item_.tags]),
            row["types"],
            row["location"],
            item_.specific_location,
        ]
        # add the custom values
        wewe = {k.lower(): v for k, v in wewe.items()}
        for k in field_set:
            if k in wewe:
                temp.append(wewe[k])
            else:
                temp.append("")
        csv_list.append(temp)

    si = StringIO()
    cw = csv.writer(si)
    cw.writerows(csv_list)
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename={filename}"
    output.headers["Content-types"] = "text/csv"
    return output


@items_routes.route('/items')
@login_required
def items():
    username = current_user.username
    return redirect(url_for('items.items_with_username', username=username).replace('%40', '@'))


@items_routes.route('/@<username>/items')
def items_with_username(username=None):
    return items_with_username_and_inventory(username=username, inventory_slug="all")


@items_routes.route('/@<username>/<inventory_slug>')
def items_with_username_and_inventory(username=None, inventory_slug=None):
    user_is_authenticated = current_user.is_authenticated
    logged_in_user = None
    requested_user = None
    logged_in_user_id = None
    requested_user_id = None
    logged_in_username = None
    requested_username = None

    # remove spurious whitespace (if any)
    inventory_slug = inventory_slug.strip()

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

    if inventory_ is None and inventory_slug != "all":
        return render_template('404.html', message="No such inventory"), 404

    item_types_ = get_all_item_types()
    all_fields = dict(get_all_fields())

    request_params = _process_url_query(req_=request, inventory_user=requested_user)
    data_dict, item_id_list = find_items_query(requested_user, logged_in_user, inventory_id,
                                               request_params=request_params)

    inventory_templates = get_user_templates(user=current_user)

    users_in_this_inventory = get_users_for_inventory(inventory_id=inventory_id, current_user_id=current_user.id)

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
                           all_user_inventories=all_user_inventories, users_in_this_inventory=users_in_this_inventory,
                           user_is_authenticated=user_is_authenticated, inventory_slug=inventory_slug)


@items_routes.route('/items/<inventory_slug>')
def items_with_inventory(inventory_slug=None):
    return items_with_username_and_inventory(username=None, inventory_slug=inventory_slug)


def _get_inventory(inventory_slug: str, logged_in_user_id):

    if inventory_slug == "default":
        inventory_slug_to_use = f"default-{current_user.username}"
    elif inventory_slug is None or inventory_slug == '':
        inventory_slug_to_use = 'all'
    else:
        inventory_slug_to_use = inventory_slug

    field_template_ = None

    if inventory_slug_to_use != "all":
        inventory_, user_inventory_ = find_inventory_by_slug(inventory_slug=inventory_slug_to_use,
                                                             user_id=logged_in_user_id)
        if inventory_ is None:
            return None, None, None
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

    item_id_list = []
    data_dict = []
    for i in items_:
        item_id_list.append(i[0].id)
        dat = {
                "item": i[0],
                "types": i[1],
                "location": i[2]
            }
        if inventory_id is not None:
            dat["user_inventory"] = i[3]
        data_dict.append(
            dat
        )

    return data_dict, item_id_list


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


@items_routes.route('/item/delete', methods=['POST'])
@login_required
def del_items():
    print(request.json)
    if request.method == 'POST':
        json_data = request.json
        item_ids = json_data['item_ids']
        username = json_data['username']
        delete_items(item_ids=item_ids, user=current_user)
        return redirect(url_for('item.items_with_username', username=username).replace('%40', '@'))
