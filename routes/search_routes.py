from flask import Blueprint, render_template, request
from flask_login import login_required, current_user

from database_functions import search_items
import strings

search_routes = Blueprint('search', __name__)


@search_routes.context_processor
def inject_front_end_strings():
    """
    Inject strings into the front end
    :return:
    """
    return dict(strings=strings)


@search_routes.route(rule='/search', methods=['GET', 'POST'])
@login_required
def search():
    query_string = request.args.get('q')
    if query_string is not None:
        items = search_items(query=query_string, user_id=current_user.id)
        return render_template(template_name_or_list='search/search.html', items=items, q=query_string, username=current_user.username)
    return render_template('search/search.html')
