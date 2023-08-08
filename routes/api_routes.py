
from flask import Blueprint
from flask_login import login_required, current_user

from database_functions import get_all_itemtypes_for_user

api_routes = Blueprint('api', __name__)


@api_routes.context_processor
def my_utility_processor():
    def item_tag_to_string(item_tag_list):
        tag_arr = []
        for tag in item_tag_list:
            tag_arr.append(tag.tag.replace("@#$", " "))
        return ",".join(tag_arr)

    return dict(item_tag_to_string=item_tag_to_string)


@api_routes.route('/api/item-types', methods=['GET'])
@login_required
def user_item_types():
    user_itemtypes_ = get_all_itemtypes_for_user(user_id=current_user.id)
    return user_itemtypes_


# @api_routes.route('/api/locations', methods=['GET'])
# @login_required
# def user_locations():
#     user_locations_ = get_all_itemtypes_for_user(user_id=current_user.id)
#     return user_locations_
