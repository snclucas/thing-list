from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user

from database_functions import get_user_inventories, get_user_item_count, get_user_templates, get_user_locations, \
    get_all_itemtypes_for_user, find_user_by_username, delete_notification_by_id, get_number_user_locations

main = Blueprint('main', __name__)


@main.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.profile', username=current_user.username))
    else:
        return render_template('index.html')


@main.route('/about')
def about():
    return render_template('about.html')

@main.route('/privacy-policy')
def privacy():
    return render_template('privacy_policy.html')


@main.route('/delete-notification>', methods=['POST'])
@login_required
def del_notification():
    if request.method == 'POST':
        json_data = request.json
        username = json_data['username']
        notification_id = json_data['notification_id']
        delete_notification_by_id(notification_id=notification_id, user=current_user)

        return redirect(url_for('main.profile', username=username))


@main.route('/@<username>')
@login_required
def profile(username):
    user_is_authenticated = current_user.is_authenticated
    current_user_id = None
    requesting_user_id = None

    # -1 for the default None item type
    num_item_types = len(get_all_itemtypes_for_user(user_id=current_user.id, string_list=False)) - 1
    num_items = get_user_item_count(user_id=current_user.id)
    num_field_templates = len(get_user_templates(user=current_user))
    num_user_locations = get_number_user_locations(user_id=current_user.id)

    if user_is_authenticated:
        current_user_id = current_user.id
        if username != current_user.username:
            user_ = find_user_by_username(username=username)
            if user_ is not None:
                requesting_user_id = user_.id
        else:
            requesting_user_id = current_user.id

    user_inventories = get_user_inventories(current_user_id=current_user_id, requesting_user_id=requesting_user_id,
                                            access_level=-1)

    user_notifications = current_user.notifications
    # -1 to remove the default inventory
    return render_template('profile.html', name=current_user.username, num_items=num_items,
                           num_item_types=num_item_types, username=username,
                           num_field_templates=num_field_templates, num_user_locations=num_user_locations,
                           user_notifications=user_notifications, user_is_authenticated=user_is_authenticated,
                           num_inventories=len(list(user_inventories))-1)
