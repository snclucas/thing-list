import bleach
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from database_functions import get_user_inventories, delete_item_from_inventory, \
    add_item_to_inventory, \
    get_items_for_inventory, find_inventory, get_all_item_types, find_inventory_by_slug, \
    find_user_by_username, edit_inventory_data, get_all_user_locations, \
    add_new_inventory, delete_inventory

inv = Blueprint('inv', __name__)

__PUBLIC__ = 2
__PRIVATE__ = 2


@inv.context_processor
def my_utility_processor():
    def item_tag_to_string(item_tag_list):
        tag_arr = []
        for tag in item_tag_list:
            tag_arr.append(tag.tag.replace("@#$", " "))
        return ",".join(tag_arr)
    return dict(item_tag_to_string=item_tag_to_string)


@inv.route('/inventories', methods=['GET'])
@login_required
def inventories():
    user_is_authenticated = current_user.is_authenticated
    user_invs = get_user_inventories(logged_in_user=current_user, requested_username=None, access_level=-1)

    number_inventories = len(user_invs) - 1  # -1 to count for the 'hidden' default inventory

    return render_template('inventory/inventories.html', username=current_user.username, inventories=user_invs,
                           user_is_authenticated=user_is_authenticated, number_inventories=number_inventories)


@inv.route('/@<username>/inventories')
def inventories_for_username(username):
    user_is_authenticated = current_user.is_authenticated

    if user_is_authenticated:
        user_invs = get_user_inventories(logged_in_user=current_user, requested_username=username, access_level=-1)
    else:
        user_invs = get_user_inventories(logged_in_user=None, requested_username=username, access_level=-1)

    number_inventories = len(user_invs) - 1  # -1 to count for the 'hidden' default inventory

    return render_template('inventory/inventories.html', inventories=user_invs,
                           user_is_authenticated=user_is_authenticated, number_inventories=number_inventories)


@inv.route('/inventory/<inventory_id>')
@login_required
def inventory(inventory_id: int):
    inventory_ = find_inventory(inventory_id=inventory_id)

    return redirect(url_for('inv.inventory_by_slug', inventory_slug=inventory_.slug))


@inv.route('/inventory/add', methods=['POST'])
@login_required
def add_inventory():
    if request.method == 'POST':
        inventory_name_ = bleach.clean(request.form.get("inventory_name"))
        inventory_description_ = bleach.clean(request.form.get("inventory_description"))
        add_new_inventory(name=inventory_name_, description=inventory_description_, user=current_user)
    return redirect(url_for('inv.inventories'))


@inv.route('/inventory/delete', methods=['POST'])
@login_required
def del_inventory():
    if request.method == 'POST':
        json_data = request.json
        username = json_data['username']
        inventory_id = json_data['inventory_id']
        inventory_slug = json_data['inventory_slug']
        delete_inventory(inventory_id=inventory_id, user=current_user)

        # raise abort(500, message="Unable to determine domain permissions")

        return redirect(url_for('inv.inventory_by_slug', username=username, inventory_slug=inventory_slug))


@inv.route('/inventory/edit', methods=['POST'])
@login_required
def edit_inventory():
    if request.method == 'POST':
        inventory_id = bleach.clean(request.form.get("inventory_id"))
        inventory_name = bleach.clean(request.form.get("inventory_name"))
        inventory_description = bleach.clean(request.form.get("inventory_description"))

        edit_inventory_data(user=current_user, inventory_id=int(inventory_id), name=inventory_name,
                            description=inventory_description,
                            access_level=int(0))
        return redirect(url_for('inv.inventories'))


@inv.route('/inventory/@<username>/<inventory_slug>')
def inventory_by_slug(username: str, inventory_slug: str):
    user_is_authenticated = current_user.is_authenticated

    if user_is_authenticated:
        inventory_, user_inventory_ = \
            find_inventory_by_slug(inventory_slug=inventory_slug, user_id=current_user.id)
        user_locations_ = get_all_user_locations(user=current_user)
    else:
        inventory_, user_inventory_ = find_inventory_by_slug(inventory_slug=inventory_slug)
        user_locations_ = None

    inventory_access_level = user_inventory_.access_level
    all_access_levels = {
        0: "Private",
        2: "Public"
    }

    if user_inventory_ is None:
        return render_template('404.html', message="You do not have access to this inventory"), 404
    else:

        item_types_ = get_all_item_types()

        user_ = find_user_by_username(username=username)
        # work on this to show public inventories
        is_inventory_owner = (user_inventory_.access_level == 0)

        if user_ in inventory_.users:
            items_ = get_items_for_inventory(inventory_id=inventory_.id, user=current_user)
            return render_template('inventory/inventory.html', username=username,
                                   inventory_items={"items": items_, "inventory": inventory_},
                                   item_types=item_types_,
                                   user_locations=user_locations_, inventory_access_level=inventory_access_level,
                                   all_access_levels=all_access_levels,
                                   is_inventory_owner=is_inventory_owner, user_is_authenticated=user_is_authenticated)
        else:
            return render_template('404.html'), 404


@inv.route('/inventory/@<username>/<inventory_slug>/delete/<item_id>', methods=['POST'])
@login_required
def delete_from_inventory(username: str, inventory_slug, item_id):
    inventory_ = find_inventory_by_slug(inventory_slug=inventory_slug, user_id=current_user)
    delete_item_from_inventory(user=current_user, inventory_id=int(inventory_.id), item_id=int(item_id))
    return redirect(url_for('inv.inventory_by_slug', username=username, inventory_slug=inventory_.slug))


@inv.route('/inventory/additem', methods=['POST'])
@login_required
def add_to_inventory():

    if request.method == 'POST':
        item_name = request.form.get("name")
        item_description = request.form.get("description")
        inventory_id = request.form.get("inventory_id")

        username = request.form.get("username")
        inventory_slug = request.form.get("inventory_slug")
        item_type = request.form.get("type")
        item_location = request.form.get("location_id")
        item_specific_location = request.form.get("specific_location")
        item_tags = request.form.get("tags")
        item_tags = item_tags.split(",")

        item_custom_fields = dict(request.form)
        del item_custom_fields['username']
        del item_custom_fields['name']
        del item_custom_fields['id']
        del item_custom_fields['description']
        del item_custom_fields['inventory_id']
        del item_custom_fields['location_id']
        del item_custom_fields['inventory_slug']
        del item_custom_fields['csrf_token']
        del item_custom_fields['tags']

        add_item_to_inventory(item_name=item_name, item_desc=item_description, item_type=item_type,
                              item_tags=item_tags,
                              item_location=int(item_location), item_specific_location=item_specific_location,
                              inventory_id=inventory_id, user=current_user,
                              custom_fields=item_custom_fields)

        if inventory_id == '' or inventory_slug == '' or inventory_id is None or inventory_slug is None:
            return redirect(url_for('item.items_with_username',
                                    username=username))
        else:
            return redirect(url_for('item.items_with_username_and_inventory',
                                    username=username, inventory_slug=inventory_slug))
