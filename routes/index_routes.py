from flask import Blueprint, render_template
from flask_login import login_required, current_user

from database_functions import get_user_inventories, get_user_item_count, get_user_templates, get_user_locations, \
    get_all_itemtypes_for_user

main = Blueprint('main', __name__)


@main.route('/')
def index():
    return render_template('index.html')


@main.route('/privacy-policy')
def privacy():
    return render_template('privacy_policy.html')


@main.route('/@<username>')
@login_required
def profile(username):
    num_item_types = len(get_all_itemtypes_for_user(user_id=current_user.id, string_list=False))
    num_items = get_user_item_count(user_id=current_user.id)
    num_field_templates = len(get_user_templates(user=current_user))
    num_user_locations = len(get_user_locations(user=current_user))
    user_inventories = get_user_inventories(logged_in_user=current_user, requested_username=None)
    user_notifications = current_user.notifications
    # -1 to remove the default inventory
    return render_template('profile.html', name=current_user.username, num_items=num_items,
                           num_item_types=num_item_types, username=username,
                           num_field_templates=num_field_templates, num_user_locations=num_user_locations,
                           user_notifications=user_notifications,
                           num_inventories=len(list(user_inventories))-1)
