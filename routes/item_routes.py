import os
import pathlib
import random
import string
from io import BytesIO

from PIL import Image
from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import login_required, current_user

from app import app, __VIEWER__
from database_functions import get_all_user_locations, \
    get_all_item_types, \
    update_item_by_id, get_item_by_slug, add_images_to_item, delete_images_from_item, set_item_main_image, \
    find_type_by_text, find_user, find_inventory_by_slug, find_location_by_name, \
    get_item_fields, get_all_item_fields, \
    get_all_fields, set_field_status, update_item_fields, \
    set_inventory_default_fields, save_inventory_fieldtemplate, get_user_location_by_id

item_routes = Blueprint('item', __name__)


@item_routes.context_processor
def my_utility_processor():
    def item_tag_to_string(item_tag_list):
        tag_arr = []
        for tag in item_tag_list:
            tag_arr.append(tag.tag.replace("@#$", " "))
        return ",".join(tag_arr)

    return dict(item_tag_to_string=item_tag_to_string)


@item_routes.route('/@<username>/<inventory_slug>/<item_slug>')
def item_with_username_and_inventory(username: str, inventory_slug: str, item_slug: str):

    user_is_authenticated = current_user.is_authenticated
    all_user_locations_ = None
    if user_is_authenticated:
        all_user_locations_ = get_all_user_locations(user=current_user)

    if user_is_authenticated:
        requested_user = current_user
        requested_user_id = requested_user.id

        # check for default inventory
        if inventory_slug == "d":
            inventory_slug = f"default-{username}"

    else:
        requested_user = None
        requested_user_id = None

    # get the inventory to check permissions
    inventory_, user_inventory_ = find_inventory_by_slug(inventory_slug=inventory_slug, user_id=requested_user_id)

    if inventory_ is None:
        return render_template('404.html', message="No such item or you do not have access to this item"), 404

    item_access_level = __VIEWER__
    if user_inventory_ is None:
        if not inventory_.public:
            return render_template('404.html', message="No such item or you do not have access to this item"), 404
    else:
        item_access_level = user_inventory_.access_level

    item_data_ = get_item_by_slug(item_slug=item_slug)
    if item_data_ is not None:
        item_, item_type_string, inventory_item_ = item_data_
    else:
        item_, item_type_string, inventory_item_ = None, None, None

    if item_ is None or inventory_item_ is None:
        return render_template('404.html', message="No such item or you do not have access to this item"), 404

    item_fields = dict(get_item_fields(item_id=item_.id))
    all_item_fields = dict(get_all_item_fields(item_id=item_.id))
    all_fields = dict(get_all_fields())

    item_location = None
    if user_is_authenticated and item_access_level != __VIEWER__:
        user_location = get_user_location_by_id(location_id=item_.location_id, user_id=current_user.id)
        if user_location is not None:
            item_location = user_location

    all_item_types_ = get_all_item_types()

    return render_template('item/item.html', name=username, item_fields=item_fields, all_item_fields=all_item_fields,
                           all_fields=all_fields, inventory_slug=inventory_.slug,
                           item=item_, username=username, item_type=item_type_string,
                           all_item_types=all_item_types_,
                           all_user_locations=all_user_locations_, item_location=item_location,
                           image_dir=app.config['UPLOAD_FOLDER'], item_access_level=item_access_level)


@item_routes.route('/item/edit/<item_id>', methods=['POST'])
@login_required
def edit_item(item_id):
    if request.method == 'POST':
        form_data = dict(request.form)
        del form_data["csrf_token"]
        item_id = form_data["item_id"]
        del form_data["item_id"]

        item_slug = form_data["item_slug"]
        del form_data["item_slug"]

        inventory_slug = form_data["inventory_slug"]
        del form_data["inventory_slug"]

        username = form_data["username"]
        del form_data["username"]

        item_name = request.form.get("item_name")
        item_description = request.form.get("item_description")

        del form_data["item_name"]
        del form_data["item_description"]

        item_tags = request.form.get("item_tags")
        if item_tags != '':
            item_tags = item_tags.strip().split(",")
        else:
            item_tags = []
        del form_data["item_tags"]

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

        new_item_slug = update_item_by_id(item_data=new_item_data, item_id=int(item_id), user=current_user)
        return redirect(url_for('item.item_with_username_and_inventory',
                                username=username,
                                inventory_slug=inventory_slug,
                                item_slug=new_item_slug))


















#
#
# @item_routes.route('/@<username>/item/<item_slug>')
# def item_with_username(username: str, item_slug: str):
#     logged_in_user_id = None
#     item_user_id = None
#     all_user_locations_ = None
#
#     if current_user.is_authenticated:
#         logged_in_user_id = current_user.id
#         all_user_locations_ = get_all_user_locations(user=current_user)
#
#     if username is None:
#         username = current_user.username
#     else:
#         user_ = find_user(username_or_email=username)
#         if user_ is not None:
#             item_user_id = user_.id
#
#     name = username
#
#     all_item_types_ = get_all_item_types()
#
#     if logged_in_user_id is None:
#         item_result = get_item_by_slug(username=username, item_slug=item_slug, user=None)
#     else:
#         item_result = get_item_by_slug(username=username, item_slug=item_slug, user=current_user)
#
#     item_access_level = item_result["access"]
#     item_location = None
#
#     if item_result["status"] == "success":
#         item_ = item_result["item"]
#         item_type_string = item_result["item_type"]
#         inventory_item = item_result["inventory_item"]
#
#         item_fields = dict(get_item_fields(item_id=item_.id))
#         all_item_fields = dict(get_all_item_fields(item_id=item_.id))
#         all_fields = dict(get_all_fields())
#
#         if item_access_level == "owner":
#             user_location = get_user_location(user=current_user, location_id=item_.location_id)
#             if user_location is not None:
#                 item_location = user_location[0]
#
#     elif item_access_level == "denied":
#         return render_template('404.html', message="You do not have access to this item"), 404
#     else:
#         return render_template('404.html', message="No item found"), 404
#
#     return render_template('item/item.html', name=name, item_fields=item_fields, all_item_fields=all_item_fields,
#                            all_fields=all_fields,
#                            item=item_, username=username, item_type=item_type_string,
#                            all_item_types=all_item_types_,
#                            all_user_locations=all_user_locations_, item_location=item_location,
#                            image_dir=app.config['UPLOAD_FOLDER'], item_access_level=item_access_level)


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


# @item_routes.route('/item/<item_slug>')
# @login_required
# def item(item_slug: str):
#     username = current_user.username
#     return redirect(url_for('item.item_with_username', username=username, item_slug=item_slug).replace('%40', '@'))


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

        return redirect(url_for('items.items_with_username_and_inventory',
                                username=current_user.username, inventory_slug=inventory_slug))


@item_routes.route("/item/images/remove", methods=["POST"])
def delete_images():
    if request.method == 'POST':
        json_data = request.json
        item_id = json_data['item_id']
        item_slug = json_data['item_slug']
        inventory_slug = json_data['inventory_slug']
        username = json_data['username']
        image_list = json_data['image_id_list']

        delete_images_from_item(item_id=item_id, image_ids=image_list, user=current_user)

        return redirect(url_for('item.item_with_username_and_inventory',
                                username=username,
                                inventory_slug=inventory_slug,
                                item_slug=item_slug))


@item_routes.route("/item/images/setmainimage", methods=["POST"])
def set_main_image():
    if request.method == 'POST':
        json_data = request.json
        main_image = json_data['main_image']
        item_slug = json_data['item_slug']
        inventory_slug = json_data['inventory_slug']
        item_id = json_data['item_id']
        username = json_data['username']

        main_image = main_image.replace('/uploads/', '')

        set_item_main_image(main_image_url=main_image, item_id=item_id, user=current_user)

        return redirect(url_for('item.item_with_username_and_inventory',
                                username=username,
                                inventory_slug=inventory_slug,
                                item_slug=item_slug))


@item_routes.route("/item/images/upload", methods=["POST"])
def upload():
    new_filename_list = []

    username = request.form.get("username")
    item_id = request.form.get("item_id")
    item_slug = request.form.get("item_slug")
    inventory_slug = request.form.get("inventory_slug")

    uploaded_files = request.files.getlist("file[]")
    for file in uploaded_files:
        file_name, file_extension = os.path.splitext(file.filename)

        new_filename = ''.join(random.choices(string.ascii_lowercase, k=15)) + file_extension
        new_filename_list.append(new_filename)

        in_mem_file = BytesIO(file.read())
        image = Image.open(in_mem_file)
        image = image.convert('RGB')
        image.thumbnail((600, 600))
        in_mem_file = BytesIO()
        image.save(in_mem_file, format="JPEG")
        in_mem_file.seek(0)

        pathlib.Path(os.path.join(app.config['UPLOAD_FOLDER'], new_filename)).write_bytes(
            in_mem_file.getbuffer().tobytes())

    add_images_to_item(item_id=item_id, filenames=new_filename_list, user=current_user)

    return redirect(url_for('item.item_with_username_and_inventory',
                            username=username,
                            inventory_slug=inventory_slug,
                            item_slug=item_slug))
