
from flask import Blueprint, render_template, redirect, url_for, request

from models import Item
from app import app

search_routes = Blueprint('search', __name__)


@search_routes.route('/search')
def search():
    query_string = request.args.get('q')

    if query_string is not None:

        body = {
            "query": {
                "multi_match": {
                    "query": query_string,
                    "fields": ["content", "title"]
                }
            }
        }

        page = request.args.get('page', 1, type=int)
        posts, total = Item.search(query_string, page,
                                   app.config['POSTS_PER_PAGE'])
        next_url = url_for('search_routes.search', q=query_string, page=page + 1) \
            if total > page * app.config['POSTS_PER_PAGE'] else None
        prev_url = url_for('search_routes.search', q=query_string, page=page - 1) \
            if page > 1 else None

        return render_template('search/search.html')
    else:
        return render_template('search/search.html')
